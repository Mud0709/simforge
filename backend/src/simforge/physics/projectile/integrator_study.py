"""Integrator comparison study: fixed-step methods vs the exact linear-drag solution.

Pure computation: no HTTP, no database, no Pydantic. :mod:`integrator_model` turns the
dataclasses returned here into the API contract.

System
------
State s = (x, y, vx, vy), with k = b/m::

    x' = vx      y' = vy      vx' = -k vx      vy' = -g - k vy

Linear stability
----------------
The system is linear. Its Jacobian has eigenvalue 0 (twice, from position) and eigenvalue
-k (twice, from velocity). A one-step method maps a velocity perturbation through its
stability function R(z), with z = -k h. The method is stable if |R(-kh)| <= 1:

* forward Euler   R(z) = 1 + z                        -> stable for kh <= 2
* RK4             R(z) = 1 + z + z^2/2 + z^3/6 + z^4/24 -> stable for kh <= 2.7853...
* Verlet (below)  R(z) = (1 + z/2) / (1 - z/2)        -> |R| < 1 for every kh > 0

The position eigenvalue 0 gives R = 1: errors in position are carried forward, neither
damped nor amplified.

Velocity Verlet with linear drag
--------------------------------
Standard velocity Verlet assumes the acceleration depends on position only. Here
a = -g y_hat - k v depends on velocity, so its update

    x_{n+1} = x_n + h v_n + (h^2 / 2) a_n
    v_{n+1} = v_n + (h / 2) (a_n + a_{n+1}),   a_{n+1} = -g y_hat - k v_{n+1}

is *implicit* in v_{n+1}. Because drag is linear, the implicit equation can be solved
exactly::

    v_{n+1} = [ (1 - kh/2) v_n - g h y_hat ] / (1 + kh/2)

This is the trapezoidal rule for the velocity equation (second order, A-stable). The
position update is a second-order Taylor step. The scheme is therefore globally second
order. Verlet's usual advantages (symplecticity, long-term energy behaviour) concern
conservative Hamiltonian systems. They do **not** apply to this dissipative system, and no
such claim is made. Explicit "predicted-velocity" variants are not used; they are ad hoc
and their order depends on the predictor.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq

from simforge.numerics.convergence import OrderFit, fit_order, local_orders
from simforge.numerics.fixed_step import (
    RHS,
    FixedStepSolution,
    Stepper,
    euler_stability,
    euler_step,
    integrate_fixed,
    rk4_stability,
    rk4_step,
)
from simforge.physics.projectile import analytical
from simforge.physics.projectile.analytical import ProjectileSetup

FloatArray = NDArray[np.float64]
MethodName = Literal["euler", "rk4", "verlet"]
StabilityClass = Literal["stable", "marginal", "unstable"]

# --- Fit-range rule ------------------------------------------------------------------
# Fixed *before* looking at any results, and documented in SCIENTIFIC_VALIDATION.md.
# A run contributes to the order fit only if it is linearly stable, it is in the
# asymptotic regime (kh and h/T small), and its error is well above accumulated round-off.
MAX_KH_FOR_FIT = 0.2
MAX_H_OVER_T_FOR_FIT = 1.0 / 20.0
ROUNDOFF_SAFETY = 100.0  # floor = ROUNDOFF_SAFETY * N * eps * scale
EPS = float(np.finfo(np.float64).eps)


def _rk4_real_stability_limit() -> float:
    """The nonzero real root of R(z) = 1 for RK4, returned as a positive kh. Computed, not
    hard-coded.

    On the negative real axis RK4's R(z) falls from 1 to a minimum of about 0.27 and then
    rises back through +1 near z = -2.785. (It never reaches -1, unlike Euler's.) Beyond the
    limit, perturbations therefore grow *without* alternating sign.
    """
    return -float(brentq(lambda z: rk4_stability(z) - 1.0, -3.0, -2.5, xtol=1e-15))


def verlet_stability(z: float) -> float:
    return (1.0 + 0.5 * z) / (1.0 - 0.5 * z)


@dataclass(frozen=True, slots=True)
class MethodTheory:
    name: str
    order: int
    stability_limit_kh: float | None  # None: stable for every kh > 0


THEORY: dict[MethodName, MethodTheory] = {
    "euler": MethodTheory("Forward Euler", 1, 2.0),
    "rk4": MethodTheory("Classical Runge-Kutta (RK4)", 4, _rk4_real_stability_limit()),
    "verlet": MethodTheory("Velocity Verlet (implicit linear drag)", 2, None),
}

_STABILITY_FUNCTIONS = {"euler": euler_stability, "rk4": rk4_stability, "verlet": verlet_stability}


def amplification_factor(method: MethodName, kh: float) -> float:
    """R(-kh): factor by which one step multiplies a velocity perturbation."""
    return _STABILITY_FUNCTIONS[method](-kh)


def classify_stability(method: MethodName, kh: float) -> StabilityClass:
    r = abs(amplification_factor(method, kh))
    if math.isclose(r, 1.0, rel_tol=1e-12, abs_tol=0.0):
        return "marginal"
    return "stable" if r < 1.0 else "unstable"


# --- The ODE and the steppers ----------------------------------------------------------


def rhs(setup: ProjectileSetup) -> RHS:
    k, g = setup.k, setup.gravity

    def f(_t: float, s: FloatArray) -> FloatArray:
        return np.array([s[2], s[3], -k * s[2], -g - k * s[3]])

    return f


def verlet_step_factory(setup: ProjectileSetup) -> Stepper:
    """Velocity Verlet with the drag term solved implicitly (exact for linear drag)."""
    k, g = setup.k, setup.gravity

    def step(_f: RHS, _t: float, s: FloatArray, h: float) -> FloatArray:
        x, y, vx, vy = s
        ax, ay = -k * vx, -g - k * vy
        denom = 1.0 + 0.5 * k * h
        return np.array(
            [
                x + h * vx + 0.5 * h * h * ax,
                y + h * vy + 0.5 * h * h * ay,
                (1.0 - 0.5 * k * h) * vx / denom,
                ((1.0 - 0.5 * k * h) * vy - g * h) / denom,
            ]
        )

    return step


def initial_state(setup: ProjectileSetup) -> FloatArray:
    return np.array([0.0, setup.launch_height, setup.vx0, setup.vy0])


def integrate(
    setup: ProjectileSetup, method: MethodName, h: float, n_steps: int
) -> FixedStepSolution:
    stepper: Stepper = {"euler": euler_step, "rk4": rk4_step}.get(method) or verlet_step_factory(
        setup
    )
    return integrate_fixed(stepper, rhs(setup), initial_state(setup), 0.0, h, n_steps)


# --- The study ---------------------------------------------------------------------------


def steps_for(horizon: float, dt: float) -> int:
    """Number of steps so that N h = horizon exactly with h <= dt.

    The small tolerance stops T/dt = 29.000000000001 (rounding noise) becoming 30 steps.
    """
    return max(1, math.ceil(horizon / dt * (1.0 - 1e-12)))


@dataclass(frozen=True, slots=True)
class RunResult:
    dt_requested: float
    h: float  # effective step, horizon / n_steps
    n_steps: int
    kh: float
    amplification_factor: float
    stability: StabilityClass
    diverged: bool
    n_completed: int
    max_position_error: float | None  # m, max over nodes; None if diverged
    max_velocity_error: float | None  # m/s
    final_position_error: float | None
    final_velocity_error: float | None
    position_roundoff_floor: float
    velocity_roundoff_floor: float
    in_position_fit: bool
    in_velocity_fit: bool
    exclusion_reason: str | None  # why the run is excluded from both fits, if it is


@dataclass(frozen=True, slots=True)
class MethodStudy:
    method: MethodName
    theory: MethodTheory
    runs: list[RunResult]  # ordered from coarsest to finest h
    position_local_orders: list[float | None]
    velocity_local_orders: list[float | None]
    position_fit: OrderFit | None
    velocity_fit: OrderFit | None
    trajectory: tuple[FloatArray, FloatArray, float] | None  # (x, y, h) of coarsest stable run


@dataclass(frozen=True, slots=True)
class StudyResult:
    horizon: float  # s, exact flight time; every run integrates over [0, horizon]
    k: float  # 1/s
    position_scale: float  # m, max |r| of the exact solution
    velocity_scale: float  # m/s, max |v| of the exact solution
    methods: list[MethodStudy]
    exact_trajectory: tuple[FloatArray, FloatArray]


def _exclusion_reason(
    run_stability: StabilityClass, diverged: bool, kh: float, h_over_t: float
) -> str | None:
    if diverged:
        return "diverged"
    if run_stability != "stable":
        return f"{run_stability}: |R(-kh)| {'=' if run_stability == 'marginal' else '>'} 1"
    if kh > MAX_KH_FOR_FIT:
        return f"not asymptotic: kh = {kh:.3g} > {MAX_KH_FOR_FIT}"
    if h_over_t > MAX_H_OVER_T_FOR_FIT:
        return f"not asymptotic: h/T = {h_over_t:.3g} > 1/{round(1 / MAX_H_OVER_T_FOR_FIT)}"
    return None


def _run(
    setup: ProjectileSetup,
    method: MethodName,
    dt: float,
    horizon: float,
    pos_scale: float,
    vel_scale: float,
) -> tuple[RunResult, FixedStepSolution]:
    n = steps_for(horizon, dt)
    h = horizon / n
    kh = setup.k * h
    sol = integrate(setup, method, h, n)
    stability = classify_stability(method, kh)
    pos_floor = ROUNDOFF_SAFETY * n * EPS * pos_scale
    vel_floor = ROUNDOFF_SAFETY * n * EPS * vel_scale

    errors: list[float | None] = [None, None, None, None]
    if not sol.diverged:
        x, y, vx, vy = analytical.state(setup, sol.t)
        pos_err = np.hypot(sol.y[:, 0] - x, sol.y[:, 1] - y)
        vel_err = np.hypot(sol.y[:, 2] - vx, sol.y[:, 3] - vy)
        errors = [
            float(pos_err.max()),
            float(vel_err.max()),
            float(pos_err[-1]),
            float(vel_err[-1]),
        ]

    reason = _exclusion_reason(stability, sol.diverged, kh, h / horizon)
    in_pos = reason is None and errors[0] is not None and errors[0] > pos_floor
    in_vel = reason is None and errors[1] is not None and errors[1] > vel_floor
    if reason is None and not (in_pos or in_vel):
        reason = "error below round-off floor"

    result = RunResult(
        dt_requested=dt,
        h=h,
        n_steps=n,
        kh=kh,
        amplification_factor=amplification_factor(method, kh),
        stability=stability,
        diverged=sol.diverged,
        n_completed=len(sol.t) - 1,
        max_position_error=errors[0],
        max_velocity_error=errors[1],
        final_position_error=errors[2],
        final_velocity_error=errors[3],
        position_roundoff_floor=pos_floor,
        velocity_roundoff_floor=vel_floor,
        in_position_fit=in_pos,
        in_velocity_fit=in_vel,
        exclusion_reason=reason,
    )
    return result, sol


def _local_orders(runs: list[RunResult], attr: str) -> list[float | None]:
    # Diverged runs have no error; 0.0 makes local_orders return None for those pairs.
    return local_orders([r.h for r in runs], [getattr(r, attr) or 0.0 for r in runs])


def _downsample(n: int, max_points: int) -> FloatArray:
    return np.unique(np.linspace(0, n - 1, min(n, max_points)).round().astype(int))


def run_study(
    setup: ProjectileSetup,
    dt_values: Sequence[float],
    methods: Sequence[MethodName],
    *,
    max_plot_points: int = 400,
) -> StudyResult:
    """Integrate with every (method, dt) pair over [0, T_exact] and compare with the
    exact solution at every node."""
    if setup.k <= 0:
        raise ValueError("The integrator study requires nonzero drag (k > 0)")
    horizon = analytical.flight_time(setup)
    t_ref = np.linspace(0.0, horizon, 1001)
    x_ref, y_ref, vx_ref, vy_ref = analytical.state(setup, t_ref)
    pos_scale = float(np.max(np.hypot(x_ref, y_ref)))
    vel_scale = float(np.max(np.hypot(vx_ref, vy_ref)))

    studies: list[MethodStudy] = []
    for method in methods:
        pairs = [
            _run(setup, method, dt, horizon, pos_scale, vel_scale)
            for dt in sorted(dt_values, reverse=True)
        ]
        runs = [r for r, _ in pairs]

        pos_fit = fit_order(
            [r.h for r in runs if r.in_position_fit],
            [r.max_position_error or 0.0 for r in runs if r.in_position_fit],
        )
        vel_fit = fit_order(
            [r.h for r in runs if r.in_velocity_fit],
            [r.max_velocity_error or 0.0 for r in runs if r.in_velocity_fit],
        )

        trajectory = None
        for r, sol in pairs:  # coarsest first
            if r.stability == "stable" and not r.diverged:
                idx = _downsample(len(sol.t), max_plot_points)
                trajectory = (sol.y[idx, 0], sol.y[idx, 1], r.h)
                break

        studies.append(
            MethodStudy(
                method=method,
                theory=THEORY[method],
                runs=runs,
                position_local_orders=_local_orders(runs, "max_position_error"),
                velocity_local_orders=_local_orders(runs, "max_velocity_error"),
                position_fit=pos_fit,
                velocity_fit=vel_fit,
                trajectory=trajectory,
            )
        )

    idx = _downsample(len(t_ref), max_plot_points)
    return StudyResult(
        horizon=horizon,
        k=setup.k,
        position_scale=pos_scale,
        velocity_scale=vel_scale,
        methods=studies,
        exact_trajectory=(x_ref[idx], y_ref[idx]),
    )
