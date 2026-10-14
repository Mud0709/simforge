import sqlite3
from pathlib import Path

import pytest

from simforge.persistence.experiments import init_db


def test_init_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "db.sqlite3"
    init_db(db)
    init_db(db)
    assert db.exists()


def test_schema_version_mismatch_is_refused(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE schema_version SET version = 999")
    conn.close()
    with pytest.raises(RuntimeError, match="schema v999"):
        init_db(db)
