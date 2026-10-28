"""Range against launch angle for quadratic drag (roadmap 2.2, plan D4-D10).

Pure computation; no HTTP, no database, no Pydantic models of its own (the API is slice 3).
There is no formula for the range with quadratic drag, so every point of the curve is one
full 2.1 run (:func:`quadratic_model.run`), and the best angle is searched for, not computed.

Vacuum reference (RS1)
----------------------
With no drag, a ball launched at speed v0 (m/s) and angle theta from height h (m) lands
after T = (v0 sin theta + sqrt(v0^2 sin^2 theta + 2 g h)) / g, so its range is

    R(theta) = v0 cos theta (v0 sin theta + sqrt(v0^2 sin^2 theta + 2 g h)) / g    (m).

Its maximum over theta is at tan theta* = v0 / sqrt(v0^2 + 2 g h), where
R* = (v0 / g) sqrt(v0^2 + 2 g h): 45 degrees and v0^2 / g from the ground, and a lower angle
from a height (the same closed form as the linear sweep's, ``angle_sweep.vacuum_optimum``).
Both terms of the bracket are non-negative for 0 <= theta <= 90 degrees, so nothing cancels.

Angles are in degrees, as in the API. 90 degrees is treated as exactly vertical, range
exactly 0, as the 2.1 model does (``QuadraticSetup.vx0``): cos(radians(90)) is 6.1e-17,
not 0. Inputs are checked here (finite, in their domain) because these functions are also
used directly, outside the API schema layer.

The sweep (plan D4, D5, D7, D8)
-------------------------------
1. Guard first: the 2.1 drag-time bound (:func:`quadratic_model.drag_time_bound`, proved) is
   computed at every grid angle before any solve, and an explicit method is refused if any
   exceeds the 2.1 limit, naming the worst angle. Refinement angles are guarded again
   inside each run.
2. One 2.1 run per grid angle (``n_angles`` evenly spaced from 0 to 90 degrees), with the
   setup built as the 2.1 route builds it (``math.radians``), so each point is bit-identical
   to a single 2.1 run (RS2). 0 degrees from the ground is not run (2.1 refuses it): it is
   "no flight", range, time and height exactly 0.
3. The best grid point is refined by a bounded Brent search on its neighbouring interval;
   the grid point is kept if it beats the refinement (as in the linear sweep). Brent finds
   a *local* maximum, so the number of interior grid peaks is reported.
4. A budget on the total right-hand-side evaluations, checked after each run (so at most
   one run in progress can overshoot it). Evaluations, not seconds: a count is reproducible,
   a timeout depends on the machine's load.

The stated accuracy of the best angle (plan D6, RS4)
---------------------------------------------------
Near the top R(theta) ~ R* - (1/2) K (theta - theta*)^2, so if the computed curve is within
eps_R of the true one, its maximiser is within 2 sqrt(eps_R / K) rad of theta* (to the
quadratic approximation). Here eps_R = 10 (rtol R + atol), the project's solver-error scale,
which is *not* a proved bound on the global error, and K comes from the grid's second
difference. So u is an **estimate, not a bound**, and observed to be pessimistic: the
solver's error is smooth in the angle, so it moved the peak far less than eps_R suggests
(observed, not proved: see the slice 2 measurements in the tests).
"""

from __future__ import annotations

import dataclasses
import math
import time
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import ModelInfo, ValidationCheck
from simforge.physics.projectile import quadratic_model
from simforge.physics.projectile.model import EXPLICIT_STIFFNESS_LIMIT
from simforge.physics.projectile.quadratic_model import QuadraticComputation
from simforge.physics.projectile.quadratic_numerical import QuadraticSetup
from simforge.physics.projectile.schemas import SolverSettings

