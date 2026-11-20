"""Per-run checks of ``physics.projectile`` and ``physics.projectile.angle_sweep`` (roadmap 2.4,
slice 3, plan D13; notes section 1). Both models go to version 1.1.0.

Contract (the builder implements it; these tests pin it):

``model.run(request).checks`` (new field ``ProjectileComputation.checks: list[ValidationCheck]``,
also returned as ``checks`` by ``/api/v1/physics/projectile/simulate``), in this order, all
``kind = "numerical_diagnostic"``, every value a dimensionless relative error:

- ``flight_time_error``: |T_num - T_exact| / T_exact (= ``comparison.flight_time.relative``).
- ``range_error``: |R_num - R_exact| / max(R_exact, H_exact), relative to the trajectory's
  size, since R_exact = 0 for a vertical launch (H_exact > 0 always: a run with no flight is
  refused).
- ``max_height_error``: |H_num - H_exact| / H_exact (= ``comparison.max_height.relative``).
- ``energy_balance``: ``comparison.max_energy_balance_residual`` (max |KE + PE + W - E0| / E0).

Thresholds ``PROJECTILE_ERROR_F * (rtol + atol / scale) + PROJECTILE_ERROR_FLOOR``, both named
constants in ``simforge.physics.projectile.model``, 1-2-5 values, measured on a grid (methods
x tolerance pairs x corners, recorded in SCIENTIFIC_VALIDATION.md with the machine) with at
least 10x margin over the worst need (notes section 1). ``scale`` is a size of the run in the
units atol applies to (the builder chooses and documents it, e.g. max(R, H) in m). A
threshold above 1 would allow an error above 100%: then ``passed = None`` and the note says
"uninformative" (as quadratic drag v1.0.1 and the oscillator).

``model.run_angle_sweep(request).checks`` (new field ``AngleSweepComputation.checks``, also
returned as ``checks`` by ``/api/v1/physics/projectile/angle-sweep``), in this order:

- ``interior_peaks``: kind ``numerical_diagnostic``, value = number of grid points i (not the
  first or last) whose range is strictly greater than both neighbours'; threshold 1.0;
  passed = value <= 1 (0 means the best grid point is an edge).
- ``drag_never_lengthens_range``: R8, a proved inequality (the label or note says "proved"),
  kind not ``informational``. With V(a) the vacuum range at angle a and the sweep's launch
  height, value = the largest of (R_i - V(a_i)) / V(a_i) over grid angles with V(a_i) > 0,
  (R* - V(a*)) / V(a*) at the refined best angle a* (if V(a*) > 0), and (R* - V*) / V* against
  the vacuum best range V*. Threshold ``R8_ALLOWANCE_C * eps`` (``model.R8_ALLOWANCE_C``,
  a measured 1-2-5 value; eps = 2.22e-16); passed = value <= threshold.

Planted errors (seams used, no new production seam): the drag sign flipped everywhere
(``ProjectileSetup.k`` returns -b/m), and the drag sign flipped in the numerical solver only
(``numerical.integrate`` given b -> -b).
"""

from __future__ import annotations

import dataclasses
import itertools
import math
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import ValidationCheck
from simforge.physics.projectile import model, numerical
from simforge.physics.projectile.analytical import ProjectileSetup
from simforge.physics.projectile.schemas import (
    AngleSweepRequest,
    ProjectileParameters,
    ProjectileRequest,
    SolverSettings,
)
from tests.approx import rel_approx

EPS = float(np.finfo(np.float64).eps)
PROJECTILE_IDS = ["flight_time_error", "range_error", "max_height_error", "energy_balance"]
SWEEP_IDS = ["interior_peaks", "drag_never_lengthens_range"]
METHODS = ["RK45", "DOP853", "Radau"]
TOLERANCE_PAIRS = [(1e-13, 1e-14), (1e-10, 1e-10), (1e-6, 1e-6), (1e-3, 0.1)]
# The notes' rule (section 1): factors are at least 10x the worst need measured on the grid.
MARGIN = 10.0

