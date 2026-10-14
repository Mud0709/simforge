"""Integrator study on projectile motion with linear drag.

References: each scheme's exact discrete solution for the velocity equation, the
methods' stability theory, the exact continuous solution, and a published value for
RK4's stability interval.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from simforge.numerics.convergence import MIN_FIT_POINTS
from simforge.physics.projectile import integrator_study as study
from simforge.physics.projectile.analytical import ProjectileSetup, flight_time

G = 9.80665
HALVING = [0.2 / 2**i for i in range(8)]


def setup(
    b: float = 1.0, m: float = 1.0, h: float = 0.0, angle: float = 45.0, v0: float = 20.0
) -> ProjectileSetup:
    return ProjectileSetup(v0, math.radians(angle), h, m, b, G)


# --- Stability theory -----------------------------------------------------------------


def test_rk4_stability_limit_matches_literature() -> None:
    # Real stability interval of classical RK4 is about [-2.785, 0]
    # (Hairer & Wanner, Solving ODEs II, Sec. IV.2).
    limit = study.THEORY["rk4"].stability_limit_kh
    assert limit == pytest.approx(2.785293563, abs=1e-8)
    assert study.amplification_factor("rk4", limit) == pytest.approx(1.0, abs=1e-12)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("method", "kh", "expected"),
    [
        ("euler", 1.9, "stable"),
        ("euler", 2.0, "marginal"),
        ("euler", 2.1, "unstable"),
        ("rk4", 2.7, "stable"),
        ("rk4", 2.9, "unstable"),
        ("verlet", 0.1, "stable"),
        ("verlet", 1e3, "stable"),
    ],
)
def test_stability_classification(method: study.MethodName, kh: float, expected: str) -> None:
    assert study.classify_stability(method, kh) == expected


@pytest.mark.parametrize("method", ["euler", "rk4", "verlet"])
@pytest.mark.parametrize("kh", [0.05, 0.5, 1.9, 2.5, 3.0, 10.0])
def test_horizontal_velocity_follows_exact_discrete_solution(
    method: study.MethodName, kh: float
) -> None:
    """vx' = -k vx is linear and homogeneous, so every scheme gives vx_n = vx0 R(-kh)^n
    exactly. This tests the implementations inside *and* beyond their stability limits."""
    s = setup(b=2.0)
    n = 30
    sol = study.integrate(s, method, kh / s.k, n)
    expected = s.vx0 * study.amplification_factor(method, kh) ** np.arange(n + 1)
    np.testing.assert_allclose(sol.y[:, 2], expected, rtol=1e-12, atol=1e-300)


def test_behaviour_on_either_side_of_euler_limit() -> None:
    s = setup(b=2.0)
    below = study.integrate(s, "euler", 1.9 / s.k, 200).y[:, 2]
    above = study.integrate(s, "euler", 2.1 / s.k, 200).y[:, 2]
    assert abs(below[-1]) < 1e-3 * abs(below[0])  # decays, alternating in sign
    assert abs(above[-1]) > 1e3 * abs(above[0])  # grows, alternating in sign
    assert np.all(np.sign(above[1:]) != np.sign(above[:-1]))


def test_rk4_instability_grows_without_sign_alternation() -> None:
    s = setup(b=2.0)
    vx = study.integrate(s, "rk4", 2.9 / s.k, 200).y[:, 2]
    assert abs(vx[-1]) > 10 * abs(vx[0])
    assert np.all(vx > 0)  # R(-2.9) > 1, unlike Euler's R < -1


def test_verlet_bounded_at_any_step_size() -> None:
    s = setup(b=2.0)
    vx = study.integrate(s, "verlet", 1e3 / s.k, 500).y[:, 2]
    assert np.all(np.abs(vx) <= abs(vx[0]))


# --- Convergence (the main result) ----------------------------------------------------

CASES = {
    "default": {},
    "high_launch_heavy": {"b": 0.5, "m": 2.0, "h": 10.0, "angle": 30.0},
    "strong_drag_steep": {"b": 3.0, "m": 1.0, "h": 2.0, "angle": 70.0, "v0": 15.0},
}


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize(("method", "order"), [("euler", 1), ("rk4", 4), ("verlet", 2)])
def test_fitted_order_matches_theory(case: str, method: study.MethodName, order: int) -> None:
    m = study.run_study(setup(**CASES[case]), HALVING, [method]).methods[0]
    fit = m.position_fit
    assert fit is not None, "fit rule left too few points"
    # Never claim an order from fewer points than the documented rule allows. (With weak
    # drag, RK4's errors reach the round-off floor early, so some cases have only 3.)
    assert fit.n_points >= MIN_FIT_POINTS
    assert fit.order == pytest.approx(order, abs=0.1)
    assert fit.r_squared > 0.999
    # Every local order inside the fit range must already be close to the theory: this
    # guards against a good overall slope hiding a pre-asymptotic trend.
    fitted_pairs = [
        p
        for p, coarse, fine in zip(m.position_local_orders, m.runs, m.runs[1:], strict=False)
        if coarse.in_position_fit and fine.in_position_fit
    ]
    assert len(fitted_pairs) >= MIN_FIT_POINTS - 1
    assert all(p is not None and abs(p - order) < 0.15 for p in fitted_pairs)


def test_default_case_has_at_least_five_fit_points_per_method() -> None:
    for m in study.run_study(setup(), HALVING, ["euler", "rk4", "verlet"]).methods:
        assert m.position_fit is not None
        assert m.position_fit.n_points >= 5


def test_verlet_velocity_converges_at_second_order_independently() -> None:
    m = study.run_study(setup(), HALVING, ["verlet"]).methods[0]
    assert m.velocity_fit is not None
    assert m.velocity_fit.order == pytest.approx(2.0, abs=0.1)


@pytest.mark.parametrize("method", ["euler", "rk4"])
def test_runge_kutta_methods_preserve_linear_invariant(method: study.MethodName) -> None:
    """v + k r + g t y_hat is conserved exactly by any RK method, so the error obeys
    dv = -k dr at every node, and velocity error = k * position error."""
    s = setup(b=0.7)
    h = 0.05
    sol = study.integrate(s, method, h, 40)
    invariant = sol.y[:, 2:] + s.k * sol.y[:, :2]
    invariant[:, 1] += G * sol.t
    np.testing.assert_allclose(
        invariant, np.broadcast_to(invariant[0], invariant.shape), rtol=1e-13, atol=1e-12
    )


def test_verlet_does_not_preserve_linear_invariant() -> None:
    run = study.run_study(setup(b=0.7), [0.05, 0.025, 0.0125], ["verlet"]).methods[0].runs[0]
    assert run.max_velocity_error is not None
    assert run.max_position_error is not None
    assert abs(run.max_velocity_error / (0.7 * run.max_position_error) - 1) > 0.1


# --- Fit-range rule and edge cases -----------------------------------------------------


def test_errors_below_roundoff_floor_are_excluded() -> None:
    m = study.run_study(setup(), HALVING, ["rk4"]).methods[0]
    finest = m.runs[-1]
    assert finest.max_position_error is not None
    assert finest.max_position_error < finest.position_roundoff_floor
    assert not finest.in_position_fit
    assert finest.exclusion_reason == "error below round-off floor"


def test_no_order_claimed_without_enough_points() -> None:
    m = study.run_study(setup(), [0.5, 0.3], ["euler"]).methods[0]  # h/T too large for both
    assert m.position_fit is None
    assert all(
        r.exclusion_reason and r.exclusion_reason.startswith("not asymptotic") for r in m.runs
    )


def test_divergent_run_is_reported_without_non_finite_values() -> None:
    s = setup(b=50.0, h=1e4)  # long, strongly damped fall
    t = flight_time(s)
    dt = 10.0 / s.k  # kh = 10: Euler |R| = 9
    assert t / dt > 200  # enough steps to overflow the divergence threshold
    m = study.run_study(s, [dt, dt / 2], ["euler"]).methods[0]
    run = m.runs[0]
    assert run.diverged
    assert run.stability == "unstable"
    assert run.max_position_error is None
    assert run.exclusion_reason == "diverged"
    assert run.n_completed < run.n_steps


def test_unstable_but_finite_run_is_flagged_and_excluded() -> None:
    s = setup(b=30.0)
    run = study.run_study(s, [2.2 / s.k, 0.001], ["euler"]).methods[0].runs[0]
    assert not run.diverged
    assert run.stability == "unstable"
    assert run.exclusion_reason is not None
    assert run.exclusion_reason.startswith("unstable")


def test_step_larger_than_horizon_takes_one_step() -> None:
    run = study.run_study(setup(), [100.0, 50.0], ["rk4"]).methods[0].runs[0]
    assert run.n_steps == 1
    assert run.h == pytest.approx(flight_time(setup()), rel=1e-15)


def test_steps_for_tolerates_rounding_noise() -> None:
    assert study.steps_for(2.9, 0.1) == 29  # 2.9 / 0.1 = 28.999999999999996
    assert study.steps_for(3.0, 0.1) == 30  # 3.0 / 0.1 = 30.000000000000004
    assert study.steps_for(3.0, 0.7) == 5  # ceil(4.29) -> h = 0.6 <= dt


def test_effective_step_never_exceeds_requested() -> None:
    for run in study.run_study(setup(), [0.07, 0.013, 0.0031], ["euler"]).methods[0].runs:
        assert run.h <= run.dt_requested
        assert run.h * run.n_steps == pytest.approx(flight_time(setup()), rel=1e-14)


def test_vacuum_is_rejected_by_the_engine() -> None:
    with pytest.raises(ValueError, match="nonzero drag"):
        study.run_study(setup(b=0.0), HALVING, ["rk4"])


def test_study_is_deterministic() -> None:
    a = study.run_study(setup(), HALVING[:4], ["euler", "rk4", "verlet"])
    b = study.run_study(setup(), HALVING[:4], ["euler", "rk4", "verlet"])
    assert [r.max_position_error for m in a.methods for r in m.runs] == [
        r.max_position_error for m in b.methods for r in m.runs
    ]
