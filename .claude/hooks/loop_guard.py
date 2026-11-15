#!/usr/bin/env python3
"""Loop guard: stop an agent re-running the same failing shell command.

Ported idea from Microsoft's TokenEconomizer loop guard (Apache-2.0, github.com/microsoft/
TokenEconomizer), which is a plugin and so cannot run in cloud sessions. This is the simple
core: no judge model, only a counter.

    loop_guard.py fail    PostToolUseFailure(Bash): count a failure of this exact command
    loop_guard.py pre     PreToolUse(Bash): block the command once it has failed 3 times
    loop_guard.py reset   PostToolUse(Edit|Write|MultiEdit|NotebookEdit|Bash): an edit clears the
                          counts; a Bash success clears that command's count

State is one small JSON file per session and agent in the temp directory. Exit 2 blocks the
call and tells the agent to change something first. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

LIMIT = 3


def state_file(data: dict[str, object]) -> Path:
    who = f"{data.get('session_id', 'session')}-{data.get('agent_id', 'main')}"
    root = Path(os.environ.get("SIMFORGE_LOOPGUARD_DIR") or tempfile.gettempdir())
    return root / f"simforge-loopguard-{who}.json"


def key(data: dict[str, object]) -> str:
    tool_input = data.get("tool_input")
    command = " ".join(
        str(tool_input.get("command", "") if isinstance(tool_input, dict) else "").split()
    )
    return hashlib.sha1(command.encode()).hexdigest()[:16]


def load(path: Path) -> dict[str, int]:
    try:
        return {str(k): int(v) for k, v in json.loads(path.read_text()).items()}
    except (OSError, ValueError):
        return {}


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else ""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    path = state_file(data)
    counts = load(path)
    if mode == "pre":
        if data.get("tool_name") == "Bash" and counts.get(key(data), 0) >= LIMIT:
            print(
                f"Blocked by .claude/hooks/loop_guard.py: this exact command has failed {LIMIT} "
                "times with no edit in between. Read the error, change something (a file, the "
                "command, the approach) or ask the author; do not run it again unchanged.",
                file=sys.stderr,
            )
            return 2
        return 0
    if mode == "fail":
        counts[key(data)] = counts.get(key(data), 0) + 1
    elif mode == "reset":
        if data.get("tool_name") == "Bash":
            counts.pop(key(data), None)
        else:
            counts = {}
    else:
        return 0
    path.write_text(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