# BUILDER MAY SET
# Test-side allowance for R8 per angle, in units of eps relative to the vacuum range. Measured
# 2026-11-19 on the current analytical sweep (scratch: v0 in {0.01, 1, 20, 300, 1e4} m/s,
# b in {0, 1e-12, 1e-6, 0.1, 10, 1e4} kg/s at m = 1 kg, h in {0, 10, 1e3, 1e5} m, 10/91/361
# angles; and the corners below): the largest (R - V)/V was 2.1 eps, in vacuum (b = 0), where
# R and V are the same quantity computed two ways and differ only by rounding. 50 leaves ~24x.
R8_TEST_C = 50.0
# Agreement of a check's value with the test's own evaluation of the same formula: the two
# differ only in rounding (a few ulps of O(1) quantities), so 1e-12 relative is ample.
SAME_FORMULA_REL = 1e-12
# The R8 value is an O(1) difference of relative ranges, possibly 0: compared absolutely;
# two evaluations of the vacuum closed form differ by a few eps, 1e-14 is ~45 eps.
SAME_FORMULA_ABS = 1e-14
# END OF BUILDER MAY SET


def run(
    params: ProjectileParameters | None = None,
    method: str = "DOP853",
    rtol: float = 1e-10,
    atol: float = 1e-10,
) -> Any:
    solver = SolverSettings(method=method, rtol=rtol, atol=atol)
    request = ProjectileRequest(
        parameters=params or ProjectileParameters(), solver=solver, save_experiment=False
    )
    return model.run(request)


def sweep(params: ProjectileParameters | None = None, n_angles: int = 91) -> Any:
    request = AngleSweepRequest(
        parameters=params or ProjectileParameters(), n_angles=n_angles, save_experiment=False
    )
    return model.run_angle_sweep(request)


def checks_of(comp: Any) -> dict[str, ValidationCheck]:
    return {c.id: c for c in comp.checks}


def is_one_two_five(x: float) -> bool:
    mantissa = x / 10.0 ** math.floor(math.log10(x))
    return any(math.isclose(mantissa, m, rel_tol=1e-12) for m in (1.0, 2.0, 5.0))


def vacuum_range(v0: float, angle_deg: float, h: float, g: float) -> float:
    """Test-local closed form: vx0 (vy0 + sqrt(vy0^2 + 2 g h)) / g; 0 for a vertical launch."""
    if angle_deg == 90.0:
        return 0.0
    a = math.radians(angle_deg)
    vx0, vy0 = v0 * math.cos(a), v0 * math.sin(a)
    return vx0 * (vy0 + math.sqrt(vy0 * vy0 + 2.0 * g * h)) / g


def vacuum_best_range(v0: float, h: float, g: float) -> float:
    """Closed form v0 sqrt(v0^2 + 2 g h) / g (maximum of vacuum_range over the angle)."""
    return v0 * math.sqrt(v0 * v0 + 2.0 * g * h) / g


def expected_r8_value(p: ProjectileParameters, comp: Any) -> float:
    """The contract's R8 value, computed from the sweep's ranges and test-side vacuum ranges."""
    res = comp.result
    v0, h, g = p.initial_speed, p.launch_height, p.gravity
    excesses = []
    for point in res.points:
        v = vacuum_range(v0, point.angle_deg, h, g)
        if v > 0:
            excesses.append((point.range - v) / v)
    v = vacuum_range(v0, res.best_angle_deg, h, g)
    if v > 0:
        excesses.append((res.best_range - v) / v)
    v_best = vacuum_best_range(v0, h, g)
    excesses.append((res.best_range - v_best) / v_best)
    return float(max(excesses))


def assert_well_formed(check: ValidationCheck) -> None:
    assert check.label
    assert check.note
    assert math.isfinite(check.value)
    if check.kind == "informational":
        assert check.threshold is None
        assert check.passed is None


# --- Versions and constants ---------------------------------------------------------------------


def test_both_models_are_version_1_1_0() -> None:
    assert model.MODEL_INFO.id == "physics.projectile"
    assert model.MODEL_INFO.version == "1.1.0"
    assert model.ANGLE_SWEEP_INFO.id == "physics.projectile.angle_sweep"
    assert model.ANGLE_SWEEP_INFO.version == "1.1.0"


