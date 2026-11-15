"""Seam 2: the oscillator's numerical solve against independent references (2.3, slice 2).

Written test-first: ``simforge.physics.oscillator.numerical`` does not exist when these tests
are written, so it is imported inside each test (the ``num`` fixture). The tests then collect,
and fail one by one with ModuleNotFoundError, until the module is built.

References (never the solver's own output):
- the exact solution ``analytical.state`` (slice 1, itself tested against a 90-digit
  ``decimal`` evaluation of the textbook branch formulas);
- the energy balance KE + PE + W_damp - W_drive = E0 (OR6), exact for the true motion;
- the free decay's exact identities (OR4): with v0 = 0 the maxima of x are at t = n T_d with
  x = x0 e^{-gamma n T_d};
- closed forms written here from the definitions (w0 = sqrt(k/m), gamma = b/2m, ...).

Scales (plan D5, D8; author's decision of 2026-11-09): X = ``analytical.scale`` (a proved
bound on |x| over the run, from the inputs only), velocity scale V = w0 X, energy scale
k X^2 = m V^2. Thresholds come from ``oscillator_thresholds`` (measured, see there).

Interface the builder implements (module ``simforge.physics.oscillator.numerical``):

    damping_acceleration(eta: float, zeta: float) -> float
        The scaled damping term of d(eta)/d(tau): -2 zeta eta (in units of w0^2 X). A
        module-level function that the right-hand side looks up at call time, so a test can
        replace it (the wrong-damping mutant). The work W_damp is integrated from 2 zeta eta^2
        (b v^2 in SI) written separately, never from this function.

    integrate(p: OscillatorInputs, *, duration: float, scale: float, method: SolverMethod,
              rtol: float, atol: float) -> OscillatorSolution
        Solves the dimensionless form tau = w0 t, xi = x / X, eta = v / (w0 X) with SciPy
        solve_ivp on [0, w0 duration], with the two works divided by k X^2, and returns SI
        values as well. Raises SolverError (simforge.core.errors) if the solver fails.

    OscillatorSolution (frozen dataclass), all arrays at the solver's step nodes:
        t (s), x (m), v (m/s), damping_work (J), drive_work (J)       SI
        tau, xi, eta, damping_work_scaled, drive_work_scaled           scaled (W / k X^2)
        maxima_t (s), maxima_x (m): the interior maxima of x (v crosses 0 downwards), with
            0 < t <= duration; the start is never one, even when v0 = 0 (SciPy reports an
            event at t = 0 then, measured in scratch, so it must be dropped)
        scale (X, m), n_steps (= len(t) - 1), n_rhs_evaluations, method, rtol, atol
        sample(t: FloatArray) -> FloatArray: dense output at times t (s), rows x, v,
            damping_work, drive_work in SI
"""

from __future__ import annotations

import importlib
import math
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from simforge.physics.oscillator import analytical as osc
from tests.approx import rel_approx
from tests.physics.oscillator_thresholds import (
    DEFAULT,
    METHODS,
    REGIMES,
    TIGHTEST,
    Method,
    Run,
    regime_run,
    threshold,
)

EPS = float(np.finfo(float).eps)  # 2.2e-16


@pytest.fixture
def num() -> ModuleType:
    """The module under test, imported when a test runs, not at collection (module docstring)."""
    return importlib.import_module("simforge.physics.oscillator.numerical")


def solve(num: ModuleType, run: Run, method: Method, pair: tuple[float, float]) -> Any:
    rtol, atol = pair
    return num.integrate(
        run.inputs,
        duration=run.duration,
        scale=osc.scale(run.inputs, run.duration),
        method=method,
        rtol=rtol,
        atol=atol,
    )


def w0_of(p: osc.OscillatorInputs) -> float:
    return math.sqrt(p.spring_constant / p.mass)


def node_errors(run: Run, sol: Any) -> tuple[float, float, float]:
    """(max |x - x_exact| / X, max |v - v_exact| / (w0 X), max energy residual / k X^2) over
    the step nodes, every reference computed here from ``analytical`` and the definitions."""
    p = run.inputs
    x_scale = osc.scale(p, run.duration)
    w0 = w0_of(p)
    t = np.asarray(sol.t, dtype=np.float64)
    x_exact, v_exact = osc.state(p, t)
    dx = float(np.max(np.abs(sol.x - x_exact))) / x_scale
    dv = float(np.max(np.abs(sol.v - v_exact))) / (w0 * x_scale)
    return dx, dv, energy_residual(run, sol)


def energy_residual(run: Run, sol: Any) -> float:
    """max |KE + PE + W_damp - W_drive - E0| / (k X^2) over the step nodes (OR6, plan D8)."""
    p = run.inputs
    m, k = p.mass, p.spring_constant
    x_scale = osc.scale(p, run.duration)
    e0 = 0.5 * m * p.initial_velocity**2 + 0.5 * k * p.initial_displacement**2
    balance = 0.5 * m * sol.v**2 + 0.5 * k * sol.x**2 + sol.damping_work - sol.drive_work - e0
    return float(np.max(np.abs(balance))) / (k * x_scale**2)


# --- The damping function the mutant replaces -------------------------------------------------


def test_damping_acceleration_is_minus_two_zeta_eta(num: ModuleType) -> None:
    # Hand-worked: -2 x 0.1 x 0.5 = -0.1 and -2 x 0.25 x (-3) = 1.5. Every product here is by a
    # power of two or lands on the same float in any order, so equality is exact.
    assert num.damping_acceleration(0.5, 0.1) == -0.1
    assert num.damping_acceleration(-3.0, 0.25) == 1.5
    assert num.damping_acceleration(0.7, 0.0) == 0.0


# --- Agreement with the exact solution in every regime -------------------------------------


@pytest.mark.parametrize("driven", [False, True], ids=["free", "driven"])
@pytest.mark.parametrize("regime", REGIMES)
@pytest.mark.parametrize("method", METHODS)
def test_tightest_pair_matches_the_exact_solution_in_every_regime(
    num: ModuleType, method: Method, regime: osc.Regime, driven: bool
) -> None:
    run = regime_run(regime, driven)
    assert osc.derived(run.inputs).regime == regime  # the catalogue covers each Regime value
    sol = solve(num, run, method, TIGHTEST)
    dx, dv, de = node_errors(run, sol)
    # Thresholds measured on the corner grid (oscillator_thresholds); the exact solution's own
    # floor is ~1.5 eps (w0 T + 1) X ~ 5e-15 X here, far below them (slice 1 error model).
    assert dx <= threshold("displacement_error", *TIGHTEST, run.inputs, run.duration)
    assert dv <= threshold("velocity_error", *TIGHTEST, run.inputs, run.duration)
    assert de <= threshold("energy_balance", *TIGHTEST, run.inputs, run.duration)


@pytest.mark.parametrize("method", METHODS)
def test_error_falls_as_the_tolerance_tightens(num: ModuleType, method: Method) -> None:
    # A solve that ignored rtol/atol would not improve. From the middle pair to the default one
    # (rtol + atol) falls 5000x; measured in scratch (a close variant of this run) the error
    # fell 580x (DOP853) to 3700x (Radau). A factor of 20 keeps a 29x margin and still catches
    # "no change" (a ratio near 1).
    run = regime_run("underdamped", driven=True)
    loose = node_errors(run, solve(num, run, method, (1e-6, 1e-8)))[0]
    tight = node_errors(run, solve(num, run, method, DEFAULT))[0]
    assert tight * 20 < loose


# --- The solution's structure and its scaled and SI forms ------------------------------------


