"""Orchestrates one projectile run: exact solution, numerical solution, and their comparison.

Pure computation — no HTTP, no database. The API layer adds run metadata and persistence.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo
from simforge.physics.projectile import analytical
from simforge.physics.projectile.analytical import ProjectileSetup
from simforge.physics.projectile.numerical import NumericalSolution, integrate
from simforge.physics.projectile.schemas import (
    AnalyticalResult,
    Comparison,
    ErrorMetric,
    NumericalResult,
    ProjectileParameters,
    ProjectileRequest,
    ProjectileSeries,
)

MODEL_INFO = ModelInfo(
    id="physics.projectile",
    version="1.0.0",
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


@dataclass(frozen=True, slots=True)
class ProjectileComputation:
    analytical: AnalyticalResult
    numerical: NumericalResult
    comparison: Comparison
    series: ProjectileSeries
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

    # --- Accuracy at the solver's own step nodes (pure integration error) -------------
    x_ex, y_ex, _vx_ex, _vy_ex = analytical.state(setup, sol.t)
    max_position_error = float(np.max(np.hypot(sol.x - x_ex, sol.y - y_ex)))
    ke, pe = _energies(setup, sol.y, sol.vx, sol.vy)
    e0 = ke[0] + pe[0]  # > 0 because initial_speed > 0 and launch_height >= 0
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

    elapsed_ms = (time.perf_counter() - start) * 1e3
    return ProjectileComputation(exact, numerical, comparison, series, elapsed_ms)
