from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from simforge.api.dependencies import Repository
from simforge.api.runs import ModelEntry, execute
from simforge.core.schemas import ModelInfo, RunMetadata
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


# --- Projectile ---------------------------------------------------------------------------


def _projectile_response(
    request: ProjectileRequest, result: projectile.ProjectileComputation, metadata: RunMetadata
) -> ProjectileResponse:
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


PROJECTILE = ModelEntry(
    info=projectile.MODEL_INFO,
    request_type=ProjectileRequest,
    compute=projectile.run,
    # Only the inputs that affect the numbers are hashed (not save_experiment).
    inputs=lambda req, _: req.model_dump(include={"parameters", "solver", "n_samples"}),
    summary=lambda r: {
        "analytical": r.analytical.model_dump(exclude={"method_note"}),
        "numerical": r.numerical.model_dump(),
        "comparison": r.comparison.model_dump(),
    },
    respond=_projectile_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=lambda inputs, _: ProjectileRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
)


@router.get("/projectile/info")
def projectile_info() -> ModelInfo:
    return projectile.MODEL_INFO


@router.post("/projectile/simulate")
async def simulate_projectile(request: ProjectileRequest, repo: Repository) -> ProjectileResponse:
    return await execute(PROJECTILE, request, repo, save=request.save_experiment)


# --- Integrator study ---------------------------------------------------------------------


def _study_summary(result: integrator_model.StudyComputation) -> dict[str, Any]:
    return {
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
    }


def _study_response(
    request: IntegratorStudyRequest,
    result: integrator_model.StudyComputation,
    metadata: RunMetadata,
) -> IntegratorStudyResponse:
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


INTEGRATOR_STUDY = ModelEntry(
    info=integrator_model.MODEL_INFO,
    request_type=IntegratorStudyRequest,
    compute=integrator_model.run,
    inputs=lambda req, _: req.model_dump(include={"parameters", "dt_values", "methods"}),
    summary=_study_summary,
    respond=_study_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=lambda inputs, _: IntegratorStudyRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
)


@router.post("/projectile/integrators")
async def integrator_study(
    request: IntegratorStudyRequest, repo: Repository
) -> IntegratorStudyResponse:
    return await execute(INTEGRATOR_STUDY, request, repo, save=request.save_experiment)


# --- Angle sweep --------------------------------------------------------------------------


def _sweep_response(
    request: AngleSweepRequest, computation: projectile.AngleSweepComputation, metadata: RunMetadata
) -> AngleSweepResponse:
    r = computation.result
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


ANGLE_SWEEP = ModelEntry(
    info=projectile.ANGLE_SWEEP_INFO,
    request_type=AngleSweepRequest,
    compute=projectile.run_angle_sweep,
    # The launch angle does not affect a sweep, so it is left out of the hashed inputs (and a
    # rebuilt request uses the default angle).
    inputs=lambda req, _: {
        "parameters": req.parameters.model_dump(exclude={"launch_angle_deg"}),
        "n_angles": req.n_angles,
    },
    summary=lambda c: {
        "best_angle_deg": c.result.best_angle_deg,
        "best_range": c.result.best_range,
        "vacuum_best_angle_deg": c.result.vacuum_best_angle_deg,
        "vacuum_best_range": c.result.vacuum_best_range,
    },
    respond=_sweep_response,
    elapsed_ms=lambda c: c.elapsed_ms,
    rebuild=lambda inputs, _: AngleSweepRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
)


@router.post("/projectile/angle-sweep")
async def projectile_angle_sweep(
    request: AngleSweepRequest, repo: Repository
) -> AngleSweepResponse:
    return await execute(ANGLE_SWEEP, request, repo, save=request.save_experiment)
