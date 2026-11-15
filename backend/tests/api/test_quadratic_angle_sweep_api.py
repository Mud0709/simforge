"""Seam 4: the quadratic-drag angle sweep over HTTP (roadmap 2.2, slice 3; plan D7, D8, D10, D11).

Expected values are independent of the code under test: the textbook vacuum range
v0^2 sin 2 theta / g and the closed-form optimum tan theta* = v0 / sqrt(v0^2 + 2 g h) are
written out here, every sweep point is compared with a separate request to the 2.1 endpoint
at that angle (RS2), the terminal speed is checked through the force balance c v_t^2 = m g,
and validation boundaries are worked by hand.
"""

from __future__ import annotations

import fnmatch
import json
import math
import random
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.api.registry import get_entry
from simforge.api.replay import compare_summaries
from simforge.physics.projectile import quadratic_numerical
from tests.api.test_replay import flat
from tests.approx import rel_approx

URL = "/api/v1/physics/projectile/quadratic-drag/angle-sweep"
SINGLE = "/api/v1/physics/projectile/quadratic-drag/simulate"
MODEL_ID = "physics.projectile.quadratic_angle_sweep"
G = 9.80665
# The edge case: v0 = 10 m/s from 1e5 m without drag has theta* = atan(10 / sqrt(100 +
# 2 g h)) = 0.409 degrees, so on a 10-degree grid the best grid point is 0 degrees and the
# uncertainty estimate u is null (it needs a centred second difference).
EDGE = {"initial_speed": 10.0, "launch_height": 1e5, "drag_constant": 0.0}