def test_thresholds_are_named_one_two_five_constants() -> None:
    for name in ("PROJECTILE_ERROR_F", "PROJECTILE_ERROR_FLOOR", "R8_ALLOWANCE_C"):
        value = getattr(model, name)
        assert isinstance(value, float), name
        assert value > 0, name
        assert is_one_two_five(value), (name, value)


# --- Default runs ---------------------------------------------------------------------------


def test_default_projectile_run_shows_its_checks_and_all_pass() -> None:
    comp = run()
    assert [c.id for c in comp.checks] == PROJECTILE_IDS
    for c in comp.checks:
        assert_well_formed(c)
        assert c.kind == "numerical_diagnostic"
        assert c.threshold is not None
        assert c.passed is True, c.id
        assert "uninformative" not in c.note.lower()


def test_projectile_check_values_follow_the_contract() -> None:
    """The values are the stated errors against the exact solution, not something else."""
    for params in [
        ProjectileParameters(),
        ProjectileParameters(launch_angle_deg=90.0, launch_height=5.0),
        ProjectileParameters(launch_angle_deg=0.0, launch_height=50.0, drag_coefficient=1.0),
    ]:
        comp = run(params, method="RK45", rtol=1e-6, atol=1e-6)
        by_id = checks_of(comp)
        exact, cmp_ = comp.analytical, comp.comparison
        size = max(exact.range, exact.max_height)
        expected = {
            "flight_time_error": cmp_.flight_time.absolute / exact.flight_time,
            "range_error": cmp_.range.absolute / size,
            "max_height_error": cmp_.max_height.absolute / exact.max_height,
            "energy_balance": cmp_.max_energy_balance_residual,
        }
        for check_id, value in expected.items():
            assert by_id[check_id].value == rel_approx(value, rel=SAME_FORMULA_REL), check_id
        rtol = 1e-6
        floor = model.PROJECTILE_ERROR_FLOOR
        for c in comp.checks:  # F (rtol + atol/scale) + floor >= F rtol + floor, any scale
            assert c.threshold is not None
            assert c.threshold >= (model.PROJECTILE_ERROR_F * rtol + floor) * (1 - 1e-12)


def test_default_sweep_shows_its_checks_and_all_pass() -> None:
    p = ProjectileParameters()
    comp = sweep(p)
    assert [c.id for c in comp.checks] == SWEEP_IDS
    for c in comp.checks:
        assert_well_formed(c)
        assert c.passed is True, c.id
    by_id = checks_of(comp)
    peaks = by_id["interior_peaks"]
    assert peaks.kind == "numerical_diagnostic"
    assert peaks.value == 1.0  # the plan's "interior peaks = 1" on the default grid
    assert peaks.threshold == 1.0
    r8 = by_id["drag_never_lengthens_range"]
    assert r8.kind != "informational"
    assert "proved" in (r8.label + r8.note).lower()
    assert r8.threshold == rel_approx(model.R8_ALLOWANCE_C * EPS, rel=1e-15)
    # Default b = 0.1 kg/s, m = 1 kg: drag shortens every range by a visible fraction.
    assert r8.value < -1e-3


def test_interior_peaks_counts_strict_local_maxima_of_the_grid() -> None:
    for p, n in [(ProjectileParameters(), 91), (ProjectileParameters(launch_height=1e5), 10)]:
        comp = sweep(p, n)
        r = [pt.range for pt in comp.result.points]
        count = sum(1 for i in range(1, len(r) - 1) if r[i] > r[i - 1] and r[i] > r[i + 1])
        peaks = checks_of(comp)["interior_peaks"]
        assert peaks.value == float(count)
        assert peaks.passed is (count <= 1)


