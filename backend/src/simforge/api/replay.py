"""Replay a stored run and say whether the same answer came back.

Two hashes, two questions. The input hash says the same *question* is being asked (the
rebuilt request must hash to the stored one). The output digest says the same *answer*
came back: equal digests mean every output value is bit-identical. When digests are not
available (v1 records) or differ, the stored summary is compared field by field against
tolerances each model declares in advance, with a reason for each.
"""

from __future__ import annotations

import base64
import binascii
import fnmatch
import hashlib
import math
from dataclasses import dataclass
from typing import Any, Literal, TypeGuard

from fastapi import HTTPException, status
from pydantic import Field, ValidationError

from simforge.api.registry import get_entry
from simforge.api.runs import Tolerance, execute_run
from simforge.core.reproducibility import environment_info
from simforge.core.schemas import ModelInfo, RunMetadata, StrictModel
from simforge.persistence.experiments import ExperimentRecord, ExperimentRepository

Verdict = Literal["identical", "within_tolerance", "differs"]


class DatasetSupply(StrictModel):
    content_base64: str = Field(
        description="The same file the run profiled, base64-encoded. Checked by SHA-256 and "
        "size before it is read; it is used for this replay only and never stored."
    )


class ReplayRequest(StrictModel):
    dataset: DatasetSupply | None = Field(
        default=None, description="Only for a dataset profile of an uploaded file."
    )
    save_experiment: bool = Field(
        default=False,
        description="Store the replay as a new record linked to the original (replay_of). "
        "The original record is never changed.",
    )


class FieldComparison(StrictModel):
    field: str = Field(description="Summary field, nested names joined by dots.")
    original: float | int | str | bool | None
    replay: float | int | str | bool | None
    absolute_difference: float | None = Field(description="None when not both numbers.")
    tolerance: Tolerance
    within_tolerance: bool


class EnvironmentDifference(StrictModel):
    key: str
    original: str | None = Field(description="None if the original run did not record it.")
    replay: str | None


class ReplayResponse(StrictModel):
    original_run_id: str
    model: ModelInfo
    verdict: Verdict
    basis: Literal["output_digest", "summary", "summary_only"] = Field(
        description="output_digest: the digests were compared (every output value). summary: "
        "the digests differ, so the stored summary was compared with tolerances; outputs not "
        "in the summary (such as time series) are not compared. summary_only: a v1 record "
        "with no digest, so only its summary could be compared."
    )
    explanation: str
    original_output_digest: str | None
    replay_output_digest: str
    environment_matches: bool
    environment_differences: list[EnvironmentDifference]
    fields: list[FieldComparison] = Field(description="Every summary field, compared.")
    largest_difference: FieldComparison | None = Field(
        description="The field furthest from agreement, relative to its tolerance; None if "
        "every field is exactly equal."
    )
    metadata: RunMetadata = Field(description="The replay's own run metadata.")


# --- comparison ---------------------------------------------------------------------------


def flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in d.items():
        if isinstance(value, dict):
            out |= flatten(value, f"{prefix}{key}.")
        else:
            out[f"{prefix}{key}"] = value
    return out


def _is_number(x: object) -> TypeGuard[int | float]:
    return isinstance(x, int | float) and not isinstance(x, bool)


def _rule_for(field: str, rules: dict[str, Tolerance]) -> Tolerance:
    matching = [pattern for pattern in rules if fnmatch.fnmatchcase(field, pattern)]
    if len(matching) != 1:
        raise RuntimeError(f"field {field!r} matches {len(matching)} tolerance rules")
    return rules[matching[0]]


def compare_field(field: str, a: Any, b: Any, tolerance: Tolerance) -> FieldComparison:
    if _is_number(a) and _is_number(b):
        diff = abs(float(a) - float(b))
        allowed = tolerance.absolute + tolerance.relative * max(abs(float(a)), abs(float(b)))
        within = diff <= allowed and math.isfinite(diff)
    else:
        diff, within = None, a == b and type(a) is type(b)
    return FieldComparison(
        field=field,
        original=a,
        replay=b,
        absolute_difference=diff,
        tolerance=tolerance,
        within_tolerance=within,
    )


def _distance(c: FieldComparison) -> float:
    """How far a field is from agreement, in units of its tolerance (inf if it fails exactly)."""
    if c.absolute_difference is None:
        return 0.0 if c.within_tolerance else math.inf
    if c.absolute_difference == 0:
        return 0.0
    numbers = [abs(float(v)) for v in (c.original, c.replay) if _is_number(v)]
    allowed = c.tolerance.absolute + c.tolerance.relative * max(numbers)
    return c.absolute_difference / allowed if allowed > 0 else math.inf


