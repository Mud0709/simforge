"""Exact references for projectile motion with quadratic drag (roadmap 2.1, R1-R4, R6, R7).

Model
-----
A point mass ``m`` in uniform gravity ``g`` (pointing in -y) feels a drag force
``F = -c |v| v`` (c in kg/m). With ``kappa = c / m`` (1/m)::

    dvx/dt = -kappa |v| vx
    dvy/dt = -g - kappa |v| vy

The 2-D motion has no closed form (|v| couples x and y), so this module holds only what is
exact: the *vertical* flight (R1-R3), the terminal speed (R4), a conserved quantity of the
2-D motion (R6) and two proved bounds (R7). The derivations are in
``docs/plans/ROADMAP_2_1_PLAN.md`` ("Reference formulas").

Everything is written in terms of the terminal speed ``v_t = sqrt(m g / c)`` (m/s); then
``kappa = g / v_t**2`` and the time scale is ``tau = v_t / g`` (s). The mass enters only
through ``v_t``. ``v_t = math.inf`` means vacuum (``c = 0``), as
:func:`terminal_speed` returns for ``c = 0``.

Why the formulas look different from the textbook
-------------------------------------------------
Each function is written as *the vacuum result times a correction factor* that tends to 1
as ``v_t -> infinity``; for example the apex time ``tau atan(v0/v_t)`` is computed as
``(v0/g) * atan(r)/r`` with ``r = v0/v_t``. This is the same idea as ``psi`` and ``phi`` in
the linear-drag module (:mod:`.analytical`):

- the vacuum (``v_t = inf``) is the same code path, with no special case and no 0 * inf;
- weak drag does not cancel: ``ln(1 + r**2)`` would round ``1 + r**2`` first, and
  ``ln cosh(u)`` would round ``cosh(u)`` (close to 1) first;
- nothing overflows: the plan's ``tau asinh(sqrt(expm1(2X)))`` overflows once ``2X > 709.8``
  (strong drag, long drops), and ``v_t**2`` overflows for subnormal ``kappa``.

The forms are mathematically identical to the plan's; tests compare them with 50-digit
evaluations of the plain textbook formulas.

Assumptions: SI units; y up; launch from x = 0 at height h >= 0; constant g and c; no wind,
spin, lift or buoyancy. Inputs are checked here (finite, in their domain) because these
functions are also used directly, outside the API schema layer.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from simforge.physics.projectile import analytical

FloatArray = NDArray[np.float64]

# Below these arguments the correction factors equal 1 to within rounding: the first
# neglected term (u^2/6 for 2 ln cosh(u)/u^2, X/6 and X/2 for the fall factors) is below
# eps/2 = 1.1e-16, so the switch costs no accuracy and avoids 0/0 when u^2 or X underflows.
_LN_COSH_SERIES_BELOW = 1e-4  # u^2/6 = 1.7e-9 is the term kept; 2u^4/45 = 4.4e-18 is dropped
_FALL_FACTOR_ONE_BELOW = 1e-16


@dataclass(frozen=True, slots=True)
class VerticalFlight:
    """Exact vertical (90 degree) flight with quadratic drag (R3). SI units."""

    apex_time: float  # s, from launch to the top
    max_height: float  # m above the ground: h + H
    fall_time: float  # s, from the top to the ground
    flight_time: float  # s, apex_time + fall_time
    impact_speed: float  # m/s


# --- Input checks ----------------------------------------------------------------------


def _check(name: str, value: float, *, positive: bool = False, allow_inf: bool = False) -> None:
    if math.isnan(value) or (math.isinf(value) and not (allow_inf and value > 0)):
        raise ValueError(f"{name} must be finite (got {value})")
    if value < 0 or (positive and value == 0):
        kind = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be {kind} (got {value})")


def _check_vt_g(v_t: float, g: float) -> None:
    _check("v_t", v_t, positive=True, allow_inf=True)
    _check("g", g, positive=True)


def _times(t: ArrayLike, upper: float | None = None) -> FloatArray:
    arr = np.asarray(t, dtype=np.float64)
    if not np.all(np.isfinite(arr)) or np.any(arr < 0):
        raise ValueError("times must be finite and non-negative")
    if upper is not None and np.any(arr > upper):
        raise ValueError(f"times must be at most the apex time {upper} s (the rise ends there)")
    return arr


def _inverse(v_t: float) -> float:
    """1 / v_t, which is 0 in vacuum."""
    return 0.0 if math.isinf(v_t) else 1.0 / v_t


def _over_x(f: Callable[[FloatArray], FloatArray], x: FloatArray) -> FloatArray:
    """f(x) / x, with the limit 1 at x = 0 (for f = sin, tan, tanh, log1p: f(x) ~ x)."""
    safe = np.where(x == 0, 1.0, x)
    return np.where(x == 0, 1.0, f(safe) / safe)


# --- R4: terminal speed ------------------------------------------------------------------


def terminal_speed(mass: float, drag_constant: float, g: float) -> float:
    """v_t = sqrt(m g / c) in m/s, where weight m g balances drag c v_t^2 (R4).

    ``mass`` in kg, ``drag_constant`` c in kg/m (F = -c|v|v), ``g`` in m/s^2. Returns
    ``math.inf`` for c = 0 (vacuum: nothing stops the speed growing).
    """
    _check("mass", mass, positive=True)
    _check("drag_constant", drag_constant)
    _check("g", g, positive=True)
    if drag_constant == 0:
        return math.inf
    ratio = mass * g / drag_constant
    if math.isfinite(ratio):
        return math.sqrt(ratio)
    # m g / c overflows (tiny or subnormal c, or huge m) although v_t itself is finite:
    # take the square roots first, so a weak but nonzero drag is not reported as vacuum.
    return math.sqrt(mass) * math.sqrt(g) / math.sqrt(drag_constant)


# --- R1: the rise (vertical, v > 0) -----------------------------------------------------


def apex_time(v0: float, v_t: float, g: float) -> float:
    """Time to the top of a vertical throw at v0 (m/s): t_a = tau atan(v0/v_t), in s (R1).

    Computed as (v0/g) * atan(r)/r with r = v0/v_t; the vacuum limit is v0/g.
    """
    _check("v0", v0)
    _check_vt_g(v_t, g)
    r = v0 * _inverse(v_t)
    return v0 / g * (math.atan(r) / r if r > 0 else 1.0)


def apex_height(v0: float, v_t: float, g: float) -> float:
    """Height gained by a vertical throw: H = (v_t^2 / 2g) ln(1 + v0^2/v_t^2), in m (R1).

    Computed as (v0^2 / 2g) * log1p(r^2)/r^2; the vacuum limit is v0^2 / 2g.
    """
    _check("v0", v0)
    _check_vt_g(v_t, g)
    r2 = (v0 * _inverse(v_t)) ** 2
    return v0**2 / (2 * g) * (math.log1p(r2) / r2 if r2 > 0 else 1.0)


def rise_velocity(t: ArrayLike, v0: float, v_t: float, g: float) -> FloatArray:
    """Upward velocity (m/s) at times t (s) after a vertical launch at v0, for 0 <= t <= t_a.

    v(t) = v_t tan(phi0 - s) with phi0 = atan(v0/v_t) and s = t/tau (R1), computed as
    (v0 - g t tan(s)/s) / (1 + r tan s), which is v0 - g t in vacuum. After the apex drag
    reverses direction and the fall formulas apply instead, so later times are rejected.
    """
    t_arr = _times(t, upper=apex_time(v0, v_t, g))
    q = _inverse(v_t)
    s = g * t_arr * q
    numerator: FloatArray = v0 - g * t_arr * _over_x(np.tan, s)
    return numerator / (1 + v0 * q * np.tan(s))


def rise_height(t: ArrayLike, v0: float, h: float, v_t: float, g: float) -> FloatArray:
    """Height (m) at times t (s) after a vertical launch at v0 from height h, 0 <= t <= t_a.

    y(t) = h + (v_t^2/g) ln(cos s + (v0/v_t) sin s) with s = t/tau (R1). Computed as
    h + B * log1p(A)/A, where B = v0 t (sin s)/s - (g t^2/2) ((sin(s/2))/(s/2))^2 is the
    vacuum-like rise and A = g B / v_t^2 = cos s + (v0/v_t) sin s - 1; in vacuum, A = 0 and
    y = h + v0 t - g t^2/2.
    """
    _check("h", h)
    t_arr = _times(t, upper=apex_time(v0, v_t, g))
    q = _inverse(v_t)
    s = g * t_arr * q
    b: FloatArray = v0 * t_arr * _over_x(np.sin, s) - g * t_arr**2 / 2 * _over_x(np.sin, s / 2) ** 2
    return h + b * _over_x(np.log1p, g * q * q * b)


# --- R2: the fall from rest -------------------------------------------------------------


def fall_speed(t: ArrayLike, v_t: float, g: float) -> FloatArray:
    """Downward speed w (m/s) at times t (s) after falling from rest: w = v_t tanh(t/tau).

    Computed as g t tanh(u)/u with u = t/tau (R2); g t in vacuum, v_t for t >> tau.
    """
    _check_vt_g(v_t, g)
    t_arr = _times(t)
    return g * t_arr * _over_x(np.tanh, g * t_arr * _inverse(v_t))


def _ln_cosh_ratio(u: FloatArray) -> FloatArray:
    """2 ln(cosh u) / u^2 for u >= 0, with the limit 1 at u = 0.

    Small u: the series 1 - u^2/6. u <= 1: ln cosh u = log1p(2 sinh^2(u/2)), with no rounding
    of cosh u ~ 1. u > 1: ln cosh u = u - ln 2 + log1p(e^(-2u)), which cannot overflow.
    """
    small = u < _LN_COSH_SERIES_BELOW
    safe = np.where(small, 1.0, u)
    # np.where evaluates both branches, so clip each to where it is finite.
    near = np.log1p(2 * np.sinh(np.minimum(safe, 1.0) / 2) ** 2)
    far = safe - math.log(2.0) + np.log1p(np.exp(-2 * np.maximum(safe, 1.0)))
    ln_cosh = np.where(safe <= 1.0, near, far)
    return np.where(small, 1 - u**2 / 6, 2 * ln_cosh / safe**2)


def fall_distance(t: ArrayLike, v_t: float, g: float) -> FloatArray:
    """Distance fallen (m) at times t (s) after falling from rest: (v_t^2/g) ln cosh(t/tau).

    Computed as (g t^2/2) * 2 ln(cosh u)/u^2 with u = t/tau (R2); g t^2/2 in vacuum.
    """
    _check_vt_g(v_t, g)
    t_arr = _times(t)
    return g * t_arr**2 / 2 * _ln_cosh_ratio(g * t_arr * _inverse(v_t))


def fall_time(drop: float, v_t: float, g: float) -> float:
    """Time (s) to fall ``drop`` metres from rest: tau arcosh(e^X) with X = g drop / v_t^2 (R2).

    Uses arcosh(e^X) = X + log1p(sqrt(1 - e^(-2X))) (positive terms only, no overflow),
    written as sqrt(2 drop / g) times arcosh(e^X)/sqrt(2X), which tends to 1 as X -> 0.
    """
    _check("drop", drop)
    _check_vt_g(v_t, g)
    q = _inverse(v_t)
    xi = g * drop * q * q
    if xi < _FALL_FACTOR_ONE_BELOW:  # arcosh(e^X)/sqrt(2X) = 1 + X/6 + ...
        factor = 1.0
    else:
        factor = (xi + math.log1p(math.sqrt(-math.expm1(-2 * xi)))) / math.sqrt(2 * xi)
    return math.sqrt(2 * drop / g) * factor


def fall_impact_speed(drop: float, v_t: float, g: float) -> float:
    """Speed (m/s) after falling ``drop`` metres from rest: v_t sqrt(1 - e^(-2X)) (R2).

    Computed as sqrt(2 g drop) * sqrt((1 - e^(-2X)) / 2X); the vacuum limit is sqrt(2 g drop).
    """
    _check("drop", drop)
    _check_vt_g(v_t, g)
    q = _inverse(v_t)
    xi = g * drop * q * q
    # (1 - e^(-2X)) / 2X = 1 - X + ..., which is 1 to rounding below the threshold.
    factor = 1.0 if xi < _FALL_FACTOR_ONE_BELOW else math.sqrt(-math.expm1(-2 * xi) / (2 * xi))
    return math.sqrt(2 * g * drop) * factor


# --- R3: the full vertical flight -------------------------------------------------------


def vertical_flight(v0: float, h: float, v_t: float, g: float) -> VerticalFlight:
    """Exact flight of a ball thrown straight up at v0 (m/s) from height h (m) (R3).

    Rise (R1) to the height h + H, then fall from rest (R2) through h + H. From the ground
    the impact speed is v0 v_t / sqrt(v0^2 + v_t^2) < v0, and the fall takes longer than
    the rise (going up, gravity and drag both slow the ball; coming down they oppose).
    """
    _check("h", h)
    t_a = apex_time(v0, v_t, g)
    top = h + apex_height(v0, v_t, g)
    t_f = fall_time(top, v_t, g)
    return VerticalFlight(
        apex_time=t_a,
        max_height=top,
        fall_time=t_f,
        flight_time=t_a + t_f,
        impact_speed=fall_impact_speed(top, v_t, g),
    )


# --- R6: the hodograph invariant --------------------------------------------------------


def hodograph_invariant(vx: ArrayLike, vy: ArrayLike, v_t: float, g: float) -> FloatArray:
    """I = 1/vx^2 + (kappa/g) [v vy / vx^2 + asinh(vy/vx)], in s^2/m^2 (R6).

    Conserved along every 2-D flight with quadratic drag and vx > 0 (kappa/g = 1/v_t^2):
    drag points along v, so only gravity turns the velocity, and d(1/vx^2)/dtheta =
    -(2 kappa/g) sec^3(theta) integrates in closed form. vx keeps its sign (dvx/dt is
    proportional to -vx), so I is defined for the whole flight. In vacuum I = 1/vx^2.

    Conditioning: late in a long fall vy -> -v_t and the two terms nearly cancel while
    1/vx^2 grows, so a residual of I needs a scale-aware normalisation (slice 2).
    """
    _check_vt_g(v_t, g)
    vx_arr = np.asarray(vx, dtype=np.float64)
    vy_arr = np.asarray(vy, dtype=np.float64)
    if not (np.all(np.isfinite(vx_arr)) and np.all(np.isfinite(vy_arr))):
        raise ValueError("vx and vy must be finite")
    if np.any(vx_arr <= 0):
        raise ValueError("vx must be positive (the invariant is undefined for vertical motion)")
    q = _inverse(v_t)
    speed = np.hypot(vx_arr, vy_arr)
    return 1 / vx_arr**2 + q * q * (speed * vy_arr / vx_arr**2 + np.arcsinh(vy_arr / vx_arr))


# --- R7: proved bounds ------------------------------------------------------------------


def speed_bound(v0: float, v_t: float) -> float:
    """Upper bound on the speed throughout the flight: max(v0, v_t), in m/s (R7 i).

    Proof: d(v^2/2)/dt = -g vy - kappa v^3 <= v (g - kappa v^2), negative whenever v > v_t.
    Infinite in vacuum (a falling ball keeps speeding up).
    """
    _check("v0", v0)
    _check("v_t", v_t, positive=True, allow_inf=True)
    return max(v0, v_t)


def flight_time_bound(v0: float, launch_angle_rad: float, h: float, v_t: float, g: float) -> float:
    """Proved upper bound on the flight time, in s (R7 ii): vy0/g + T_fall.

    Going up, dvy/dt <= -g, so the rise lasts at most vy0/g and climbs at most vy0^2/2g.
    Coming down, d|vy|/dt >= g - kappa V |vy| with V = max(v0, v_t) (R7 i), so the ball
    falls at least as fast as under *linear* drag with k = kappa V; T_fall is the exact
    linear-drag time to fall from rest through h + vy0^2/2g (``analytical.flight_time``).
    Exact in vacuum; otherwise loose (measured up to ~7e5x), so use it only as a cap.
    """
    _check("v0", v0)
    _check("h", h)
    _check_vt_g(v_t, g)
    if not 0 <= launch_angle_rad <= math.pi / 2:
        raise ValueError(f"launch_angle_rad must be between 0 and pi/2 (got {launch_angle_rad})")
    vy0 = v0 * math.sin(launch_angle_rad)
    q = _inverse(v_t)
    k = g * q * max(v0 * q, 1.0)  # kappa V = (g/v_t^2) max(v0, v_t), and 0 in vacuum
    top = h + vy0**2 / (2 * g)
    t_fall = analytical.flight_time(analytical.ProjectileSetup(0.0, 0.0, top, 1.0, k, g))
    return vy0 / g + t_fall
