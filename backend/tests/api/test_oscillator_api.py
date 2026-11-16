"""Seam 4: the harmonic oscillator over HTTP (roadmap 2.3, slice 3; plan D2, D9, D10, D12, D13).

Expected values are independent of the code under test: omega0, gamma, zeta, Q, the damped
frequency, the steady-state amplitude and phase, the amplitude peak and the motion itself are
written out here in their plain textbook forms (the code evaluates them through exact
rationals and a unified, cancellation-free form, plan D3), and the regimes are chosen so that
the hand-worked numbers are exact (b = 26 gives beta = 12; b = 10 is exactly critical).

The three presets (plan "What 2.3 builds"; UI-only, plan D1): Simple (b = 0, F0 = 0), Damped
(the defaults, plan D2) and Driven (damped, driven at the natural frequency).
"""

from __future__ import annotations

import fnmatch
import json
import math
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from simforge.api.registry import get_entry
from tests.api.test_replay import flat
from tests.approx import rel_approx

URL = "/api/v1/physics/oscillator/simulate"
MODEL_ID = "physics.oscillator"
EPS = float(np.finfo(float).eps)  # 2.2e-16
# Closed forms against closed forms: each side is at most a few roundings from the exact
# value (the code rounds an exact rational once, then a sqrt or a division; the test's plain
# formulas take up to about four roundings on these small, exactly representable inputs), so
# they agree to well within 16 ulp.
CLOSED = 16 * EPS
# Numerical against exact, as a fraction of the scale X. Slice 2 measured the displacement
# error at the step nodes against F (rtol + atol)(1 + cycles) + 5e-9 with F = 50, worst 0.10
# of that threshold over 1608 runs (SCIENTIFIC_VALIDATION.md). At the default pair (1e-10,
# 1e-10) and at most 16 cycles here that is 50 * 2e-10 * 17 + 5e-9 = 1.75e-7: 2e-7 of X.
NODE_ERROR = 2e-7
# The exact-solution column against the plain formulas, as a fraction of X. Slice 1's error
# model is 1.5 eps (Q + w0 T + A/X + 1) X, about 4e-14 X for Q = 10, w0 T = 100; the plain
# formulas here round w_d t (|w_d t| <= 100) to about 100 eps, so 2e-13 X covers both.
EXACT_COLUMN = 2e-13

SIMPLE: dict[str, Any] = {"damping_coefficient": 0.0, "drive_amplitude": 0.0}
DAMPED: dict[str, Any] = {}  # the defaults are the Damped preset (plan D2)
DRIVEN: dict[str, Any] = {"drive_amplitude": 1.0, "drive_angular_frequency": 5.0}
# The defaults, written out (plan D2): m = 1 kg, k = 25 N/m, b = 0.5 kg/s, F0 = 0, w = 5 rad/s,
# x0 = 0.1 m, v0 = 0, T = 20 s.
DEFAULTS = {
    "mass": 1.0,
    "spring_constant": 25.0,
    "damping_coefficient": 0.5,
    "drive_amplitude": 0.0,
    "drive_angular_frequency": 5.0,
    "initial_displacement": 0.1,
    "initial_velocity": 0.0,
    "duration": 20.0,
}


def post(client: TestClient, params: dict[str, Any], **extra: Any) -> Any:
    return client.post(URL, json={"parameters": params, "save_experiment": False, **extra})


def ok(client: TestClient, params: dict[str, Any], **extra: Any) -> dict[str, Any]:
    r = post(client, params, **extra)
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def underdamped_reference(p: dict[str, float], t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """x(t), v(t) for b < 2 sqrt(mk) (b = 0 included, away from undamped resonance), written
    as the textbook sum of the steady state and the decaying transient.

    x_p = A cos(w t - delta), A = (F0/m) / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2),
    delta = atan2(2 gamma w, w0^2 - w^2); the transient e^(-gamma t)(c1 cos w_d t + c2 sin w_d t)
    takes x(0) - x_p(0) and v(0) - x_p'(0).
    """
    m, k, b = p["mass"], p["spring_constant"], p["damping_coefficient"]
    f0, w = p["drive_amplitude"], p["drive_angular_frequency"]
    x0, v0 = p["initial_displacement"], p["initial_velocity"]
    w0 = math.sqrt(k / m)
    gamma = b / (2 * m)
    wd = math.sqrt(w0**2 - gamma**2)
    if f0 > 0:
        a = (f0 / m) / math.hypot(w0**2 - w**2, 2 * gamma * w)
        delta = math.atan2(2 * gamma * w, w0**2 - w**2)
    else:
        a, delta = 0.0, 0.0
    xp = a * np.cos(w * t - delta)
    vp = -a * w * np.sin(w * t - delta)
    c1 = x0 - a * math.cos(delta)
    c2 = (v0 - a * w * math.sin(delta) + gamma * c1) / wd
    decay = np.exp(-gamma * t)
    cos, sin = np.cos(wd * t), np.sin(wd * t)
    x = xp + decay * (c1 * cos + c2 * sin)
    v = vp + decay * ((-gamma * c1 + wd * c2) * cos + (-gamma * c2 - wd * c1) * sin)
    return x, v


# --- the contract (plan D12) ---------------------------------------------------------------


def test_default_request_returns_a_complete_labelled_result(client: TestClient) -> None:
    r = client.post(URL, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {
        "model",
        "parameters",
        "solver",
        "units",
        "assumptions",
        "derived",
        "steady_state",
        "numerical",
        "diagnostics",
        "checks",
        "series",
        "resonance",
        "method_note",
        "metadata",
    }
    assert body["model"]["id"] == MODEL_ID
    assert body["model"]["version"] == "1.0.0"
    assert body["parameters"] == DEFAULTS
    assert body["units"]["spring_constant"] == "N/m"
    assert body["units"]["damping_coefficient"] == "kg/s"
    assert "fraction of the scale X" in body["units"]["atol"]
    assert {a["id"] for a in body["assumptions"]} >= {
        "point_mass_on_ideal_spring",
        "linear_damping",
    }
    assert body["numerical"]["method"] == "DOP853"
    assert body["method_note"].startswith("numerical")
    assert {c["id"] for c in body["checks"]} >= {
        "displacement_error",
        "velocity_error",
        "energy_balance",
        "free_decay_period",
        "free_decay_ratio",
        "cost",
    }
    assert all(c["passed"] is not False for c in body["checks"])
    assert len(body["series"]["t"]) == 400
    assert body["metadata"]["experiment_saved"] is True


@pytest.mark.parametrize(
    "params",
    [SIMPLE, DAMPED, DRIVEN, {"damping_coefficient": 26.0}, {"damping_coefficient": 0.0, **DRIVEN}],
)
def test_response_is_strict_json_with_its_nulls(client: TestClient, params: dict[str, Any]) -> None:
    # Q is infinite when b = 0 and A has a pole at w0 when undamped: both must come back as
    # null, never as the non-standard literals Infinity or NaN.
    r = post(client, params)
    assert r.status_code == 200, r.text
    json.loads(r.text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


# --- the three presets ---------------------------------------------------------------------


def test_damped_preset_matches_the_textbook(client: TestClient) -> None:
    body = ok(client, DAMPED)
    d = body["derived"]
    # w0 = sqrt(25/1) = 5, gamma = 0.5/2 = 0.25, zeta = 0.5/(2 sqrt 25) = 0.05, Q = 5/0.5 = 10.
    assert d["natural_angular_frequency"] == rel_approx(5.0, CLOSED)
    assert d["damping_rate"] == rel_approx(0.25, CLOSED)
    assert d["damping_ratio"] == rel_approx(0.05, CLOSED)
    assert d["quality_factor"] == rel_approx(10.0, CLOSED)
    assert d["regime"] == "underdamped"
    wd = math.sqrt(25.0 - 0.0625)  # w_d^2 = w0^2 - gamma^2 = 24.9375, exact in binary
    assert d["damped_angular_frequency"] == rel_approx(wd, CLOSED)
    assert d["damped_period"] == rel_approx(2 * math.pi / wd, CLOSED)
    assert d["overdamped_rate"] is None
    # Undriven: no steady state and no resonance curve (plan D12).
    assert body["steady_state"] is None
    assert body["resonance"] is None
    # Underdamped: an envelope R e^(-gamma t) with R the transient's amplitude,
    # R = sqrt(x0^2 + ((v0 + gamma x0)/w_d)^2) for a free run.
    t = np.array(body["series"]["t"])
    r_amp = math.hypot(0.1, (0.0 + 0.25 * 0.1) / wd)
    envelope = np.array(body["series"]["envelope"])
    np.testing.assert_allclose(envelope, r_amp * np.exp(-0.25 * t), rtol=CLOSED * 8, atol=0)
    # (8 x CLOSED: e^(-gamma t) at gamma t up to 5 adds a few roundings to each side.)


def test_simple_preset_is_undamped_shm(client: TestClient) -> None:
    body = ok(client, SIMPLE)
    d = body["derived"]
    assert d["regime"] == "undamped"
    assert d["damping_rate"] == 0.0
    assert d["damping_ratio"] == 0.0
    assert d["quality_factor"] is None  # Q = sqrt(mk)/0: infinite, shown as null
    # Without damping the damped frequency is w0 itself and the period 2 pi / w0.
    assert d["damped_angular_frequency"] == rel_approx(5.0, CLOSED)
    assert d["damped_period"] == rel_approx(2 * math.pi / 5.0, CLOSED)
    assert d["overdamped_rate"] is None
    assert body["steady_state"] is None
    assert body["resonance"] is None
    assert body["series"]["envelope"] is None  # nothing decays
    # x = x0 cos(w0 t): at T = 20 s, 0.1 cos(100).
    x_scale = d["scale"]
    assert x_scale >= 0.1  # X bounds |x|, and |x(0)| = 0.1
    assert abs(body["numerical"]["final_displacement"] - 0.1 * math.cos(100.0)) <= (
        NODE_ERROR * x_scale
    )
    # No damping, no drive: both works stay 0 (their integrands are 0 * v^2 and 0 * v).
    assert set(body["series"]["damping_work"]) == {0.0}
    assert set(body["series"]["drive_work"]) == {0.0}


def test_driven_preset_at_resonance_has_the_textbook_steady_state(client: TestClient) -> None:
    body = ok(client, DRIVEN)
    s = body["steady_state"]
    assert s is not None
    # At w = w0 the stiffness and inertia cancel: A = (F0/m) / (2 gamma w) = 1 / 2.5 = 0.4 m,
    # and the displacement lags the force by exactly a quarter cycle, delta = pi/2.
    assert s["amplitude"] == rel_approx(0.4, CLOSED)
    assert s["phase_lag"] == rel_approx(math.pi / 2, CLOSED)
    # zeta = 0.05 < 1/sqrt 2: the amplitude peaks at w_r = sqrt(w0^2 - 2 gamma^2), height
    # A_max = (F0/m) / (2 gamma w_d) (plan D10).
    assert s["peak_angular_frequency"] == rel_approx(math.sqrt(25.0 - 2 * 0.0625), CLOSED)
    assert s["peak_amplitude"] == rel_approx(1.0 / (2 * 0.25 * math.sqrt(24.9375)), CLOSED)
    res = body["resonance"]
    assert res is not None
    w = np.array(res["angular_frequency"])
    # From 0 to max(3 w0, 1.2 w) = 15 rad/s (plan D9), in increasing order.
    assert w[0] == 0.0
    assert w[-1] == rel_approx(15.0, CLOSED)
    assert np.all(np.diff(w) > 0)
    # Every point is the textbook formula. Near w0 the plain w0^2 - w^2 cancels, but its
    # rounding (eps w0^2) is negligible next to (2 gamma w)^2 there, so 64 ulp is ample.
    a_ref = 1.0 / np.hypot(25.0 - w**2, 0.5 * w)
    np.testing.assert_allclose(res["amplitude"], a_ref, rtol=64 * EPS, atol=0)
    phase = np.array(res["phase_lag"])
    assert phase[0] == 0.0  # a static force: no lag
    assert np.all((phase >= 0) & (phase <= math.pi))
    assert np.all(np.diff(phase) >= 0)  # the lag grows from 0 through pi/2 towards pi
    # The peak itself is on the curve (plan D9 review item 5), and is its largest amplitude.
    assert max(res["amplitude"]) == rel_approx(s["peak_amplitude"], CLOSED)
    # A driven, damped run reports the transient left at the end (informational).
    assert "steady_state_reached" in {c["id"] for c in body["checks"]}
    assert body["diagnostics"]["remaining_transient"] is not None


@pytest.mark.parametrize(
    "params", [SIMPLE, DAMPED, DRIVEN, {**DRIVEN, "drive_angular_frequency": 4.0}]
)
def test_motion_matches_the_textbook_solution(client: TestClient, params: dict[str, Any]) -> None:
    body = ok(client, params)
    p = {**DEFAULTS, **params}
    t = np.array(body["series"]["t"])
    assert t[0] == 0.0
    assert t[-1] == p["duration"]
    x_ref, v_ref = underdamped_reference(p, t)
    x_scale = body["derived"]["scale"]
    w0 = math.sqrt(p["spring_constant"] / p["mass"])
    # X is a proved bound on |x| over the run (slice 1, decision B): check it against the
    # independent motion (1 + 1e-12 allows the reference's own rounding).
    assert np.max(np.abs(x_ref)) <= x_scale * (1 + 1e-12)
    np.testing.assert_allclose(
        body["series"]["x_exact"], x_ref, rtol=0, atol=EXACT_COLUMN * x_scale
    )
    np.testing.assert_allclose(
        body["series"]["v_exact"], v_ref, rtol=0, atol=EXACT_COLUMN * w0 * x_scale
    )
    final = body["numerical"]["final_displacement"]
    assert abs(final - x_ref[-1]) <= NODE_ERROR * x_scale
    # Energies are the textbook 1/2 m v^2 and 1/2 k x^2 of the reported numerical series.
    x, v = np.array(body["series"]["x"]), np.array(body["series"]["v"])
    np.testing.assert_allclose(
        body["series"]["kinetic_energy"], 0.5 * p["mass"] * v**2, rtol=4 * EPS, atol=0
    )
    np.testing.assert_allclose(
        body["series"]["potential_energy"], 0.5 * p["spring_constant"] * x**2, rtol=4 * EPS, atol=0
    )


# --- nulls when undriven, undamped or overdamped ---------------------------------------------


def test_undamped_driven_run_has_no_steady_state_or_resonance_curve(client: TestClient) -> None:
    # With b = 0 a drive never settles (A has a pole at w0 and no transient decays): plan D12.
    body = ok(
        client, {"damping_coefficient": 0.0, "drive_amplitude": 1.0, "drive_angular_frequency": 3.0}
    )
    assert body["derived"]["quality_factor"] is None
    assert body["steady_state"] is None
    assert body["resonance"] is None
    assert body["series"]["envelope"] is None
    assert body["diagnostics"]["remaining_transient"] is None
    assert body["diagnostics"]["free_decay_period_residual"] is None


def test_overdamped_run_has_beta_and_no_damped_frequency(client: TestClient) -> None:
    # b = 26: gamma = 13, beta = sqrt(gamma^2 - w0^2) = sqrt(169 - 25) = 12 exactly; the two
    # decay rates are gamma -+ beta = 1 and 25 per second. T = 1 s (gamma T = 13 >= 1).
    body = ok(client, {"damping_coefficient": 26.0, "duration": 1.0})
    d = body["derived"]
    assert d["regime"] == "overdamped"
    assert d["overdamped_rate"] == rel_approx(12.0, CLOSED)
    assert d["damped_angular_frequency"] is None
    assert d["damped_period"] is None
    assert d["quality_factor"] == rel_approx(5.0 / 26.0, CLOSED)  # sqrt(mk)/b
    assert d["damping_ratio"] == rel_approx(2.6, CLOSED)
    assert body["steady_state"] is None
    assert body["resonance"] is None
    assert body["series"]["envelope"] is None  # no oscillation, so no envelope
    assert body["diagnostics"]["free_decay_period_residual"] is None
    assert body["diagnostics"]["free_decay_ratio_residual"] is None
    # x = c1 e^(-t) + c2 e^(-25 t) with c1 + c2 = x0 and -c1 - 25 c2 = v0 = 0:
    # c2 = -x0/24, c1 = 25 x0 / 24.
    x_ref = 25 * 0.1 / 24 * math.exp(-1.0) - 0.1 / 24 * math.exp(-25.0)
    assert abs(body["numerical"]["final_displacement"] - x_ref) <= NODE_ERROR * d["scale"]
    # Stiffness number (gamma + beta) T = 25 (plan D6, D8).
    assert body["diagnostics"]["stiffness_number"] == rel_approx(25.0, CLOSED)


def test_critical_damping_is_labelled_exactly(client: TestClient) -> None:
    # b = 10 = 2 sqrt(mk) exactly in floats: critically damped, zeta = 1, Q = 1/2.
    body = ok(client, {"damping_coefficient": 10.0, "duration": 2.0})
    d = body["derived"]
    assert d["regime"] == "critically_damped"
    assert d["damping_ratio"] == 1.0
    assert d["quality_factor"] == 0.5
    assert d["damped_angular_frequency"] is None
    assert d["overdamped_rate"] is None
    # x = (x0 + (v0 + gamma x0) t) e^(-gamma t) = (0.1 + 0.5 t) e^(-5 t).
    x_ref = (0.1 + 0.5 * 2.0) * math.exp(-10.0)
    assert abs(body["numerical"]["final_displacement"] - x_ref) <= NODE_ERROR * d["scale"]


# --- validation messages that come from the model (ModelDomainError -> 422) -------------------


def test_stiff_run_with_an_explicit_method_gets_an_explanatory_422(client: TestClient) -> None:
    # b = 1000: gamma = 500, beta = sqrt(250000 - 25); (gamma + beta) T = 999.975 x 20 ~ 2e4,
    # above the explicit-method limit of 1e4 (plan D6). Radau has no such limit.
    params = {"damping_coefficient": 1000.0}
    r = post(client, params, solver={"method": "RK45"})
    assert r.status_code == 422
    assert "Radau" in r.json()["detail"]
    assert post(client, params, solver={"method": "Radau"}).status_code == 200


# --- reproducibility and the stored record (plan D12, D13) -----------------------------------


def test_identical_inputs_give_identical_hash_and_results(client: TestClient) -> None:
    payload = {"parameters": DRIVEN, "save_experiment": False}
    a, b = client.post(URL, json=payload).json(), client.post(URL, json=payload).json()
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]
    assert a["metadata"]["output_digest"] == b["metadata"]["output_digest"]
    assert a["numerical"] == b["numerical"]  # deterministic: bitwise-identical floats


def test_hash_covers_parameters_solver_and_samples_but_not_the_save_flag(
    client: TestClient,
) -> None:
    def digest(payload: dict[str, Any]) -> str:
        return str(client.post(URL, json=payload).json()["metadata"]["input_hash"])

    assert digest({"save_experiment": False}) == digest({"save_experiment": True})
    assert digest({}) != digest({"parameters": {"damping_coefficient": 0.4}})
    assert digest({}) != digest({"solver": {"rtol": 1e-9}})
    assert digest({}) != digest({"n_samples": 401})


SUMMARY_LEAVES = {
    "max_displacement_error",
    "max_velocity_error",
    "max_energy_balance_residual",
    "free_decay_period_residual",
    "free_decay_ratio_residual",
    "n_steps",
    "n_rhs_evaluations",
}


@pytest.mark.parametrize(
    "params",
    [SIMPLE, DAMPED, DRIVEN, {"damping_coefficient": 26.0, "duration": 1.0}],
)
def test_record_run_stores_the_d12_summary(client: TestClient, params: dict[str, Any]) -> None:
    # Plan D12: derived, steady_state, the three error maxima, the two free-decay residuals
    # (or null), n_steps and n_rhs_evaluations; curves are recomputed, never stored.
    run = client.post(URL, json={"parameters": params}).json()
    record = client.get(f"/api/v1/experiments/{run['metadata']['run_id']}").json()
    assert record["model_id"] == MODEL_ID
    summary = record["summary"]
    assert summary["derived"] == run["derived"]
    assert summary["steady_state"] == run["steady_state"]
    leaves = flat(summary)
    names = {key.rsplit(".", 1)[-1]: value for key, value in leaves.items()}
    assert set(names) >= SUMMARY_LEAVES, sorted(names)
    for name in ("max_displacement_error", "max_velocity_error", "max_energy_balance_residual"):
        assert names[name] == run["diagnostics"][name]
    for name in ("free_decay_period_residual", "free_decay_ratio_residual"):
        assert names[name] == run["diagnostics"][name]
    assert names["n_steps"] == run["numerical"]["n_steps"]
    assert names["n_rhs_evaluations"] == run["numerical"]["n_rhs_evaluations"]
    assert not any(isinstance(v, list) for v in leaves.values()), "a curve was stored"
    # Hashed inputs (plan D12): parameters, solver, n_samples, as 2.1.
    assert set(record["inputs"]) == {"parameters", "solver", "n_samples"}


def test_headline_names_x0_zeta_regime_and_q(client: TestClient) -> None:
    # Plan slice 3: "x0 0.1 m, zeta 0.05 (underdamped), Q 10" for the defaults.
    run = client.post(URL, json={}).json()
    record = client.get(f"/api/v1/experiments/{run['metadata']['run_id']}").json()
    entry = get_entry(MODEL_ID)
    assert entry is not None
    headline = entry.headline(record["summary"])
    assert "0.1 m" in headline
    assert "0.05" in headline
    assert "underdamped" in headline
    assert "Q 10" in headline


@pytest.mark.parametrize(
    "params",
    [
        SIMPLE,
        {"damping_coefficient": 0.0, "drive_amplitude": 1.0, "drive_angular_frequency": 3.0},
        {"damping_coefficient": 26.0, "duration": 1.0},
        {"damping_coefficient": 10.0, "duration": 2.0},
    ],
)
def test_null_fields_have_one_tolerance_rule_each_and_replay_identically(
    client: TestClient, params: dict[str, Any]
) -> None:
    # The registry case covers a driven damped run; these cover the nulls (undamped Q and
    # steady state, overdamped w_d and residuals, critical damping), whose rules must not
    # divide by a missing value.
    run = client.post(URL, json={"parameters": params}).json()
    record = client.get(f"/api/v1/experiments/{run['metadata']['run_id']}").json()
    entry = get_entry(MODEL_ID)
    assert entry is not None
    rules = entry.tolerances(record["inputs"], record["summary"])
    for field in flat(record["summary"]):
        matching = [p for p in rules if fnmatch.fnmatchcase(field, p)]
        assert len(matching) == 1, (field, matching)
        rule = rules[matching[0]]
        assert rule.reason
        assert math.isfinite(rule.relative), field
        assert math.isfinite(rule.absolute), field
    replay = client.post(f"/api/v1/experiments/{record['run_id']}/replay", json={}).json()
    assert replay["verdict"] == "identical"