# Brent's absolute tolerance on the angle, in degrees (plan D5, the linear sweep's value).
ANGLE_XATOL = 1e-7
# Points in each run's resampled series: the 2.1 schema minimum, since the sweep discards
# the series (plan D4). It does not affect the solve.
N_SAMPLES = 10
# eps_R = SOLVER_ERROR_FACTOR x (rtol R + atol), the solver-error scale in u (plan D6).
SOLVER_ERROR_FACTOR = 10.0
# The sweep's work budget: total right-hand-side evaluations over all its runs (plan D8),
# checked after each run. Set from a measurement (slice 2; one machine, an Intel Xeon at
# 2.1 GHz, Python 3.12.3, SciPy 1.18.1, NumPy 2.5.4): 540 sweeps of 91 angles, v0 in {1, 20,
# 300, 1e4} m/s x eps = (v0/v_t)^2 in {0, 0.1, 1, 10, 100} x h in {0, 10, 1e4} m x the three
# methods x (rtol, atol) in {(1e-6, 1e-6), (1e-10, 1e-10), (1e-13, 1e-14)}.
# - Cost per evaluation in large sweeps (> 2e5): DOP853 9-13 us, RK45 11-15 us, Radau 34-42
#   us; so the wall time at the budget is set by Radau.
# - The ceiling is latency: the browser reaches the API through Next.js rewrites, whose proxy
#   gives up after 30 s by default (next/dist/server/lib/router-utils/proxy-request.js).
#   At 3e5 the slowest refusals measured took 11.4 s (Radau, rtol = 1e-13, v0 = 20 m/s,
#   eps = 100, h = 1e4 m), including the one run that may overshoot the budget (single runs
#   there use up to ~6e4 evaluations, ~2 s; the plan saw ~1e5 and 3-4 s in harder corners),
#   so a machine ~2x slower still answers within the 30 s. At 5e5 they took 19.4 s, too
#   close.
# - What 3e5 admits at 91 angles: every sweep at the 2.1 defaults (v0 = 20 m/s, c = 0.01 kg/m,
#   m = 1 kg, h = 0) with every method (Radau ~1.9e5); the explicit methods at default
#   tolerances in 52 of the 56 cases their stiffness guard allows (the four others need 5e5
#   to over 1.5e6); Radau in 60/60 cases at (1e-6, 1e-6), 30/60 at the defaults and 12/60 at
#   (1e-13, 1e-14). Refused sweeps are told to use fewer angles or a looser tolerance: in the
#   stiffest Radau-only case measured (eps = 100, h = 1e4 m, default tolerances, 7.3e5 at 91
#   angles) 31 angles still need ~3e5, as Brent's refinement costs about a third of the grid.
MAX_SWEEP_RHS_EVALUATIONS = 300_000


def _check(name: str, value: float, *, positive: bool = False) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite (got {value})")
    if value < 0 or (positive and value == 0):
        kind = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be {kind} (got {value})")


def vacuum_range(v0: float, angle_deg: float, h: float, g: float) -> float:
    """Exact range in m with no drag (RS1), at launch speed v0 (m/s), angle (degrees, 0 to 90)
    and height h (m), with gravity g (m/s^2). Exactly 0 at 90 degrees, and at 0 degrees from
    the ground."""
    _check("v0", v0)
    _check("angle_deg", angle_deg)
    if angle_deg > 90:
        raise ValueError(f"angle_deg must be at most 90 (got {angle_deg})")
    _check("h", h)
    _check("g", g, positive=True)
    theta = math.radians(angle_deg)
    vx0 = 0.0 if theta == math.pi / 2 else v0 * math.cos(theta)  # exactly vertical at 90
    vy0 = v0 * math.sin(theta)
    return vx0 * (vy0 + math.sqrt(vy0 * vy0 + 2 * g * h)) / g


def vacuum_optimum(v0: float, h: float, g: float) -> tuple[float, float]:
    """Exact best angle (degrees) and maximum range (m) with no drag (RS1), from height h (m).

    theta* = atan(v0 / sqrt(v0^2 + 2 g h)) and R* = (v0 / g) sqrt(v0^2 + 2 g h).
    """
    _check("v0", v0)
    _check("h", h)
    _check("g", g, positive=True)
    root = math.sqrt(v0 * v0 + 2 * g * h)
    return math.degrees(math.atan2(v0, root)), v0 * root / g


# --- The sweep ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SweepPoint:
    angle_deg: float
    range: float  # m, numerical (exactly 0 at 90 degrees, and for no flight)
    flight_time: float  # s
    max_height: float  # m
    flew: bool  # False only at 0 degrees from the ground: no flight, no solve, all exactly 0


@dataclass(frozen=True, slots=True)
class SweepRun:
    """One 2.1 run of the sweep, at a grid angle or a refinement angle."""

    angle_deg: float
    computation: QuadraticComputation