def strict(text: str) -> Any:
    return json.loads(text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def post(client: TestClient, params: dict[str, Any], **extra: Any) -> Any:
    return client.post(URL, json={"parameters": params, "save_experiment": False, **extra})


def post_raw(client: TestClient, body: str) -> Any:
    return client.post(URL, content=body, headers={"Content-Type": "application/json"})


def stored(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    run = client.post(URL, json={**body, "save_experiment": True})
    assert run.status_code == 200, run.text
    record: dict[str, Any] = client.get(
        f"/api/v1/experiments/{run.json()['metadata']['run_id']}"
    ).json()
    return record


# --- the contract ---------------------------------------------------------------------------


def test_default_request_returns_a_complete_labelled_result(client: TestClient) -> None:
    r = client.post(URL, json={})
    assert r.status_code == 200, r.text
    body = strict(r.text)
    assert body["model"]["id"] == MODEL_ID
    assert body["model"]["version"] == "1.0.1"
    assert body["units"]["drag_constant"] == "kg/m"
    assert body["units"]["angle"] == "deg"
    assert {a["id"] for a in body["assumptions"]} >= {"point_mass", "quadratic_drag"}
    assert "linear_drag" not in {a["id"] for a in body["assumptions"]}
    assert body["solver"]["method"] == "DOP853"
    # 91 angles (the default, 1-degree steps) from exactly 0 to exactly 90 degrees.
    n = 91
    for key in ("angles_deg", "ranges", "flight_times", "max_heights", "vacuum_ranges"):
        assert len(body[key]) == n, key
    assert body["angles_deg"][0] == 0.0
    assert body["angles_deg"][-1] == 90.0
    # 0 degrees from the ground is no flight, and 90 degrees lands where it started: both
    # exactly 0, for the drag curve and for the exact vacuum one.
    assert body["ranges"][0] == body["ranges"][-1] == 0.0
    assert body["vacuum_ranges"][0] == body["vacuum_ranges"][-1] == 0.0
    # The refined best is at least the best grid point (the grid point is kept otherwise).
    assert body["best_range"] >= max(body["ranges"])
    assert body["best_angle_uncertainty_deg"] is not None
    assert body["best_angle_uncertainty_deg"] > 0
    assert body["best_angle_note"].startswith("Estimate, not a bound")
    # One run per flown grid angle (90 of them) plus Brent's refinement runs.
    assert body["n_runs"] > n - 1
    assert 0 < body["n_rhs_evaluations"] <= 300_000
    assert body["checks"]
    assert all(c["passed"] is not False for c in body["checks"])
    assert {"interior_peaks", "sweep_cost"} <= {c["id"] for c in body["checks"]}
    assert body["method_note"].startswith("numerical")
    assert body["metadata"]["experiment_saved"] is True


def test_drag_lowers_the_best_angle_and_range_below_the_vacuum_ones(client: TestClient) -> None:
    # Observed for every drag strength measured (plan RS5), and proved to first order for weak
    # drag (RS3); the 2.1 defaults have eps = (v0/v_t)^2 = 0.41.
    body = post(client, {}, n_angles=31).json()
    assert body["vacuum_best_angle_deg"] == pytest.approx(45.0, abs=1e-12)
    assert body["best_angle_deg"] < body["vacuum_best_angle_deg"]
    assert body["best_range"] < body["vacuum_best_range"]


def test_terminal_speed_balances_weight_and_drag(client: TestClient) -> None:
    m, c = 0.057, 1.05e-3  # roughly a tennis ball: c = rho C_d A / 2
    body = post(client, {"mass": m, "drag_constant": c}, n_angles=10).json()
    v_t = body["terminal_speed"]
    # Force balance at terminal speed: c v_t^2 = m g (a few roundings: 1e-14 relative).
    assert c * v_t**2 == rel_approx(m * G, rel=1e-14)


@pytest.mark.parametrize("method", ["DOP853", "RK45", "Radau"])
def test_vacuum_sweep_from_the_ground_is_45_degrees_and_v0_squared_over_g(
    client: TestClient, method: str
) -> None:
    v0 = 10.0
    # 31 angles (3-degree steps): the closed forms hold at every grid angle, and 45 degrees is
    # a grid point either way.
    params = {"initial_speed": v0, "drag_constant": 0.0}
    r = post(client, params, solver={"method": method}, n_angles=31)
    assert r.status_code == 200, r.text
    body = strict(r.text)
    assert body["terminal_speed"] is None  # infinite: JSON has no infinity
    # Closed form, written out: theta* = 45 degrees, R* = v0^2 / g.
    assert body["vacuum_best_angle_deg"] == pytest.approx(45.0, abs=1e-12)
    assert body["vacuum_best_range"] == rel_approx(v0**2 / G, rel=1e-14)
    # The numerical optimum: Brent stops within ~sqrt(eps_mach) x 45 = 6.6e-7 degrees of the
    # computed curve's flat top (plan RS1, measured within 7e-7), so 1e-5 degrees; the range
    # at a flat top is insensitive to that (plan RS1: within 9e-16 relative), so 1e-12.
    assert body["best_angle_deg"] == pytest.approx(45.0, abs=1e-5)
    assert body["best_range"] == rel_approx(v0**2 / G, rel=1e-12)
    for angle, vac, num in zip(
        body["angles_deg"], body["vacuum_ranges"], body["ranges"], strict=True
    ):
        if angle == 90.0:
            # Exactly vertical (as in 2.1): exactly 0, where the plain textbook form gives
            # v0^2 sin(2 radians(90)) / g = 1.2e-15 m, since sin(pi) rounds to 1.2e-16.
            assert vac == num == 0.0
            continue
        textbook = v0**2 * math.sin(2 * math.radians(angle)) / G
        # Closed forms evaluated two ways: a few roundings, amplified near 90 degrees where
        # sin 2 theta is small (both are ~1e-16 absolute there), so a 1e-15 m floor.
        assert vac == pytest.approx(textbook, rel=1e-13, abs=1e-15)
        # Numerical against exact: the solver at rtol = atol = 1e-10 within 1e-9 (as the 2.1
        # API test for the same vacuum flight), plus the same floor.
        assert num == pytest.approx(textbook, rel=1e-9, abs=1e-15)


def test_vacuum_sweep_from_a_height_has_the_closed_form_optimum(client: TestClient) -> None:
    # v0 = 10 m/s, h = 15 m, g = 9.80665 m/s^2: tan theta* = v0 / sqrt(v0^2 + 2 g h), and
    # R* = (v0 / g) sqrt(v0^2 + 2 g h), written out here.
    v0, h = 10.0, 15.0
    root = math.sqrt(v0**2 + 2 * G * h)
    params = {"initial_speed": v0, "launch_height": h, "drag_constant": 0.0}
    body = post(client, params, n_angles=31).json()
    assert body["vacuum_best_angle_deg"] == pytest.approx(math.degrees(math.atan(v0 / root)))
    assert body["vacuum_best_range"] == rel_approx(v0 * root / G, rel=1e-14)
    assert body["best_angle_deg"] == pytest.approx(math.degrees(math.atan(v0 / root)), abs=1e-5)
    assert body["best_range"] == rel_approx(v0 * root / G, rel=1e-12)
    # From a height 0 degrees is a real flight: R = v0 sqrt(2 h / g).
    assert body["ranges"][0] == rel_approx(v0 * math.sqrt(2 * h / G), rel=1e-9)


def test_every_point_is_the_2_1_run_at_that_angle(client: TestClient) -> None:
    # RS2 through the API: each sweep point equals a separate request to the 2.1 endpoint at
    # the same angle, bit for bit (same machine, same operations).
    params = {"drag_constant": 0.05, "launch_height": 1.5}
    solver = {"method": "RK45"}
    body = post(client, params, solver=solver, n_angles=10).json()
    for k, angle in enumerate(body["angles_deg"]):
        single = post_single(client, {**params, "launch_angle_deg": angle}, solver)
        assert body["ranges"][k] == single["range"], angle
        assert body["flight_times"][k] == single["flight_time"], angle
        assert body["max_heights"][k] == single["max_height"], angle


def post_single(client: TestClient, params: dict[str, Any], solver: dict[str, Any]) -> Any:
    r = client.post(SINGLE, json={"parameters": params, "solver": solver, "save_experiment": False})
    assert r.status_code == 200, r.text
    return r.json()["numerical"]


def test_the_launch_angle_is_ignored_in_results_and_hash(client: TestClient) -> None:
    def run(params: dict[str, Any]) -> Any:
        r = post(client, params, n_angles=10)
        assert r.status_code == 200, r.text
        return r.json()

    # 0 degrees from the ground cannot fly as a single run, but a sweep ignores the angle.
    a, b = run({"launch_angle_deg": 0.0}), run({"launch_angle_deg": 70.0})
    assert a["parameters"]["launch_angle_deg"] == 0.0  # echoed, as the linear sweep does
    assert a["ranges"] == b["ranges"]
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]
    assert a["metadata"]["output_digest"] == b["metadata"]["output_digest"]


# --- validation -----------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["initial_speed", "drag_constant", "mass", "launch_height"])
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(client: TestClient, field: str, literal: str) -> None:
    r = post_raw(client, f'{{"parameters": {{"{field}": {literal}}}}}')
    assert r.status_code == 422
    detail = strict(r.text)
    assert detail["detail"][0]["loc"] == ["body", "parameters", field]


@pytest.mark.parametrize(
    "body", ['{"solver": {"atol": NaN}}', '{"solver": {"rtol": Infinity}}', '{"n_angles": NaN}']
)
def test_non_finite_settings_are_rejected(client: TestClient, body: str) -> None:
    r = post_raw(client, body)
    assert r.status_code == 422
    strict(r.text)


@pytest.mark.parametrize(
    "payload",
    [
        {"n_angles": 9},
        {"n_angles": 362},
        {"n_angles": 45.5},
        {"parameters": {"mass": 0}},
        {"parameters": {"drag_constant": -0.1}},
        {"parameters": {"drag_constant": 1.0001e6}},
        {"parameters": {"launch_angle_deg": 90.0001}},
        {"parameters": {"drag_coefficient": 0.1}},  # the linear model's b, not this c
        {"solver": {"method": "Euler"}},
        {"solver": {"rtol": 0.5}},
        {"angles": [10, 20]},
        {"n_samples": 10},  # the sweep keeps no series
        # The work budget is the server's limit, not a request field (plan D8).
        {"max_rhs_evaluations": 10**9},
    ],
)
def test_invalid_requests_are_rejected(client: TestClient, payload: dict[str, Any]) -> None:
    r = client.post(URL, json=payload)
    assert r.status_code == 422
    strict(r.text)


def test_stiff_sweep_with_an_explicit_method_is_refused_before_solving(
    client: TestClient,
) -> None:
    # A 100 km fall at v_t = 3 m/s travels at least kappa h = g h / v_t^2 ~ 1.1e5 drag lengths,
    # above the explicit-method limit of 1e4, at every angle. The guard names the worst one.
    params = {"launch_height": 1e5, "drag_constant": G / 9.0, "initial_speed": 10.0}
    r = post(client, params, solver={"method": "RK45"}, n_angles=10)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "Radau" in detail
    assert "drag lengths" in detail
    assert re.search(r"flight at \d+°", detail), detail


# --- reproducibility ------------------------------------------------------------------------


def test_identical_inputs_give_identical_hash_and_results(client: TestClient) -> None:
    payload = {"parameters": {"drag_constant": 0.03}, "n_angles": 10, "save_experiment": False}
    a, b = client.post(URL, json=payload).json(), client.post(URL, json=payload).json()
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]
    assert a["metadata"]["output_digest"] == b["metadata"]["output_digest"]
    assert a["ranges"] == b["ranges"]  # deterministic: bitwise-identical floats


