from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simforge.config import Settings
from simforge.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(Settings(db_path=tmp_path / "test.sqlite3"))
    with TestClient(app) as c:  # context manager runs the lifespan (DB init)
        yield c
