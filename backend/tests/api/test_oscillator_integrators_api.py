"""Seam 5 for the oscillator methods study over HTTP (roadmap 2.4, slice 2; plan D8, D14).

Written test-first: the route and ``simforge.physics.oscillator.integrator_model`` do not
exist yet, so the caps are read inside the tests that need them.

API contract the builder implements:

``POST /api/v1/physics/oscillator/integrators`` (in ``api/routes/oscillator.py``, beside
``/oscillator/simulate``), request ``OscillatorIntegratorRequest`` and response
``OscillatorIntegratorResponse`` (``physics/oscillator/integrator_schemas.py``; the request
fields are documented in ``tests/physics/test_oscillator_integrators.py``). Response fields:
model (id "physics.oscillator.integrators", version "1.0.0"), parameters, dt_values, methods,
energy_dt, periods, units, assumptions, angular_frequency (rad/s), period (s),
amplitude_scale (m), fit_rule, results, energy, checks, metadata. ``results[i]``: method,
theoretical_order, runs (with max_scaled_error, in_fit), fit; ``energy[i]``: method, h, theta,
n_steps, diverged, diverged_at_step, n_completed, final_energy_ratio,
max_relative_energy_error, energy_bound, modified_energy_residual, envelope (t_start, t_end,
lo, hi). The stored inputs (hashed) are exactly parameters, dt_values, methods, energy_dt and
periods (plan D14). The summary's field names are the builder's choice (fitted orders, final
energy errors), each with a replay tolerance rule.

Refusals (422, saying what to change): non-finite numbers anywhere; x0 = v0 = 0; duplicate
dt_values or methods; periods outside 1-1000; steps <= 0; and the two step caps of
``integrator_model`` (``MAX_STEPS_PER_RUN``, ``MAX_TOTAL_STEPS``, measured in this slice),
whose messages give the needed count N and the limit as plain integers (as the projectile
study does). Per-run N = ceil(T / dt (1 - 1e-12)) for the order runs (one period T) and
ceil(periods T / energy_dt (1 - 1e-12)) for the long run; the per-run message names the
largest of these; the total is len(methods) x (sum of the order runs' N + the long run's N).
"""

from __future__ import annotations

import importlib
import json
import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/physics/oscillator/integrators"
PERIOD = 2 * math.pi / 5.0  # default m = 1 kg, k = 25 N/m: w = 5 rad/s


