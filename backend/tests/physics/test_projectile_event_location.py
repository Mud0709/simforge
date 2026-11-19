"""Seam for the projectile integrator study's event location (roadmap 2.4, slice 4; plan D11,
D13, R6).

Written test-first: the new fields and checks do not exist when these tests are written, so
the modules are imported inside fixtures and the tests fail on missing attributes until built.

What is checked, and against what (never the code's own output):
- landing-time orders per method and interpolant on the default request, within 0.1 of
  min(p, q) (R6; q = 2 linear, 4 Hermite): Euler 1/1, RK4 2/4, Verlet 2/2. The order
  statement O(h^min(p, q)) is a **standard result, tested here** (not proved in this repo).
  Reference landing time: ``analytical.flight_time`` (brentq on the closed-form y(t);
  independent of every integrator, validated in ``test_projectile_analytical.py``);
- mid-step placement h_e = T/(N + 1/2) (the exact landing sits at s = 1/2 of step N + 1);
- the interpolation error alone (interpolant applied to the EXACT nodal values) against the
  R6 leading terms at s = 1/2, with signs derived here: linear t~ - T = h^2 y''/(8|y'|) (y
  concave, the chord lands early); Hermite t~ - T = -h^4 y''''/(384|y'|) (y - p =
  y''''/24 (t - t0)^2 (t - t1)^2 < 0, so the cubic lands late). Exact y'' = -k A, y'''' =
  -k^3 A, A = (vy0 + g/k) e^{-kT} (closed form, written below);
- trap (i), the round-off floor: a run whose landing error is at or below
  ROUNDOFF_SAFETY (i + 1) eps T is excluded from the fit (reason names round-off), and a
  request whose runs are all near-exact gives no verdict, never a false fail;
- trap (ii), cancellation: RK4's own error and Hermite's error are both O(h^4) and cancel at
  some (angle, k) (measured: ratio e_interp/e_int = -1.03 at 15 deg, b = 0.3; -0.92 at 5 deg,
  b = 1). Without a rule, fits on 12-point grids there gave 3.70 and 4.12 (false fails;
  measured in a scratch scan, 2026-11-19, 8 angles x 5 drags x 3 grids). Expected rule: a
  run is excluded when |e| < EVENT_CANCELLATION_RATIO (|e_interp| + |e - e_interp|), ratio
  0.5 (the O(h^5) remainder is then amplified at most 2x); with the rule the same scan had
  no false fail. With too few points left, the check gives passed = None with a reason;
- no crossing: an event run with no downward crossing of y = 0 within 2N + 2 steps is
  excluded with a reason (an unstable RK4 run, and a planted frozen stepper);
- the linear invariant: every RK method preserves v + k r + g t y_hat, so delta v = -k delta r
  exactly at every node (kind exact identity; the float residual is rounding only);
  a planted non-RK stepper (semi-implicit Euler) fails it;
- a planted wrong Hermite slope (dg0 and dg1 swapped: value error h^2 y''/4 at s = 1/2, so
  order 2) fails ``event_order_rk4_hermite``.

Interface the builder implements (plan D11, D13, D14; existing fields unchanged):

``simforge.physics.projectile.integrator_study``
    Looks up ``euler_step``, ``rk4_step`` and ``locate_crossing`` (imported from
    ``simforge.numerics.events``) in its own module namespace at run time, so a test can
    substitute them with ``monkeypatch.setattr``. Event runs use the same steppers.

``simforge.physics.projectile.integrator_model``
    MODEL_INFO.version "1.1.0". EVENT_CANCELLATION_RATIO = 0.5. VELOCITY_POSITION_IDENTITY_C
    (equal to this file's C_VELOCITY_POSITION_IDENTITY). ``run(request)`` returns a
    StudyComputation that gains ``checks: list[ValidationCheck]`` (the response gains it too).
    Each ``MethodStudyResult`` gains:
      event_runs: one per run, same order as ``runs``, each with
        n_steps (N of the matching fixed-horizon run), h (= T/(N + 1/2), s), kh, stability,
        diverged, n_completed (steps taken; at most 2N + 2), crossed (bool), crossing_step
        (i: first node with y_i > 0 and y_{i+1} <= 0, ``events.first_crossing``; None if no
        crossing), landing_time_linear, landing_time_hermite (s; None if no crossing),
        landing_error_linear, landing_error_hermite (|t^ - T|, s; None if no crossing),
        interpolation_error_linear, interpolation_error_hermite (signed t~ - T, s, the same
        interpolant on the exact nodal y, vy at t_i, t_{i+1}; None if those do not bracket),
        roundoff_floor (ROUNDOFF_SAFETY (i + 1) eps T, s; 0 if no crossing),
        in_linear_fit, in_hermite_fit, linear_exclusion_reason, hermite_exclusion_reason
        (None when in the fit). Fit rule: crossed; stable; kh <= MAX_KH_FOR_FIT;
        h <= T MAX_H_OVER_T_FOR_FIT; error > roundoff_floor (reason contains "round-off");
        not cancelling (reason contains "cancel"); no crossing: reason contains "crossing".
      landing_fit_linear, landing_fit_hermite: OrderFitResult | None, fitted to the landing
        error against h, theoretical_order min(p, 2) and min(p, 4).
    Check ids (m a requested method, q in {linear, hermite}):
      "order_<m>"  numerical_diagnostic, |position_fit.order - p|, threshold 0.1 (when a fit
                   exists); "fit_points_<m>" informational;
      "velocity_position_identity_<m>" (euler, rk4)  exact_identity, value max over stable,
                   non-diverged runs of max_n ||(v_n - v(t_n)) + k (r_n - r(t_n))||_inf /
                   (N eps V), V = velocity_scale + k position_scale + g T; threshold
                   VELOCITY_POSITION_IDENTITY_C; passed None with a reason if no run qualifies;
      "event_order_<m>_<q>"  numerical_diagnostic, |fit - min(p, q)|, threshold 0.1; with no
                   fit: present, passed None, threshold None, value = points meeting the rule,
                   note says why (round-off, cancellation, crossing counts);
      "event_fit_points_<m>_<q>" informational (value = points in the fit).
    Every check: passed True or None, or False only on a real failure; None has a note.
"""

