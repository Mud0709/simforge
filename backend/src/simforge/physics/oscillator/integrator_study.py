"""Oscillator methods study: the pure scientific core (roadmap 2.4, plan D8-D10, R1-R7).

The undamped, undriven oscillator x'' = -w^2 x, w = sqrt(k/m), with state y = (x, v) in SI
units (m, m/s). Two parts, both on the slice-1 numerics:

* **orders** over ONE period T = 2 pi / w: each method at each dt, N = ceil(T/dt), h = T/N,
  errors max |x - x_exact| (m) and max |v - v_exact| (m/s) over the nodes, against the exact
  solution x0 cos wt + (v0/w) sin wt; orders fitted by ``numerics.workbench`` (measured);
* **energy** over ``periods`` periods at ``energy_dt``: E proportional to x^2 + (v/w)^2, the
  relative error (E_n - E_0)/E_0, the modified energy H~ (R3/R4) for the symplectic methods
  and the proved bound R5.

No HTTP, no database, no Pydantic. ``symplectic_euler`` and ``velocity_verlet`` are looked up
as module attributes at run time (a test substitutes a planted mutant).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from simforge.numerics.fixed_step import (
    RHS,
    SYMPLECTIC_METHODS,
    FloatArray,
    Stepper,
    euler_step,
    harmonic_energy_bound,
    harmonic_energy_factor,
    integrate_fixed,
    modified_energy,
    rk4_step,
    symplectic_euler,
    velocity_verlet,
)
from simforge.numerics.workbench import (
    EnergyEnvelope,
    ErrorGroup,
    MethodConvergence,
    Problem,
    energy_envelope,
    run_convergence,
)

THEORETICAL_ORDER = {"euler": 1, "rk4": 4, "symplectic_euler": 1, "velocity_verlet": 2}
MAX_THETA_FOR_FIT = 0.2  # w h above this is not asymptotic (plan D9)
MAX_GROWTH_FOR_FIT = 0.1  # |rho^N - 1| above this: amplitude changed by > 10% (plan D9)
ROUNDOFF_SAFETY = 100.0  # floor 100 N eps on the scaled error (plan D9)


def steps_for(horizon: float, dt: float) -> int:
    """N = ceil(horizon/dt), as the workbench driver computes it (rounding noise ignored)."""
    return max(1, math.ceil(horizon / dt * (1.0 - 1e-12)))


@dataclass(frozen=True, slots=True)
class Oscillator:
    omega: float  # rad/s
    x0: float  # m
    v0: float  # m/s

    @property
    def period(self) -> float:
        return 2 * math.pi / self.omega

    @property
    def amplitude(self) -> float:
        """X = sqrt(x0^2 + (v0/w)^2), m: the exact solution's amplitude."""
        return math.hypot(self.x0, self.v0 / self.omega)


def _stepper(method: str, omega2: float) -> Stepper:
    def accel(_t: float, q: FloatArray) -> FloatArray:
        return -omega2 * q

    if method == "euler":
        return euler_step
    if method == "rk4":
        return rk4_step
    factory = symplectic_euler if method == "symplectic_euler" else velocity_verlet
    return factory(accel)


def _rhs(omega2: float) -> RHS:
    def f(_t: float, y: FloatArray) -> FloatArray:
        return np.array([y[1], -omega2 * y[0]])

    return f


def _exclusion(omega: float) -> Callable[[str, float, int], str | None]:
    def rule(method: str, h: float, n: int) -> str | None:
        theta = omega * h
        if theta > MAX_THETA_FOR_FIT:
            return f"w h = {theta:.3g} > {MAX_THETA_FOR_FIT} (not asymptotic)"
        if method not in SYMPLECTIC_METHODS:
            # rho^2 = E_{n+1}/E_n (R1, R2): the closed-form amplitude change over N steps.
            growth = abs(math.expm1(0.5 * n * math.log(harmonic_energy_factor(method, theta))))
            if growth > MAX_GROWTH_FOR_FIT:
                return f"amplitude changes by {growth:.3g} over the period (> 10%)"
        return None

    return rule


def run_orders(
    osc: Oscillator, dt_values: Sequence[float], methods: Sequence[str]
) -> list[MethodConvergence]:
    omega, x0, u0 = osc.omega, osc.x0, osc.v0 / osc.omega
    omega2 = omega * omega

    def exact(t: FloatArray) -> FloatArray:
        c, s = np.cos(omega * t), np.sin(omega * t)
        return np.column_stack([x0 * c + u0 * s, omega * (u0 * c - x0 * s)])

    problem = Problem(
        rhs=_rhs(omega2),
        y0=np.array([osc.x0, osc.v0]),
        t0=0.0,
        horizon=osc.period,
        exact=exact,
        groups=(
            ErrorGroup("position", (0,), osc.amplitude),
            ErrorGroup("velocity", (1,), omega * osc.amplitude),
            # The fitted error: phase-space distance in (q, v/w) over X, max over ALL nodes.
            # Not the end node alone: symplectic Euler is O(h^2) at t = T (superconvergent).
            ErrorGroup("scaled", (0, 1), 1.0, (1 / osc.amplitude, 1 / (omega * osc.amplitude))),
        ),
        exclusion=_exclusion(omega),
    )
    steppers = {m: _stepper(m, omega2) for m in methods}
    return run_convergence(problem, steppers, dt_values, roundoff_safety=ROUNDOFF_SAFETY)


@dataclass(frozen=True, slots=True)
class EnergyRun:
    method: str
    h: float  # s
    theta: float  # w h
    n_steps: int
    diverged: bool
    n_completed: int
    final_energy_ratio: float | None  # E_N/E_0; None if diverged
    max_relative_energy_error: float  # max |E_n - E_0|/E_0 over the completed nodes
    energy_bound: float | None  # R5 (symplectic, theta < 2)
    modified_energy_residual: float | None  # max |H~_n - H~_0|/|H~_0| (symplectic, H~_0 != 0)
    envelope: EnergyEnvelope  # of (E_n - E_0)/E_0


def run_energy(osc: Oscillator, method: str, energy_dt: float, periods: int) -> EnergyRun:
    horizon = periods * osc.period
    n = steps_for(horizon, energy_dt)
    h = horizon / n
    omega = osc.omega
    theta = omega * h
    omega2 = omega * omega
    sol = integrate_fixed(
        _stepper(method, omega2),
        _rhs(omega2),
        np.array([osc.x0, osc.v0]),
        0.0,
        h,
        n,
    )
    q, v = sol.y[:, 0], sol.y[:, 1]
    u = v / omega
    energy = q * q + u * u
    rel = (energy - energy[0]) / energy[0]
    bound = residual = None
    if method in SYMPLECTIC_METHODS:
        b = harmonic_energy_bound(method, theta)
        bound = b if math.isfinite(b) else None
        h_mod = np.asarray(modified_energy(method, q, v, omega, h))
        # H~ is positive definite only for theta < 2; beyond, H~_0 can be 0 or tiny (no scale).
        if theta < 2.0:
            residual = float(np.max(np.abs(h_mod - h_mod[0])) / abs(h_mod[0]))
    return EnergyRun(
        method=method,
        h=h,
        theta=theta,
        n_steps=n,
        diverged=sol.diverged,
        n_completed=len(sol.t) - 1,
        final_energy_ratio=None if sol.diverged else float(energy[-1] / energy[0]),
        max_relative_energy_error=float(np.max(np.abs(rel))),
        energy_bound=bound,
        modified_energy_residual=residual,
        envelope=energy_envelope(sol.t, rel),
    )
