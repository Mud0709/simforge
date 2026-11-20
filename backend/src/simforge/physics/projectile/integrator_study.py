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

Event location (roadmap 2.4 slice 4, plan D11, R6)
--------------------------------------------------
Each fixed-horizon run of N steps has an event run with h = T/(N + 1/2), so the exact landing
sits mid-step. The first downward crossing of y = 0 is located by linear and cubic Hermite
interpolation (``numerics.events``); the landing error is O(h^min(p, q)), q = 2 or 4.
``euler_step``, ``rk4_step`` and ``locate_crossing`` are looked up in this module at run time.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

import numpy as np
from scipy.optimize import brentq

from simforge.numerics.convergence import OrderFit, fit_order
from simforge.numerics.events import first_crossing, locate_crossing
from simforge.numerics.fixed_step import (
    RHS,
    FixedStepSolution,
    FloatArray,
    Stepper,
    euler_stability,
    euler_step,
    integrate_fixed,
    rk4_stability,
    rk4_step,
)
from simforge.numerics.workbench import ConvergenceRun, ErrorGroup, Problem, run_convergence
from simforge.physics.projectile import analytical
from simforge.physics.projectile.analytical import ProjectileSetup

MethodName = Literal["euler", "rk4", "verlet"]
EventKind = Literal["linear", "hermite"]
EVENT_KINDS: tuple[EventKind, ...] = ("linear", "hermite")
INTERPOLANT_ORDER: dict[EventKind, int] = {"linear": 2, "hermite": 4}
RK_METHODS: tuple[MethodName, ...] = ("euler", "rk4")  # preserve v + k r + g t y_hat exactly
StabilityClass = Literal["stable", "marginal", "unstable"]

# --- Fit-range rule ------------------------------------------------------------------
# Fixed *before* looking at any results, and documented in SCIENTIFIC_VALIDATION.md.
# A run contributes to the order fit only if it is linearly stable, it is in the
# asymptotic regime (kh and h/T small), and its error is well above accumulated round-off.
MAX_KH_FOR_FIT = 0.2
MAX_H_OVER_T_FOR_FIT = 1.0 / 20.0
ROUNDOFF_SAFETY = 100.0  # floor = ROUNDOFF_SAFETY * N * eps * scale
EPS = float(np.finfo(np.float64).eps)
# An event run leaves the landing fit when its error |e| < ratio (|e_interp| + |e - e_interp|):
# the integrator's and the interpolant's errors cancel, and the O(h^5) remainder they leave
# would bias the slope; at 0.5 it is amplified at most 2x (plan R6, SCIENTIFIC_VALIDATION.md).
EVENT_CANCELLATION_RATIO = 0.5
# The error at landing is asymptotic only if the decaying mode is: kh <= 0.2 is not enough
# when kT is large (Euler at b = 10: local orders 0.48 -> 0.93). Mirrors the oscillator's rule.
MAX_DECAY_MISMATCH_FOR_EVENT_FIT = 0.1


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


def _stepper(setup: ProjectileSetup, method: MethodName) -> Stepper:
    # Looked up in this module's namespace at call time, so a test can plant a mutant.
    if method == "euler":
        return euler_step
    if method == "rk4":
        return rk4_step
    return verlet_step_factory(setup)


def integrate(
    setup: ProjectileSetup, method: MethodName, h: float, n_steps: int
) -> FixedStepSolution:
    return integrate_fixed(
        _stepper(setup, method), rhs(setup), initial_state(setup), 0.0, h, n_steps
    )


# --- The study ---------------------------------------------------------------------------


