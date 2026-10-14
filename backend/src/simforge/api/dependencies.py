from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from simforge.persistence.experiments import ExperimentRepository


def get_repository(request: Request) -> ExperimentRepository:
    repo: ExperimentRepository = request.app.state.experiments
    return repo


Repository = Annotated[ExperimentRepository, Depends(get_repository)]
