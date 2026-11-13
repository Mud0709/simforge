"""Seam 3: one oscillator run, its checks, nulls and guard (roadmap 2.3, slice 2).

Written test-first: ``simforge.physics.oscillator.model`` (and ``numerical``) do not exist
when these tests are written, so they are imported inside each test (the ``model`` and ``num``
fixtures). The tests collect, and fail with ModuleNotFoundError, until they are built.

What is checked, and against what:
- the corner grid (``test_corner_grid``: 3 methods x 4 (rtol, atol) pairs x the four Regime
  values x free/driven = 96 runs) and the Risks corners (``test_corner_grid_risks``): every
  diagnostic check passes, its threshold is the measured constant of ``oscillator_thresholds``
  (so the model's numbers cannot drift from the measured ones), the loosest settings are
  labelled uninformative, and the evidence (each value / threshold, max|v| / (w0 X), the
  N_max run time) is recorded with ``record_property`` (``pytest --junitxml``);
- the diagnostics are the defined errors, recomputed here from ``numerical.integrate``'s
  nodes and the exact solution ``analytical.state`` (independent of the model's assembly);
- the free-decay residuals against OR4, the steady state and resonance curve against their
  formulas written here, the nulls of D12, the stiffness guard (refusing before any solve),
  and a planted wrong damping law that the checks must catch.

Interface the builder implements (module ``simforge.physics.oscillator.model``):

    MODEL_INFO (id "physics.oscillator", version "1.0.0"), UNITS (with an "atol" entry naming
    the scale X), ASSUMPTIONS, MAX_CYCLES (= N_MAX, the measured cycle limit).

    run(inputs: OscillatorInputs, duration: float, solver: SolverSettings, *,
        n_samples: int = 400) -> OscillatorComputation
        SolverSettings is the shared ``simforge.physics.projectile.schemas.SolverSettings``.
        Calls ``numerical.integrate(inputs, duration=duration, scale=analytical.scale(inputs,
        duration), method=..., rtol=..., atol=...)`` exactly once, after the guard.
        Guard: the stiffness number S = |fastest eigenvalue| x T, i.e. (gamma + beta) T when
        overdamped and w0 T otherwise; RK45 and DOP853 are refused with ModelDomainError when
        S > EXPLICIT_STIFFNESS_LIMIT (1e4, from projectile.model), before any solve; the message
        gives S as f"{S:.3g}", the limit as f"{limit:.0e}", the method, and suggests Radau.

    OscillatorComputation attributes used here:
        derived (== analytical.derived), scale (X, m, == analytical.scale), velocity_scale
        (V = w0 X, m/s), steady_state (== analytical.steady_state: None when F0 = 0 or b = 0),
        numerical (.final_displacement, .final_velocity, .n_steps, .n_rhs_evaluations,
        .method, .rtol, .atol), diagnostics (below), checks (list[ValidationCheck]), series
        (below), resonance (None when F0 = 0 or b = 0; else .angular_frequency, .amplitude,
        .phase_lag, lists from w = 0 to max(3 w0, 1.2 w)), elapsed_ms.
    diagnostics: max_displacement_error (max |x - x_exact| / X over the step nodes),
        max_velocity_error (max |v - v_exact| / (w0 X)), max_energy_balance_residual
        (max |KE + PE + W_damp - W_drive - E0| / (k X^2)), free_decay_period_residual and
        free_decay_ratio_residual (first two interior maxima: w0 |(t2 - t1) - T_d| and
        |x2 - e^{-gamma T_d} x1| / X; None unless free, underdamped and >= 2 maxima),
        remaining_transient (the transient left at t = T as a fraction of A; None unless
        driven and damped), cycles (T max(w0, w) / 2 pi), stiffness_number (S above).
    series: t (n_samples times, evenly from 0 to T), x, v, x_exact, v_exact, envelope
        (analytical.transient_envelope; None unless underdamped), kinetic_energy,
        potential_energy, damping_work, drive_work (lists of float, SI).
    checks (ids): "displacement_error", "velocity_error", "energy_balance" (always;
        numerical_diagnostic); "free_decay_period", "free_decay_ratio" (only when the
        free-decay residuals exist); "steady_state_reached" (informational, only when driven
        and damped; value = remaining_transient); "cost" (informational, value =
        n_rhs_evaluations, its note giving the cycles and the stiffness number). Every
        non-informational check has threshold = FACTOR (rtol + atol)(1 + ERROR_GROWTH_PER_CYCLE
        cycles) + FLOOR with the model's own constants equal to oscillator_thresholds', and its
        note contains "uninformative" exactly when that threshold exceeds 1; passed is then
        None (no verdict), otherwise value <= threshold.
"""