def steps_for(horizon: float, dt: float) -> int:
    """Number of steps so that N h = horizon exactly with h <= dt * (1 + 1e-12).

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
class EventRun:
    n_steps: int  # N of the matching fixed-horizon run
    h: float  # s, T / (N + 1/2): the exact landing sits mid-step
    kh: float
    stability: StabilityClass
    diverged: bool
    n_completed: int  # steps taken, at most 2N + 2
    crossed: bool
    crossing_step: int | None  # i: y_i > 0 >= y_{i+1}
    landing_time_linear: float | None  # s
    landing_time_hermite: float | None
    landing_error_linear: float | None  # |t^ - T|, s
    landing_error_hermite: float | None
    interpolation_error_linear: float | None  # signed, the interpolant on the exact nodes, s
    interpolation_error_hermite: float | None
    roundoff_floor: float  # s; 0 if no crossing
    in_linear_fit: bool
    in_hermite_fit: bool
    linear_exclusion_reason: str | None
    hermite_exclusion_reason: str | None


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
    event_runs: list[EventRun]  # same order as runs
    landing_fit_linear: OrderFit | None
    landing_fit_hermite: OrderFit | None
    identity_residual: float | None  # RK methods: max ||dv + k dr||_inf / (N eps V), stable runs


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


def _problem(setup: ProjectileSetup, horizon: float, pos_scale: float, vel_scale: float) -> Problem:
    def exact(t: FloatArray) -> FloatArray:
        return np.column_stack(analytical.state(setup, t))

    def exclusion(method: str, h: float, _n: int) -> str | None:
        kh = setup.k * h
        stability = classify_stability(cast(MethodName, method), kh)
        return _exclusion_reason(stability, False, kh, h / horizon)

    return Problem(
        rhs=rhs(setup),
        y0=initial_state(setup),
        t0=0.0,
        horizon=horizon,
        exact=exact,
        groups=(
            ErrorGroup("position", (0, 1), pos_scale),
            ErrorGroup("velocity", (2, 3), vel_scale),
        ),
        exclusion=exclusion,
    )


def _run_result(method: MethodName, k: float, r: ConvergenceRun) -> RunResult:
    kh = k * r.h
    return RunResult(
        dt_requested=r.dt_requested,
        h=r.h,
        n_steps=r.n_steps,
        kh=kh,
        amplification_factor=amplification_factor(method, kh),
        stability=classify_stability(method, kh),
        diverged=r.diverged,
        n_completed=r.n_completed,
        max_position_error=r.max_errors["position"],
        max_velocity_error=r.max_errors["velocity"],
        final_position_error=r.final_errors["position"],
        final_velocity_error=r.final_errors["velocity"],
        position_roundoff_floor=r.roundoff_floors["position"],
        velocity_roundoff_floor=r.roundoff_floors["velocity"],
        in_position_fit=r.in_fit["position"],
        in_velocity_fit=r.in_fit["velocity"],
        exclusion_reason=r.exclusion_reason,
    )


def _downsample(n: int, max_points: int) -> FloatArray:
    return np.unique(np.linspace(0, n - 1, min(n, max_points)).round().astype(int))


def _event_run(setup: ProjectileSetup, method: MethodName, n: int, horizon: float) -> EventRun:
    """Integrate with h = T/(N + 1/2) until the first downward crossing of y = 0 (at most
    2N + 2 steps) and locate it with both interpolants of y (slopes vy)."""
    h = horizon / (n + 0.5)
    kh = setup.k * h
    stability = classify_stability(method, kh)
    sol = integrate(setup, method, h, n + 2)  # an accurate run crosses in step N + 1
    ys, diverged = sol.y, sol.diverged
    i = first_crossing(ys[:, 1])
    if i is None and not diverged:
        rest = integrate_fixed(_stepper(setup, method), rhs(setup), ys[-1], (n + 2) * h, h, n)
        ys, diverged = np.vstack([ys, rest.y[1:]]), rest.diverged
        i = first_crossing(ys[:, 1])
    n_completed = len(ys) - 1
    if i is None:
        missing = f"no downward crossing of y = 0 within {n_completed} steps"
        return EventRun(
            n_steps=n,
            h=h,
            kh=kh,
            stability=stability,
            diverged=diverged,
            n_completed=n_completed,
            crossed=False,
            crossing_step=None,
            landing_time_linear=None,
            landing_time_hermite=None,
            landing_error_linear=None,
            landing_error_hermite=None,
            interpolation_error_linear=None,
            interpolation_error_hermite=None,
            roundoff_floor=0.0,
            in_linear_fit=False,
            in_hermite_fit=False,
            linear_exclusion_reason=missing,
            hermite_exclusion_reason=missing,
        )

    t0, t1 = i * h, (i + 1) * h
    floor = ROUNDOFF_SAFETY * (i + 1) * EPS * horizon
    _, y_ex, _, vy_ex = analytical.state(setup, np.array([t0, t1]))
    brackets = bool(y_ex[0] * y_ex[1] <= 0)
    base = _exclusion_reason(stability, diverged, kh, h / horizon)
    if base is None:
        # The discrete decay R^N against the exact e^{-kNh} over the same span (N h = T - h/2).
        mismatch = abs(amplification_factor(method, kh) ** n * math.exp(kh * n) - 1.0)
        if mismatch > MAX_DECAY_MISMATCH_FOR_EVENT_FIT:
            base = f"pre-asymptotic: |R(-kh)^N e^(kNh) - 1| = {mismatch:.3g} > 0.1"
    t_hat: dict[EventKind, float] = {}
    e_int: dict[EventKind, float | None] = {}
    why: dict[EventKind, str | None] = {}
    for q in EVENT_KINDS:
        t_hat[q] = locate_crossing(t0, t1, ys[i, 1], ys[i + 1, 1], ys[i, 3], ys[i + 1, 3], kind=q)
        e = t_hat[q] - horizon
        ei = (
            locate_crossing(t0, t1, y_ex[0], y_ex[1], vy_ex[0], vy_ex[1], kind=q) - horizon
            if brackets
            else None
        )
        reason: str | None = base
        if reason is None and abs(e) <= floor:
            reason = f"landing error at or below the round-off floor ({floor:.2g} s)"
        if reason is None and ei is None:
            reason = "exact nodes do not bracket the landing, so cancellation cannot be checked"
        if (
            reason is None
            and ei is not None
            and (abs(e) < EVENT_CANCELLATION_RATIO * (abs(ei) + abs(e - ei)))
        ):
            reason = "integrator and interpolation errors cancel (|e| < 0.5 x their sum)"
        e_int[q], why[q] = ei, reason
    return EventRun(
        n_steps=n,
        h=h,
        kh=kh,
        stability=stability,
        diverged=diverged,
        n_completed=n_completed,
        crossed=True,
        crossing_step=i,
        landing_time_linear=t_hat["linear"],
        landing_time_hermite=t_hat["hermite"],
        landing_error_linear=abs(t_hat["linear"] - horizon),
        landing_error_hermite=abs(t_hat["hermite"] - horizon),
        interpolation_error_linear=e_int["linear"],
        interpolation_error_hermite=e_int["hermite"],
        roundoff_floor=floor,
        in_linear_fit=why["linear"] is None,
        in_hermite_fit=why["hermite"] is None,
        linear_exclusion_reason=why["linear"],
        hermite_exclusion_reason=why["hermite"],
    )


def _landing_fit(events: list[EventRun], q: EventKind) -> OrderFit | None:
    fitted = [ev for ev in events if getattr(ev, f"in_{q}_fit")]
    return fit_order([ev.h for ev in fitted], [getattr(ev, f"landing_error_{q}") for ev in fitted])


def _identity_residual(
    setup: ProjectileSetup, method: MethodName, runs: list[RunResult], scale: float
) -> float | None:
    """max over stable runs of max_n ||(v_n - v(t_n)) + k (r_n - r(t_n))||_inf / (N eps V)."""
    worst: float | None = None
    for r in runs:
        if r.stability != "stable" or r.diverged:
            continue
        sol = integrate(setup, method, r.h, r.n_steps)
        d = sol.y - np.column_stack(analytical.state(setup, sol.t))
        res = float(np.abs(d[:, 2:] + setup.k * d[:, :2]).max() / (r.n_steps * EPS * scale))
        worst = res if worst is None else max(worst, res)
    return worst


def run_study(
    setup: ProjectileSetup,
    dt_values: Sequence[float],
    methods: Sequence[MethodName],
    *,
    max_plot_points: int = 400,
    horizon: float | None = None,
) -> StudyResult:
    """Integrate with every (method, dt) pair over [0, T_exact] and compare with the
    exact solution at every node; then locate the landing in a matching event run.
    ``horizon`` is T_exact, if the caller already has it."""
    if setup.k <= 0:
        raise ValueError("The integrator study requires nonzero drag (k > 0)")
    if horizon is None:
        horizon = analytical.flight_time(setup)
    t_ref = np.linspace(0.0, horizon, 1001)
    x_ref, y_ref, vx_ref, vy_ref = analytical.state(setup, t_ref)
    pos_scale = float(np.max(np.hypot(x_ref, y_ref)))
    vel_scale = float(np.max(np.hypot(vx_ref, vy_ref)))

    problem = _problem(setup, horizon, pos_scale, vel_scale)
    identity_scale = vel_scale + setup.k * pos_scale + setup.gravity * horizon  # V
    steppers: dict[str, Stepper] = {m: _stepper(setup, m) for m in methods}
    studies: list[MethodStudy] = []
    for method, conv in zip(methods, run_convergence(problem, steppers, dt_values), strict=True):
        runs = [_run_result(method, setup.k, r) for r in conv.runs]
        events = [_event_run(setup, method, r.n_steps, horizon) for r in runs]
        trajectory = None
        for r in runs:  # coarsest first
            if r.stability == "stable" and not r.diverged:
                sol = integrate(setup, method, r.h, r.n_steps)
                idx = _downsample(len(sol.t), max_plot_points)
                trajectory = (sol.y[idx, 0], sol.y[idx, 1], r.h)
                break

        studies.append(
            MethodStudy(
                method=method,
                theory=THEORY[method],
                runs=runs,
                position_local_orders=conv.local_orders["position"],
                velocity_local_orders=conv.local_orders["velocity"],
                position_fit=conv.fits["position"],
                velocity_fit=conv.fits["velocity"],
                trajectory=trajectory,
                event_runs=events,
                landing_fit_linear=_landing_fit(events, "linear"),
                landing_fit_hermite=_landing_fit(events, "hermite"),
                identity_residual=(
                    _identity_residual(setup, method, runs, identity_scale)
                    if method in RK_METHODS
                    else None
                ),
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
