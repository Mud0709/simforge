"""Orchestrates one oscillator run (roadmap 2.3, seam 3): guard, solve, diagnostics, checks.

Pure computation: no HTTP, no database. The API layer (slice 3) validates the request
(``schemas.OscillatorParameters``), adds run metadata and persistence. A run is: the
stiffness guard, the numerical solve (:mod:`.numerical`, in scaled units), the exact solution
at the solver's step nodes (:mod:`.analytical`), the diagnostics and checks of plan D8, the
closed forms of D12 (derived quantities, steady state, the resonance curve of D9) and plot
series resampled from the solver's dense output.

Scales (plan D5, D8; the author's decision of 2026-11-09): the displacement scale X is
``analytical.scale`` (a proved bound on |x| over the run, from the inputs only), the velocity
scale is V = w0 X and the energy scale k X^2 = m V^2. Every error below is in these units.
V = w0 X is the speed of a free oscillation of amplitude X; a drive far above w0 moves the
mass faster (max|v| / V reached 50 at w = 100 w0, measured), and the thresholds were measured
with that corner included (``ENERGY_BALANCE_FACTOR``).

Check thresholds (plan D8, measured in slice 2): ``FACTOR (rtol + atol) (1 +
ERROR_GROWTH_PER_CYCLE cycles) + FLOOR`` in scaled units, one FACTOR and FLOOR per check. The
global error of an adaptive solve is not bounded by its tolerances, and the phase error of an
oscillation accumulates, so each factor is the worst measured need times a margin of at least
10, and the threshold grows with the cycles; the numbers, the corners and the machine are in
the comments below, in ``tests/physics/oscillator_thresholds.py`` and in
``SCIENTIFIC_VALIDATION.md``. A threshold above 1 (in units of X, V or k X^2) would pass an
error as large as the motion itself, so its note says the check is uninformative there (the
loosest tolerances allowed, or long runs at loose ones).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo, ValidationCheck
from simforge.physics.oscillator import analytical, numerical
from simforge.physics.oscillator.analytical import (
    Derived,
    FloatArray,
    OscillatorInputs,
    SteadyState,
)
from simforge.physics.oscillator.numerical import OscillatorSolution
from simforge.physics.projectile.model import EXPLICIT_STIFFNESS_LIMIT
from simforge.physics.projectile.numerical import SolverMethod
from simforge.physics.projectile.schemas import SolverSettings

MODEL_INFO = ModelInfo(
    id="physics.oscillator",
    version="1.0.0",
    name="Harmonic oscillator (simple, damped, driven)",
    description="A mass on a spring with linear damping F = -b v and a driving force "
    "F0 cos(w t). The exact solution, valid in every regime, is compared against an adaptive "
    "Runge-Kutta (or Radau) integration of the dimensionless equation.",
)

UNITS: dict[str, str] = {
    "mass": "kg",
    "spring_constant": "N/m",
    "damping_coefficient": "kg/s",
    "drive_amplitude": "N",
    "drive_angular_frequency": "rad/s",
    "initial_displacement": "m",
    "initial_velocity": "m/s",
    "duration": "s",
    "t": "s",
    "x": "m",
    "v": "m/s",
    "energy": "J",
    "natural_angular_frequency": "rad/s",
    "damping_rate": "1/s",
    "damping_ratio": "dimensionless",
    "quality_factor": "dimensionless",
    "damped_angular_frequency": "rad/s",
    "overdamped_rate": "1/s",
    "damped_period": "s",
    "scale": "m (X, a proved bound on |x| over the run)",
    "velocity_scale": "m/s (V = w0 X)",
    "amplitude": "m",
    "phase_lag": "rad",
    "atol": "dimensionless, a fraction of the scale X (m) for x, of w0 X for v and of k X^2 "
    "for the works (the solver integrates the scaled equation)",
    "max_displacement_error": "dimensionless (fraction of X)",
    "max_velocity_error": "dimensionless (fraction of w0 X)",
    "max_energy_balance_residual": "dimensionless (fraction of k X^2)",
    "free_decay_period_residual": "dimensionless (w0 times an error in s, i.e. radians)",
    "free_decay_ratio_residual": "dimensionless (fraction of X)",
    "remaining_transient": "dimensionless (fraction of the steady amplitude A)",
    "cycles": "dimensionless (duration max(w0, w) / 2 pi)",
    "stiffness_number": "dimensionless (fastest decay or oscillation rate times duration)",
}

ASSUMPTIONS: list[Assumption] = [
    Assumption(
        id="point_mass_on_ideal_spring",
        statement="A point mass on a massless spring that obeys Hooke's law, F = -k x, at "
        "every extension (a real spring stops being linear when stretched far).",
    ),
    Assumption(
        id="linear_damping",
        statement="Damping is linear in velocity, F = -b v, with constant b (viscous "
        "damping, e.g. a slow vane in oil). Friction between dry surfaces (constant force) "
        "and air drag at speed (closer to quadratic) are not modelled.",
    ),
    Assumption(
        id="sinusoidal_drive",
        statement="The driving force is F0 cos(w t), starting at its maximum at t = 0, with "
        "constant amplitude and frequency, and is not affected by the motion it drives.",
    ),
    Assumption(
        id="one_dimension",
        statement="Motion along one line; gravity, if present, only shifts the equilibrium "
        "(x is measured from it) and does not change the motion.",
    ),
    Assumption(
        id="constant_parameters",
        statement="m, k and b are constant during the run: no wear, heating or change of mass.",
    ),
]

METHOD_NOTE = (
    "numerical: SciPy solve_ivp on the dimensionless equation (tau = w0 t, xi = x / X, "
    "eta = v / (w0 X)), with the damping and drive works integrated alongside from b v^2 and "
    "F0 cos(w t) v. exact: the closed-form solution (one formula for every regime), evaluated "
    "in float64 to within a few eps (Q + w0 T + A/X + 1) X (measured in slice 1). formula: the "
    "steady state and the resonance curve, exact closed forms."
)

# ======================= Thresholds (measured in slice 2) ===================================
# threshold = FACTOR (rtol + atol) (1 + ERROR_GROWTH_PER_CYCLE cycles) + FLOOR, scaled units.
# Each FACTOR is the smallest 1-2-5 value at least 10x the worst need measured on 1608 runs
# inside the limits (corner grid, 100-cycle runs, free decays zeta 0.01-0.99, 600 seeded
# random runs; worst value / threshold 0.10). The growth term is measured: the global error
# grew in proportion to the cycles (displacement error / (rtol + atol), undamped, DOP853 at
# the default pair: 75 at 100 cycles, 747 at 1000). The energy factor is set by drives far
# above w0, where max|v| reaches 50 w0 X, so it is loose for slower motions. The values equal
# tests/physics/oscillator_thresholds.py's (the tests check that they agree), whose comments
# and SCIENTIFIC_VALIDATION.md ("physics.oscillator") record each measurement.
DISPLACEMENT_ERROR_FACTOR = 50.0
DISPLACEMENT_ERROR_FLOOR = 1e-9
VELOCITY_ERROR_FACTOR = 500.0
VELOCITY_ERROR_FLOOR = 1e-9
ENERGY_BALANCE_FACTOR = 2e4
ENERGY_BALANCE_FLOOR = 1e-9
FREE_DECAY_PERIOD_FACTOR = 1e3
FREE_DECAY_PERIOD_FLOOR = 1e-9
FREE_DECAY_RATIO_FACTOR = 20.0
FREE_DECAY_RATIO_FLOOR = 1e-9
ERROR_GROWTH_PER_CYCLE = 1.0
# The most cycles, duration max(w0, w) / 2 pi, a run may have (plan D6; enforced by the API
# schema, schemas.OscillatorParameters). Measured: at the default settings (DOP853, rtol =
# atol = 1e-10) 500 cycles took 0.8 to 1.4 s, within D6's 2 s (1000 cycles: up to 2.5 s).
# Other settings are slower (Radau at the default pair: 36 to 78 s at 500 cycles); a cycle
# limit alone does not bound them.
MAX_CYCLES = 500
# ============================================================================================

# The free-decay checks need a second maximum of at least this fraction of X (_free_decay):
# below it the located time of the maximum is set by the solver's tolerance, not the physics.
# Measured: with this rule the worst period residual was 0.077 of its threshold on 840 free
# decays (zeta 0.01 to 0.99); without it, 1e9 (rtol + atol) at zeta = 0.9 for a correct solve.
FREE_DECAY_MIN_MAXIMUM = 1e-3

# Number of drive frequencies on the resonance curve (plan D9), from 0 to max(3 w0, 1.2 w).
RESONANCE_POINTS = 241

_FACTORS: dict[str, tuple[float, float]] = {
    "displacement_error": (DISPLACEMENT_ERROR_FACTOR, DISPLACEMENT_ERROR_FLOOR),
    "velocity_error": (VELOCITY_ERROR_FACTOR, VELOCITY_ERROR_FLOOR),
    "energy_balance": (ENERGY_BALANCE_FACTOR, ENERGY_BALANCE_FLOOR),
    "free_decay_period": (FREE_DECAY_PERIOD_FACTOR, FREE_DECAY_PERIOD_FLOOR),
    "free_decay_ratio": (FREE_DECAY_RATIO_FACTOR, FREE_DECAY_RATIO_FLOOR),
}


@dataclass(frozen=True, slots=True)
class NumericalSummary:
    final_displacement: float  # m, x at t = duration
    final_velocity: float  # m/s
    n_steps: int
    n_rhs_evaluations: int
    method: SolverMethod
    rtol: float
    atol: float


@dataclass(frozen=True, slots=True)
class Diagnostics:
    max_displacement_error: float  # max |x - x_exact| / X over the step nodes
    max_velocity_error: float  # max |v - v_exact| / (w0 X)
    max_energy_balance_residual: float  # max |KE + PE + W_damp - W_drive - E0| / (k X^2)
    free_decay_period_residual: float | None  # w0 |(t2 - t1) - T_d|; free underdamped only
    free_decay_ratio_residual: float | None  # |x2 - e^{-gamma T_d} x1| / X
    remaining_transient: float | None  # transient left at t = T / A; driven and damped only
    cycles: float  # T max(w0, w) / 2 pi
    stiffness_number: float  # (gamma + beta) T when overdamped, w0 T otherwise


@dataclass(frozen=True, slots=True)
class OscillatorSeries:
    """Evenly resampled series for plotting (SI). x, v and the works come from the solver's
    dense output; x_exact, v_exact and the envelope from the exact solution."""

    t: list[float]
    x: list[float]
    v: list[float]
    x_exact: list[float]
    v_exact: list[float]
    envelope: list[float] | None  # R e^{-gamma t}; None unless underdamped
    kinetic_energy: list[float]
    potential_energy: list[float]
    damping_work: list[float]
    drive_work: list[float]


@dataclass(frozen=True, slots=True)
class ResonanceCurve:
    """The steady state against drive frequency, from the formula (OR1; plan D9)."""

    angular_frequency: list[float]  # rad/s, from 0 to max(3 w0, 1.2 w)
    amplitude: list[float]  # m
    phase_lag: list[float]  # rad, in [0, pi]


@dataclass(frozen=True, slots=True)
class OscillatorComputation:
    derived: Derived
    scale: float  # X, m
    velocity_scale: float  # V = w0 X, m/s
    steady_state: SteadyState | None
    numerical: NumericalSummary
    diagnostics: Diagnostics
    checks: list[ValidationCheck]
    series: OscillatorSeries
    resonance: ResonanceCurve | None
    elapsed_ms: float


# --- The stiffness guard ---------------------------------------------------------------------


def stiffness_number(d: Derived, duration: float) -> float:
    """S = |fastest eigenvalue| x T (dimensionless).

    The eigenvalues of x'' + 2 gamma x' + w0^2 x = 0 are -gamma +- sqrt(gamma^2 - w0^2). When
    overdamped both are real and the fastest is -(gamma + beta); otherwise their modulus is
    w0 (a complex pair, or the double root -w0 at critical damping). An explicit method's
    step is limited to about 1/|eigenvalue| by stability, so S sets its least number of steps.
    """
    if d.overdamped_rate is not None:
        return (d.damping_rate + d.overdamped_rate) * duration
    return d.natural_angular_frequency * duration


def _guard(stiffness: float, method: str) -> None:
    if method != "Radau" and stiffness > EXPLICIT_STIFFNESS_LIMIT:
        raise ModelDomainError(
            f"The run's stiffness number (fastest decay rate times duration) is "
            f"{stiffness:.3g}, above the {EXPLICIT_STIFFNESS_LIMIT:.0e} limit for {method}: "
            "an explicit method's step is limited by the fast decay, so the run would be "
            "prohibitively slow. Use method='Radau' for stiff (heavily damped) runs, or "
            "shorten the duration."
        )


# --- Diagnostics -----------------------------------------------------------------------------


def _node_errors(p: OscillatorInputs, sol: OscillatorSolution) -> tuple[float, float, float]:
    """(max |x - x_exact| / X, max |v - v_exact| / (w0 X), max energy residual / k X^2)."""
    x_scale = sol.scale
    w0 = sol.natural_angular_frequency
    m, k = p.mass, p.spring_constant
    x_exact, v_exact = analytical.state(p, sol.t)
    dx = float(np.max(np.abs(sol.x - x_exact))) / x_scale
    dv = float(np.max(np.abs(sol.v - v_exact))) / (w0 * x_scale)
    e0 = 0.5 * m * p.initial_velocity**2 + 0.5 * k * p.initial_displacement**2
    balance = 0.5 * m * sol.v**2 + 0.5 * k * sol.x**2 + sol.damping_work - sol.drive_work - e0
    de = float(np.max(np.abs(balance))) / (k * x_scale**2)
    return dx, dv, de


def _free_decay(
    p: OscillatorInputs, d: Derived, sol: OscillatorSolution
) -> tuple[float | None, float | None]:
    """Residuals of OR4 on the first two interior maxima, in scaled units, or (None, None).

    For a free underdamped motion successive maxima are exactly T_d apart and their ratio is
    exactly e^{-gamma T_d}, whatever the initial conditions.

    Only when the second maximum is at least ``FREE_DECAY_MIN_MAXIMUM`` of X: at a maximum
    the acceleration is -w0^2 x, so an error dv in the velocity moves the time where v = 0 by
    dv / (w0^2 x), i.e. w0 dt = d(v / w0 X) / (x / X). Near critical damping the motion has
    decayed to almost nothing by its second maximum (e^{-13} per period at zeta = 0.9), and
    the located times are then set by the solver's tolerance, not by the physics (measured:
    the period residual reached 1e9 x (rtol + atol) at zeta = 0.9 for a correct solve).
    """
    if p.drive_amplitude != 0 or d.regime != "underdamped" or len(sol.maxima_t) < 2:
        return None, None
    if float(sol.maxima_x[1]) < FREE_DECAY_MIN_MAXIMUM * sol.scale:
        return None, None
    period = d.damped_period
    assert period is not None  # underdamped
    (t1, t2), (x1, x2) = sol.maxima_t[:2], sol.maxima_x[:2]
    period_residual = d.natural_angular_frequency * abs(float(t2 - t1) - period)
    ratio = math.exp(-d.damping_rate * period)
    ratio_residual = abs(float(x2) - ratio * float(x1)) / sol.scale
    return period_residual, ratio_residual


def _remaining_transient(
    p: OscillatorInputs, steady: SteadyState | None, duration: float
) -> float | None:
    """sqrt(x_h(T)^2 + (v_h(T)/w0)^2) / A, the transient left at the end (driven and damped).

    The transient x_h = x - x_p is itself a free motion (F0 = 0) from x_h(0) = x0 - A cos delta
    and v_h(0) = v0 - w A sin delta (OR2), so it is evaluated exactly as that free motion,
    never as the difference x - x_p (which would cancel to ~eps A).
    """
    if steady is None:
        return None
    a, delta = steady.amplitude, steady.phase_lag
    w = p.drive_angular_frequency
    free = OscillatorInputs(
        mass=p.mass,
        spring_constant=p.spring_constant,
        damping_coefficient=p.damping_coefficient,
        initial_displacement=p.initial_displacement - a * math.cos(delta),
        initial_velocity=p.initial_velocity - w * a * math.sin(delta),
    )
    x_h, v_h = analytical.state(free, np.array([duration]))
    w0 = math.sqrt(p.spring_constant / p.mass)
    return math.hypot(float(x_h[0]), float(v_h[0]) / w0) / a


def threshold(check_id: str, solver: SolverSettings, cycles: float) -> float:
    """The check's threshold, FACTOR (rtol + atol) (1 + growth cycles) + FLOOR (scaled)."""
    factor, floor = _FACTORS[check_id]
    return factor * (solver.rtol + solver.atol) * (1.0 + ERROR_GROWTH_PER_CYCLE * cycles) + floor


