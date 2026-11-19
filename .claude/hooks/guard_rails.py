#!/usr/bin/env python3
"""Project PreToolUse hook: while an autopilot tick runs, block edits to the guard-rail paths.

A tick marks itself by writing `work`, `slice` or `state` to `<git dir>/autopilot-run`
(autopilot skill, step 0); the file is ignored once it is older than 6 hours, so a crashed
tick cannot leave the author's own checkout locked. With no fresh marker this hook does nothing. The paths are
listed in `.claude/hooks/guard-rails.txt`.

Covers the Edit, Write, MultiEdit and NotebookEdit tools, and Bash commands that write to a
guarded path: the target of a redirect, or an argument of `sed -i`, `tee`, rm/mv/cp, `git
checkout/restore/stash`. Running a guarded script (`python3 scripts/doc_index.py`) is not a
write, and heredoc bodies are data. Best effort: a shell can write a file in ways this does not
see (`python -c`). Exit 2 blocks the call.
Standard library only.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

MARKER_MAX_AGE_S = 6 * 3600
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
WRITERS = {"tee", "rm", "mv", "cp", "truncate", "patch", "ln", "install"}
GIT_WRITERS = {"checkout", "restore", "stash", "reset", "clean"}
SEGMENT_END = re.compile(r"\n|;|&&|\|\||\|")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
REDIRECT = re.compile(r"^\d*>{1,2}(.*)$")


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


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies: their text is data, not commands."""
    kept: list[str] = []
    end: str | None = None
    for line in command.split("\n"):
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        kept.append(line)
        match = HEREDOC.search(line)
        if match:
            end = match.group(2)
    return "\n".join(kept)


def written_paths(command: str) -> list[str]:
    """Paths a shell command writes to, as far as its text shows (best effort)."""
    paths: list[str] = []
    for segment in SEGMENT_END.split(strip_heredocs(command)):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()
        words = [t for t in tokens if not REDIRECT.match(t)]
        for i, token in enumerate(tokens):
            match = REDIRECT.match(token)
            if match:
                target = match.group(1) or (tokens[i + 1] if i + 1 < len(tokens) else "")
                if target and not target.startswith("&") and target != "/dev/null":
                    paths.append(target)
        while words and re.match(r"^\w+=", words[0]):
            words = words[1:]
        if not words:
            continue
        name = os.path.basename(words[0])
        args = [w for w in words[1:] if not w.startswith("-")]
        in_place = name == "sed" and any(
            re.match(r"^-[a-zA-Z]*i|^--in-place", w) for w in words[1:] if w.startswith("-")
        )
        if name in WRITERS or in_place:
            paths += args
        elif name == "git" and args and args[0] in GIT_WRITERS:
            paths += args[1:]
    return paths


def reason_to_block(tool: str, tool_input: dict[str, object], rules: list[str]) -> str | None:
    if tool in EDIT_TOOLS:
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if path and is_guarded(relative_to_root(path), rules):
            return f"`{relative_to_root(path)}` is a guard-rail path"
    elif tool == "Bash":
        for target in written_paths(str(tool_input.get("command", ""))):
            if is_guarded(relative_to_root(target), rules):
                return f"the command writes the guard-rail path `{target}`"
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