from __future__ import annotations

import importlib
import math
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from simforge.physics.projectile import analytical
from simforge.physics.projectile.analytical import ProjectileSetup
from tests.approx import rel_approx

EPS = float(np.finfo(np.float64).eps)
G = 9.80665
METHODS = ("euler", "rk4", "verlet")
KINDS = ("linear", "hermite")
P = {"euler": 1, "rk4": 4, "verlet": 2}
Q = {"linear": 2, "hermite": 4}
ORDER_TOL = 0.1  # plan D13, check (2)
ROUNDOFF_SAFETY = 100.0  # integrator_study.ROUNDOFF_SAFETY (unchanged fit rule)
CANCELLATION_RATIO = 0.5  # expected EVENT_CANCELLATION_RATIO (see module docstring)

# BUILDER MAY SET
# Rounding allowance for delta v + k delta r = 0, in units of N eps V (see the docstring).
# A priori each step adds a few roundings of operands bounded by V, and a linear invariant is
# never amplified (I(Phi(s)) = I(s) + const for every s), so O(1) per step. Measured (slice 4
# test writing, x86_64, Python 3.12): worst 0.83 over angles {0.5, 5, 15, 45, 75, 90} deg,
# b in {1e-3, 0.1, 1, 10, 100}, h0 in {0, 100} m, 20 step sizes, Euler and RK4, stable runs,
# exact state from analytical.state; >= 10x on the 1-2-5 series gives 10.
C_VELOCITY_POSITION_IDENTITY = 10.0
# END OF BUILDER MAY SET

GRID_125 = [0.1 * 0.8**i for i in range(12)]
GRID_15 = [0.3 * 0.7**i for i in range(12)]


@pytest.fixture
def schemas() -> ModuleType:
    return importlib.import_module("simforge.physics.projectile.integrator_schemas")


@pytest.fixture
def model() -> ModuleType:
    return importlib.import_module("simforge.physics.projectile.integrator_model")


@pytest.fixture
def study() -> ModuleType:
    return importlib.import_module("simforge.physics.projectile.integrator_study")


def params(angle: float = 45.0, b: float = 1.0, h0: float = 0.0) -> dict[str, float]:
    return {
        "initial_speed": 20.0,
        "launch_angle_deg": angle,
        "launch_height": h0,
        "mass": 1.0,
        "drag_coefficient": b,
    }


