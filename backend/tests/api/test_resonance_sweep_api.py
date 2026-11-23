"""The simulated resonance curve over HTTP (roadmap 2.5, slice 4; plan D6, D9, D11, D12).

Expected values are independent of the code under test: the exact resonance curve R1
A(w) = (F0/m) / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2), tan delta = 2 gamma w / (w0^2 - w^2),
and the exact peak R2 w_r = sqrt(w0^2 - 2 gamma^2), A_max = (F0/m) / (2 gamma w_d), are
written out here; the grid is the evenly spaced one D6 describes; the settle times are whole
drive periods (D7); and the numerical amplitudes are held to the proved bound B1 the response
states for each point (C1, R3 and R5: proved given the measured trajectory error).

Assumed contract (slice 4 defines it): the request has ``parameters`` (mass, spring_constant,
damping_coefficient, drive_amplitude, omega_min, omega_max, settle_tolerance), ``solver``,
``n_frequencies`` and ``save_experiment``; the stored inputs are ``parameters``, ``solver``
and ``n_frequencies``.
"""

from __future__ import annotations

import fnmatch
import json
import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.api.registry import get_entry
from simforge.physics.oscillator.resonance_sweep import MAX_RESONANCE_SWEEP_RHS_EVALUATIONS
from tests.api.test_replay import flat
from tests.approx import rel_approx

URL = "/api/v1/physics/oscillator/resonance-sweep"
MODEL_ID = "physics.oscillator.resonance_sweep"
# Plan D11 defaults: m = 1 kg, k = 25 N/m, b = 1 kg/s (w0 = 5 rad/s, gamma = 0.5 1/s,
# zeta = 0.1, Q = 5), F0 = 1 N, w from 0.5 to 15 rad/s, 21 frequencies, DOP853, eps_s = 1e-6.
M, K, B, F0 = 1.0, 25.0, 1.0, 1.0
W_MIN, W_MAX, N_DEFAULT = 0.5, 15.0, 21
EPS_S_DEFAULT = 1e-6
PARAMETER_FIELDS = {
    "mass",
    "spring_constant",
    "damping_coefficient",
    "drive_amplitude",
    "omega_min",
    "omega_max",
    "settle_tolerance",
}
# The cheap request used where the default's cost is not the point: zeta = 0.2, 5 points.
SMALL = {"parameters": {"damping_coefficient": 2.0, "omega_min": 1.0, "omega_max": 10.0}}


