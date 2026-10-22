"""Golden digests: fixed inputs must keep producing bit-identical outputs for a model version.

This is a **regression guard, not evidence of correctness**: the pinned digests were taken
from the code itself. Correctness comes from the independent reference tests. What this test
catches is an output that changes *without* the model's version changing, which would make
a replay of an old run report "differs" for a reason nobody declared.

If it fails because you changed a model's outputs on purpose: bump that model's version in
its MODEL_INFO (a replay of older runs is then refused with an explanation, as decided for
roadmap 1.4), and pin the new digest here. If you changed nothing in the model, look for an
accidental change (a library upgrade, a reordered sum) before re-pinning.

The digests are bit-exact, so they hold for the locked library versions (uv.lock) on
linux-x86_64, where they were measured and where CI runs.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.test_registry import CASES

# (model version, output digest) for each case in test_registry.CASES, in order.
PINNED: list[tuple[str, str]] = [
    ("1.0.0", "42c7fe10ebb4ff6f0dba7d7af78e544b60cbde0ff4ba3e78fc2480d4282268cd"),
    ("1.0.0", "8f5707cfc2257db2b64365efd986b4de2138817bfb2c97c3e687c76a1dd2d3b7"),
    ("1.0.0", "b96d243c782874bee8d23fdb766f952d91c4d4fa0b169569ee5e46912f7ca6bf"),
    ("1.0.0", "74e3847314690424fbdab562073df689bef734d925d3fc9ddde22f273265f873"),
    ("1.0.0", "fedec99079dee306ccd58c162e803a96bb69d314415876e7bf3ea0f3416c79c2"),
    ("1.0.0", "a9f059e5a3b427e7564828d8df9962e0d852c58194f7126f7dffaf5fe77b2213"),
]


def test_every_case_is_pinned() -> None:
    assert len(PINNED) == len(CASES)


@pytest.mark.parametrize(("case", "pinned"), list(zip(CASES, PINNED, strict=True)))
def test_outputs_have_not_changed_for_this_model_version(
    client: TestClient,
    case: tuple[str, str, dict[str, Any], bytes | None],
    pinned: tuple[str, str],
) -> None:
    model_id, url, body, _ = case
    response = client.post(url, json={**body, "save_experiment": False}).json()
    version, digest = pinned
    if response["model"]["version"] != version:
        pytest.fail(f"{model_id} is now v{response['model']['version']}: pin its new digest")
    assert response["metadata"]["output_digest"] == digest, (
        f"{model_id} v{version} produced different outputs. Bump its version if this was "
        "intended (see this file's docstring); otherwise find the accidental change."
    )