@dataclass(frozen=True, slots=True)
class SummaryComparison:
    fields: list[FieldComparison]
    missing: list[str]  # fields in only one of the two summaries
    largest: FieldComparison | None

    @property
    def exactly_equal(self) -> bool:
        return not self.missing and all(
            c.absolute_difference in (None, 0.0) and c.within_tolerance for c in self.fields
        )

    @property
    def within_tolerance(self) -> bool:
        return not self.missing and all(c.within_tolerance for c in self.fields)


def compare_summaries(
    original: dict[str, Any], replay: dict[str, Any], rules: dict[str, Tolerance]
) -> SummaryComparison:
    a, b = flatten(original), flatten(replay)
    shared = [f for f in a if f in b]
    fields = [compare_field(f, a[f], b[f], _rule_for(f, rules)) for f in shared]
    missing = sorted(set(a) ^ set(b))
    differing = [c for c in fields if _distance(c) > 0]
    largest = max(differing, key=_distance) if differing else None
    return SummaryComparison(fields, missing, largest)


def environment_differences(
    original: dict[str, str], current: dict[str, str]
) -> list[EnvironmentDifference]:
    return [
        EnvironmentDifference(key=key, original=original.get(key), replay=current.get(key))
        for key in sorted(set(original) | set(current))
        if original.get(key) != current.get(key)
    ]


# --- replay -------------------------------------------------------------------------------


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _supplied_dataset(record: ExperimentRecord, supply: DatasetSupply | None) -> bytes | None:
    """The re-supplied file, checked against the stored identity *before* it is read."""
    stored = record.inputs.get("dataset")
    if supply is None:
        return None
    if not isinstance(stored, dict):
        raise _unprocessable(f"{record.model_id} takes no dataset; send no file to replay it.")
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


async def replay_run(
    record: ExperimentRecord, body: ReplayRequest, repo: ExperimentRepository
) -> ReplayResponse:
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
    dataset = _supplied_dataset(record, body.dataset)
    try:
        request = entry.rebuild(record.inputs, dataset)
    except ValidationError as exc:
        raise _unprocessable(
            "The stored inputs are no longer valid for the current model: "
            + "; ".join(str(e["msg"]) for e in exc.errors(include_input=False))
        ) from exc
    except LookupError as exc:
        raise _unprocessable(f"To replay {record.model_id}, {exc}.") from exc

    outcome = await execute_run(
        entry,
        request,
        repo,
        save=body.save_experiment,
        replay_of=record.run_id,
        expected_input_hash=record.input_hash,
    )

    metadata = outcome.response.metadata
    rules = entry.tolerances(record.inputs, record.summary)
    comparison = compare_summaries(record.summary, outcome.summary, rules)
    verdict: Verdict
    if record.output_digest is not None and record.output_digest == metadata.output_digest:
        verdict, basis = "identical", "output_digest"
        explanation = "Every output value is bit-identical (the output digests match)."
    else:
        basis = "summary_only" if record.output_digest is None else "summary"
        if comparison.missing:
            verdict = "differs"
            explanation = (
                "The stored summary and the replay's summary have different fields: "
                + ", ".join(comparison.missing)
                + "."
            )
        elif comparison.exactly_equal and basis == "summary_only":
            verdict = "identical"
            explanation = (
                "Every stored summary value is identical. This v1 record has no output digest, "
                "so outputs outside the summary could not be compared."
            )
        elif comparison.within_tolerance:
            verdict = "within_tolerance"
            explanation = (
                "Every summary value agrees within its declared tolerance"
                + ("" if basis == "summary_only" else ", but the outputs are not bit-identical")
                + ". Outputs outside the summary are not compared."
            )
        else:
            largest = comparison.largest
            verdict = "differs"
            explanation = (
                f"{largest.field if largest else 'A field'} is outside its declared tolerance."
            )
    env = environment_differences(record.environment, environment_info())
    return ReplayResponse(
        original_run_id=record.run_id,
        model=entry.info,
        verdict=verdict,
        basis=basis,
        explanation=explanation,
        original_output_digest=record.output_digest,
        replay_output_digest=metadata.output_digest,
        environment_matches=not env,
        environment_differences=env,
        fields=comparison.fields,
        largest_difference=comparison.largest,
        metadata=metadata,
    )