from __future__ import annotations

import importlib
import math
from types import ModuleType
from typing import Any, cast

import numpy as np
import pytest

from simforge.core.errors import ModelDomainError
from simforge.physics.oscillator import analytical as osc
from simforge.physics.projectile.schemas import SolverSettings
from tests.approx import rel_approx
from tests.physics.oscillator_thresholds import (
    DEFAULT,
    LOOSEST,
    METHODS,
    MIDDLE,
    N_MAX,
    REGIMES,
    RISK_RUNS,
    RISK_SETTINGS,
    TIGHTEST,
    TOLERANCE_PAIRS,
    CheckKind,
    Method,
    Run,
    cycles,
    regime_run,
    threshold,
)

EPS = float(np.finfo(float).eps)  # 2.2e-16
EXPLICIT_STIFFNESS_LIMIT = 1e4  # plan D6; the shared constant of projectile.model

DIAGNOSTIC_IDS = {"displacement_error", "velocity_error", "energy_balance"}
FREE_DECAY_IDS = {"free_decay_period", "free_decay_ratio"}
INFORMATIONAL_IDS = {"steady_state_reached", "cost", "free_decay_not_checked"}
PAIR_IDS = {TIGHTEST: "tightest", DEFAULT: "default", MIDDLE: "middle", LOOSEST: "loosest"}


@pytest.fixture
def model() -> ModuleType:
    """The module under test, imported when a test runs, not at collection (docstring)."""
    return importlib.import_module("simforge.physics.oscillator.model")


@pytest.fixture
def num() -> ModuleType:
    return importlib.import_module("simforge.physics.oscillator.numerical")


def run_model(
    model: ModuleType,
    run: Run,
    method: Method,
    pair: tuple[float, float],
    n_samples: int = 50,
) -> Any:
    rtol, atol = pair
    solver = SolverSettings(method=method, rtol=rtol, atol=atol)
    return model.run(run.inputs, run.duration, solver, n_samples=n_samples)


def solve(num: ModuleType, run: Run, method: Method, pair: tuple[float, float]) -> Any:
    """The numerical solve exactly as the model's contract makes it (deterministic)."""
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


def by_id(comp: Any) -> dict[str, Any]:
    checks = {c.id: c for c in comp.checks}
    assert len(checks) == len(comp.checks), "check ids must be unique"
    return checks


def max_speed_ratio(run: Run) -> float:
    """max |v_exact| / (w0 X) on a fine grid (40 points per cycle): evidence for V = w0 X."""
    p = run.inputs
    n = int(4001 + 40 * cycles(p, run.duration))
    _, v = osc.state(p, np.linspace(0.0, run.duration, n))
    return float(np.max(np.abs(v))) / (w0_of(p) * osc.scale(p, run.duration))


