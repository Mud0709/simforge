"""A free run (F0 = 0) does not depend on the drive frequency (review 2026-11-10, item 4).

With no drive, ``drive_angular_frequency`` multiplies a force of exactly 0, so the motion is
the same for every value of it. The run's limits and thresholds must then not depend on it
either: before this fix the cycle count ``duration * max(w0, w) / 2 pi`` used w even when
F0 = 0, so an inert number could refuse a run (above N_max cycles), loosen every threshold
(they grow with the cycles) and let a too-short run through.

References: the equation of motion itself (F0 cos(w t) = 0 when F0 = 0) and hand-worked
cycle counts for m = 1 kg, k = 25 N/m, so w0 = 5 rad/s and T0 = 2 pi / 5 s exactly.
"""

from __future__ import annotations

import itertools
import math

import pytest
from pydantic import ValidationError

from simforge.physics.oscillator import analytical as osc
from simforge.physics.oscillator import model
from simforge.physics.oscillator.schemas import OscillatorParameters
from simforge.physics.projectile.schemas import SolverSettings
from tests.approx import rel_approx
from tests.physics import oscillator_thresholds as thresholds

EPS = 2.220446049250313e-16
T0 = 2 * math.pi / 5.0  # one natural period for m = 1, k = 25


def free(w: float, b: float = 0.5) -> osc.OscillatorInputs:
    return osc.OscillatorInputs(
        mass=1.0,
        spring_constant=25.0,
        damping_coefficient=b,
        drive_amplitude=0.0,
        drive_angular_frequency=w,
        initial_displacement=0.1,
        initial_velocity=0.0,
    )


def test_effective_drive_frequency_is_zero_without_a_drive() -> None:
    assert osc.effective_drive_frequency(free(500.0)) == 0.0
    driven = osc.OscillatorInputs(
        mass=1.0, spring_constant=25.0, drive_amplitude=2.0, drive_angular_frequency=7.0
    )
    assert osc.effective_drive_frequency(driven) == 7.0


def test_free_run_is_identical_for_every_drive_frequency() -> None:
    """Same numbers, same cycle count (3 natural periods = 3 cycles), same thresholds."""
    solver = SolverSettings(method="DOP853", rtol=1e-10, atol=1e-10)
    a = model.run(free(0.0), 3 * T0, solver)
    b = model.run(free(500.0), 3 * T0, solver)  # w = 100 w0, inert
    assert a.diagnostics.cycles == rel_approx(3.0, 2 * EPS)
    assert b.diagnostics.cycles == a.diagnostics.cycles
    assert b.series.x == a.series.x
    assert [(c.id, c.value, c.threshold, c.passed) for c in b.checks if c.id != "cost"] == [
        (c.id, c.value, c.threshold, c.passed) for c in a.checks if c.id != "cost"
    ]


def test_threshold_helper_counts_natural_cycles_for_a_free_run() -> None:
    assert thresholds.cycles(free(500.0), 3 * T0) == rel_approx(3.0, 2 * EPS)


def test_rate_duration_product_ignores_an_inert_drive_frequency() -> None:
    # gamma = 0.25 1/s, w0 = 5 rad/s: max(w0, gamma) T = 5 x 0.1 = 0.5, whatever w is.
    assert osc.rate_duration_product(free(500.0), 0.1) == rel_approx(0.5, EPS)


def params(**changes: float) -> dict[str, float]:
    base = {
        "mass": 1.0,
        "spring_constant": 25.0,
        "damping_coefficient": 0.5,
        "drive_amplitude": 0.0,
        "drive_angular_frequency": 500.0,
        "initial_displacement": 0.1,
        "initial_velocity": 0.0,
        "duration": 10 * T0,
    }
    return {**base, **changes}


def test_free_run_is_not_refused_for_cycles_of_a_drive_that_is_off() -> None:
    """10 natural periods = 10 cycles. Counted with w = 100 w0 it was 1000 > N_max = 500."""
    OscillatorParameters(**params())
    with pytest.raises(ValidationError, match="cycles"):  # the same run, driven: 1000 cycles
        OscillatorParameters(**params(drive_amplitude=1.0))


def test_free_run_accepts_any_drive_frequency_but_a_driven_one_keeps_the_ratio_rule() -> None:
    OscillatorParameters(**params(drive_angular_frequency=5000.0, duration=T0))  # 1000 w0
    with pytest.raises(ValidationError, match="drive frequency"):
        OscillatorParameters(
            **params(drive_angular_frequency=5000.0, duration=T0 / 100, drive_amplitude=1.0)
        )


def test_too_short_free_run_is_refused_whatever_the_drive_frequency() -> None:
    """max(w0, gamma) T = 5 x 0.1 = 0.5 < 1. Counted with w = 500 rad/s it was 50: accepted."""
    with pytest.raises(ValidationError, match="too short"):
        OscillatorParameters(**params(duration=0.1))


# --- Review 2026-11-10, item 5: the resonance curve must contain its peak ---------------------


