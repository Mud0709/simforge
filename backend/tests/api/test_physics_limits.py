"""Physical input limits: absurd inputs get a 422 with a reason, never a 500.

Limits (agreed with the author): mass >= 1e-6 kg, initial speed >= 1e-3 m/s, drag rate
k = b/m <= 1e4 s^-1, and integrator steps dt >= 1e-9 s. Below these the linear-drag model is
not physically meaningful, and the arithmetic can overflow or underflow.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.physics.projectile.schemas import ProjectileParameters

SIM = "/api/v1/physics/projectile/simulate"
SWEEP = "/api/v1/physics/projectile/angle-sweep"
STUDY = "/api/v1/physics/projectile/integrators"


def post(client: TestClient, url: str, params: dict[str, Any], **extra: Any) -> Any:
    return client.post(url, json={"parameters": params, "save_experiment": False, **extra})


@pytest.mark.parametrize(
    ("params", "fragment"),
    [
        ({"mass": 1e-305, "drag_coefficient": 1e6}, "mass"),  # k overflows to inf
        ({"mass": 1e-7}, "mass"),
        ({"initial_speed": 1e-200}, "initial_speed"),  # kinetic energy underflows to 0
        ({"initial_speed": 5e-4}, "initial_speed"),
        ({"mass": 1e-3, "drag_coefficient": 100.0}, "k = b/m"),  # k = 1e5 s^-1
    ],
)
@pytest.mark.parametrize("url", [SIM, SWEEP, STUDY])
def test_absurd_inputs_are_rejected_with_a_reason(
    client: TestClient, url: str, params: dict[str, Any], fragment: str
) -> None:
    r = post(client, url, params)
    assert r.status_code == 422
    assert fragment in r.text


def test_limits_themselves_are_allowed() -> None:
    ProjectileParameters(mass=1e-6, initial_speed=1e-3, drag_coefficient=0.01)  # k = 1e4
    ProjectileParameters(mass=1e-3, drag_coefficient=10.0)  # k exactly 1e4 s^-1
    with pytest.raises(ValueError, match="k = b/m"):
        ProjectileParameters(mass=1e-3, drag_coefficient=10.000001)


@pytest.mark.parametrize(
    ("params", "dt_values"),
    [
        ({}, [1e-310, 0.1]),  # subnormal step: horizon/dt overflows
        ({"mass": 2.0, "drag_coefficient": 5e-324}, [0.1, 0.05]),  # k underflows to 0
    ],
)
def test_integrator_study_degenerate_inputs_get_422(
    client: TestClient, params: dict[str, Any], dt_values: list[float]
) -> None:
    assert post(client, STUDY, params, dt_values=dt_values).status_code == 422


def _explained(r: Any) -> bool:
    """A 422 whose detail actually says something (a sentence, not just a status)."""
    detail = r.json()["detail"]
    text = detail if isinstance(detail, str) else " ".join(d.get("msg", "") for d in detail)
    return len(text) > 30


def test_corners_of_the_allowed_space_never_crash(client: TestClient) -> None:
    # Every corner, on every endpoint and with every solver, either runs or is refused with
    # a 422 that explains why (for example the stiffness guard). Never a 500. Where the
    # simulator runs, the numerical flight time must agree with the exact one.
    corners = itertools.product(
        [1e-6, 1e6], [1e-3, 1e4], [0.0, 1e4], [0.01, 1000.0], [0.0, 1e5], [0.001, 90.0]
    )
    ran = 0
    for mass, speed, k, g, h, angle in corners:
        b = k * mass
        if b > 1e6:
            continue
        params = {
            "mass": mass,
            "initial_speed": speed,
            "drag_coefficient": b,
            "gravity": g,
            "launch_height": h,
            "launch_angle_deg": angle,
        }
        requests: list[tuple[str, dict[str, Any]]] = [
            (SIM, {"solver": {"method": m}}) for m in ("RK45", "DOP853", "Radau")
        ]
        requests += [(SWEEP, {"n_angles": 10}), (STUDY, {})]
        for url, extra in requests:
            r = post(client, url, params, **extra)
            assert r.status_code in (200, 422), (url, params, r.text[:200])
            if r.status_code == 422:
                assert _explained(r), (url, params, r.text[:200])
            elif url == SIM:
                ran += 1
                body = r.json()
                exact = body["analytical"]["flight_time"]
                numeric = body["numerical"]["flight_time"]
                assert math.isfinite(exact)
                assert exact > 0
                # Agreement is only meaningful when the motion is much larger than the
                # solver's absolute tolerance (1e-10 m by default). At the slowest corners
                # the projectile rises ~1e-14 m, so the solver error, which the response
                # reports honestly, dominates; there we require a finite, positive result.
                scale = body["analytical"]["range"] + body["analytical"]["max_height"] - h
                if scale > 1e-6:
                    assert numeric == pytest.approx(exact, rel=1e-5), (url, extra, params)
    assert ran > 0


def test_sweep_ignores_the_launch_angle_so_zero_is_allowed(client: TestClient) -> None:
    flat = {"launch_angle_deg": 0.0, "launch_height": 0.0}
    assert post(client, SWEEP, flat).status_code == 200
    # The simulator and the study do use the angle: from the ground, 0 degrees cannot fly.
    assert "zero flight time" in post(client, SIM, flat).text
    assert "zero flight time" in post(client, STUDY, flat).text
