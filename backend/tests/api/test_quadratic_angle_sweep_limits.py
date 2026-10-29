"""Input limits of the quadratic-drag angle sweep (plan D7, D8; slice 3): a result or a 422,
never a 500.

The sweep is valid iff a 2.1 request (``QuadraticDragRequest``) with the same parameters and
solver is valid at the sweep's smallest flown angle (plan D7): 0 degrees from a height, else
the first grid step 90 / (n_angles - 1). The drag-rate and atol rules do not depend on the
angle, and the drag-free flight time (vy0 + sqrt(vy0^2 + 2 g h)) / g grows with the angle, so
the 1-microsecond rule holds at every larger angle if it holds at the smallest. Its refusals
say which angle they were checked at. Two limits come from the sweep itself: the 2.1
stiffness guard at every grid angle before any solve, and the work budget of 300 000
right-hand-side evaluations, a server limit (not a request field) checked after each run.
"""

from __future__ import annotations

import itertools
import math
import time
from typing import Any

from fastapi.testclient import TestClient

from tests.approx import rel_approx

URL = "/api/v1/physics/projectile/quadratic-drag/angle-sweep"
G = 9.80665
ATOL_FRACTION = 0.01  # the 2.1 rule: atol <= 0.01 min(v0, v_t)


def post(client: TestClient, params: dict[str, Any], **extra: Any) -> Any:
    return client.post(URL, json={"parameters": params, "save_experiment": False, **extra})


def explained(r: Any) -> bool:
    """A 422 whose detail actually says something (a sentence, not just a status)."""
    detail = r.json()["detail"]
    text = detail if isinstance(detail, str) else " ".join(d.get("msg", "") for d in detail)
    return len(text) > 30


# --- validated once, at the smallest flown angle ---------------------------------------------


def test_the_microsecond_rule_is_checked_at_the_first_grid_step_from_the_ground(
    client: TestClient,
) -> None:
    # From the ground in vacuum a flight lasts 2 v0 sin(theta) / g. With v0 = 3e-3 m/s and
    # g = 1000 m/s^2 that is 6e-6 sin(theta) s: 1.04e-6 s at 10 degrees (the first step of a
    # 10-angle grid) but 1.05e-7 s at 1 degree (the first step of the default 91-angle grid).
    params = {"initial_speed": 3e-3, "gravity": 1000.0, "drag_constant": 0.0}
    ok = post(client, params, n_angles=10)
    assert ok.status_code == 200, ok.text
    r = post(client, params, n_angles=91)
    assert r.status_code == 422
    assert "at the sweep's smallest angle 1°" in r.text
    assert "microsecond" in r.text


def test_from_a_height_the_smallest_angle_is_zero(client: TestClient) -> None:
    # Horizontal launch from h: the flight lasts sqrt(2 h / g). At g = 1000 m/s^2 that is
    # 1.41e-6 s from h = 1e-9 m but 8.9e-7 s from h = 4e-10 m.
    base = {"initial_speed": 1e-3, "gravity": 1000.0, "drag_constant": 0.0}
    ok = post(client, {**base, "launch_height": 1e-9}, n_angles=10)
    assert ok.status_code == 200, ok.text
    r = post(client, {**base, "launch_height": 4e-10}, n_angles=10)
    assert r.status_code == 422
    assert "at the sweep's smallest angle 0°" in r.text
    assert "microsecond" in r.text


def test_the_atol_rule_is_the_2_1_rule_and_says_where_it_was_checked(client: TestClient) -> None:
    params = {"initial_speed": 0.5, "drag_constant": 0.0}  # min(v0, inf) = 0.5 m/s
    assert post(client, params, solver={"atol": 0.005}, n_angles=10).status_code == 200
    r = post(client, params, solver={"atol": 0.00500001}, n_angles=10)
    assert r.status_code == 422
    assert "at the sweep's smallest angle 10°" in r.text
    assert "use atol <=" in r.text  # the 2.1 advice, rounded down so that it is accepted