@pytest.mark.parametrize("ratio", [0.5, 1.0, 3.0, 100.0])
@pytest.mark.parametrize("quality", [5.0, 100.0, 1e4])
def test_resonance_curve_resolves_its_peak(quality: float, ratio: float) -> None:
    """The amplitude peak is A_max = f / (2 gamma wd) at w_r = sqrt(w0^2 - 2 gamma^2) (OR5,
    written out here), and its width is about 2 gamma = w0 / Q. An evenly spaced grid of 241
    points up to max(3 w0, 1.2 w) has a spacing of at least w0 / 80, so for Q = 1e4 (width
    w0 / 1e4) or a drive at 100 w0 (spacing w0 / 2) it stepped over the peak. The curve must
    contain w_r itself and points on both sides within one half-width gamma."""
    w0, f0 = 5.0, 2.0
    b = w0 / quality  # m = 1: Q = w0 / (2 gamma) = w0 / b
    p = osc.OscillatorInputs(
        mass=1.0,
        spring_constant=25.0,
        damping_coefficient=b,
        drive_amplitude=f0,
        drive_angular_frequency=ratio * w0,
    )
    gamma = b / 2
    w_r = math.sqrt(w0**2 - 2 * gamma**2)
    a_max = f0 / (2 * gamma * math.sqrt(w0**2 - gamma**2))
    solver = SolverSettings(method="DOP853", rtol=1e-8, atol=1e-8)
    curve = model.run(p, 2 * T0 / max(1.0, ratio), solver).resonance
    assert curve is not None
    omega, amplitude = curve.angular_frequency, curve.amplitude
    assert all(hi > lo for lo, hi in itertools.pairwise(omega))  # strictly increasing
    assert omega[0] == 0.0
    assert omega[-1] == rel_approx(max(3 * w0, 1.2 * ratio * w0), 2 * EPS)  # plan D9
    # The peak value: w_r is on the grid to rounding; A is flat there (dA/dw = 0), so 1e-12.
    assert max(amplitude) == rel_approx(a_max, 1e-12)
    peak = amplitude.index(max(amplitude))
    assert omega[peak] == rel_approx(w_r, 4 * EPS)
    assert 0 < w_r - omega[peak - 1] <= gamma
    assert 0 < omega[peak + 1] - w_r <= gamma


# --- Review 2026-11-10, item 6: say when the free-decay checks are left out -------------------


def test_free_decay_checks_absent_near_critical_damping_are_explained() -> None:
    """zeta = 0.9 (b = 9): maxima shrink by e^{-gamma T_d} = e^{-2 pi 0.9/sqrt(0.19)} = 2.3e-6
    per period, so the second maximum is far below 1e-3 X and the checks are not made. The
    run must say so in an informational row instead of just showing fewer checks."""
    solver = SolverSettings(method="DOP853", rtol=1e-10, atol=1e-10)
    comp = model.run(free(0.0, b=9.0), 6 * T0, solver)
    by_id = {c.id: c for c in comp.checks}
    assert "free_decay_period" not in by_id
    assert "free_decay_ratio" not in by_id
    row = by_id["free_decay_not_checked"]
    assert (row.kind, row.threshold, row.passed) == ("informational", None, None)
    assert 0.0 <= row.value < model.FREE_DECAY_MIN_MAXIMUM
    assert "not checked" in row.note


def test_free_decay_checks_present_have_no_such_row() -> None:
    solver = SolverSettings(method="DOP853", rtol=1e-10, atol=1e-10)
    comp = model.run(free(0.0, b=0.5), 6 * T0, solver)
    ids = {c.id for c in comp.checks}
    assert {"free_decay_period", "free_decay_ratio"} <= ids
    assert "free_decay_not_checked" not in ids


# --- Review 2026-11-10, item 3: free-decay thresholds and the length of the run ---------------


def test_free_decay_thresholds_do_not_grow_with_the_length_of_the_run() -> None:
    """The two maxima lie within 2 T_d, so a run 40 times longer has the same free-decay
    thresholds: FACTOR (rtol + atol)(1 + 2 w0/wd) + FLOOR, with gamma = 0.25 /s and
    wd = sqrt(25 - 0.0625) rad/s written out here."""
    solver = SolverSettings(method="DOP853", rtol=1e-10, atol=1e-10)
    short = {c.id: c for c in model.run(free(0.0), 4 * T0, solver).checks}
    long = {c.id: c for c in model.run(free(0.0), 160 * T0, solver).checks}
    growth = 1.0 + 2.0 * 5.0 / math.sqrt(25.0 - 0.0625)
    for check_id, factor in (("free_decay_period", 5e3), ("free_decay_ratio", 50.0)):
        expected = factor * 2e-10 * growth + 1e-9
        assert short[check_id].threshold == rel_approx(expected, 8 * EPS)
        assert long[check_id].threshold == short[check_id].threshold
        assert short[check_id].passed is True
        assert long[check_id].passed is True
    # The whole-run checks still grow with the run: 50 x 2e-10 x (1 + cycles) + 5e-9 is
    # 5.5e-8 at 4 cycles and 1.615e-6 at 160, a ratio of 29.
    assert long["displacement_error"].threshold > 25 * short["displacement_error"].threshold
