"""Experiment log: a record of *what was run*, not a cache of results.

Only validated inputs, solver settings, environment versions, summary metrics and (since
record v2) a SHA-256 fingerprint of the outputs are stored. Full time series are
deliberately not stored: every model is deterministic, so a run can be reproduced from its
inputs. Keeping the database small and the source of truth in the inputs is the
reproducibility contract.

Uses the standard-library ``sqlite3`` module directly: one table, no ORM needed yet.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import Field

from simforge.core.reproducibility import canonical_json
from simforge.core.schemas import StrictModel

SCHEMA_VERSION = 2
#: Version of the record written by this code. v1 records (before roadmap 1.4) have no output
#: digest; they are kept as they were and read as record_version 1.
RECORD_VERSION = 2

_SCHEMA = """
CREATE TABLE schema_version (version INTEGER NOT NULL);
CREATE TABLE experiments (
    run_id         TEXT PRIMARY KEY,
    model_id       TEXT NOT NULL,
    model_version  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    input_hash     TEXT NOT NULL,
    inputs         TEXT NOT NULL,  -- canonical JSON
    summary        TEXT NOT NULL,  -- canonical JSON
    environment    TEXT NOT NULL,  -- canonical JSON
    record_version INTEGER NOT NULL DEFAULT 1,
    output_digest  TEXT,           -- NULL for v1 records
    replay_of      TEXT            -- run_id of the run this one replayed, if any
);
CREATE INDEX idx_experiments_created ON experiments (created_at DESC);
CREATE INDEX idx_experiments_hash ON experiments (input_hash);
"""

# v1 -> v2: three added columns. Existing rows are never rewritten; the defaults make them
# read as v1 records with no output digest that replayed nothing.
_MIGRATE_V1_TO_V2 = (
    "ALTER TABLE experiments ADD COLUMN record_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE experiments ADD COLUMN output_digest TEXT",
    "ALTER TABLE experiments ADD COLUMN replay_of TEXT",
    "UPDATE schema_version SET version = 2",
)


class ExperimentRecord(StrictModel):
    run_id: str
    model_id: str
    model_version: str
    created_at: str
    input_hash: str
    inputs: dict[str, Any] = Field(description="Validated inputs exactly as used by the run.")
    summary: dict[str, Any] = Field(description="Headline metrics; series are not stored.")
    environment: dict[str, str]
    record_version: int = Field(
        default=1, description="1: before roadmap 1.4 (no output digest); 2: current."
    )
    output_digest: str | None = Field(
        default=None,
        description="SHA-256 of the canonical JSON of the full response without its run "
        "metadata. Equal digests mean every output value is bit-identical. None for v1.",
    )
    replay_of: str | None = Field(
        default=None, description="run_id of the run this record replayed, if it is a replay."
    )


def init_db(path: Path) -> None:
    """Create the experiment log, or bring an existing one up to the current schema.

    A v1 log is copied to ``<name>.v1.bak`` first, then migrated in one transaction: either
    every step applies or none does. A log newer than this code is refused untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    version = _schema_version(path)
    if version is None:
        with _transaction(path) as conn:
            for statement in _SCHEMA.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    elif version == 1:
        backup = path.with_name(path.name + ".v1.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        with _transaction(path) as conn:
            for statement in _MIGRATE_V1_TO_V2:
                conn.execute(statement)
    elif version != SCHEMA_VERSION:
        raise RuntimeError(
            f"Database {path} has schema v{version}, but this SimForge reads up to "
            f"v{SCHEMA_VERSION}. Update SimForge, or move the file aside."
        )


def _schema_version(path: Path) -> int | None:
    """The log's schema version, or None if there is no log yet."""
    conn = sqlite3.connect(path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "schema_version" not in tables:
            return None
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return None if row is None else int(row[0])
    finally:
        conn.close()


@contextmanager
def _transaction(path: Path) -> Iterator[sqlite3.Connection]:
    """A real transaction for schema changes too. (In its default mode, Python's sqlite3
    commits before an ALTER TABLE, so a failed migration could be left half done.)"""
    conn = sqlite3.connect(path, autocommit=False)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


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
                "INSERT INTO experiments (run_id, model_id, model_version, created_at, "
                "input_hash, inputs, summary, environment, record_version, output_digest, "
                "replay_of) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.run_id,
                    record.model_id,
                    record.model_version,
                    record.created_at,
                    record.input_hash,
                    canonical_json(record.inputs),
                    canonical_json(record.summary),
                    canonical_json(record.environment),
                    record.record_version,
                    record.output_digest,
                    record.replay_of,
                ),
            )

    def get(self, run_id: str) -> ExperimentRecord | None:
        with _connect(self._path) as conn:
            row = conn.execute("SELECT * FROM experiments WHERE run_id = ?", (run_id,)).fetchone()
        return _to_record(row) if row else None

    def list(
        self,
        *,
        model_id: str | None = None,
        lab: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExperimentRecord]:
        """Newest first. ``lab`` keeps models whose id starts with ``<lab>.``."""
        query = "SELECT * FROM experiments"
        clauses: list[str] = []
        params: list[Any] = []
        if model_id is not None:
            clauses.append("model_id = ?")
            params.append(model_id)
        if lab is not None:
            clauses.append("substr(model_id, 1, ?) = ?")
            params += [len(lab) + 1, f"{lab}."]
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?"
        with _connect(self._path) as conn:
            rows = conn.execute(query, (*params, limit, offset)).fetchall()
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
        record_version=row["record_version"],
        output_digest=row["output_digest"],
        replay_of=row["replay_of"],
    )