def assert_checks_pass(
    comp: Any,
    run: Run,
    pair: tuple[float, float],
    record_property: Any,
) -> None:
    p = run.inputs
    rtol, atol = pair
    checks = by_id(comp)
    assert set(checks) <= DIAGNOSTIC_IDS | FREE_DECAY_IDS | INFORMATIONAL_IDS
    assert DIAGNOSTIC_IDS | {"cost"} <= set(checks)
    driven_damped = p.drive_amplitude > 0 and p.damping_coefficient > 0
    assert ("steady_state_reached" in checks) == driven_damped
    free_underdamped = p.drive_amplitude == 0 and osc.derived(p).regime == "underdamped"
    # A free underdamped run either has both free-decay checks or says why not (review
    # 2026-11-10, item 6); no other run mentions them.
    has_decay = set(checks) >= FREE_DECAY_IDS
    assert has_decay or not FREE_DECAY_IDS & set(checks)
    assert ("free_decay_not_checked" in checks) == (free_underdamped and not has_decay)
    if not free_underdamped:
        assert not FREE_DECAY_IDS & set(checks)
    elif pair != LOOSEST:
        # Every free underdamped run here has at least two interior maxima; at the loosest
        # pair the solver may miss one (seen in scratch), so the checks may then be absent.
        assert set(checks) >= FREE_DECAY_IDS
    for check in comp.checks:
        if check.id in INFORMATIONAL_IDS:
            assert check.kind == "informational"
            assert check.threshold is None
            assert check.passed is None
            record_property(check.id, check.value)
            continue
        assert check.kind != "informational"
        expected = threshold(cast(CheckKind, check.id), rtol, atol, p, run.duration)
        # Same formula and constants; the model may group the products differently: 8 eps.
        assert check.threshold == rel_approx(expected, 8 * EPS)
        record_property(f"{check.id}_over_threshold", check.value / check.threshold)
        assert check.value <= check.threshold, f"{check.id}: {check.value:.3g}"
        # A threshold above 1 cannot fail, so it gives no verdict (review 2026-11-10).
        assert check.passed is (None if check.threshold > 1.0 else True)
        # Plan (slice 2 review notes): a threshold above 1 in scaled units says nothing.
        assert ("uninformative" in check.note.lower()) == (check.threshold > 1.0)
    record_property("max_v_over_w0X", max_speed_ratio(run))


# --- The corner grid (slice 2 Acceptance, check 1) ---------------------------------------------


@pytest.mark.parametrize("driven", [False, True], ids=["free", "driven"])
@pytest.mark.parametrize("regime", REGIMES)
@pytest.mark.parametrize("pair", TOLERANCE_PAIRS, ids=[PAIR_IDS[p] for p in TOLERANCE_PAIRS])
@pytest.mark.parametrize("method", METHODS)
def test_corner_grid(
    model: ModuleType,
    method: Method,
    pair: tuple[float, float],
    regime: osc.Regime,
    driven: bool,
    record_property: Any,
) -> None:
    run = regime_run(regime, driven)
    assert osc.derived(run.inputs).regime == regime
    comp = run_model(model, run, method, pair)
    assert_checks_pass(comp, run, pair, record_property)


RISK_CASES = [
    pytest.param(name, method, pair, id=f"{name}-{method}-{PAIR_IDS[pair]}")
    for name, settings in RISK_SETTINGS.items()
    for method, pair in settings
]


@pytest.mark.parametrize(("name", "method", "pair"), RISK_CASES)
def test_corner_grid_risks(
    model: ModuleType,
    name: str,
    method: Method,
    pair: tuple[float, float],
    record_property: Any,
) -> None:
    run = RISK_RUNS[name]
    comp = run_model(model, run, method, pair)
    assert_checks_pass(comp, run, pair, record_property)
    # N_max timing is a recorded measurement, never a timed assertion (plan review notes).
    record_property("elapsed_ms", comp.elapsed_ms)
    record_property("cycles", comp.diagnostics.cycles)


def test_n_max_corners_are_n_max_cycles_long() -> None:
    # cycles = T max(w0, w) / 2 pi with T = N_MAX 2 pi / w0 and w <= w0: a few roundings.
    for name in ("n_max_cycles_undamped", "n_max_cycles_driven"):
        run = RISK_RUNS[name]
        assert cycles(run.inputs, run.duration) == rel_approx(N_MAX, 8 * EPS)


def test_max_cycles_is_the_measured_n_max(model: ModuleType) -> None:
    assert model.MAX_CYCLES == N_MAX


ALL_RUNS = {
    **{
        f"{r}-{'driven' if d else 'free'}": regime_run(r, d) for r in REGIMES for d in (False, True)
    },
    **RISK_RUNS,
}


@pytest.mark.parametrize("name", list(ALL_RUNS))
def test_thresholds_exceed_the_exact_solutions_own_floor(name: str) -> None:
    """The checks compare with ``analytical.state``, whose own error is (measured in slice 1,
    worst c = 1.46) c eps (Q + w0 T + A/X + 1) X with c <= 1.5. A threshold near that floor
    would fail a perfect solver; 10x above it, the floor uses at most a tenth of the margin.
    (The slice 1 error model is for x; it is applied to the displacement threshold only.)"""
    run = ALL_RUNS[name]
    p = run.inputs
    d = osc.derived(p)
    ss = osc.steady_state(p)
    quality = d.quality_factor or 0.0
    amplitude = ss.amplitude if ss is not None else 0.0
    x_scale = osc.scale(p, run.duration)
    floor = 1.5 * EPS * (quality + w0_of(p) * run.duration + amplitude / x_scale + 1)
    assert threshold("displacement_error", *TIGHTEST, p, run.duration) >= 10 * floor


