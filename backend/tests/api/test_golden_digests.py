"""Golden runs: fixed inputs must keep producing the same outputs for a model version.

This is a **regression guard, not evidence of correctness**: the pinned values were taken
from the code itself. Correctness comes from the independent reference tests. What this test
catches is an output that changes *without* the model's version changing, which would make a
replay of an old run report a difference nobody declared.

Bit-identical outputs can only be expected on the machine type the runs were pinned on: on
another CPU the same code and the same locked libraries can round the last bits differently
(CI showed this in roadmap 1.4: four of five models gave different digests on GitHub's
runners). So:

* digest equal to the pinned one: pass (every output bit-identical);
* otherwise the stored summary is compared with the model's **declared replay tolerances**,
  exactly as a replay would, and the test warns that only tolerance-level agreement was
  checked. A value outside its tolerance fails. On CI this is a real cross-machine test of
  the declared tolerances.

If outputs change on purpose: bump the model's version in its MODEL_INFO, then re-pin with
``uv run python -m tests.api.pin_golden_runs`` (from ``backend/``). If you changed nothing in
the model, look for the accidental change (a library upgrade, a reordered sum) first.
"""

from __future__ import annotations

import json
import warnings
from typing import Any

import pytest

from simforge.api.registry import get_entry
from simforge.api.replay import compare_summaries
from tests.api.pin_golden_runs import GOLDEN_FILE, current_runs
from tests.api.test_registry import CASES

GOLDEN: list[dict[str, Any]] = json.loads(GOLDEN_FILE.read_text())


class GoldenToleranceOnly(UserWarning):
    """Outputs were not bit-identical here; they agreed within the declared tolerances."""


def check_golden(golden: dict[str, Any], now: dict[str, Any]) -> str:
    """Return "identical" or "within_tolerance"; fail the test otherwise."""
    model_id = golden["model_id"]
    if now["model_version"] != golden["model_version"]:
        pytest.fail(f"{model_id} is now v{now['model_version']}: re-pin the golden runs")
    if now["output_digest"] == golden["output_digest"]:
        return "identical"
    entry = get_entry(model_id)
    assert entry is not None
    rules = entry.tolerances(golden["inputs"], golden["summary"])
    comparison = compare_summaries(golden["summary"], now["summary"], rules)
    largest = comparison.largest
    detail = (
        "no summary field differs"
        if largest is None
        else f"largest difference: {largest.field} {largest.original!r} -> {largest.replay!r}"
    )
    if not comparison.within_tolerance:
        pytest.fail(
            f"{model_id} v{golden['model_version']} changed beyond its declared tolerances "
            f"({detail}; fields only in one summary: {comparison.missing}). Bump its version "
            "if this was intended (see this file's docstring)."
        )
    changed_env = {
        k: (v, now["environment"].get(k))
        for k, v in golden["environment"].items()
        if now["environment"].get(k) != v
    }
    warnings.warn(
        GoldenToleranceOnly(
            f"{model_id}: outputs not bit-identical to the pinned run; summary within declared "
            f"tolerances ({detail}). Environment differences from the pinning run: "
            f"{changed_env or 'none recorded'}."
        ),
        stacklevel=2,
    )
    return "within_tolerance"


def test_every_case_is_pinned() -> None:
    assert [g["model_id"] for g in GOLDEN] == [case[0] for case in CASES]


def test_outputs_have_not_changed_for_their_model_versions() -> None:
    for golden, now in zip(GOLDEN, current_runs(), strict=True):
        check_golden(golden, now)


# --- the check itself can fail ------------------------------------------------------------


def _solow_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    golden = next(g for g in GOLDEN if g["model_id"] == "economy.solow")
    return golden, json.loads(json.dumps(golden))  # an independent copy


def test_a_changed_digest_with_a_tiny_change_passes_with_a_warning() -> None:
    golden, now = _solow_pair()
    now["output_digest"] = "0" * 64
    now["summary"]["final_capital"] *= 1 + 2e-16  # about one unit in the last place
    with pytest.warns(GoldenToleranceOnly, match="final_capital"):
        assert check_golden(golden, now) == "within_tolerance"


def test_a_change_beyond_tolerance_fails() -> None:
    golden, now = _solow_pair()
    now["output_digest"] = "0" * 64
    now["summary"]["final_capital"] *= 1 + 1e-6
    with pytest.raises(pytest.fail.Exception, match="beyond its declared tolerances"):
        check_golden(golden, now)


def test_a_new_model_version_requires_re_pinning() -> None:
    golden, now = _solow_pair()
    now["model_version"] = "9.9.9"
    with pytest.raises(pytest.fail.Exception, match="re-pin"):
        check_golden(golden, now)
