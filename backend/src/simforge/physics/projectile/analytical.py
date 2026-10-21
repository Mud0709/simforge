"""Closed-form solution of 2-D projectile motion with linear (Stokes) drag.

Model
-----
A point mass ``m`` moves in a uniform gravitational field ``g`` (pointing in -y) and
feels a drag force proportional to its velocity, ``F = -b v``. With ``k = b / m`` the
equations of motion are linear and decoupled::

    dvx/dt = -k vx
    dvy/dt = -g - k vy

Their exact solution, writing ``u = k t`` (elapsed time in units of the drag
relaxation time ``tau = 1 / k``), is::

    x(t)  = x0 + vx0 * t * psi(u)
    y(t)  = y0 + vy0 * t * psi(u) - g * t**2 * phi(u)
    vx(t) = vx0 * exp(-u)
    vy(t) = vy0 * exp(-u) - g * t * psi(u)

with the auxiliary functions::

    psi(u) = (1 - exp(-u)) / u           -> 1   as u -> 0
    phi(u) = (exp(-u) - 1 + u) / u**2    -> 1/2 as u -> 0

Why write it this way?
----------------------
The textbook form ``y = y0 + tau (vy0 + v_t)(1 - e^(-t/tau)) - v_t t`` subtracts two
nearly equal, very large numbers when drag is weak (``tau`` huge), destroying most
significant digits (catastrophic cancellation). In the ``psi``/``phi`` form the vacuum
limit ``b = 0`` is recovered *exactly* (``u = 0`` gives ``psi = 1``, ``phi = 1/2``), and
``phi`` is evaluated with a Taylor series for small ``u`` where the direct formula
would cancel. One code path therefore covers vacuum and drag without a special case.

Flight time
-----------
The landing time solves ``y(T) = 0``. For ``b > 0`` it has a closed form in terms of the
principal branch of the Lambert W function (:func:`flight_time_lambert_w`); for
``b = 0`` it is the positive root of a quadratic. The Lambert-W form loses accuracy
near its branch point (weak drag), so :func:`flight_time` instead brackets the root of
the exact ``y(t)`` and refines it with Brent's method to near machine precision. The
two are cross-checked in the test suite. The *trajectory* is exact; the *landing time*
is an exact equation solved numerically to ~1e-15 relative tolerance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq
from scipy.special import lambertw

FloatArray = NDArray[np.float64]

# Conservative switch to the Taylor series: the direct phi formula's relative error grows
# roughly like eps / u (measured ~1e-15 at u = 0.1, ~1e-14 near u = 0.01).
_SERIES_THRESHOLD = 0.1
# Taylor coefficients of phi(u) = sum_{n>=0} (-1)^n u^n / (n + 2)!.
# 12 terms at u = 0.1 leave a truncation error below 1e-23.
_PHI_SERIES = np.array([(-1.0) ** n / math.factorial(n + 2) for n in range(12)])
_PSI_SERIES = np.array([(-1.0) ** n / math.factorial(n + 1) for n in range(12)])


@dataclass(frozen=True, slots=True)
class ProjectileSetup:
    """Physical parameters in SI units. Validation happens in the API schema layer;
    this class assumes finite, physically meaningful values."""

    initial_speed: float  # m/s
    launch_angle_rad: float  # rad, measured from the horizontal
    launch_height: float  # m
    mass: float  # kg
    drag_coefficient: float  # kg/s  (b in F = -b v)
    gravity: float  # m/s^2

    @property
    def vx0(self) -> float:
        # cos(math.radians(90)) is 6.1e-17, not 0: a vertical launch would get a fake range.
        if self.launch_angle_rad == math.pi / 2:
            return 0.0
        return self.initial_speed * math.cos(self.launch_angle_rad)

    @property
    def vy0(self) -> float:
        return self.initial_speed * math.sin(self.launch_angle_rad)

    @property
    def k(self) -> float:
        """Drag rate b/m in 1/s. Zero means vacuum."""
        return self.drag_coefficient / self.mass

    @property
    def terminal_speed(self) -> float:
        """Terminal fall speed g/k in m/s (infinite in vacuum)."""
        return math.inf if self.k == 0 else self.gravity / self.k


def _series(u: FloatArray, coefficients: FloatArray) -> FloatArray:
    # Horner's rule, highest power first.
    result = np.zeros_like(u)
    for c in coefficients[::-1]:
        result = result * u + c
    return result


def psi(u: FloatArray) -> FloatArray:
    """(1 - exp(-u)) / u, accurate for all u >= 0 (including u = 0)."""
    u = np.asarray(u, dtype=np.float64)
    small = u < _SERIES_THRESHOLD
    safe_u = np.where(small, 1.0, u)  # avoids 0/0 in the branch np.where discards
    return np.where(small, _series(u, _PSI_SERIES), -np.expm1(-safe_u) / safe_u)


def phi(u: FloatArray) -> FloatArray:
    """(exp(-u) - 1 + u) / u**2, accurate for all u >= 0 (including u = 0)."""
    u = np.asarray(u, dtype=np.float64)
    small = u < _SERIES_THRESHOLD
    safe_u = np.where(small, 1.0, u)
    return np.where(small, _series(u, _PHI_SERIES), (np.expm1(-safe_u) + safe_u) / safe_u**2)


def state(
    setup: ProjectileSetup, t: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
    """Exact position (x, y) and velocity (vx, vy) at times ``t``. Launch is at x = 0."""
    t = np.asarray(t, dtype=np.float64)
    u = setup.k * t
    ps = psi(u)
    decay = np.exp(-u)
    x = setup.vx0 * t * ps
    y = setup.launch_height + setup.vy0 * t * ps - setup.gravity * t**2 * phi(u)
    vx = setup.vx0 * decay
    vy = setup.vy0 * decay - setup.gravity * t * ps
    return x, y, vx, vy


def _y(setup: ProjectileSetup, t: float) -> float:
    return float(state(setup, np.array([t]))[1][0])


def apex_time(setup: ProjectileSetup) -> float:
    """Time at which vy = 0 (maximum height). Zero if launched horizontally."""
    if setup.k == 0:
        return setup.vy0 / setup.gravity
    # vy = 0  =>  e^{-kt} (vy0 + v_t) = v_t  =>  t = ln(1 + vy0 / v_t) / k
    return math.log1p(setup.vy0 / setup.terminal_speed) / setup.k


def flight_time_vacuum(setup: ProjectileSetup) -> float:
    """Positive root of h + vy0 t - g t^2 / 2 = 0 (valid only for b = 0)."""
    g, vy0, h = setup.gravity, setup.vy0, setup.launch_height
    # vy0 >= 0 here, so this form has no subtractive cancellation.
    return (vy0 + math.sqrt(vy0 * vy0 + 2.0 * g * h)) / g


def flight_time_lambert_w(setup: ProjectileSetup) -> float:
    """Closed-form landing time for b > 0 via the principal branch of Lambert W.

    Setting y(T) = 0 with u = kT, c = 1 + vy0 / v_t and h' = h k / v_t gives
    c (1 - e^{-u}) + h' = u, whose positive solution is

        u = c + h' + W0(-c * exp(-(c + h')))

    Accuracy degrades as the argument approaches the branch point -1/e (weak drag),
    which is why :func:`flight_time` is the function used for results.
    """
    if setup.k == 0:
        raise ValueError("Lambert-W form requires drag_coefficient > 0; use flight_time_vacuum")
    vt = setup.terminal_speed
    c = 1.0 + setup.vy0 / vt
    h_prime = setup.launch_height * setup.k / vt
    w = lambertw(-c * math.exp(-(c + h_prime)), k=0)
    return float((c + h_prime + w.real) / setup.k)


def flight_time(setup: ProjectileSetup) -> float:
    """Landing time (y = 0), solved from the exact y(t) to near machine precision.

    After the apex vy < 0 for all later t (in both vacuum and linear drag), so y is
    strictly decreasing there and the root in [t_apex, t_hi] is unique.
    """
    t_lo = apex_time(setup)
    if _y(setup, t_lo) <= 0.0:  # launched horizontally from ground level: no flight
        return t_lo
    # The vacuum landing time is a good first guess for the upper bracket; widen until y < 0.
    t_hi = max(flight_time_vacuum(setup), 2.0 * t_lo, 1e-12)
    while _y(setup, t_hi) > 0.0:
        t_hi *= 2.0
    root = brentq(lambda t: _y(setup, t), t_lo, t_hi, xtol=1e-300, rtol=4 * np.finfo(float).eps)
    return float(root)
