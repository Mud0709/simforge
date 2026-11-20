"""The landing logic shared by the linear and quadratic projectile solvers (roadmap 2.4, D12).

Both solvers integrate the state ``[x, y, vx, vy, W]`` from t = 0 until the projectile
comes back to y = 0 while descending, and locate the apex (vy = 0 going down) on the way.
Only the right-hand side differs, so this module holds one copy of the two events, the
SciPy call and the status handling; each solver passes its own ``rhs``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import solve_ivp

from simforge.core.errors import SolverError

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
        error on top of the step error. Accuracy metrics use the accepted step nodes
        instead, though the last node (the landing event) is itself interpolated.
        """
        result: FloatArray = self.dense(t)  # type: ignore[operator]
        return result


def hits_ground(t: float, s: FloatArray) -> float:
    # Launched from the ground, y = 0 exactly at t = 0. If the first step overshoots the
    # landing, SciPy would read 0 -> negative as a crossing and report landing at t = 0.
    # Treating the launch instant as "above ground" leaves only the real landing.
    return float(s[1]) if t > 0.0 else 1.0


def reaches_apex(_t: float, s: FloatArray) -> float:
    return float(s[3])


hits_ground.terminal = True  # type: ignore[attr-defined]
hits_ground.direction = -1.0  # type: ignore[attr-defined]  # only while descending
reaches_apex.direction = -1.0  # type: ignore[attr-defined]  # vy crosses zero going down


def solve_to_landing(
    rhs: Callable[[float, FloatArray], FloatArray],
    y0: FloatArray,
    *,
    method: SolverMethod,
    rtol: float,
    atol: float,
    t_max: float,
) -> NumericalSolution:
    """Integrate ``rhs`` from ``y0`` at t = 0 until y = 0 while descending, or ``t_max``."""
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
        t_apex, max_height = 0.0, float(y0[1])
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
