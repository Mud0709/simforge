"""The simulated resonance curve (roadmap 2.5, plan D6-D10, slice 3).

Pure computation; no HTTP, no database, no Pydantic (the API is slice 4). At each drive
frequency w of an evenly spaced grid, the 2.3 oscillator is started from rest, run until its
transient has died down to a stated fraction of the steady amplitude, and its steady
amplitude and phase lag are read off by a lock-in over whole drive periods. The resulting
curve is compared with the closed form R1 point by point, with bounds that are proved given
the run's measured trajectory error. The peak is refined by a bounded search (the 2.5 sweep
driver, :mod:`simforge.numerics.sweep`).

Notation (SI): w0 = sqrt(k/m), gamma = b/2m, f = F0/m, T = 2 pi/w, x_p = A cos(w t - delta).

R1, R2 (closed forms, proved and tested in 2.3; ``analytical.steady_state``)
---------------------------------------------------------------------------
A(w) = f / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2), delta = atan2(2 gamma w, w0^2 - w^2) in
[0, pi]; w_r = sqrt(w0^2 - 2 gamma^2) and A_max = f / (2 gamma wd), wd = sqrt(w0^2 -
gamma^2), when zeta < 1/sqrt 2.

R3 (the lock-in is exact on a sinusoid; proved)
-----------------------------------------------
Take M >= 3 samples per period over N whole periods: t_j = t_s + j T/M, j = 0..NM - 1, and
c = (2/NM) sum x_j cos(w t_j), s = (2/NM) sum x_j sin(w t_j). For x = A cos(w t - delta),
x_j cos(w t_j) = (A/2)[cos delta + cos(2 w t_j - delta)], and the second terms sum to the real
part of e^{-i delta} e^{2i w t_s} sum_j e^{4 pi i j/M}. That sum is a geometric series of
ratio e^{4 pi i/M} != 1 (M does not divide 2) over N full turns, so it is 0. Hence
c = A cos delta, and in the same way s = A sin delta: exactly, with no method error. Then
A = hypot(c, s) and delta = atan2(s, c).

R4 (power balance; proved, independent of the formula for A)
------------------------------------------------------------
In steady state, x_p' = -w A sin(w t - delta). Averaged over one period, the drive's power
<F0 cos(w t) x_p'> = (1/2) F0 w A sin delta, and the damping's <b x_p'^2> = (1/2) b w^2 A^2.
The energy of a periodic motion does not change over a period, so the two are equal:
sin delta = b w A / F0.

R5 (what an error in the signal does to the lock-in; proved)
------------------------------------------------------------
Any signal error e_j moves (c, s) by the vector (2/NM) sum e_j (cos w t_j, sin w t_j), of
length at most (2/NM) sum |e_j| <= 2 max |e_j|; A = hypot(c, s) moves by no more (triangle
inequality). From rest the transient is x - x_p = R e^{-gamma t} cos(wd t - phi) (2.3,
``analytical.transient_envelope``), so a window starting at t_s adds at most 2 R e^{-gamma t_s}.
The settle time t_s is the smallest whole number n of drive periods with
2 R e^{-gamma n T} <= eps_s A (plan D7), so the transient moves A by at most eps_s A.

The bounds (plan D10), given the measured e_x = max |x_num - x_exact| over the window
-----------------------------------------------------------------------------------
B1 = 2 e_x + eps_s A + r_A, r_A the rounding allowance (``ROUNDING_FACTOR``).
C1 |A_sim - A| <= B1 (R3, R5). C2 |wrap(delta_sim - delta)| <= arcsin(B1/A): (c, s) is
(A cos delta, A sin delta) moved by at most B1, and a vector of length A moved by B1 < A
turns by at most arcsin(B1/A) (no verdict when B1 >= A). C3 the extraction alone, on the exact
x(t) at the same times: |A_ext - A| <= eps_s A + r_A. C4 |sin delta_sim - b w A_sim/F0| <=
arcsin(B1/A) + b w B1/F0, from R4 and |sin u - sin v| <= |u - v|. C5 the refined peak:
|w_peak - w_r| <= max(u, xatol), u = 2 sqrt(B1/K) an **estimate, not a bound** (2.2's argument,
K the grid's second-difference curvature), so C5 is observed evidence, not a proof.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo, ValidationCheck
from simforge.numerics.sweep import WorkBudget, WorkBudgetExceededError, curvature, refine_maximum
from simforge.physics.oscillator import analytical, model
from simforge.physics.oscillator.analytical import FloatArray, OscillatorInputs
from simforge.physics.oscillator.model import OscillatorComputation
from simforge.physics.projectile.schemas import SolverSettings
from simforge.physics.sweep_checks import aggregate

# Samples per drive period in the lock-in (plan D8). R3 holds for any M >= 3; 64 keeps the
# samples dense against the solver's dense-output interpolant and costs nothing (no solve).
SAMPLES_PER_PERIOD = 64
# Whole drive periods in the lock-in window after the settle time (plan D7).
WINDOW_PERIODS = 2
# Brent's tolerance on w, as a fraction of w0 (plan D9; 2.2's relative-precision argument).
PEAK_XATOL_FACTOR = 1e-7
# Points in each run's resampled series: the 2.3 schema minimum; the sweep discards the series
# and it does not affect the solve.
N_SAMPLES = 10
# Methods allowed (plan D6): an underdamped run is not stiff, and Radau costs ~3x per call.
METHODS = ("DOP853", "RK45")
# r_A = ROUNDING_FACTOR (max(w0, w) t_end + Q + 20) eps max|x_num| (plan D10's allowance, in a
# form that grows with the phase w t_end rather than with M N_W). Per sample: w t_j is rounded
# to a relative eps (a phase error eps w t_end in cos(w t_j) and, through the float t_j not being
# exactly evenly spaced, in x_j as well: ~4 eps w t_end after R5's factor 2), the exact x(t) is
# evaluated to a few eps (Q + w0 t + 1) X (2.3, measured), and the products and pairwise sum add
# ~16 eps. 16 covers these terms with a margin of at least 2. Measured (slice 3, 432 points,
# zeta 0.005-0.9, w/w0 0.05-20, eps_s 1e-12 to 1e-2): the float lock-in of the exact x(t) is
# within 0.0063 r_A of a long-double one at the same times.
ROUNDING_FACTOR = 16.0

TWO_PI = 2.0 * math.pi
_EPS = float(np.finfo(np.float64).eps)


@dataclass(frozen=True, slots=True)
class ResonanceSweepInputs:
    """The sweep's physical inputs and grid, SI (plan D6). Every run starts from rest."""

    mass: float  # m, kg, > 0
    spring_constant: float  # k, N/m, > 0
    damping_coefficient: float  # b, kg/s, > 0 (underdamped: checked in run)
    drive_amplitude: float  # F0, N, > 0
    omega_min: float  # rad/s, 0 < omega_min < omega_max
    omega_max: float  # rad/s, <= 1e4
    n_frequencies: int  # >= 3 (the cap is the schema's, slice 4)
    settle_tolerance: float = 1e-6  # eps_s, in [1e-12, 1e-2]

    def __post_init__(self) -> None:
        for name in ("mass", "spring_constant", "damping_coefficient", "drive_amplitude"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0):
                raise ValueError(f"{name} must be positive and finite (got {value})")
        lo, hi = self.omega_min, self.omega_max
        if not (math.isfinite(lo) and math.isfinite(hi) and 0 < lo < hi <= 1e4):
            raise ValueError(f"need 0 < omega_min < omega_max <= 1e4 rad/s (got {lo}, {hi})")
        if self.n_frequencies < 3:
            raise ValueError(f"n_frequencies must be at least 3 (got {self.n_frequencies})")
        if not 1e-12 <= self.settle_tolerance <= 1e-2:  # also refuses NaN
            raise ValueError(
                f"settle_tolerance must be in [1e-12, 1e-2] (got {self.settle_tolerance})"
            )

    def at(self, w: float) -> OscillatorInputs:
        """The 2.3 inputs of one run from rest at drive frequency w (rad/s)."""
        return OscillatorInputs(
            mass=self.mass,
            spring_constant=self.spring_constant,
            damping_coefficient=self.damping_coefficient,
            drive_amplitude=self.drive_amplitude,
            drive_angular_frequency=w,
        )


