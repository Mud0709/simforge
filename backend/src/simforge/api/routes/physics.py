from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from simforge.api.dependencies import Repository
from simforge.core.errors import ModelDomainError, SolverError
from simforge.core.reproducibility import environment_info, input_hash
from simforge.core.schemas import ModelInfo, RunMetadata
from simforge.persistence.experiments import ExperimentRecord
from simforge.physics.projectile import model as projectile
from simforge.physics.projectile.schemas import ProjectileRequest, ProjectileResponse

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

    # Only the inputs that affect the numbers are hashed (not save_experiment).
    inputs = request.model_dump(include={"parameters", "solver", "n_samples"})
    env = environment_info()
    run_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    digest = input_hash(inputs)

    if request.save_experiment:
        repo.add(
            ExperimentRecord(
                run_id=run_id,
                model_id=projectile.MODEL_INFO.id,
                model_version=projectile.MODEL_INFO.version,
                created_at=created_at,
                input_hash=digest,
                inputs=inputs,
                summary={
                    "analytical": result.analytical.model_dump(exclude={"method_note"}),
                    "numerical": result.numerical.model_dump(),
                    "comparison": result.comparison.model_dump(),
                },
                environment=env,
            )
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
        metadata=RunMetadata(
            run_id=run_id,
            created_at=created_at,
            input_hash=digest,
            elapsed_ms=result.elapsed_ms,
            experiment_saved=request.save_experiment,
            **env,
        ),
    )
