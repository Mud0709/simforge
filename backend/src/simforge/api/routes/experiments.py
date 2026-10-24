from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import Field

from simforge.api.dependencies import Repository
from simforge.api.registry import get_entry
from simforge.api.replay import ReplayRequest, ReplayResponse, replay_run
from simforge.core.schemas import StrictModel
from simforge.persistence.experiments import ExperimentRecord

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


@router.post("/{run_id}/replay")
async def replay_experiment(run_id: str, body: ReplayRequest, repo: Repository) -> ReplayResponse:
    """Rerun a stored run with the same inputs and the same model version, and say whether
    the same answer came back: identical, within tolerance, or differs."""
    record = await run_in_threadpool(repo.get, run_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No experiment with run_id {run_id!r}")
    return await replay_run(record, body, repo)