# --- Lock-in, settle time and phase conventions (R3, R5, D7, D8) ------------------------------


def lock_in(t: FloatArray, x: FloatArray, omega: float) -> tuple[float, float]:
    """(c, s) = (2/NM) sum x_j (cos w t_j, sin w t_j): (A cos delta, A sin delta) exactly for
    x = A cos(w t - delta) sampled over whole periods (R3)."""
    phase = omega * t
    return 2.0 * float(np.mean(x * np.cos(phase))), 2.0 * float(np.mean(x * np.sin(phase)))


def window_times(omega: float, t_s: float) -> FloatArray:
    """t_j = t_s + j T/M, j = 0..N_W M - 1 (s): N_W whole drive periods from t_s."""
    n = WINDOW_PERIODS * SAMPLES_PER_PERIOD
    times: FloatArray = t_s + np.arange(n, dtype=np.float64) * (TWO_PI / omega / SAMPLES_PER_PERIOD)
    return times


def settle_periods(p: OscillatorInputs, eps_s: float) -> int:
    """The smallest whole n >= 0 with 2 R e^{-gamma n T} <= eps_s A (R5, D7); underdamped,
    driven inputs from rest."""
    steady = analytical.steady_state(p)
    envelope = analytical.transient_envelope(p, 0.0)
    if steady is None or envelope is None:
        raise ValueError("the settle time needs a driven, underdamped oscillator")
    gamma = p.damping_coefficient / (2 * p.mass)
    period = TWO_PI / p.drive_angular_frequency
    radius = float(envelope)
    n_star = math.log(2 * radius / (eps_s * steady.amplitude)) / (gamma * period)
    return max(0, math.ceil(n_star))