def test_the_drag_rate_rule_is_the_2_1_rule(client: TestClient) -> None:
    r = post(client, {"mass": 1e-3, "drag_constant": 100.0}, n_angles=10)  # kappa v0 = 2e6/s
    assert r.status_code == 422
    assert "drag rate" in r.text


def test_the_requests_own_launch_angle_is_not_validated_as_a_flight(client: TestClient) -> None:
    # 0 degrees from the ground is refused by 2.1 ("zero flight time") but a sweep ignores
    # the angle in its parameters, as the linear sweep does.
    r = post(client, {"launch_angle_deg": 0.0, "launch_height": 0.0}, n_angles=10)
    assert r.status_code == 200, r.text


# --- every corner of the allowed space -------------------------------------------------------

MASSES, SPEEDS, DRAGS = (1e-6, 1e6), (1e-3, 1e4), ("vacuum", "largest")
GRAVITIES, HEIGHTS = (0.01, 1000.0), (0.0, 1e5)
METHODS = ("RK45", "DOP853", "Radau")
TIGHT = (1e-13, 1e-14)  # the tightest (rtol, atol) allowed
LOOSE_RTOL = 1e-3  # the loosest rtol; atol is set per corner, just inside its rule
N_ANGLES = 10  # the fewest angles allowed: corners probe the inputs, not the grid
# Wall time per request. The work budget bounds a sweep's cost in evaluations; at 3e5 the
# slowest refusals measured in slice 2 took 11.4 s (Radau at rtol = 1e-13), and on these
# corners in slice 3 11.6 s. The ceiling that matters is the browser's: the Next.js proxy
# gives up after 30 s, so a sweep beyond 25 s would leave too little margin on a slower
# machine, and the test fails. The slowest Radau refusal is no longer run on every push
# (_skipped); its time is the slice 2 measurement recorded at MAX_SWEEP_RHS_EVALUATIONS.
SECONDS_PER_REQUEST = 25.0
BUDGET_MESSAGE = "right-hand-side evaluations"


def _largest_drag_constant(mass: float, v0: float, g: float) -> float:
    """The largest c allowed (c <= 1e6 and kappa max(v0, v_t) <= 1e4), just inside."""
    kappa = min(1e4 / v0, 1e8 / g)  # kappa v0 <= 1e4 and sqrt(kappa g) <= 1e4
    return min(1e6, mass * kappa) * (1 - 1e-9)


def _skipped(mass: float, v0: float, drag: str, g: float, h: float, tight_radau: bool) -> bool:
    """Whether this request repeats a computation, or a check, that a kept request makes.

    The earlier version of this test made 182 requests in 55 s (slice 3, one machine), and CI
    runs it on every push. Every sweep point is a single 2.1 run, bit for bit (RS2), and the
    2.1 corners test (test_quadratic_drag_limits.py) runs single runs on these corners with
    every method at both tolerance settings (at 0, 1e-3 and 90 degrees). What this test adds
    is the sweep's own logic: the rule at the smallest angle, the guard, the budget, Brent's
    refinement, the aggregated checks. It is thinned only where that repeats itself:

    * In vacuum the mass does not enter the motion (kappa = c/m = 0, and the energy check is
      relative), so only m = 1e-6 kg runs (the 8 corners with m = 1e6 kg: 48 requests, 3 s).
    * At v0 = 1e4 m/s with the largest c, kappa = 1 /m for both masses (the cap c <= 1e6
      does not bind; the equivalence the 2.1 corners test uses), and m only scales the drag
      work W. Only m = 1e-6 kg runs (the 4 corners with m = 1e6 kg: 24 requests, 10 s).
    * Tight-tolerance Radau with drag: measured on all 16 corners, 11 were refused by the work
      budget (9.2 to 11.6 s each) and two completed after 1.4e5 and 2.4e5 evaluations (4.5
      and 8.2 s); the earlier version kept six of them, 35 s. A budget refusal is the same
      check whatever the method (the count is compared after each run), and RK45's refusal
      here exercises it in 3 s. Kept: the corners from the ground at v0 = 1e-3 m/s where it
      is cheap: m = 1e6 kg at g = 0.01 m/s^2 completes (0.6 s), and both g = 1000 m/s^2
      corners are refused by validation at once.
    """
    if drag == "vacuum":
        return mass == 1e6
    if v0 == 1e4 and mass == 1e6:
        return True
    if tight_radau:
        return not (v0 == 1e-3 and h == 0 and (mass, g) != (1e-6, 0.01))
    return False


