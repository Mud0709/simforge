#!/usr/bin/env python3
"""Project PreToolUse hook: while an autopilot tick runs, block edits to the guard-rail paths.

A tick marks itself by writing `work` or `state` to `<git dir>/autopilot-run` (autopilot skill,
step 5); the file is ignored once it is older than 6 hours, so a crashed tick cannot leave the
author's own checkout locked. With no fresh marker this hook does nothing. The paths are
listed in `.claude/hooks/guard-rails.txt`.

Covers the Edit, Write, MultiEdit and NotebookEdit tools, and Bash commands that both write
(a redirect, `sed -i`, `tee`, rm/mv/cp, `git checkout/restore/stash`) and name a guarded path.
Best effort: a shell can write a file in ways this does not see. Exit 2 blocks the call.
Standard library only.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MARKER_MAX_AGE_S = 6 * 3600
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
WRITES = re.compile(
    r"(?<![<>&0-9])>{1,2}\s*[^&\s]|(?:^|[\s;&|(])(?:tee|rm|mv|cp|truncate|patch)\b"
    r"|(?:^|[\s;&|(])sed\s+(?:[^;&|]*?\s)?(?:-[a-zA-Z]*i\b|--in-place)"
    r"|(?:^|[\s;&|(])git\s+(?:checkout|restore|stash|reset|clean)\b"
)


def root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def marker_path() -> Path:
    override = os.environ.get("SIMFORGE_MARKER")
    if override:
        return Path(override)
    out = subprocess.run(
        ["git", "rev-parse", "--git-dir"], cwd=root(), capture_output=True, text=True, check=False
    ).stdout.strip()
    return (root() / out / "autopilot-run") if out else Path("/nonexistent")


def tick_is_running() -> bool:
    marker = marker_path()
    try:
        return time.time() - marker.stat().st_mtime < MARKER_MAX_AGE_S
    except OSError:
        return False


def patterns() -> list[str]:
    lines = (Path(__file__).with_name("guard-rails.txt")).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def is_guarded(relative: str, rules: list[str]) -> bool:
    guarded = False
    for rule in rules:
        negate = rule.startswith("!")
        if fnmatch.fnmatchcase(relative, rule[1:] if negate else rule):
            guarded = not negate
    return guarded


def relative_to_root(path: str) -> str:
    p = Path(path)
    p = p if p.is_absolute() else root() / p
    try:
        return os.path.normpath(p).removeprefix(os.path.normpath(root()) + os.sep)
    except ValueError:
        return str(p)


def reason_to_block(tool: str, tool_input: dict[str, object], rules: list[str]) -> str | None:
    if tool in EDIT_TOOLS:
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if path and is_guarded(relative_to_root(path), rules):
            return f"`{relative_to_root(path)}` is a guard-rail path"
    elif tool == "Bash":
        command = str(tool_input.get("command", ""))
        if WRITES.search(command):
            for token in re.split(r"[\s;&|()<>'\"=]+", command):
                if token and is_guarded(relative_to_root(token), rules):
                    return f"the command writes and names the guard-rail path `{token}`"
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not tick_is_running():
        return 0
    reason = reason_to_block(
        str(data.get("tool_name", "")), data.get("tool_input") or {}, patterns()
    )
    if reason:
        print(
            f"Blocked by .claude/hooks/guard_rails.py: {reason}. An autopilot tick may not change "
            "guard rails (autopilot skill, step 0): record a genuine stop instead.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
