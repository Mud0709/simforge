"""Input limits of the resonance sweep (roadmap 2.5, slice 4; plan D6, D7, D11): a result or a
422 that says what to change, never a 500.

Each refusal below is worked by hand from the plan's rules: finite SI inputs, b > 0, F0 > 0,
underdamped (zeta = b / (2 sqrt(m k)) < 1), Q = sqrt(m k) / b <= 300, 0 < omega_min <
omega_max <= 1e4 rad/s, 3 <= n_frequencies <= MAX_N_FREQUENCIES, settle_tolerance in
[1e-12, 1e-2], DOP853 or RK45 only; every grid point within 2.3's MAX_CYCLES (500) before any
solve; and the work budget MAX_RESONANCE_SWEEP_RHS_EVALUATIONS, a server limit checked after
each run. The cap and the budget are measured in slice 4 (D11) and imported here.
"""

from __future__ import annotations

import json
import math
import re
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.physics.oscillator import model as oscillator_model
from simforge.physics.oscillator.resonance_sweep import (
    MAX_N_FREQUENCIES,
    MAX_RESONANCE_SWEEP_RHS_EVALUATIONS,
)

URL = "/api/v1/physics/oscillator/resonance-sweep"
# Plan check (3) of slice 4: the slowest request must answer within half of the 30 s Next.js
# proxy ceiling on the measuring machine, so that a machine 2x slower still answers in time.
SECONDS_PER_REQUEST = 15.0
BUDGET_MESSAGE = "right-hand-side evaluations"


def post(client: TestClient, params: dict[str, Any], **extra: Any) -> Any:
    return client.post(URL, json={"parameters": params, "save_experiment": False, **extra})


def post_raw(client: TestClient, body: str) -> Any:
    return client.post(URL, content=body, headers={"Content-Type": "application/json"})


