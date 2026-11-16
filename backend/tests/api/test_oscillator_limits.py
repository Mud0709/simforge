"""Input limits of the harmonic oscillator (plan D6, slice 3): a result or a 422, never a 500.

``schemas.py`` validation was deferred from slice 2 to here. Every limit is checked through
HTTP at its boundary, with values worked out by hand, and every refusal must (a) be a 422
whose message names the limit's number and (b) store nothing in the experiment log.

Single fields (SI): m 1e-6 to 1e6 kg, k 1e-6 to 1e9 N/m, b 0 to 1e6 kg/s, F0 0 to 1e6 N,
w 0 to 1e4 rad/s, x0 -1e3 to 1e3 m, v0 -1e4 to 1e4 m/s, duration > 0 to 1e6 s, n_samples
10 to 5000; NaN and +-Infinity refused for every field. Combined rules: w0 from 1e-3 to 1e4
rad/s; gamma = b/2m at most 1e4 1/s (the drag-rate limit); w at most 100 w0; Q at most 1e4
when b > 0; at most 500 cycles, duration max(w0, w) / 2 pi; max(w0, w, gamma) duration at least
1 (w counts in both only when driven); not all of x0, v0, F0 zero; explicit methods refused
when the stiffness number exceeds 1e4 (the model's guard); and the run-cost rule, a budget of
right-hand-side evaluations per run (``model.MAX_RUN_RHS_EVALUATIONS``).
"""

from __future__ import annotations

import itertools
import json
import math
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.physics.oscillator import model

URL = "/api/v1/physics/oscillator/simulate"
LOG = "/api/v1/experiments"
TWO_PI = 2 * math.pi
# Wall time per request in the corners test. The run-cost budget bounds a run's evaluations;
# it is measured so that the slowest allowed run (Radau at the tightest pair) stays well
# inside the 30 s after which the Next.js proxy gives up (found in 2.2, B2). 25 s leaves a
# margin for a slower machine; a request beyond it would leave the page waiting, so the test
# fails (as the 2.2 sweep's corners test).
SECONDS_PER_REQUEST = 25.0
FIELDS = (
    "mass",
    "spring_constant",
    "damping_coefficient",
    "drive_amplitude",
    "drive_angular_frequency",
    "initial_displacement",
    "initial_velocity",
    "duration",
)


def post(client: TestClient, params: dict[str, Any], **extra: Any) -> Any:
    return client.post(URL, json={"parameters": params, "save_experiment": False, **extra})


def post_raw(client: TestClient, body: str) -> Any:
    return client.post(URL, content=body, headers={"Content-Type": "application/json"})


def message(r: Any) -> str:
    detail = r.json()["detail"]
    return detail if isinstance(detail, str) else " ".join(d.get("msg", "") for d in detail)


def explained(r: Any) -> bool:
    """A 422 whose detail actually says something (a sentence, not just a status)."""
    return len(message(r)) > 30


def refused(client: TestClient, params: dict[str, Any], **extra: Any) -> str:
    """POST with saving on; assert a 422 and an empty experiment log; return the message."""
    r = client.post(URL, json={"parameters": params, "save_experiment": True, **extra})
    assert r.status_code == 422, r.text
    assert client.get(LOG).json() == [], "a refused run was stored"
    return message(r)


def accepted(client: TestClient, params: dict[str, Any], **extra: Any) -> dict[str, Any]:
    r = post(client, params, **extra)
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


# --- non-finite numbers ---------------------------------------------------------------------


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(client: TestClient, field: str, literal: str) -> None:
    r = post_raw(client, f'{{"parameters": {{"{field}": {literal}}}}}')
    assert r.status_code == 422
    detail = json.loads(r.text, parse_constant=lambda c: pytest.fail(f"non-finite {c}"))
    assert detail["detail"][0]["loc"] == ["body", "parameters", field]
    assert client.get(LOG).json() == []


@pytest.mark.parametrize("setting", ["rtol", "atol"])
def test_non_finite_solver_settings_are_rejected(client: TestClient, setting: str) -> None:
    assert post_raw(client, f'{{"solver": {{"{setting}": NaN}}}}').status_code == 422