def phase_lag(c: float, s: float) -> float:
    """atan2(s, c) shifted into [-pi/2, 3pi/2) (rad): continuous through pi, where a lag near pi
    with s rounded below 0 would otherwise jump to -pi (D8)."""
    angle = math.atan2(s, c)
    return angle + TWO_PI if angle < -math.pi / 2 else angle


def wrap_phase(angle: float) -> float:
    """angle wrapped into (-pi, pi] (rad); exact (IEEE remainder)."""
    r = math.remainder(angle, TWO_PI)
    return r + TWO_PI if r <= -math.pi else r


def phase_error(delta_sim: float, delta: float) -> float:
    """|wrap(delta_sim - delta)|: every phase comparison uses the wrapped difference (D8)."""
    return abs(wrap_phase(delta_sim - delta))


def phase_bound(b1: float, a: float) -> float | None:
    """arcsin(B1/A), C2's bound; None when B1 >= A (the moved vector can point anywhere)."""
    return math.asin(b1 / a) if b1 < a else None


# --- The sweep ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SweepPoint:
    """One run of the 2.3 model at drive frequency w, and its lock-in."""

    angular_frequency: float  # w, rad/s
    amplitude: float  # A_sim, m, numerical
    phase_lag: float  # delta_sim, rad, in [-pi/2, 3pi/2)
    exact_amplitude: float  # A, m (R1)
    exact_phase_lag: float  # delta, rad, in [0, pi] (R1)
    extraction_amplitude: float  # A_ext, m: the lock-in of the exact x(t) at the same times
    settle_time: float  # t_s, s
    trajectory_error: float  # e_x, m (measured)
    rounding_allowance: float  # r_A, m
    amplitude_bound: float  # B1, m
    computation: OscillatorComputation


@dataclass(frozen=True, slots=True)
class ResonancePeak:
    angular_frequency: float  # rad/s, numerical: the refined peak
    amplitude: float  # m, numerical
    amplitude_bound: float  # B1 of the run at the refined peak, m
    uncertainty: float | None  # u, rad/s: an estimate, not a bound; None at an edge
    uncertainty_note: str
    exact_angular_frequency: float | None  # w_r (R2); None when zeta >= 1/sqrt 2
    exact_amplitude: float | None  # A_max (R2)


@dataclass(frozen=True, slots=True)
class ResonanceSweepComputation:
    inputs: ResonanceSweepInputs
    angular_frequencies: list[float]  # rad/s, the grid
    amplitudes: list[float]  # m, numerical
    phase_lags: list[float]  # rad, numerical, in [-pi/2, 3pi/2)
    exact_amplitudes: list[float]  # m (R1)
    exact_phase_lags: list[float]  # rad, in [0, pi] (R1)
    settle_times: list[float]  # s
    amplitude_bounds: list[float]  # B1, m
    points: list[SweepPoint]  # the grid, then every refinement run
    peak: ResonancePeak
    grid_step_over_gamma: float  # (D9): above 1 the grid may flatten or miss the peak
    n_rhs_evaluations: int
    checks: list[ValidationCheck]
    elapsed_ms: float


