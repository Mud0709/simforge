from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/economy/solow/simulate"


def strict(text: str) -> Any:
    return json.loads(text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def test_default_run_has_consistent_shapes_and_passing_checks(client: TestClient) -> None:
    r = client.post(URL, json={})
    assert r.status_code == 200
    body = strict(r.text)
    assert body["model"]["id"] == "economy.solow"
    assert body["model"]["version"] == "1.0.0"
    h = body["horizon_years"]
    assert body["years"] == list(range(h + 1))
    for scenario in ("baseline", "scenario"):
        path = body[scenario]
        for key in ("savings_rate", "capital", "output", "consumption", "investment"):
            assert len(path[key]) == h + 1
        assert len(path["output_per_worker_growth"]) == h
        assert path["output_per_worker_index"][0] == 100.0
    assert {c["id"] for c in body["checks"]} >= {
        "steady_state_residual_baseline",
        "identical_before_policy",
    }
    assert all(c["passed"] is not False for c in body["checks"])
    assert {a["id"] for a in body["assumptions"]} >= {"annual_timing", "cobb_douglas"}


def test_steady_states_and_golden_rule_match_formulas(client: TestClient) -> None:
    p = {
        "capital_share": 0.35,
        "savings_rate": 0.2,
        "depreciation": 0.06,
        "population_growth": 0.01,
        "technology_growth": 0.02,
    }
    body = client.post(URL, json={"parameters": p, "policy": {"new_savings_rate": 0.25}}).json()
    lam = 0.01 + 0.02 + 0.01 * 0.02 + 0.06
    for key, s in (("baseline_steady_state", 0.2), ("scenario_steady_state", 0.25)):
        ss = body[key]
        assert ss["capital"] == pytest.approx((s / lam) ** (1 / 0.65), rel=1e-14)
        assert ss["consumption"] == pytest.approx((1 - s) * ss["output"], rel=1e-15)
        assert ss["capital_output_ratio"] == pytest.approx(s / lam, rel=1e-15)
    assert body["golden_rule"]["savings_rate"] == 0.35
    conv = body["convergence"]
    assert conv["effective_depreciation"] == pytest.approx(lam, rel=1e-15)
    assert conv["one_minus_rho"] == pytest.approx(0.65 * lam / (1.01 * 1.02), rel=1e-14)


def test_policy_year_timing_in_the_response(client: TestClient) -> None:
    body = client.post(
        URL, json={"policy": {"new_savings_rate": 0.3, "policy_year": 5}, "horizon_years": 30}
    ).json()
    base, scen = body["baseline"], body["scenario"]
    assert scen["savings_rate"][4] == 0.2
    assert scen["savings_rate"][5] == 0.3
    assert scen["capital"][:6] == base["capital"][:6]
    assert scen["consumption"][:5] == base["consumption"][:5]
    assert scen["consumption"][5] < base["consumption"][5]  # saving more cuts consumption now
    assert scen["capital"][6] > base["capital"][6]


def test_run_is_saved_with_hashed_inputs(client: TestClient) -> None:
    payload = {"horizon_years": 40}
    a = client.post(URL, json=payload).json()
    b = client.post(URL, json={**payload, "save_experiment": False}).json()
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]
    record = client.get(f"/api/v1/experiments/{a['metadata']['run_id']}").json()
    assert record["model_id"] == "economy.solow"
    assert set(record["inputs"]) == {"parameters", "policy", "horizon_years"}
    assert record["summary"]["half_life_years"] == pytest.approx(
        a["convergence"]["half_life_years"]
    )
    assert client.get(f"/api/v1/experiments/{b['metadata']['run_id']}").status_code == 404
    c = client.post(URL, json={"horizon_years": 41, "save_experiment": False}).json()
    assert c["metadata"]["input_hash"] != a["metadata"]["input_hash"]


def test_largest_and_smallest_scales_stay_finite(client: TestClient) -> None:
    """Corners of the input box: k* near 1e60 and near 1e-42. lambda is exactly the
    1e-3 bound for the first case, so this also checks the bound is inclusive."""
    big = {
        "capital_share": 0.95,
        "savings_rate": 0.99,
        "depreciation": 0.051,
        "population_growth": -0.05,
        "technology_growth": 0.0,
        "initial_capital_ratio": 10,
    }
    small = {
        "capital_share": 0.95,
        "savings_rate": 0.01,
        "depreciation": 1.0,
        "population_growth": 0.1,
        "technology_growth": 0.1,
        "initial_capital_ratio": 0.01,
    }
    for p in (big, small):
        for s1 in (0.01, 0.99):
            payload = {"parameters": p, "policy": {"new_savings_rate": s1}, "horizon_years": 500}
            r = client.post(URL, json={**payload, "save_experiment": False})
            assert r.status_code == 200, r.text
            strict(r.text)


def test_info_endpoint(client: TestClient) -> None:
    assert client.get("/api/v1/economy/solow/info").json()["id"] == "economy.solow"


@pytest.mark.parametrize(
    "payload",
    [
        {"parameters": {"capital_share": 1.0}},
        {"parameters": {"capital_share": 0.0}},
        {"parameters": {"savings_rate": 0.0}},
        {"parameters": {"savings_rate": 1.0}},
        {"parameters": {"depreciation": -0.01}},
        {"parameters": {"population_growth": 0.2}},
        {"parameters": {"technology_growth": -0.01}},
        {"parameters": {"initial_capital_ratio": 0.0}},
        {"parameters": {"initial_capital_ratio": 11}},
        # lambda = n + g + n g + delta = 0: no steady state.
        {
            "parameters": {
                "population_growth": -0.05,
                "technology_growth": 0.0,
                "depreciation": 0.05,
            }
        },
        {"policy": {"new_savings_rate": 1.5}},
        {"policy": {"policy_year": -1}},
        {"policy": {"policy_year": 100}},  # = default horizon: change would be invisible
        {"horizon_years": 0},
        {"horizon_years": 501},
        {"horizon_years": 10.5},
        {"unknown": 1},
        {"parameters": {"alpha": 0.3}},
        {"policy": {"year": 3}},
    ],
)
def test_invalid_payloads_are_rejected(client: TestClient, payload: dict[str, Any]) -> None:
    r = client.post(URL, json=payload)
    assert r.status_code == 422, payload
    strict(r.text)


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(client: TestClient, literal: str) -> None:
    body = f'{{"parameters": {{"savings_rate": {literal}}}}}'
    r = client.post(URL, content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    strict(r.text)


def test_lambda_error_message_explains_the_problem(client: TestClient) -> None:
    payload = {
        "parameters": {"population_growth": -0.05, "technology_growth": 0.0, "depreciation": 0.05}
    }
    detail = client.post(URL, json=payload).json()["detail"][0]["msg"]
    assert "steady state" in detail
