#!/usr/bin/env python3
"""Check that every tagged code excerpt in the learning guides matches its source lines.

An excerpt is a tag ``<!-- src: path:a-b -->`` (or ``path:a`` for one line) followed by a
fenced code block. The block must equal lines a..b of ``path`` (relative to the repository
root), ignoring trailing spaces. ``docs/CLAUDE.md`` states the rule; this script enforces it,
so an edit that moves code without updating a guide fails ``scripts/check.sh`` and CI.

Usage: ``python3 scripts/check_excerpts.py`` (exit 0 when all match; 1 with a list when not).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"<!-- src: (\S+?):(\d+)(?:-(\d+))? -->")


def problems(doc: Path, root: Path = ROOT) -> tuple[int, list[str]]:
    """(number of excerpts found, one message per excerpt that does not match)."""
    lines = doc.read_text(encoding="utf-8").split("\n")
    found, bad = 0, []
    for i, line in enumerate(lines):
        tag = TAG.search(line)
        if tag is None or "`<!--" in line:  # a tag quoted in prose is not an excerpt
            continue
        found += 1
        where = f"{doc.relative_to(root)}:{i + 1}"
        path, first, last = tag.group(1), int(tag.group(2)), int(tag.group(3) or tag.group(2))
        start = i + 1
        while start < len(lines) and not lines[start].strip():
            start += 1
        if start >= len(lines) or not lines[start].startswith("```"):
            bad.append(f"{where}: no code block follows the tag for {path}")
            continue
        end = start + 1
        while end < len(lines) and not lines[end].startswith("```"):
            end += 1
        excerpt = [text.rstrip() for text in lines[start + 1 : end]]
        source = root / path
        if not source.is_file():
            bad.append(f"{where}: {path} does not exist")
            continue
        wanted = [
            text.rstrip()
            for text in source.read_text(encoding="utf-8").split("\n")[first - 1 : last]
        ]
        if excerpt != wanted:
            bad.append(f"{where}: excerpt differs from {path}:{first}-{last}")
    return found, bad


def main() -> int:
    total, bad = 0, []
    for doc in sorted((ROOT / "docs").glob("*.md")):
        found, doc_bad = problems(doc)
        total += found
        bad += doc_bad
    if bad:
        print("\n".join(bad), file=sys.stderr)
        print(f"{len(bad)} of {total} excerpts do not match their source.", file=sys.stderr)
        return 1
    print(f"{total} excerpts match their source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
