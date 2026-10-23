"""Run record v2: every run carries a fingerprint of its outputs and the code that made it."""

from __future__ import annotations

import hashlib
import json
import re

import pytest
from fastapi.testclient import TestClient

from simforge.core import reproducibility

URL = "/api/v1/economy/solow/simulate"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def published_digest(body: dict[str, object]) -> str:
    """The digest as documented, recomputed by a client from the JSON it received: SHA-256
    of the response without its metadata, keys sorted, no whitespace."""
    rest = {k: v for k, v in body.items() if k != "metadata"}
    text = json.dumps(rest, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def test_a_run_reports_and_stores_its_output_digest_and_code_identity(
    client: TestClient,
) -> None:
    body = client.post(URL, json={}).json()
    meta = body["metadata"]
    assert HEX64.match(meta["output_digest"])
    # Anyone can check the digest from the response alone.
    assert meta["output_digest"] == published_digest(body)
    assert meta["git_commit"]
    assert meta["python_implementation"] == "CPython"

    record = client.get(f"/api/v1/experiments/{meta['run_id']}").json()
    assert record["record_version"] == 2
    assert record["output_digest"] == meta["output_digest"]
    assert record["replay_of"] is None
    assert record["environment"]["git_commit"] == meta["git_commit"]


def test_same_inputs_give_the_same_digest_and_different_inputs_do_not(
    client: TestClient,
) -> None:
    def digest(payload: dict[str, object]) -> str:
        return str(client.post(URL, json=payload).json()["metadata"]["output_digest"])

    assert digest({}) == digest({})
    assert digest({}) != digest({"policy": {"new_savings_rate": 0.31}})


def test_the_digest_is_not_affected_by_run_metadata(client: TestClient) -> None:
    a = client.post(URL, json={"save_experiment": True}).json()["metadata"]
    b = client.post(URL, json={"save_experiment": False}).json()["metadata"]
    assert a["run_id"] != b["run_id"]
    assert a["output_digest"] == b["output_digest"]


def test_the_commit_can_be_set_by_the_deployment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMFORGE_GIT_COMMIT", "0123abc")
    reproducibility.code_version.cache_clear()
    try:
        assert reproducibility.environment_info()["git_commit"] == "0123abc"
    finally:
        reproducibility.code_version.cache_clear()
