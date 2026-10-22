"""One code path for running any model: compute, record, respond.

Each model describes itself once as a :class:`ModelEntry`. The live endpoints and replay
both go through the same entry, so a replay asks exactly the question the original run
asked, computed by exactly the same code.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool

from simforge.api.recording import record_run
from simforge.core.errors import ModelDomainError, SolverError
from simforge.core.schemas import ModelInfo, RunMetadata, StrictModel
from simforge.persistence.experiments import ExperimentRepository
from simforge.quant.profiling.parsing import DatasetError


@dataclass(frozen=True, slots=True)
class ModelEntry[Req: StrictModel, Res: StrictModel, Result]:
    """Everything the API needs to know about one model."""

    info: ModelInfo
    request_type: type[Req]
    #: Runs the model. May raise ModelDomainError, DatasetError (422) or SolverError (500).
    compute: Callable[[Req], Result]
    #: The inputs that determine the numbers: what is hashed and stored.
    inputs: Callable[[Req, Result], dict[str, Any]]
    #: Headline numbers stored in the experiment log.
    summary: Callable[[Result], dict[str, Any]]
    #: The full API response for this run.
    respond: Callable[[Req, Result, RunMetadata], Res]
    elapsed_ms: Callable[[Result], float]
    #: Rebuilds a request from stored inputs (and, for an uploaded dataset, its bytes).
    #: The rebuilt request never saves to the log by itself.
    rebuild: Callable[[dict[str, Any], bytes | None], Req]


def compute_or_explain[Req: StrictModel, Res: StrictModel, Result](
    entry: ModelEntry[Req, Res, Result], request: Req
) -> Result:
    """Run the model, turning its domain errors into HTTP errors with their explanation."""
    try:
        return entry.compute(request)
    except (ModelDomainError, DatasetError) as exc:
        # The message describes the problem; it never quotes an uploaded file.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except SolverError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc


async def execute[Req: StrictModel, Res: StrictModel, Result](
    entry: ModelEntry[Req, Res, Result],
    request: Req,
    repo: ExperimentRepository,
    *,
    save: bool,
) -> Res:
    """What every model endpoint does. CPU work and SQLite I/O run in worker threads, so
    the event loop stays responsive."""
    result = await run_in_threadpool(compute_or_explain, entry, request)
    metadata = await run_in_threadpool(
        record_run,
        repo,
        entry.info,
        entry.inputs(request, result),
        entry.summary(result),
        save=save,
        elapsed_ms=entry.elapsed_ms(result),
    )
    return entry.respond(request, result, metadata)
