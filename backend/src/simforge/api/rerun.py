"""Rebuilding a stored run so it can be computed again: one set of refusals for every route.

Replay (is the answer the same?) and recomputed outputs (give me the answer again) both
rerun a stored record. Both must refuse the same cases, so the checks live here once: the
model must still exist, at the same version, and an uploaded file must be supplied again
and match the stored SHA-256 and size before it is read.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Any

from fastapi import HTTPException, status
from pydantic import Field, ValidationError

from simforge.api.registry import get_entry
from simforge.api.runs import ModelEntry
from simforge.core.schemas import StrictModel
from simforge.persistence.experiments import ExperimentRecord


class DatasetSupply(StrictModel):
    content_base64: str = Field(
        description="The same file the run profiled, base64-encoded. Checked by SHA-256 and "
        "size before it is read; it is used for this rerun only and never stored."
    )


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _supplied_dataset(record: ExperimentRecord, supply: DatasetSupply | None) -> bytes | None:
    """The re-supplied file, checked against the stored identity *before* it is read."""
    stored = record.inputs.get("dataset")
    if supply is None:
        return None
    if not isinstance(stored, dict):
        raise _unprocessable(f"{record.model_id} takes no dataset; send no file to rerun it.")
    try:
        data = base64.b64decode(supply.content_base64, validate=True)
    except binascii.Error as exc:
        raise _unprocessable("The supplied file is not valid base64.") from exc
    digest = hashlib.sha256(data).hexdigest()
    if digest != stored.get("sha256") or len(data) != stored.get("byte_size"):
        raise _unprocessable(
            "The supplied file is not the one this run profiled: its SHA-256 or size differs "
            f"(supplied {len(data)} bytes, SHA-256 {digest[:12]}…; the run used "
            f"{stored.get('byte_size')} bytes, SHA-256 {str(stored.get('sha256'))[:12]}…). "
            "It was not read."
        )
    return data


def prepare_rerun(
    record: ExperimentRecord, supply: DatasetSupply | None
) -> tuple[ModelEntry[Any, Any, Any], StrictModel]:
    """The registry entry and the rebuilt request for ``record``, or the HTTP refusal: 422 for
    an unknown model, inputs that no longer validate or a missing or different file; 409 for
    a changed model version. (A body that is too large was already refused with 413.)"""
    entry = get_entry(record.model_id)
    if entry is None:
        raise _unprocessable(f"SimForge has no model {record.model_id!r} any more.")
    if record.model_version != entry.info.version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This run used {record.model_id} v{record.model_version}; the current version is "
            f"v{entry.info.version}. A rerun would use different code, so it would not be a "
            "reproduction. Run the model again instead.",
        )
    dataset = _supplied_dataset(record, supply)
    try:
        request = entry.rebuild(record.inputs, dataset)
    except ValidationError as exc:
        raise _unprocessable(
            "The stored inputs are no longer valid for the current model: "
            + "; ".join(str(e["msg"]) for e in exc.errors(include_input=False))
        ) from exc
    except LookupError as exc:
        raise _unprocessable(f"To rerun {record.model_id}, {exc}.") from exc
    return entry, request
