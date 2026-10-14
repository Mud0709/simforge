from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from simforge.api.dependencies import Repository
from simforge.persistence.experiments import ExperimentRecord

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("")
def list_experiments(
    repo: Repository,
    model_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[ExperimentRecord]:
    return repo.list(model_id=model_id, limit=limit)


@router.get("/{run_id}")
def get_experiment(run_id: str, repo: Repository) -> ExperimentRecord:
    record = repo.get(run_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No experiment with run_id {run_id!r}")
    return record
