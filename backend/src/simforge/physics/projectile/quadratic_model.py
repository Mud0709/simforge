"""Orchestrates one quadratic-drag run (roadmap 2.1, plan D4 and D7).

Pure computation: no HTTP, no database. The API layer (slice 3) adds the schemas, run
metadata and persistence. A run is: the stiffness guard, the numerical solution
(:mod:`.quadratic_numerical`), the exact references that exist (terminal speed, the same
launch with no drag and, for an exactly vertical launch only, the exact vertical flight),
the diagnostics R5 and R6, the proved bounds R7 checked on the step nodes, and plot series.

The stiffness guard (a design default of slice 2; the plan is amended in slice 5)
---------------------------------------------------------------------------------
The linear model refuses a run when the flight lasts more than 1e4 drag relaxation times,
k T, for an explicit method. Here the drag rate is kappa |v| (1/s), so the same quantity is
the *drag time*

    S = integral of kappa |v| dt = kappa L,

the path length L measured in drag lengths m/c. It sets the cost of an explicit method: the
velocity Jacobian of -kappa |v| v has eigenvalues -kappa |v| and -2 kappa |v|, so once the
step is limited by stability rather than accuracy, the number of steps grows like S
(measured: 2.5 to 16 right-hand-side evaluations per unit of S for DOP853 above S = 100).

S is not known before the run, so the guard uses a proved upper bound (:func:`drag_time_bound`)
whose slack is only *additive and logarithmic*, unlike the plan's kappa max(v0, v_t) T_bound,
which multiplies two loose bounds (T_bound alone is loose by up to ~7e5 times). On a 1007-point
grid within the planned input limits (slice 2 report) the plan's rule refused 323 runs for an
explicit method, 193 of which finished in at most 38 000 evaluations (true S <= 1e4); this
rule refused 130, none of which finished within 250 000 evaluations. Radau is L-stable, so
its step is not limited by the drag rate: it gets no drag-time limit (on the same grid every
run the plan's 1e7 limit would have refused finished in under 0.5 s).

Not bounded yet (slice 3's input limits must close it): Radau's cost is not bounded by S
either. When atol is far above the velocity scale min(v0, v_t) (measured: g = 0.01 m/s^2,
v0 = 1e-3 m/s, v_t = 3e-5 to 1e-4 m/s, atol = 1e-3 to 0.1), the velocity is not
error-controlled and Radau ran for over 20 s (some runs over 50 s, with overflow warnings)
even at S <= 1e6, which the plan's 1e7 limit would have accepted. At realistic scales (g =
9.8 m/s^2, v_t = 1 m/s, h = 1e5 m, S ~ 1e6) every tolerance tried finished in under 4 s.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo, ValidationCheck
from simforge.physics.projectile import quadratic_reference as qr
from simforge.physics.projectile.model import ASSUMPTIONS as LINEAR_ASSUMPTIONS
from simforge.physics.projectile.model import EXPLICIT_STIFFNESS_LIMIT
from simforge.physics.projectile.numerical import FloatArray, NumericalSolution
from simforge.physics.projectile.quadratic_numerical import QuadraticSetup, integrate
from simforge.physics.projectile.schemas import ErrorMetric, NumericalResult, SolverSettings

MODEL_INFO = ModelInfo(
    id="physics.projectile.quadratic_drag",
    version="1.0.0",
    name="Projectile motion with quadratic drag",
    description="2-D point-mass projectile under uniform gravity and quadratic drag "
    "F = -c|v|v. No exact 2-D solution exists: an adaptive Runge-Kutta integration is checked "
    "against the exact vertical flight, the drag-free limit, the terminal speed, the energy "
    "balance and a conserved quantity of the motion.",
)

UNITS: dict[str, str] = {
    "initial_speed": "m/s",
    "launch_angle_deg": "deg",
    "launch_height": "m",
    "mass": "kg",
    "drag_constant": "kg/m",
    "gravity": "m/s^2",
    "t": "s",
    "x": "m",
    "y": "m",
    "speed": "m/s",
    "flight_time": "s",
    "apex_time": "s",
    "range": "m",
    "max_height": "m",
    "impact_speed": "m/s",
    "terminal_speed": "m/s",
    "energy": "J",
    "max_energy_balance_residual": "dimensionless (fraction of E0)",
    "max_invariant_residual": "dimensionless (fraction of max 1/vx^2)",
    "drag_time_bound": "dimensionless (drag lengths m/c travelled, at most)",
    "flight_time_bound": "s",
}

ASSUMPTIONS: list[Assumption] = [
    *(a for a in LINEAR_ASSUMPTIONS if a.id != "linear_drag"),
    Assumption(
        id="quadratic_drag",
        statement="Drag is quadratic in speed, F = -c|v|v, with constant c = rho C_d A / 2 "
        "(kg/m). This is close to the drag on a ball in air at everyday speeds, as long as "
        "C_d stays constant; spin, lift and wind are ignored.",
    ),
]

NUMERICAL_NOTE = "numerical: adaptive Runge-Kutta solve (SciPy solve_ivp)"
VACUUM_NOTE = "exact: the same launch with no drag, from the textbook closed forms"
VERTICAL_NOTE = (
    "exact: the vertical flight with quadratic drag, rising with tan and falling with tanh "
    "(R1-R3); only for an exactly vertical launch, where the motion is one-dimensional"
)

# Check thresholds: GLOBAL_ERROR_FACTOR x (rtol + atol/v0) + ACCURACY_FLOOR. The global error
# of an adaptive solve is not bounded by rtol; how far it strays was *measured* (2728 runs:
# 5 speeds x 5 angles x 6 terminal speeds x 2 heights x 3 methods x rtol = atol in {1e-4,
# 1e-7, 1e-10, 1e-13}, one machine). Worst residual / (rtol + atol/v0): energy 490, invariant
# 8.5e3, speed bound excess 45, vertical flight time 61. The invariant's worst case is real:
# DOP853 takes ~15 steps on a nearly drag-free, nearly vertical flight and its vx is then off
# by 4e-10 relative at rtol = 1e-13 (checked against Radau). 1e4 leaves a margin of >= 14x at
# rtol >= 1e-10; at rtol = 1e-13, where error estimators work near rounding, the floor 1e-9
# leaves 2.4x over that DOP853 case.
# Revised in the slice 2 review: that case is nearly vertical, where vx0 << v0, so atol asks
# far less of vx than atol/v0 says; at default settings RK45 then *failed* correct runs (v0 =
# 1 m/s, 89.99 deg: vx off by 3.5e-6 relative, confirmed against DOP853 at rtol = 1e-13).
# The invariant now uses its own scale, rtol + atol/min(vx0, v_t) (_invariant_accuracy).
# Re-measured on 10 080 runs (v0 in {0.01, 1, 20, 300, 1e4} m/s; 8 angles up to 89.999 and
# 90; h in {0, 10, 2000} m; v_t in {1, 20, 1e3, inf} m/s; 3 methods; 7 (rtol, atol) pairs
# from (1e-13, 1e-14) to (1e-6, 0.1); one machine): no check failed, and the largest value /
# threshold was 0.081 (invariant), 0.012 (energy), 0.006 (speed bound excess), 0.18
# (vertical flight time, at atol = 0.1), so every check keeps a margin of >= 5x.
GLOBAL_ERROR_FACTOR = 1e4
ACCURACY_FLOOR = 1e-9


@dataclass(frozen=True, slots=True)
class VacuumFlight:
    """The same launch with no drag (exact)."""

    flight_time: float  # s
    range: float  # m
    max_height: float  # m
    apex_time: float  # s
    impact_speed: float  # m/s
    method_note: str


@dataclass(frozen=True, slots=True)
class VerticalReference:
    """The exact vertical flight (R3) and the numerical errors against it."""

    exact: qr.VerticalFlight
    flight_time: ErrorMetric
    apex_time: ErrorMetric
    max_height: ErrorMetric
    impact_speed: ErrorMetric
    method_note: str


@dataclass(frozen=True, slots=True)
class Diagnostics:
    max_energy_balance_residual: float  # max |KE + PE + W - E0| / E0 over step nodes
    max_invariant_residual: float | None  # max |I - I0| / max(1/vx^2); None if undefined
    invariant_note: str
    drag_time_bound: float  # proved upper bound on S = integral of kappa |v| dt
    flight_time_bound: float  # s, proved upper bound on the flight time (R7 ii)


@dataclass(frozen=True, slots=True)
class QuadraticSeries:
    """Uniformly resampled series for plotting, from the solver's dense output; the vacuum
    trajectory (exact) on its own time grid, since it lasts longer."""

    t: list[float]
    x: list[float]
    y: list[float]
    speed: list[float]
    kinetic_energy: list[float]
    potential_energy: list[float]
    drag_work: list[float]
    vacuum_t: list[float]
    vacuum_x: list[float]
    vacuum_y: list[float]


@dataclass(frozen=True, slots=True)
class QuadraticComputation:
    numerical: NumericalResult
    terminal_speed: float | None  # m/s, exact; None in vacuum (JSON has no infinity)
    vacuum: VacuumFlight
    vertical_reference: VerticalReference | None
    diagnostics: Diagnostics
    checks: list[ValidationCheck]
    series: QuadraticSeries
    elapsed_ms: float


# --- The stiffness guard --------------------------------------------------------------------


def _inverse_terminal_speed(setup: QuadraticSetup) -> float:
    """1/v_t, which is exactly 0 in vacuum (so no 0 * inf appears below)."""
    return 0.0 if setup.drag_constant == 0 else 1.0 / setup.terminal_speed


def _flight_time_bound(setup: QuadraticSetup) -> float:
    return qr.flight_time_bound(
        setup.initial_speed,
        setup.launch_angle_rad,
        setup.launch_height,
        setup.terminal_speed,
        setup.gravity,
    )


def drag_time_bound(setup: QuadraticSetup) -> float:
    """Proved upper bound on the drag time S = integral of kappa |v| dt (dimensionless).

        S <= ln(1 + kappa vx0 T_bound) + ln(1 + vy0^2 / v_t^2) + kappa h

    Proof. |v| <= |vx| + |vy|, so S <= kappa (X + Y), where X is the range and Y the total
    vertical distance travelled.
    - Range: dvx/dt = -kappa |v| vx <= -kappa vx^2 (since |v| >= vx > 0), so
      vx(t) <= vx0 / (1 + kappa vx0 t) and kappa X <= ln(1 + kappa vx0 T) <= ln(1 + kappa vx0
      T_bound), with T_bound the proved flight-time bound (R7 ii).
    - Height: while rising, dvy/dt = -g - kappa |v| vy <= -g - kappa vy^2 < 0, so with vy as
      the variable, dy = vy dvy / |dvy/dt| <= vy dvy / (g + kappa vy^2), and the climb is at
      most (1/(2 kappa)) ln(1 + vy0^2/v_t^2) (the exact vertical apex height R1 at speed vy0).
      After the apex vy < 0 for good (at vy = 0, dvy/dt = -g), so the ball comes down the
      climb plus h once: kappa Y = 2 kappa H + kappa h <= ln(1 + vy0^2/v_t^2) + kappa h.
    For a vertical launch every step is an equality. Since S >= kappa h, the bound exceeds S
    by at most the two logarithms (at most a few tens within the input limits). In vacuum
    kappa = 0 and 1/v_t = 0 exactly, so the bound is exactly 0, with no 0 * inf.
    """
    kappa, q = setup.kappa, _inverse_terminal_speed(setup)
    if kappa == 0:
        return 0.0
    horizontal = math.log1p(kappa * setup.vx0 * _flight_time_bound(setup))
    rise = math.log1p((setup.vy0 * q) ** 2)
    return horizontal + rise + kappa * setup.launch_height


def _guard(setup: QuadraticSetup, method: str) -> float:
    bound = drag_time_bound(setup)
    if method != "Radau" and bound > EXPLICIT_STIFFNESS_LIMIT:
        raise ModelDomainError(
            f"The flight travels up to {bound:.3g} drag lengths m/c (its drag time, the "
            f"integral of kappa |v| dt, is at most this), above the "
            f"{EXPLICIT_STIFFNESS_LIMIT:.0e} limit for {method}: an explicit method's step "
            "is limited by the drag rate, so the run would be prohibitively slow. Use "
            "method='Radau' for stiff problems."
        )
    return bound


# --- Exact references ---------------------------------------------------------------------


def _error(numerical: float, exact: float) -> ErrorMetric:
    abs_err = abs(numerical - exact)
    return ErrorMetric(absolute=abs_err, relative=abs_err / abs(exact) if exact != 0 else None)


def _vacuum(setup: QuadraticSetup) -> VacuumFlight:
    g, h, vx0, vy0 = setup.gravity, setup.launch_height, setup.vx0, setup.vy0
    t = (vy0 + math.sqrt(vy0 * vy0 + 2 * g * h)) / g  # vy0 >= 0: no cancellation
    return VacuumFlight(
        flight_time=t,
        range=vx0 * t,
        max_height=h + vy0 * vy0 / (2 * g),
        apex_time=vy0 / g,
        impact_speed=math.sqrt(setup.initial_speed**2 + 2 * g * h),
        method_note=VACUUM_NOTE,
    )


def _vertical(setup: QuadraticSetup, sol: NumericalSolution) -> VerticalReference | None:
    if not setup.is_vertical:
        return None
    exact = qr.vertical_flight(
        setup.initial_speed, setup.launch_height, setup.terminal_speed, setup.gravity
    )
    return VerticalReference(
        exact=exact,
        flight_time=_error(sol.flight_time, exact.flight_time),
        apex_time=_error(sol.apex_time, exact.apex_time),
        max_height=_error(sol.max_height, exact.max_height),
        impact_speed=_error(math.hypot(sol.vx[-1], sol.vy[-1]), exact.impact_speed),
        method_note=VERTICAL_NOTE,
    )


# --- Diagnostics ----------------------------------------------------------------------------


def _energies(
    setup: QuadraticSetup, y: FloatArray, vx: FloatArray, vy: FloatArray
) -> tuple[FloatArray, FloatArray]:
    kinetic: FloatArray = 0.5 * setup.mass * (vx**2 + vy**2)
    potential: FloatArray = setup.mass * setup.gravity * y
    return kinetic, potential


def _energy_residual(setup: QuadraticSetup, sol: NumericalSolution) -> float:
    ke, pe = _energies(setup, sol.y, sol.vx, sol.vy)
    e0 = float(ke[0] + pe[0])  # > 0: speed >= 1e-3 m/s and mass >= 1e-6 kg (planned limits)
    return float(np.max(np.abs(ke + pe + sol.drag_work - e0)) / e0)


def _invariant_residual(setup: QuadraticSetup, sol: NumericalSolution) -> tuple[float | None, str]:
    """max |I - I0| / max(1/vx^2) over the step nodes (R6), or None with the reason.

    Normalisation: late in a long fall vx decays like e^(-t/tau), so I's terms grow like
    1/vx^2 and nearly cancel while I stays at I0. A relative state error of ~rtol then moves
    I by ~rtol / vx^2, which divided by I0 can exceed 1e17 (measured) although the solve is
    accurate. Dividing by the largest 1/vx^2 makes the residual a relative error of the
    state. Its weakness: errors early in the flight, where 1/vx^2 is small, are diluted.
    """
    if setup.is_vertical:
        return None, "Undefined for a vertical launch: vx = 0 exactly, and I divides by vx."
    vx_min = float(np.min(sol.vx))
    undefined = (
        f"Undefined in this run: vx fell to {vx_min:.3g} m/s, where I (which divides by "
        "vx^2) is not defined or overflows. The true vx stays positive but decays like "
        f"e^(-t/tau) in a long fall; below the absolute tolerance atol = {sol.atol:g} the "
        "solver does not control its sign or size."
    )
    if vx_min <= 0:
        return None, undefined
    v_t = setup.terminal_speed
    # A tiny positive vx can overflow 1/vx^2 or v vy / vx^2 (JSON has no infinity).
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        scale = float(np.max(1.0 / sol.vx**2))
        inv = qr.hodograph_invariant(sol.vx, sol.vy, v_t, setup.gravity)
        i0 = qr.hodograph_invariant(
            np.array([setup.vx0]), np.array([setup.vy0]), v_t, setup.gravity
        )[0]
        residual = float(np.max(np.abs(inv - i0)) / scale)
    if not (math.isfinite(scale) and math.isfinite(residual)):
        return None, undefined
    note = "max |I - I0| / max(1/vx^2) over the solver's step nodes."
    return residual, note


# --- Checks ----------------------------------------------------------------------------------


def _accuracy(setup: QuadraticSetup, solver: SolverSettings) -> float:
    """The requested relative accuracy: rtol, plus atol relative to the launch speed."""
    return solver.rtol + solver.atol / setup.initial_speed


def _invariant_accuracy(setup: QuadraticSetup, solver: SolverSettings) -> float:
    """The requested relative accuracy of the velocities that I depends on.

    I tests vx relative to itself (vx0 is small for a nearly vertical launch) and, late in a
    long fall, vy against -v_t; atol bounds each component absolutely, so the relative
    accuracy asked of them is rtol + atol / min(vx0, v_t), not rtol + atol / v0. Only called
    when I is defined, so vx0 > 0; v_t is infinite in vacuum, leaving vx0.
    """
    return solver.rtol + solver.atol / min(setup.vx0, setup.terminal_speed)


def _threshold(accuracy: float) -> float:
    return GLOBAL_ERROR_FACTOR * accuracy + ACCURACY_FLOOR


def _diagnostic(
    check_id: str, label: str, value: float, threshold: float, note: str
) -> ValidationCheck:
    return ValidationCheck(
        id=check_id,
        label=label,
        value=value,
        threshold=threshold,
        passed=value <= threshold,
        kind="numerical_diagnostic",
        note=note,
    )


def _checks(
    setup: QuadraticSetup,
    solver: SolverSettings,
    sol: NumericalSolution,
    diagnostics: Diagnostics,
    vertical: VerticalReference | None,
) -> list[ValidationCheck]:
    tol = _threshold(_accuracy(setup, solver))
    factor = f"{GLOBAL_ERROR_FACTOR:g} x (rtol + atol/v0) + {ACCURACY_FLOOR:g}"
    checks = [
        _diagnostic(
            "energy_balance",
            "Energy balance KE + PE + W = E0",
            diagnostics.max_energy_balance_residual,
            tol,
            "max |KE + PE + W - E0| / E0 over the step nodes, with W integrated from c|v|^3 "
            f"independently of the force. Exactly 0 for the true motion. Threshold: {factor}.",
        )
    ]
    residual = diagnostics.max_invariant_residual
    if residual is None:
        checks.append(
            ValidationCheck(
                id="hodograph_invariant",
                label="Hodograph invariant (not available)",
                value=float(np.min(sol.vx)),
                threshold=None,
                passed=None,
                kind="informational",
                note=f"Value: the smallest vx (m/s). {diagnostics.invariant_note}",
            )
        )
    else:
        checks.append(
            _diagnostic(
                "hodograph_invariant",
                "Hodograph invariant I is constant",
                residual,
                _threshold(_invariant_accuracy(setup, solver)),
                "max |I - I0| / max(1/vx^2) over the step nodes, I = 1/vx^2 + (kappa/g)"
                "[v vy/vx^2 + asinh(vy/vx)]: the one check here that tests the coupling of x "
                "and y through |v|. Constant for the true motion. Threshold: "
                f"{GLOBAL_ERROR_FACTOR:g} x (rtol + atol/min(vx0, v_t)) + {ACCURACY_FLOOR:g}.",
            )
        )
    if setup.drag_constant > 0:
        bound = qr.speed_bound(setup.initial_speed, setup.terminal_speed)
        checks.append(
            _diagnostic(
                "speed_bound",
                "Speed <= max(v0, v_t) (proved)",
                float(np.max(np.hypot(sol.vx, sol.vy))) / bound,
                1.0 + tol,
                "Largest speed on the step nodes divided by max(v0, v_t); proved <= 1 for the "
                "true motion (R7 i). Threshold: 1 + " + factor + ".",
            )
        )
    checks.append(
        _diagnostic(
            "flight_time_bound",
            "Flight time <= T_bound (proved)",
            sol.flight_time / diagnostics.flight_time_bound,
            1.0 + tol,
            "Numerical flight time divided by the proved bound T_bound (R7 ii), which is "
            "exact in vacuum and loose with drag. Threshold: 1 + " + factor + ".",
        )
    )
    if vertical is not None and vertical.flight_time.relative is not None:
        checks.append(
            _diagnostic(
                "vertical_flight_time",
                "Flight time vs the exact vertical flight",
                vertical.flight_time.relative,
                tol,
                "Relative error of the numerical flight time against the exact R3 value "
                f"(tan up, tanh down). Threshold: {factor}.",
            )
        )
    checks.append(
        ValidationCheck(
            id="drag_time",
            label="Drag time (upper bound)",
            value=diagnostics.drag_time_bound,
            threshold=None,
            passed=None,
            kind="informational",
            note="Proved upper bound on the integral of kappa |v| dt, the path length in drag "
            "lengths m/c: how stiff the run is. Explicit methods are refused above "
            f"{EXPLICIT_STIFFNESS_LIMIT:.0e}; Radau has no such limit.",
        )
    )
    return checks


# --- The run -----------------------------------------------------------------------------------


def _numerical_metrics(sol: NumericalSolution) -> NumericalResult:
    return NumericalResult(
        flight_time=sol.flight_time,
        range=float(sol.x[-1]),
        max_height=sol.max_height,
        apex_time=sol.apex_time,
        impact_speed=float(math.hypot(sol.vx[-1], sol.vy[-1])),
        method=sol.method,
        rtol=sol.rtol,
        atol=sol.atol,
        n_steps=sol.n_steps,
        n_rhs_evaluations=sol.n_rhs_evaluations,
    )


def _series(
    setup: QuadraticSetup, sol: NumericalSolution, vacuum: VacuumFlight, n: int
) -> QuadraticSeries:
    t = np.linspace(0.0, sol.flight_time, n)
    xs, ys, vxs, vys, ws = sol.sample(t)
    ke, pe = _energies(setup, ys, vxs, vys)
    tv = np.linspace(0.0, vacuum.flight_time, n)
    return QuadraticSeries(
        t=t.tolist(),
        x=xs.tolist(),
        y=ys.tolist(),
        speed=np.hypot(vxs, vys).tolist(),
        kinetic_energy=ke.tolist(),
        potential_energy=pe.tolist(),
        drag_work=ws.tolist(),
        vacuum_t=tv.tolist(),
        vacuum_x=(setup.vx0 * tv).tolist(),
        vacuum_y=(setup.launch_height + setup.vy0 * tv - setup.gravity * tv**2 / 2).tolist(),
    )


def run(
    setup: QuadraticSetup, solver: SolverSettings, *, n_samples: int = 400
) -> QuadraticComputation:
    start = time.perf_counter()
    drag_time = _guard(setup, solver.method)
    t_bound = _flight_time_bound(setup)
    # Twice the proved bound: the bound is exact in vacuum, and a cap equal to the landing
    # time could leave the landing event at the very end of the interval, where rounding can
    # hide the sign change. The landing itself is found by the solver's event detection.
    sol = integrate(
        setup, method=solver.method, rtol=solver.rtol, atol=solver.atol, t_max=2.0 * t_bound
    )
    residual, invariant_note = _invariant_residual(setup, sol)
    diagnostics = Diagnostics(
        max_energy_balance_residual=_energy_residual(setup, sol),
        max_invariant_residual=residual,
        invariant_note=invariant_note,
        drag_time_bound=drag_time,
        flight_time_bound=t_bound,
    )
    vertical = _vertical(setup, sol)
    vacuum = _vacuum(setup)
    v_t = setup.terminal_speed
    return QuadraticComputation(
        numerical=_numerical_metrics(sol),
        terminal_speed=None if math.isinf(v_t) else v_t,
        vacuum=vacuum,
        vertical_reference=vertical,
        diagnostics=diagnostics,
        checks=_checks(setup, solver, sol, diagnostics, vertical),
        series=_series(setup, sol, vacuum, n_samples),
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )
