#!/usr/bin/env python3
"""Agent-scoped PreToolUse guard (set in each agent's front-matter `hooks:`).

    subagent_guard.py all       every subagent: no `git commit`, `git push`, `gh pr`
    subagent_guard.py readonly  reviewer and explorer: the same, plus no file edits

Reads the hook JSON on stdin; exit 2 blocks the tool call and sends stderr to the agent.
`readonly` also blocks the Edit/Write tools and the common ways a shell writes a file
(redirects outside /tmp, `sed -i`, `tee`, rm/mv/cp/touch/mkdir, `git add/checkout/...`).
Best effort only: a shell can always write somehow (`python3 -c ...`), so the tools list in
the agent's front-matter stays the first line of defence. Standard library only.
"""

from __future__ import annotations

import json
import re
import sys

GIT_PUBLISH = re.compile(r"(?:^|[\s;&|(])git\s+(?:-\S+\s+(?:\S+\s+)?)*(?:commit|push)\b")
GH_PR = re.compile(r"(?:^|[\s;&|(])gh\s+(?:[^;&|]*?\s)?pr\b")
GIT_WRITE = re.compile(
    r"(?:^|[\s;&|(])git\s+(?:-\S+\s+(?:\S+\s+)?)*"
    r"(?:add|checkout|switch|reset|clean|stash|restore|apply|merge|rebase|cherry-pick|rm|mv|tag|branch)\b"
)
WRITER = re.compile(r"(?:^|[\s;&|(])(?:rm|mv|cp|touch|mkdir|rmdir|chmod|truncate|patch|tee)\b")
SED_INPLACE = re.compile(r"(?:^|[\s;&|(])sed\s+(?:[^;&|]*?\s)?(?:-[a-zA-Z]*i\b|--in-place)")
REDIRECT = re.compile(r"(?<![<>&0-9])>{1,2}\s*(?!&)(\S+)")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def bare(command: str) -> str:
    """The command with quoted text replaced by Q, so `grep "a>b"` is not read as a redirect."""
    out: list[str] = []
    quote = ""
    for ch in command:
        if quote:
            if ch == quote:
                quote = ""
                out.append("Q")
        elif ch in "'\"":
            quote = ch
        else:
            out.append(ch)
    return "".join(out)


def block(reason: str) -> None:
    print(f"Blocked by .claude/hooks/subagent_guard.py: {reason}", file=sys.stderr)
    sys.exit(2)


def check(mode: str, tool: str, tool_input: dict[str, object]) -> str | None:
    """The reason to block this call, or None."""
    if tool in EDIT_TOOLS:
        return "this agent is read-only and may not edit files" if mode == "readonly" else None
    if tool != "Bash":
        return None
    command = str(tool_input.get("command", ""))
    text = bare(command)
    if GIT_PUBLISH.search(text):
        return "subagents never `git commit` or `git push`; the main session commits"
    if GH_PR.search(text):
        return "subagents never use `gh pr`; the main session opens pull requests"
    if mode != "readonly":
        return None
    if GIT_WRITE.search(text) or WRITER.search(text) or SED_INPLACE.search(text):
        return "this agent is read-only: no command that changes files or the git state"
    for target in REDIRECT.findall(text):
        if not (target.startswith("/tmp/") or target == "/dev/null"):
            return f"this agent is read-only: no redirect to {target} (only /tmp/ and /dev/null)"
    return None


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else "all"
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # a malformed event is not ours to block
    reason = check(mode, str(data.get("tool_name", "")), data.get("tool_input") or {})
    if reason:
        block(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
