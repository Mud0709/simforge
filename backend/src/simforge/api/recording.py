"""Shared run bookkeeping for every model endpoint: run metadata and the experiment log."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from simforge.core.reproducibility import environment_info, input_hash
from simforge.core.schemas import ModelInfo, RunMetadata
from simforge.persistence.experiments import (
    RECORD_VERSION,
    ExperimentRecord,
    ExperimentRepository,
)


def record_run(
    repo: ExperimentRepository,
    model_info: ModelInfo,
    inputs: dict[str, Any],
    summary: dict[str, Any],
    *,
    output_digest: str,
    save: bool,
    elapsed_ms: float,
    replay_of: str | None = None,
) -> RunMetadata:
    """Build run metadata and, if requested, store the run in the experiment log.

    ``inputs`` must contain exactly the fields that affect the numbers, so that identical
    computations share an input hash.
    """
    env = environment_info()
    run_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    digest = input_hash(inputs)
    if save:
        repo.add(
            ExperimentRecord(
                run_id=run_id,
                model_id=model_info.id,
                model_version=model_info.version,
                created_at=created_at,
                input_hash=digest,
                inputs=inputs,
                summary=summary,
                environment=env,
                record_version=RECORD_VERSION,
                output_digest=output_digest,
                replay_of=replay_of,
            )
        )
    return RunMetadata(
        run_id=run_id,
        created_at=created_at,
        input_hash=digest,
        output_digest=output_digest,
        elapsed_ms=elapsed_ms,
        experiment_saved=save,
        **env,
    )
