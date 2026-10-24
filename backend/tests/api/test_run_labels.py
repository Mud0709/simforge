"""Naming and annotating runs: labels change, scientific records never do."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

LOG = "/api/v1/experiments"


def saved_run(client: TestClient) -> dict[str, Any]:
    run = client.post("/api/v1/economy/solow/simulate", json={}).json()
    record: dict[str, Any] = client.get(f"{LOG}/{run['metadata']['run_id']}").json()
    return record


def test_a_run_can_be_named_and_annotated(client: TestClient) -> None:
    record = saved_run(client)
    assert (record["name"], record["note"]) == (None, None)
    r = client.patch(
        f"{LOG}/{record['run_id']}",
        json={"name": "Golden rule", "note": "s1 = \N{GREEK SMALL LETTER ALPHA}"},
    )
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["note"]) == (
        "Golden rule",
        "s1 = \N{GREEK SMALL LETTER ALPHA}",
    )
    again = client.get(f"{LOG}/{record['run_id']}").json()
    assert again == r.json()
    unlabelled = {k: v for k, v in again.items() if k not in ("name", "note")}
    assert unlabelled == {k: v for k, v in record.items() if k not in ("name", "note")}


def test_an_omitted_label_is_kept_and_an_empty_one_cleared(client: TestClient) -> None:
    run_id = saved_run(client)["run_id"]
    client.patch(f"{LOG}/{run_id}", json={"name": "A", "note": "B"})
    assert client.patch(f"{LOG}/{run_id}", json={"note": "C"}).json()["name"] == "A"
    cleared = client.patch(f"{LOG}/{run_id}", json={"name": "", "note": None}).json()
    assert (cleared["name"], cleared["note"]) == (None, None)


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x" * 81},
        {"note": "x" * 2001},
        {"summary": {"final_capital": 1.0}},  # results can never be edited
        {"model_version": "2.0.0"},
    ],
)
def test_long_labels_and_scientific_fields_are_refused(
    client: TestClient, body: dict[str, Any]
) -> None:
    record = saved_run(client)
    assert client.patch(f"{LOG}/{record['run_id']}", json=body).status_code == 422
    assert client.get(f"{LOG}/{record['run_id']}").json() == record


def test_labelling_an_unknown_run_is_404(client: TestClient) -> None:
    assert client.patch(f"{LOG}/no-such-run", json={"name": "x"}).status_code == 404