@pytest.mark.parametrize("method", METHODS)
def test_solution_starts_at_the_initial_state_and_ends_at_the_duration(
    num: ModuleType, method: Method
) -> None:
    run = regime_run("underdamped", driven=True)
    p = run.inputs
    sol = solve(num, run, method, DEFAULT)
    assert sol.method == method
    assert (sol.rtol, sol.atol) == DEFAULT
    assert sol.scale == osc.scale(p, run.duration)
    assert sol.n_steps == len(sol.t) - 1
    assert sol.n_rhs_evaluations >= sol.n_steps
    assert sol.t[0] == 0.0
    assert np.all(np.diff(sol.t) > 0)
    # t = tau / w0 with tau ending at w0 T: two roundings, so 2 eps relative.
    assert sol.t[-1] == rel_approx(run.duration, 2 * EPS)
    # x0 -> x0 / X -> X (x0 / X) and v0 -> v0 / (w0 X) -> w0 X (...): at most four roundings.
    assert sol.x[0] == rel_approx(p.initial_displacement, 4 * EPS)
    assert sol.v[0] == rel_approx(p.initial_velocity, 4 * EPS)
    # Both works start at exactly 0 (they are integrals from t = 0).
    assert sol.damping_work[0] == 0.0
    assert sol.drive_work[0] == 0.0
    for arr in (sol.x, sol.v, sol.damping_work, sol.drive_work, sol.xi, sol.eta, sol.tau):
        assert len(arr) == len(sol.t)


@pytest.mark.parametrize("driven", [False, True], ids=["free", "driven"])
@pytest.mark.parametrize("regime", REGIMES)
@pytest.mark.parametrize("method", METHODS)
def test_scaled_and_si_states_agree_to_rounding(
    num: ModuleType, method: Method, regime: osc.Regime, driven: bool
) -> None:
    run = regime_run(regime, driven)
    p = run.inputs
    sol = solve(num, run, method, DEFAULT)
    x_scale = osc.scale(p, run.duration)
    w0 = w0_of(p)
    k = p.spring_constant
    # Each SI value is its scaled value times X, w0 X or k X^2 (and t = tau / w0). The code and
    # this test may group the products differently: each side is then within 2 to 3 roundings
    # (eps/2 each) of the exact product, and w0 itself may differ by one rounding, so 4 eps
    # elementwise covers every grouping. Element by element, so tiny values are held relative.
    assert sol.x == rel_approx(x_scale * sol.xi, 4 * EPS)
    assert sol.v == rel_approx(w0 * x_scale * sol.eta, 4 * EPS)
    assert sol.t == rel_approx(sol.tau / w0, 4 * EPS)
    energy_scale = k * x_scale * x_scale
    assert sol.damping_work == rel_approx(energy_scale * sol.damping_work_scaled, 4 * EPS)
    assert sol.drive_work == rel_approx(energy_scale * sol.drive_work_scaled, 4 * EPS)


def test_units_do_not_change_the_scaled_motion(num: ModuleType) -> None:
    """Scaling m, k, b and F0 by lambda leaves w0, gamma, zeta, f = F0/m and X unchanged, so
    the motion is the same and the works (in J) scale by lambda. A unit bug in the scaled
    equations (b/m where b/sqrt(mk) belongs, k where m belongs, F0 where F0/m belongs) changes
    them by a factor lambda^(1/2) = 32 or lambda = 1024 and fails by O(1)."""
    lam = 2.0**10  # a power of 4: every product, quotient and sqrt below is scaled exactly
    run = regime_run("underdamped", driven=True)
    p = run.inputs
    q = osc.OscillatorInputs(
        mass=lam * p.mass,
        spring_constant=lam * p.spring_constant,
        damping_coefficient=lam * p.damping_coefficient,
        drive_amplitude=lam * p.drive_amplitude,
        drive_angular_frequency=p.drive_angular_frequency,
        initial_displacement=p.initial_displacement,
        initial_velocity=p.initial_velocity,
    )
    scaled_run = Run(q, run.duration)
    assert osc.scale(q, run.duration) == osc.scale(p, run.duration)  # X is unit-free here
    a = solve(num, run, "DOP853", DEFAULT)
    b = solve(num, scaled_run, "DOP853", DEFAULT)
    # Both solves are within their thresholds of the same exact motion (test above), so their
    # final states differ by at most twice that; expected identical, but only the physics is
    # asserted, so a correct code that rounds its coefficients differently also passes.
    x_scale = osc.scale(p, run.duration)
    w0 = w0_of(p)
    tol_x = 2 * threshold("displacement_error", *DEFAULT, p, run.duration)
    tol_v = 2 * threshold("velocity_error", *DEFAULT, p, run.duration)
    tol_e = 2 * threshold("energy_balance", *DEFAULT, p, run.duration)
    assert abs(b.x[-1] - a.x[-1]) <= tol_x * x_scale
    assert abs(b.v[-1] - a.v[-1]) <= tol_v * w0 * x_scale
    energy_scale = p.spring_constant * x_scale**2
    assert abs(b.damping_work[-1] / lam - a.damping_work[-1]) <= tol_e * energy_scale
    assert abs(b.drive_work[-1] / lam - a.drive_work[-1]) <= tol_e * energy_scale