def _duration(p: OscillatorInputs, eps_s: float) -> tuple[float, float]:
    """(t_s, run duration) in s: n whole periods to settle, then the window (D7)."""
    n = settle_periods(p, eps_s)
    period = TWO_PI / p.drive_angular_frequency
    return n * period, (n + WINDOW_PERIODS) * period


def _refuse_over_cap(inputs: ResonanceSweepInputs, grid: list[float]) -> None:
    """Before any solve: every grid point's cycles within 2.3's MAX_CYCLES (D7)."""
    cycles = [
        (w, analytical.cycles(inputs.at(w), _duration(inputs.at(w), inputs.settle_tolerance)[1]))
        for w in grid
    ]
    worst_w, worst = max(cycles, key=lambda c: c[1])
    if worst > model.MAX_CYCLES:
        d = analytical.derived(inputs.at(worst_w))
        n_over = sum(c > model.MAX_CYCLES for _, c in cycles)
        raise ModelDomainError(
            f"The run at w = {worst_w:.6g} rad/s needs {worst:.4g} cycles (settling to "
            f"eps_s = {inputs.settle_tolerance:g} of A, then {WINDOW_PERIODS} periods), above the "
            f"{model.MAX_CYCLES} cycle limit of one oscillator run; {n_over} of the "
            f"{len(grid)} frequencies are over. With Q = {d.quality_factor:.4g} the transient "
            "decays over about Q/pi cycles per factor e: use more damping, a larger "
            "settle_tolerance, or a narrower or lower range of frequencies."
        )


def _point(
    inputs: ResonanceSweepInputs, w: float, solver: SolverSettings, budget: WorkBudget
) -> SweepPoint:
    p = inputs.at(w)
    eps_s = inputs.settle_tolerance
    t_s, duration = _duration(p, eps_s)
    cycles = analytical.cycles(p, duration)
    if cycles > model.MAX_CYCLES:  # a refinement frequency between two admitted grid points
        raise ModelDomainError(
            f"The refinement run at w = {w:.6g} rad/s needs {cycles:.4g} cycles, above the "
            f"{model.MAX_CYCLES} cycle limit; use a larger settle_tolerance or more damping."
        )
    computation, sol = model.run_with_solution(p, duration, solver, n_samples=N_SAMPLES)
    try:
        budget.charge(sol.n_rhs_evaluations)
    except WorkBudgetExceededError as exc:
        raise ModelDomainError(
            f"The sweep needed more than {budget.limit:,} right-hand-side evaluations "
            f"({exc.total:,} by w = {w:.6g} rad/s); use fewer frequencies, a looser tolerance "
            "or a larger settle_tolerance."
        ) from exc
    t = window_times(w, t_s)
    x_num = sol.sample(t)[0]
    x_exact = analytical.state(p, t)[0]
    c, s = lock_in(t, x_num, w)
    c_ext, s_ext = lock_in(t, x_exact, w)
    steady = computation.steady_state
    assert steady is not None  # driven and damped
    a = steady.amplitude
    e_x = float(np.max(np.abs(x_num - x_exact)))
    quality = computation.derived.quality_factor or 0.0
    phase_span = max(computation.derived.natural_angular_frequency, w) * duration
    r_a = ROUNDING_FACTOR * (phase_span + quality + 20) * _EPS * float(np.max(np.abs(x_num)))
    return SweepPoint(
        angular_frequency=w,
        amplitude=math.hypot(c, s),
        phase_lag=phase_lag(c, s),
        exact_amplitude=a,
        exact_phase_lag=steady.phase_lag,
        extraction_amplitude=math.hypot(c_ext, s_ext),
        settle_time=t_s,
        trajectory_error=e_x,
        rounding_allowance=r_a,
        amplitude_bound=2 * e_x + eps_s * a + r_a,
        computation=computation,
    )


def _uncertainty(
    amplitudes: list[float], i: int, step: float, b1: float
) -> tuple[float | None, str]:
    """u = 2 sqrt(B1/K) in rad/s (D9), or None with the reason."""
    k = curvature(amplitudes, i, step)
    if k is None:
        return None, (
            "No estimate: the best grid point is at an edge of the grid, or the grid curve is "
            "not bent downwards there, so the curvature K, and with it u, is undefined."
        )
    return 2 * math.sqrt(b1 / k), (
        f"Estimate, not a bound: u = 2 sqrt(B1/K), with B1 = {b1:.3g} m the bound on the "
        f"amplitude error at the peak and K = {k:.4g} m s^2/rad^2 from the grid's second "
        "difference (quadratic approximation near the peak)."
    )


