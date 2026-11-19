"""Model-free convergence driver and energy envelope (plan 2.4, D1, D7).

A model supplies a :class:`Problem` (right-hand side, initial state, exact solution, error
measures and its own fit-exclusion rule); :func:`run_convergence` runs each method at each
step size, measures errors against the exact solution and fits empirical orders
(:mod:`simforge.numerics.convergence`). The orders are measured, not proved.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from simforge.numerics.convergence import OrderFit, fit_order, local_orders
from simforge.numerics.fixed_step import RHS, FloatArray, Stepper, integrate_fixed

EPS = float(np.finfo(np.float64).eps)


@dataclass(frozen=True, slots=True)
class ErrorGroup:
    name: str
    components: tuple[int, ...]  # error at a node: Euclidean norm over these components
    scale: float  # same units; sets the round-off floor


@dataclass(frozen=True, slots=True)
class Problem:
    rhs: RHS
    y0: FloatArray
    t0: float
    horizon: float  # every run integrates over [t0, t0 + horizon]
    exact: Callable[[FloatArray], FloatArray]  # node times (n+1,) -> exact states (n+1, dim)
    groups: tuple[ErrorGroup, ...]
    exclusion: Callable[[str, float, int], str | None]  # (method, h, n_steps) -> reason


@dataclass(frozen=True, slots=True)
class ConvergenceRun:
    dt_requested: float
    h: float  # effective step, horizon / n_steps
    n_steps: int
    diverged: bool
    n_completed: int
    max_errors: dict[str, float | None]  # by group; None if diverged
    final_errors: dict[str, float | None]
    roundoff_floors: dict[str, float]
    in_fit: dict[str, bool]
    exclusion_reason: str | None


@dataclass(frozen=True, slots=True)
class MethodConvergence:
    method: str
    runs: list[ConvergenceRun]  # coarsest to finest h
    local_orders: dict[str, list[float | None]]
    fits: dict[str, OrderFit | None]


def _run(
    problem: Problem, method: str, step: Stepper, dt: float, roundoff_safety: float
) -> ConvergenceRun:
    # The tolerance stops T/dt = 29.000000000001 (rounding noise) becoming 30 steps.
    n = max(1, math.ceil(problem.horizon / dt * (1.0 - 1e-12)))
    h = problem.horizon / n
    sol = integrate_fixed(step, problem.rhs, problem.y0, problem.t0, h, n)
    names = [g.name for g in problem.groups]
    floors = {g.name: roundoff_safety * n * EPS * g.scale for g in problem.groups}
    max_err: dict[str, float | None] = dict.fromkeys(names)
    final_err: dict[str, float | None] = dict.fromkeys(names)
    if not sol.diverged:
        diff = sol.y - problem.exact(sol.t)
        for g in problem.groups:
            err = np.linalg.norm(diff[:, list(g.components)], axis=1)
            max_err[g.name], final_err[g.name] = float(err.max()), float(err[-1])

    reason = "diverged" if sol.diverged else problem.exclusion(method, h, n)
    above = {k: (e := max_err[k]) is not None and e > floors[k] for k in names}
    if reason is None and not any(above.values()):
        reason = "error below round-off floor"
    return ConvergenceRun(
        dt_requested=dt,
        h=h,
        n_steps=n,
        diverged=sol.diverged,
        n_completed=len(sol.t) - 1,
        max_errors=max_err,
        final_errors=final_err,
        roundoff_floors=floors,
        in_fit={k: reason is None and above[k] for k in names},
        exclusion_reason=reason,
    )


def run_convergence(
    problem: Problem,
    steppers: Mapping[str, Stepper],
    dt_values: Sequence[float],
    *,
    roundoff_safety: float = 100.0,
) -> list[MethodConvergence]:
    """Run every method at every dt (coarsest to finest) and fit orders per error group."""
    out = []
    for method, step in steppers.items():
        runs = [
            _run(problem, method, step, dt, roundoff_safety)
            for dt in sorted(dt_values, reverse=True)
        ]
        hs = [r.h for r in runs]
        orders: dict[str, list[float | None]] = {}
        fits: dict[str, OrderFit | None] = {}
        for g in problem.groups:
            # Diverged runs have no error; 0.0 makes local_orders return None for those pairs.
            orders[g.name] = local_orders(hs, [r.max_errors[g.name] or 0.0 for r in runs])
            fit_runs = [r for r in runs if r.in_fit[g.name]]
            fits[g.name] = fit_order(
                [r.h for r in fit_runs], [r.max_errors[g.name] or 0.0 for r in fit_runs]
            )
        out.append(MethodConvergence(method=method, runs=runs, local_orders=orders, fits=fits))
    return out


@dataclass(frozen=True, slots=True)
class EnergyEnvelope:
    t_start: FloatArray  # first node time of each bin
    t_end: FloatArray  # last node time of each bin
    lo: FloatArray  # min of the values in each bin
    hi: FloatArray  # max of the values in each bin


def energy_envelope(t: FloatArray, values: FloatArray, max_bins: int = 200) -> EnergyEnvelope:
    """Split the nodes into min(len(t), max_bins) contiguous non-empty bins and keep each
    bin's min and max, so isolated spikes survive downsampling."""
    if max_bins < 1:
        raise ValueError(f"max_bins must be >= 1, got {max_bins}")
    if len(t) != len(values):
        raise ValueError(f"t and values differ in length ({len(t)} vs {len(values)})")
    n = len(t)
    if n == 0:
        raise ValueError("cannot bin an empty series")
    k = min(n, max_bins)
    edges = np.arange(k + 1) * n // k  # strictly increasing since n >= k
    starts = edges[:-1]
    return EnergyEnvelope(
        t_start=t[starts],
        t_end=t[edges[1:] - 1],
        lo=np.minimum.reduceat(values, starts),
        hi=np.maximum.reduceat(values, starts),
    )
