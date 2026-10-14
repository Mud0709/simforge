"""Experiment log: a record of *what was run*, not a cache of results.

Only validated inputs, solver settings, environment versions and summary metrics are
stored. Full time series are deliberately not stored: every model is deterministic, so
a run can be reproduced from its inputs. Keeping the database small and the source of
truth in the inputs is the reproducibility contract.

Uses the standard-library ``sqlite3`` module directly: one table, no ORM needed yet.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import Field

from simforge.core.reproducibility import canonical_json
from simforge.core.schemas import StrictModel

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS experiments (
    run_id        TEXT PRIMARY KEY,
    model_id      TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    input_hash    TEXT NOT NULL,
    inputs        TEXT NOT NULL,  -- canonical JSON
    summary       TEXT NOT NULL,  -- canonical JSON
    environment   TEXT NOT NULL   -- canonical JSON
);
CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_experiments_hash ON experiments (input_hash);
"""


class ExperimentRecord(StrictModel):
    run_id: str
    model_id: str
    model_version: str
    created_at: str
    input_hash: str
    inputs: dict[str, Any] = Field(description="Validated inputs exactly as used by the run.")
    summary: dict[str, Any] = Field(description="Headline metrics; series are not stored.")
    environment: dict[str, str]


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(_SCHEMA)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        elif row[0] != SCHEMA_VERSION:
            raise RuntimeError(
                f"Database {path} has schema v{row[0]}, expected v{SCHEMA_VERSION}. "
                "Delete it or add a migration."
            )


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:  # commits on success, rolls back on exception
            yield conn
    finally:
        conn.close()


class ExperimentRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def add(self, record: ExperimentRecord) -> None:
        with _connect(self._path) as conn:
            conn.execute(
                "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.run_id,
                    record.model_id,
                    record.model_version,
                    record.created_at,
                    record.input_hash,
                    canonical_json(record.inputs),
                    canonical_json(record.summary),
                    canonical_json(record.environment),
                ),
            )

    def get(self, run_id: str) -> ExperimentRecord | None:
        with _connect(self._path) as conn:
            row = conn.execute("SELECT * FROM experiments WHERE run_id = ?", (run_id,)).fetchone()
        return _to_record(row) if row else None

    def list(self, *, model_id: str | None = None, limit: int = 50) -> list[ExperimentRecord]:
        query = "SELECT * FROM experiments"
        params: tuple[Any, ...] = ()
        if model_id is not None:
            query += " WHERE model_id = ?"
            params = (model_id,)
        query += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        with _connect(self._path) as conn:
            rows = conn.execute(query, (*params, limit)).fetchall()
        return [_to_record(r) for r in rows]


def _to_record(row: sqlite3.Row) -> ExperimentRecord:
    return ExperimentRecord(
        run_id=row["run_id"],
        model_id=row["model_id"],
        model_version=row["model_version"],
        created_at=row["created_at"],
        input_hash=row["input_hash"],
        inputs=json.loads(row["inputs"]),
        summary=json.loads(row["summary"]),
        environment=json.loads(row["environment"]),
    )
