"""Check thresholds and the run catalogue for the oscillator's numerical tests (2.3, slice 2).

Test-side only. It is shared by ``test_oscillator_numerical.py`` (seam 2) and
``test_oscillator_model.py`` (seam 3), so each measured number lives in one place, and the
model's own constants are tested against these (``test_corner_grid*``).

Threshold form (plan D8, in scaled units: displacement / X, velocity / (w0 X), energy / k X^2,
time * w0):

    value <= FACTOR * (rtol + atol) * (1 + ERROR_GROWTH_PER_CYCLE * cycles) + FLOOR,
    cycles = duration * max(w0, w) / (2 pi)                         (plan D6's cycle count)

THE BUILDER MAY SET ONLY THE NUMERIC VALUES OF THE CONSTANTS IN THE BLOCK MARKED
"BUILDER MAY SET" BELOW. Set each from measurement on the corner grid (the worst value of the
check over the grid, then a stated, justified margin), never tuned until a test passes (plan,
slice 2 Acceptance block), and replace "to be set from measurement" in its comment with the
measurement: the worst value / threshold, its corner, the machine, NumPy and SciPy versions.
The same numbers go into SCIENTIFIC_VALIDATION.md's oscillator section. Nothing else in this
file or in the two test files may change.

Provisional values: D8's 1e4 x (rtol + atol) + 1e-9 for every check, no cycles factor, and
D6's N_max = 1000 cycles. What the test writer measured before the build (a throwaway scaled
solve in the session scratchpad, NOT the product code; one x86_64 machine, NumPy 2.5.4,
SciPy 1.18.1) and the builder should confirm with the real code:
- every grid case below, run for 4 s from v0 = 0 (a close variant of the 3 s grid), stayed at
  or below 8.5e-3 of the provisional thresholds (worst: velocity, overdamped, DOP853);
- the corner at w = 100 w0 from rest has max|v| / (w0 X) = 50 (the velocity scale
  V = w0 X sits far below the motion's speed there), and its energy residual / k X^2 was
  2.1x the provisional threshold for RK45 at (1e-10, 1e-10): the energy factor will need
  measuring there (or the normalisation revisiting with the author: an open question);
- 1000 undamped cycles at (1e-10, 1e-10): displacement error 0.075 (DOP853) and 0.18 (RK45)
  of the provisional threshold, against ~2e-4 for 2.4 cycles: the error grows with cycles;
  run times 1.1 s (DOP853), 5.0 s (RK45) and 78 s (Radau), so N_max needs measuring against
  D6's 2 s with Radau in mind.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from simforge.physics.oscillator import analytical as osc

Method = Literal["RK45", "DOP853", "Radau"]
CheckKind = Literal[
    "displacement_error",
    "velocity_error",
    "energy_balance",
    "free_decay_period",
    "free_decay_ratio",
]

# ======================= BUILDER MAY SET (numeric values only) ============================
# Measured 2026-11-10 (slice 2 builder; one x86_64 VM, Intel Xeon 2.1 GHz, Python 3.12.3,
# NumPy 2.5.4, SciPy 1.18.1) on 1608 runs inside the limits: this corner grid (113), 55 runs
# of 100 cycles, 840 free decays (zeta 0.01 to 0.99, five starts) and 600 seeded random runs
# (zeta 0 to 1e3, w/w0 0 to 100, all methods and pairs). Rule: each FACTOR is the smallest
# 1-2-5 value at least 10x the worst (value - FLOOR) / ((rtol + atol)(1 + cycles)) measured.
# The FLOORs stay at D8's 1e-9: >= 100x the exact solution's own error at every allowed corner
# (slice 1's worst, 5.8e-12 X: Q = 1e4 at resonance at the minimum duration).
# Displacement error: max |x - x_exact| / X over the step nodes.
# Worst needed 4.0 (seeded random run: w = 0.016 w0, b = 0, RK45 at the loosest pair); worst
# value / threshold 0.10 (zeta = 3.1, DOP853, default pair); grid worst 0.066.
DISPLACEMENT_ERROR_FACTOR = 50.0
DISPLACEMENT_ERROR_FLOOR = 1e-9
# Velocity error: max |v - v_exact| / (w0 X) over the step nodes (V = w0 X, author 2026-11-09).
# Worst needed 30 (random run, overdamped zeta = 3.1, DOP853, default pair: the fast start);
# worst value / threshold 0.064 there; grid worst 0.049 (overdamped-free, DOP853, default).
VELOCITY_ERROR_FACTOR = 500.0
VELOCITY_ERROR_FLOOR = 1e-9
# Energy balance: max |KE + PE + W_damp - W_drive - E0| / (k X^2) over the step nodes.
# Worst needed 621 inside the limits (w = 100 w0, RK45, middle pair, 100 cycles) and 1.3e3 at
# 1000 cycles (beyond N_MAX, but this error grew faster than the cycles, so it bounds the
# 500-cycle runs); the grid's drive_at_100_w0 (RK45, default) needed 590 and was 0.994 of
# D8's provisional 1e4 (rtol + atol) + 1e-9, with no cycles factor. The cause is the
# normalisation, not the solver: there max|v| / (w0 X) = 50, so KE reaches ~1250 k X^2 and an
# error relative to the motion's own energy of ~1e-9 is ~1e-6 in units of k X^2. Short runs
# with |v| <= w0 X needed at most ~25, so this factor is ~800x loose for them (open question
# for the author: normalise by the energy in motion). Worst value / threshold 0.067.
ENERGY_BALANCE_FACTOR = 2e4
ENERGY_BALANCE_FLOOR = 1e-9
# Free-decay period: w0 |(t2 - t1) - T_d| for the first two interior maxima (radians).
# Worst needed 76 (zeta = 0.5, x0 = 0.1 m, v0 = -1 m/s, DOP853, default pair), with the
# model's rule that x2 >= 1e-3 X (model.FREE_DECAY_MIN_MAXIMUM: without it a correct solve
# reached 1e9 (rtol + atol) at zeta = 0.9, where x2 ~ 1e-11 X). Worst value / threshold 0.077.
FREE_DECAY_PERIOD_FACTOR = 1e3
FREE_DECAY_PERIOD_FLOOR = 1e-9
# Free-decay ratio: |x2 - e^{-gamma T_d} x1| / X for the first two interior maxima.
# Worst needed 1.8 (zeta = 1.6e-4, RK45, loosest pair); worst value / threshold 0.089.
FREE_DECAY_RATIO_FACTOR = 20.0
FREE_DECAY_RATIO_FLOOR = 1e-9
# Growth of every threshold with the number of cycles (plan Risks: phase error accumulates).
# Measured linear growth: displacement error / (rtol + atol), undamped, default pair, 100 and
# 1000 cycles: 75 and 747 (DOP853), 182 and 1820 (RK45); the energy at w = 100 w0 (RK45, middle
# pair) 6.3e4 at 100 and 1.3e6 at 1000 cycles. Without growth (0) the factors would have to be
# 5e3 (displacement) and 2e6 (energy) for a 10x margin inside the limits, making short runs'
# checks hundreds of times loose and the energy check uninformative (threshold > 1) at the
# middle pair. 1 = proportional to the run's length in cycles, never below one cycle's worth.
ERROR_GROWTH_PER_CYCLE = 1.0
# N_max: the most cycles, duration * max(w0, w) / 2 pi, a run may have (plan D6).
# Timed (model.run, n_samples 400; this VM's times vary by up to ~1.5x): at the default
# settings (DOP853, rtol = atol = 1e-10) 1000 cycles took 1.7 to 2.5 s (worst: w = 100 w0) and
# 500 cycles 0.8 to 1.4 s (best of 3, n_samples 400 or 5000), so 500 is the largest round
# value within D6's 2 s with headroom. No single cycle limit bounds the other settings: at 500
# cycles (one run each) DOP853 at the tightest pair took 2.4 to 3.4 s, RK45 (default) 2.4 to
# 4.5 s, Radau (middle) 4.9 to 8.2 s and Radau (default) 36 to 78 s, above the 30 s proxy
# limit (an open decision for slice 3).
N_MAX = 500
# ==================== END OF BUILDER MAY SET =============================================

FACTORS: dict[CheckKind, tuple[float, float]] = {
    "displacement_error": (DISPLACEMENT_ERROR_FACTOR, DISPLACEMENT_ERROR_FLOOR),
    "velocity_error": (VELOCITY_ERROR_FACTOR, VELOCITY_ERROR_FLOOR),
    "energy_balance": (ENERGY_BALANCE_FACTOR, ENERGY_BALANCE_FLOOR),
    "free_decay_period": (FREE_DECAY_PERIOD_FACTOR, FREE_DECAY_PERIOD_FLOOR),
    "free_decay_ratio": (FREE_DECAY_RATIO_FACTOR, FREE_DECAY_RATIO_FLOOR),
}

METHODS: tuple[Method, ...] = ("RK45", "DOP853", "Radau")
# (rtol, atol): the tightest allowed, the default, a middle pair and the loosest allowed
# (slice 2 Acceptance block, check 1; SolverSettings' bounds).
TIGHTEST = (1e-13, 1e-14)
DEFAULT = (1e-10, 1e-10)
MIDDLE = (1e-6, 1e-8)
LOOSEST = (1e-3, 1e-1)
TOLERANCE_PAIRS: tuple[tuple[float, float], ...] = (TIGHTEST, DEFAULT, MIDDLE, LOOSEST)


def cycles(p: osc.OscillatorInputs, duration: float) -> float:
    """duration * max(w0, w) / (2 pi): the run's length in cycles (plan D6), dimensionless."""
    w0 = math.sqrt(p.spring_constant / p.mass)
    return duration * max(w0, p.drive_angular_frequency) / (2 * math.pi)


