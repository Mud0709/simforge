"""docs/INDEX.md is up to date (scripts/doc_index.py --check), so CI fails when it is stale."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_doc_index_is_fresh() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "doc_index.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
