"""The agent definitions in .claude/agents/ match the model table in CLAUDE.md.

CLAUDE.md is the one place the routing rule is written; each agent's front-matter pins the same
model and effort so nothing depends on a spawn-time override. This test fails when they drift,
and checks the structural rules (read-only agents have no edit tools, every agent is guarded).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
AGENTS = ROOT / ".claude" / "agents"
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_ONLY = {"reviewer", "explorer", "test-runner"}


def front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    head = text.split("---\n")[1]
    return {
        m.group(1): m.group(2).strip() for m in re.finditer(r"^([a-zA-Z]+):[ \t]*(.*)$", head, re.M)
    }


def table() -> dict[str, tuple[str, str]]:
    """agent name -> (model, effort), from the table in CLAUDE.md."""
    rows: dict[str, tuple[str, str]] = {}
    for line in (ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"`claude-[a-z0-9-]+`, \w+", cells[1]):
            continue
        model, effort = (x.strip("` ") for x in cells[1].split(","))
        for name in re.findall(r"`([a-z-]+)`", cells[0]):
            rows[name] = (model, effort)
    return rows


def test_the_table_lists_every_agent_file() -> None:
    assert set(table()) == {p.stem for p in AGENTS.glob("*.md")}


@pytest.mark.parametrize("name", sorted(p.stem for p in AGENTS.glob("*.md")))
def test_each_agent_pins_the_model_and_effort_the_table_says(name: str) -> None:
    fm = front_matter(AGENTS / f"{name}.md")
    assert fm["name"] == name
    assert (fm["model"], fm["effort"]) == table()[name]
    assert int(fm["maxTurns"]) > 0


@pytest.mark.parametrize("name", sorted(p.stem for p in AGENTS.glob("*.md")))
def test_read_only_agents_have_no_edit_tools_and_every_agent_is_guarded(name: str) -> None:
    path = AGENTS / f"{name}.md"
    tools = {t.strip() for t in front_matter(path)["tools"].split(",")}
    if name in READ_ONLY:
        assert not tools & EDIT_TOOLS
    assert "subagent_guard.py" in path.read_text(encoding="utf-8")


def test_effort_is_capped_and_the_main_session_default_is_medium() -> None:
    import json

    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["effortLevel"] == "medium"
    assert settings["maxEffortLevel"] == "high"
    assert settings["autoCompactWindow"] == 400000
