from __future__ import annotations

import json
import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/physics/projectile/angle-sweep"
G = 9.80665


def strict(text: str) -> Any:
    return json.loads(text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def test_vacuum_sweep_finds_45_degrees_and_v_squared_over_g(client: TestClient) -> None:
    r = client.post(URL, json={"parameters": {"initial_speed": 10.0, "drag_coefficient": 0.0}})
    assert r.status_code == 200
    body = strict(r.text)
    assert body["model"]["id"] == "physics.projectile.angle_sweep"
    assert len(body["angles_deg"]) == len(body["ranges"]) == 91
    assert body["angles_deg"][0] == 0.0
    assert body["angles_deg"][-1] == 90.0
    assert body["best_angle_deg"] == pytest.approx(45.0, abs=1e-6)
    assert body["best_range"] == pytest.approx(100.0 / G, rel=1e-12)
    assert body["vacuum_best_angle_deg"] == pytest.approx(45.0, abs=1e-12)


def test_drag_sweep_reports_lower_angle_than_vacuum(client: TestClient) -> None:
    body = client.post(URL, json={"parameters": {"drag_coefficient": 1.0}}).json()
    assert body["best_angle_deg"] < body["vacuum_best_angle_deg"]
    assert body["best_range"] < body["vacuum_best_range"]
    assert body["best_range"] >= max(body["ranges"])


def test_launch_angle_does_not_affect_result_or_hash(client: TestClient) -> None:
    def run(angle: float) -> Any:
        payload = {"parameters": {"launch_angle_deg": angle}, "save_experiment": False}
        return client.post(URL, json=payload).json()

    a, b = run(10.0), run(70.0)
    assert a["ranges"] == b["ranges"]
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]


def test_sweep_is_saved_to_experiment_log(client: TestClient) -> None:
    body = client.post(URL, json={"n_angles": 31}).json()
    record = client.get(f"/api/v1/experiments/{body['metadata']['run_id']}").json()
    assert record["model_id"] == "physics.projectile.angle_sweep"
    assert record["inputs"]["n_angles"] == 31
    assert "launch_angle_deg" not in record["inputs"]["parameters"]
    assert math.isclose(record["summary"]["best_range"], body["best_range"])


@pytest.mark.parametrize(
    "payload",
    [
        {"n_angles": 9},
        {"n_angles": 362},
        {"n_angles": 45.5},
        {"parameters": {"mass": 0}},
        {"parameters": {"drag_coefficient": -1}},
        {"angles": [10, 20]},
    ],
)
def test_invalid_requests_are_rejected(client: TestClient, payload: dict[str, Any]) -> None:
    r = client.post(URL, json=payload)
    assert r.status_code == 422
    strict(r.text)


def test_non_finite_input_is_rejected(client: TestClient) -> None:
    r = client.post(
        URL,
        content='{"parameters": {"initial_speed": NaN}}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
    strict(r.text)
