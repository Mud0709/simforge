"""Range against launch angle for quadratic drag (roadmap 2.2; in progress).

Pure computation; no HTTP, no database, no Pydantic. Slice 1 holds only the exact vacuum
references the sweep is drawn and checked against (RS1 in ``docs/plans/ROADMAP_2_2_PLAN.md``);
the sweep itself (one 2.1 run per angle, then a Brent refinement) follows in slice 2.

Vacuum reference (RS1)
----------------------
With no drag, a ball launched at speed v0 (m/s) and angle theta from height h (m) lands
after T = (v0 sin theta + sqrt(v0^2 sin^2 theta + 2 g h)) / g, so its range is

    R(theta) = v0 cos theta (v0 sin theta + sqrt(v0^2 sin^2 theta + 2 g h)) / g    (m).

Its maximum over theta is at tan theta* = v0 / sqrt(v0^2 + 2 g h), where
R* = (v0 / g) sqrt(v0^2 + 2 g h): 45 degrees and v0^2 / g from the ground, and a lower angle
from a height (the same closed form as the linear sweep's, ``angle_sweep.vacuum_optimum``).
Both terms of the bracket are non-negative for 0 <= theta <= 90 degrees, so nothing cancels.

Angles are in degrees, as in the API. 90 degrees is treated as exactly vertical, range
exactly 0, as the 2.1 model does (``QuadraticSetup.vx0``): cos(radians(90)) is 6.1e-17,
not 0. Inputs are checked here (finite, in their domain) because these functions are also
used directly, outside the API schema layer.
"""

from __future__ import annotations

import math


def _check(name: str, value: float, *, positive: bool = False) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite (got {value})")
    if value < 0 or (positive and value == 0):
        kind = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be {kind} (got {value})")


def vacuum_range(v0: float, angle_deg: float, h: float, g: float) -> float:
    """Exact range in m with no drag (RS1), at launch speed v0 (m/s), angle (degrees, 0 to 90)
    and height h (m), with gravity g (m/s^2). Exactly 0 at 90 degrees, and at 0 degrees from
    the ground."""
    _check("v0", v0)
    _check("angle_deg", angle_deg)
    if angle_deg > 90:
        raise ValueError(f"angle_deg must be at most 90 (got {angle_deg})")
    _check("h", h)
    _check("g", g, positive=True)
    theta = math.radians(angle_deg)
    vx0 = 0.0 if theta == math.pi / 2 else v0 * math.cos(theta)  # exactly vertical at 90
    vy0 = v0 * math.sin(theta)
    return vx0 * (vy0 + math.sqrt(vy0 * vy0 + 2 * g * h)) / g


def vacuum_optimum(v0: float, h: float, g: float) -> tuple[float, float]:
    """Exact best angle (degrees) and maximum range (m) with no drag (RS1), from height h (m).

    theta* = atan(v0 / sqrt(v0^2 + 2 g h)) and R* = (v0 / g) sqrt(v0^2 + 2 g h).
    """
    _check("v0", v0)
    _check("h", h)
    _check("g", g, positive=True)
    root = math.sqrt(v0 * v0 + 2 * g * h)
    return math.degrees(math.atan2(v0, root)), v0 * root / g
