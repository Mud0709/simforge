"""scripts/tick_metrics.py: test counts, durations and check status parsed from check logs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("tick_metrics", ROOT / "scripts" / "tick_metrics.py")
assert _spec is not None
assert _spec.loader is not None
tick_metrics = importlib.util.module_from_spec(_spec)
sys.modules["tick_metrics"] = tick_metrics
_spec.loader.exec_module(tick_metrics)

# Summaries copied from real runs of this repository's checks (2026-11-08), except the
# Playwright and failing cases, which follow those tools' documented summary formats.
PYTEST_QUIET = "...............  [100%]\n15 passed, 302 deselected in 0.26s\n"
PYTEST_BORDERED = "== 15 passed, 302 deselected in 0.10s ==\n"
PYTEST_FAILING = (
    "FAILED tests/x.py::t\n===== 1 failed, 2068 passed, 3 skipped in 94.70s (0:01:34) =====\n"
)
VITEST = (
    " Test Files  2 passed (2)\n      Tests  34 passed (34)\n   Start at  05:57:23\n"
    "   Duration  1.67s (environment 65%, transform 25%, setup 9%, tests 1%)\n"
)
VITEST_FAILING = "      Tests  1 failed | 33 passed (34)\n   Duration  950ms (transform 1%)\n"
PLAYWRIGHT = "  Running 4 tests using 2 workers\n\n  4 passed (12.3s)\n"
PLAYWRIGHT_FAILING = "  1 failed\n    [chromium] e2e/a.spec.ts:3 ...\n  3 passed (1.5m)\n"


@pytest.mark.parametrize(
    ("log", "expected"),
    [
        (PYTEST_QUIET, (15, 0, 0, 0.26)),
        (PYTEST_BORDERED, (15, 0, 0, 0.10)),
        (PYTEST_FAILING, (2068, 1, 3, 94.70)),
        (VITEST, (34, 0, 0, 1.67)),
        (VITEST_FAILING, (33, 1, 0, 0.95)),
        (PLAYWRIGHT, (4, 0, 0, 12.3)),
        (PLAYWRIGHT_FAILING, (3, 1, 0, 90.0)),
        ("\x1b[32m15 passed\x1b[0m in 0.26s\n", (15, 0, 0, 0.26)),
    ],
)
def test_parse_log_reads_each_tools_summary(
    log: str, expected: tuple[int, int, int, float]
) -> None:
    result = tick_metrics.parse_log(log)
    assert result.summary
    assert (result.passed, result.failed, result.skipped) == expected[:3]
    assert result.seconds == pytest.approx(expected[3], rel=1e-12, abs=0)  # decimal sums only


def test_a_log_without_a_summary_or_exit_line_is_unknown_not_pass() -> None:
    result = tick_metrics.parse_log("ruff: All checks passed!\n")
    assert not result.summary
    assert result.status == "unknown"


@pytest.mark.parametrize(
    ("log", "status"),
    [
        ("All checks passed!\nexit: 0\n", "pass"),  # lint: the exit line decides
        ("app.py:3: error: Incompatible types\nFound 3 errors in 1 file\nexit: 1\n", "fail"),
        (PYTEST_QUIET + "exit: 1\n", "fail"),  # a non-zero exit fails with no failed test
        # Vitest: a test file that fails to load runs no test but fails the check
        (" Test Files  1 failed | 1 passed (2)\n      Tests  2 passed (2)\n", "fail"),
        ("  2 interrupted\n  5 passed (3.0s)\n", "fail"),
        ("  1 flaky\n  4 passed (3.0s)\nexit: 0\n", "pass"),  # passed on retry
    ],
)
def test_the_check_status_uses_the_exit_code_and_failure_lines(log: str, status: str) -> None:
    assert tick_metrics.parse_log(log).status == status


def test_flaky_and_did_not_run_are_counted_apart() -> None:
    result = tick_metrics.parse_log("  1 flaky\n  3 did not run\n  4 passed (3.0s)\n")
    assert (result.passed, result.failed, result.skipped, result.flaky) == (4, 0, 3, 1)


def test_entry_properties_are_written_and_replaced(tmp_path: Path) -> None:
    logs = []
    for name, text in [
        ("pytest.log", PYTEST_FAILING),
        ("vitest.log", VITEST + "exit: 0\n"),
        ("ruff.log", "ok\n"),
    ]:
        path = tmp_path / name
        path.write_text(text)
        logs.append(path)
    entry = tmp_path / "entry.md"
    entry.write_text(
        '---\ndate: 2026-11-08T06:00\ntests_passed: 999\nchecks:\n  - "old: pass"\n---\n\nBody.\n'
    )
    tick_metrics.main([str(entry), *map(str, logs)])
    text = entry.read_text()
    assert "tests_passed: 2102\n" in text  # 2068 + 34
    assert "tests_failed: 1\n" in text
    assert "tests_flaky: 0\n" in text
    assert "test_seconds: 96.37\n" in text  # 94.70 + 1.67
    assert '  - "pytest: fail"\n  - "vitest: pass"\n  - "ruff: unknown"\n' in text
    assert "999" not in text
    assert "old: pass" not in text
    assert text.endswith("---\n\nBody.\n")
    assert text.startswith("---\ndate: 2026-11-08T06:00\n")
    first = text
    tick_metrics.main([str(entry), *map(str, logs)])
    assert entry.read_text() == first  # running it twice changes nothing


def test_no_recognised_summary_writes_unknown(tmp_path: Path) -> None:
    entry = tmp_path / "entry.md"
    entry.write_text("---\ndate: 2026-11-08T06:00\n---\n")
    tick_metrics.main([str(entry)])
    text = entry.read_text()
    assert "tests_passed: unknown\n" in text
    assert "checks: []\n" in text


def test_an_entry_without_front_matter_is_refused(tmp_path: Path) -> None:
    entry = tmp_path / "entry.md"
    entry.write_text("no properties\n")
    with pytest.raises(ValueError, match="front matter"):
        tick_metrics.main([str(entry)])