# --- Checks (D10) ------------------------------------------------------------------------------


def _graded(
    check_id: str, label: str, value: float, limit: float | None, note: str
) -> ValidationCheck:
    return ValidationCheck(
        id=check_id,
        label=label,
        value=value,
        threshold=limit,
        passed=None if limit is None else value <= limit,
        kind="numerical_diagnostic",
        note=note,
    )


def _point_checks(pt: SweepPoint, inputs: ResonanceSweepInputs) -> list[ValidationCheck]:
    a, b1, w = pt.exact_amplitude, pt.amplitude_bound, pt.angular_frequency
    turn = phase_bound(b1, a)
    drive = inputs.damping_coefficient * w / inputs.drive_amplitude  # b w / F0, 1/m
    vacuous = " No verdict where B1 >= A (the bound says nothing)." if turn is None else ""
    given = "Proved given the measured e_x (R3, R5)."
    return [
        _graded(
            "lock_in_amplitude",
            "Lock-in amplitude vs the exact A(w)",
            abs(pt.amplitude - a),
            b1,
            f"|A_sim - A| in m against B1 = 2 e_x + eps_s A + r_A, e_x = max |x_num - x_exact| "
            f"over the window. {given}",
        ),
        _graded(
            "lock_in_phase",
            "Lock-in phase lag vs the exact delta(w)",
            phase_error(pt.phase_lag, pt.exact_phase_lag),
            turn,
            f"|wrap(delta_sim - delta)| in rad against arcsin(B1/A). {given}{vacuous}",
        ),
        _graded(
            "extraction_amplitude",
            "Lock-in of the exact motion vs A(w)",
            abs(pt.extraction_amplitude - a),
            inputs.settle_tolerance * a + pt.rounding_allowance,
            "|A_ext - A| in m, the lock-in of the exact x(t) at the same times (extraction and "
            "transient only), against eps_s A + r_A. Proved (R3, R5).",
        ),
        _graded(
            "power_balance",
            "Power balance sin delta = b w A / F0",
            abs(math.sin(pt.phase_lag) - drive * pt.amplitude),
            None if turn is None else turn + drive * b1,
            "|sin delta_sim - b w A_sim / F0| (dimensionless) against arcsin(B1/A) + b w B1/F0; "
            f"R4 holds exactly in steady state, without the formula for A. {given}{vacuous}",
        ),
    ]


def _checks(
    points: list[SweepPoint], peak: ResonancePeak, xatol: float, inputs: ResonanceSweepInputs
) -> list[ValidationCheck]:
    by_id: dict[str, list[tuple[float, ValidationCheck]]] = {}
    for pt in points:
        for check in [*_point_checks(pt, inputs), *pt.computation.checks]:
            by_id.setdefault(check.id, []).append((pt.angular_frequency, check))
    checks = [aggregate(entries, " rad/s") for entries in by_id.values()]
    w_r, u = peak.exact_angular_frequency, peak.uncertainty
    offset = 0.0 if w_r is None else abs(peak.angular_frequency - w_r)
    limit = None if w_r is None or u is None else max(u, xatol)
    checks.append(
        ValidationCheck(
            id="peak_frequency",
            label="Refined peak vs the exact w_r",
            value=offset,
            threshold=limit,
            passed=None if limit is None else offset <= limit,
            kind="numerical_diagnostic",
            note="|w_peak - w_r| in rad/s against max(u, xatol): u is an estimate, not a bound, "
            "so this is observed evidence, not a proof. No verdict without an interior peak "
            "(zeta >= 1/sqrt 2: no w_r) or without u (the grid maximum at an edge).",
        )
    )
    return checks


# --- The model run -----------------------------------------------------------------------------


