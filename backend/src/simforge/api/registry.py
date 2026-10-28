"""The model registry: every model the API serves, looked up by its stable id.

A plain tuple and a lookup function; the entries themselves live next to their routes.
"""

from __future__ import annotations

from typing import Any

from simforge.api.routes.economy import SOLOW
from simforge.api.routes.physics import (
    ANGLE_SWEEP,
    INTEGRATOR_STUDY,
    PROJECTILE,
    QUADRATIC_DRAG,
)
from simforge.api.routes.quant import DATASET_PROFILE
from simforge.api.runs import ModelEntry

ENTRIES: tuple[ModelEntry[Any, Any, Any], ...] = (
    PROJECTILE,
    INTEGRATOR_STUDY,
    ANGLE_SWEEP,
    SOLOW,
    DATASET_PROFILE,
    QUADRATIC_DRAG,
)

_BY_ID = {entry.info.id: entry for entry in ENTRIES}
if len(_BY_ID) != len(ENTRIES):  # pragma: no cover - a programming error caught at import
    raise RuntimeError("two registry entries share a model id")


def get_entry(model_id: str) -> ModelEntry[Any, Any, Any] | None:
    return _BY_ID.get(model_id)