def run(schemas: ModuleType, model: ModuleType, **body: Any) -> Any:
    request = schemas.IntegratorStudyRequest.model_validate({**body, "save_experiment": False})
    return model.run(request)


def setup_of(p: dict[str, float]) -> ProjectileSetup:
    return ProjectileSetup(
        p["initial_speed"], math.radians(p["launch_angle_deg"]), p["launch_height"], 1.0,
        p["drag_coefficient"], G,
    )  # fmt: skip


def by_method(c: Any) -> dict[str, Any]:
    return {r.method: r for r in c.results}


def checks_of(c: Any) -> dict[str, Any]:
    return {ch.id: ch for ch in c.checks}


def assert_no_false_verdict(c: Any) -> None:
    for ch in c.checks:
        assert ch.passed is not False, (ch.id, ch.value, ch.threshold, ch.note)
        if ch.passed is None:
            assert ch.note.strip(), ch.id


# --- Default request --------------------------------------------------------------------


def test_version_is_1_1_0(model: ModuleType) -> None:
    assert model.MODEL_INFO.version == "1.1.0"
    assert model.EVENT_CANCELLATION_RATIO == CANCELLATION_RATIO
    assert model.VELOCITY_POSITION_IDENTITY_C == C_VELOCITY_POSITION_IDENTITY


def test_default_landing_orders_are_min_p_q(schemas: ModuleType, model: ModuleType) -> None:
    """Measured in scratch: 0.995/0.997, 2.000/4.039 (4 points), 2.000/2.000."""
    c = run(schemas, model)
    checks = checks_of(c)
    for m, r in by_method(c).items():
        assert len(r.event_runs) == len(r.runs) == 8
        for q in KINDS:
            fit = getattr(r, f"landing_fit_{q}")
            assert fit is not None, (m, q)
            assert fit.theoretical_order == min(P[m], Q[q])
            assert fit.n_points >= 3
            assert fit.order == pytest.approx(min(P[m], Q[q]), abs=ORDER_TOL), (m, q)
            ch = checks[f"event_order_{m}_{q}"]
            assert ch.kind == "numerical_diagnostic"
            assert ch.threshold == ORDER_TOL
            assert ch.passed is True
            assert checks[f"event_fit_points_{m}_{q}"].kind == "informational"
            assert checks[f"event_fit_points_{m}_{q}"].value == fit.n_points
        assert checks[f"order_{m}"].passed is True
        assert checks[f"fit_points_{m}"].kind == "informational"
    assert_no_false_verdict(c)


def test_event_runs_use_mid_step_placement_and_flight_time(
    schemas: ModuleType, model: ModuleType
) -> None:
    c = run(schemas, model)
    t_land = analytical.flight_time(setup_of(params()))
    assert c.horizon == rel_approx(t_land, 4 * EPS)
    for r in c.results:
        for fixed, ev in zip(r.runs, r.event_runs, strict=True):
            n = fixed.n_steps
            assert ev.n_steps == n
            # one division and one addition of exact halves: a few ulps
            assert ev.h == rel_approx(t_land / (n + 0.5), 4 * EPS)
            assert ev.crossed is True
            assert ev.n_completed <= 2 * n + 2
            assert ev.roundoff_floor == rel_approx(
                ROUNDOFF_SAFETY * (ev.crossing_step + 1) * EPS * t_land, 1e-12
            )
            if ev.in_linear_fit or ev.in_hermite_fit:
                # an accurate run lands near s = 1/2 of step N + 1
                assert ev.crossing_step == n
            for q in KINDS:
                t_hat = getattr(ev, f"landing_time_{q}")
                assert ev.h * ev.crossing_step <= t_hat * (1 + 4 * EPS)
                assert t_hat <= ev.h * (ev.crossing_step + 1) * (1 + 4 * EPS)
                # |t^ - T| from the response against the independent T: rounding of one
                # subtraction of numbers <= 2T
                assert getattr(ev, f"landing_error_{q}") == pytest.approx(
                    abs(t_hat - t_land), abs=4 * EPS * t_land
                )


