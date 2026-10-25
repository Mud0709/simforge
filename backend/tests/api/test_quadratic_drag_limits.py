"""Input limits of the quadratic-drag model (plan D6, slice 3): a result or a 422, never a 500.

Limits: the linear model's floors and ceilings (mass >= 1e-6 kg, speed 1e-3 to 1e4 m/s,
height up to 1e5 m, g from 0.01 to 1000 m/s^2), c from 0 to 1e6 kg/m, and three combined
rules, each checked here at its boundary with values worked out by hand:

* the largest drag rate in the flight, kappa max(v0, v_t), is at most 1e4 s^-1 (by R7 i the
  speed never exceeds max(v0, v_t)); kappa v_t = sqrt(kappa g), so c = 0 needs no 0 * inf;
* the solver's absolute tolerance atol is at most 1% of the smallest velocity scale,
  min(v0, v_t): far above it the velocity is not error-controlled, and runs became very
  slow (measured: up to 10 s at 10 times the scale, timeouts and overflow at 100 times;
  at 0.1 times one run already missed its own accuracy check, at 0.01 none did);
* the flight must last at least 1 microsecond without drag: SciPy locates the landing only
  to about 1e-15 s, and much shorter flights crashed the run.
"""

from __future__ import annotations

import itertools
import math
import re
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.physics.projectile.quadratic_schemas import (
    QuadraticDragParameters,
    QuadraticDragRequest,
)
from tests.approx import rel_approx

URL = "/api/v1/physics/projectile/quadratic-drag/simulate"
G = 9.80665
ATOL_FRACTION = 0.01  # the stated fraction of min(v0, v_t)
MIN_FLIGHT_TIME = 1e-6  # s, without drag
# Time budget per request in the corners test. Measured in slice 3: the slowest corner is
# Radau at rtol = 1e-13 on the strongest drag at v0 = 1e4 m/s, 2-3.3 s on the development
# machine (under load); everything else is under 0.3 s. 10 s leaves room for a slower CI
# runner; a run beyond it would make the page unusable, so the test fails.
SECONDS_PER_REQUEST = 10.0


def post(client: TestClient, params: dict[str, Any], **extra: Any) -> Any:
    return client.post(URL, json={"parameters": params, "save_experiment": False, **extra})


def explained(r: Any) -> bool:
    """A 422 whose detail actually says something (a sentence, not just a status)."""
    detail = r.json()["detail"]
    text = detail if isinstance(detail, str) else " ".join(d.get("msg", "") for d in detail)
    return len(text) > 30


# --- the drag-rate limit, kappa max(v0, v_t) <= 1e4 s^-1 -------------------------------------


def test_drag_rate_limit_on_the_launch_speed_branch() -> None:
    # m = 1 kg, v0 = 1e4 m/s, c = 1 kg/m: kappa v0 = 1e4 exactly, and v_t = sqrt(g) < v0.
    QuadraticDragParameters(mass=1.0, initial_speed=1e4, drag_constant=1.0)
    with pytest.raises(ValueError, match="drag rate"):
        QuadraticDragParameters(mass=1.0, initial_speed=1e4, drag_constant=1.000001)


def test_drag_rate_limit_on_the_terminal_speed_branch() -> None:
    # g = 1000, kappa = 1e5 1/m: kappa v_t = sqrt(kappa g) = sqrt(1e8) = 1e4 exactly, while
    # kappa v0 = 100 at v0 = 1e-3 m/s. A rule on kappa v0 alone would accept c = 1.0001e5.
    base = {"mass": 1.0, "initial_speed": 1e-3, "gravity": 1000.0, "launch_height": 1.0}
    QuadraticDragParameters(**base, drag_constant=1e5)
    with pytest.raises(ValueError, match="drag rate"):
        QuadraticDragParameters(**base, drag_constant=1.0001e5)


def test_drag_rate_limit_through_http_names_the_rule(client: TestClient) -> None:
    r = post(client, {"mass": 1e-3, "drag_constant": 100.0})  # kappa v0 = 2e6 s^-1
    assert r.status_code == 422
    assert "drag rate" in r.text


