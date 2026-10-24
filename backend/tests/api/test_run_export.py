"""Exporting a stored run as versioned JSON (roadmap 1.6, decision D5).

The independent reference for the exported record is what ``GET /experiments/{id}`` returns
for the same run: the export must carry that record unchanged, adding only its envelope.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

LOG = "/api/v1/experiments"
SOLOW = "/api/v1/economy/solow/simulate"


def export_url(run_id: str) -> str:
    return f"{LOG}/{run_id}/export"


def saved_run(client: TestClient) -> dict[str, Any]:
    run = client.post(SOLOW, json={"save_experiment": True}).json()
    record: dict[str, Any] = client.get(f"{LOG}/{run['metadata']['run_id']}").json()
    return record


def test_the_export_wraps_the_logged_record_unchanged(client: TestClient) -> None:
    record = saved_run(client)
    r = client.get(export_url(record["run_id"]))
    assert r.status_code == 200, r.text
    out = r.json()
    assert set(out) == {"export_version", "exported_at", "record"}
    assert out["export_version"] == 1
    assert out["record"] == client.get(f"{LOG}/{record['run_id']}").json()


def test_exported_at_is_a_utc_time_of_the_request(client: TestClient) -> None:
    run_id = saved_run(client)["run_id"]
    before = datetime.now(UTC)
    exported = client.get(export_url(run_id)).json()["exported_at"]
    after = datetime.now(UTC)
    when = datetime.fromisoformat(exported)
    assert when.utcoffset() is not None, "exported_at must be timezone-aware"
    assert when.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
    assert before <= when <= after


def test_an_unknown_run_cannot_be_exported(client: TestClient) -> None:
    r = client.get(export_url("no-such-run"))
    assert r.status_code == 404
    assert "no-such-run" in r.json()["detail"]


def test_the_download_filename_never_contains_a_label(client: TestClient) -> None:
    record = saved_run(client)
    run_id = record["run_id"]
    patched = client.patch(f"{LOG}/{run_id}", json={"name": '=evil"; x', "note": "secret note"})
    assert patched.status_code == 200
    r = client.get(export_url(run_id))
    assert r.status_code == 200
    disposition = r.headers["content-disposition"]
    expected = f"{record['model_id']}_{run_id[:8]}.json"
    assert disposition == f'attachment; filename="{expected}"'
    assert re.fullmatch(r"[A-Za-z0-9._-]+", expected)
    for label in ("evil", "secret"):
        assert label not in disposition
    # The labels are still part of the exported record itself.
    assert (r.json()["record"]["name"], r.json()["record"]["note"]) == ('=evil"; x', "secret note")