def test_interpolation_error_matches_r6_leading_terms(
    schemas: ModuleType, model: ModuleType
) -> None:
    """R6 at s = 1/2 with signs derived in the docstring. Measured relative deviation of the
    leading term (O(h^2) relative): <= 3.4e-4 for N >= 22; 1e-3 is about 3x that. Hermite
    is compared only where the predicted error exceeds 1e-11 s, so rounding (~1e-15 s) stays
    below 1e-4 relative."""
    c = run(schemas, model)
    s = setup_of(params())
    t_land = analytical.flight_time(s)
    k = s.k
    a = (s.vy0 + G / k) * math.exp(-k * t_land)
    y1, y2, y4 = a - G / k, -k * a, -(k**3) * a
    for r in c.results:
        for ev in r.event_runs:
            if ev.n_steps < 22 or ev.crossing_step != ev.n_steps:
                continue
            lin = ev.h**2 * y2 / (8 * abs(y1))
            assert ev.interpolation_error_linear == rel_approx(lin, 1e-3)
            her = -(ev.h**4) * y4 / (384 * abs(y1))
            if abs(her) > 1e-11:
                assert ev.interpolation_error_hermite == rel_approx(her, 1e-3)


# --- Trap (i): the round-off floor ------------------------------------------------------


def test_default_rk4_hermite_excludes_runs_at_the_roundoff_floor(
    schemas: ModuleType, model: ModuleType
) -> None:
    """Measured: the three finest RK4/Hermite runs (errors 9e-12, 6e-13, 4e-14 s) are at or
    below their floors (1.7e-11 to 6.6e-11 s); a fit including them would be meaningless."""
    c = run(schemas, model)
    t_land = analytical.flight_time(setup_of(params()))
    r = by_method(c)["rk4"]
    below = [ev for ev in r.event_runs if ev.landing_error_hermite <= ev.roundoff_floor]
    assert len(below) >= 2
    for ev in below:
        assert ev.in_hermite_fit is False
        assert "round-off" in ev.hermite_exclusion_reason
    for ev in r.event_runs:
        if ev.in_hermite_fit:
            assert abs(ev.landing_time_hermite - t_land) > ev.roundoff_floor


def test_near_exact_runs_give_no_verdict_not_a_false_fail(
    schemas: ModuleType, model: ModuleType
) -> None:
    c = run(schemas, model, dt_values=[0.004, 0.002, 0.001], methods=["rk4"])
    r = by_method(c)["rk4"]
    assert r.landing_fit_hermite is None
    for ev in r.event_runs:
        assert ev.in_hermite_fit is False
        assert "round-off" in ev.hermite_exclusion_reason
    ch = checks_of(c)["event_order_rk4_hermite"]
    assert ch.passed is None
    assert ch.threshold is None
    assert_no_false_verdict(c)


# --- Trap (ii): RK4 and Hermite errors cancelling -----------------------------------------


@pytest.mark.parametrize(
    ("angle", "b", "grid"),
    [(15.0, 0.3, GRID_125), (15.0, 0.3, GRID_15), (5.0, 1.0, GRID_125), (5.0, 1.0, GRID_15)],
)
def test_cancellation_never_gives_a_false_fail(
    schemas: ModuleType, model: ModuleType, angle: float, b: float, grid: list[float]
) -> None:
    """Without the cancellation rule these four fits measured 3.70, 3.67, 4.12, 4.11."""
    p = params(angle, b)
    c = run(schemas, model, parameters=p, dt_values=grid, methods=["rk4"])
    t_land = analytical.flight_time(setup_of(p))
    r = by_method(c)["rk4"]
    assert any(
        ev.hermite_exclusion_reason and "cancel" in ev.hermite_exclusion_reason
        for ev in r.event_runs
    )
    for ev in r.event_runs:
        if ev.in_hermite_fit:
            e = ev.landing_time_hermite - t_land
            e_interp = ev.interpolation_error_hermite
            assert abs(e) >= CANCELLATION_RATIO * (abs(e_interp) + abs(e - e_interp))
    ch = checks_of(c)["event_order_rk4_hermite"]
    assert ch.passed is not False
    if r.landing_fit_hermite is not None:
        assert r.landing_fit_hermite.order == pytest.approx(4, abs=ORDER_TOL)
    assert_no_false_verdict(c)


# --- No crossing --------------------------------------------------------------------------