@dataclass(frozen=True, slots=True)
class QuadraticSweep:
    points: list[SweepPoint]  # the grid, 0 to 90 degrees
    runs: list[SweepRun]  # every solve in order: the grid (except no flight), then Brent's
    best_angle_deg: float  # numerical: the refined best angle
    best_range: float  # m, numerical
    best_angle_uncertainty_deg: float | None  # estimate, not a bound; None at an edge
    best_angle_note: str
    interior_peaks: int  # grid points whose range beats both neighbours
    n_rhs_evaluations: int  # the whole sweep's


def _at(setup: QuadraticSetup, angle_deg: float) -> QuadraticSetup:
    """The same launch at another angle, built as the 2.1 route builds it (90 -> pi/2)."""
    return dataclasses.replace(setup, launch_angle_rad=math.radians(angle_deg))


def _no_flight(setup: QuadraticSetup, angle_deg: float) -> bool:
    return angle_deg == 0 and setup.launch_height == 0


def _guard(setup: QuadraticSetup, method: str, grid: list[float]) -> None:
    """Refuse an explicit method before any solve if the 2.1 guard would refuse any angle."""
    if method == "Radau":  # L-stable: no drag-time limit in 2.1 either
        return
    bounds = [
        (a, quadratic_model.drag_time_bound(_at(setup, a)))
        for a in grid
        if not _no_flight(setup, a)
    ]
    worst_angle, worst = max(bounds, key=lambda b: b[1])
    if worst > EXPLICIT_STIFFNESS_LIMIT:
        n_over = sum(b > EXPLICIT_STIFFNESS_LIMIT for _, b in bounds)
        raise ModelDomainError(
            f"The sweep's flight at {worst_angle:g}° travels up to {worst:.6g} drag lengths "
            f"m/c (its drag time, the integral of kappa |v| dt, is at most this); {n_over} of "
            f"its {len(bounds)} angles are above the {EXPLICIT_STIFFNESS_LIMIT:.0e} limit for "
            f"{method}: an explicit method's step is limited by the drag rate, so the runs "
            "would be prohibitively slow. Use method='Radau' for stiff problems."
        )


def _uncertainty(
    points: list[SweepPoint], i: int, best: tuple[float, float], solver: SolverSettings
) -> tuple[float | None, str]:
    """u = 2 sqrt(eps_R / K) in degrees (plan D6), or None with the reason."""
    best_angle, best_range = best
    n = len(points)
    if i in (0, n - 1):
        edge = points[i].angle_deg
        where = (
            f"the best angle is that edge, {edge:g}°"
            if best_angle == edge
            else f"the refined best angle is {best_angle:.6g}°"
        )
        return None, (
            f"No estimate: the best grid point is at the edge of the grid ({edge:g}°), where "
            f"the curvature K cannot be taken from a centred second difference; {where}."
        )
    d2 = points[i + 1].range - 2 * points[i].range + points[i - 1].range
    if not d2 < 0:
        return None, (
            "No estimate: the grid curve is not bent downwards at its best point (second "
            f"difference {d2:.3g} m), so K, and with it u, is undefined."
        )
    step = math.radians(points[1].angle_deg - points[0].angle_deg)
    curvature = -d2 / step**2  # K, m/rad^2
    eps_r = SOLVER_ERROR_FACTOR * (solver.rtol * best_range + solver.atol)
    u = math.degrees(2 * math.sqrt(eps_r / curvature))
    return u, (
        "Estimate, not a bound: u = 2 sqrt(eps_R / K), with eps_R = "
        f"{SOLVER_ERROR_FACTOR:g} (rtol R + atol) = {eps_r:.3g} m, the solver-error scale "
        "(not a proved bound on the global error), and K = |R''| = "
        f"{curvature:.4g} m/rad^2 from the grid's second difference. Observed to be "
        "pessimistic (evidence, not a proof): the solver's error is smooth in the angle, "
        "so in the cases measured it moved the peak far less."
    )


