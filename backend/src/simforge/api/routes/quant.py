from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from simforge.api.dependencies import Repository
from simforge.api.recording import record_run
from simforge.quant.profiling import model as profiling
from simforge.quant.profiling.parsing import DatasetError
from simforge.quant.profiling.schemas import ProfileRequest, ProfileResponse, SampleInfo

router = APIRouter(prefix="/quant", tags=["quant"])


@router.get("/datasets/samples")
def list_samples() -> list[SampleInfo]:
    return [info for _, info in profiling.SAMPLES.values()]


@router.post("/datasets/profile")
async def profile_dataset(request: ProfileRequest, repo: Repository) -> ProfileResponse:
    try:
        result = await run_in_threadpool(profiling.run, request)
    except DatasetError as exc:
        # The message describes the problem (row numbers, counts); it never quotes the file
        # beyond a short example the user already has.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    # Identity of the computation: the file's bytes (by hash and size) and every option.
    # No rows, file name or column names: overrides use positions; markers are typed settings.
    inputs = {
        "dataset": {"sha256": result.dataset.sha256, "byte_size": result.dataset.byte_size},
        "options": result.options.model_dump(mode="json"),
    }
    # SQLite I/O runs in a worker thread so it never blocks the event loop.
    metadata = await run_in_threadpool(
        record_run,
        repo,
        profiling.MODEL_INFO,
        inputs,
        {
            "source": result.dataset.source,
            "sample_id": result.dataset.sample_id,
            "rows": len(result.table.rows),
            "columns": len(result.table.header),
            "missing_cells": result.missing_cells,
            "duplicate_rows": result.duplicates.duplicate_rows,
            "mixed_columns": sum(1 for c in result.columns if profiling.is_mixed(c)),
        },
        save=request.save_experiment,
        elapsed_ms=result.elapsed_ms,
    )
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