def threshold(
    kind: CheckKind, rtol: float, atol: float, p: osc.OscillatorInputs, duration: float
) -> float:
    """The test's threshold for one check (module docstring), in that check's scaled units."""
    factor, floor = FACTORS[kind]
    return factor * (rtol + atol) * (1.0 + ERROR_GROWTH_PER_CYCLE * cycles(p, duration)) + floor


# --- The run catalogue ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Run:
    """One run's physical inputs (SI) and duration (s)."""

    inputs: osc.OscillatorInputs
    duration: float


def _inputs(b: float, f0: float, w: float, x0: float, v0: float) -> osc.OscillatorInputs:
    # m = 1 kg, k = 25 N/m: w0 = 5 rad/s exactly, T0 = 2 pi / 5 = 1.257 s (plan D2's defaults).
    return osc.OscillatorInputs(
        mass=1.0,
        spring_constant=25.0,
        damping_coefficient=b,
        drive_amplitude=f0,
        drive_angular_frequency=w,
        initial_displacement=x0,
        initial_velocity=v0,
    )


# One damping coefficient per Regime value (decided exactly by analytical.derived, and checked
# in the tests): b = 0; b = 0.5 kg/s (zeta = 0.05, Q = 10, the Damped preset); b = 10 kg/s
# (b^2 = 4mk exactly in floats); b = 40 kg/s (zeta = 4).
REGIME_DAMPING: dict[osc.Regime, float] = {
    "undamped": 0.0,
    "underdamped": 0.5,
    "critically_damped": 10.0,
    "overdamped": 40.0,
}
# 3 s = 2.4 natural periods: two interior maxima for the free underdamped run (at T_d and
# 2 T_d = 2.52 s), and the tightest Radau solve stays near 1 s (measured in scratch: 1.5 s for
# 4 s). max(w0, w, gamma) T >= 15, above the model's minimum of 1 (MIN_DURATION_RATE_PRODUCT).
GRID_DURATION = 3.0


