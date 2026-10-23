from __future__ import annotations

import base64
import hashlib
from typing import Any

from fastapi import APIRouter

from simforge.api.dependencies import Repository
from simforge.api.runs import ModelEntry, Tolerance, execute
from simforge.core.schemas import RunMetadata
from simforge.quant.profiling import model as profiling
from simforge.quant.profiling.schemas import (
    ProfileRequest,
    ProfileResponse,
    SampleId,
    SampleInfo,
)

router = APIRouter(prefix="/quant", tags=["quant"])


def _profile_inputs(_: ProfileRequest, result: profiling.ProfileComputation) -> dict[str, Any]:
    # Identity of the computation: the file's bytes (by hash and size) and every option.
    # No rows, file name or column names: overrides use positions; markers are typed settings.
    return {
        "dataset": {"sha256": result.dataset.sha256, "byte_size": result.dataset.byte_size},
        "options": result.options.model_dump(mode="json"),
    }


def _profile_summary(result: profiling.ProfileComputation) -> dict[str, Any]:
    return {
        "source": result.dataset.source,
        "sample_id": result.dataset.sample_id,
        "rows": len(result.table.rows),
        "columns": len(result.table.header),
        "missing_cells": result.missing_cells,
        "duplicate_rows": result.duplicates.duplicate_rows,
        "mixed_columns": sum(1 for c in result.columns if profiling.is_mixed(c)),
    }


def _profile_response(
    request: ProfileRequest, result: profiling.ProfileComputation, metadata: RunMetadata
) -> ProfileResponse:
    return ProfileResponse(
        model=profiling.MODEL_INFO,
        dataset=result.dataset,
        options=result.options,
        n_rows=len(result.table.rows),
        n_columns=len(result.table.header),
        blank_lines_skipped=result.table.blank_lines_skipped,
        missing_cells=result.missing_cells,
        duplicates=result.duplicates,
        columns=result.columns,
        preview=result.preview,
        assumptions=profiling.ASSUMPTIONS,
        checks=result.checks,
        method_note=profiling.METHOD_NOTE,
        metadata=metadata,
    )


def sample_with_hash(sha256: str) -> SampleId | None:
    """The bundled sample whose bytes have this SHA-256, if any."""
    for sample_id in profiling.SAMPLES:
        if hashlib.sha256(profiling.sample_bytes(sample_id)).hexdigest() == sha256:
            return sample_id
    return None


def _profile_rebuild(inputs: dict[str, Any], dataset: bytes | None) -> ProfileRequest:
    """A profile request from stored inputs. A bundled sample is found by its hash; an
    uploaded file was never stored, so its bytes must be supplied again."""
    if dataset is not None:
        source: dict[str, Any] = {
            "kind": "upload",
            "content_base64": base64.b64encode(dataset).decode("ascii"),
        }
    else:
        sample_id = sample_with_hash(inputs["dataset"]["sha256"])
        if sample_id is None:
            raise LookupError("this run profiled an uploaded file; supply the same file again")
        source = {"kind": "sample", "sample_id": sample_id}
    return ProfileRequest.model_validate(
        {"source": source, "options": inputs["options"], "save_experiment": False}
    )


DATASET_PROFILE = ModelEntry(
    info=profiling.MODEL_INFO,
    request_type=ProfileRequest,
    compute=profiling.run,
    inputs=_profile_inputs,
    summary=_profile_summary,
    respond=_profile_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=_profile_rebuild,
    # Every stored value is a count or a label: a profile involves no floating-point result
    # in its summary, so any change is a real change.
    tolerances=lambda inputs, summary: {
        "*": Tolerance.exact("Counts and labels: exact, by definition of a profile.")
    },
)


@router.get("/datasets/samples")
def list_samples() -> list[SampleInfo]:
    return [info for _, info in profiling.SAMPLES.values()]


@router.post("/datasets/profile")
async def profile_dataset(request: ProfileRequest, repo: Repository) -> ProfileResponse:
    return await execute(DATASET_PROFILE, request, repo, save=request.save_experiment)
