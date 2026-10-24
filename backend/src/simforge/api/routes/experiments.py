from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import AwareDatetime, Field

from simforge.api.dependencies import Repository
from simforge.api.outputs import RecomputedOutputs, RecomputeRequest, recompute_outputs
from simforge.api.registry import get_entry
from simforge.api.replay import ReplayRequest, ReplayResponse, replay_run
from simforge.core.schemas import StrictModel
from simforge.persistence.experiments import ExperimentRecord, ExperimentRepository

router = APIRouter(prefix="/experiments", tags=["experiments"])

Lab = Literal["physics", "economy", "quant"]


class LoggedRun(ExperimentRecord):
    """A stored run as the log shows it: the record plus its lab and a one-line headline."""

    lab: str = Field(description="The lab, from the model id: physics, economy or quant.")
    headline: str = Field(description="One line written by the model; '—' if unavailable.")
    replay_needs_file: bool = Field(
        description="True if replaying needs the user to supply a file again (an upload)."
    )


def _headline(record: ExperimentRecord) -> str:
    entry = get_entry(record.model_id)
    if entry is None:
        return "—"
    try:
        return entry.headline(record.summary)
    except (KeyError, TypeError, ValueError):  # an older summary shape
        return "—"


def _needs_file(record: ExperimentRecord) -> bool:
    entry = get_entry(record.model_id)
    try:
        return entry is not None and entry.replay_needs_file(record.inputs)
    except (KeyError, TypeError):  # an older inputs shape
        return False


def _logged(record: ExperimentRecord) -> LoggedRun:
    return LoggedRun(
        **record.model_dump(),
        lab=record.model_id.split(".", 1)[0],
        headline=_headline(record),
        replay_needs_file=_needs_file(record),
    )


@router.get("")
def list_experiments(
    repo: Repository,
    model_id: str | None = None,
    lab: Lab | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[LoggedRun]:
    records = repo.list(model_id=model_id, lab=lab, limit=limit, offset=offset)
    return [_logged(r) for r in records]


@router.get("/{run_id}")
def get_experiment(run_id: str, repo: Repository) -> LoggedRun:
    record = repo.get(run_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No experiment with run_id {run_id!r}")
    return _logged(record)


class RunExport(StrictModel):
    """A stored run as a versioned, downloadable JSON file (roadmap 1.6, decision D5). The
    version lets a future import or report check what it reads. No series: the log stores
    inputs, not curves (ARCHITECTURE decision 5)."""

    export_version: Literal[1] = Field(description="The export format version.")
    exported_at: AwareDatetime = Field(description="When this export was made (UTC).")
    record: LoggedRun = Field(description="The run exactly as GET /experiments/{run_id} shows it.")


@router.get("/{run_id}/export")
def export_experiment(run_id: str, repo: Repository, response: Response) -> RunExport:
    record = repo.get(run_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No experiment with run_id {run_id!r}")
    # Model id and run id only: user labels never go in a filename (safety rule, 1.6 plan).
    filename = f"{record.model_id}_{record.run_id[:8]}.json"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return RunExport(export_version=1, exported_at=datetime.now(UTC), record=_logged(record))


class RunLabels(StrictModel):
    """A run's name and note. Omitted fields are kept; null or "" clears. Nothing else about
    a run can be changed: its inputs, results and fingerprints are the scientific record."""

    name: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=2000)


@router.patch("/{run_id}")
def label_experiment(run_id: str, labels: RunLabels, repo: Repository) -> LoggedRun:
    record = repo.get(run_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No experiment with run_id {run_id!r}")
    sent = labels.model_fields_set

    def pick(field: str, current: str | None) -> str | None:
        if field not in sent:
            return current
        value: str | None = getattr(labels, field)
        return value or None

    updated = repo.set_labels(
        run_id, name=pick("name", record.name), note=pick("note", record.note)
    )
    if updated is None:  # removed meanwhile
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No experiment with run_id {run_id!r}")
    return _logged(updated)


async def _stored(run_id: str, repo: ExperimentRepository) -> ExperimentRecord:
    """The stored run a rerun starts from (replay or recomputed outputs), or 404."""
    record = await run_in_threadpool(repo.get, run_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No experiment with run_id {run_id!r}")
    return record


@router.post("/{run_id}/replay")
async def replay_experiment(run_id: str, body: ReplayRequest, repo: Repository) -> ReplayResponse:
    """Rerun a stored run with the same inputs and the same model version, and say whether
    the same answer came back: identical, within tolerance, or differs."""
    return await replay_run(await _stored(run_id, repo), body, repo)


@router.post("/{run_id}/outputs")
async def recompute_experiment_outputs(
    run_id: str, body: RecomputeRequest, repo: Repository
) -> RecomputedOutputs:
    """Compute a stored run again and return its full response (series included), with
    whether it is bit-identical to the original. Refuses exactly what replay refuses; never
    saves anything."""
    return await recompute_outputs(await _stored(run_id, repo), body, repo)