@pytest.mark.parametrize("method", METHODS)
def test_dense_output_reproduces_the_step_nodes(num: ModuleType, method: Method) -> None:
    run = regime_run("underdamped", driven=True)
    sol = solve(num, run, method, DEFAULT)
    rows = sol.sample(np.asarray(sol.t, dtype=np.float64))
    assert rows.shape == (4, len(sol.t))
    x_scale = osc.scale(run.inputs, run.duration)
    # At a node the interpolant equals the node up to the rounding of its polynomial (a few
    # terms of size <= |y|): measured <= 1.1e-16 at this pair in scratch; 64 eps of the scale
    # leaves margin while catching a swapped row or a missing SI conversion (factor X, w0 X).
    w0 = w0_of(run.inputs)
    energy_scale = run.inputs.spring_constant * x_scale**2
    for row, nodes, unit in (
        (rows[0], sol.x, x_scale),
        (rows[1], sol.v, w0 * x_scale),
        (rows[2], sol.damping_work, energy_scale),
        (rows[3], sol.drive_work, energy_scale),
    ):
        assert float(np.max(np.abs(row - nodes))) <= 64 * EPS * unit


# --- The works are integrated independently of the force -------------------------------------


@pytest.mark.parametrize("method", METHODS)
def test_free_run_does_no_drive_work_and_undamped_run_no_damping_work(
    num: ModuleType, method: Method
) -> None:
    # With F0 = 0 the drive power F0 cos(w t) v is exactly 0, and with b = 0 the damping power
    # b v^2 is exactly 0, so each work stays exactly 0 at every node (measured in scratch for
    # all three methods, Radau included).
    free = solve(num, regime_run("underdamped", driven=False), method, DEFAULT)
    assert np.all(free.drive_work == 0.0)
    assert free.damping_work[-1] > 0.0
    undamped = solve(num, regime_run("undamped", driven=True), method, DEFAULT)
    assert np.all(undamped.damping_work == 0.0)
    assert np.any(undamped.drive_work != 0.0)


def wrong_damping(eta: float, zeta: float) -> float:
    """The mutant (plan, seam 2): a quadratic damping force -b v |v| / V in place of -b v,
    scaled: -2 zeta eta |eta|. It agrees with the true law only where |eta| = 1."""
    return -2.0 * zeta * eta * abs(eta)


