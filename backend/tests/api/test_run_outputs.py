"""Recomputing a stored run's outputs (roadmap 1.6, decisions D1 and D2).

The expected digest is always the one stored with the original run: an invariant recorded
before this route existed, never recomputed by the code under test. The refusals are the
same cases replay refuses, because both routes share one refusal helper.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.api.registry import get_entry
from tests.api.test_registry import CASES, UPLOAD
from tests.api.test_replay import SOLOW, replay_url, run_and_record, store_variant


def outputs_url(run_id: str) -> str:
    return f"/api/v1/experiments/{run_id}/outputs"


def file_payload(dataset: bytes) -> dict[str, Any]:
    return {"dataset": {"content_base64": base64.b64encode(dataset).decode()}}


def without(data: dict[str, Any], exclude: dict[str, Any]) -> dict[str, Any]:
    """``data`` minus the nested keys marked True in ``exclude`` (Pydantic's exclude shape)."""
    out = dict(data)
    for key, rule in exclude.items():
        if rule is True:
            out.pop(key, None)
        elif key in out:
            out[key] = without(out[key], rule)
    return out


def sha256_of_canonical_json(data: Any) -> str:
    """Written here from the definition in ARCHITECTURE decision 5 (sorted keys, no spaces,
    finite floats), not imported, so the check does not rely on the code it checks."""
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def log_size(client: TestClient) -> int:
    return len(client.get("/api/v1/experiments", params={"limit": 500}).json())


# --- the same answer comes back -----------------------------------------------------------


@pytest.mark.parametrize(("model_id", "url", "body", "dataset"), CASES)
def test_every_model_recomputes_to_the_stored_digest(
    client: TestClient, model_id: str, url: str, body: dict[str, Any], dataset: bytes | None
) -> None:
    record = run_and_record(client, url, body)
    r = client.post(outputs_url(record["run_id"]), json=file_payload(dataset) if dataset else {})
    assert r.status_code == 200, r.text
    out = r.json()
    assert set(out) == {"original_run_id", "digest_match", "response"}
    assert out["original_run_id"] == record["run_id"]
    assert out["digest_match"] is True

    response = out["response"]
    assert response["model"]["id"] == model_id
    assert response["metadata"]["output_digest"] == record["output_digest"]
    assert response["metadata"]["experiment_saved"] is False
    # The response that arrived (after serialisation) is itself the bit-identical answer:
    # hashing what was received gives the digest stored with the original run.
    entry = get_entry(model_id)
    assert entry is not None
    exclude = {"metadata": True, **(entry.digest_exclude or {})}
    assert sha256_of_canonical_json(without(response, exclude)) == record["output_digest"]


def test_a_stored_digest_that_differs_is_reported_not_hidden(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    run_id = store_variant(client, record, output_digest="0" * 64)
    r = client.post(outputs_url(run_id), json={})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["digest_match"] is False
    assert out["response"]["metadata"]["output_digest"] == record["output_digest"]


def test_a_v1_record_without_a_digest_cannot_be_checked(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    v1 = store_variant(client, record, record_version=1, output_digest=None)
    r = client.post(outputs_url(v1), json={})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["digest_match"] is None  # unknown, not "differs"
    assert out["response"]["metadata"]["output_digest"] == record["output_digest"]


# --- nothing is saved ---------------------------------------------------------------------


@pytest.mark.parametrize(("model_id", "url", "body", "dataset"), CASES)
def test_recomputing_saves_nothing(
    client: TestClient, model_id: str, url: str, body: dict[str, Any], dataset: bytes | None
) -> None:
    record = run_and_record(client, url, body)
    before = log_size(client)
    r = client.post(outputs_url(record["run_id"]), json=file_payload(dataset) if dataset else {})
    assert r.status_code == 200, r.text
    assert log_size(client) == before
    assert (
        client.get(f"/api/v1/experiments/{r.json()['response']['metadata']['run_id']}").status_code
        == 404
    )
    assert client.get(f"/api/v1/experiments/{record['run_id']}").json() == record


def test_a_request_to_save_is_refused_by_the_schema(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    r = client.post(outputs_url(record["run_id"]), json={"save_experiment": True})
    assert r.status_code == 422


# --- refusals: exactly replay's -----------------------------------------------------------


def test_unknown_run_is_404(client: TestClient) -> None:
    r = client.post(outputs_url("no-such-run"), json={})
    assert r.status_code == 404
    assert "no-such-run" in r.json()["detail"]  # the run is unknown, not the route


def test_unknown_model_is_422(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    run_id = store_variant(client, record, model_id="economy.retired_model")
    r = client.post(outputs_url(run_id), json={})
    assert r.status_code == 422
    assert "economy.retired_model" in r.json()["detail"]


def test_a_changed_model_version_is_refused_with_409(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    before = log_size(client)
    run_id = store_variant(client, record, model_version="0.9.0")
    r = client.post(outputs_url(run_id), json={})
    assert r.status_code == 409
    assert "0.9.0" in r.json()["detail"]
    assert "1.0.0" in r.json()["detail"]
    assert log_size(client) == before + 1  # only the controlled record


def test_stored_inputs_that_are_no_longer_valid_are_422(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    inputs = {**record["inputs"], "horizon_years": 9999}
    r = client.post(outputs_url(store_variant(client, record, inputs=inputs)), json={})
    assert r.status_code == 422
    assert "no longer valid" in r.json()["detail"]


def test_an_upload_without_the_file_is_422(client: TestClient) -> None:
    record = run_and_record(client, CASES[5][1], CASES[5][2])
    r = client.post(outputs_url(record["run_id"]), json={})
    assert r.status_code == 422
    assert "supply the same file" in r.json()["detail"]


def test_a_different_file_is_refused_before_it_is_read(client: TestClient) -> None:
    record = run_and_record(client, CASES[5][1], CASES[5][2])
    # Malformed CSV (a stray quote): if it were parsed, the error would be about the quote.
    r = client.post(outputs_url(record["run_id"]), json=file_payload(b'a,b\n1,"x\n'))
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "SHA-256" in detail
    assert "quotation" not in detail


def test_a_file_for_a_model_that_takes_none_is_422(client: TestClient) -> None:
    record = run_and_record(client, SOLOW, {})
    r = client.post(outputs_url(record["run_id"]), json=file_payload(UPLOAD))
    assert r.status_code == 422


def test_a_domain_error_is_422(client: TestClient) -> None:
    record = run_and_record(client, CASES[1][1], CASES[1][2])
    inputs = {**record["inputs"], "dt_values": [0.1, 0.000001]}  # far too many steps
    r = client.post(outputs_url(store_variant(client, record, inputs=inputs)), json={})
    assert r.status_code == 422
    assert "limit" in r.json()["detail"]


def test_a_file_that_is_not_base64_is_422(client: TestClient) -> None:
    record = run_and_record(client, CASES[5][1], CASES[5][2])
    r = client.post(outputs_url(record["run_id"]), json={"dataset": {"content_base64": "@@@"}})
    assert r.status_code == 422
    assert "base64" in r.json()["detail"]


def test_replay_and_outputs_refuse_with_the_same_status_and_message(client: TestClient) -> None:
    solow = run_and_record(client, SOLOW, {})
    upload = run_and_record(client, CASES[5][1], CASES[5][2])
    refused = [
        (store_variant(client, solow, model_id="economy.retired_model"), {}),
        (store_variant(client, solow, model_version="0.9.0"), {}),
        (upload["run_id"], {}),
        (upload["run_id"], file_payload(b"a,b\n1,2\n")),
        (solow["run_id"], file_payload(UPLOAD)),
    ]
    for run_id, body in refused:
        a = client.post(replay_url(run_id), json=body)
        b = client.post(outputs_url(run_id), json=body)
        assert a.status_code in (409, 422), a.text
        assert (a.status_code, a.json()) == (b.status_code, b.json())


def test_an_oversized_body_is_413(client: TestClient) -> None:
    huge = "A" * (4 * 1024 * 1024)
    r = client.post(outputs_url("any"), json={"dataset": {"content_base64": huge}})
    assert r.status_code == 413