def test_hash_ignores_the_save_flag_but_not_the_inputs(client: TestClient) -> None:
    def digest(payload: dict[str, Any]) -> str:
        return str(
            client.post(URL, json={"n_angles": 10, **payload}).json()["metadata"]["input_hash"]
        )

    base = digest({"save_experiment": False})
    assert base == digest({"save_experiment": True})
    assert base != digest({"parameters": {"drag_constant": 0.02}})
    assert base != digest({"solver": {"rtol": 1e-9}})
    assert base != digest({"n_angles": 11})


SUMMARY_FIELDS = {
    "best_angle_deg",
    "best_range",
    "best_angle_uncertainty_deg",
    "vacuum_best_angle_deg",
    "vacuum_best_range",
    "terminal_speed",
    "n_rhs_evaluations",
}


@pytest.mark.parametrize(
    "body",
    [
        {"n_angles": 10},
        {"parameters": {"drag_constant": 0.0, "launch_height": 3.0}, "n_angles": 10},
        {"parameters": EDGE, "n_angles": 10},
    ],
)
def test_stored_summary_fields_and_one_tolerance_rule_each(
    client: TestClient, body: dict[str, Any]
) -> None:
    # Plan D10: the headline numbers are stored, the curves and checks are shown, not stored.
    # The vacuum case has a null terminal speed and the edge case a null u: their rules must
    # keep null as null, and every rule must be finite with a reason.
    record = stored(client, body)
    summary = record["summary"]
    assert set(summary) == SUMMARY_FIELDS
    assert "launch_angle_deg" not in record["inputs"]["parameters"]
    assert set(record["inputs"]) == {"parameters", "solver", "n_angles"}
    entry = get_entry(MODEL_ID)
    assert entry is not None
    rules = entry.tolerances(record["inputs"], summary)
    for field in flat(summary):
        matching = [p for p in rules if fnmatch.fnmatchcase(field, p)]
        assert len(matching) == 1, (field, matching)
        rule = rules[matching[0]]
        assert rule.reason
        assert math.isfinite(rule.relative), field
        assert math.isfinite(rule.absolute), field
    replay = client.post(f"/api/v1/experiments/{record['run_id']}/replay", json={}).json()
    assert replay["verdict"] == "identical"


