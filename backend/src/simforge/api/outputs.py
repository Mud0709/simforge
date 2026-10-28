"""Recompute a stored run's full outputs (roadmap 1.6, decisions D1 and D2).

The log stores inputs, not series (ARCHITECTURE decision 5), so a past run's curves exist
only after computing it again. This does exactly what replay does up to the comparison: the
same refusals (one shared helper), the same rebuilt request, the same code path. It never
saves anything. The stored output digest then says whether the recomputed answer is
bit-identical to the original one.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Discriminator, Field, Tag

from simforge.api.rerun import DatasetSupply, prepare_rerun
from simforge.api.routes.economy import SOLOW
from simforge.api.routes.physics import (
    ANGLE_SWEEP,
    INTEGRATOR_STUDY,
    PROJECTILE,
    QUADRATIC_DRAG,
)
from simforge.api.routes.quant import DATASET_PROFILE
from simforge.api.runs import execute_run
from simforge.core.schemas import StrictModel
from simforge.economy.solow.schemas import SolowResponse
from simforge.persistence.experiments import ExperimentRecord, ExperimentRepository
from simforge.physics.projectile.integrator_schemas import IntegratorStudyResponse
from simforge.physics.projectile.quadratic_schemas import QuadraticDragResponse
from simforge.physics.projectile.schemas import AngleSweepResponse, ProjectileResponse
from simforge.quant.profiling.schemas import ProfileResponse


def _model_id(value: Any) -> str | None:
    """Which model a response came from: its ``model.id`` (a dict when validating JSON, an
    object when validating a response built here)."""
    model = value.get("model") if isinstance(value, dict) else getattr(value, "model", None)
    model_id = model.get("id") if isinstance(model, dict) else getattr(model, "id", None)
    return model_id if isinstance(model_id, str) else None


# The responses share no literal field to discriminate on, and adding one would change every
# output digest, so the union is told apart by ``model.id`` (one schema checked, not six).
ModelResponse = Annotated[
    Annotated[ProjectileResponse, Tag(PROJECTILE.info.id)]
    | Annotated[IntegratorStudyResponse, Tag(INTEGRATOR_STUDY.info.id)]
    | Annotated[AngleSweepResponse, Tag(ANGLE_SWEEP.info.id)]
    | Annotated[SolowResponse, Tag(SOLOW.info.id)]
    | Annotated[ProfileResponse, Tag(DATASET_PROFILE.info.id)]
    | Annotated[QuadraticDragResponse, Tag(QUADRATIC_DRAG.info.id)],
    Discriminator(_model_id),
]


class RecomputeRequest(StrictModel):
    dataset: DatasetSupply | None = Field(
        default=None, description="Only for a dataset profile of an uploaded file."
    )


class RecomputedOutputs(StrictModel):
    original_run_id: str
    digest_match: bool | None = Field(
        description="True if every recomputed output value is bit-identical to the stored "
        "run's (the output digests are equal). False if both digests exist and differ "
        "(another CPU or library can round the last bits differently). Null if the stored "
        "record is v1 and has no output digest, so bit-identity cannot be checked."
    )
    response: ModelResponse = Field(
        description="The model's normal response, computed again from the stored inputs. Its "
        "metadata describes this recomputation (a new run id); it is never saved."
    )


async def recompute_outputs(
    record: ExperimentRecord, body: RecomputeRequest, repo: ExperimentRepository
) -> RecomputedOutputs:
    entry, request = prepare_rerun(record, body.dataset)
    outcome = await execute_run(
        entry, request, repo, save=False, expected_input_hash=record.input_hash
    )
    digest = outcome.response.metadata.output_digest
    return RecomputedOutputs(
        original_run_id=record.run_id,
        digest_match=None if record.output_digest is None else record.output_digest == digest,
        response=outcome.response,
    )
