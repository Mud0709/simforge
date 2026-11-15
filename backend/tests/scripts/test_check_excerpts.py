"""Learning-guide excerpts match their source (scripts/check_excerpts.py), so CI fails when
code moves and a guide is not updated; and the checker itself catches a planted mismatch."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check_excerpts.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_excerpts", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guide_excerpts_match_their_source() -> None:
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    # The guides hold dozens of excerpts: a run that found none checked nothing.
    assert int(result.stdout.split()[0]) >= 50


def _doc(tmp_path: Path, body: str) -> Path:
    (tmp_path / "code.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    doc = tmp_path / "guide.md"
    doc.write_text(body, encoding="utf-8")
    return doc


def test_matching_excerpt_passes(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "<!-- src: code.py:2-3 -->\n```python\nb = 2\nc = 3\n```\n")
    assert _module().problems(doc, tmp_path) == (1, [])


def test_changed_line_moved_range_and_missing_file_are_reported(tmp_path: Path) -> None:
    check = _module().problems
    changed = _doc(tmp_path, "<!-- src: code.py:2-3 -->\n```python\nb = 2\nc = 4\n```\n")
    assert len(check(changed, tmp_path)[1]) == 1
    moved = _doc(tmp_path, "<!-- src: code.py:1-2 -->\n```python\nb = 2\nc = 3\n```\n")
    assert len(check(moved, tmp_path)[1]) == 1
    missing = _doc(tmp_path, "<!-- src: gone.py:1 -->\n```python\na = 1\n```\n")
    assert "does not exist" in check(missing, tmp_path)[1][0]
    no_block = _doc(tmp_path, "<!-- src: code.py:1 -->\n\nprose only\n")
    assert "no code block" in check(no_block, tmp_path)[1][0]


def test_a_tag_quoted_in_prose_is_not_an_excerpt(tmp_path: Path) -> None:
    doc = _doc(tmp_path, "Excerpts are tagged `<!-- src: path:1-2 -->` in the guides.\n")
    assert _module().problems(doc, tmp_path) == (0, [])
