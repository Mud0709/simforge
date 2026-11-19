"""Fixed-step explicit integrators for y' = f(t, y), implemented without SciPy.

These are textbook one-step methods, written for clarity rather than speed. For a step
size h, with y_n approximating y(t_n), t_n = t0 + n h:

Forward Euler (order 1)::

    y_{n+1} = y_n + h f(t_n, y_n)

Classical Runge-Kutta, "RK4" (order 4)::

    k1 = f(t_n,         y_n)
    k2 = f(t_n + h/2,   y_n + h/2 k1)
    k3 = f(t_n + h/2,   y_n + h/2 k2)
    k4 = f(t_n + h,     y_n + h   k3)
    y_{n+1} = y_n + h/6 (k1 + 2 k2 + 2 k3 + k4)

"Order p" means the *global* error at a fixed time behaves like C h^p as h -> 0, provided
f is smooth enough and the method is stable for the chosen h. Neither statement is
assumed by the code; both are checked empirically by the convergence tests.

Below them: symplectic Euler and velocity Verlet for q'' = a(t, q), and closed forms for
all four methods on the harmonic test equation (proved in the 2.4 plan, R1-R5 and R7).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
RHS = Callable[[float, FloatArray], FloatArray]
Stepper = Callable[[RHS, float, FloatArray, float], FloatArray]

# Once any state component exceeds this magnitude the run is declared divergent and
# stopped. It is far beyond any physical value in SimForge, and far enough below the
# float64 overflow limit (~1.8e308) that one more step of growth cannot overflow for the
# amplification factors these methods can reach under the API's input bounds.
DIVERGENCE_THRESHOLD = 1e100


def euler_step(f: RHS, t: float, y: FloatArray, h: float) -> FloatArray:
    return y + h * f(t, y)


def rk4_step(f: RHS, t: float, y: FloatArray, h: float) -> FloatArray:
    k1 = f(t, y)
    k2 = f(t + 0.5 * h, y + 0.5 * h * k1)
    k3 = f(t + 0.5 * h, y + 0.5 * h * k2)
    k4 = f(t + h, y + h * k3)
    return y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


@dataclass(frozen=True, slots=True)
class FixedStepSolution:
    t: FloatArray  # node times, shape (n_completed + 1,)
    y: FloatArray  # states, shape (n_completed + 1, dim)
    diverged: bool  # True if stopped early because the state blew up


def integrate_fixed(
    step: Stepper, f: RHS, y0: FloatArray, t0: float, h: float, n_steps: int
) -> FixedStepSolution:
    """Take ``n_steps`` steps of size ``h`` from (t0, y0) with the given one-step method.

    Node times are computed as t0 + n h (not by repeated addition, which accumulates
    rounding error in t). Stops early, flagging ``diverged``, if the state becomes
    non-finite or exceeds :data:`DIVERGENCE_THRESHOLD`.
    """
    if not h > 0 or n_steps < 1:
        raise ValueError("h must be positive and n_steps >= 1")
    y = np.empty((n_steps + 1, y0.size))
    y[0] = y0
    n_done = 0
    diverged = False
    with np.errstate(over="ignore", invalid="ignore"):
        for n in range(n_steps):
            y_next = step(f, t0 + n * h, y[n], h)
            if not np.all(np.isfinite(y_next)) or np.max(np.abs(y_next)) > DIVERGENCE_THRESHOLD:
                diverged = True
                break
            y[n + 1] = y_next
            n_done = n + 1
    t: FloatArray = t0 + h * np.arange(n_done + 1, dtype=np.float64)
    return FixedStepSolution(t=t, y=y[: n_done + 1], diverged=diverged)


# --- Linear stability ------------------------------------------------------------------
# Applied to the test equation y' = lambda y, a one-step method gives y_{n+1} = R(z) y_n
# with z = lambda h. R is the method's *stability function*; the method is stable for
# that z when |R(z)| <= 1.


def euler_stability(z: float) -> float:
    return 1.0 + z


def rk4_stability(z: float) -> float:
    # RK4 reproduces the Taylor series of e^z up to z^4.
    return 1.0 + z + z**2 / 2.0 + z**3 / 6.0 + z**4 / 24.0


# --- Symplectic steppers (plan 2.4, D4) -------------------------------------------------
# For second-order systems q'' = a(t, q) with state y = (q, v): for len(y) = 2d, q = y[:d]
# and v = y[d:]. The returned steppers have the usual Stepper signature (so they work with
# integrate_fixed) but ignore f: they use only the acceleration.

Accel = Callable[[float, FloatArray], FloatArray]


def symplectic_euler(accel: Accel) -> Stepper:
    """Symplectic Euler, kick then drift: v1 = v + h a(t, q); q1 = q + h v1 (order 1).

    ``accel`` must not depend on velocity: the method is symplectic only for a(t, q).
    """

    def step(_f: RHS, t: float, y: FloatArray, h: float) -> FloatArray:
        d = y.size // 2
        v1 = y[d:] + h * accel(t, y[:d])
        return np.concatenate([y[:d] + h * v1, v1])

    return step


def velocity_verlet(accel: Accel) -> Stepper:
    """Velocity Verlet (order 2): a0 = a(t, q); q1 = q + h v + h^2/2 a0;
    v1 = v + h/2 (a0 + a(t + h, q1)).

    ``accel`` must not depend on velocity: the method is symplectic only for a(t, q).
    """

    def step(_f: RHS, t: float, y: FloatArray, h: float) -> FloatArray:
        d = y.size // 2
        q, v = y[:d], y[d:]
        a0 = accel(t, q)
        q1 = q + h * v + (h * h / 2) * a0
        return np.concatenate([q1, v + (h / 2) * (a0 + accel(t + h, q1))])

    return step


# --- Closed forms on the harmonic test equation q'' = -omega^2 q, theta = omega h -------
# All derived by hand in the 2.4 plan (R1-R5, R7) and checked against exact rational
# iteration in the tests; E is proportional to q^2 + (v/omega)^2.

SYMPLECTIC_METHODS = ("symplectic_euler", "velocity_verlet")


def _unsupported(method: str) -> ValueError:
    return ValueError(f"no closed form for method {method!r}")


def harmonic_energy_factor(method: str, theta: float) -> float:
    """E_{n+1}/E_n, the same at every step (exact identity): Euler 1 + theta^2 (R1);
    RK4 |R(i theta)|^2 = 1 - theta^6/72 + theta^8/576 (R2)."""
    if method == "euler":
        return 1.0 + theta * theta
    if method == "rk4":
        return 1.0 - theta**6 / 72.0 + theta**8 / 576.0
    raise _unsupported(method)


def modified_energy(
    method: str, q: float | FloatArray, v: float | FloatArray, omega: float, h: float
) -> float | FloatArray:
    """The quadratic H~ (m^2) conserved exactly by the step map (proved, R3/R4).

    Symplectic Euler: q^2 + v^2/omega^2 - h q v. Velocity Verlet:
    (1 - theta^2/4) q^2 + v^2/omega^2.
    """
    if method == "symplectic_euler":
        return q * q + v * v / omega**2 - h * q * v
    if method == "velocity_verlet":
        theta = omega * h
        return (1.0 - theta * theta / 4.0) * q * q + v * v / omega**2
    raise _unsupported(method)


def harmonic_energy_bound(method: str, theta: float) -> float:
    """Proved bound on max_n |E_n - E_0|/E_0 in exact arithmetic (R5), for every n:
    theta/(1 - theta/2) (symplectic Euler), (theta^2/4)/(1 - theta^2/4) (Verlet);
    infinite for theta >= 2 (unstable, R7)."""
    if method not in SYMPLECTIC_METHODS:
        raise _unsupported(method)
    if theta >= 2.0:
        return math.inf
    if method == "symplectic_euler":
        return theta / (1.0 - theta / 2.0)
    return (theta * theta / 4.0) / (1.0 - theta * theta / 4.0)


def harmonic_phase_per_step(method: str, theta: float) -> float:
    """Phase advanced per step (rad, closed form R7): arccos(1 - theta^2/2), computed as the
    equal 2 asin(theta/2), which stays accurate at small theta; NaN for theta >= 2."""
    if method not in SYMPLECTIC_METHODS:
        raise _unsupported(method)
    if theta >= 2.0:
        return math.nan
    return 2.0 * math.asin(theta / 2.0)


def harmonic_stability_limit(method: str) -> float:
    """Largest theta of the stable range (R7): Euler 0 (unstable for every theta > 0),
    RK4 2 sqrt(2), symplectic Euler and Verlet 2 (trace 2 - theta^2)."""
    limits = {"euler": 0.0, "rk4": 2.0 * math.sqrt(2.0)} | dict.fromkeys(SYMPLECTIC_METHODS, 2.0)
    if method not in limits:
        raise _unsupported(method)
    return limits[method]