def _formula(check_id: str) -> str:
    factor, floor = _FACTORS[check_id]
    growth = f" x (1 + {ERROR_GROWTH_PER_CYCLE:g} x cycles)" if ERROR_GROWTH_PER_CYCLE != 0 else ""
    return f"{factor:g} x (rtol + atol){growth} + {floor:g}, measured on a corner grid"


def _diagnostic(
    check_id: str, label: str, value: float, solver: SolverSettings, cycles: float, note: str
) -> ValidationCheck:
    limit = threshold(check_id, solver, cycles)
    note = f"{note} Threshold: {_formula(check_id)}."
    if limit > 1.0:
        note += (
            " Uninformative at these tolerances: the threshold exceeds the scale itself, so "
            "an error as large as the motion would pass; tighten rtol and atol for a "
            "meaningful check."
        )
    return ValidationCheck(
        id=check_id,
        label=label,
        value=value,
        threshold=limit,
        passed=value <= limit,
        kind="numerical_diagnostic",
        note=note,
    )


def _checks(
    solver: SolverSettings, diag: Diagnostics, sol: OscillatorSolution
) -> list[ValidationCheck]:
    cycles = diag.cycles
    checks = [
        _diagnostic(
            "displacement_error",
            "Displacement vs the exact solution",
            diag.max_displacement_error,
            solver,
            cycles,
            "max |x - x_exact| / X over the solver's step nodes, X the proved bound on |x|.",
        ),
        _diagnostic(
            "velocity_error",
            "Velocity vs the exact solution",
            diag.max_velocity_error,
            solver,
            cycles,
            "max |v - v_exact| / (w0 X) over the solver's step nodes.",
        ),
        _diagnostic(
            "energy_balance",
            "Energy balance KE + PE + W_damp - W_drive = E0",
            diag.max_energy_balance_residual,
            solver,
            cycles,
            "max |KE + PE + W_damp - W_drive - E0| / (k X^2) over the step nodes, with both "
            "works integrated from b v^2 and F0 cos(w t) v, independently of the force. "
            "Exactly 0 for the true motion.",
        ),
    ]
    if diag.free_decay_period_residual is not None:
        checks.append(
            _diagnostic(
                "free_decay_period",
                "Time between maxima = T_d (exact)",
                diag.free_decay_period_residual,
                solver,
                cycles,
                "w0 |(t2 - t1) - T_d| for the first two maxima of the free decay (located by "
                "an event on v = 0); exactly 0 for the true motion (OR4).",
            )
        )
    if diag.free_decay_ratio_residual is not None:
        checks.append(
            _diagnostic(
                "free_decay_ratio",
                "Ratio of successive maxima = e^(-gamma T_d) (exact)",
                diag.free_decay_ratio_residual,
                solver,
                cycles,
                "|x2 - e^(-gamma T_d) x1| / X for the first two maxima of the free decay; "
                "exactly 0 for the true motion (OR4).",
            )
        )
    if diag.remaining_transient is not None:
        checks.append(
            ValidationCheck(
                id="steady_state_reached",
                label="Steady state reached (transient left at the end)",
                value=diag.remaining_transient,
                threshold=None,
                passed=None,
                kind="informational",
                note="The transient left at t = T, sqrt(x_h^2 + (v_h/w0)^2), as a fraction of "
                "the steady amplitude A; computed exactly from the closed form. Small values "
                "mean the motion has settled into x_p = A cos(w t - delta).",
            )
        )
    checks.append(
        ValidationCheck(
            id="cost",
            label="Cost (right-hand-side evaluations)",
            value=float(sol.n_rhs_evaluations),
            threshold=None,
            passed=None,
            kind="informational",
            note=f"{sol.n_steps} steps over {cycles:.4g} cycles; stiffness number "
            f"{diag.stiffness_number:.3g} (explicit methods are refused above "
            f"{EXPLICIT_STIFFNESS_LIMIT:.0e}; Radau has no such limit).",
        )
    )
    return checks