def strict(text: str) -> Any:
    return json.loads(text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def post(client: TestClient, body: dict[str, Any]) -> Any:
    return client.post(URL, json={"save_experiment": False, **body})


def stored(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    run = client.post(URL, json={**body, "save_experiment": True})
    assert run.status_code == 200, run.text
    record: dict[str, Any] = client.get(
        f"/api/v1/experiments/{run.json()['metadata']['run_id']}"
    ).json()
    return record


def exact_amplitude(w: float, m: float = M, k: float = K, b: float = B, f0: float = F0) -> float:
    """R1, written out: A = (F0/m) / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2)."""
    w0sq, gamma = k / m, b / (2 * m)
    return (f0 / m) / math.sqrt((w0sq - w * w) ** 2 + (2 * gamma * w) ** 2)


def exact_phase(w: float, m: float = M, k: float = K, b: float = B) -> float:
    """R1: delta in [0, pi] with tan delta = 2 gamma w / (w0^2 - w^2)."""
    return math.atan2(2 * (b / (2 * m)) * w, k / m - w * w)


# Tolerances on the closed forms above against the response's exact values: both are a few
# roundings of the same formula (possibly arranged differently). The cancellation in
# w0^2 - w^2 costs eps w0^2 absolute, i.e. at most eps w0^2 / (2 gamma w) <= 50 eps relative
# on these grids (w >= 0.5 rad/s, w0^2 = 25, gamma = 0.5), so 1e-13 (450 eps) has margin.
CLOSED_FORM_REL = 1e-13
CLOSED_FORM_PHASE_ABS = 1e-13  # rad, the same argument for atan2 of numbers of order 1


# --- the contract ---------------------------------------------------------------------------


def test_default_request_returns_a_complete_labelled_result(client: TestClient) -> None:
    r = client.post(URL, json={})
    assert r.status_code == 200, r.text
    body = strict(r.text)
    assert body["model"]["id"] == MODEL_ID
    assert body["model"]["version"] == "1.0.0"
    assert body["parameters"] == {
        "mass": M,
        "spring_constant": K,
        "damping_coefficient": B,
        "drive_amplitude": F0,
        "omega_min": W_MIN,
        "omega_max": W_MAX,
        "settle_tolerance": EPS_S_DEFAULT,
    }
    assert body["solver"]["method"] == "DOP853"
    for field, unit in {
        "mass": "kg",
        "spring_constant": "N/m",
        "damping_coefficient": "kg/s",
        "drive_amplitude": "N",
        "omega_min": "rad/s",
        "omega_max": "rad/s",
        "amplitude": "m",
        "phase_lag": "rad",
        "settle_time": "s",
    }.items():
        assert body["units"][field] == unit, field
    assert {"starts_from_rest", "steady_state_after_settling"} <= {
        a["id"] for a in body["assumptions"]
    }
    per_point = (
        "angular_frequencies",
        "amplitudes",
        "phase_lags",
        "exact_amplitudes",
        "exact_phase_lags",
        "settle_times",
        "amplitude_bounds",
    )
    for key in per_point:
        assert len(body[key]) == N_DEFAULT, key
    # D6: evenly spaced from exactly omega_min to exactly omega_max. Step 0.725 rad/s; the
    # points of a linspace are within a few roundings of lo + i h (1e-14 relative).
    w = body["angular_frequencies"]
    assert w[0] == W_MIN
    assert w[-1] == W_MAX
    h = (W_MAX - W_MIN) / (N_DEFAULT - 1)
    for i, wi in enumerate(w):
        assert wi == rel_approx(W_MIN + i * h, rel=1e-14), i
    # D9/D12: the grid step over gamma, exact by definition: 0.725 / 0.5 = 1.45.
    assert body["grid_step_over_gamma"] == rel_approx(h / (B / (2 * M)), rel=1e-14)
    assert 0 < body["n_rhs_evaluations"] <= MAX_RESONANCE_SWEEP_RHS_EVALUATIONS
    ids = {c["id"] for c in body["checks"]}
    assert {
        "lock_in_amplitude",
        "lock_in_phase",
        "extraction_amplitude",
        "power_balance",
        "peak_frequency",
    } <= ids
    assert all(c["passed"] is not False for c in body["checks"])
    assert body["metadata"]["experiment_saved"] is True


def test_exact_curve_is_r1_and_every_point_is_within_its_bound(client: TestClient) -> None:
    body = strict(client.post(URL, json={"save_experiment": False}).text)
    for k, w in enumerate(body["angular_frequencies"]):
        a = exact_amplitude(w)
        assert body["exact_amplitudes"][k] == rel_approx(a, rel=CLOSED_FORM_REL), w
        assert body["exact_phase_lags"][k] == pytest.approx(
            exact_phase(w), rel=0, abs=CLOSED_FORM_PHASE_ABS
        ), w
        # C1 against this test's own R1: |A_sim - A| <= B1 is proved given e_x (R3, R5); the
        # extra 1e-13 A covers the two evaluations of the closed form differing (above).
        b1 = body["amplitude_bounds"][k]
        assert b1 > 0
        assert abs(body["amplitudes"][k] - a) <= b1 + CLOSED_FORM_REL * a, w
        # D7: the settle time is a whole number of drive periods 2 pi / w. The count is at
        # most a few hundred and t_s w / 2 pi is a few roundings of it: 1e-9 absolute.
        periods = body["settle_times"][k] * w / (2 * math.pi)
        assert periods == pytest.approx(round(periods), rel=0, abs=1e-9), w
        assert round(periods) >= 0
    # The dashed curve (2.3's resonance curve): R1 at each of its frequencies.
    curve = body["resonance"]
    assert len(curve["angular_frequency"]) == len(curve["amplitude"]) == len(curve["phase_lag"])
    for w, a, d in zip(
        curve["angular_frequency"], curve["amplitude"], curve["phase_lag"], strict=True
    ):
        assert a == rel_approx(exact_amplitude(w), rel=CLOSED_FORM_REL), w
        assert d == pytest.approx(exact_phase(w), rel=0, abs=CLOSED_FORM_PHASE_ABS), w


def test_peak_against_the_exact_resonance(client: TestClient) -> None:
    body = strict(client.post(URL, json={"save_experiment": False}).text)
    peak = body["peak"]
    w0sq, gamma = K / M, B / (2 * M)
    w_r = math.sqrt(w0sq - 2 * gamma**2)  # R2: sqrt(24.5) = 4.9497 rad/s
    a_max = (F0 / M) / (2 * gamma * math.sqrt(w0sq - gamma**2))  # R2: 1 / sqrt(24.75)
    # Closed forms evaluated two ways: a few roundings (1e-14 relative, 45 eps).
    assert peak["exact_angular_frequency"] == rel_approx(w_r, rel=1e-14)
    assert peak["exact_amplitude"] == rel_approx(a_max, rel=1e-14)
    # The refinement keeps the grid point when it beats Brent (D3), so the refined amplitude
    # is at least the best grid amplitude; and every A_sim is within its B1 of an A(w) <= A_max
    # (C1, proved given e_x), so the refined amplitude is at most A_max + B1 at the peak.
    assert peak["amplitude"] >= max(body["amplitudes"])
    assert peak["amplitude"] <= a_max + peak["amplitude_bound"]
    assert W_MIN <= peak["angular_frequency"] <= W_MAX
    # zeta = 0.1 has an interior peak, and the best grid point (4.85 rad/s) is interior, so u
    # exists and is labelled an estimate (D9).
    assert peak["uncertainty"] is not None
    assert peak["uncertainty"] > 0
    assert peak["uncertainty_note"].startswith("Estimate, not a bound")


def test_no_exact_peak_when_zeta_is_at_least_one_over_root_two(client: TestClient) -> None:
    # zeta = 0.8 > 1/sqrt 2 (b = 2 zeta sqrt(m k) = 8 kg/s): R2 has no interior maximum, A(w)
    # falls from A(0) = F0/k, so w_r and A_max are null and C5 gives no verdict (D9, D10).
    r = post(
        client,
        {"parameters": {"damping_coefficient": 8.0, "omega_min": 0.5, "omega_max": 10.0}},
    )
    assert r.status_code == 200, r.text
    peak = r.json()["peak"]
    assert peak["exact_angular_frequency"] is None
    assert peak["exact_amplitude"] is None
    c5 = next(c for c in r.json()["checks"] if c["id"] == "peak_frequency")
    assert c5["passed"] is None


# --- reproducibility ------------------------------------------------------------------------


def test_identical_inputs_give_identical_hash_and_results(client: TestClient) -> None:
    body = {**SMALL, "n_frequencies": 5}
    a, b = post(client, body).json(), post(client, body).json()
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]
    assert a["metadata"]["output_digest"] == b["metadata"]["output_digest"]
    assert a["amplitudes"] == b["amplitudes"]  # deterministic: bitwise-identical floats


def test_hash_ignores_the_save_flag_but_not_the_inputs(client: TestClient) -> None:
    def digest(extra: dict[str, Any]) -> str:
        payload = {**SMALL, "n_frequencies": 5, **extra}
        r = client.post(URL, json=payload)
        assert r.status_code == 200, r.text
        return str(r.json()["metadata"]["input_hash"])

    base = digest({"save_experiment": False})
    assert base == digest({"save_experiment": True})
    assert base != digest({"n_frequencies": 6})
    assert base != digest({"solver": {"method": "RK45"}})
    changed = {**SMALL["parameters"], "settle_tolerance": 1e-4}
    assert base != digest({"parameters": changed})


def test_saved_run_replays_identical_and_stored_inputs_rebuild_it(client: TestClient) -> None:
    body = {**SMALL, "n_frequencies": 5}
    record = stored(client, body)
    assert record["model_id"] == MODEL_ID
    assert set(record["inputs"]) == {"parameters", "solver", "n_frequencies"}
    assert set(record["inputs"]["parameters"]) == PARAMETER_FIELDS
    assert record["inputs"]["n_frequencies"] == 5
    # The stored inputs, posted again, ask the same question (same input hash).
    again = post(client, record["inputs"])
    assert again.status_code == 200, again.text
    assert again.json()["metadata"]["input_hash"] == record["input_hash"]
    replay = client.post(f"/api/v1/experiments/{record['run_id']}/replay", json={}).json()
    assert replay["verdict"] == "identical"


def test_stored_summary_has_one_finite_tolerance_rule_per_field(client: TestClient) -> None:
    # D12: the summary stores the refined peak w and A and the worst C1 ratio; each field
    # gets exactly one finite replay rule with a reason.
    body = {**SMALL, "n_frequencies": 7}
    full = post(client, body).json()
    record = stored(client, body)
    summary = flat(record["summary"])
    values = list(summary.values())
    assert full["peak"]["angular_frequency"] in values
    assert full["peak"]["amplitude"] in values
    assert any("ratio" in name for name in summary)
    entry = get_entry(MODEL_ID)
    assert entry is not None
    rules = entry.tolerances(record["inputs"], record["summary"])
    for field in summary:
        matching = [p for p in rules if fnmatch.fnmatchcase(field, p)]
        assert len(matching) == 1, (field, matching)
        rule = rules[matching[0]]
        assert rule.reason
        assert math.isfinite(rule.relative), field
        assert math.isfinite(rule.absolute), field


def test_peak_rules_are_at_least_the_stated_precision(client: TestClient) -> None:
    # D12: across platforms the peak w agrees within max(xatol, u), xatol = 1e-7 w0 (D9), and
    # the peak amplitude within its B1. A rule tighter than either would fail a correct
    # replay on another CPU. The default has u (asserted above); w0 = 5 rad/s.
    full = post(client, {}).json()
    record = stored(client, {})
    entry = get_entry(MODEL_ID)
    assert entry is not None
    rules = entry.tolerances(record["inputs"], record["summary"])
    summary = flat(record["summary"])
    peak = full["peak"]

    def allowance(value: float) -> float:
        name = next(n for n, v in summary.items() if v == value)
        rule = rules[next(p for p in rules if fnmatch.fnmatchcase(name, p))]
        return float(rule.absolute + rule.relative * abs(value))

    w0 = math.sqrt(K / M)
    assert allowance(peak["angular_frequency"]) >= max(1e-7 * w0, peak["uncertainty"])
    assert allowance(peak["amplitude"]) >= peak["amplitude_bound"]