# --- The diagnostics are the defined errors (V = w0 X, energy / k X^2) ------------------------

# Driven at w = 3 w0, so a velocity scale max(w0, w) X (the slice 1 note's, replaced on
# 2026-11-09) would report a third of the defined error and fail the comparison below.
FAST_DRIVE = Run(
    osc.OscillatorInputs(
        mass=1.0,
        spring_constant=25.0,
        damping_coefficient=0.5,
        drive_amplitude=1.0,
        drive_angular_frequency=15.0,
        initial_displacement=0.1,
        initial_velocity=-0.2,
    ),
    3.0,
)


@pytest.mark.parametrize("method", METHODS)
def test_diagnostics_are_the_node_errors_scaled_by_x_and_w0x(
    model: ModuleType, num: ModuleType, method: Method
) -> None:
    run = FAST_DRIVE
    p = run.inputs
    comp = run_model(model, run, method, DEFAULT)
    sol = solve(num, run, method, DEFAULT)  # the same solve: same nodes
    x_scale = osc.scale(p, run.duration)
    w0 = w0_of(p)
    m, k = p.mass, p.spring_constant
    x_exact, v_exact = osc.state(p, np.asarray(sol.t, dtype=np.float64))
    dx = float(np.max(np.abs(sol.x - x_exact))) / x_scale
    dv = float(np.max(np.abs(sol.v - v_exact))) / (w0 * x_scale)
    e0 = 0.5 * m * p.initial_velocity**2 + 0.5 * k * p.initial_displacement**2
    balance = 0.5 * m * sol.v**2 + 0.5 * k * sol.x**2 + sol.damping_work - sol.drive_work - e0
    de = float(np.max(np.abs(balance))) / (k * x_scale**2)
    diag = comp.diagnostics
    # Same nodes, same references: the model may only round x_exact or the scaling
    # differently, a few eps of X (16 eps in scaled units). The energy sums four terms of order
    # max(1, (v/V)^2) <= 1 here (|v| <= w0 X measured for this run), so 64 eps.
    assert abs(diag.max_displacement_error - dx) <= 16 * EPS
    assert abs(diag.max_velocity_error - dv) <= 16 * EPS
    assert abs(diag.max_energy_balance_residual - de) <= 64 * EPS
    assert comp.velocity_scale == rel_approx(w0 * x_scale, 2 * EPS)
    assert comp.scale == x_scale
    checks = by_id(comp)
    assert checks["displacement_error"].value == diag.max_displacement_error
    assert checks["velocity_error"].value == diag.max_velocity_error
    assert checks["energy_balance"].value == diag.max_energy_balance_residual
    numerical = comp.numerical
    assert numerical.n_steps == sol.n_steps
    assert numerical.n_rhs_evaluations == sol.n_rhs_evaluations
    assert numerical.final_displacement == sol.x[-1]
    assert numerical.final_velocity == sol.v[-1]
    assert (numerical.method, numerical.rtol, numerical.atol) == (method, *DEFAULT)
    assert checks["cost"].value == numerical.n_rhs_evaluations


@pytest.mark.parametrize("method", METHODS)
def test_free_decay_residuals_use_the_first_two_maxima(
    model: ModuleType, num: ModuleType, method: Method
) -> None:
    run = regime_run("underdamped", driven=False)
    p = run.inputs
    comp = run_model(model, run, method, DEFAULT)
    sol = solve(num, run, method, DEFAULT)
    assert len(sol.maxima_t) >= 2
    w0 = w0_of(p)
    gamma = p.damping_coefficient / (2 * p.mass)
    period = 2 * math.pi / math.sqrt(w0 * w0 - gamma * gamma)  # T_d, from the definitions
    (t1, t2), (x1, x2) = sol.maxima_t[:2], sol.maxima_x[:2]
    period_residual = w0 * abs((t2 - t1) - period)
    ratio_residual = abs(x2 - math.exp(-gamma * period) * x1) / osc.scale(p, run.duration)
    diag = comp.diagnostics
    # Scaled times reach w0 t2 = 12.6 rad, so regrouping (tau or t, T_d from analytical or
    # here) moves the period residual by a few eps of that: 64 eps. The ratio: 64 eps too.
    assert abs(diag.free_decay_period_residual - period_residual) <= 64 * EPS
    assert abs(diag.free_decay_ratio_residual - ratio_residual) <= 64 * EPS
    checks = by_id(comp)
    assert checks["free_decay_period"].value == diag.free_decay_period_residual
    assert checks["free_decay_ratio"].value == diag.free_decay_ratio_residual