# --- Series and the resonance curve -----------------------------------------------------------


def _series(
    p: OscillatorInputs, sol: OscillatorSolution, duration: float, n: int
) -> OscillatorSeries:
    t: FloatArray = np.linspace(0.0, duration, n)
    x, v, w_damp, w_drive = sol.sample(t)
    x_exact, v_exact = analytical.state(p, t)
    envelope = analytical.transient_envelope(p, t)
    return OscillatorSeries(
        t=t.tolist(),
        x=x.tolist(),
        v=v.tolist(),
        x_exact=x_exact.tolist(),
        v_exact=v_exact.tolist(),
        envelope=None if envelope is None else envelope.tolist(),
        kinetic_energy=(0.5 * p.mass * v**2).tolist(),
        potential_energy=(0.5 * p.spring_constant * x**2).tolist(),
        damping_work=w_damp.tolist(),
        drive_work=w_drive.tolist(),
    )


def _resonance(p: OscillatorInputs, steady: SteadyState | None) -> ResonanceCurve | None:
    if steady is None:  # undriven, or b = 0 (A has a pole at w0)
        return None
    w = analytical.resonance_frequencies(p, RESONANCE_POINTS)
    amplitude, phase = analytical.resonance_curve(p, w)
    return ResonanceCurve(w.tolist(), amplitude.tolist(), phase.tolist())