# --- single-field bounds ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "bound"),
    [
        ("mass", 0.99e-6, 1e-6),
        ("mass", 1.0001e6, 1e6),
        ("spring_constant", 0.99e-6, 1e-6),
        ("spring_constant", 1.0001e9, 1e9),
        ("damping_coefficient", -0.1, 0),
        ("damping_coefficient", 1.0001e6, 1e6),
        ("drive_amplitude", -0.1, 0),
        ("drive_amplitude", 1.0001e6, 1e6),
        ("drive_angular_frequency", -0.1, 0),
        ("drive_angular_frequency", 1.0001e4, 1e4),
        ("initial_displacement", -1.0001e3, -1e3),
        ("initial_displacement", 1.0001e3, 1e3),
        ("initial_velocity", -1.0001e4, -1e4),
        ("initial_velocity", 1.0001e4, 1e4),
        ("duration", 0.0, 0),
        ("duration", -1.0, 0),
        ("duration", 1.0001e6, 1e6),
    ],
)
def test_each_field_bound_is_refused_with_its_number(
    client: TestClient, field: str, value: float, bound: float
) -> None:
    r = client.post(URL, json={"parameters": {field: value}, "save_experiment": True})
    assert r.status_code == 422, r.text
    first = r.json()["detail"][0]
    assert first["loc"] == ["body", "parameters", field]
    assert str(bound) in first["msg"], first["msg"]  # e.g. "greater than or equal to 1e-06"
    assert client.get(LOG).json() == []


def test_invalid_request_settings_are_rejected(client: TestClient) -> None:
    assert client.post(URL, json={"solver": {"method": "Euler"}}).status_code == 422
    assert client.post(URL, json={"solver": {"rtol": 0.5}}).status_code == 422
    assert client.post(URL, json={"n_samples": 9}).status_code == 422
    assert client.post(URL, json={"n_samples": 5001}).status_code == 422
    assert client.post(URL, json={"unknown": 1}).status_code == 422
    assert client.post(URL, json={"parameters": {"drag_coefficient": 0.1}}).status_code == 422
    assert client.post(URL, json={"parameters": {"mass": "heavy"}}).status_code == 422


# --- combined rules ---------------------------------------------------------------------------


def test_natural_frequency_below_its_floor_is_refused(client: TestClient) -> None:
    # w0 = sqrt(k/m): sqrt(1e-6 / 0.25) = 2e-3 rad/s is allowed (T = 1000 s: w0 T = 2 >= 1,
    # 0.32 cycles); sqrt(1e-6 / 4) = 5e-4 rad/s is below 1e-3.
    base = {"spring_constant": 1e-6, "damping_coefficient": 0.0, "duration": 1000.0}
    accepted(client, {**base, "mass": 0.25})
    text = refused(client, {**base, "mass": 4.0})
    assert "w0" in text
    assert "0.001" in text


def test_natural_frequency_above_its_ceiling_is_refused(client: TestClient) -> None:
    # sqrt(99.9999 / 1e-6) = 9999.995 rad/s is allowed (T = 0.01 s: 15.9 cycles, w0 T = 100);
    # sqrt(1e9 / 1e-6) = 3.2e7 rad/s is above 1e4.
    base = {"mass": 1e-6, "damping_coefficient": 0.0, "duration": 0.01}
    accepted(client, {**base, "spring_constant": 99.9999})
    text = refused(client, {**base, "spring_constant": 1e9})
    assert "w0" in text
    assert "10000" in text


def test_damping_rate_limit(client: TestClient) -> None:
    # gamma = b / 2m with m = 0.5 kg: b = 1e4 kg/s gives exactly 1e4 1/s (allowed; strongly
    # overdamped, so Radau), b = 1.0001e4 gives 1.0001e4 1/s (refused). k = 50: w0 = 10.
    base = {"mass": 0.5, "spring_constant": 50.0, "duration": 1.0}
    accepted(client, {**base, "damping_coefficient": 1e4}, solver={"method": "Radau"})
    text = refused(client, {**base, "damping_coefficient": 1.0001e4}, solver={"method": "Radau"})
    assert "damping rate" in text
    assert "10000" in text