@pytest.mark.parametrize(("regime", "driven"), [(r, d) for r in REGIMES for d in (False, True)])
def test_cycles_and_stiffness_number_follow_their_definitions(
    model: ModuleType, regime: osc.Regime, driven: bool
) -> None:
    run = regime_run(regime, driven)
    p = run.inputs
    comp = run_model(model, run, "DOP853", DEFAULT)
    w0 = w0_of(p)
    gamma = p.damping_coefficient / (2 * p.mass)
    # |fastest eigenvalue| of x'' + 2 gamma x' + w0^2 x = 0: gamma + beta when overdamped,
    # and w0 otherwise (|complex pair| = w0; the double root at critical damping is w0).
    rate = gamma + math.sqrt(gamma * gamma - w0 * w0) if regime == "overdamped" else w0
    # A few roundings each (sqrt, sums, products): 8 eps.
    assert comp.diagnostics.stiffness_number == rel_approx(rate * run.duration, 8 * EPS)
    assert comp.diagnostics.cycles == rel_approx(cycles(p, run.duration), 8 * EPS)


# --- Nulls (plan D12) -------------------------------------------------------------------------


def test_undriven_run_has_no_steady_state_resonance_or_drive_work(model: ModuleType) -> None:
    run = regime_run("underdamped", driven=False)
    comp = run_model(model, run, "DOP853", DEFAULT)
    assert comp.steady_state is None
    assert comp.resonance is None
    assert comp.diagnostics.remaining_transient is None
    assert all(w == 0.0 for w in comp.series.drive_work)
    assert comp.series.envelope is not None  # underdamped: the decay envelope exists
    assert comp.diagnostics.free_decay_period_residual is not None
    assert comp.diagnostics.free_decay_ratio_residual is not None


@pytest.mark.parametrize("driven", [False, True], ids=["free", "driven"])
def test_undamped_run_has_no_quality_factor_steady_state_envelope_or_damping_work(
    model: ModuleType, driven: bool
) -> None:
    run = regime_run("undamped", driven)
    comp = run_model(model, run, "DOP853", DEFAULT)
    assert comp.derived.quality_factor is None
    assert comp.steady_state is None  # no steady state without damping (analytical)
    assert comp.resonance is None  # A has a pole at w0 without damping
    assert comp.series.envelope is None
    assert comp.diagnostics.remaining_transient is None
    assert comp.diagnostics.free_decay_period_residual is None  # only for underdamped runs
    assert comp.diagnostics.free_decay_ratio_residual is None
    assert all(w == 0.0 for w in comp.series.damping_work)


@pytest.mark.parametrize("driven", [False, True], ids=["free", "driven"])
def test_overdamped_run_has_no_damped_frequency_envelope_or_free_decay(
    model: ModuleType, driven: bool
) -> None:
    run = regime_run("overdamped", driven)
    comp = run_model(model, run, "DOP853", DEFAULT)
    assert comp.derived.damped_angular_frequency is None
    assert comp.derived.damped_period is None
    assert comp.derived.overdamped_rate is not None
    assert comp.series.envelope is None
    assert comp.diagnostics.free_decay_period_residual is None
    assert comp.diagnostics.free_decay_ratio_residual is None
    if driven:
        # zeta = 4 >= 1/sqrt(2): A falls monotonically from w = 0, so there is no peak (OR5).
        assert comp.steady_state is not None
        assert comp.steady_state.peak_angular_frequency is None
        assert comp.steady_state.peak_amplitude is None
    else:
        assert comp.steady_state is None


