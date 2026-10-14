from __future__ import annotations

from fastapi import APIRouter

from simforge.core.reproducibility import environment_info
from simforge.core.schemas import StrictModel

router = APIRouter(tags=["meta"])


class Health(StrictModel):
    status: str
    environment: dict[str, str]


@router.get("/health")
def health() -> Health:
    return Health(status="ok", environment=environment_info())