def run(
    inputs: ResonanceSweepInputs, solver: SolverSettings, *, max_rhs_evaluations: int
) -> ResonanceSweepComputation:
    """The resonance curve at ``n_frequencies`` evenly spaced drive frequencies, the refined
    peak and the checks C1-C5 with 2.3's per-run checks aggregated over every run.

    Raises ModelDomainError before any solve for Radau, an input that is not underdamped, or
    a grid point over 2.3's cycle limit; and once the sweep needs more than
    ``max_rhs_evaluations`` right-hand-side evaluations (checked after each run)."""
    start = time.perf_counter()
    if solver.method not in METHODS:
        raise ModelDomainError(
            f"The resonance sweep runs DOP853 or RK45 only (got {solver.method}): an underdamped "
            "run is not stiff, and Radau's cost per evaluation would set the sweep's budget."
        )
    grid: list[float] = np.linspace(
        inputs.omega_min, inputs.omega_max, inputs.n_frequencies
    ).tolist()
    d = analytical.derived(inputs.at(grid[0]))
    if d.regime != "underdamped":
        raise ModelDomainError(
            f"The resonance sweep needs an underdamped oscillator (zeta < 1; got zeta = "
            f"{d.damping_ratio:.4g}, {d.regime.replace('_', ' ')}): the settle time comes from "
            "the decaying oscillation's envelope. Lower the damping coefficient b below "
            "2 sqrt(m k)."
        )
    _refuse_over_cap(inputs, grid)
    budget = WorkBudget(max_rhs_evaluations)
    points = [_point(inputs, w, solver, budget) for w in grid]
    by_w = {pt.angular_frequency: pt for pt in points}

    def amplitude_at(w: float) -> float:
        if w not in by_w:
            pt = _point(inputs, w, solver, budget)
            points.append(pt)
            by_w[w] = pt
        return by_w[w].amplitude

    amplitudes = [pt.amplitude for pt in points]
    w0 = d.natural_angular_frequency
    xatol = PEAK_XATOL_FACTOR * w0
    w_peak, a_peak, i = refine_maximum(amplitude_at, grid, amplitudes, xatol)
    step = (inputs.omega_max - inputs.omega_min) / (inputs.n_frequencies - 1)
    b1_peak = by_w[w_peak].amplitude_bound
    u, note = _uncertainty(amplitudes, i, step, b1_peak)
    steady = analytical.steady_state(inputs.at(grid[0]))
    assert steady is not None
    peak = ResonancePeak(
        angular_frequency=w_peak,
        amplitude=a_peak,
        amplitude_bound=b1_peak,
        uncertainty=u,
        uncertainty_note=note,
        exact_angular_frequency=steady.peak_angular_frequency,
        exact_amplitude=steady.peak_amplitude,
    )
    grid_points = points[: len(grid)]
    return ResonanceSweepComputation(
        inputs=inputs,
        angular_frequencies=grid,
        amplitudes=amplitudes,
        phase_lags=[pt.phase_lag for pt in grid_points],
        exact_amplitudes=[pt.exact_amplitude for pt in grid_points],
        exact_phase_lags=[pt.exact_phase_lag for pt in grid_points],
        settle_times=[pt.settle_time for pt in grid_points],
        amplitude_bounds=[pt.amplitude_bound for pt in grid_points],
        points=points,
        peak=peak,
        grid_step_over_gamma=step / d.damping_rate,
        n_rhs_evaluations=budget.total,
        checks=_checks(points, peak, xatol, inputs),
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )


# --- Identity, units and labels (used by the API, slice 4) -------------------------------------

MODEL_INFO = ModelInfo(
    id="physics.oscillator.resonance_sweep",
    version="1.0.0",
    name="Simulated resonance curve (driven, damped oscillator)",
    description="Steady amplitude and phase lag against drive frequency, each point one run of "
    "the oscillator model from rest, waited out until the transient is below a stated fraction "
    "of the amplitude and read off by a lock-in over whole drive periods; compared with the "
    "exact resonance curve, with the peak refined by a bounded search.",
)

UNITS: dict[str, str] = {
    "mass": "kg",
    "spring_constant": "N/m",
    "damping_coefficient": "kg/s",
    "drive_amplitude": "N",
    "omega_min": "rad/s",
    "omega_max": "rad/s",
    "settle_tolerance": "dimensionless (fraction of the steady amplitude A)",
    "angular_frequency": "rad/s",
    "amplitude": "m",
    "phase_lag": "rad",
    "settle_time": "s",
    "amplitude_bound": "m",
    "peak_uncertainty": "rad/s",
    "grid_step_over_gamma": "dimensionless",
    "n_rhs_evaluations": "count",
}

ASSUMPTIONS: list[Assumption] = [
    *model.ASSUMPTIONS,
    Assumption(
        id="starts_from_rest",
        statement="Every run starts from rest (x0 = v0 = 0) at its own drive frequency, as a "
        "resonance curve is measured: one fresh run per frequency, not a slow frequency ramp.",
    ),
    Assumption(
        id="steady_state_after_settling",
        statement="The amplitude is read after waiting until the transient's proved envelope "
        "is below settle_tolerance x A; what is left of it is counted in the error bound.",
    ),
]
