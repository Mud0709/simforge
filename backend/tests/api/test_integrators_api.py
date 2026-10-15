from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/physics/projectile/integrators"


def strict(text: str) -> Any:
    return json.loads(text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def test_default_study_returns_fitted_orders(client: TestClient) -> None:
    r = client.post(URL, json={})
    assert r.status_code == 200
    body = strict(r.text)
    assert body["model"]["id"] == "physics.projectile.integrators"
    assert body["parameters"]["drag_coefficient"] == 1.0
    by_method = {m["method"]: m for m in body["results"]}
    for method, order in [("euler", 1), ("rk4", 4), ("verlet", 2)]:
        m = by_method[method]
        assert m["position_fit"]["order"] == pytest.approx(order, abs=0.1)
        assert m["position_reference"]["order"] == order
        assert len(m["runs"]) == 8
        assert m["trajectory"] is not None
    assert {a["id"] for a in body["assumptions"]} >= {"fixed_horizon", "linear_invariant"}
    assert "fixed before any results" in body["fit_rule"]["description"]


def test_study_is_saved_to_experiment_log(client: TestClient) -> None:
    body = client.post(
        URL, json={"methods": ["rk4"], "dt_values": [0.1, 0.05, 0.025, 0.0125]}
    ).json()
    record = client.get(f"/api/v1/experiments/{body['metadata']['run_id']}").json()
    assert record["model_id"] == "physics.projectile.integrators"
    assert record["inputs"]["methods"] == ["rk4"]
    assert record["summary"]["methods"]["rk4"]["theoretical_order"] == 4


def test_divergent_runs_produce_strict_json(client: TestClient) -> None:
    payload = {
        # v_t = g/k = 0.2 m/s, so the fall from 100 m lasts ~500 s: ~2500 Euler steps at
        # kh = 10 (|R| = 9), far more than needed to pass the divergence threshold.
        "parameters": {"drag_coefficient": 50.0, "launch_height": 100.0},
        "dt_values": [0.2, 0.1],
        "methods": ["euler"],
        "save_experiment": False,
    }
    r = client.post(URL, json=payload)
    assert r.status_code == 200
    run = strict(r.text)["results"][0]["runs"][0]
    assert run["diverged"] is True
    assert run["max_position_error"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"parameters": {"drag_coefficient": 0.0}},
        {"dt_values": [0.1]},
        {"dt_values": [0.1, 0.0]},
        {"dt_values": [0.1, -0.05]},
        {"dt_values": [0.1, 0.1]},
        {"dt_values": [0.1 / 2**i for i in range(13)]},
        {"dt_values": [0.1, "small"]},
        {"methods": []},
        {"methods": ["leapfrog"]},
        {"methods": ["rk4", "rk4"]},
        {"tolerance": 1e-6},
    ],
)
def test_invalid_requests_are_rejected(client: TestClient, payload: dict[str, Any]) -> None:
    r = client.post(URL, json=payload)
    assert r.status_code == 422
    strict(r.text)


def test_vacuum_rejection_explains_why(client: TestClient) -> None:
    r = client.post(URL, json={"parameters": {"drag_coefficient": 0.0}})
    assert "no convergence order can be measured" in r.text


def test_non_finite_step_is_rejected(client: TestClient) -> None:
    r = client.post(
        URL, content='{"dt_values": [0.1, NaN]}', headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 422
    strict(r.text)


def test_excessive_step_count_is_refused_with_explanation(client: TestClient) -> None:
    r = client.post(URL, json={"dt_values": [0.1, 1e-6]})
    assert r.status_code == 422
    assert "limit is 50000 per run" in r.json()["detail"]


def test_existing_simulation_endpoint_unaffected(client: TestClient) -> None:
    r = client.post("/api/v1/physics/projectile/simulate", json={})
    assert r.status_code == 200
    assert r.json()["model"]["id"] == "physics.projectile"
