"""Orchestrates one projectile run: exact solution, numerical solution, and their comparison.

Pure computation — no HTTP, no database. The API layer adds run metadata and persistence.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo, ValidationCheck
from simforge.physics.projectile import analytical, angle_sweep
from simforge.physics.projectile.analytical import ProjectileSetup
from simforge.physics.projectile.numerical import NumericalSolution, integrate
from simforge.physics.projectile.schemas import (
    AnalyticalResult,
    AngleSweepRequest,
    Comparison,
    ErrorMetric,
    NumericalResult,
    ProjectileParameters,
    ProjectileRequest,
    ProjectileSeries,
)

MODEL_INFO = ModelInfo(
    id="physics.projectile",
    version="1.1.0",
    name="Projectile motion with linear drag",
    description="2-D point-mass projectile under uniform gravity and linear (Stokes) drag. "
    "Exact closed-form trajectory compared against an adaptive Runge-Kutta integration.",
)

UNITS: dict[str, str] = {
    "initial_speed": "m/s",
    "launch_angle_deg": "deg",
    "launch_height": "m",
    "mass": "kg",
    "drag_coefficient": "kg/s",
    "gravity": "m/s^2",
    "t": "s",
    "x": "m",
    "y": "m",
    "speed": "m/s",
    "flight_time": "s",
    "apex_time": "s",
    "range": "m",
    "max_height": "m",
    "impact_speed": "m/s",
    "energy": "J",
    "max_position_error": "m",
    "max_energy_balance_residual": "dimensionless (fraction of E0)",
}

ASSUMPTIONS: list[Assumption] = [
    Assumption(
        id="point_mass",
        statement="The projectile is a point mass: no rotation, "
        "no lift (e.g. Magnus effect), no change of shape or mass.",
    ),
    Assumption(
        id="uniform_gravity",
        statement="Gravity is uniform and constant. Reasonable "
        "when heights and ranges are tiny compared with the planet's radius.",
    ),
    Assumption(
        id="linear_drag",
        statement="Drag is linear in velocity, F = -b v, with constant "
        "b. This holds at low Reynolds number (small, slow objects in viscous fluids). "
        "Everyday projectiles such as balls experience drag closer to quadratic in "
        "speed, so this model is not quantitatively accurate for them.",
    ),
    Assumption(
        id="still_air", statement="The fluid is at rest (no wind) and buoyancy is neglected."
    ),
    Assumption(
        id="flat_ground",
        statement="The ground is flat at y = 0 and the flight ends at "
        "the first downward crossing of y = 0. Launch is from x = 0.",
    ),
]

ANALYTICAL_NOTE = (
    "Trajectory from the exact closed-form solution, evaluated in float64 with "
    "cancellation-free formulas. Landing time is the root of the exact y(t), located by "
    "Brent's method to ~1e-15 relative tolerance (a closed form via Lambert W exists and is "
    "used as an independent cross-check in tests)."
)

# Beyond this many drag relaxation times (k * T) the problem is stiff for explicit
# Runge-Kutta methods: step size is limited by stability, not accuracy.
EXPLICIT_STIFFNESS_LIMIT = 1e4
IMPLICIT_STIFFNESS_LIMIT = 1e7

# Per-run check thresholds: PROJECTILE_ERROR_F x (rtol + atol / max(R, H)) + PROJECTILE_ERROR_FLOOR,
# R and H the exact range and max height in m. Measured, not proved (SCIENTIFIC_VALIDATION.md,
# physics.projectile, "Per-run checks"): 12 432 runs, worst F needed for a 10x margin 295.
PROJECTILE_ERROR_F = 500.0
PROJECTILE_ERROR_FLOOR = 1e-10  # guard for rounding; F x rtol alone covered every run measured
# R8 allowance in eps, relative to the vacuum range (SCIENTIFIC_VALIDATION.md,
# physics.projectile.angle_sweep, "Per-run checks"): worst measured 2.16 eps, x10 = 21.6.
R8_ALLOWANCE_C = 50.0


@dataclass(frozen=True, slots=True)
class ProjectileComputation:
    analytical: AnalyticalResult
    numerical: NumericalResult
    comparison: Comparison
    series: ProjectileSeries
    checks: list[ValidationCheck]
    elapsed_ms: float


def to_setup(p: ProjectileParameters) -> ProjectileSetup:
    return ProjectileSetup(
        initial_speed=p.initial_speed,
        launch_angle_rad=math.radians(p.launch_angle_deg),
        launch_height=p.launch_height,
        mass=p.mass,
        drag_coefficient=p.drag_coefficient,
        gravity=p.gravity,
    )


def _error(numerical: float, exact: float) -> ErrorMetric:
    abs_err = abs(numerical - exact)
    return ErrorMetric(absolute=abs_err, relative=abs_err / abs(exact) if exact != 0 else None)


def _exact_metrics(setup: ProjectileSetup) -> AnalyticalResult:
    t_flight = analytical.flight_time(setup)
    t_apex = analytical.apex_time(setup)
    x, y, vx, vy = analytical.state(setup, np.array([t_apex, t_flight]))
    return AnalyticalResult(
        flight_time=t_flight,
        range=float(x[1]),
        max_height=float(y[0]),
        apex_time=t_apex,
        impact_speed=float(math.hypot(vx[1], vy[1])),
        method_note=ANALYTICAL_NOTE,
    )


def _numerical_metrics(sol: NumericalSolution) -> NumericalResult:
    return NumericalResult(
        flight_time=sol.flight_time,
        range=float(sol.x[-1]),
        max_height=sol.max_height,
        apex_time=sol.apex_time,
        impact_speed=float(math.hypot(sol.vx[-1], sol.vy[-1])),
        method=sol.method,
        rtol=sol.rtol,
        atol=sol.atol,
        n_steps=sol.n_steps,
        n_rhs_evaluations=sol.n_rhs_evaluations,
    )


def _energies(
    setup: ProjectileSetup, y: np.ndarray, vx: np.ndarray, vy: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    kinetic = 0.5 * setup.mass * (vx**2 + vy**2)
    potential = setup.mass * setup.gravity * y
    return kinetic, potential


UNINFORMATIVE_NOTE = (
    " Uninformative at these tolerances: the threshold allows an error larger than the "
    "quantity itself (above 100%), so the check could not fail and no verdict is given; "
    "tighten rtol and atol for a meaningful check."
)


def _checks(
    exact: AnalyticalResult, comparison: Comparison, rtol: float, atol: float
) -> list[ValidationCheck]:
    # atol is absolute in every state unit; the trajectory's size max(R, H) (> 0: a run with
    # no flight is refused) is the scale it is measured against (SV, "Per-run checks").
    size = max(exact.range, exact.max_height)
    limit = PROJECTILE_ERROR_F * (rtol + atol / size) + PROJECTILE_ERROR_FLOOR
    informative = limit <= 1.0
    formula = (
        f" Threshold: {PROJECTILE_ERROR_F:g} x (rtol + atol / max(R, H)) + "
        f"{PROJECTILE_ERROR_FLOOR:g}, measured on a grid."
    )
    rows = [
        (
            "flight_time_error",
            "Flight time vs the exact solution",
            comparison.flight_time.absolute / exact.flight_time,
            "|T_num - T_exact| / T_exact.",
        ),
        (
            "range_error",
            "Range vs the exact solution",
            comparison.range.absolute / size,
            "|R_num - R_exact| / max(R_exact, H_exact): relative to the trajectory's size, "
            "since R_exact = 0 for a vertical launch.",
        ),
        (
            "max_height_error",
            "Max height vs the exact solution",
            comparison.max_height.absolute / exact.max_height,
            "|H_num - H_exact| / H_exact.",
        ),
        (
            "energy_balance",
            "Energy balance KE + PE + W = E0",
            comparison.max_energy_balance_residual,
            "max |KE + PE + W - E0| / E0 over the step nodes, with W integrated from b|v|^2. "
            "Exactly 0 for the true motion.",
        ),
    ]
    return [
        ValidationCheck(
            id=check_id,
            label=label,
            value=value,
            threshold=limit,
            passed=(value <= limit) if informative else None,
            kind="numerical_diagnostic",
            note=note + formula + ("" if informative else UNINFORMATIVE_NOTE),
        )
        for check_id, label, value, note in rows
    ]


def run(request: ProjectileRequest) -> ProjectileComputation:
    start = time.perf_counter()
    setup = to_setup(request.parameters)
    solver = request.solver

    exact = _exact_metrics(setup)

    stiffness = setup.k * exact.flight_time
    limit = IMPLICIT_STIFFNESS_LIMIT if solver.method == "Radau" else EXPLICIT_STIFFNESS_LIMIT
    if stiffness > limit:
        hint = " Use method='Radau' for stiff problems." if solver.method != "Radau" else ""
        raise ModelDomainError(
            f"The flight lasts {stiffness:.3g} drag relaxation times (k*T), above the "
            f"{limit:.0e} limit for {solver.method}; the run would be prohibitively slow." + hint
        )

    # The exact flight time is used only as a generous cap on integration time; the
    # landing itself is found independently by the solver's event detection.
    sol = integrate(
        setup,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        t_max=2.0 * exact.flight_time,
    )
    numerical = _numerical_metrics(sol)

    # --- Accuracy at the solver's step nodes (the landing node is event-interpolated) ---
    x_ex, y_ex, _vx_ex, _vy_ex = analytical.state(setup, sol.t)
    max_position_error = float(np.max(np.hypot(sol.x - x_ex, sol.y - y_ex)))
    ke, pe = _energies(setup, sol.y, sol.vx, sol.vy)
    e0 = ke[0] + pe[0]  # > 0: initial_speed >= 1e-3 m/s and mass >= 1e-6 kg (schema limits)
    max_energy_residual = float(np.max(np.abs(ke + pe + sol.drag_work - e0)) / e0)

    comparison = Comparison(
        flight_time=_error(numerical.flight_time, exact.flight_time),
        range=_error(numerical.range, exact.range),
        max_height=_error(numerical.max_height, exact.max_height),
        impact_speed=_error(numerical.impact_speed, exact.impact_speed),
        max_position_error=max_position_error,
        max_energy_balance_residual=max_energy_residual,
    )

    # --- Uniform resampling for plots ----------------------------------------------
    t = np.linspace(0.0, sol.flight_time, request.n_samples)
    xs, ys, vxs, vys, ws = sol.sample(t)
    xa, ya, _, _ = analytical.state(setup, t)
    ke_s, pe_s = _energies(setup, ys, vxs, vys)
    series = ProjectileSeries(
        t=t.tolist(),
        x_numerical=xs.tolist(),
        y_numerical=ys.tolist(),
        x_analytical=xa.tolist(),
        y_analytical=ya.tolist(),
        speed_numerical=np.hypot(vxs, vys).tolist(),
        kinetic_energy=ke_s.tolist(),
        potential_energy=pe_s.tolist(),
        drag_work=ws.tolist(),
    )

    checks = _checks(exact, comparison, solver.rtol, solver.atol)
    elapsed_ms = (time.perf_counter() - start) * 1e3
    return ProjectileComputation(exact, numerical, comparison, series, checks, elapsed_ms)


# --- Angle sweep ----------------------------------------------------------------------------

ANGLE_SWEEP_INFO = ModelInfo(
    id="physics.projectile.angle_sweep",
    version="1.1.0",
    name="Range versus launch angle (linear drag)",
    description="Range from the analytical solution at evenly spaced launch angles from 0 to 90 "
    "degrees, and the angle that maximises it, compared with the closed-form vacuum optimum.",
)

ANGLE_SWEEP_UNITS: dict[str, str] = {
    "angle": "deg",
    "range": "m",
    "flight_time": "s",
    "max_height": "m",
}

ANGLE_SWEEP_NOTE = (
    "Every range comes from the analytical linear-drag solution: closed-form motion, with the "
    "landing time found by Brent's method to about 1e-15. The best angle is the best "
    "grid point refined by a bounded Brent search to about 1e-6 degrees. The range curve is "
    "flat at its peak, so the maximum range is known far more precisely than the angle that "
    "achieves it."
)


@dataclass(frozen=True, slots=True)
class AngleSweepComputation:
    result: angle_sweep.AngleSweep
    angles_deg: list[float]
    checks: list[ValidationCheck]
    elapsed_ms: float


def _sweep_checks(setup: ProjectileSetup, result: angle_sweep.AngleSweep) -> list[ValidationCheck]:
    r = [p.range for p in result.points]
    peaks = sum(1 for i in range(1, len(r) - 1) if r[i] > r[i - 1] and r[i] > r[i + 1])
    # (R - V) / V at each grid angle and at the refined best angle (where V > 0: not 90
    # degrees, nor 0 degrees from the ground), and best range against the vacuum best range.
    pairs = [(p.range, angle_sweep.vacuum_range(setup, p.angle_deg)) for p in result.points]
    pairs.append((result.best_range, angle_sweep.vacuum_range(setup, result.best_angle_deg)))
    pairs.append((result.best_range, result.vacuum_best_range))
    excess = max((rng - vac) / vac for rng, vac in pairs if vac > 0)
    allowance = R8_ALLOWANCE_C * float(np.finfo(np.float64).eps)
    return [
        ValidationCheck(
            id="interior_peaks",
            label="Interior peaks of the range curve",
            value=float(peaks),
            threshold=1.0,
            passed=peaks <= 1,
            kind="numerical_diagnostic",
            note="Grid points (not the first or last) whose range is strictly greater than "
            "both neighbours'. One peak is what the refined best angle assumes; 0 means the "
            "best grid point is an edge.",
        ),
        ValidationCheck(
            id="drag_never_lengthens_range",
            label="Drag never lengthens the range (proved, R8)",
            value=excess,
            threshold=allowance,
            passed=excess <= allowance,
            kind="exact_identity",
            note="Largest (R - V) / V over the grid angles and the best angle, V the vacuum "
            "range at the same angle and launch height, and (R* - V*) / V* for the best "
            "ranges. Proved <= 0 for linear drag; the threshold "
            f"{R8_ALLOWANCE_C:g} x eps allows only rounding, measured on a grid.",
        ),
    ]


def run_angle_sweep(request: AngleSweepRequest) -> AngleSweepComputation:
    start = time.perf_counter()
    angles = np.linspace(0.0, 90.0, request.n_angles).tolist()
    setup = to_setup(request.parameters)
    result = angle_sweep.sweep(setup, angles)
    checks = _sweep_checks(setup, result)
    return AngleSweepComputation(result, angles, checks, (time.perf_counter() - start) * 1e3)