def sweep(
    setup: QuadraticSetup,
    solver: SolverSettings,
    n_angles: int,
    *,
    max_rhs_evaluations: int = MAX_SWEEP_RHS_EVALUATIONS,
) -> QuadraticSweep:
    """Range at ``n_angles`` evenly spaced angles from 0 to 90 degrees, and the refined best
    angle. ``setup.launch_angle_rad`` is ignored. Raises :class:`ModelDomainError` when the
    stiffness guard refuses the sweep, or when it needs more than ``max_rhs_evaluations``."""
    if n_angles < 3:
        raise ValueError("need at least 3 angles to bracket a maximum")
    grid: list[float] = np.linspace(0.0, 90.0, n_angles).tolist()
    _guard(setup, solver.method, grid)
    points: list[SweepPoint] = []
    runs: list[SweepRun] = []
    total = 0

    def solve(angle_deg: float) -> QuadraticComputation:
        nonlocal total
        computation = quadratic_model.run(_at(setup, angle_deg), solver, n_samples=N_SAMPLES)
        runs.append(SweepRun(angle_deg, computation))
        total += computation.numerical.n_rhs_evaluations
        if total > max_rhs_evaluations:
            if len(points) < n_angles:  # this run is grid point number len(points) + 1
                progress = f"after {len(points) + 1} of {n_angles} angles"
            else:
                n_refine = len(runs) - sum(p.flew for p in points)
                progress = f"after all {n_angles} angles and {n_refine} refinement runs"
            raise ModelDomainError(
                f"The sweep needed more than {max_rhs_evaluations:,} right-hand-side "
                f"evaluations ({total:,} {progress}); use fewer angles, a looser tolerance, "
                "or DOP853 where the drag-time bound allows."
            )
        return computation

    for angle in grid:
        if _no_flight(setup, angle):
            points.append(SweepPoint(angle, 0.0, 0.0, 0.0, flew=False))
            continue
        result = solve(angle).numerical
        points.append(
            SweepPoint(angle, result.range, result.flight_time, result.max_height, flew=True)
        )

    def minus_range(angle: float) -> float:
        a = float(angle)
        return -0.0 if _no_flight(setup, a) else -solve(a).numerical.range

    i = max(range(n_angles), key=lambda j: points[j].range)
    refined = minimize_scalar(
        minus_range,
        bounds=(grid[max(i - 1, 0)], grid[min(i + 1, n_angles - 1)]),
        method="bounded",
        options={"xatol": ANGLE_XATOL},
    )
    best = (float(refined.x), -float(refined.fun))
    if points[i].range > best[1]:  # the optimum sits on a grid point (to rounding)
        best = (points[i].angle_deg, points[i].range)
    uncertainty, note = _uncertainty(points, i, best, solver)
    ranges = [p.range for p in points]
    peaks = sum(1 for j in range(1, n_angles - 1) if ranges[j - 1] < ranges[j] > ranges[j + 1])
    return QuadraticSweep(
        points=points,
        runs=runs,
        best_angle_deg=best[0],
        best_range=best[1],
        best_angle_uncertainty_deg=uncertainty,
        best_angle_note=note,
        interior_peaks=peaks,
        n_rhs_evaluations=total,
    )


# --- The model run: references and aggregated checks (plan D10) -----------------------------


@dataclass(frozen=True, slots=True)
class QuadraticAngleSweepComputation:
    sweep: QuadraticSweep
    vacuum_ranges: list[float]  # m, exact, at the grid angles
    vacuum_best_angle_deg: float  # exact
    vacuum_best_range: float  # m, exact
    terminal_speed: float | None  # m/s, exact; None in vacuum
    checks: list[ValidationCheck]
    elapsed_ms: float


def _angles(angles: list[float]) -> str:
    return ", ".join(f"{a:.10g}°" for a in angles)


def _runs(n: int) -> str:
    return f"{n} run" if n == 1 else f"{n} runs"


def _aggregate(entries: list[tuple[float, ValidationCheck]]) -> ValidationCheck:
    """One 2.1 check over every run: passed only if every run passed; value and threshold
    from the run with the largest value / threshold (thresholds differ between angles)."""
    graded = [(a, c) for a, c in entries if c.threshold is not None]
    if not graded:  # informational in every run: report the largest value
        angle, worst = max(entries, key=lambda e: e[1].value)
        note = (
            f"{worst.note} Across the sweep: the largest value of {_runs(len(entries))}, "
            f"at {angle:.10g}°."
        )
        return worst.model_copy(update={"note": note})
    angle, worst = max(graded, key=lambda e: e[1].value / e[1].threshold)  # type: ignore[operator]
    n_failed = sum(c.passed is not True for _, c in graded)
    note = (
        f"{worst.note} Across the sweep: {_runs(len(graded))}, {n_failed} failed; the "
        f"largest value / threshold is at {angle:.10g}°."
    )
    unavailable = [a for a, c in entries if c.threshold is None]
    if unavailable:
        note += f" Not available in {_runs(len(unavailable))} (at {_angles(unavailable)})."
    return worst.model_copy(update={"passed": n_failed == 0, "note": note})