def strict(text: str) -> Any:
    return json.loads(text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def steps(horizon: float, dt: float) -> int:
    return max(1, math.ceil(horizon / dt * (1.0 - 1e-12)))


def caps() -> tuple[int, int]:
    model = importlib.import_module("simforge.physics.oscillator.integrator_model")
    return model.MAX_STEPS_PER_RUN, model.MAX_TOTAL_STEPS


def test_default_request_returns_the_full_response(client: TestClient) -> None:
    r = client.post(URL, json={})
    assert r.status_code == 200
    body = strict(r.text)
    assert body["model"]["id"] == "physics.oscillator.integrators"
    assert body["model"]["version"] == "1.0.0"
    assert {
        "parameters",
        "dt_values",
        "methods",
        "energy_dt",
        "periods",
        "units",
        "assumptions",
        "angular_frequency",
        "period",
        "amplitude_scale",
        "fit_rule",
        "results",
        "energy",
        "checks",
        "metadata",
    } <= body.keys()
    assert body["parameters"] == {
        "mass": 1.0,
        "spring_constant": 25.0,
        "initial_displacement": 0.1,
        "initial_velocity": 0.0,
    }
    assert body["dt_values"] == [0.04 / 2**i for i in range(8)]
    assert body["methods"] == ["euler", "rk4", "symplectic_euler", "velocity_verlet"]
    assert body["energy_dt"] == 0.05
    assert body["periods"] == 200
    assert [m["method"] for m in body["results"]] == body["methods"]
    assert [e["method"] for e in body["energy"]] == body["methods"]
    for e in body["energy"]:
        assert {"t_start", "t_end", "lo", "hi"} <= e["envelope"].keys()
    assert all(c["passed"] is not False for c in body["checks"])


def test_study_is_saved_with_its_hashed_inputs(client: TestClient) -> None:
    body = client.post(URL, json={"methods": ["velocity_verlet"], "periods": 5}).json()
    record = client.get(f"/api/v1/experiments/{body['metadata']['run_id']}").json()
    assert record["model_id"] == "physics.oscillator.integrators"
    assert set(record["inputs"]) == {"parameters", "dt_values", "methods", "energy_dt", "periods"}


def test_diverged_run_gives_strict_json(client: TestClient) -> None:
    payload = {"methods": ["euler"], "periods": 1000, "save_experiment": False}
    r = client.post(URL, json=payload)
    assert r.status_code == 200
    e = strict(r.text)["energy"][0]
    assert e["diverged"] is True
    assert e["final_energy_ratio"] is None
    assert isinstance(e["diverged_at_step"], int)


@pytest.mark.parametrize(
    "content",
    [
        '{"parameters": {"initial_displacement": NaN}}',
        '{"parameters": {"mass": Infinity}}',
        '{"parameters": {"initial_velocity": -Infinity}}',
        '{"dt_values": [0.04, NaN]}',
        '{"dt_values": [0.04, Infinity]}',
        '{"energy_dt": NaN}',
        '{"energy_dt": -Infinity}',
    ],
)
def test_non_finite_values_are_refused(client: TestClient, content: str) -> None:
    r = client.post(URL, content=content, headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    strict(r.text)


def test_nothing_moving_is_refused(client: TestClient) -> None:
    r = client.post(
        URL, json={"parameters": {"initial_displacement": 0.0, "initial_velocity": 0.0}}
    )
    assert r.status_code == 422
    assert "initial_displacement" in r.text
    assert "initial_velocity" in r.text


@pytest.mark.parametrize(
    "payload",
    [
        {"dt_values": [0.04, 0.04]},
        {"methods": ["rk4", "rk4"]},
        {"methods": []},
        {"methods": ["leapfrog"]},
        {"dt_values": [0.04]},
        {"dt_values": [0.04 / 2**i for i in range(13)]},
        {"dt_values": [0.04, 0.0]},
        {"dt_values": [0.04, -0.01]},
        {"energy_dt": 0.0},
        {"periods": 0},
        {"periods": 1001},
        {"periods": 2.5},
        {"parameters": {"spring_constant": 1e9, "mass": 1e-3}},  # w = 1e6 rad/s > 1e4
        {"parameters": {"damping_coefficient": 0.1}},  # undamped study: no such field
        {"tolerance": 1e-6},
    ],
)
def test_invalid_requests_are_refused(client: TestClient, payload: dict[str, Any]) -> None:
    r = client.post(URL, json=payload)
    assert r.status_code == 422
    strict(r.text)


def test_duplicate_steps_refusal_says_so(client: TestClient) -> None:
    r = client.post(URL, json={"dt_values": [0.04, 0.02, 0.04]})
    assert r.status_code == 422
    assert "duplicate" in r.text


def test_order_run_step_cap_names_n(client: TestClient) -> None:
    per_run, _ = caps()
    dt = 1e-6
    n = steps(PERIOD, dt)  # 1256638: T/dt = 1256637.06, far from an integer
    assert n > per_run
    r = client.post(URL, json={"dt_values": [0.04, dt]})
    assert r.status_code == 422
    assert str(n) in r.text
    assert str(per_run) in r.text


def test_long_run_step_cap_names_n(client: TestClient) -> None:
    per_run, _ = caps()
    energy_dt = 1e-5
    n = steps(200 * PERIOD, energy_dt)  # 25132741.2...: far from an integer
    assert n > per_run
    r = client.post(URL, json={"energy_dt": energy_dt})
    assert r.status_code == 422
    assert str(n) in r.text
    assert str(per_run) in r.text


def test_total_step_cap_names_n(client: TestClient) -> None:
    """Twelve order runs of per_run - i steps each (dt = T/(per_run - i - 0.5), so T/dt sits
    half a step from an integer) are each allowed, but together exceed any total cap below
    48 x per_run."""
    per_run, total_cap = caps()
    dts = [PERIOD / (per_run - i - 0.5) for i in range(12)]
    n_energy = steps(PERIOD, 0.05)  # periods = 1: T/0.05 = 25.13, so 26
    total = 4 * (sum(per_run - i for i in range(12)) + n_energy)
    assert total > total_cap, "MAX_TOTAL_STEPS must stay below 48 x MAX_STEPS_PER_RUN"
    r = client.post(URL, json={"dt_values": dts, "periods": 1})
    assert r.status_code == 422
    assert str(total) in r.text
    assert str(total_cap) in r.text


def test_existing_oscillator_endpoint_unaffected(client: TestClient) -> None:
    r = client.post("/api/v1/physics/oscillator/simulate", json={})
    assert r.status_code == 200
    assert r.json()["model"]["id"] == "physics.oscillator"
