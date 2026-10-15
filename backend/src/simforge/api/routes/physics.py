from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from simforge.api.dependencies import Repository
from simforge.core.errors import ModelDomainError, SolverError
from simforge.core.reproducibility import environment_info, input_hash
from simforge.core.schemas import ModelInfo, RunMetadata
from simforge.persistence.experiments import ExperimentRecord, ExperimentRepository
from simforge.physics.projectile import integrator_model
from simforge.physics.projectile import model as projectile
from simforge.physics.projectile.integrator_schemas import (
    IntegratorStudyRequest,
    IntegratorStudyResponse,
)
from simforge.physics.projectile.schemas import ProjectileRequest, ProjectileResponse

router = APIRouter(prefix="/physics", tags=["physics"])


def _record_run(
    repo: ExperimentRepository,
    model_info: ModelInfo,
    inputs: dict[str, Any],
    summary: dict[str, Any],
    *,
    save: bool,
    elapsed_ms: float,
) -> RunMetadata:
    """Build run metadata and, if requested, store the run in the experiment log.

    ``inputs`` must contain exactly the fields that affect the numbers, so that identical
    computations share an input hash.
    """
    env = environment_info()
    run_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    digest = input_hash(inputs)
    if save:
        repo.add(
            ExperimentRecord(
                run_id=run_id,
                model_id=model_info.id,
                model_version=model_info.version,
                created_at=created_at,
                input_hash=digest,
                inputs=inputs,
                summary=summary,
                environment=env,
            )
        )
    return RunMetadata(
        run_id=run_id,
        created_at=created_at,
        input_hash=digest,
        elapsed_ms=elapsed_ms,
        experiment_saved=save,
        **env,
    )


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

    metadata = _record_run(
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

    metadata = _record_run(
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