def _checks(result: QuadraticSweep, budget: int) -> list[ValidationCheck]:
    by_id: dict[str, list[tuple[float, ValidationCheck]]] = {}
    for run in result.runs:
        for check in run.computation.checks:
            by_id.setdefault(check.id, []).append((run.angle_deg, check))
    checks = [_aggregate(entries) for entries in by_id.values()]
    n_grid = sum(p.flew for p in result.points)
    checks += [
        ValidationCheck(
            id="interior_peaks",
            label="Interior peaks on the grid",
            value=float(result.interior_peaks),
            threshold=1.0,
            passed=result.interior_peaks <= 1,
            kind="informational",
            note="Grid points whose range beats both neighbours. Expected 1 (observed in every "
            "case measured: evidence, not a proof); 0 means the best grid point is at an edge. "
            "More than 1 means the refinement, which searches only next to the best grid "
            "point, may have found a local maximum rather than the highest one.",
        ),
        ValidationCheck(
            id="sweep_cost",
            label="Runs and solver evaluations",
            value=float(result.n_rhs_evaluations),
            threshold=None,
            passed=None,
            kind="informational",
            note=f"{_runs(len(result.runs))} of the 2.1 model ({n_grid} at grid angles, "
            f"{len(result.runs) - n_grid} in the refinement) used "
            f"{result.n_rhs_evaluations:,} right-hand-side evaluations, against the "
            f"sweep's budget of {budget:,}.",
        ),
    ]
    return checks


def run_angle_sweep(
    setup: QuadraticSetup,
    solver: SolverSettings,
    n_angles: int,
    *,
    max_rhs_evaluations: int = MAX_SWEEP_RHS_EVALUATIONS,
) -> QuadraticAngleSweepComputation:
    """The sweep, its exact vacuum references and its checks aggregated over every run."""
    start = time.perf_counter()
    result = sweep(setup, solver, n_angles, max_rhs_evaluations=max_rhs_evaluations)
    v0, h, g = setup.initial_speed, setup.launch_height, setup.gravity
    vacuum_angle, vacuum_best = vacuum_optimum(v0, h, g)
    v_t = setup.terminal_speed
    return QuadraticAngleSweepComputation(
        sweep=result,
        vacuum_ranges=[vacuum_range(v0, p.angle_deg, h, g) for p in result.points],
        vacuum_best_angle_deg=vacuum_angle,
        vacuum_best_range=vacuum_best,
        terminal_speed=None if math.isinf(v_t) else v_t,
        checks=_checks(result, max_rhs_evaluations),
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )


# --- The model's identity, units and labels (plan D1, D9, D10; used by the API, slice 3) ----

MODEL_INFO = ModelInfo(
    id="physics.projectile.quadratic_angle_sweep",
    version="1.0.0",
    name="Range versus launch angle (quadratic drag)",
    description="Range at evenly spaced launch angles from 0 to 90 degrees with quadratic drag "
    "F = -c|v|v, each point one full run of the quadratic-drag model (no formula exists), and "
    "the angle that maximises it, found by a bounded Brent search, with an estimate of its "
    "accuracy. Compared with the exact drag-free curve and optimum.",
)

UNITS: dict[str, str] = {
    "initial_speed": "m/s",
    "launch_height": "m",
    "mass": "kg",
    "drag_constant": "kg/m",
    "gravity": "m/s^2",
    "angle": "deg",
    "range": "m",
    "flight_time": "s",
    "max_height": "m",
    "vacuum_range": "m",
    "best_angle_uncertainty": "deg",
    "terminal_speed": "m/s",
    "n_rhs_evaluations": "count",
}

METHOD_NOTE = (
    "numerical: every range is one full run of the quadratic-drag model (an adaptive "
    "Runge-Kutta solve, SciPy solve_ivp), so each point equals a single run at that angle. "
    "The best angle is the best grid point refined by a bounded Brent search (within about 1e-6 "
    "degrees of the computed curve's flat peak); how far that peak can sit from the true one is "
    "the stated uncertainty, an estimate, not a bound. The drag-free curve and optimum are "
    "exact closed forms."
)
