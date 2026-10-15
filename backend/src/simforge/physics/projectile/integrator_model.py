"""Orchestrates the integrator study: engine dataclasses -> validated API contract.

No HTTP and no database: the API layer adds run metadata and persistence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo
from simforge.numerics.convergence import MIN_FIT_POINTS, OrderFit
from simforge.physics.projectile import analytical
from simforge.physics.projectile import integrator_study as study
from simforge.physics.projectile.integrator_schemas import (
    FitRule,
    IntegratorRun,
    IntegratorStudyRequest,
    MethodStudyResult,
    OrderFitResult,
    ReferenceLine,
    TrajectorySample,
    XYSeries,
)
from simforge.physics.projectile.model import ASSUMPTIONS as PROJECTILE_ASSUMPTIONS
from simforge.physics.projectile.model import to_setup

MODEL_INFO = ModelInfo(
    id="physics.projectile.integrators",
    version="1.0.0",
    name="Integrator convergence study (projectile with linear drag)",
    description="Forward Euler, RK4 and velocity Verlet, implemented from scratch, compared "
    "against the exact linear-drag solution over a range of fixed time steps.",
)

UNITS: dict[str, str] = {
    "dt": "s",
    "h": "s",
    "kh": "dimensionless",
    "horizon": "s",
    "k": "1/s",
    "position_error": "m",
    "velocity_error": "m/s",
    "x": "m",
    "y": "m",
}

ASSUMPTIONS: list[Assumption] = [
    *PROJECTILE_ASSUMPTIONS,
    Assumption(
        id="fixed_horizon",
        statement="Every run integrates over the same window [0, T], where T is the exact "
        "flight time, using N = ceil(T/dt) equal steps. Landing is not detected, because "
        "locating it between grid points would add interpolation error that could hide "
        "the method's true order.",
    ),
    Assumption(
        id="error_metric",
        statement="Errors are Euclidean distances from the exact solution at the grid "
        "nodes. The 'max' errors are the largest over all nodes; the 'final' errors are at "
        "t = T. The exact solution is evaluated in float64 (relative error ~1e-15), which "
        "is negligible next to the round-off floor.",
    ),
    Assumption(
        id="linear_invariant",
        statement="v + k r + g t y_hat is constant along the exact solution, and every "
        "Runge-Kutta method (including Euler and RK4) preserves it exactly. Their velocity "
        "error is therefore exactly k times their position error, so their velocity "
        "convergence is not independent evidence. Velocity Verlet does not preserve it.",
    ),
]

FIT_RULE = FitRule(
    max_kh=study.MAX_KH_FOR_FIT,
    max_h_over_horizon=study.MAX_H_OVER_T_FOR_FIT,
    roundoff_safety_factor=study.ROUNDOFF_SAFETY,
    min_points=MIN_FIT_POINTS,
    description=(
        f"A run enters the fit only if it is linearly stable (|R(-kh)| < 1), in the "
        f"asymptotic regime (kh <= {study.MAX_KH_FOR_FIT} and h <= T/"
        f"{round(1 / study.MAX_H_OVER_T_FOR_FIT)}), and its error exceeds "
        f"{study.ROUNDOFF_SAFETY:.0f} x N x machine epsilon x the solution's scale. An "
        f"order is reported only with at least {MIN_FIT_POINTS} such step sizes. The rule "
        "was fixed before any results were inspected."
    ),
)

MAX_STEPS_PER_RUN = 50_000
MAX_TOTAL_STEPS = 150_000


@dataclass(frozen=True, slots=True)
class StudyComputation:
    horizon: float
    k: float
    position_scale: float
    velocity_scale: float
    results: list[MethodStudyResult]
    exact_trajectory: XYSeries
    elapsed_ms: float


def _fit(fit: OrderFit | None, theoretical: int) -> OrderFitResult | None:
    if fit is None:
        return None
    return OrderFitResult(
        order=fit.order,
        theoretical_order=theoretical,
        r_squared=fit.r_squared,
        n_points=fit.n_points,
        h_min=fit.h_min,
        h_max=fit.h_max,
    )


def _reference(
    runs: list[study.RunResult], fit: OrderFit | None, attr: str, flag: str, order: int
) -> ReferenceLine | None:
    """Theoretical-slope line over the fit range, anchored at the finest fitted point.

    Drawn only when a fit exists: the theoretical order is a statement about the
    asymptotic regime, so the line is only meaningful where the data are in it.
    """
    if fit is None:
        return None
    anchor = min((r for r in runs if getattr(r, flag)), key=lambda r: r.h)
    e0: float = getattr(anchor, attr)
    hs = [fit.h_min, fit.h_max]
    return ReferenceLine(order=order, h=hs, error=[e0 * (h / anchor.h) ** order for h in hs])


def _fit_note(m: study.MethodStudy) -> str | None:
    if m.position_fit is not None:
        return None
    n = sum(r.in_position_fit for r in m.runs)
    return (
        f"Only {n} step size(s) satisfied the fit rule (need {MIN_FIT_POINTS}); no order is "
        "claimed. Add smaller steps within the stability and asymptotic limits."
    )


def run(request: IntegratorStudyRequest) -> StudyComputation:
    start = time.perf_counter()
    setup = to_setup(request.parameters)
    horizon = analytical.flight_time(setup)

    steps = [study.steps_for(horizon, dt) for dt in request.dt_values]
    if max(steps) > MAX_STEPS_PER_RUN:
        raise ModelDomainError(
            f"dt = {min(request.dt_values):.3g} s needs {max(steps)} steps over T = "
            f"{horizon:.4g} s; the limit is {MAX_STEPS_PER_RUN} per run. Use larger steps."
        )
    total = sum(steps) * len(request.methods)
    if total > MAX_TOTAL_STEPS:
        raise ModelDomainError(
            f"This study needs {total} steps in total; the limit is {MAX_TOTAL_STEPS}. "
            "Use fewer or larger time steps, or fewer methods."
        )

    result = study.run_study(setup, request.dt_values, request.methods)

    methods: list[MethodStudyResult] = []
    for m in result.methods:
        p = m.theory.order
        methods.append(
            MethodStudyResult(
                method=m.method,
                name=m.theory.name,
                theoretical_order=p,
                stability_limit_kh=m.theory.stability_limit_kh,
                runs=[IntegratorRun.model_validate(r, from_attributes=True) for r in m.runs],
                position_local_orders=m.position_local_orders,
                velocity_local_orders=m.velocity_local_orders,
                position_fit=_fit(m.position_fit, p),
                velocity_fit=_fit(m.velocity_fit, p),
                position_reference=_reference(
                    m.runs, m.position_fit, "max_position_error", "in_position_fit", p
                ),
                velocity_reference=_reference(
                    m.runs, m.velocity_fit, "max_velocity_error", "in_velocity_fit", p
                ),
                fit_note=_fit_note(m),
                trajectory=(
                    TrajectorySample(
                        h=m.trajectory[2], x=m.trajectory[0].tolist(), y=m.trajectory[1].tolist()
                    )
                    if m.trajectory is not None
                    else None
                ),
            )
        )

    x_ref, y_ref = result.exact_trajectory
    return StudyComputation(
        horizon=result.horizon,
        k=result.k,
        position_scale=result.position_scale,
        velocity_scale=result.velocity_scale,
        results=methods,
        exact_trajectory=XYSeries(x=x_ref.tolist(), y=y_ref.tolist()),
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )
