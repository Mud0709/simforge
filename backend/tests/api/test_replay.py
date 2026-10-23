"""Replay: rerun a stored run and say whether the same answer came back.

Verdicts other than "identical" are shown with controlled records: a real record whose
stored summary is nudged by a known amount inside or outside its declared tolerance.
"""

from __future__ import annotations

import base64
import fnmatch
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.api.registry import ENTRIES, get_entry
from simforge.persistence.experiments import ExperimentRecord, ExperimentRepository
from tests.api.test_registry import CASES, UPLOAD

SOLOW = "/api/v1/economy/solow/simulate"


def replay_url(run_id: str) -> str:
    return f"/api/v1/experiments/{run_id}/replay"


def run_and_record(client: TestClient, url: str, body: dict[str, Any]) -> dict[str, Any]:
    run = client.post(url, json={**body, "save_experiment": True}).json()
    record: dict[str, Any] = client.get(f"/api/v1/experiments/{run['metadata']['run_id']}").json()
    return record


def store_variant(client: TestClient, record: dict[str, Any], **changes: Any) -> str:
    """Store a copy of ``record`` with ``changes`` under a new run id (a controlled record)."""
    repo: ExperimentRepository = client.app.state.experiments  # type: ignore[attr-defined]
    run_id = str(uuid.uuid4())
    stored = {k: v for k, v in record.items() if k not in ("lab", "headline")}  # log-only
    repo.add(ExperimentRecord.model_validate({**stored, **changes, "run_id": run_id}))
    return run_id


# --- identical ----------------------------------------------------------------------------


@pytest.mark.parametrize(("model_id", "url", "body", "dataset"), CASES)
def test_every_model_replays_bit_identically_here(
    client: TestClient, model_id: str, url: str, body: dict[str, Any], dataset: bytes | None
) -> None:
    record = run_and_record(client, url, body)
    payload = {"dataset": {"content_base64": base64.b64encode(dataset).decode()}} if dataset else {}
    r = client.post(replay_url(record["run_id"]), json=payload)
    assert r.status_code == 200, r.text
    replay = r.json()
    assert replay["verdict"] == "identical"
    assert replay["basis"] == "output_digest"
    assert replay["replay_output_digest"] == record["output_digest"]
    assert replay["environment_matches"] is True
    assert replay["environment_differences"] == []
    assert replay["metadata"]["experiment_saved"] is False