@pytest.mark.parametrize("mass", [1e-6, 1e6])
@pytest.mark.parametrize("drag_constant", [0.0, 5e-324])
def test_vacuum_and_subnormal_drag_constants_run(
    client: TestClient, mass: float, drag_constant: float
) -> None:
    # c = 0 has v_t = inf (kappa v_t would be 0 * inf); a subnormal c has a huge but finite
    # v_t and, at m = 1e6 kg, a kappa that underflows to 0. Each must run, never crash.
    r = post(client, {"mass": mass, "drag_constant": drag_constant})
    assert r.status_code == 200, r.text
    body = r.json()
    if drag_constant == 0:
        assert body["terminal_speed"] is None
    else:
        assert body["terminal_speed"] > 1e100
    # Drag this weak is invisible: the range is the vacuum one, to the solver's accuracy.
    assert body["numerical"]["range"] == rel_approx(body["vacuum"]["range"], rel=1e-9)


# --- the absolute-tolerance rule, atol <= 0.01 min(v0, v_t) --------------------------------


def test_atol_rule_in_vacuum_uses_the_launch_speed(client: TestClient) -> None:
    params = {"initial_speed": 0.5, "drag_constant": 0.0}  # min(v0, inf) = 0.5 m/s
    assert post(client, params, solver={"atol": 0.005}).status_code == 200
    r = post(client, params, solver={"atol": 0.00500001})
    assert r.status_code == 422
    assert "atol" in r.text
    assert "0.005" in r.text  # it says how small atol must be


@pytest.mark.parametrize("v0", [0.12356, 0.5, 0.7777, 3.14159])
def test_the_atol_the_refusal_suggests_is_accepted(client: TestClient, v0: float) -> None:
    # In vacuum the limit is 0.01 v0: 0.0012356 m/s at v0 = 0.12356. Rounded to the nearest
    # 3 significant figures that would read 0.00124, above the limit, so the advice would
    # be refused; it must be rounded down (0.00123).
    params = {"initial_speed": v0, "drag_constant": 0.0}
    r = post(client, params, solver={"atol": 0.1})
    assert r.status_code == 422
    suggested = float(re.search(r"use atol <= ([0-9.e+-]+)", r.text).group(1))  # type: ignore[union-attr]
    assert suggested <= ATOL_FRACTION * v0
    assert suggested >= 0.99 * ATOL_FRACTION * v0  # still says how small, to 3 figures
    ok = post(client, params, solver={"atol": suggested})
    assert ok.status_code == 200, ok.text


def test_atol_rule_with_drag_uses_the_terminal_speed(client: TestClient) -> None:
    # v0 = 20 m/s and c = m g / 0.25, so v_t = 0.5 m/s (to rounding) < v0: the limit is 0.005.
    params = {"initial_speed": 20.0, "drag_constant": G / 0.25}
    ok = post(client, params, solver={"atol": 0.005 * (1 - 1e-9)})
    assert ok.status_code == 200, ok.text
    r = post(client, params, solver={"atol": 0.005 * (1 + 1e-9)})
    assert r.status_code == 422
    assert "terminal speed" in r.text


def test_the_slow_case_found_in_slice_2_is_refused_at_once(client: TestClient) -> None:
    # g = 0.01 m/s^2, v0 = 1e-3 m/s, kappa = 1e7 1/m: v_t = sqrt(g / kappa) = 3.2e-5 m/s, and
    # atol = 1e-3 is 32 times that. Radau ran for over 20 s on such runs before this rule.
    params = {
        "gravity": 0.01,
        "initial_speed": 1e-3,
        "mass": 0.1,
        "drag_constant": 1e6,  # kappa = c/m = 1e7 1/m
        "launch_height": 1e5,
        "launch_angle_deg": 90.0,
    }
    start = time.perf_counter()
    r = post(client, params, solver={"method": "Radau", "rtol": 1e-3, "atol": 1e-3})
    assert time.perf_counter() - start < 1.0
    assert r.status_code == 422
    assert "terminal speed" in r.text
    # The same flight at an atol the rule allows runs, and fast (measured: well under 0.1 s).
    ok = post(client, params, solver={"method": "Radau", "rtol": 1e-3, "atol": 3e-7})
    assert ok.status_code == 200, ok.text


def test_atol_rule_lives_on_the_request_not_the_solver_settings() -> None:
    # The shared SolverSettings are unchanged (the linear model uses them); only this
    # model's request combines atol with the velocity scale.
    params = {"initial_speed": 0.5, "drag_constant": 0.0}
    with pytest.raises(ValueError, match="atol"):
        QuadraticDragRequest.model_validate({"parameters": params, "solver": {"atol": 0.006}})


