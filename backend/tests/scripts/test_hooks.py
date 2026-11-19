"""The agent and tick hooks in .claude/hooks/ and the commit-msg hook in .githooks/.

Each hook is run as the harness runs it: the tool call as JSON on stdin, exit code 2 meaning
"blocked". The cases are written from the rules (a subagent never commits or pushes; a
read-only agent never writes; a tick never edits a guard rail; the same failing command is
stopped after three failures), not from the hooks' output.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / ".claude" / "hooks"


def run_hook(
    script: str,
    args: list[str],
    payload: dict[str, object],
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(HOOKS / script), *args],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        check=False,
    )


def bash(command: str, **extra: object) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}, **extra}


# --- subagent_guard.py -------------------------------------------------------------------

PUBLISHING = [
    "git commit -m x",
    "git add -A && git commit -m x",
    "git -C /tmp/repo push origin main",
    "git push --force-with-lease",
    "gh pr create --draft",
    "cd backend; gh pr merge 3",
]
HARMLESS = [
    "git log --oneline | head",
    "git diff HEAD~1 -- CLAUDE.md",
    'grep -n "git commit" CLAUDE.md',
    "sed -n '1,5p' f | grep -i x",
    "gh api repos/o/r/pulls | grep -i pr",
    "uv run pytest tests/x.py -q > /tmp/tick/pytest.log 2>&1",
    "ls > /dev/null",
]
WRITING = [
    "echo hi > notes.txt",
    "sed -i 's/a/b/' f",
    "cat a | tee out.txt",
    "rm -rf build",
    "mv a b",
    "git checkout -- .",
    "git stash",
]


@pytest.mark.parametrize("mode", ["all", "readonly"])
@pytest.mark.parametrize("command", PUBLISHING)
def test_no_subagent_commits_pushes_or_opens_prs(mode: str, command: str) -> None:
    assert run_hook("subagent_guard.py", [mode], bash(command)).returncode == 2


@pytest.mark.parametrize("mode", ["all", "readonly"])
@pytest.mark.parametrize("command", HARMLESS)
def test_reading_and_logging_commands_are_allowed(mode: str, command: str) -> None:
    assert run_hook("subagent_guard.py", [mode], bash(command)).returncode == 0


@pytest.mark.parametrize("command", WRITING)
def test_read_only_agents_cannot_write_through_the_shell(command: str) -> None:
    assert run_hook("subagent_guard.py", ["readonly"], bash(command)).returncode == 2
    assert run_hook("subagent_guard.py", ["all"], bash(command)).returncode == 0


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
def test_edit_tools_are_blocked_only_for_read_only_agents(tool: str) -> None:
    call = {"tool_name": tool, "tool_input": {"file_path": "x.py"}}
    assert run_hook("subagent_guard.py", ["readonly"], call).returncode == 2
    assert run_hook("subagent_guard.py", ["all"], call).returncode == 0


def test_auto_mode_limits_subagents_by_type_and_leaves_the_main_thread_alone() -> None:
    def code(command: str, **who: str) -> int:
        return run_hook("subagent_guard.py", ["auto"], bash(command, **who)).returncode

    assert code("git commit -m x") == 0  # no agent_id: the main thread commits
    assert code("echo x > f.txt") == 0
    assert code("git commit -m x", agent_id="a1", agent_type="builder") == 2
    assert code("echo x > f.txt", agent_id="a1", agent_type="builder") == 0
    assert code("echo x > f.txt", agent_id="a2", agent_type="reviewer") == 2
    assert code("echo x > f.txt", agent_id="a3", agent_type="explorer") == 2
    assert code("git push", agent_id="a4", agent_type="general-purpose") == 2


def test_the_hook_log_records_each_call_when_asked(tmp_path: Path) -> None:
    log = tmp_path / "hook.jsonl"
    payload = bash("git push", agent_id="a1", agent_type="reviewer")
    run_hook("subagent_guard.py", ["auto"], payload, {"SIMFORGE_HOOK_LOG": str(log)})
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry == {"mode": "readonly", "agent": "reviewer", "tool": "Bash", "blocked": True}


def test_a_malformed_event_is_not_blocked() -> None:
    result = subprocess.run(
        ["python3", str(HOOKS / "subagent_guard.py"), "all"],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


# --- guard_rails.py ----------------------------------------------------------------------


def tick_env(tmp_path: Path, age_hours: float = 0.0, kind: str = "work") -> dict[str, str]:
    marker = tmp_path / "autopilot-run"
    marker.write_text(kind)
    old = time.time() - age_hours * 3600
    os.utime(marker, (old, old))
    return {"SIMFORGE_MARKER": str(marker), "CLAUDE_PROJECT_DIR": str(ROOT)}


GUARDED = [
    ".claude/skills/autopilot/SKILL.md",
    ".claude/agents/builder.md",
    ".github/workflows/ci.yml",
    "scripts/check.sh",
    "scripts/tick_metrics.py",
    "Makefile",
    "CLAUDE.md",
    "backend/CLAUDE.md",
    "docs/journal/_template.md",
    "backend/pyproject.toml",
]
FREE = [
    ".claude/autopilot/STATE.md",
    ".claude/autopilot/FINDINGS.md",
    "backend/src/simforge/physics/oscillator/model.py",
    "docs/HANDOFF.md",
    "docs/journal/2026-11-15-0300-x.md",
]


@pytest.mark.parametrize("path", GUARDED)
def test_a_running_tick_cannot_edit_a_guard_rail(tmp_path: Path, path: str) -> None:
    call = {"tool_name": "Edit", "tool_input": {"file_path": str(ROOT / path)}}
    assert run_hook("guard_rails.py", [], call, tick_env(tmp_path)).returncode == 2


@pytest.mark.parametrize("path", FREE)
def test_a_running_tick_can_edit_everything_else(tmp_path: Path, path: str) -> None:
    call = {"tool_name": "Write", "tool_input": {"file_path": str(ROOT / path)}}
    assert run_hook("guard_rails.py", [], call, tick_env(tmp_path)).returncode == 0


def test_without_a_tick_marker_nothing_is_blocked(tmp_path: Path) -> None:
    call = {"tool_name": "Edit", "tool_input": {"file_path": str(ROOT / "CLAUDE.md")}}
    env = {"SIMFORGE_MARKER": str(tmp_path / "missing"), "CLAUDE_PROJECT_DIR": str(ROOT)}
    assert run_hook("guard_rails.py", [], call, env).returncode == 0


def test_a_stale_marker_is_ignored(tmp_path: Path) -> None:
    call = {"tool_name": "Edit", "tool_input": {"file_path": str(ROOT / "CLAUDE.md")}}
    assert run_hook("guard_rails.py", [], call, tick_env(tmp_path, age_hours=7)).returncode == 0


def test_a_shell_write_to_a_guard_rail_is_blocked_but_reading_is_not(tmp_path: Path) -> None:
    env = tick_env(tmp_path)

    def code(command: str) -> int:
        return run_hook("guard_rails.py", [], bash(command), env).returncode

    assert code("sed -i 's/a/b/' scripts/check.sh") == 2
    assert code("echo x >> CLAUDE.md") == 2
    assert code("sed -n '1,5p' scripts/check.sh") == 0
    assert code("cat CLAUDE.md | head") == 0


def test_running_a_guarded_script_is_not_writing_it(tmp_path: Path) -> None:
    """Regenerating the docs index runs scripts/doc_index.py; a redirect elsewhere is no write."""
    env = tick_env(tmp_path)

    def code(command: str) -> int:
        return run_hook("guard_rails.py", [], bash(command), env).returncode

    assert code("python3 scripts/doc_index.py > /dev/null") == 0
    assert (
        code("python3 scripts/doc_index.py && python3 scripts/doc_index.py --check; echo rc=$?")
        == 0
    )
    assert code("python3 scripts/doc_index.py 2>&1 | tail -3") == 0
    assert code("scripts/run_logged.sh check 'scripts/check.sh --e2e'") == 0
    assert code("echo x > docs/journal/note.md") == 0


def test_text_inside_a_heredoc_is_data_not_a_command(tmp_path: Path) -> None:
    env = tick_env(tmp_path)
    journal = "cat > docs/journal/x.md <<'EOF'\nran scripts/check.sh and rm CLAUDE.md\nEOF"
    assert run_hook("guard_rails.py", [], bash(journal), env).returncode == 0
    into_rail = "cat > scripts/new.sh <<'EOF'\nhello\nEOF"
    assert run_hook("guard_rails.py", [], bash(into_rail), env).returncode == 2


def test_every_write_form_aimed_at_a_guard_rail_is_still_blocked(tmp_path: Path) -> None:
    env = tick_env(tmp_path)

    def code(command: str) -> int:
        return run_hook("guard_rails.py", [], bash(command), env).returncode

    assert code("echo x > scripts/check.sh") == 2
    assert code("cp /tmp/a scripts/check.sh") == 2
    assert code("mv /tmp/a Makefile") == 2
    assert code("echo x | tee CLAUDE.md") == 2
    assert code("rm .claude/agents/builder.md") == 2
    assert code("git checkout -- scripts/check.sh") == 2
    assert code("cd . && sed -i s/a/b/ backend/pyproject.toml") == 2


# --- loop_guard.py -----------------------------------------------------------------------


def loop_env(tmp_path: Path) -> dict[str, str]:
    return {"SIMFORGE_LOOPGUARD_DIR": str(tmp_path)}


def test_the_same_failing_command_is_blocked_after_three_failures(tmp_path: Path) -> None:
    env = loop_env(tmp_path)
    call = bash("uv run pytest tests/x.py", session_id="s1")
    for _ in range(3):
        assert run_hook("loop_guard.py", ["pre"], call, env).returncode == 0
        run_hook("loop_guard.py", ["fail"], call, env)
    assert run_hook("loop_guard.py", ["pre"], call, env).returncode == 2
    other = bash("uv run pytest tests/y.py", session_id="s1")
    assert run_hook("loop_guard.py", ["pre"], other, env).returncode == 0


def test_an_edit_clears_the_failure_counts(tmp_path: Path) -> None:
    env = loop_env(tmp_path)
    call = bash("make check", session_id="s1")
    for _ in range(3):
        run_hook("loop_guard.py", ["fail"], call, env)
    edit = {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}, "session_id": "s1"}
    run_hook("loop_guard.py", ["reset"], edit, env)
    assert run_hook("loop_guard.py", ["pre"], call, env).returncode == 0


def test_a_success_clears_that_commands_count_and_agents_are_counted_apart(tmp_path: Path) -> None:
    env = loop_env(tmp_path)
    call = bash("make check", session_id="s1")
    for _ in range(3):
        run_hook("loop_guard.py", ["fail"], call, env)
    other_agent = bash("make check", session_id="s1", agent_id="a7")
    assert run_hook("loop_guard.py", ["pre"], other_agent, env).returncode == 0
    run_hook("loop_guard.py", ["reset"], call, env)
    assert run_hook("loop_guard.py", ["pre"], call, env).returncode == 0


# --- .githooks/commit-msg ----------------------------------------------------------------


def commit(tmp_path: Path, message: str, marker: Path | None, age_hours: float = 0.0) -> str:
    repo = tmp_path / "repo"
    if not repo.exists():
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        for key, value in [
            ("user.name", "t"),
            ("user.email", "t@example.com"),
            ("commit.gpgsign", "false"),
            ("core.hooksPath", str(ROOT / ".githooks")),
        ]:
            subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
    (repo / "f.txt").write_text(message)
    env = {**os.environ}
    env.pop("SIMFORGE_MARKER", None)
    if marker is not None:
        old = time.time() - age_hours * 3600
        os.utime(marker, (old, old))
        env["SIMFORGE_MARKER"] = str(marker)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", message], check=True, env=env)
    return subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%B"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@pytest.mark.parametrize("kind", ["work", "slice", "state"])
def test_commit_msg_adds_the_autopilot_trailer_while_a_tick_marker_is_fresh(
    tmp_path: Path, kind: str
) -> None:
    marker = tmp_path / "autopilot-run"
    marker.write_text(kind)
    body = commit(tmp_path, "A unit of work", marker)
    assert f"Autopilot-run: {kind}" in body
    assert body.count("Autopilot-run:") == 1
    assert "Co-Authored-By: Claude" in body


def test_commit_msg_keeps_an_existing_trailer_and_adds_nothing_without_a_marker(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "autopilot-run"
    marker.write_text("work")
    body = commit(tmp_path, "Unit\n\nAutopilot-run: state", marker)
    assert body.count("Autopilot-run:") == 1
    assert "Autopilot-run: state" in body
    assert "Autopilot-run" not in commit(tmp_path, "The author's own commit", None)


def test_commit_msg_ignores_a_stale_marker(tmp_path: Path) -> None:
    marker = tmp_path / "autopilot-run"
    marker.write_text("work")
    assert "Autopilot-run" not in commit(tmp_path, "Old marker", marker, age_hours=7)
