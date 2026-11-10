"""Seam 3: one quadratic-drag run, assembled (roadmap 2.1): guard, references, checks.

Expected values come from independent sources: the linear model's closed form with b = 0
(a different code path from this model's textbook vacuum formulas), the identity
c v_t^2 = m g, the exact vertical flight R3, and a test-local SciPy integration of the
drag time S = integral of kappa |v| dt. Never from the model under test.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterator

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import ValidationCheck
from simforge.physics.projectile import analytical
from simforge.physics.projectile import quadratic_model as qm
from simforge.physics.projectile import quadratic_reference as qr
from simforge.physics.projectile.numerical import NumericalSolution
from simforge.physics.projectile.quadratic_numerical import QuadraticSetup
from simforge.physics.projectile.schemas import SolverSettings

G = 9.80665


def make_setup(
    v0: float = 20.0, angle: float = 45.0, h: float = 0.0, v_t: float = 20.0, m: float = 1.0
) -> QuadraticSetup:
    c = 0.0 if math.isinf(v_t) else m * G / v_t**2
    return QuadraticSetup(v0, math.radians(angle), h, m, c, G)


def run(s: QuadraticSetup, method: str = "DOP853", rtol: float = 1e-10) -> qm.QuadraticComputation:
    solver = SolverSettings(method=method, rtol=rtol, atol=rtol)  # type: ignore[arg-type]
    return qm.run(s, solver)


def numbers(obj: object) -> Iterator[float]:
    """Every float in a computation (dataclasses, Pydantic models, lists), recursively."""
    if isinstance(obj, float):
        yield obj
    elif isinstance(obj, list | tuple):
        for item in obj:
            yield from numbers(item)
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from numbers(getattr(obj, f.name))
    elif hasattr(obj, "model_dump"):
        yield from numbers(list(obj.model_dump().values()))
    elif isinstance(obj, dict):
        yield from numbers(list(obj.values()))


def reference_drag_time(s: QuadraticSetup) -> float:
    """Test-local reference for S = integral of kappa |v| dt over the flight (= kappa x path
    length): SciPy DOP853 at rtol = atol = 1e-12, with S as an extra state."""
    kappa = s.drag_constant / s.mass
    vx0 = (
        0.0 if s.launch_angle_rad == math.pi / 2 else s.initial_speed * math.cos(s.launch_angle_rad)
    )

    def rhs(_t: float, y: np.ndarray) -> list[float]:
        v = math.hypot(y[2], y[3])
        return [y[2], y[3], -kappa * v * y[2], -G - kappa * v * y[3], kappa * v]

    def landing(t: float, y: np.ndarray) -> float:
        return float(y[1]) if t > 0 else 1.0

    landing.terminal = True
    landing.direction = -1
    y0 = [0.0, s.launch_height, vx0, s.initial_speed * math.sin(s.launch_angle_rad), 0.0]
    t_end = 2 * qr.flight_time_bound(
        s.initial_speed, s.launch_angle_rad, s.launch_height, s.terminal_speed, G
    )
    sol = solve_ivp(rhs, (0.0, t_end), y0, method="DOP853", rtol=1e-12, atol=1e-12, events=landing)
    assert sol.status == 1
    return float(sol.y_events[0][0][4])


# --- The stiffness guard -------------------------------------------------------------------


@pytest.mark.parametrize("method", ["RK45", "DOP853"])
def test_guard_refuses_a_stiff_run_for_explicit_methods_with_a_reason(method: str) -> None:
    # A 100 km fall at v_t = 3 m/s: S >= kappa h = g h / v_t^2 ~ 1.1e5 drag times, above 1e4.
    s = make_setup(v0=10.0, angle=45.0, h=1e5, v_t=3.0)
    with pytest.raises(ModelDomainError, match=r"Radau") as info:
        run(s, method)
    message = str(info.value)
    assert method in message
    assert "1e+04" in message  # the limit it was compared with


def test_the_same_run_is_accepted_with_radau() -> None:
    # Radau is L-stable: its step is not limited by the drag rate, so it has no such limit.
    s = make_setup(v0=10.0, angle=45.0, h=1e5, v_t=3.0)
    r = run(s, "Radau")
    assert r.numerical.flight_time > 1e5 / 3.0  # it really fell at about v_t
    assert all(c.passed is not False for c in r.checks)


def test_guard_accepts_the_run_the_plans_bound_refused() -> None:
    # Plan D4's rule kappa max(v0, v_t) T_bound gives 6.2e5 here (refused against 1e4), but the
    # flight's drag time S is 6.7 (measured with the reference below; its bound is 19), so an
    # explicit method finishes it in a few hundred steps.
    s = make_setup(v0=1e3, angle=60.0, h=0.0, v_t=30.0)
    kappa = s.drag_constant / s.mass
    plan_rule = (
        kappa * 1e3 * qr.flight_time_bound(1e3, s.launch_angle_rad, 0.0, s.terminal_speed, G)
    )
    assert plan_rule > 1e4
    r = run(s, "RK45")
    assert r.diagnostics.drag_time_bound < 1e4
    assert r.numerical.n_steps < 1000


@pytest.mark.parametrize(
    ("v0", "angle", "h", "v_t"),
    [
        (20.0, 45.0, 0.0, 20.0),
        (1e3, 60.0, 0.0, 30.0),
        (5.0, 0.0, 50.0, 8.0),
        (50.0, 75.0, 100.0, 3.0),
    ],
)
def test_drag_time_bound_holds(v0: float, angle: float, h: float, v_t: float) -> None:
    s = make_setup(v0=v0, angle=angle, h=h, v_t=v_t)
    exact = reference_drag_time(s)
    bound = qm.drag_time_bound(s)
    # The reference's error is ~1e-12 relative plus atol 1e-12 on S; the bound is a proof.
    assert exact <= bound * (1 + 1e-10) + 1e-10
    # Its slack is additive and logarithmic (module docstring): measured <= 27 drag times on
    # a 1007-point grid, and 0.4 to 12.4 on these cases.
    assert bound - exact < 30.0


@pytest.mark.parametrize(("v0", "h", "v_t"), [(30.0, 0.0, 20.0), (1e3, 500.0, 5.0)])
def test_drag_time_bound_is_exact_for_vertical_flights(v0: float, h: float, v_t: float) -> None:
    # Vertically every step of the proof is an equality: S = kappa (2 H + h) exactly.
    s = make_setup(v0=v0, angle=90.0, h=h, v_t=v_t)
    # The reference carries ~1e-12 relative error (rtol) and its S state an absolute 1e-12.
    assert qm.drag_time_bound(s) == pytest.approx(reference_drag_time(s), rel=1e-10, abs=1e-10)


# --- Vacuum: no infinity and no NaN anywhere ----------------------------------------------


@pytest.mark.parametrize("angle", [45.0, 90.0, 0.0])
def test_vacuum_run_has_no_terminal_speed_and_no_nan(angle: float) -> None:
    s = make_setup(v0=20.0, angle=angle, h=5.0, v_t=math.inf)
    r = run(s)
    assert r.terminal_speed is None  # JSON has no infinity
    assert r.diagnostics.drag_time_bound == 0.0
    values = list(numbers(r))
    assert len(values) > 100
    assert all(math.isfinite(v) for v in values)


def test_terminal_speed_balances_weight_and_drag() -> None:
    s = make_setup(m=0.145, v_t=33.0)
    r = run(s)
    assert r.terminal_speed is not None
    # c v_t^2 = m g, a few correctly rounded operations: rel 1e-15.
    assert s.drag_constant * r.terminal_speed**2 == pytest.approx(s.mass * G, rel=1e-15)


# --- The exact drag-free comparison ---------------------------------------------------------


@pytest.mark.parametrize(("angle", "h"), [(45.0, 0.0), (30.0, 12.0), (0.0, 25.0), (90.0, 3.0)])
def test_vacuum_comparison_matches_the_linear_model_without_drag(angle: float, h: float) -> None:
    s = make_setup(v0=20.0, angle=angle, h=h, v_t=15.0)
    vac = run(s).vacuum
    # Independent code path: the linear closed form at b = 0 (psi/phi form, landing by Brent
    # to 4 eps). Both are a few roundings from the true values: rel 1e-14.
    lin = analytical.ProjectileSetup(20.0, math.radians(angle), h, 1.0, 0.0, G)
    t = analytical.flight_time(lin)
    x, _, vx, vy = analytical.state(lin, np.array([t]))
    assert vac.flight_time == pytest.approx(t, rel=1e-14)
    assert vac.range == pytest.approx(float(x[0]), rel=1e-14, abs=1e-14)
    assert vac.apex_time == pytest.approx(analytical.apex_time(lin), rel=1e-14, abs=1e-14)
    assert vac.impact_speed == pytest.approx(math.hypot(vx[0], vy[0]), rel=1e-14)
    _, y_apex, _, _ = analytical.state(lin, np.array([analytical.apex_time(lin)]))
    assert vac.max_height == pytest.approx(float(y_apex[0]), rel=1e-14)
    assert "exact" in vac.method_note.lower()


# --- The vertical reference: only for an exactly vertical launch ---------------------------


def test_vertical_reference_is_given_only_at_exactly_90_degrees() -> None:
    r = run(make_setup(v0=30.0, angle=90.0, h=2.0, v_t=20.0))
    ref = r.vertical_reference
    assert ref is not None
    exact = qr.vertical_flight(30.0, 2.0, make_setup(v_t=20.0).terminal_speed, G)
    assert ref.exact == exact
    # The numerical errors against it: 100 x rtol (see test_quadratic_numerical).
    for err in (ref.flight_time, ref.apex_time, ref.max_height, ref.impact_speed):
        assert err.relative is not None
        assert err.relative < 1e-8
    assert r.numerical.range == 0.0
    # cos(radians(89.99999)) ~ 1.7e-7: a genuinely 2-D launch, so no vertical reference.
    assert run(make_setup(v0=30.0, angle=89.99999, h=2.0, v_t=20.0)).vertical_reference is None
    assert run(make_setup(v0=30.0, angle=45.0, h=2.0, v_t=20.0)).vertical_reference is None


def test_vertical_launch_reports_no_invariant() -> None:
    r = run(make_setup(v0=30.0, angle=90.0, v_t=20.0))
    assert r.diagnostics.max_invariant_residual is None
    assert "vertical" in r.diagnostics.invariant_note


# --- The invariant residual: normalised, and null (not an error) when undefined ------------


def test_invariant_residual_is_small_in_a_long_fall_where_vx_stays_positive() -> None:
    # Relative to I0 the drift here is 0.02 to 0.4 (test_quadratic_numerical), so only the
    # max(1/vx^2) normalisation gives a meaningful number. The smallest vx is ~1e-6 m/s, 1e4
    # times atol, so its sign does not depend on last-bit rounding (CI runs on another CPU).
    r = run(make_setup(v0=20.0, angle=45.0, h=150.0, v_t=10.0))
    assert r.diagnostics.max_invariant_residual is not None
    assert r.diagnostics.max_invariant_residual < 1e-8


def tiny_vx_solution(s: QuadraticSetup, vx_end: float, vy_end: float) -> NumericalSolution:
    """A hand-made two-node solution whose last node has the given velocity. It isolates the
    residual's undefined cases from the solver, whose vx below atol is not controlled
    (its sign there can differ between CPUs)."""
    return NumericalSolution(
        t=np.array([0.0, 1.0]),
        x=np.array([0.0, 1.0]),
        y=np.array([s.launch_height, 0.0]),
        vx=np.array([s.vx0, vx_end]),
        vy=np.array([s.vy0, vy_end]),
        drag_work=np.array([0.0, 1.0]),
        flight_time=1.0,
        apex_time=0.0,
        max_height=s.launch_height,
        n_steps=1,
        n_rhs_evaluations=1,
        method="DOP853",
        rtol=1e-10,
        atol=1e-10,
        dense=None,
    )


@pytest.mark.parametrize(
    "vx_end",
    [
        -9e-14,  # below zero: what DOP853 gives in a long fall below atol (measured)
        0.0,
        1e-170,  # positive, but 1/vx^2 overflows to inf
        1e-153,  # 1/vx^2 = 1e306 is finite, but v vy / vx^2 = -1e310 overflows
    ],
)
def test_invariant_is_null_with_a_reason_when_undefined_or_overflowing(vx_end: float) -> None:
    s = make_setup(v0=20.0, angle=45.0, h=100.0, v_t=100.0)
    residual, note = qm._invariant_residual(s, tiny_vx_solution(s, vx_end, -100.0))
    assert residual is None  # never inf or NaN: JSON has neither
    assert "vx" in note
    assert "atol" in note


def test_invariant_check_is_informational_or_passes_in_a_very_long_fall() -> None:
    # A ~200 s fall (200 tau): the true vx decays to ~1e-85 m/s, far below atol = 1e-10, where
    # the solver does not control it. On the pinning machine DOP853 lets it dip just below
    # zero (measured -9e-14 m/s), so the invariant is undefined; on another CPU last-bit
    # rounding may keep it positive. Either outcome is correct, but never a failed check.
    r = run(make_setup(v0=20.0, angle=45.0, h=2000.0, v_t=10.0))
    check = next(c for c in r.checks if c.id == "hodograph_invariant")
    assert math.isfinite(check.value)
    if r.diagnostics.max_invariant_residual is None:
        assert "atol" in r.diagnostics.invariant_note
        assert check.kind == "informational"
        assert check.passed is None
    else:
        assert check.kind == "numerical_diagnostic"
        assert check.passed is True


# --- Checks and labels ------------------------------------------------------------------------


def test_checks_are_present_labelled_and_pass_by_default() -> None:
    r = run(make_setup(v0=100.0, angle=30.0, h=10.0, v_t=20.0))
    ids = [c.id for c in r.checks]
    assert ids == [
        "energy_balance",
        "hodograph_invariant",
        "speed_bound",
        "flight_time_bound",
        "drag_time",
    ]
    for c in r.checks:
        assert c.label
        assert c.note
        if c.kind == "informational":
            assert c.threshold is None
            assert c.passed is None
        else:
            assert c.threshold is not None
            assert c.passed is True
    assert r.diagnostics.max_energy_balance_residual < 1e-8


@pytest.mark.parametrize(
    ("v0", "angle", "h", "v_t", "method", "rtol", "atol"),
    [
        # Nearly vertical: vx0 = 1.7e-4 m/s, so atol = 1e-10 allows 6e-7 relative error in vx
        # per step, far more than atol/v0 = 1e-10. Default tolerances; measured residual 3.5e-6.
        (1.0, 89.99, 0.0, 1.0, "RK45", 1e-10, 1e-10),
        (1.0, 89.999, 0.0, 1.0, "RK45", 1e-10, 1e-10),
        (20.0, 89.999, 0.0, 1e3, "DOP853", 1e-13, 1e-13),
        # A long fall at v_t = 1 m/s with atol = 0.1: late in the flight I tests vy against
        # -v_t, which atol controls only to 0.1 / v_t = 10% (measured residual 0.39).
        (1e4, 30.0, 0.0, 1.0, "RK45", 1e-6, 1e-1),
    ],
)
def test_invariant_check_does_not_fail_an_accurate_run(
    v0: float, angle: float, h: float, v_t: float, method: str, rtol: float, atol: float
) -> None:
    """The invariant's threshold must use the velocity scale the solver's atol is measured
    against, min(vx0, v_t), not v0 (sweep of 10 080 runs in the slice 2 review)."""
    s = make_setup(v0=v0, angle=angle, h=h, v_t=v_t)
    solver = SolverSettings(method=method, rtol=rtol, atol=atol)  # type: ignore[arg-type]
    check = next(c for c in qm.run(s, solver).checks if c.id == "hodograph_invariant")
    assert check.threshold is not None
    # Never failed; and a verdict of "passed" only where the threshold could fail a run (the
    # atol = 0.1 case allows 1e4 x 0.1/v_t = 1000, so it gets no verdict: review 2026-11-10).
    assert check.passed is (True if check.threshold <= 1.0 else None)


def test_vertical_run_adds_its_exact_comparison_check() -> None:
    r = run(make_setup(v0=30.0, angle=90.0, v_t=20.0))
    by_id = {c.id: c for c in r.checks}
    assert by_id["vertical_flight_time"].kind == "numerical_diagnostic"
    assert by_id["vertical_flight_time"].passed is True
    assert by_id["hodograph_invariant"].passed is None


def test_vacuum_run_has_no_speed_bound_check() -> None:
    # There is no speed bound in vacuum (a falling ball keeps speeding up).
    r = run(make_setup(v_t=math.inf))
    assert "speed_bound" not in {c.id for c in r.checks}
    assert all(c.passed is not False for c in r.checks)


def test_numerical_result_is_labelled_with_its_solver() -> None:
    r = run(make_setup(), "RK45", rtol=1e-8)
    assert r.numerical.method == "RK45"
    assert r.numerical.rtol == 1e-8
    assert r.numerical.atol == 1e-8


# --- Series ----------------------------------------------------------------------------------


def test_series_end_at_landing_and_vacuum_series_has_its_own_grid() -> None:
    r = run(make_setup(v0=20.0, angle=45.0, h=5.0, v_t=15.0))
    s = r.series
    assert len(s.t) == 400
    assert s.t[-1] == pytest.approx(r.numerical.flight_time, rel=1e-15)
    assert abs(s.y[-1]) < 1e-8
    assert len(s.vacuum_t) == 400
    assert s.vacuum_t[-1] == pytest.approx(r.vacuum.flight_time, rel=1e-15)
    assert abs(s.vacuum_y[-1]) < 1e-9
    # Drag shortens the flight; the energies are consistent with the drag work (R5).
    assert r.numerical.range < r.vacuum.range
    e = np.array(s.kinetic_energy) + np.array(s.potential_energy) + np.array(s.drag_work)
    np.testing.assert_allclose(e, e[0], rtol=1e-8)


def test_checks_fail_for_the_wrong_coupling(monkeypatch: pytest.MonkeyPatch) -> None:
    """The checks are not decoration: with the wrong force law (-kappa|vx|vx, -kappa|vy|vy)
    the energy balance and the invariant fail at default settings (measured 0.29 and 0.24
    against a threshold of ~1e-6), while the loose flight-time bound still passes."""
    from simforge.physics.projectile import quadratic_numerical as qn

    def wrong_coupling(vx: float, vy: float, kappa: float) -> tuple[float, float]:
        return -kappa * abs(vx) * vx, -kappa * abs(vy) * vy

    monkeypatch.setattr(qn, "drag_acceleration", wrong_coupling)
    by_id = {c.id: c for c in run(make_setup(v0=100.0, angle=30.0, h=10.0, v_t=20.0)).checks}
    assert by_id["energy_balance"].passed is False
    assert by_id["hodograph_invariant"].passed is False
    assert by_id["flight_time_bound"].passed is True


# --- Review 2026-11-10: a check that cannot fail is not shown as passed ---------------------


def _graded(comp: qm.QuadraticComputation) -> list[ValidationCheck]:
    return [c for c in comp.checks if c.threshold is not None]


@pytest.mark.parametrize("rtol", [1e-10, 1e-6, 5e-5])
def test_informative_thresholds_still_grade_the_run(rtol: float) -> None:
    """Allowance 1e4 x (rtol + atol/v0) + 1e-9 <= 1 here (at most 1e4 x 5e-5 x (1 + 1/20) =
    0.525), so every graded check gives a verdict and no note calls it uninformative."""
    comp = qm.run(make_setup(), SolverSettings(method="RK45", rtol=rtol, atol=rtol))
    for check in _graded(comp):
        assert check.passed is True, check.id
        assert "uninformative" not in check.note.lower()


@pytest.mark.parametrize(("rtol", "atol"), [(1e-3, 1e-10), (1e-3, 0.1), (2e-4, 1e-10)])
def test_a_threshold_that_cannot_fail_gives_no_verdict(rtol: float, atol: float) -> None:
    """With rtol >= 2e-4 the allowance is 1e4 x rtol >= 2: a relative residual of 100% (or a
    speed twice the *proved* bound) would still be under the threshold. Such a check must
    not be reported as passed: passed is None and the note says why. The value and the
    threshold are still reported, so nothing is hidden."""
    comp = qm.run(make_setup(), SolverSettings(method="RK45", rtol=rtol, atol=atol))
    graded = _graded(comp)
    assert {c.id for c in graded} >= {
        "energy_balance",
        "hodograph_invariant",
        "speed_bound",
        "flight_time_bound",
    }
    for check in graded:
        assert check.passed is None, check.id
        assert "uninformative" in check.note.lower()
        assert check.kind == "numerical_diagnostic"
        assert math.isfinite(check.value)


def test_the_invariant_alone_can_be_uninformative() -> None:
    """The invariant's accuracy scale is rtol + atol/min(vx0, v_t), the others' rtol +
    atol/v0. At 89 degrees vx0 = 20 cos(89 deg) = 0.349 m/s: with atol = 1e-4 the invariant's
    allowance is 1e4 x 1e-4/0.349 = 2.9 (no verdict) while the energy's is 1e4 x (1e-10 +
    1e-4/20) = 0.05 (a verdict)."""
    comp = qm.run(make_setup(angle=89.0), SolverSettings(method="DOP853", rtol=1e-10, atol=1e-4))
    by_id = {c.id: c for c in comp.checks}
    assert by_id["hodograph_invariant"].passed is None
    assert "uninformative" in by_id["hodograph_invariant"].note.lower()
    assert by_id["energy_balance"].passed is True
    assert "uninformative" not in by_id["energy_balance"].note.lower()