# --- The run -----------------------------------------------------------------------------------


def run(
    inputs: OscillatorInputs,
    duration: float,
    solver: SolverSettings,
    *,
    n_samples: int = 400,
) -> OscillatorComputation:
    """One run: guard, numerical solve, exact comparison, checks, closed forms, series."""
    start = time.perf_counter()
    p = inputs
    d = analytical.derived(p)
    x_scale = analytical.scale(p, duration)
    if x_scale == 0:
        raise ModelDomainError(
            "Nothing moves: initial_displacement, initial_velocity and drive_amplitude are all "
            "0. Set at least one of them."
        )
    stiffness = stiffness_number(d, duration)
    _guard(stiffness, solver.method)

    sol = numerical.integrate(
        p,
        duration=duration,
        scale=x_scale,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
    )
    dx, dv, de = _node_errors(p, sol)
    period_residual, ratio_residual = _free_decay(p, d, sol)
    steady = analytical.steady_state(p)
    w0 = d.natural_angular_frequency
    diagnostics = Diagnostics(
        max_displacement_error=dx,
        max_velocity_error=dv,
        max_energy_balance_residual=de,
        free_decay_period_residual=period_residual,
        free_decay_ratio_residual=ratio_residual,
        remaining_transient=_remaining_transient(p, steady, duration),
        cycles=duration * max(w0, p.drive_angular_frequency) / (2 * math.pi),
        stiffness_number=stiffness,
    )
    numerical_summary = NumericalSummary(
        final_displacement=float(sol.x[-1]),
        final_velocity=float(sol.v[-1]),
        n_steps=sol.n_steps,
        n_rhs_evaluations=sol.n_rhs_evaluations,
        method=sol.method,
        rtol=sol.rtol,
        atol=sol.atol,
    )
    return OscillatorComputation(
        derived=d,
        scale=x_scale,
        velocity_scale=w0 * x_scale,
        steady_state=steady,
        numerical=numerical_summary,
        diagnostics=diagnostics,
        checks=_checks(solver, diagnostics, sol),
        series=_series(p, sol, duration, n_samples),
        resonance=_resonance(p, steady),
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )
