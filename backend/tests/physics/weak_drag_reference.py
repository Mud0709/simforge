"""Weak-drag perturbation reference for quadratic drag (roadmap 2.2, RS3; a test-side helper).

Nothing in the product depends on this module: it gives the sweep's tests (slice 2) an
independent first-order prediction for weak quadratic drag. Its own tests are in
``test_weak_drag_reference.py``.

Model and symbols
-----------------
Drag F = -c|v|v on a mass m, kappa = c/m (1/m), terminal speed v_t = sqrt(m g / c) (m/s).
The dimensionless drag strength is

    eps = kappa v0^2 / g = (v0 / v_t)^2        (eps = 0 in vacuum).

Launch from the ground (h = 0) at speed v0 and angle theta (rad). To first order in eps,

    R(theta) = (v0^2 / g) [sin 2 theta - eps F(theta)] + O(eps^2),
    F(theta) = c s^2 + c^3 s A + c (1 + s^2) / 4 - c^5 A / (4 s),

with c = cos theta, s = sin theta and A = asinh(tan theta). At 45 degrees

    F(pi/4)  = 7 / (8 sqrt 2) + (3/16) ln(1 + sqrt 2)  = 0.783976...
    F'(pi/4) = (3 sqrt 2 - ln(1 + sqrt 2)) / 8         = 0.420158...

and setting d/dtheta [sin 2 theta - eps F] = 0 near pi/4 (where 2 cos 2 theta ~ -4 (theta - pi/4))
gives the best angle and the best range

    theta* = 45 deg - (180/pi) eps F'(pi/4) / 4 + O(eps^2) = 45 deg - 6.0183 deg x eps + O(eps^2),
    R* / (v0^2 / g) = 1 - F(pi/4) eps + O(eps^2) = 1 - 0.783976 eps + O(eps^2)

(the angle shift changes R* only at second order).

Provenance and status
---------------------
Derived by hand for the 2.2 plan (``docs/plans/ROADMAP_2_2_PLAN.md``, "RS3"), by a regular
perturbation of the vacuum path about its apex; **not checked against the literature**. The
coefficients below are computed from their closed forms, not from the rounded decimals. What
is established, and how, is in the tests: the closed forms against 50-digit evaluations of
F's definition, F against quadrature of the integrals it comes from, and the first-order
predictions against an independent high-accuracy integration (the residual shrinks like
eps^2). The O(eps^2) remainder is not bounded, so how small eps must be for "weak" drag is
not quantified: at the 2.1 defaults (eps = 0.41) the first-order angle is 42.55 degrees
against 42.98 computed, 0.43 degrees off (it overstates the 2.0-degree drop by about a fifth).
"""

from __future__ import annotations

import math

_LN_1_PLUS_SQRT2 = math.log1p(math.sqrt(2.0))  # = asinh(1)

# F(pi/4) = 7/(8 sqrt 2) + (3/16) ln(1 + sqrt 2): first-order loss of range at 45 degrees.
RANGE_COEFFICIENT = 7.0 / (8.0 * math.sqrt(2.0)) + 3.0 / 16.0 * _LN_1_PLUS_SQRT2
# F'(pi/4) = (3 sqrt 2 - ln(1 + sqrt 2)) / 8 (per rad). Positive, so drag lowers the angle.
F_PRIME_AT_45 = (3.0 * math.sqrt(2.0) - _LN_1_PLUS_SQRT2) / 8.0
# d theta* / d eps at eps = 0, in degrees: (180/pi) F'(pi/4) / 4 = 6.0183...
ANGLE_COEFFICIENT_DEG = math.degrees(F_PRIME_AT_45) / 4.0


def range_correction(theta: float) -> float:
    """F(theta), the first-order range loss: R = (v0^2/g)[sin 2 theta - eps F(theta)] + O(eps^2).

    ``theta`` in rad, strictly between 0 and pi/2 (F's formula divides by sin theta). Not
    accurate near 0, where the last two terms cancel (F ~ theta^2).
    """
    if not 0 < theta < math.pi / 2:
        raise ValueError(f"theta must be strictly between 0 and pi/2 rad (got {theta})")
    c, s = math.cos(theta), math.sin(theta)
    a = math.asinh(math.tan(theta))
    return c * s * s + c**3 * s * a + c * (1 + s * s) / 4 - c**5 * a / (4 * s)


def _check_eps(eps: float) -> None:
    if not (math.isfinite(eps) and eps >= 0):
        raise ValueError(f"eps must be finite and non-negative (got {eps})")


def first_order_best_angle_deg(eps: float) -> float:
    """theta* ~ 45 - 6.0183 eps degrees from the ground, with eps = (v0/v_t)^2; error O(eps^2)."""
    _check_eps(eps)
    return 45.0 - ANGLE_COEFFICIENT_DEG * eps


def first_order_best_range_ratio(eps: float) -> float:
    """R* / (v0^2/g) ~ 1 - 0.783976 eps from the ground, eps = (v0/v_t)^2; error O(eps^2)."""
    _check_eps(eps)
    return 1.0 - RANGE_COEFFICIENT * eps