def test_drive_frequency_at_most_100_w0(client: TestClient) -> None:
    # Defaults: w0 = 5 rad/s, so w <= 500 rad/s. T = 5 s keeps 500 rad/s within 500 cycles
    # (5 x 500 / 2 pi = 398).
    base = {"drive_amplitude": 1.0, "duration": 5.0}
    accepted(client, {**base, "drive_angular_frequency": 500.0})
    text = refused(client, {**base, "drive_angular_frequency": 500.001})
    assert "100 w0" in text
    assert "500" in text
    # Without a drive (F0 = 0) the frequency limits nothing (slice 2 review, item 4).
    accepted(client, {"drive_amplitude": 0.0, "drive_angular_frequency": 1e4})


def test_quality_factor_at_most_1e4_when_damped(client: TestClient) -> None:
    # m = k = 1: Q = sqrt(mk)/b = 1/b. b = 1.0001e-4 gives Q = 9999 (allowed); b = 0.9999e-4
    # gives Q = 10001 (refused); b = 0 is undamped and exact (allowed).
    base = {"mass": 1.0, "spring_constant": 1.0, "initial_displacement": 1.0}
    accepted(client, {**base, "damping_coefficient": 1.0001e-4})
    accepted(client, {**base, "damping_coefficient": 0.0})
    text = refused(client, {**base, "damping_coefficient": 0.9999e-4})
    assert "quality factor" in text
    assert "1e4" in text


def test_at_most_500_cycles(client: TestClient) -> None:
    # Defaults: w0 = 5 rad/s, so 500 cycles last 500 x 2 pi / 5 = 628.32 s.
    limit = model.MAX_CYCLES * TWO_PI / 5.0
    accepted(client, {"duration": limit * (1 - 1e-9)})
    text = refused(client, {"duration": limit * (1 + 1e-9)})
    assert "cycles" in text
    assert "500" in text


def test_a_drive_faster_than_w0_sets_the_cycles(client: TestClient) -> None:
    # Driven at w = 50 rad/s = 10 w0: 500 cycles last 500 x 2 pi / 50 = 62.83 s.
    limit = model.MAX_CYCLES * TWO_PI / 50.0
    base = {"drive_amplitude": 1.0, "drive_angular_frequency": 50.0}
    accepted(client, {**base, "duration": limit * (1 - 1e-9)}, solver={"rtol": 1e-6})
    text = refused(client, {**base, "duration": limit * (1 + 1e-9)})
    assert "500" in text
    # Undriven, the same w counts for nothing: 62.9 s is 50 cycles of w0.
    accepted(client, {"drive_angular_frequency": 50.0, "duration": limit * (1 + 1e-9)})


@pytest.mark.parametrize(
    ("params", "rate"),
    [
        ({}, 5.0),  # w0 = 5 rad/s
        ({"drive_amplitude": 1.0, "drive_angular_frequency": 50.0}, 50.0),  # w = 50 > w0
        ({"damping_coefficient": 200.0}, 100.0),  # gamma = b/2m = 100 > w0
    ],
)
def test_minimum_duration_is_one_over_the_fastest_rate(
    client: TestClient, params: dict[str, Any], rate: float
) -> None:
    # max(w0, w, gamma) T >= 1 (slice 1, measured): T = 1/rate is the shortest run.
    accepted(client, {**params, "duration": (1 / rate) * (1 + 1e-9)})
    text = refused(client, {**params, "duration": (1 / rate) * (1 - 1e-9)})
    assert "too short" in text
    assert "lengthen duration" in text


def test_an_undriven_drive_frequency_does_not_shorten_the_minimum(client: TestClient) -> None:
    # F0 = 0: w = 50 does not count, so T = 0.021 s is w0 T = 0.105 < 1.
    text = refused(client, {"drive_angular_frequency": 50.0, "duration": 0.021})
    assert "too short" in text


def test_nothing_moving_is_refused(client: TestClient) -> None:
    params = {"initial_displacement": 0.0, "initial_velocity": 0.0, "drive_amplitude": 0.0}
    text = refused(client, params)
    assert "nothing moves" in text.lower()


def test_stiffness_rule_at_its_boundary(client: TestClient) -> None:
    # m = 1, k = 25, b = 1000: gamma = 500, beta = sqrt(500^2 - 25), fastest decay rate
    # gamma + beta. The stiffness number (gamma + beta) T may reach 1e4 for explicit methods.
    fastest = 500.0 + math.sqrt(250_000.0 - 25.0)
    t_limit = 1e4 / fastest  # about 10 s, 8 cycles
    params = {"damping_coefficient": 1000.0}
    ok = accepted(client, {**params, "duration": t_limit * (1 - 1e-9)}, solver={"method": "RK45"})
    assert ok["diagnostics"]["stiffness_number"] <= 1e4
    text = refused(client, {**params, "duration": t_limit * (1 + 1e-9)}, solver={"method": "RK45"})
    assert "stiffness number" in text
    assert "1e+04" in text
    assert "Radau" in text
    accepted(client, {**params, "duration": t_limit * (1 + 1e-9)}, solver={"method": "Radau"})


# --- the run-cost rule ------------------------------------------------------------------------

# Slice 2's item 1: w0 = 1 rad/s driven at w = 100 w0 for just under 500 cycles (31.4 s:
# 499.7 cycles). Radau at the tightest pair ran for 792 s on it before the budget.
FAST_DRIVE = {
    "mass": 1.0,
    "spring_constant": 1.0,
    "damping_coefficient": 0.1,
    "drive_amplitude": 1.0,
    "drive_angular_frequency": 100.0,
    "initial_displacement": 0.0,
    "duration": 31.4,
}
TIGHT = {"rtol": 1e-13, "atol": 1e-14}  # the tightest pair allowed


def test_a_run_over_the_budget_is_refused_quickly_and_says_what_to_change(
    client: TestClient,
) -> None:
    start = time.perf_counter()
    text = refused(client, FAST_DRIVE, solver={"method": "Radau", **TIGHT})
    seconds = time.perf_counter() - start
    assert seconds < SECONDS_PER_REQUEST, seconds
    assert f"{model.MAX_RUN_RHS_EVALUATIONS:,}" in text
    assert "right-hand-side evaluations" in text
    assert "looser tolerance" in text
    assert "fewer cycles" in text
    assert "another method" in text
    # The same motion at the loosest pair is far under the budget (measured: 68 692
    # evaluations, 2.3 s), and runs.
    loose = accepted(client, FAST_DRIVE, solver={"method": "Radau", "rtol": 1e-3, "atol": 0.1})
    assert loose["numerical"]["n_rhs_evaluations"] <= model.MAX_RUN_RHS_EVALUATIONS


# --- every corner of the allowed space --------------------------------------------------------

MASSES = (1e-6, 1e6)
W0_TARGETS = (1e-3, 1e4)  # k is clamped into [1e-6, 1e9], so not every target is reached
DAMPINGS = ("none", "lightest", "critical", "largest")
DRIVES = ("off", "static", "fastest")
DURATIONS = ("shortest", "longest")
METHODS = ("RK45", "DOP853", "Radau")
TIGHT_PAIR = (1e-13, 1e-14)
LOOSE_PAIR = (1e-3, 1e-1)
BUDGET_MESSAGE = "right-hand-side evaluations"


def _unit_corner(
    mass: float, w0_target: float, damping: str, drive: str, length: str
) -> dict[str, float]:
    """One corner of the single-field and combined limits, each just inside its rule."""
    k = min(max(mass * w0_target**2, 1e-6), 1e9)
    w0 = math.sqrt(k / mass)
    root_mk = math.sqrt(mass * k)
    b = {
        "none": 0.0,
        "lightest": root_mk / 1e4 * (1 + 1e-9),  # Q just under 1e4
        "critical": min(2 * root_mk, 1e6),  # b^2 = 4mk to rounding, where b <= 1e6 allows
        "largest": min(1e6, 2 * mass * 1e4) * (1 - 1e-9),  # gamma just under 1e4
    }[damping]
    f0, w = {
        "off": (0.0, 0.0),
        "static": (1e6, 0.0),
        "fastest": (1e6, min(1e4, 100 * w0) * (1 - 1e-9)),
    }[drive]
    fastest_rate = max(w0, w, b / (2 * mass))
    fastest_cycle = max(w0, w)
    duration = (
        (1 / fastest_rate) * (1 + 1e-9)
        if length == "shortest"
        else min(1e6, model.MAX_CYCLES * TWO_PI / fastest_cycle) * (1 - 1e-9)
    )
    return {
        "mass": mass,
        "spring_constant": k,
        "damping_coefficient": b,
        "drive_amplitude": f0,
        "drive_angular_frequency": w,
        "initial_displacement": 1e3,
        "initial_velocity": -1e4,
        "duration": duration,
    }


