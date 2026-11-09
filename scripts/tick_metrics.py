#!/usr/bin/env python3
"""Write test counts and durations, parsed from check logs, into a journal entry's properties.

The autopilot saves the output of each check it runs to a log file, then runs
    python3 scripts/tick_metrics.py docs/journal/<entry>.md <log> [<log> ...]
The numbers in the entry's front matter come from this script, never from the model:
`tests_passed`, `tests_failed`, `tests_skipped`, `test_seconds` (sums over all logs) and
`tests_flaky` and `checks` (one string per log: "<file name>: pass", "fail" or "unknown").

Save every check as `cmd > /tmp/tick/<check>.log 2>&1; echo "exit: $?" >> /tmp/tick/<check>.log`.
A check is "fail" when its exit code is non-zero or its summary reports failures (failed
tests, a failed Vitest test file, interrupted Playwright tests), "pass" when its exit code is
0, and "unknown" only when the log has neither an exit line nor a recognised summary. Lint,
type and build checks have no test counts; their exit line decides.

Recognised summaries: pytest, with or without -q ("3 passed, 1 failed, 2 skipped in 4.20s"),
Vitest ("Tests  12 passed | 1 failed (13)" and "Duration  1.23s"),
Playwright ("4 passed (12.3s)", "1 failed"). Standard library only.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
PYTEST = re.compile(
    r"^=*\s*(?P<body>\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected)[^=\n]*?)"
    r" in (?P<secs>[\d.]+)s(?:\s*\([^)]*\))?\s*=*\s*$",
    re.M,
)
PYTEST_PART = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)")
VITEST_TESTS = re.compile(r"^\s*Tests\s+(?P<body>.+?)\s+\(\d+\)\s*$", re.M)
VITEST_PART = re.compile(r"(\d+) (passed|failed|skipped|todo)")
VITEST_TIME = re.compile(r"^\s*Duration\s+(?P<secs>[\d.]+)(?P<unit>m?s)\b", re.M)
PLAYWRIGHT_PASSED = re.compile(r"^\s*(\d+) passed \((?P<secs>[\d.]+)(?P<unit>m|s|ms)\)", re.M)
PLAYWRIGHT_OTHER = re.compile(r"^\s*(\d+) (failed|flaky|skipped|interrupted|did not run)\s*$", re.M)
VITEST_FILES_FAILED = re.compile(r"^\s*Test Files\s+(\d+) failed", re.M)
EXIT = re.compile(r"^exit: (-?\d+)\s*$", re.M)


@dataclass
class Counts:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    flaky: int = 0
    seconds: float = 0.0
    found: bool = False
    checks: list[tuple[str, str]] = field(default_factory=list)


def _seconds(value: str, unit: str) -> float:
    number = float(value)
    return {"ms": number / 1000, "s": number, "m": number * 60}[unit]


@dataclass
class LogResult:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    flaky: int = 0
    seconds: float = 0.0
    summary: bool = False  # a test summary was recognised
    failing: bool = False  # the summary or the exit code says the check failed
    exit_code: int | None = None

    @property
    def status(self) -> str:
        if self.failing or (self.exit_code is not None and self.exit_code != 0):
            return "fail"
        if self.exit_code == 0 or self.summary:
            return "pass"
        return "unknown"


def parse_log(text: str) -> LogResult:
    """Counts, durations and the pass/fail evidence in one check's log."""
    text = ANSI.sub("", text)
    r = LogResult()
    for m in PYTEST.finditer(text):
        parts = PYTEST_PART.findall(m.group("body"))
        if not parts:
            continue
        r.summary = True
        r.seconds += float(m.group("secs"))
        for n, kind in parts:
            if kind in ("passed", "xpassed"):
                r.passed += int(n)
            elif kind in ("failed", "error", "errors"):
                r.failed += int(n)
            else:
                r.skipped += int(n)
    for m in VITEST_TESTS.finditer(text):
        r.summary = True
        for n, kind in VITEST_PART.findall(m.group("body")):
            if kind == "passed":
                r.passed += int(n)
            elif kind == "failed":
                r.failed += int(n)
            else:
                r.skipped += int(n)
    if VITEST_FILES_FAILED.search(text):
        r.summary = True
        r.failing = True  # a test file that fails to load runs no tests but fails the check
    for m in VITEST_TIME.finditer(text):
        r.seconds += _seconds(m.group("secs"), m.group("unit"))
    for m in PLAYWRIGHT_PASSED.finditer(text):
        r.summary = True
        r.passed += int(m.group(1))
        r.seconds += _seconds(m.group("secs"), m.group("unit"))
    for m in PLAYWRIGHT_OTHER.finditer(text):
        r.summary = True
        n, kind = int(m.group(1)), m.group(2)
        if kind == "flaky":
            r.flaky += n  # passed on retry; Playwright exits 0
        elif kind in ("skipped", "did not run"):
            r.skipped += n
        else:
            r.failed += n
    r.failing = r.failing or r.failed > 0
    exits = EXIT.findall(text)
    if exits:
        r.exit_code = int(exits[-1])
    return r


def collect(logs: list[Path]) -> Counts:
    counts = Counts()
    for log in logs:
        r = parse_log(log.read_text(encoding="utf-8", errors="replace"))
        if r.summary:
            counts.found = True
            counts.passed += r.passed
            counts.failed += r.failed
            counts.skipped += r.skipped
            counts.flaky += r.flaky
            counts.seconds += r.seconds
        counts.checks.append((log.stem, r.status))
    return counts


def update_front_matter(entry: str, counts: Counts) -> str:
    """Replace or add the metric properties in the entry's YAML front matter."""
    if not entry.startswith("---\n") or "\n---\n" not in entry[4:]:
        raise ValueError("the journal entry has no front matter (--- ... ---)")
    end = entry.index("\n---\n", 4)
    head, rest = entry[4:end], entry[end:]
    keys = (
        "tests_passed",
        "tests_failed",
        "tests_skipped",
        "tests_flaky",
        "test_seconds",
        "checks",
    )
    kept: list[str] = []
    skipping = False
    for line in head.split("\n"):
        key = line.split(":", 1)[0].strip()
        if not line.startswith((" ", "\t", "-")):
            skipping = key in keys
        if not skipping:
            kept.append(line)
    if counts.found:
        kept += [
            f"tests_passed: {counts.passed}",
            f"tests_failed: {counts.failed}",
            f"tests_skipped: {counts.skipped}",
            f"tests_flaky: {counts.flaky}",
            f"test_seconds: {round(counts.seconds, 2)}",
        ]
    else:
        kept += [
            "tests_passed: unknown",
            "tests_failed: unknown",
            "tests_skipped: unknown",
            "tests_flaky: unknown",
            "test_seconds: unknown",
        ]
    if counts.checks:
        kept.append("checks:")
        kept += [f'  - "{name}: {result}"' for name, result in counts.checks]
    else:
        kept.append("checks: []")
    return "---\n" + "\n".join(kept) + rest


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print(__doc__, file=sys.stderr)
        return 2
    entry_path = Path(argv[0])
    counts = collect([Path(p) for p in argv[1:]])
    entry_path.write_text(
        update_front_matter(entry_path.read_text(encoding="utf-8"), counts), encoding="utf-8"
    )
    print(
        f"{entry_path}: {counts.passed} passed, {counts.failed} failed, "
        f"{counts.skipped} skipped, {round(counts.seconds, 2)} s; "
        + ", ".join(f"{n} {r}" for n, r in counts.checks)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