def test_default_api_responses_carry_the_checks(client: TestClient) -> None:
    body = client.post("/api/v1/physics/projectile/simulate", json={"save_experiment": False})
    assert body.status_code == 200
    data = body.json()
    assert data["model"]["version"] == "1.1.0"
    assert [c["id"] for c in data["checks"]] == PROJECTILE_IDS
    assert all(c["passed"] is True for c in data["checks"])
    body = client.post("/api/v1/physics/projectile/angle-sweep", json={"save_experiment": False})
    assert body.status_code == 200
    data = body.json()
    assert data["model"]["version"] == "1.1.0"
    assert [c["id"] for c in data["checks"]] == SWEEP_IDS
    assert all(c["passed"] is True for c in data["checks"])


# --- The threshold grid ---------------------------------------------------------------------

# The corners of the allowed space (as test_physics_limits.py): mass, speed, k = b/m, g, h, angle.
CORNERS = [
    c
    for c in itertools.product(
        [1e-6, 1e6], [1e-3, 1e4], [0.0, 1e4], [0.01, 1000.0], [0.0, 1e5], [0.001, 90.0]
    )
    if c[2] * c[0] <= 1e6  # b = k m within its schema limit
]


def corner_params(mass: float, speed: float, k: float, g: float, h: float, angle: float) -> Any:
    return ProjectileParameters(
        mass=mass,
        initial_speed=speed,
        drag_coefficient=k * mass,
        gravity=g,
        launch_height=h,
        launch_angle_deg=angle,
    )


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("rtol", "atol"), TOLERANCE_PAIRS)
def test_checks_pass_or_give_no_verdict_on_the_grid(method: str, rtol: float, atol: float) -> None:
    """Every corner either is refused by the stiffness guard (ModelDomainError) or runs with
    every check passing or giving no verdict; a verdict keeps the 10x margin; threshold > 1
    (an allowance above 100%) gives passed = None, and only then."""
    ran = 0
    for corner in CORNERS:
        try:
            comp = run(corner_params(*corner), method=method, rtol=rtol, atol=atol)
        except ModelDomainError:
            continue
        ran += 1
        assert [c.id for c in comp.checks] == PROJECTILE_IDS
        for c in comp.checks:
            case = (c.id, method, rtol, atol, corner, c.value, c.threshold)
            assert_well_formed(c)
            assert c.threshold is not None
            if c.threshold > 1.0:
                assert c.passed is None, case
                assert "uninformative" in c.note.lower(), case
            else:
                assert c.passed is True, case
                assert "uninformative" not in c.note.lower(), case
                assert c.value * MARGIN <= c.threshold, case
    assert ran > 0


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("rtol", "atol"), TOLERANCE_PAIRS)
@pytest.mark.parametrize("params", [{}, {"launch_height": 100.0, "launch_angle_deg": 0.0},
                                    {"launch_angle_deg": 90.0}, {"drag_coefficient": 0.0},
                                    {"initial_speed": 300.0, "drag_coefficient": 5.0}])  # fmt: skip
def test_ordinary_runs_pass_at_every_method_and_tolerance(
    method: str, rtol: float, atol: float, params: dict[str, float]
) -> None:
    comp = run(ProjectileParameters(**params), method=method, rtol=rtol, atol=atol)
    for c in comp.checks:
        case = (c.id, c.value, c.threshold)
        assert c.passed is (None if c.threshold is not None and c.threshold > 1.0 else True), case


def test_a_threshold_above_100_percent_gives_no_verdict() -> None:
    """v0 = 0.1 m/s: the whole trajectory is ~1e-3 m and E0 = 5e-3 J, so atol = 0.1 is
    ~100x the run's size; with rtol = 1e-3 every threshold exceeds 1 for any scale that is a
    size of this run and any factor >= 1, so no check can give a verdict."""
    comp = run(ProjectileParameters(initial_speed=0.1), method="RK45", rtol=1e-3, atol=0.1)
    assert [c.id for c in comp.checks] == PROJECTILE_IDS
    for c in comp.checks:
        assert c.threshold is not None, c.id
        assert c.threshold > 1.0, c.id
        assert c.passed is None, c.id
        assert "uninformative" in c.note.lower(), c.id
        assert c.kind == "numerical_diagnostic"
        assert math.isfinite(c.value)


