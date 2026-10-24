"""Run record v2: migrating a real v1 experiment log.

The v1 schema below is copied from the released v1 code (it must never be edited), so the
test migrates the file layout users actually have, not whatever the current code creates.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from simforge.persistence.experiments import (
    SCHEMA_VERSION,
    ExperimentRecord,
    ExperimentRepository,
    init_db,
)

V1_SCHEMA = """
CREATE TABLE schema_version (version INTEGER NOT NULL);
CREATE TABLE experiments (
    run_id        TEXT PRIMARY KEY,
    model_id      TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    input_hash    TEXT NOT NULL,
    inputs        TEXT NOT NULL,
    summary       TEXT NOT NULL,
    environment   TEXT NOT NULL
);
CREATE INDEX idx_experiments_created ON experiments (created_at DESC);
CREATE INDEX idx_experiments_hash ON experiments (input_hash);
INSERT INTO schema_version (version) VALUES (1);
"""
V1_ROW = (
    "run-1",
    "economy.solow",
    "1.0.0",
    "2026-10-15T12:00:00+00:00",
    "a" * 64,
    '{"horizon_years":100}',
    '{"final_capital":6.539483386104942}',
    '{"numpy_version":"2.3.0","simforge_version":"0.1.0"}',
)


def make_v1_db(path: Path, extra_sql: str = "") -> None:
    conn = sqlite3.connect(path)
    conn.executescript(V1_SCHEMA + extra_sql)
    conn.execute(
        "INSERT INTO experiments (run_id, model_id, model_version, created_at, input_hash, "
        "inputs, summary, environment) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        V1_ROW,
    )
    conn.commit()
    conn.close()


def version_of(path: Path) -> int:
    conn = sqlite3.connect(path)
    (v,) = conn.execute("SELECT version FROM schema_version").fetchone()
    conn.close()
    return int(v)


def test_v1_log_is_migrated_and_old_rows_are_kept_exactly(tmp_path: Path) -> None:
    db = tmp_path / "simforge.sqlite3"
    make_v1_db(db)
    original_bytes = db.read_bytes()

    init_db(db)

    assert version_of(db) == 3
    # A backup of the untouched v1 file is kept next to it.
    assert (tmp_path / "simforge.sqlite3.v1.bak").read_bytes() == original_bytes
    record = ExperimentRepository(db).get("run-1")
    assert record is not None
    assert (
        record.run_id,
        record.model_id,
        record.model_version,
        record.created_at,
        record.input_hash,
    ) == V1_ROW[:5]
    assert record.inputs == json.loads(V1_ROW[5])
    assert record.summary == json.loads(V1_ROW[6])
    assert record.environment == json.loads(V1_ROW[7])
    # Old rows are interpreted, never rewritten: v1, no output digest, not a replay.
    assert record.record_version == 1
    assert record.output_digest is None
    assert record.replay_of is None


def test_migrating_twice_changes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "simforge.sqlite3"
    make_v1_db(db)
    init_db(db)
    backup = (tmp_path / "simforge.sqlite3.v1.bak").read_bytes()
    init_db(db)
    assert version_of(db) == 3
    assert (tmp_path / "simforge.sqlite3.v1.bak").read_bytes() == backup
    assert len(ExperimentRepository(db).list()) == 1


def test_a_failed_migration_rolls_back_completely(tmp_path: Path) -> None:
    # A v1 file that already has a column the migration wants to add: the second ALTER
    # fails after the first succeeded. Nothing may be left half-migrated.
    db = tmp_path / "simforge.sqlite3"
    make_v1_db(db, "ALTER TABLE experiments ADD COLUMN replay_of TEXT;")
    with pytest.raises(sqlite3.OperationalError, match="duplicate column"):
        init_db(db)
    assert version_of(db) == 1
    conn = sqlite3.connect(db)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(experiments)")]
    conn.close()
    assert "record_version" not in columns
    assert "output_digest" not in columns


def test_a_newer_log_is_refused_untouched(tmp_path: Path) -> None:
    db = tmp_path / "simforge.sqlite3"
    make_v1_db(db)
    conn = sqlite3.connect(db)
    newer = SCHEMA_VERSION + 1
    conn.execute("UPDATE schema_version SET version = ?", (newer,))
    conn.commit()
    conn.close()
    before = db.read_bytes()
    with pytest.raises(RuntimeError, match=f"schema v{newer}"):
        init_db(db)
    assert db.read_bytes() == before
    assert not (tmp_path / "simforge.sqlite3.v1.bak").exists()


def test_a_new_log_starts_at_the_current_version_and_stores_the_new_fields(
    tmp_path: Path,
) -> None:
    db = tmp_path / "new.sqlite3"
    init_db(db)
    assert version_of(db) == 3
    assert not (tmp_path / "new.sqlite3.v1.bak").exists()
    repo = ExperimentRepository(db)
    record = ExperimentRecord(
        run_id="run-2",
        model_id="economy.solow",
        model_version="1.0.0",
        created_at="2026-10-22T00:00:00+00:00",
        input_hash="b" * 64,
        inputs={},
        summary={},
        environment={},
        record_version=2,
        output_digest="c" * 64,
        replay_of="run-1",
    )
    repo.add(record)
    assert repo.get("run-2") == record


# --- v2 -> v3: names and notes (roadmap 1.5) ----------------------------------------------


def make_v2_db(path: Path) -> None:
    """A v2 log as roadmap 1.4 wrote it (v1 layout plus three columns)."""
    make_v1_db(path)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        ALTER TABLE experiments ADD COLUMN record_version INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE experiments ADD COLUMN output_digest TEXT;
        ALTER TABLE experiments ADD COLUMN replay_of TEXT;
        UPDATE schema_version SET version = 2;
        """
    )
    conn.commit()
    conn.close()


def test_a_v2_log_gains_names_and_notes_and_keeps_everything_else(tmp_path: Path) -> None:
    db = tmp_path / "simforge.sqlite3"
    make_v2_db(db)
    original = db.read_bytes()
    init_db(db)
    assert version_of(db) == 3
    assert (tmp_path / "simforge.sqlite3.v2.bak").read_bytes() == original
    record = ExperimentRepository(db).get("run-1")
    assert record is not None
    assert record.summary == json.loads(V1_ROW[6])
    assert (record.name, record.note) == (None, None)


def test_a_v1_log_is_migrated_all_the_way(tmp_path: Path) -> None:
    db = tmp_path / "simforge.sqlite3"
    make_v1_db(db)
    init_db(db)
    assert version_of(db) == 3
    assert (tmp_path / "simforge.sqlite3.v1.bak").exists()
    record = ExperimentRepository(db).get("run-1")
    assert record is not None
    assert (record.record_version, record.name) == (1, None)


def test_labels_change_and_nothing_else_does(tmp_path: Path) -> None:
    db = tmp_path / "simforge.sqlite3"
    make_v1_db(db)
    init_db(db)
    repo = ExperimentRepository(db)
    before = repo.get("run-1")
    assert before is not None
    after = repo.set_labels("run-1", name="Baseline", note="first try")
    assert after is not None
    assert (after.name, after.note) == ("Baseline", "first try")
    assert after.model_copy(update={"name": None, "note": None}) == before
    assert repo.set_labels("no-such-run", name="x", note=None) is None