def test_unstable_run_without_crossing_is_excluded(schemas: ModuleType, model: ModuleType) -> None:
    """b = 10, dt = 0.5: N = 4, k h_e = 3.43 > 2.785 (RK4 unstable); measured: y never has a
    downward crossing within 2N + 2 steps (it leaves y = 0 already going down)."""
    c = run(schemas, model, parameters=params(b=10.0), dt_values=[0.5, 0.25], methods=["rk4"])
    ev = by_method(c)["rk4"].event_runs[0]
    assert ev.n_steps == 4
    assert ev.crossed is False
    assert ev.crossing_step is None
    for q in KINDS:
        assert getattr(ev, f"landing_time_{q}") is None
        assert getattr(ev, f"landing_error_{q}") is None
        assert getattr(ev, f"in_{q}_fit") is False
        assert "crossing" in getattr(ev, f"{q}_exclusion_reason")


def test_horizon_ending_before_landing_is_excluded(
    schemas: ModuleType, model: ModuleType, study: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A planted stepper that never moves keeps y = 10 m > 0 to the cap of 2N + 2 steps."""
    monkeypatch.setattr(study, "rk4_step", lambda _f, _t, s, _h: np.array(s, dtype=float))
    c = run(schemas, model, parameters=params(h0=10.0), dt_values=[0.1, 0.05, 0.025],
            methods=["rk4"])  # fmt: skip
    r = by_method(c)["rk4"]
    for ev in r.event_runs:
        assert ev.crossed is False
        assert ev.n_completed == 2 * ev.n_steps + 2
        assert ev.in_linear_fit is False
        assert ev.in_hermite_fit is False
        assert "crossing" in ev.linear_exclusion_reason
    assert r.landing_fit_linear is None
    assert r.landing_fit_hermite is None
    checks = checks_of(c)
    for q in KINDS:
        assert checks[f"event_order_rk4_{q}"].passed is None
        assert checks[f"event_order_rk4_{q}"].note.strip()


# --- delta v = -k delta r (exact identity for Runge-Kutta methods) --------------------------


def identity_residual(
    study: ModuleType, s: ProjectileSetup, method: str, n: int, t_land: float
) -> float:
    """Independent recomputation: the scheme's nodes against ``analytical.state``."""
    sol = study.integrate(s, method, t_land / n, n)
    x, y, vx, vy = analytical.state(s, sol.t)
    dr = sol.y[:, :2] - np.stack([x, y], 1)
    dv = sol.y[:, 2:] - np.stack([vx, vy], 1)
    scale = np.abs(np.stack([vx, vy], 1)).max() + s.k * np.hypot(x, y).max() + G * t_land
    return float(np.abs(dv + s.k * dr).max() / (n * EPS * scale))


@pytest.mark.parametrize(
    ("angle", "b", "h0"),
    [(45.0, 1.0, 0.0), (0.5, 0.001, 100.0), (90.0, 100.0, 0.0), (15.0, 0.1, 100.0)],
)
def test_velocity_position_identity_holds_to_rounding(
    schemas: ModuleType, model: ModuleType, study: ModuleType, angle: float, b: float, h0: float
) -> None:
    p = params(angle, b, h0)
    s = setup_of(p)
    t_land = analytical.flight_time(s)
    c = run(schemas, model, parameters=p)
    checks = checks_of(c)
    for m in ("euler", "rk4"):
        ch = checks[f"velocity_position_identity_{m}"]
        assert ch.kind == "exact_identity"
        assert ch.threshold == C_VELOCITY_POSITION_IDENTITY
        assert ch.passed is True, (m, ch.value)
        for fixed in by_method(c)[m].runs:
            if fixed.stability == "stable" and not fixed.diverged:
                assert identity_residual(study, s, m, fixed.n_steps, t_land) <= ch.threshold
    assert "velocity_position_identity_verlet" not in checks


def test_planted_non_runge_kutta_stepper_fails_the_identity(
    schemas: ModuleType, model: ModuleType, study: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Semi-implicit Euler (v first, then r += h v_new) changes the invariant by k h^2 a per
    step, far above N eps V."""

    def semi_implicit(f: Any, t: float, s: Any, h: float) -> Any:
        d = f(t, s)
        v = s[2:] + h * d[2:]
        return np.concatenate([s[:2] + h * v, v])

    monkeypatch.setattr(study, "euler_step", semi_implicit)
    c = run(schemas, model, methods=["euler"])
    assert checks_of(c)["velocity_position_identity_euler"].passed is False


# --- A planted wrong interpolant slope ----------------------------------------------------


def test_planted_wrong_hermite_slope_fails_the_order_check(
    schemas: ModuleType, model: ModuleType, study: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Swapping dg0 and dg1 adds (h/4)(dg1 - dg0) ~ h^2 y''/4 at s = 1/2: order 2, not 4."""
    real = study.locate_crossing

    def swapped(t0: float, t1: float, g0: float, g1: float, dg0: float, dg1: float, *,
                kind: str) -> float:  # fmt: skip
        return float(real(t0, t1, g0, g1, dg1, dg0, kind=kind))

    monkeypatch.setattr(study, "locate_crossing", swapped)
    c = run(schemas, model, methods=["rk4"])
    checks = checks_of(c)
    fit = by_method(c)["rk4"].landing_fit_hermite
    assert fit is not None
    assert fit.order == pytest.approx(2, abs=0.2)
    assert checks["event_order_rk4_hermite"].passed is False
    assert checks["event_order_rk4_linear"].passed is True


# --- Pre-asymptotic runs (coordinator decision, 2026-11-19) ---------------------------------
# At b = 10 (kT ~ 15) kh <= 0.2 is not asymptotic for Euler (local orders 0.48 -> 0.93,
# measured by the builder). Rule: an event run is excluded from the event-order fits when its
# decay factor is off by more than 10% over the steps it covers, |R(-kh)^N e^{kNh} - 1| > 0.1,
# N = n_steps, h the event step (N h = T - h/2: the same span as R^N, so a correct method is
# not penalised for the half step), reason containing "pre-asymptotic" (mirrors D9).
PRE_ASYMPTOTIC_TOL = 0.1


def stability_function(method: str, z: float) -> float:
    """Closed forms (integrator_study docstring): Euler 1 + z, RK4 its quartic Taylor
    polynomial, Verlet's trapezoidal velocity update (1 + z/2)/(1 - z/2)."""
    if method == "euler":
        return 1 + z
    if method == "rk4":
        return 1 + z + z**2 / 2 + z**3 / 6 + z**4 / 24
    return (1 + z / 2) / (1 - z / 2)


def decay_mismatch(method: str, k: float, h: float, n: int) -> float:
    return abs(stability_function(method, -k * h) ** n * math.exp(k * n * h) - 1)


@pytest.mark.parametrize("angle", [45.0, 75.0, 90.0])
def test_strong_drag_never_gives_a_false_event_order_fail(
    schemas: ModuleType, model: ModuleType, angle: float
) -> None:
    c = run(schemas, model, parameters=params(angle, 10.0))
    for ch in c.checks:
        if ch.id.startswith("event_order_"):
            assert ch.passed is not False, (ch.id, ch.value, ch.note)
            if ch.passed is None:
                assert ch.note.strip(), ch.id


@pytest.mark.parametrize("angle", [45.0, 75.0, 90.0])
def test_pre_asymptotic_rule_follows_its_closed_form(
    schemas: ModuleType, model: ModuleType, angle: float
) -> None:
    p = params(angle, 10.0)
    s = setup_of(p)
    t_land = analytical.flight_time(s)
    c = run(schemas, model, parameters=p)
    flagged = 0
    for r in c.results:
        for ev in r.event_runs:
            mismatch = decay_mismatch(r.method, s.k, ev.h, ev.n_steps)
            if ev.in_linear_fit or ev.in_hermite_fit:
                assert mismatch <= PRE_ASYMPTOTIC_TOL, (r.method, ev.n_steps, mismatch)
            # Only otherwise-eligible runs must name this reason (others may name another).
            eligible = (
                ev.crossed
                and ev.stability == "stable"
                and s.k * ev.h <= 0.2
                and ev.h <= t_land / 20
                and mismatch > PRE_ASYMPTOTIC_TOL
            )
            if eligible:
                flagged += 1
                for q in KINDS:
                    assert getattr(ev, f"in_{q}_fit") is False
                    assert "pre-asymptotic" in getattr(ev, f"{q}_exclusion_reason")
    assert flagged >= 1  # Euler at kh ~ 0.2: 0.8^N e^{0.2 N} - 1 ~ -0.17 for N ~ 8
