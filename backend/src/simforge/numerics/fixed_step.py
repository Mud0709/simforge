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
"""

from __future__ import annotations

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