# The costly corners. The motion depends on the inputs only through zeta, w/w0, the scaled
# initial state and the drive strength F0/(kX) and w0 T (the scaled equation, plan D5), so the
# cost of a run is probed at m = k = 1 (w0 = 1 rad/s) for 500 cycles (just inside the limit);
# the unit corners above probe the representability of extreme units with the same motions.
COST_CORNERS: dict[str, dict[str, float]] = {
    "free, Q = 1e4": {"damping_coefficient": 1e-4 * (1 + 1e-9), "initial_displacement": 1.0},
    "free, undamped": {"damping_coefficient": 0.0, "initial_displacement": 1.0},
    "w = 100 w0, zeta = 0.05": {
        "damping_coefficient": 0.1,
        "drive_amplitude": 1.0,
        "drive_angular_frequency": 100.0 * (1 - 1e-9),
    },
    "w = 100 w0, undamped": {
        "damping_coefficient": 0.0,
        "drive_amplitude": 1.0,
        "drive_angular_frequency": 100.0 * (1 - 1e-9),
    },
    "w = w0, Q = 1e4": {
        "damping_coefficient": 1e-4 * (1 + 1e-9),
        "drive_amplitude": 1.0,
        "drive_angular_frequency": 1.0,
    },
    "w = w0 / 100, Q = 1e4": {
        "damping_coefficient": 1e-4 * (1 + 1e-9),
        "drive_amplitude": 1.0,
        "drive_angular_frequency": 1e-2,
    },
    "gamma = 1e4 (stiff)": {"damping_coefficient": 2e4 * (1 - 1e-9), "initial_displacement": 1.0},
}


def _cost_corner(name: str) -> dict[str, float]:
    p = {
        "mass": 1.0,
        "spring_constant": 1.0,
        "initial_displacement": 0.0,
        "initial_velocity": 0.0,
        **COST_CORNERS[name],
    }
    driven = p.get("drive_amplitude", 0.0) > 0
    fastest_cycle = max(1.0, p.get("drive_angular_frequency", 0.0) if driven else 0.0)
    p["duration"] = model.MAX_CYCLES * TWO_PI / fastest_cycle * (1 - 1e-9)
    return p


def _tight_kept(name: str, method: str) -> bool:
    """Whether a tightest-pair request on this cost corner is made (the rest are thinned).

    Measured when this test was written (no budget yet; one machine): at the tightest pair
    DOP853 made 318 000 to 330 000 evaluations (2.3 to 2.5 s) on the four corners whose
    fastest motion is w0, 401 000 and 538 000 (3.2 and 3.6 s) at w = 100 w0; RK45 1.2e6 to
    2.07e6 (12 to 20 s). A budget refusal is the same check on every corner (the count is
    taken in the right-hand side), so each explicit method keeps its costliest corners:
    DOP853 w = 100 w0 undamped (the most evaluations) and Q = 1e4 at resonance (the w0
    group); RK45 free undamped (the most evaluations, 18.6 s unbounded: a lax budget fails the
    ceiling). Radau keeps w = 100 w0, zeta = 0.05 (slice 2's 792 s run: plan check 3) and the
    stiff corner (3 646 evaluations, 0.1 s), the case Radau exists for; RADAU_TIGHT_EXTRA adds
    the others measured to stay cheap.
    """
    if method == "DOP853":
        return name in ("w = 100 w0, undamped", "w = w0, Q = 1e4")
    if method == "RK45":
        return name in ("free, undamped", "gamma = 1e4 (stiff)")  # the stiff one: the guard
    return name in ("w = 100 w0, zeta = 0.05", "gamma = 1e4 (stiff)", *RADAU_TIGHT_EXTRA)


RADAU_TIGHT_EXTRA: tuple[str, ...] = ()


