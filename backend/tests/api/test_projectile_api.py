from __future__ import annotations

import json
import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/physics/projectile/simulate"


def post_raw(client: TestClient, body: str) -> Any:
    return client.post(URL, content=body, headers={"Content-Type": "application/json"})


def test_default_request_returns_complete_result(client: TestClient) -> None:
    r = client.post(URL, json={})
    assert r.status_code == 200
    body = r.json()
    assert body["model"]["id"] == "physics.projectile"
    assert body["units"]["range"] == "m"
    assert {a["id"] for a in body["assumptions"]} >= {"point_mass", "linear_drag"}
    assert body["comparison"]["max_position_error"] < 1e-7
    assert len(body["series"]["t"]) == 400
    assert body["metadata"]["experiment_saved"] is True


def test_vacuum_range_through_api_matches_textbook(client: TestClient) -> None:
    params = {"initial_speed": 10.0, "launch_angle_deg": 30.0, "drag_coefficient": 0.0}
    body = client.post(URL, json={"parameters": params}).json()
    expected = 10.0**2 * math.sin(math.radians(60.0)) / 9.80665
    assert body["analytical"]["range"] == pytest.approx(expected, rel=1e-13)
    assert body["numerical"]["range"] == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(client: TestClient, literal: str) -> None:
    # Python's json parser accepts these non-standard literals, so this must be enforced.
    r = post_raw(client, f'{{"parameters": {{"initial_speed": {literal}}}}}')
    assert r.status_code == 422
    # The error body itself must be strict JSON (it echoes the rejected input).
    detail = json.loads(r.text, parse_constant=lambda c: pytest.fail(f"non-finite {c}"))
    assert detail["detail"][0]["loc"] == ["body", "parameters", "initial_speed"]


@pytest.mark.parametrize(
    "params",
    [
        {"mass": 0},
        {"mass": -1},
        {"initial_speed": 0},
        {"launch_angle_deg": 91},
        {"launch_angle_deg": -1},
        {"drag_coefficient": -0.1},
        {"gravity": 0},
        {"launch_angle_deg": 0, "launch_height": 0},
        {"initial_speed": "fast"},
        {"masss": 1.0},
    ],
)
def test_invalid_parameters_are_rejected(client: TestClient, params: dict[str, Any]) -> None:
    assert client.post(URL, json={"parameters": params}).status_code == 422


def test_invalid_solver_settings_are_rejected(client: TestClient) -> None:
    assert client.post(URL, json={"solver": {"method": "Euler"}}).status_code == 422
    assert client.post(URL, json={"solver": {"rtol": 0.5}}).status_code == 422
    assert client.post(URL, json={"n_samples": 1_000_000}).status_code == 422


def test_stiff_problem_returns_explanatory_422(client: TestClient) -> None:
    params = {"launch_height": 1e4, "drag_coefficient": 100.0, "mass": 0.1}
    r = client.post(URL, json={"parameters": params, "solver": {"method": "RK45"}})
    assert r.status_code == 422
    assert "Radau" in r.json()["detail"]


def test_identical_inputs_give_identical_hash_and_results(client: TestClient) -> None:
    payload = {"parameters": {"drag_coefficient": 0.3}, "save_experiment": False}
    a, b = client.post(URL, json=payload).json(), client.post(URL, json=payload).json()
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]
    assert a["metadata"]["run_id"] != b["metadata"]["run_id"]
    assert a["analytical"] == b["analytical"]
    assert a["numerical"] == b["numerical"]  # deterministic: bitwise-identical floats


def test_hash_ignores_save_flag_but_not_parameters(client: TestClient) -> None:
    def digest(payload: dict[str, Any]) -> str:
        return str(client.post(URL, json=payload).json()["metadata"]["input_hash"])

    assert digest({"save_experiment": False}) == digest({"save_experiment": True})
    assert digest({}) != digest({"parameters": {"mass": 2.0}})


def test_response_is_strict_json(client: TestClient) -> None:
    r = client.post(URL, json={})
    json.loads(r.text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))