@pytest.mark.parametrize("corner", [c[:5] for c in CORNERS if c[5] == 0.001])
def test_sweep_checks_hold_at_the_corners(corner: tuple[float, ...]) -> None:
    mass, speed, k, g, h = corner
    p = corner_params(mass, speed, k, g, h, 45.0)
    comp = sweep(p, n_angles=10)
    by_id = checks_of(comp)
    assert [c.id for c in comp.checks] == SWEEP_IDS
    assert by_id["interior_peaks"].passed is True  # measured: 0 or 1 at every corner
    assert by_id["drag_never_lengthens_range"].passed is True


# --- R8: drag never lengthens the range ---------------------------------------------------------


@pytest.mark.parametrize("v0", [1.0, 20.0, 1e4])
@pytest.mark.parametrize("b", [0.0, 1e-12, 0.1, 1e4])
@pytest.mark.parametrize("h", [0.0, 10.0, 1e5])  # ground and cliff launches
def test_drag_never_lengthens_the_range_at_any_angle(v0: float, b: float, h: float) -> None:
    """R8 (proved for linear drag, any launch height, vx0 > 0): at every grid angle the range
    with drag is at most the vacuum range at that angle (test-side closed form), up to
    R8_TEST_C eps of rounding; and the check reports exactly that comparison."""
    p = ProjectileParameters(initial_speed=v0, drag_coefficient=b, launch_height=h, mass=1.0)
    comp = sweep(p)
    for point in comp.result.points:
        v = vacuum_range(v0, point.angle_deg, h, p.gravity)
        assert point.range <= v * (1.0 + R8_TEST_C * EPS), (point.angle_deg, point.range, v)
    best = vacuum_best_range(v0, h, p.gravity)
    assert comp.result.best_range <= best * (1.0 + R8_TEST_C * EPS)
    r8 = checks_of(comp)["drag_never_lengthens_range"]
    assert abs(r8.value - expected_r8_value(p, comp)) <= SAME_FORMULA_ABS
    assert r8.passed is True


# --- Planted errors ---------------------------------------------------------------------------


def flip_drag_everywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """k = -b/m: drag pushes along the motion, in the exact solution and the solver alike."""
    monkeypatch.setattr(ProjectileSetup, "k", property(lambda s: -s.drag_coefficient / s.mass))


def test_wrong_drag_sign_everywhere_fails_a_projectile_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact and numerical solutions then agree with each other, but W is still integrated
    from +b|v|^2: the energy balance breaks (measured residual 1.06 at the default run,
    2026-11-19, against thresholds near 1e-6)."""
    flip_drag_everywhere(monkeypatch)
    comp = run()
    assert any(c.passed is False for c in comp.checks), [(c.id, c.value) for c in comp.checks]


def test_wrong_drag_sign_everywhere_fails_the_sweeps_r8(monkeypatch: pytest.MonkeyPatch) -> None:
    """A forward 'drag' lengthens the range beyond vacuum (measured: up to 36% at the default
    parameters, 2026-11-19), which R8 forbids."""
    flip_drag_everywhere(monkeypatch)
    comp = sweep()
    r8 = checks_of(comp)["drag_never_lengthens_range"]
    assert r8.passed is False
    assert r8.value > 0.1


def test_wrong_drag_sign_in_the_solver_fails_the_exact_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The solver alone gets b -> -b: its flight time is off by 10%, range 47%, height 21%
    (measured at the default run, 2026-11-19), far above any informative threshold."""
    original = numerical.integrate

    def wrong_sign(setup: ProjectileSetup, **kwargs: Any) -> Any:
        flipped = dataclasses.replace(setup, drag_coefficient=-setup.drag_coefficient)
        return original(flipped, **kwargs)

    monkeypatch.setattr(numerical, "integrate", wrong_sign)
    if hasattr(model, "integrate"):  # model.py may import the function by name
        monkeypatch.setattr(model, "integrate", wrong_sign)
    by_id = checks_of(run())
    assert by_id["flight_time_error"].passed is False
    assert by_id["range_error"].passed is False
    assert by_id["max_height_error"].passed is False