def test_a_v1_record_is_compared_on_its_summary_only(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    v1 = store_variant(client, record, record_version=1, output_digest=None)
    replay = client.post(replay_url(v1), json={}).json()
    assert replay["verdict"] == "identical"
    assert replay["basis"] == "summary_only"
    assert "summary" in replay["explanation"]


# --- within tolerance and differs ---------------------------------------------------------


def test_a_tiny_difference_is_within_tolerance_and_named(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    summary = dict(record["summary"])
    # 1e-15 relative: about 5 ulp, far inside k*'s declared tolerance.
    summary["scenario_steady_state_capital"] *= 1 + 1e-15
    run_id = store_variant(client, record, summary=summary, output_digest="0" * 64)
    replay = client.post(replay_url(run_id), json={}).json()
    assert replay["verdict"] == "within_tolerance"
    assert replay["basis"] == "summary"
    largest = replay["largest_difference"]
    assert largest["field"] == "scenario_steady_state_capital"
    assert largest["within_tolerance"] is True
    assert largest["tolerance"]["reason"]


def test_a_difference_outside_tolerance_differs(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    summary = dict(record["summary"])
    summary["scenario_steady_state_capital"] *= 1 + 1e-6
    run_id = store_variant(client, record, summary=summary, output_digest="0" * 64)
    replay = client.post(replay_url(run_id), json={}).json()
    assert replay["verdict"] == "differs"
    assert replay["largest_difference"]["field"] == "scenario_steady_state_capital"
    assert replay["largest_difference"]["within_tolerance"] is False


def test_a_changed_count_differs_even_by_one(client: TestClient) -> None:
    record = run_and_record(client, *CASES[4][1:3])  # the bundled messy sample
    summary = {**record["summary"], "rows": record["summary"]["rows"] + 1}
    run_id = store_variant(client, record, summary=summary, output_digest="0" * 64)
    replay = client.post(replay_url(run_id), json={}).json()
    assert replay["verdict"] == "differs"
    assert replay["largest_difference"]["field"] == "rows"


def test_a_changed_summary_structure_differs(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    summary = {**record["summary"], "retired_field": 1.0}
    run_id = store_variant(client, record, summary=summary, output_digest=None, record_version=1)
    replay = client.post(replay_url(run_id), json={}).json()
    assert replay["verdict"] == "differs"
    assert "retired_field" in replay["explanation"]


def test_environment_differences_are_listed(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    env = {**record["environment"], "numpy_version": "1.0.0"}
    run_id = store_variant(client, record, environment=env)
    replay = client.post(replay_url(run_id), json={}).json()
    assert replay["verdict"] == "identical"
    assert replay["environment_matches"] is False
    (difference,) = replay["environment_differences"]
    assert difference["key"] == "numpy_version"
    assert difference["original"] == "1.0.0"


# --- saving a replay ----------------------------------------------------------------------


def test_a_saved_replay_is_a_new_record_linked_to_the_original(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    replay = client.post(replay_url(record["run_id"]), json={"save_experiment": True}).json()
    new_id = replay["metadata"]["run_id"]
    assert new_id != record["run_id"]
    saved = client.get(f"/api/v1/experiments/{new_id}").json()
    assert saved["replay_of"] == record["run_id"]
    assert saved["input_hash"] == record["input_hash"]
    assert client.get(f"/api/v1/experiments/{record['run_id']}").json() == record


# --- refusals -----------------------------------------------------------------------------


def test_unknown_run_is_404(client: TestClient) -> None:
    assert client.post(replay_url("no-such-run"), json={}).status_code == 404


def test_unknown_model_is_422(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    run_id = store_variant(client, record, model_id="economy.retired_model")
    r = client.post(replay_url(run_id), json={})
    assert r.status_code == 422
    assert "economy.retired_model" in r.json()["detail"]


def test_a_changed_model_version_is_refused_with_409(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    run_id = store_variant(client, record, model_version="0.9.0")
    r = client.post(replay_url(run_id), json={})
    assert r.status_code == 409
    assert "0.9.0" in r.json()["detail"]
    assert "1.0.0" in r.json()["detail"]


def test_stored_inputs_that_are_no_longer_valid_are_422(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    inputs = {**record["inputs"], "horizon_years": 9999}
    r = client.post(replay_url(store_variant(client, record, inputs=inputs)), json={})
    assert r.status_code == 422
    assert "no longer valid" in r.json()["detail"]


def test_a_domain_error_on_replay_is_422(client: TestClient) -> None:
    record = run_and_record(client, CASES[1][1], CASES[1][2])
    inputs = {**record["inputs"], "dt_values": [0.1, 0.000001]}  # far too many steps
    r = client.post(replay_url(store_variant(client, record, inputs=inputs)), json={})
    assert r.status_code == 422
    assert "limit" in r.json()["detail"]


def test_an_upload_replay_without_the_file_is_422(client: TestClient) -> None:
    record = run_and_record(client, CASES[5][1], CASES[5][2])
    r = client.post(replay_url(record["run_id"]), json={})
    assert r.status_code == 422
    assert "supply the same file" in r.json()["detail"]


def test_a_different_file_is_refused_before_it_is_read(client: TestClient) -> None:
    record = run_and_record(client, CASES[5][1], CASES[5][2])
    # Malformed CSV (a stray quote): if it were parsed, the error would be about the quote.
    wrong = b'a,b\n1,"x\n'
    r = client.post(
        replay_url(record["run_id"]),
        json={"dataset": {"content_base64": base64.b64encode(wrong).decode()}},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "SHA-256" in detail
    assert "quotation" not in detail


def test_a_file_for_a_model_that_takes_none_is_422(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    r = client.post(
        replay_url(record["run_id"]),
        json={"dataset": {"content_base64": base64.b64encode(UPLOAD).decode()}},
    )
    assert r.status_code == 422


def test_an_oversized_replay_body_is_413(client: TestClient) -> None:
    huge = "A" * (4 * 1024 * 1024)
    r = client.post(replay_url("any"), json={"dataset": {"content_base64": huge}})
    assert r.status_code == 413


# --- declared tolerances ------------------------------------------------------------------


def flat(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out |= flat(v, f"{prefix}{k}.")
        else:
            out[f"{prefix}{k}"] = v
    return out


@pytest.mark.parametrize(("model_id", "url", "body", "dataset"), CASES)
def test_every_stored_field_has_exactly_one_declared_tolerance_with_a_reason(
    client: TestClient, model_id: str, url: str, body: dict[str, Any], dataset: bytes | None
) -> None:
    record = run_and_record(client, url, body)
    entry = get_entry(model_id)
    assert entry is not None
    rules = entry.tolerances(record["inputs"], record["summary"])
    for field in flat(record["summary"]):
        matching = [p for p in rules if fnmatch.fnmatchcase(field, p)]
        assert len(matching) == 1, (field, matching)
        assert rules[matching[0]].reason


def test_every_model_declares_tolerances() -> None:
    assert all(entry.tolerances is not None for entry in ENTRIES)
