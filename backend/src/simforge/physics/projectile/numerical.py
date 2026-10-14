"""Numerical integration of projectile motion with linear drag.

This module knows only the *force law* — it never calls the closed-form solution
except to choose a safe upper limit for the integration time. That independence is the
point: agreement between the two is evidence that both are right.

The state vector is ``[x, y, vx, vy, W]`` where ``W`` is the cumulative work done
*against* drag, ``dW/dt = b |v|^2``. Integrating ``W`` alongside the motion lets us check
the energy balance ``KE(t) + PE(t) + W(t) = E0``, an invariant the solver is not told
about and which therefore measures its accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import solve_ivp

from simforge.core.errors import SolverError
from simforge.physics.projectile.analytical import ProjectileSetup

FloatArray = NDArray[np.float64]
SolverMethod = Literal["RK45", "DOP853", "Radau"]


@dataclass(frozen=True, slots=True)
class NumericalSolution:
    t: FloatArray  # accepted step times (s), ending at the landing event
    x: FloatArray
    y: FloatArray
    vx: FloatArray
    vy: FloatArray
    drag_work: FloatArray  # J, cumulative work done against drag
    flight_time: float  # s, located by event detection
    apex_time: float  # s, located by event detection (0 if launched horizontally)
    max_height: float  # m
    n_steps: int
    n_rhs_evaluations: int
    method: SolverMethod
    rtol: float
    atol: float
    dense: object  # scipy OdeSolution, used only to resample for plots

    def sample(self, t: FloatArray) -> FloatArray:
        """Interpolated state at arbitrary times (rows: x, y, vx, vy, W).

        This uses the solver's dense-output interpolant, which adds its own (small)
        error on top of the step error. Accuracy metrics are therefore computed at the
        accepted step nodes, not at these resampled points.
        """
        result: FloatArray = self.dense(t)  # type: ignore[operator]
        return result


def integrate(
    setup: ProjectileSetup,
    *,
    method: SolverMethod,
    rtol: float,
    atol: float,
    t_max: float,
) -> NumericalSolution:
    """Integrate until the projectile returns to y = 0 or ``t_max`` is reached."""
    k, g, b = setup.k, setup.gravity, setup.drag_coefficient

    def rhs(_t: float, s: FloatArray) -> FloatArray:
        _, _, vx, vy, _ = s
        return np.array([vx, vy, -k * vx, -g - k * vy, b * (vx * vx + vy * vy)])

    def hits_ground(_t: float, s: FloatArray) -> float:
        return float(s[1])

    def reaches_apex(_t: float, s: FloatArray) -> float:
        return float(s[3])

    hits_ground.terminal = True  # type: ignore[attr-defined]
    hits_ground.direction = -1.0  # type: ignore[attr-defined]  # only while descending
    reaches_apex.direction = -1.0  # type: ignore[attr-defined]  # vy crosses zero going down

    y0 = np.array([0.0, setup.launch_height, setup.vx0, setup.vy0, 0.0])
    sol = solve_ivp(
        rhs,
        (0.0, t_max),
        y0,
        method=method,
        rtol=rtol,
        atol=atol,
        events=[hits_ground, reaches_apex],
        dense_output=True,
    )
    if sol.status == -1:
        raise SolverError(f"{method} failed: {sol.message}")
    if sol.status != 1 or len(sol.t_events[0]) == 0:
        raise SolverError(f"{method} did not reach the ground before t_max = {t_max:.6g} s")

    t_land = float(sol.t_events[0][0])
    # A horizontal launch (vy0 = 0) starts at its apex. Depending on SciPy's treatment of
    # an event function that is exactly zero at t0, the event may or may not be reported;
    # either way the apex is (t = 0, y = launch height).
    if len(sol.t_events[1]) > 0:
        t_apex, max_height = float(sol.t_events[1][0]), float(sol.y_events[1][0][1])
    else:
        t_apex, max_height = 0.0, setup.launch_height
    # solve_ivp's final node is the event time itself, so the node series ends at landing.
    return NumericalSolution(
        t=sol.t,
        x=sol.y[0],
        y=sol.y[1],
        vx=sol.y[2],
        vy=sol.y[3],
        drag_work=sol.y[4],
        flight_time=t_land,
        apex_time=t_apex,
        max_height=max_height,
        n_steps=len(sol.t) - 1,
        n_rhs_evaluations=int(sol.nfev),
        method=method,
        rtol=rtol,
        atol=atol,
        dense=sol.sol,
    )