def strict(text: str) -> Any:
    return json.loads(text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def detail_text(r: Any) -> str:
    detail = r.json()["detail"]
    return detail if isinstance(detail, str) else " ".join(d.get("msg", "") for d in detail)


def explained(r: Any) -> bool:
    """A 422 whose detail actually says something (a sentence, not just a status)."""
    return len(detail_text(r)) > 30


@pytest.fixture
def no_solve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any oscillator solve fails the test: the refusal must come before it."""

    def solved(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("a run was solved before the refusal")

    monkeypatch.setattr(oscillator_model, "run_with_solution", solved)
    monkeypatch.setattr(oscillator_model, "run", solved)


# --- the boundary: non-finite and out-of-range single fields --------------------------------

FIELDS = [
    "mass",
    "spring_constant",
    "damping_coefficient",
    "drive_amplitude",
    "omega_min",
    "omega_max",
    "settle_tolerance",
]


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(
    client: TestClient, no_solve: None, field: str, literal: str
) -> None:
    r = post_raw(client, f'{{"parameters": {{"{field}": {literal}}}}}')
    assert r.status_code == 422
    detail = strict(r.text)
    assert detail["detail"][0]["loc"] == ["body", "parameters", field]


@pytest.mark.parametrize(
    "body",
    ['{"solver": {"atol": NaN}}', '{"solver": {"rtol": Infinity}}', '{"n_frequencies": NaN}'],
)
def test_non_finite_settings_are_rejected(client: TestClient, no_solve: None, body: str) -> None:
    r = post_raw(client, body)
    assert r.status_code == 422
    strict(r.text)


@pytest.mark.parametrize(
    "payload",
    [
        {"parameters": {"damping_coefficient": 0.0}},  # undamped: no steady state to settle to
        {"parameters": {"damping_coefficient": -0.1}},
        {"parameters": {"drive_amplitude": 0.0}},  # undriven: no resonance curve
        {"parameters": {"drive_amplitude": -1.0}},
        {"parameters": {"mass": 0.0}},
        {"parameters": {"spring_constant": 0.0}},
        {"parameters": {"omega_min": 0.0}},
        {"parameters": {"omega_min": -1.0}},
        {"parameters": {"omega_min": 5.0, "omega_max": 5.0}},  # min = max
        {"parameters": {"omega_min": 6.0, "omega_max": 5.0}},  # min > max
        {"parameters": {"omega_max": 1.0001e4}},  # the 2.3 bound on w
        {"parameters": {"settle_tolerance": 1e-13}},
        {"parameters": {"settle_tolerance": 0.011}},
        {"n_frequencies": 2},
        {"n_frequencies": MAX_N_FREQUENCIES + 1},
        {"n_frequencies": 10.5},
        {"solver": {"method": "Radau"}},  # D6: an underdamped run is not stiff
        {"solver": {"method": "Euler"}},
        # Every run starts from rest at its own frequency (D6): no initial state, no single w.
        {"parameters": {"initial_displacement": 0.1}},
        {"parameters": {"drive_angular_frequency": 5.0}},
        {"parameters": {"duration": 10.0}},
        {"n_samples": 100},  # the sweep keeps no series
        # The work budget is the server's limit, not a request field (D11).
        {"max_rhs_evaluations": 10**9},
    ],
)
def test_invalid_requests_are_rejected_before_solving(
    client: TestClient, no_solve: None, payload: dict[str, Any]
) -> None:
    r = client.post(URL, json={"save_experiment": False, **payload})
    assert r.status_code == 422, r.text
    strict(r.text)


def test_radau_refusal_names_the_allowed_methods(client: TestClient, no_solve: None) -> None:
    r = post(client, {}, solver={"method": "Radau"})
    assert r.status_code == 422
    text = detail_text(r)
    assert "DOP853" in text
    assert "RK45" in text


@pytest.mark.parametrize(
    "b",
    [
        10.0,  # zeta = b / (2 sqrt(m k)) = 10 / (2 x 5) = 1: critically damped
        12.0,  # zeta = 1.2: overdamped
    ],
)
def test_not_underdamped_is_refused_saying_what_to_change(
    client: TestClient, no_solve: None, b: float
) -> None:
    # m = 1 kg, k = 25 N/m (the defaults): 2 sqrt(m k) = 10 kg/s.
    r = post(client, {"damping_coefficient": b})
    assert r.status_code == 422
    assert explained(r)
    assert "damping" in detail_text(r)


def test_quality_factor_above_300_is_refused_saying_what_to_change(
    client: TestClient, no_solve: None
) -> None:
    # m = k = 1: Q = sqrt(m k) / b = 1 / b; b = 1/301 kg/s gives Q = 301 > 300 (D6), while
    # zeta = 1/602 is underdamped and every other rule holds.
    params = {
        "mass": 1.0,
        "spring_constant": 1.0,
        "damping_coefficient": 1 / 301,
        "omega_min": 0.5,
        "omega_max": 1.5,
        "settle_tolerance": 1e-2,
    }
    r = post(client, params, n_frequencies=3)
    assert r.status_code == 422
    assert explained(r)
    text = detail_text(r)
    assert "300" in text
    assert "damping" in text


def test_a_grid_over_the_cycle_limit_is_refused_naming_the_worst_frequency(
    client: TestClient, no_solve: None
) -> None:
    # m = k = 1 (w0 = 1 rad/s), b = 0.2 kg/s (zeta = 0.1, gamma = 0.1 1/s), eps_s = 1e-6,
    # grid 1, 13, 25 rad/s. From rest R/A ~ 1 at w >> w0 (x_h(0) = -A cos delta, v_h(0) =
    # -A w sin delta with sin delta ~ 2 gamma / w), so the settle count is about
    # ln(2 / eps_s) / (gamma T) = 14.51 / (0.1 x 2 pi / w) drive periods: at 25 rad/s 578 + 2 =
    # 580 cycles > 500, at 13 rad/s 301 + 2 = 303 and at 1 rad/s 24 + 2 = 26, both admitted.
    params = {
        "mass": 1.0,
        "spring_constant": 1.0,
        "damping_coefficient": 0.2,
        "omega_min": 1.0,
        "omega_max": 25.0,
    }
    r = post(client, params, n_frequencies=3)
    assert r.status_code == 422
    text = detail_text(r)
    assert re.search(r"\b25(\.0+)? rad/s", text), text
    assert "500" in text
    assert "cycle" in text
    assert "settle_tolerance" in text  # says what to change
    # Narrowing the range below 25 rad/s removes the refusal (the solve is allowed here).


def test_the_same_grid_narrowed_is_admitted(client: TestClient) -> None:
    # The grid of the test above up to 13 rad/s: 303 cycles at the worst point (worked there).
    params = {
        "mass": 1.0,
        "spring_constant": 1.0,
        "damping_coefficient": 0.2,
        "omega_min": 1.0,
        "omega_max": 13.0,
    }
    r = post(client, params, n_frequencies=3)
    assert r.status_code == 200, r.text


def test_the_work_budget_refuses_naming_the_evaluations_in_time(client: TestClient) -> None:
    # The heaviest kind of sweep the inputs allow, per point under 2.3's per-run limit:
    # m = k = 1 (w0 = 1 rad/s), zeta = 0.0075 (b = 0.015 kg/s, Q = 66.7 <= 300), w from 0.5 to
    # 1 rad/s, eps_s = 1e-6, DOP853 at the tightest pair (rtol 1e-13, atol 1e-14). From rest
    # R/A <= 1 for w <= w0, so each run lasts about ln(2e6) / (2 pi zeta) + 2 = 310 cycles of
    # w0 (well under 500). 2.3 measured DOP853 at the tightest pair at 318 000 to 330 000
    # evaluations per 500 cycles (model.py, MAX_CYCLES comment), so ~2e5 per run and ~4e6 for
    # 21 points. At 2.3's measured 7 us per evaluation that is ~30 s: a budget that admitted it
    # would break the 15 s rule, so the sweep must be refused by the budget, and the refusal
    # (charged after each run: at most one run, ~2e5, over the budget) must come in time.
    params = {
        "mass": 1.0,
        "spring_constant": 1.0,
        "damping_coefficient": 0.015,
        "omega_min": 0.5,
        "omega_max": 1.0,
    }
    solver = {"method": "DOP853", "rtol": 1e-13, "atol": 1e-14}
    start = time.perf_counter()
    r = post(client, params, solver=solver, n_frequencies=21)
    seconds = time.perf_counter() - start
    assert r.status_code == 422, r.text[:300]
    text = detail_text(r)
    assert BUDGET_MESSAGE in text
    assert f"{MAX_RESONANCE_SWEEP_RHS_EVALUATIONS:,}" in text
    assert "fewer frequencies" in text
    assert seconds < SECONDS_PER_REQUEST, seconds


def test_the_default_sweep_is_admitted_in_time(client: TestClient) -> None:
    # D11: the defaults are chosen to fit the budget; one request well inside the 15 s rule.
    start = time.perf_counter()
    r = client.post(URL, json={"save_experiment": False})
    seconds = time.perf_counter() - start
    assert r.status_code == 200, r.text[:300]
    assert r.json()["n_rhs_evaluations"] <= MAX_RESONANCE_SWEEP_RHS_EVALUATIONS
    assert seconds < SECONDS_PER_REQUEST, seconds


def test_the_largest_grid_is_accepted_by_the_schema_and_answers_in_time(
    client: TestClient,
) -> None:
    # n_frequencies = MAX_N_FREQUENCIES on a cheap configuration (zeta = 0.5, ~7 cycles per
    # run at eps_s = 1e-6: ln(2e6) / (2 pi 0.5) + 2; loosest rtol): a result, or at most the
    # budget's refusal, never a validation refusal of the grid size, and within the 15 s rule.
    params = {"damping_coefficient": 5.0, "omega_min": 0.5, "omega_max": 15.0}
    solver = {"method": "DOP853", "rtol": 1e-6, "atol": 1e-6}
    start = time.perf_counter()
    r = post(client, params, solver=solver, n_frequencies=MAX_N_FREQUENCIES)
    seconds = time.perf_counter() - start
    assert r.status_code in (200, 422), r.text[:300]
    if r.status_code == 422:
        assert BUDGET_MESSAGE in detail_text(r), r.text[:300]
    else:
        body = r.json()
        assert len(body["amplitudes"]) == MAX_N_FREQUENCIES
        assert all(math.isfinite(a) for a in body["amplitudes"])
    assert seconds < SECONDS_PER_REQUEST, seconds
