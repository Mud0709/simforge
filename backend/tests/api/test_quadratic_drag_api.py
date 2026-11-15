"""Seam 4: the quadratic-drag model over HTTP (roadmap 2.1, slice 3; plan D2, D6-D8).

Expected values are independent of the code under test: the textbook vacuum formulas and
the exact vertical solution R3 are written out here (plain forms, not the cancellation-free
ones the reference module uses), validation boundaries are worked by hand, and the terminal
speed is checked through the force balance c v_t^2 = m g.
"""

from __future__ import annotations

import fnmatch
import json
import math
import random
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.api.registry import get_entry
from simforge.api.replay import compare_summaries
from simforge.physics.projectile import quadratic_numerical
from tests.api.test_replay import flat
from tests.approx import rel_approx

URL = "/api/v1/physics/projectile/quadratic-drag/simulate"
MODEL_ID = "physics.projectile.quadratic_drag"
G = 9.80665


def post(client: TestClient, params: dict[str, Any], **extra: Any) -> Any:
    return client.post(URL, json={"parameters": params, "save_experiment": False, **extra})


def post_raw(client: TestClient, body: str) -> Any:
    return client.post(URL, content=body, headers={"Content-Type": "application/json"})


# --- the contract ---------------------------------------------------------------------------


def test_default_request_returns_a_complete_labelled_result(client: TestClient) -> None:
    r = client.post(URL, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"]["id"] == MODEL_ID
    assert body["model"]["version"] == "1.0.1"
    assert body["units"]["drag_constant"] == "kg/m"
    assert {a["id"] for a in body["assumptions"]} >= {"point_mass", "quadratic_drag"}
    assert "linear_drag" not in {a["id"] for a in body["assumptions"]}
    assert body["numerical"]["method"] == "DOP853"
    assert body["numerical_note"].startswith("numerical")
    assert body["vacuum"]["method_note"].startswith("exact")
    assert body["vertical_reference"] is None  # 45 degrees: no exact 2-D solution
    assert body["diagnostics"]["max_invariant_residual"] is not None
    assert body["checks"]
    assert all(c["passed"] is not False for c in body["checks"])
    assert len(body["series"]["t"]) == 400
    assert len(body["series"]["vacuum_t"]) == 400
    assert body["metadata"]["experiment_saved"] is True


def test_response_is_strict_json_even_in_vacuum_and_vertical(client: TestClient) -> None:
    # Vacuum has an infinite terminal speed and a vertical launch an undefined invariant:
    # both must come back as null, never as the non-standard literals Infinity or NaN.
    for params in ({"drag_constant": 0.0}, {"launch_angle_deg": 90.0}):
        r = post(client, params)
        assert r.status_code == 200, r.text
        json.loads(r.text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def test_terminal_speed_balances_weight_and_drag(client: TestClient) -> None:
    m, c = 0.057, 1.05e-3  # roughly a tennis ball: c = rho C_d A / 2
    body = post(client, {"mass": m, "drag_constant": c}).json()
    v_t = body["terminal_speed"]
    # Force balance at terminal speed: c v_t^2 = m g (a few roundings: 1e-14 relative).
    assert c * v_t**2 == rel_approx(m * G, rel=1e-14)


def test_vacuum_run_matches_the_textbook_and_has_no_terminal_speed(client: TestClient) -> None:
    v0, angle = 10.0, 30.0
    body = post(client, {"initial_speed": v0, "launch_angle_deg": angle, "drag_constant": 0.0})
    body = body.json()
    assert body["terminal_speed"] is None  # infinite: JSON has no infinity
    textbook_range = v0**2 * math.sin(math.radians(2 * angle)) / G
    textbook_height = (v0 * math.sin(math.radians(angle))) ** 2 / (2 * G)
    # Closed forms evaluated two ways: a few roundings apart.
    assert body["vacuum"]["range"] == rel_approx(textbook_range, rel=1e-13)
    assert body["vacuum"]["max_height"] == rel_approx(textbook_height, rel=1e-13)
    # With c = 0 the solver integrates the drag-free motion. Global error of an adaptive
    # solve at rtol = atol = 1e-10 stays within 1e-9 here (the linear model's API test uses
    # the same bound for the same vacuum flight).
    assert body["numerical"]["range"] == rel_approx(textbook_range, rel=1e-9)


def test_drag_shortens_the_flight_below_the_vacuum_one(client: TestClient) -> None:
    body = post(client, {"drag_constant": 0.05}).json()
    assert body["numerical"]["range"] < body["vacuum"]["range"]
    assert body["numerical"]["max_height"] < body["vacuum"]["max_height"]
    # R7 i: the speed never exceeds max(v0, v_t), so neither does the impact speed.
    assert body["numerical"]["impact_speed"] <= max(20.0, body["terminal_speed"]) * (1 + 1e-9)


def exact_vertical(v0: float, h: float, v_t: float, g: float) -> dict[str, float]:
    """R3 written out in its plain textbook form (tan up, tanh down)."""
    tau = v_t / g
    apex_time = tau * math.atan(v0 / v_t)
    climb = v_t**2 / (2 * g) * math.log(1 + v0**2 / v_t**2)
    x = g * (h + climb) / v_t**2
    fall_time = tau * math.acosh(math.exp(x))
    return {
        "apex_time": apex_time,
        "max_height": h + climb,
        "flight_time": apex_time + fall_time,
        "impact_speed": v_t * math.sqrt(1 - math.exp(-2 * x)),
    }


@pytest.mark.parametrize(("h", "method"), [(0.0, "DOP853"), (0.0, "Radau"), (50.0, "RK45")])
def test_vertical_launch_is_compared_with_the_exact_solution(
    client: TestClient, h: float, method: str
) -> None:
    # v0 = v_t = 20 m/s: no cancellation in the plain formulas (ln 2, atan 1).
    v0, v_t = 20.0, 20.0
    c = 1.0 * G / v_t**2
    params = {"initial_speed": v0, "launch_angle_deg": 90.0, "launch_height": h, "drag_constant": c}
    body = post(client, params, solver={"method": method}).json()
    exact = exact_vertical(v0, h, v_t, G)
    ref = body["vertical_reference"]
    assert ref is not None
    for q in ("apex_time", "max_height", "flight_time", "impact_speed"):
        # Closed forms against closed forms: rounding plus c = m g / v_t^2 rounded once.
        assert ref["exact"][q] == rel_approx(exact[q], rel=1e-13), q
    # Numerical against exact. Slice 2 measured the vertical flight-time error at no more than
    # 61 x (rtol + atol/v0) over its grid; at the defaults that is 6.4e-9, so 1e-8.
    assert body["numerical"]["flight_time"] == rel_approx(exact["flight_time"], rel=1e-8)
    assert ref["flight_time"]["relative"] <= 1e-8
    # vx = 0 exactly, so the hodograph invariant (which divides by vx) is undefined.
    assert body["diagnostics"]["max_invariant_residual"] is None
    assert body["numerical"]["range"] == 0.0


# --- validation -----------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["initial_speed", "drag_constant", "mass", "launch_height"])
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(client: TestClient, field: str, literal: str) -> None:
    r = post_raw(client, f'{{"parameters": {{"{field}": {literal}}}}}')
    assert r.status_code == 422
    detail = json.loads(r.text, parse_constant=lambda c: pytest.fail(f"non-finite {c}"))
    assert detail["detail"][0]["loc"] == ["body", "parameters", field]


def test_non_finite_solver_settings_are_rejected(client: TestClient) -> None:
    r = post_raw(client, '{"solver": {"atol": NaN}}')
    assert r.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"mass": 0},
        {"mass": 1e-7},  # below the 1e-6 kg floor
        {"initial_speed": 0},
        {"initial_speed": 5e-4},  # below the 1e-3 m/s floor
        {"initial_speed": 1.0001e4},
        {"launch_angle_deg": 90.0001},
        {"launch_angle_deg": -1},
        {"launch_height": -1},
        {"launch_height": 1.0001e5},
        {"drag_constant": -0.1},
        {"drag_constant": 1.0001e6},
        {"gravity": 0.0099},
        {"gravity": 1000.1},
        {"drag_coefficient": 0.1},  # the linear model's name (b in kg/s) is not this model's c
        {"initial_speed": "fast"},
    ],
)
def test_invalid_parameters_are_rejected(client: TestClient, params: dict[str, Any]) -> None:
    assert post(client, params).status_code == 422


def test_invalid_request_settings_are_rejected(client: TestClient) -> None:
    assert client.post(URL, json={"solver": {"method": "Euler"}}).status_code == 422
    assert client.post(URL, json={"solver": {"rtol": 0.5}}).status_code == 422
    assert client.post(URL, json={"n_samples": 9}).status_code == 422
    assert client.post(URL, json={"n_samples": 5001}).status_code == 422
    assert client.post(URL, json={"unknown": 1}).status_code == 422


def test_launching_flat_from_the_ground_is_refused(client: TestClient) -> None:
    r = post(client, {"launch_angle_deg": 0.0, "launch_height": 0.0})
    assert r.status_code == 422
    assert "zero flight time" in r.text
    # From a height, a horizontal launch is a real flight.
    assert post(client, {"launch_angle_deg": 0.0, "launch_height": 10.0}).status_code == 200


def test_stiff_run_with_an_explicit_method_gets_an_explanatory_422(client: TestClient) -> None:
    # A 100 km fall at v_t = 3 m/s travels at least kappa h = g h / v_t^2 ~ 1.1e5 drag lengths,
    # above the explicit-method limit of 1e4.
    params = {"launch_height": 1e5, "drag_constant": G / 9.0, "initial_speed": 10.0}
    r = post(client, params, solver={"method": "RK45"})
    assert r.status_code == 422
    assert "Radau" in r.json()["detail"]


# --- reproducibility ------------------------------------------------------------------------


def test_identical_inputs_give_identical_hash_and_results(client: TestClient) -> None:
    payload = {"parameters": {"drag_constant": 0.03}, "save_experiment": False}
    a, b = client.post(URL, json=payload).json(), client.post(URL, json=payload).json()
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]
    assert a["metadata"]["output_digest"] == b["metadata"]["output_digest"]
    assert a["numerical"] == b["numerical"]  # deterministic: bitwise-identical floats


def test_hash_ignores_the_save_flag_but_not_the_inputs(client: TestClient) -> None:
    def digest(payload: dict[str, Any]) -> str:
        return str(client.post(URL, json=payload).json()["metadata"]["input_hash"])

    assert digest({"save_experiment": False}) == digest({"save_experiment": True})
    assert digest({}) != digest({"parameters": {"drag_constant": 0.02}})
    assert digest({}) != digest({"solver": {"rtol": 1e-9}})
    assert digest({}) != digest({"n_samples": 401})


def test_the_stored_summary_has_the_same_shape_for_every_run(client: TestClient) -> None:
    # Plan D7: numerical.*, terminal_speed, vacuum.*, diagnostics.*; the vertical comparison is
    # shown, not stored, so a vertical or vacuum run stores the same fields.
    shapes = []
    for params in ({}, {"launch_angle_deg": 90.0}, {"drag_constant": 0.0}):
        run = client.post(URL, json={"parameters": params}).json()
        record = client.get(f"/api/v1/experiments/{run['metadata']['run_id']}").json()
        summary = record["summary"]
        shapes.append({k: sorted(v) if isinstance(v, dict) else None for k, v in summary.items()})
    assert shapes[0] == shapes[1] == shapes[2]
    assert shapes[0] == {
        "numerical": sorted(
            [
                "flight_time",
                "range",
                "max_height",
                "apex_time",
                "impact_speed",
                "method",
                "rtol",
                "atol",
                "n_steps",
                "n_rhs_evaluations",
            ]
        ),
        "terminal_speed": None,
        "vacuum": sorted(["flight_time", "range", "max_height", "apex_time", "impact_speed"]),
        "diagnostics": sorted(
            [
                "max_energy_balance_residual",
                "max_invariant_residual",
                "drag_time_bound",
                "flight_time_bound",
            ]
        ),
    }


@pytest.mark.parametrize(
    "params", [{}, {"launch_angle_deg": 90.0}, {"drag_constant": 0.0, "launch_height": 3.0}]
)
def test_vertical_and_vacuum_runs_have_one_tolerance_rule_per_field(
    client: TestClient, params: dict[str, Any]
) -> None:
    # The registry case covers a 2-D run; these cover the null invariant (vertical) and the
    # null terminal speed (vacuum), whose rules must not divide by vx0 = 0 or use v_t = inf.
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


@pytest.mark.parametrize("seed", range(5))
def test_value_rules_survive_last_bit_differences_at_the_tightest_tolerance(
    monkeypatch: pytest.MonkeyPatch, seed: int
) -> None:
    # Another CPU changes the last bits of the arithmetic (another BLAS kernel in the error
    # norm, another LU in Radau). Emulated here by multiplying each drag evaluation by
    # 1 +- 1 or 2 ulp. At rtol = 1e-13 the solver works at rounding level, so a nearly
    # vertical flight's range moves by up to 5e-11 relative: the value rules must allow it.
    # (The counts n_steps and n_rhs_evaluations are exact by design, plan D8: a different
    # step sequence is a different computation, so they are left out here.)
    entry = get_entry(MODEL_ID)
    assert entry is not None
    inputs = {
        "parameters": {
            "initial_speed": 20.0,
            "launch_angle_deg": 89.9,
            "launch_height": 10.0,
            "drag_constant": 1.0,
        },
        "solver": {"method": "DOP853", "rtol": 1e-13, "atol": 1e-14},
        "n_samples": 10,
    }
    request = entry.rebuild(inputs, None)
    original = entry.summary(entry.compute(request))
    rules = entry.tolerances(inputs, original)

    exact_law = quadratic_numerical.drag_acceleration
    rng = random.Random(seed)

    def last_bits_differ(vx: float, vy: float, kappa: float) -> tuple[float, float]:
        ax, ay = exact_law(vx, vy, kappa)
        ulps = (-2, -1, 1, 2)
        return ax * (1 + rng.choice(ulps) * 2.0**-52), ay * (1 + rng.choice(ulps) * 2.0**-52)

    monkeypatch.setattr(quadratic_numerical, "drag_acceleration", last_bits_differ)
    replayed = entry.summary(entry.compute(request))
    counts = {"numerical.n_steps", "numerical.n_rhs_evaluations"}
    comparison = compare_summaries(original, replayed, rules)
    outside = [
        c.field for c in comparison.fields if c.field not in counts and not c.within_tolerance
    ]
    assert outside == [], [(c.field, c.original, c.replay) for c in comparison.fields]