def test_the_edge_case_really_has_a_null_uncertainty(client: TestClient) -> None:
    body = post(client, EDGE, n_angles=10).json()
    assert max(range(10), key=lambda k: body["ranges"][k]) == 0
    assert body["best_angle_uncertainty_deg"] is None
    assert "edge" in body["best_angle_note"]


def test_the_best_angle_rule_is_at_least_the_stated_uncertainty(client: TestClient) -> None:
    # Plan D11: best_angle_deg agrees within max(1e-5 degrees, u), the run's own estimate.
    record = stored(client, {"n_angles": 31})
    entry = get_entry(MODEL_ID)
    assert entry is not None
    rule = entry.tolerances(record["inputs"], record["summary"])["best_angle_deg"]
    u = record["summary"]["best_angle_uncertainty_deg"]
    assert u > 1e-5
    assert (rule.relative, rule.absolute) == (0.0, u)


# Last-bit emulation: another CPU rounds the last bits of the arithmetic differently (another
# libm or BLAS kernel). Emulated by multiplying each drag evaluation by 1 +- 1 or 2 ulp, as the
# 2.1 slice 3 review did. The rules were derived from a measurement (892 reruns of 223 sweeps,
# recorded with the rules in api/routes/physics.py) in which every value stayed within its
# rule: at most 0.08 of the best angle's tolerance, 0.0023 of the best range's and 0.0025 of
# u's. This is a permanent sample of it, one rerun per case, kept as a regression guard: a
# change to a rule or to the model that breaks it on these cases fails here, on every push.
# Cases, one per method: the defaults on the default 91-angle grid; stronger drag from a
# height on the coarsest grid; Radau (at rtol = 1e-8, 3x cheaper than its default, the
# measurement covered rtol 1e-13 to 1e-6); and the tightest tolerances, where rounding
# dominates. Together 3 s (the earlier 10 reruns took 14 s).
EMULATION_CASES = [
    ({}, {"method": "DOP853"}, 91),
    ({"drag_constant": 0.1, "launch_height": 5.0}, {"method": "RK45"}, 10),
    (
        {"drag_constant": 0.01, "launch_height": 5.0},
        {"method": "Radau", "rtol": 1e-8, "atol": 1e-8},
        10,
    ),
    ({"drag_constant": 1.0}, {"method": "DOP853", "rtol": 1e-13, "atol": 1e-14}, 10),
]