def regime_run(regime: osc.Regime, driven: bool) -> Run:
    """The grid's run for one regime: free from (0.1 m, 0), or driven by 1 N at 3 rad/s
    (0.6 w0, off resonance) from (0.1 m, -0.2 m/s), so x0, v0 and the drive all matter."""
    b = REGIME_DAMPING[regime]
    if driven:
        return Run(_inputs(b, 1.0, 3.0, 0.1, -0.2), GRID_DURATION)
    return Run(_inputs(b, 0.0, 0.0, 0.1, 0.0), GRID_DURATION)


REGIMES: tuple[osc.Regime, ...] = tuple(REGIME_DAMPING)

# The Risks corners (plan, Risks and slice 2 check 1), each with the (method, pair) it runs at.
# Tractability (plan: "keep the Radau and N_max corners tractable"): Radau at w = 100 w0 took
# 6.7 s at the default pair in scratch, so it runs at the middle pair there; the N_max corners
# run DOP853 at the default pair only (RK45 took 5 s and Radau 78 s for 1000 cycles).
N_MAX_DURATION = N_MAX * 2 * math.pi / 5.0  # N_MAX natural cycles at w0 = 5 rad/s
RISK_RUNS: dict[str, Run] = {
    # w = w0/100: the drive is quasi-static, x_p ~ F0/k.
    "drive_far_below_w0": Run(_inputs(0.5, 1.0, 0.05, 0.1, 0.0), 20.0),
    # w = 100 w0 (D6's limit), from rest: the motion is the small forced jitter plus its
    # transient; max|v| / (w0 X) is ~50 here (scratch measurement).
    "drive_at_100_w0": Run(_inputs(0.5, 1.0, 500.0, 0.0, 0.0), 0.2),
    # Tiny x0 with v0: X = sqrt(x0^2 + (v0/w0)^2) is set by v0.
    "tiny_x0_with_v0": Run(_inputs(0.5, 0.0, 0.0, 1e-9, 1.0), GRID_DURATION),
    # Q = sqrt(mk)/b = 5 / 5e-4 = 1e4 (the largest allowed; 5e-4 rounds up, so Q < 1e4 in exact
    # arithmetic and analytical.OscillatorInputs accepts it), driven at w = w0 from rest.
    "q_1e4_at_resonance": Run(_inputs(5e-4, 1.0, 5.0, 0.0, 0.0), 20.0),
    # b = 0 driven exactly at w0: linear growth t sin(w0 t) / (2 w0) (OR3).
    "undamped_at_resonance": Run(_inputs(0.0, 1.0, 5.0, 0.0, 0.0), 20.0),
    # N_MAX cycles: undamped and free (phase error accumulates and never decays) ...
    "n_max_cycles_undamped": Run(_inputs(0.0, 0.0, 0.0, 0.1, 0.0), N_MAX_DURATION),
    # ... and the Damped preset driven at resonance (steady state for most of the run).
    "n_max_cycles_driven": Run(_inputs(0.5, 1.0, 5.0, 0.1, 0.0), N_MAX_DURATION),
}
RISK_SETTINGS: dict[str, tuple[tuple[Method, tuple[float, float]], ...]] = {
    "drive_far_below_w0": (("RK45", DEFAULT), ("DOP853", DEFAULT), ("Radau", DEFAULT)),
    "drive_at_100_w0": (("RK45", DEFAULT), ("DOP853", DEFAULT), ("Radau", MIDDLE)),
    "tiny_x0_with_v0": (("RK45", DEFAULT), ("DOP853", DEFAULT), ("Radau", DEFAULT)),
    "q_1e4_at_resonance": (("RK45", DEFAULT), ("DOP853", DEFAULT), ("Radau", DEFAULT)),
    "undamped_at_resonance": (("RK45", DEFAULT), ("DOP853", DEFAULT), ("Radau", DEFAULT)),
    "n_max_cycles_undamped": (("DOP853", DEFAULT),),
    "n_max_cycles_driven": (("DOP853", DEFAULT),),
}