@pytest.mark.parametrize(("regime", "driven"), [(r, d) for r in REGIMES for d in (False, True)])
def test_closed_forms_are_passed_through_unchanged(
    model: ModuleType, regime: osc.Regime, driven: bool
) -> None:
    run = regime_run(regime, driven)
    p = run.inputs
    comp = run_model(model, run, "DOP853", DEFAULT)
    assert comp.derived == osc.derived(p)
    assert comp.scale == osc.scale(p, run.duration)
    assert comp.steady_state == osc.steady_state(p)


def test_driven_damped_run_reports_the_steady_state_and_resonance_curve(model: ModuleType) -> None:
    run = regime_run("underdamped", driven=True)
    p = run.inputs
    comp = run_model(model, run, "DOP853", DEFAULT)
    w0 = w0_of(p)
    gamma = p.damping_coefficient / (2 * p.mass)
    f = p.drive_amplitude / p.mass
    w = p.drive_angular_frequency
    # OR1 written out here: A = f / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2), delta = atan2(2 gamma
    # w, w0^2 - w^2). w0^2 - w^2 = 16 and 2 gamma w = 1.5 are exact here: a few roundings.
    assert comp.steady_state.amplitude == rel_approx(
        f / math.hypot(w0**2 - w**2, 2 * gamma * w), 4 * EPS
    )
    assert comp.steady_state.phase_lag == rel_approx(
        math.atan2(2 * gamma * w, w0**2 - w**2), 4 * EPS
    )
    curve = comp.resonance
    omega = np.asarray(curve.angular_frequency, dtype=np.float64)
    assert len(omega) >= 2
    assert len(curve.amplitude) == len(omega) == len(curve.phase_lag)
    assert omega[0] == 0.0
    assert omega[-1] == rel_approx(max(3 * w0, 1.2 * w), 2 * EPS)  # plan D9
    assert np.all(np.diff(omega) > 0)
    # Near w0, w0^2 - w^2 computed in floats here loses up to eps w0^2 absolutely, against a
    # denominator >= 2 gamma w ~ 2.5: about 10 eps relative in A; 64 eps covers it.
    expected = f / np.hypot(w0**2 - omega**2, 2 * gamma * omega)
    assert np.asarray(curve.amplitude) == rel_approx(expected, 64 * EPS)
    phase = np.asarray(curve.phase_lag)
    assert np.all((phase >= 0.0) & (phase <= math.pi))


def test_steady_state_reached_is_the_remaining_transient_as_a_fraction_of_a(
    model: ModuleType,
) -> None:
    # Critically damped (gamma = 5 /s), driven, 20 s: the transient is (a + b t) e^{-5 t},
    # about 1e-41 of its start at the end, so the value is ~0 (< 1e-12 whatever its norm).
    p = regime_run("critically_damped", driven=True).inputs
    long_run = run_model(model, Run(p, 20.0), "DOP853", DEFAULT)
    reached = by_id(long_run)["steady_state_reached"]
    assert reached.value == long_run.diagnostics.remaining_transient
    assert 0.0 <= reached.value < 1e-12
    # Underdamped (gamma = 0.25 /s), 3 s: e^{-0.75} = 0.47 of a transient that starts at about
    # 0.6 A (x0 - A cos delta = 0.038 m against A = 0.062 m), so well above 1e-2.
    short = run_model(model, regime_run("underdamped", driven=True), "DOP853", DEFAULT)
    assert short.diagnostics.remaining_transient > 1e-2


# --- Series -----------------------------------------------------------------------------------


def test_series_are_resampled_on_an_even_grid_with_exact_references(model: ModuleType) -> None:
    run = regime_run("underdamped", driven=True)
    p = run.inputs
    n = 37  # odd, as plan D15's stored-fields case
    comp = run_model(model, run, "DOP853", DEFAULT, n_samples=n)
    s = comp.series
    t = np.asarray(s.t, dtype=np.float64)
    assert len(t) == n
    for values in (
        s.x,
        s.v,
        s.x_exact,
        s.v_exact,
        s.envelope,
        s.kinetic_energy,
        s.potential_energy,
        s.damping_work,
        s.drive_work,
    ):
        assert len(values) == n
    assert t[0] == 0.0
    assert t == rel_approx(np.linspace(0.0, run.duration, n), 2 * EPS)
    x_exact, v_exact = osc.state(p, t)
    x_scale = osc.scale(p, run.duration)
    # The exact columns are analytical.state at these times: the same function, so equal up to
    # the rounding of t itself (2 eps of t, times |v| <= w0 X): 8 eps of the scale.
    assert np.max(np.abs(np.asarray(s.x_exact) - x_exact)) <= 8 * EPS * x_scale
    assert np.max(np.abs(np.asarray(s.v_exact) - v_exact)) <= 8 * EPS * w0_of(p) * x_scale
    envelope = osc.transient_envelope(p, t)
    assert envelope is not None
    assert np.asarray(s.envelope) == rel_approx(envelope, 8 * EPS)
    # KE = m v^2 / 2 and PE = k x^2 / 2 of the numerical series: two or three roundings.
    v, x = np.asarray(s.v), np.asarray(s.x)
    assert np.asarray(s.kinetic_energy) == rel_approx(0.5 * p.mass * v**2, 4 * EPS)
    assert np.asarray(s.potential_energy) == rel_approx(0.5 * p.spring_constant * x**2, 4 * EPS)


