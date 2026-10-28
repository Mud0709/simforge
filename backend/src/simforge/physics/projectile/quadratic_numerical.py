"""Numerical integration of projectile motion with quadratic drag (roadmap 2.1, plan D3).

Model: F = -c|v|v (c in kg/m), so with kappa = c/m::

    dvx/dt = -kappa |v| vx
    dvy/dt = -g - kappa |v| vy

The 2-D motion has no closed form, so this module is the only source of the trajectory;
:mod:`.quadratic_reference` holds what *is* exact (the vertical flight, the terminal speed,
the hodograph invariant, the bounds) and is used here only for the terminal speed.

The state vector is ``[x, y, vx, vy, W]``, where ``W`` is the work done *against* drag,
``dW/dt = c |v|^3``. ``W`` is coded from that formula directly, never as ``-F . v`` from the
force function: a wrong force law would then also give a "consistent" ``W``, and the energy
balance ``KE + PE + W = E0`` (R5) would catch nothing.

The event logic copies the linear solver's (:mod:`.numerical`) on purpose (plan D3): sharing
it would edit the linear model's code path and risk its golden digests. A shared stepping
and event layer belongs to roadmap 2.4.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

from simforge.core.errors import SolverError
from simforge.physics.projectile import quadratic_reference as qr
from simforge.physics.projectile.numerical import FloatArray, NumericalSolution, SolverMethod


@dataclass(frozen=True, slots=True)
class QuadraticSetup:
    """Physical parameters in SI units. Validation happens in the API schema layer;
    this class assumes finite, physically meaningful values (as ``ProjectileSetup``)."""

    initial_speed: float  # m/s
    launch_angle_rad: float  # rad, measured from the horizontal
    launch_height: float  # m
    mass: float  # kg
    drag_constant: float  # kg/m (c in F = -c|v|v); 0 means vacuum
    gravity: float  # m/s^2

    @property
    def is_vertical(self) -> bool:
        """Exactly 90 degrees: math.radians(90.0) == math.pi / 2 holds exactly in float64."""
        return self.launch_angle_rad == math.pi / 2

    @property
    def vx0(self) -> float:
        # cos(math.radians(90)) is 6.1e-17, not 0: a vertical launch would get a fake range
        # and a defined-looking hodograph invariant. Exactly vertical means exactly vx0 = 0.
        if self.is_vertical:
            return 0.0
        return self.initial_speed * math.cos(self.launch_angle_rad)

    @property
    def vy0(self) -> float:
        return self.initial_speed * math.sin(self.launch_angle_rad)

    @property
    def kappa(self) -> float:
        """c/m in 1/m. Zero means vacuum."""
        return self.drag_constant / self.mass

    @property
    def terminal_speed(self) -> float:
        """sqrt(m g / c) in m/s (R4); ``math.inf`` in vacuum."""
        return qr.terminal_speed(self.mass, self.drag_constant, self.gravity)


def drag_acceleration(vx: float, vy: float, kappa: float) -> tuple[float, float]:
    """Drag acceleration -kappa |v| v in m/s^2 (gravity is added separately)."""
    speed = math.hypot(vx, vy)
    return -kappa * speed * vx, -kappa * speed * vy


def integrate(
    setup: QuadraticSetup,
    *,
    method: SolverMethod,
    rtol: float,
    atol: float,
    t_max: float,
) -> NumericalSolution:
    """Integrate until the projectile returns to y = 0 or ``t_max`` is reached."""
    g, c, kappa = setup.gravity, setup.drag_constant, setup.kappa

    def rhs(_t: float, s: FloatArray) -> FloatArray:
        vx, vy = float(s[2]), float(s[3])
        # Looked up at call time, so a test can substitute a wrong force law (mutation test).
        ax, ay = drag_acceleration(vx, vy, kappa)
        # dW/dt = c |v|^3, computed here from the velocity, independently of the force.
        power = c * (vx * vx + vy * vy) ** 1.5
        return np.array([vx, vy, ax, ay - g, power])

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
    # A horizontal launch (vy0 = 0) starts at its apex; SciPy may or may not report an event
    # that is exactly zero at t0, so either way the apex is (t = 0, y = launch height).
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