def _check_request(
    client: TestClient, params: dict[str, Any], solver: dict[str, Any], tally: dict[str, Any]
) -> None:
    start = time.perf_counter()
    r = post(client, params, solver=solver)
    seconds = time.perf_counter() - start
    where = (params, solver, r.text[:300])
    tally["slowest"] = max(tally["slowest"], (seconds, repr((params, solver))))
    assert seconds < SECONDS_PER_REQUEST, (seconds, where)
    assert r.status_code in (200, 422), where
    if r.status_code == 422:
        tally["refused"] += 1
        assert explained(r), where
        if BUDGET_MESSAGE in r.text:
            tally["over_budget"] += 1
            assert f"{model.MAX_RUN_RHS_EVALUATIONS:,}" in r.text, where
        return
    tally["ran"] += 1
    body = r.json()
    json.loads(r.text, parse_constant=lambda c: pytest.fail(f"non-finite {c} at {where}"))
    assert body["numerical"]["n_rhs_evaluations"] <= model.MAX_RUN_RHS_EVALUATIONS, where
    x_scale = body["derived"]["scale"]
    assert math.isfinite(x_scale), where
    assert x_scale > 0, where
    # X is a proved bound on |x| (slice 1, decision B); the exact column must respect it
    # (to rounding: 1e-9 relative is far above the exact solution's error, slice 1).
    assert max(abs(x) for x in body["series"]["x_exact"]) <= x_scale * (1 + 1e-9), where
    # A failed accuracy check is reported, not asserted: this test is about crashes, refusals
    # and time (plan slice 3). Observed when it was written (current model.run, no HTTP): the
    # energy balance failed at m = 1e-6 kg, k = 1e-6 N/m, gamma just under 1e4 1/s, F0 = 1e6 N,
    # shortest duration (static and fastest drive), at the default solver.
    failed = [c["id"] for c in body["checks"] if c["passed"] is False]
    if failed:
        tally["failed_checks"].append((failed, params, solver))


def test_corners_of_the_allowed_space_never_crash_and_finish_in_time(client: TestClient) -> None:
    # 1. Unit corners (mass, w0, damping, drive, duration) just inside every rule: the
    #    shortest runs at the default pair, the longest at the loosest pair, with DOP853
    #    (Radau for the largest damping); their motions' costs are probed in part 2.
    # 2. Cost corners at m = k = 1 for 500 cycles: every method at the loosest pair, and the
    #    tightest pair where it is kept (_tight_kept).
    # Every request returns a result or a 422 that explains why, never a 500, within
    # SECONDS_PER_REQUEST; and the budget refusal is exercised.
    tally: dict[str, Any] = {
        "ran": 0,
        "refused": 0,
        "over_budget": 0,
        "slowest": (0.0, ""),
        "failed_checks": [],
    }
    total_start = time.perf_counter()
    for corner in itertools.product(MASSES, W0_TARGETS, DAMPINGS, DRIVES, DURATIONS):
        params = _unit_corner(*corner)
        # The largest damping is stiff (gamma T up to 6e7): explicit methods are refused by the
        # guard there at once, so Radau runs it; the guard itself is tested above.
        method = "Radau" if corner[2] == "largest" else "DOP853"
        if corner[-1] == "shortest":
            solver: dict[str, Any] = {"method": method}
        else:
            solver = {"method": method, "rtol": LOOSE_PAIR[0], "atol": LOOSE_PAIR[1]}
        _check_request(client, params, solver, tally)
    for name in COST_CORNERS:
        params = _cost_corner(name)
        for method in METHODS:
            pairs = [LOOSE_PAIR] + ([TIGHT_PAIR] if _tight_kept(name, method) else [])
            for rtol, atol in pairs:
                _check_request(
                    client, params, {"method": method, "rtol": rtol, "atol": atol}, tally
                )
    assert tally["ran"] > 0
    assert tally["refused"] > 0
    assert tally["over_budget"] > 0  # Radau at the tightest pair, w = 100 w0, at least
    seconds, where = tally["slowest"]
    print(
        f"oscillator corners: {tally['ran']} ran, {tally['refused']} refused "
        f"({tally['over_budget']} over budget) in {time.perf_counter() - total_start:.1f} s; "
        f"slowest {seconds:.2f} s: {where}; failed checks (reported): {tally['failed_checks']}"
    )