@pytest.fixture
def mutant(num: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(num, "damping_acceleration", wrong_damping)


MUTANT_RUNS = {
    "underdamped_free": regime_run("underdamped", driven=False),
    "underdamped_driven": regime_run("underdamped", driven=True),
    "overdamped_free": regime_run("overdamped", driven=False),
}
# The mutant's energy residual / k X^2 is set by the wrong physics, not by the solver: measured
# in scratch (close variants of these runs, all three methods at the default pair) 0.030 to
# 1.5, while the true law gave 1e-14 to 1e-9. 1e-3 is 30x below the smallest mutant value.
MUTANT_ENERGY_FLOOR = 1e-3


@pytest.mark.parametrize("name", list(MUTANT_RUNS))
@pytest.mark.parametrize("method", METHODS)
def test_true_damping_passes_the_energy_balance(num: ModuleType, method: Method, name: str) -> None:
    run = MUTANT_RUNS[name]
    sol = solve(num, run, method, DEFAULT)
    assert energy_residual(run, sol) <= threshold(
        "energy_balance", *DEFAULT, run.inputs, run.duration
    )


@pytest.mark.usefixtures("mutant")
@pytest.mark.parametrize("name", list(MUTANT_RUNS))
@pytest.mark.parametrize("method", METHODS)
def test_wrong_damping_fails_the_energy_balance(num: ModuleType, method: Method, name: str) -> None:
    """The works are coded from b v^2 and F0 cos(w t) v, never from the force function, so a
    wrong force leaves the energy unbalanced (if W_damp were computed from the force, the
    mutant would balance and this test would fail)."""
    run = MUTANT_RUNS[name]
    sol = solve(num, run, method, DEFAULT)
    residual = energy_residual(run, sol)
    assert residual > MUTANT_ENERGY_FLOOR
    assert residual > threshold("energy_balance", *DEFAULT, run.inputs, run.duration)
    # The exact solution sees it too (measured 0.056 to 0.56 of X in scratch).
    dx = node_errors(run, sol)[0]
    assert dx > threshold("displacement_error", *DEFAULT, run.inputs, run.duration)


# --- Maxima events against the free decay's exact identities (OR4) ----------------------------


@pytest.mark.parametrize("method", METHODS)
def test_maxima_of_a_free_decay_are_one_damped_period_apart(
    num: ModuleType, method: Method
) -> None:
    # Free, underdamped, from (x0, 0): x = x0 e^{-gamma t}[cos wd t + (gamma/wd) sin wd t], so
    # v = -(w0^2/wd) x0 e^{-gamma t} sin wd t vanishes at t = n pi / wd, and x is a maximum at
    # t = n T_d (T_d = 2 pi / wd), with x = x0 e^{-gamma n T_d}: exact, from the definitions.
    run = Run(regime_run("underdamped", driven=False).inputs, 8.0)  # T / T_d = 6.36: 6 maxima
    p = run.inputs
    sol = solve(num, run, method, DEFAULT)
    w0 = w0_of(p)
    gamma = p.damping_coefficient / (2 * p.mass)
    wd = math.sqrt(w0 * w0 - gamma * gamma)
    period = 2 * math.pi / wd
    n = np.arange(1, 7, dtype=np.float64)
    assert len(sol.maxima_t) == 6  # the start (v0 = 0) is not reported as a maximum
    assert np.all(sol.maxima_t > 0.0)
    assert np.all(sol.maxima_t <= run.duration)
    assert len(sol.maxima_x) == len(sol.maxima_t)
    x_scale = osc.scale(p, run.duration)
    # Measured in scratch at this pair: time errors 1.6e-11 to 1.4e-9 (scaled), displacement
    # errors 1.9e-11 to 7.9e-10 of X: well within the measured free-decay thresholds.
    time_error = float(np.max(np.abs(sol.maxima_t - n * period))) * w0
    x_error = float(
        np.max(np.abs(sol.maxima_x - p.initial_displacement * np.exp(-gamma * n * period)))
    )
    assert time_error <= threshold("free_decay_period", *DEFAULT, p, run.duration)
    assert x_error / x_scale <= threshold("free_decay_ratio", *DEFAULT, p, run.duration)


def test_overdamped_free_run_has_no_maxima(num: ModuleType) -> None:
    # From (x0 > 0, 0), overdamped: x decreases monotonically to 0 and never turns back (v < 0
    # for t > 0, from OR2's two decaying exponentials), so there is no interior maximum.
    sol = solve(num, regime_run("overdamped", driven=False), "DOP853", DEFAULT)
    assert len(sol.maxima_t) == 0
