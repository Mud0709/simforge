from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from simforge.api.dependencies import Repository
from simforge.api.recording import record_run
from simforge.core.errors import ModelDomainError, SolverError
from simforge.core.schemas import ModelInfo
from simforge.physics.projectile import integrator_model
from simforge.physics.projectile import model as projectile
from simforge.physics.projectile.integrator_schemas import (
    IntegratorStudyRequest,
    IntegratorStudyResponse,
)
from simforge.physics.projectile.schemas import (
    AngleSweepRequest,
    AngleSweepResponse,
    ProjectileRequest,
    ProjectileResponse,
)

router = APIRouter(prefix="/physics", tags=["physics"])


@router.get("/projectile/info")
def projectile_info() -> ModelInfo:
    return projectile.MODEL_INFO


@router.post("/projectile/simulate")
async def simulate_projectile(request: ProjectileRequest, repo: Repository) -> ProjectileResponse:
    try:
        # CPU-bound work runs in a worker thread so the event loop stays responsive.
        result = await run_in_threadpool(projectile.run, request)
    except ModelDomainError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except SolverError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    metadata = record_run(
        repo,
        projectile.MODEL_INFO,
        # Only the inputs that affect the numbers are hashed (not save_experiment).
        request.model_dump(include={"parameters", "solver", "n_samples"}),
        {
            "analytical": result.analytical.model_dump(exclude={"method_note"}),
            "numerical": result.numerical.model_dump(),
            "comparison": result.comparison.model_dump(),
        },
        save=request.save_experiment,
        elapsed_ms=result.elapsed_ms,
    )
    return ProjectileResponse(
        model=projectile.MODEL_INFO,
        parameters=request.parameters,
        solver=request.solver,
        units=projectile.UNITS,
        assumptions=projectile.ASSUMPTIONS,
        analytical=result.analytical,
        numerical=result.numerical,
        comparison=result.comparison,
        series=result.series,
        metadata=metadata,
    )


@router.post("/projectile/integrators")
async def integrator_study(
    request: IntegratorStudyRequest, repo: Repository
) -> IntegratorStudyResponse:
    try:
        result = await run_in_threadpool(integrator_model.run, request)
    except ModelDomainError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    metadata = record_run(
        repo,
        integrator_model.MODEL_INFO,
        request.model_dump(include={"parameters", "dt_values", "methods"}),
        {
            "horizon": result.horizon,
            "methods": {
                m.method: {
                    "theoretical_order": m.theoretical_order,
                    "position_order": m.position_fit.order if m.position_fit else None,
                    "position_fit_points": m.position_fit.n_points if m.position_fit else 0,
                    "velocity_order": m.velocity_fit.order if m.velocity_fit else None,
                    "finest_max_position_error": m.runs[-1].max_position_error,
                }
                for m in result.results
            },
        },
        save=request.save_experiment,
        elapsed_ms=result.elapsed_ms,
    )
    return IntegratorStudyResponse(
        model=integrator_model.MODEL_INFO,
        parameters=request.parameters,
        dt_values=request.dt_values,
        methods=request.methods,
        units=integrator_model.UNITS,
        assumptions=integrator_model.ASSUMPTIONS,
        horizon=result.horizon,
        k=result.k,
        position_scale=result.position_scale,
        velocity_scale=result.velocity_scale,
        fit_rule=integrator_model.FIT_RULE,
        results=result.results,
        exact_trajectory=result.exact_trajectory,
        metadata=metadata,
    )


@router.post("/projectile/angle-sweep")
async def projectile_angle_sweep(
    request: AngleSweepRequest, repo: Repository
) -> AngleSweepResponse:
    computation = await run_in_threadpool(projectile.run_angle_sweep, request)
    r = computation.result
    # The launch angle does not affect a sweep, so it is left out of the hashed inputs.
    params = request.parameters.model_dump(exclude={"launch_angle_deg"})
    metadata = record_run(
        repo,
        projectile.ANGLE_SWEEP_INFO,
        {"parameters": params, "n_angles": request.n_angles},
        {
            "best_angle_deg": r.best_angle_deg,
            "best_range": r.best_range,
            "vacuum_best_angle_deg": r.vacuum_best_angle_deg,
            "vacuum_best_range": r.vacuum_best_range,
        },
        save=request.save_experiment,
        elapsed_ms=computation.elapsed_ms,
    )
    return AngleSweepResponse(
        model=projectile.ANGLE_SWEEP_INFO,
        parameters=request.parameters,
        units=projectile.ANGLE_SWEEP_UNITS,
        assumptions=projectile.ASSUMPTIONS,
        angles_deg=computation.angles_deg,
        ranges=[p.range for p in r.points],
        flight_times=[p.flight_time for p in r.points],
        max_heights=[p.max_height for p in r.points],
        best_angle_deg=r.best_angle_deg,
        best_range=r.best_range,
        vacuum_best_angle_deg=r.vacuum_best_angle_deg,
        vacuum_best_range=r.vacuum_best_range,
        method_note=projectile.ANGLE_SWEEP_NOTE,
        metadata=metadata,
    )