@pytest.mark.parametrize(("params", "solver", "n_angles"), EMULATION_CASES)
def test_value_rules_survive_last_bit_differences(
    monkeypatch: pytest.MonkeyPatch,
    params: dict[str, Any],
    solver: dict[str, Any],
    n_angles: int,
) -> None:
    # The count n_rhs_evaluations is exact by design (plan D11: a different step sequence is a
    # different computation), so it is left out here, as in the 2.1 test.
    entry = get_entry(MODEL_ID)
    assert entry is not None
    full_solver = {"method": "DOP853", "rtol": 1e-10, "atol": 1e-10, **solver}
    inputs = {
        "parameters": {
            "initial_speed": 20.0,
            "launch_height": 0.0,
            "mass": 1.0,
            "drag_constant": 0.01,
            "gravity": G,
            **params,
        },
        "solver": full_solver,
        "n_angles": n_angles,
    }
    request = entry.rebuild(inputs, None)
    original = entry.summary(entry.compute(request))
    rules = entry.tolerances(inputs, original)

    exact_law = quadratic_numerical.drag_acceleration
    rng = random.Random(0)

    def last_bits_differ(vx: float, vy: float, kappa: float) -> tuple[float, float]:
        ax, ay = exact_law(vx, vy, kappa)
        ulps = (-2, -1, 1, 2)
        return ax * (1 + rng.choice(ulps) * 2.0**-52), ay * (1 + rng.choice(ulps) * 2.0**-52)

    monkeypatch.setattr(quadratic_numerical, "drag_acceleration", last_bits_differ)
    replayed = entry.summary(entry.compute(request))
    comparison = compare_summaries(original, replayed, rules)
    outside = [
        c.field
        for c in comparison.fields
        if c.field != "n_rhs_evaluations" and not c.within_tolerance
    ]
    assert outside == [], [(c.field, c.original, c.replay) for c in comparison.fields]