# --- the flight must last at least 1 microsecond ---------------------------------------------


def test_a_flight_shorter_than_a_microsecond_is_refused(client: TestClient) -> None:
    # From the ground in vacuum the flight lasts 2 v0 sin(theta) / g. With v0 = 1e-3 m/s and
    # g = 1000 m/s^2: 2e-6 sin(theta) s, so 1.29e-6 s at 40 degrees and 6.8e-7 s at 20.
    base = {"initial_speed": 1e-3, "gravity": 1000.0, "drag_constant": 0.0}
    assert post(client, {**base, "launch_angle_deg": 40.0}).status_code == 200
    r = post(client, {**base, "launch_angle_deg": 20.0})
    assert r.status_code == 422
    assert "microsecond" in r.text


@pytest.mark.parametrize(
    "params",
    [
        {"launch_angle_deg": 1e-100},  # crashed the flight-time bound's root search (500)
        {"launch_angle_deg": 1e-320},  # vy0 underflows to 0: no flight at all (500)
        {"launch_angle_deg": 0.0, "launch_height": 1e-300},
    ],
)
def test_barely_flying_launches_get_a_422_not_a_500(
    client: TestClient, params: dict[str, Any]
) -> None:
    r = post(client, {"launch_height": 0.0, **params})
    assert r.status_code == 422, r.text
    assert explained(r)


# --- every corner of the allowed space -------------------------------------------------------


def _largest_drag_constant(mass: float, v0: float, g: float) -> float:
    """The largest c allowed (c <= 1e6 and kappa max(v0, v_t) <= 1e4), just inside."""
    kappa = min(1e4 / v0, 1e8 / g)  # kappa v0 <= 1e4 and sqrt(kappa g) <= 1e4
    return min(1e6, mass * kappa) * (1 - 1e-9)


def test_corners_of_the_allowed_space_never_crash_and_finish_in_time(client: TestClient) -> None:
    # Every corner (mass, speed, c, g, height, angle), with every solver and both extreme
    # tolerance settings, either runs or is refused with a 422 that explains why. Never a 500,
    # and no request takes longer than SECONDS_PER_REQUEST.
    corners = itertools.product(
        [1e-6, 1e6], [1e-3, 1e4], ["vacuum", "largest"], [0.01, 1000.0], [0.0, 1e5], [0, 1e-3, 90]
    )
    ran = refused = 0
    slowest = (0.0, "")
    for mass, v0, drag, g, h, angle in corners:
        c = 0.0 if drag == "vacuum" else _largest_drag_constant(mass, v0, g)
        v_t = math.inf if c == 0 else math.sqrt(mass * g / c)
        params = {
            "mass": mass,
            "initial_speed": v0,
            "drag_constant": c,
            "gravity": g,
            "launch_height": h,
            "launch_angle_deg": angle,
        }
        loosest_atol = min(0.1, ATOL_FRACTION * min(v0, v_t)) * (1 - 1e-9)
        for method, (rtol, atol) in itertools.product(
            ("RK45", "DOP853", "Radau"), ((1e-13, 1e-14), (1e-3, loosest_atol))
        ):
            solver = {"method": method, "rtol": rtol, "atol": atol}
            start = time.perf_counter()
            r = post(client, params, solver=solver)
            seconds = time.perf_counter() - start
            where = (params, solver, r.text[:300])
            slowest = max(slowest, (seconds, repr((params, solver))))
            assert seconds < SECONDS_PER_REQUEST, (seconds, where)
            assert r.status_code in (200, 422), where
            if r.status_code == 422:
                refused += 1
                assert explained(r), where
                continue
            ran += 1
            body = r.json()
            t = body["numerical"]["flight_time"]
            assert math.isfinite(t), where
            assert t > 0, where
            if c == 0:
                # In vacuum the trajectory is a quadratic in t, which every method here
                # integrates exactly; what remains is the landing search (about 1e-15 s
                # absolute, over flights of at least 1e-6 s) and rounding: 1e-6 is the margin.
                assert t == rel_approx(body["vacuum"]["flight_time"], rel=1e-6), where
    assert ran > 0
    assert refused > 0
    print(f"corners: {ran} ran, {refused} refused; slowest {slowest[0]:.2f} s: {slowest[1]}")