def test_corners_of_the_allowed_space_never_crash_and_finish_in_time(client: TestClient) -> None:
    # Every corner (mass, speed, c, g, height), with every solver and both extreme tolerance
    # settings, either sweeps or is refused with a 422 that explains why. Never a 500, and no
    # request takes longer than SECONDS_PER_REQUEST. Requests that repeat what a kept one
    # checks are skipped (_skipped).
    corners = itertools.product(MASSES, SPEEDS, DRAGS, GRAVITIES, HEIGHTS)
    ran = refused = over_budget = 0
    tight_radau_kept: list[tuple[float, float, float, float, int]] = []
    slowest = (0.0, "")
    total_start = time.perf_counter()
    for mass, v0, drag, g, h in corners:
        c = 0.0 if drag == "vacuum" else _largest_drag_constant(mass, v0, g)
        v_t = math.inf if c == 0 else math.sqrt(mass * g / c)
        params = {
            "mass": mass,
            "initial_speed": v0,
            "drag_constant": c,
            "gravity": g,
            "launch_height": h,
        }
        loosest_atol = min(0.1, ATOL_FRACTION * min(v0, v_t)) * (1 - 1e-9)
        for method, (rtol, atol) in itertools.product(METHODS, (TIGHT, (LOOSE_RTOL, loosest_atol))):
            tight_radau = method == "Radau" and (rtol, atol) == TIGHT
            if _skipped(mass, v0, drag, g, h, tight_radau):
                continue
            solver = {"method": method, "rtol": rtol, "atol": atol}
            start = time.perf_counter()
            r = post(client, params, solver=solver, n_angles=N_ANGLES)
            seconds = time.perf_counter() - start
            where = (params, solver, r.text[:300])
            slowest = max(slowest, (seconds, repr((params, solver))))
            assert seconds < SECONDS_PER_REQUEST, (seconds, where)
            assert r.status_code in (200, 422), where
            if tight_radau and c > 0:
                tight_radau_kept.append((mass, v0, g, h, r.status_code))
            if r.status_code == 422:
                refused += 1
                assert explained(r), where
                if BUDGET_MESSAGE in r.text:
                    over_budget += 1
                    assert "use fewer angles" in r.text, where
                continue
            ran += 1
            body = r.json()
            assert all(math.isfinite(x) for x in body["ranges"]), where
            assert body["n_rhs_evaluations"] <= 300_000, where
            assert math.isfinite(body["best_range"]), where
            if c == 0:
                # In vacuum every method integrates the quadratic path exactly apart from the
                # landing search (about 1e-15 s over flights of at least 1e-6 s) and rounding.
                assert body["best_range"] == rel_approx(body["vacuum_best_range"], rel=1e-6), where
    assert ran > 0
    assert refused > 0
    assert over_budget > 0  # the budget refusal is exercised, and is a clean 422
    # Tight-tolerance Radau with drag still runs where it is cheap (_skipped): one sweep that
    # completes and two refused by validation.
    assert sorted(tight_radau_kept) == [
        (1e-6, 1e-3, 1000.0, 0.0, 422),
        (1e6, 1e-3, 0.01, 0.0, 200),
        (1e6, 1e-3, 1000.0, 0.0, 422),
    ]
    print(
        f"sweep corners: {ran} ran, {refused} refused ({over_budget} over budget) in "
        f"{time.perf_counter() - total_start:.1f} s; slowest {slowest[0]:.2f} s: {slowest[1]}"
    )
