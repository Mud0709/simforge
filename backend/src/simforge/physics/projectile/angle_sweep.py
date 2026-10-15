"""Range as a function of launch angle, and the angle that maximises it.

Pure computation on top of the exact linear-drag solution (:mod:`analytical`); no
HTTP, no database, no Pydantic.

Method
------
1. Evaluate the exact range R(theta) on a uniform grid of angles.
2. Take the best grid point and refine it with a bounded Brent search on the
   neighbouring grid interval. Every case checked shows R(theta) with a single
   peak on [0, 90] degrees (see the tests), so the refined point is the global
   maximum, not just a local one.

Precision note
--------------
At a maximum the curve is flat: R(theta* + d) ~ R* - (1/2) |R''| d^2. A change of d in
the angle changes R only by about d^2, so R* is known to near machine precision while
theta* is known only to roughly sqrt(machine epsilon) relative accuracy. The
optimisation tolerance (``ANGLE_XATOL``) reflects that.

Vacuum reference
----------------
With no drag, the best angle from launch height h has a closed form,
``tan(theta*) = v0 / sqrt(v0^2 + 2 g h)``, with maximum range
``R* = (v0 / g) sqrt(v0^2 + 2 g h)``. At h = 0 this is the familiar 45 degrees and
v0^2 / g.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize_scalar

from simforge.physics.projectile import analytical
from simforge.physics.projectile.analytical import ProjectileSetup

FloatArray = NDArray[np.float64]

# Brent's absolute tolerance on the angle, in degrees. Tighter is pointless: near the
# peak, range differences fall below floating-point resolution (see "Precision note").
ANGLE_XATOL = 1e-7


@dataclass(frozen=True, slots=True)
class SweepPoint:
    angle_deg: float
    range: float  # m
    flight_time: float  # s
    max_height: float  # m


@dataclass(frozen=True, slots=True)
class AngleSweep:
    points: list[SweepPoint]
    best_angle_deg: float
    best_range: float  # m
    vacuum_best_angle_deg: float
    vacuum_best_range: float  # m


def with_angle(setup: ProjectileSetup, angle_deg: float) -> ProjectileSetup:
    """The same projectile, launched at a different angle."""
    return ProjectileSetup(
        initial_speed=setup.initial_speed,
        launch_angle_rad=math.radians(angle_deg),
        launch_height=setup.launch_height,
        mass=setup.mass,
        drag_coefficient=setup.drag_coefficient,
        gravity=setup.gravity,
    )


def evaluate(setup: ProjectileSetup, angle_deg: float) -> SweepPoint:
    """Exact range, flight time and maximum height at one launch angle."""
    s = with_angle(setup, angle_deg)
    t_land = analytical.flight_time(s)
    t_apex = analytical.apex_time(s)
    x, y, _, _ = analytical.state(s, np.array([t_land, t_apex]))
    return SweepPoint(
        angle_deg=angle_deg,
        range=float(x[0]),
        flight_time=t_land,
        max_height=float(y[1]),
    )


def vacuum_optimum(setup: ProjectileSetup) -> tuple[float, float]:
    """Closed-form best angle (degrees) and maximum range (m) with no drag."""
    v, g, h = setup.initial_speed, setup.gravity, setup.launch_height
    root = math.sqrt(v * v + 2.0 * g * h)
    return math.degrees(math.atan2(v, root)), v * root / g


def sweep(setup: ProjectileSetup, angles_deg: Sequence[float]) -> AngleSweep:
    """Range at each angle, plus the refined best angle over [0, 90] degrees."""
    if len(angles_deg) < 3:
        raise ValueError("need at least 3 angles to bracket a maximum")
    points = [evaluate(setup, a) for a in angles_deg]

    # Refine around the best grid point, using its neighbours as the bracket.
    i = max(range(len(points)), key=lambda j: points[j].range)
    lo = angles_deg[max(i - 1, 0)]
    hi = angles_deg[min(i + 1, len(points) - 1)]
    result = minimize_scalar(
        lambda a: -evaluate(setup, float(a)).range,
        bounds=(lo, hi),
        method="bounded",
        options={"xatol": ANGLE_XATOL},
    )
    best_angle, best_range = float(result.x), -float(result.fun)
    if points[i].range > best_range:  # the optimum sits exactly on a grid point (or an edge)
        best_angle, best_range = points[i].angle_deg, points[i].range

    vac_angle, vac_range = vacuum_optimum(setup)
    return AngleSweep(
        points=points,
        best_angle_deg=best_angle,
        best_range=best_range,
        vacuum_best_angle_deg=vac_angle,
        vacuum_best_range=vac_range,
    )