# --- The stiffness guard ----------------------------------------------------------------------

# Overdamped, m = 1 kg, k = 1 N/m, b = 150 kg/s: gamma = 75 /s, beta = sqrt(75^2 - 1), so
# S = (gamma + beta) T = 1.5e4 over T = 100 s, above the 1e4 limit for explicit methods.
STIFF = Run(
    osc.OscillatorInputs(
        mass=1.0, spring_constant=1.0, damping_coefficient=150.0, initial_displacement=0.1
    ),
    100.0,
)


def stiff_number() -> float:
    gamma = 75.0
    return (gamma + math.sqrt(gamma * gamma - 1.0)) * STIFF.duration


@pytest.mark.parametrize("method", ["RK45", "DOP853"])
def test_guard_refuses_a_stiff_explicit_run_before_any_solve(
    model: ModuleType, num: ModuleType, method: Method, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_solve(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the run was solved before the guard refused it")

    monkeypatch.setattr(num, "integrate", no_solve)
    monkeypatch.setattr(model, "integrate", no_solve, raising=False)  # if imported by name
    monkeypatch.setattr(num, "solve_ivp", no_solve, raising=False)
    with pytest.raises(ModelDomainError) as info:
        run_model(model, STIFF, method, DEFAULT)
    message = str(info.value)
    assert stiff_number() > EXPLICIT_STIFFNESS_LIMIT
    assert f"{stiff_number():.3g}" in message  # names its number: "1.5e+04"
    assert f"{EXPLICIT_STIFFNESS_LIMIT:.0e}" in message  # and the limit: "1e+04"
    assert method in message
    assert "Radau" in message  # says what to change


def test_the_same_stiff_run_is_accepted_with_radau(model: ModuleType) -> None:
    comp = run_model(model, STIFF, "Radau", DEFAULT)
    assert comp.diagnostics.stiffness_number == rel_approx(stiff_number(), 8 * EPS)
    assert all(c.passed is not False for c in comp.checks)


# --- A planted error must fail the checks -----------------------------------------------------


def wrong_damping(eta: float, zeta: float) -> float:
    """-b v |v| / V in place of -b v, scaled (plan, seam 2): -2 zeta eta |eta|."""
    return -2.0 * zeta * eta * abs(eta)


@pytest.mark.parametrize("driven", [False, True], ids=["free", "driven"])
def test_planted_wrong_damping_fails_the_checks(
    model: ModuleType, num: ModuleType, driven: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(num, "damping_acceleration", wrong_damping)
    comp = run_model(model, regime_run("underdamped", driven), "DOP853", DEFAULT)
    checks = by_id(comp)
    # Measured in scratch: energy residual 0.030 to 0.15 of k X^2 and displacement error 0.056
    # to 0.12 of X for these runs, against thresholds near 3e-6.
    assert checks["energy_balance"].passed is False
    assert checks["displacement_error"].passed is False


# --- Model metadata ---------------------------------------------------------------------------


def test_model_info_units_and_assumptions(model: ModuleType) -> None:
    assert model.MODEL_INFO.id == "physics.oscillator"
    assert model.MODEL_INFO.version == "1.0.0"
    # atol is dimensionless, a fraction of the scale X (plan D5).
    assert "X" in model.UNITS["atol"]
    assert "dimensionless" in model.UNITS["atol"]
    ids = [a.id for a in model.ASSUMPTIONS]
    assert ids
    assert len(set(ids)) == len(ids)
