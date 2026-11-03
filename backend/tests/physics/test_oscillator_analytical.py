"""Tests for the exact solution of the linear oscillator (roadmap 2.3, slice 1, seam 1).

Model: m x'' + b x' + k x = F0 cos(w t), x(0) = x0, x'(0) = v0 (SI). Every expected value
comes from an *independent* source, never from the module under test:

- a 90-digit ``decimal`` evaluation of the textbook branch formulas, one per regime
  (``oscillator_reference.py``, written separately, sharing no code with the module);
- closed forms written out in this file from the definitions (w0 = sqrt(k/m), ...);
- exact identities of the true solution (the ODE itself, the free decay's shift
  x(t + T_d) = e^{-g T_d} x(t), the power and amplitude resonance formulas, linearity in F0,
  smoothness across the regime boundaries);
- one test-local SciPy integration with its own right-hand side.

Tolerances are stated with their reason. The scale X (amendment G2 of the 2.3 plan) is
recomputed here from its definition, and the accuracy target is 1e-13 of X.
"""

from __future__ import annotations

import math
import sys
from decimal import Decimal, localcontext
from fractions import Fraction

import numpy as np
import pytest

from simforge.physics.oscillator import analytical as osc
from tests.approx import rel_approx
from tests.physics.oscillator_reference import (
    Case,
    max_error,
    reference_amplitude_phase,
    reference_states,
    regime,
)

EPS = float(np.finfo(float).eps)  # 2.2e-16


def _inputs(case: Case) -> osc.OscillatorInputs:
    return osc.OscillatorInputs(
        mass=case.mass,
        spring_constant=case.spring_constant,
        damping_coefficient=case.damping_coefficient,
        drive_amplitude=case.drive_amplitude,
        drive_angular_frequency=case.drive_angular_frequency,
        initial_displacement=case.initial_displacement,
        initial_velocity=case.initial_velocity,
    )


# --- Derived quantities -----------------------------------------------------------------

DAMPED_PRESET = Case(1.0, 25.0, 0.5, 0.0, 5.0, 0.1, 0.0)  # plan D2 defaults


def test_damped_preset_derived_quantities_match_their_definitions() -> None:
    # w0 = sqrt(k/m) = 5, g = b/2m = 0.25, zeta = b/(2 sqrt(mk)) = 0.05, Q = sqrt(mk)/b = 10,
    # wd = sqrt(w0^2 - g^2) = sqrt(24.9375). Each is one or two roundings of the exact value,
    # so 2 eps relative is the honest bound.
    d = osc.derived(_inputs(DAMPED_PRESET))
    assert d.natural_angular_frequency == 5.0
    assert d.damping_rate == 0.25
    assert d.damping_ratio == rel_approx(0.05, 2 * EPS)
    assert d.quality_factor == rel_approx(10.0, 2 * EPS)
    assert d.regime == "underdamped"
    assert d.damped_angular_frequency == rel_approx(math.sqrt(24.9375), 2 * EPS)
    assert d.overdamped_rate is None
    assert d.damped_period == rel_approx(2 * math.pi / math.sqrt(24.9375), 4 * EPS)


def test_undamped_has_no_quality_factor_and_oscillates_at_w0() -> None:
    d = osc.derived(_inputs(Case(2.0, 3.0)))
    assert d.regime == "undamped"
    assert d.quality_factor is None
    assert d.damping_rate == 0.0
    assert d.damping_ratio == 0.0
    w0 = math.sqrt(1.5)
    assert d.natural_angular_frequency == rel_approx(w0, EPS)
    assert d.damped_angular_frequency == rel_approx(w0, EPS)
    assert d.damped_period == rel_approx(2 * math.pi / w0, 2 * EPS)


def test_critical_damping_is_exactly_b_squared_equals_4mk() -> None:
    # b = 10, m = 1, k = 25: b^2 = 4mk exactly. One ulp either side changes the label, which
    # only an exact comparison can see (b^2 - 4mk cancels completely in floats).
    critical = osc.derived(_inputs(Case(1.0, 25.0, 10.0)))
    assert critical.regime == "critically_damped"
    assert critical.damped_angular_frequency is None
    assert critical.overdamped_rate is None
    assert critical.damped_period is None
    assert osc.derived(_inputs(Case(1.0, 25.0, math.nextafter(10.0, 0.0)))).regime == (
        "underdamped"
    )
    assert osc.derived(_inputs(Case(1.0, 25.0, math.nextafter(10.0, 20.0)))).regime == (
        "overdamped"
    )


def test_damped_frequency_near_critical_has_no_cancellation() -> None:
    # One ulp below critical: w0^2 - g^2 = (100 - b^2)/4 ~ 9e-15, where the float
    # difference 25 - g*g keeps no correct digit. The exact value (decimal, from the exact
    # float b) gives wd ~ 9.4e-8; the module must match it to a few roundings.
    b = math.nextafter(10.0, 0.0)
    b_over = math.nextafter(10.0, 20.0)
    with localcontext(prec=70):  # the default 28 digits would lose ~15 to the cancellation
        q = (Decimal(25) - (Decimal(b) / 2) ** 2).sqrt()
        beta = ((Decimal(b_over) / 2) ** 2 - Decimal(25)).sqrt()
    d = osc.derived(_inputs(Case(1.0, 25.0, b)))
    assert d.damped_angular_frequency == rel_approx(float(q), 2 * EPS)
    d_over = osc.derived(_inputs(Case(1.0, 25.0, b_over)))
    assert d_over.regime == "overdamped"
    assert d_over.overdamped_rate == rel_approx(float(beta), 2 * EPS)


@pytest.mark.parametrize("ulps", [-2, -1, 0, 1, 2])
def test_near_critical_with_a_rounded_w0_is_classified_and_measured_exactly(ulps: int) -> None:
    # m = 0.3, k = 7: the critical b = 2 sqrt(2.1) is irrational, so the float nearest to it and
    # its neighbours are all slightly under- or overdamped, by |b^2 - 4mk| ~ eps b^2. The float
    # (w0 - g)(w0 + g) has an error of the same size (w0 and g are rounded), so it can get the
    # sign and every digit wrong; the exact q, rounded once, must match the 70-digit value.
    b = math.sqrt(8.4)
    for _ in range(abs(ulps)):
        b = math.nextafter(b, math.copysign(math.inf, ulps))
    case = Case(0.3, 7.0, b)
    d = osc.derived(_inputs(case))
    assert d.regime == regime(case)
    with localcontext(prec=70):
        m = Decimal(case.mass)  # the exact value of the float 0.3, on purpose
        q = Decimal(7) / m - (Decimal(b) / (2 * m)) ** 2
        rate = float(abs(q).sqrt())
    if d.regime == "underdamped":
        assert d.damped_angular_frequency == rel_approx(rate, 2 * EPS)
    else:
        assert d.regime == "overdamped"
        assert d.overdamped_rate == rel_approx(rate, 2 * EPS)


@pytest.mark.parametrize(
    ("mass", "spring", "critical_b"),
    [(2.0, 2.0, 4.0), (1.0, 25.0, 10.0), (0.3, 7.0, math.sqrt(8.4))],
)
@pytest.mark.parametrize("ulps", [-2, -1, 0, 1, 2])
def test_zeta_and_q_agree_with_the_exact_regime_label(
    mass: float, spring: float, critical_b: float, ulps: int
) -> None:
    # zeta < 1 exactly when underdamped, = 1 when critical, > 1 when overdamped, and Q > 1/2,
    # = 1/2, < 1/2 likewise, even within an ulp of critical (m = k = 2, b = 4 once gave
    # zeta = 0.9999999999999998 labelled critical). Values within 2 eps of the 70-digit ones.
    b = critical_b
    for _ in range(abs(ulps)):
        b = math.nextafter(b, math.copysign(math.inf, ulps))
    case = Case(mass, spring, b)
    d = osc.derived(_inputs(case))
    assert d.regime == regime(case)
    assert d.quality_factor is not None
    sign = {"underdamped": -1, "critically_damped": 0, "overdamped": 1}[d.regime]
    assert (d.damping_ratio > 1) - (d.damping_ratio < 1) == sign
    assert (d.quality_factor < 0.5) - (d.quality_factor > 0.5) == sign
    with localcontext(prec=70):
        zeta = Decimal(b) / (2 * (Decimal(mass) * Decimal(spring)).sqrt())
    assert d.damping_ratio == rel_approx(float(zeta), 2 * EPS)
    assert d.quality_factor == rel_approx(float(1 / (2 * zeta)), 2 * EPS)


@pytest.mark.parametrize(
    "values",
    [
        # b = 5e-324 once raised ZeroDivisionError in steady_state, state and scale (Q ~ 1e324)
        {
            "mass": 2.0,
            "spring_constant": 2.0,
            "damping_coefficient": 5e-324,
            "drive_amplitude": 1.0,
            "drive_angular_frequency": 1.0,
        },
        # k/m = 1e-310 is subnormal: w0^2 cannot be held to full precision
        {
            "mass": 1e150,
            "spring_constant": 1e-160,
            "damping_coefficient": math.nextafter(2 * math.sqrt(1e150 * 1e-160), 0.0),
        },
    ],
)
def test_inputs_outside_the_representable_domain_are_refused(values: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="must"):
        osc.OscillatorInputs(**values)


@pytest.mark.parametrize(("mass", "spring"), [(1e150, 1e-160), (1e-300, 1e300)])
def test_w0_squared_must_be_a_normal_float(mass: float, spring: float) -> None:
    # k/m = 1e-310 (subnormal: w0^2 loses precision) or 1e600 (overflows), even undamped.
    with pytest.raises(ValueError, match="normal float"):
        osc.OscillatorInputs(mass=mass, spring_constant=spring)


def test_damping_within_rounding_of_critical_at_a_tiny_w0_is_refused() -> None:
    # k/m = 1e-300 is a normal float, but one ulp off critical damping q = w0^2 - gamma^2 is
    # ~1e-316, which underflows: wd and beta (and T_d) cannot be represented.
    b = math.nextafter(2 * math.sqrt(1e-300), 0.0)
    q = Fraction(1e-300) - (Fraction(b) / 2) ** 2
    assert q != 0
    assert abs(float(q)) < sys.float_info.min
    with pytest.raises(ValueError, match="critical"):
        osc.OscillatorInputs(mass=1.0, spring_constant=1e-300, damping_coefficient=b)


def test_heavily_overdamped_rate() -> None:
    # beta = sqrt(g^2 - w0^2) with g = 20, w0 = 5: sqrt(375).
    d = osc.derived(_inputs(Case(1.0, 25.0, 40.0)))
    assert d.regime == "overdamped"
    assert d.damping_ratio == rel_approx(4.0, 2 * EPS)
    assert d.overdamped_rate == rel_approx(math.sqrt(375.0), 2 * EPS)
    assert d.damped_angular_frequency is None
    assert d.damped_period is None


@pytest.mark.parametrize(
    "field",
    [
        "mass",
        "spring_constant",
        "damping_coefficient",
        "drive_amplitude",
        "drive_angular_frequency",
        "initial_displacement",
        "initial_velocity",
    ],
)
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_inputs_are_rejected(field: str, bad: float) -> None:
    values = {"mass": 1.0, "spring_constant": 25.0}
    values[field] = bad
    with pytest.raises(ValueError, match=field):
        osc.OscillatorInputs(**values)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("mass", 0.0),
        ("mass", -1.0),
        ("spring_constant", 0.0),
        ("spring_constant", -2.0),
        ("damping_coefficient", -0.1),
        ("drive_amplitude", -1.0),
        ("drive_angular_frequency", -1.0),
    ],
)
def test_out_of_domain_inputs_are_rejected(field: str, bad: float) -> None:
    values = {"mass": 1.0, "spring_constant": 25.0}
    values[field] = bad
    with pytest.raises(ValueError, match=field):
        osc.OscillatorInputs(**values)


# --- OR1: steady state; OR5: amplitude peak --------------------------------------------


def test_no_steady_state_without_drive_or_without_damping() -> None:
    assert osc.steady_state(_inputs(Case(1.0, 25.0, 0.5))) is None  # F0 = 0
    assert osc.steady_state(_inputs(Case(1.0, 25.0, 0.0, 1.0, 3.0))) is None  # b = 0


STEADY_CASES = [
    Case(1.0, 25.0, 0.5, 1.0, 2.0),  # below resonance
    Case(1.0, 25.0, 0.5, 1.0, 5.0),  # at w0 exactly (k/m a perfect square)
    Case(1.0, 25.0, 0.5, 1.0, 12.0),  # above
    Case(1.0, 25.0, 0.5, 1.0, 0.0),  # static force: A = F0/k, delta = 0
    Case(0.3, 7.0, 0.04, 2.5, math.sqrt(7.0 / 0.3)),  # w = the float w0 (not exact)
    Case(1.0, 25.0, 5e-4, 1.0, 5.0 * (1 + 1e-5)),  # Q = 1e4 (the limit), 1/5 linewidth off
    Case(1.0, 25.0, 5e-4, 1.0, 5.0),  # Q = 1e4 at w0
    # Q = 1e4 with a rounded w0 = sqrt(70/3): driving at the float w0 is ~eps off the true w0,
    # which shifts delta by ~2 eps Q = 4e-12 rad; only an exact w0^2 - w^2 sees it.
    Case(0.3, 7.0, math.sqrt(2.1) / 1e4, 1.0, math.sqrt(7.0 / 0.3)),
    Case(0.3, 7.0, math.sqrt(2.1) / 1e4, 1.0, math.sqrt(7.0 / 0.3) * (1 + 5e-5)),  # half-power
    Case(2.0, 3.0, 40.0, 2.0, 1.7),  # overdamped, driven
    Case(1e-6, 1e-2, 1e-5, 1e-6, 80.0),  # small scales
    Case(1e6, 1e9, 1e6, 1e6, 30.0),  # large scales
]


@pytest.mark.parametrize("case", STEADY_CASES)
def test_steady_state_amplitude_and_phase_match_90_digit_reference(case: Case) -> None:
    # A = f / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2) and delta = atan2(2 gamma w, w0^2 - w^2).
    # w0^2 - w^2 is exact before one rounding, 2 gamma w and f two roundings each, hypot one
    # ulp: about 4 eps relative for A. delta from atan2 of two arguments that are accurate to
    # 2 eps relative: within 4 eps of pi, absolutely. In particular the phase lag has no
    # error of order eps Q at Q = 1e4 (4e-12 rad if w0^2 - w^2 were rounded; 4 eps pi = 3e-15).
    a_ref, delta_ref = reference_amplitude_phase(case)
    ss = osc.steady_state(_inputs(case))
    assert ss is not None
    assert ss.amplitude == rel_approx(float(a_ref), 4 * EPS)
    assert abs(Decimal(ss.phase_lag) - delta_ref) <= Decimal(4 * EPS * math.pi)
    assert 0.0 <= ss.phase_lag <= math.pi


def test_static_force_and_resonance_phase_values() -> None:
    static = osc.steady_state(_inputs(Case(1.0, 25.0, 0.5, 2.0, 0.0)))
    assert static is not None
    assert static.amplitude == rel_approx(2.0 / 25.0, 2 * EPS)  # F0/k
    assert static.phase_lag == 0.0
    at_w0 = osc.steady_state(_inputs(Case(1.0, 25.0, 0.5, 2.0, 5.0)))
    assert at_w0 is not None
    assert at_w0.phase_lag == rel_approx(math.pi / 2, EPS)  # exactly pi/2 at w = w0
    assert at_w0.amplitude == rel_approx(2.0 / (0.5 * 5.0), 2 * EPS)  # F0/(b w0)


def test_amplitude_peak_matches_its_formula_when_zeta_below_one_over_root_two() -> None:
    # w_r = sqrt(w0^2 - 2 gamma^2), A_max = f / (2 gamma wd) (OR5), from 70-digit decimal.
    case = Case(1.0, 25.0, 3.0, 2.0, 1.0)  # gamma = 1.5, zeta = 0.3
    with localcontext(prec=70):
        g = Decimal(3) / 2
        w_r = (Decimal(25) - 2 * g * g).sqrt()
        a_max = Decimal(2) / (2 * g * (Decimal(25) - g * g).sqrt())
    ss = osc.steady_state(_inputs(case))
    assert ss is not None
    assert ss.peak_angular_frequency == rel_approx(float(w_r), 4 * EPS)
    assert ss.peak_amplitude == rel_approx(float(a_max), 4 * EPS)
    # It is the maximum: the textbook amplitude on a fine grid around w_r never exceeds it
    # (beyond rounding, 4 eps) and comes within the grid's quadratic error of it.
    w = np.linspace(float(w_r) * 0.999, float(w_r) * 1.001, 2001)
    a = 2.0 / np.sqrt((25.0 - w**2) ** 2 + (3.0 * w) ** 2)
    assert np.max(a) <= ss.peak_amplitude * (1 + 4 * EPS)
    assert np.max(a) >= ss.peak_amplitude * (1 - 1e-12)


def test_no_amplitude_peak_from_zeta_one_over_root_two() -> None:
    # zeta = 1/sqrt(2) exactly when b^2 = 2mk: m = 1, k = 2, b = 2. The amplitude then falls
    # monotonically from w = 0; one ulp less damping gives a (tiny) peak.
    at_edge = osc.steady_state(_inputs(Case(1.0, 2.0, 2.0, 1.0, 1.0)))
    assert at_edge is not None
    assert at_edge.peak_angular_frequency is None
    assert at_edge.peak_amplitude is None
    below = osc.steady_state(_inputs(Case(1.0, 2.0, math.nextafter(2.0, 0.0), 1.0, 1.0)))
    assert below is not None
    assert below.peak_angular_frequency is not None
    assert below.peak_angular_frequency > 0


# --- Resonance curve (D9), OR5 (power) and OR6 (steady-state power balance) --------------

CURVE_CASE = Case(1.0, 25.0, 2.0, 3.0, 6.0)  # gamma = 1, zeta = 0.2


def test_resonance_frequency_grid_spans_zero_to_max_of_3w0_and_1_2w() -> None:
    grid = osc.resonance_frequencies(_inputs(CURVE_CASE), 301)
    assert grid.shape == (301,)
    assert grid[0] == 0.0
    assert grid[-1] == 15.0  # 3 w0 > 1.2 w
    fast = osc.resonance_frequencies(_inputs(Case(1.0, 25.0, 2.0, 3.0, 20.0)), 11)
    assert fast[-1] == rel_approx(24.0, EPS)  # 1.2 w > 3 w0
    assert np.all(np.diff(grid) > 0)


def test_resonance_curve_matches_reference_and_phase_rises_from_0_to_pi() -> None:
    p = _inputs(CURVE_CASE)
    w = osc.resonance_frequencies(p, 61)
    amplitude, phase = osc.resonance_curve(p, w)
    for wi, ai, di in zip(w, amplitude, phase, strict=True):
        a_ref, d_ref = reference_amplitude_phase(Case(1.0, 25.0, 2.0, 3.0, float(wi)))
        assert ai == rel_approx(float(a_ref), 4 * EPS)  # as in the steady-state test
        assert abs(Decimal(float(di)) - d_ref) <= Decimal(4 * EPS * math.pi)
    assert phase[0] == 0.0
    assert np.all(np.diff(phase) > 0)  # strictly increasing: 0 -> pi/2 at w0 -> towards pi
    assert phase[-1] < math.pi


def test_power_curve_peaks_at_w0_with_half_power_width_exactly_2_gamma() -> None:
    # Mean power in the steady state, P = (1/2) F0 w A sin(delta) (from the module's A, delta).
    # Exact facts (OR5): P(w0) = F0^2 / (2b); P(w) [1 + (w0^2 - w^2)^2 / (4 gamma^2 w^2)] =
    # P(w0) for every w > 0 (so the peak is at w0 and nowhere else); the half-power points are
    # w = sqrt(gamma^2 + w0^2) -+ gamma, so the width is exactly 2 gamma. Each side is a few
    # roundings and sin(delta) >= 0.05 on this grid (zeta = 0.2), so 1e-13 relative is ample.
    p = _inputs(CURVE_CASE)
    f0, b, g, w0 = 3.0, 2.0, 1.0, 5.0

    def power(w: np.ndarray) -> np.ndarray:
        a, d = osc.resonance_curve(p, w)
        return 0.5 * f0 * w * a * np.sin(d)

    p_peak = f0**2 / (2 * b)
    assert power(np.array([w0]))[0] == rel_approx(p_peak, 1e-13)
    w = np.linspace(0.5, 15.0, 400)
    lorentz = 1 + (w0**2 - w**2) ** 2 / (4 * g**2 * w**2)
    np.testing.assert_allclose(power(w) * lorentz, p_peak, rtol=1e-13, atol=0)
    half = np.array([math.sqrt(g**2 + w0**2) - g, math.sqrt(g**2 + w0**2) + g])
    np.testing.assert_allclose(power(half), p_peak / 2, rtol=1e-13, atol=0)
    assert half[1] - half[0] == rel_approx(2 * g, 4 * EPS)


def test_steady_state_power_in_equals_power_dissipated() -> None:
    # OR6: (1/2) F0 w A sin(delta) = (1/2) b w^2 A^2, an identity between the module's A and
    # delta (it fails if the phase is wrong). sin(delta) >= 0.05 on this grid: 1e-13 relative.
    p = _inputs(CURVE_CASE)
    w = np.linspace(0.5, 15.0, 400)
    a, d = osc.resonance_curve(p, w)
    np.testing.assert_allclose(
        0.5 * 3.0 * w * a * np.sin(d), 0.5 * 2.0 * w**2 * a**2, rtol=1e-13, atol=0
    )


def test_resonance_curve_needs_damping() -> None:
    # With b = 0 the amplitude has a pole at w0 and there is no steady state.
    with pytest.raises(ValueError, match="damping"):
        osc.resonance_curve(_inputs(Case(1.0, 25.0, 0.0, 1.0, 3.0)), np.array([1.0, 2.0]))


# --- The scale X (plan D5; amended by G2 and by decision B of 2026-11-03) -------------------


def _scale(case: Case, duration: float) -> float:
    """The module's X, used to normalise errors; its bound property is tested just below."""
    return osc.scale(_inputs(case), duration)


def _error_budget(case: Case, duration: float) -> float:
    """4 eps (Q + w0 T + A/X + 1), the measured error model relative to X (written out here).

    Q = sqrt(mk)/b (0 when b = 0) and A (90-digit) for the cancellation of x_p and the
    transient, w0 T for the phase rounding. Coefficient: worst measured 1.46 (short-run and
    state tests), so 4 leaves a factor ~3.
    """
    m, k, b = case.mass, case.spring_constant, case.damping_coefficient
    quality = math.sqrt(m * k) / b if b > 0 else 0.0
    amplitude = (
        float(reference_amplitude_phase(case)[0]) if b > 0 and case.drive_amplitude > 0 else 0.0
    )
    w0 = math.sqrt(k / m)
    return 4 * EPS * (quality + w0 * duration + amplitude / _scale(case, duration) + 1)


def test_scale_is_the_free_amplitude_plus_the_driven_bound() -> None:
    # X = sqrt(x0^2 + (v0/w0)^2) + D; closed values for free runs (D = 0), w0 = 5.
    free = Case(1.0, 25.0, 0.5, 0.0, 5.0, 0.1, 2.0)
    assert osc.driven_bound(_inputs(free), 20.0) == 0.0  # F0 = 0: nothing is driven
    assert osc.scale(_inputs(free), 20.0) == rel_approx(math.sqrt(0.1**2 + 0.4**2), 2 * EPS)
    other = Case(1.0, 25.0, 0.5, 0.0, 5.0, -0.7, 2.0)
    assert osc.scale(_inputs(other), 20.0) == rel_approx(math.sqrt(0.7**2 + 0.4**2), 2 * EPS)
    undamped = Case(1.0, 25.0, 0.0, 0.0, 0.0, 0.3, -2.0)  # the free amplitude exactly
    assert osc.scale(_inputs(undamped), 1.0) == rel_approx(0.5, 2 * EPS)
    driven = Case(1.0, 25.0, 0.5, 1.0, 5.0, 0.01, 0.0)
    expected = 0.01 + osc.driven_bound(_inputs(driven), 20.0)
    assert osc.scale(_inputs(driven), 20.0) == rel_approx(expected, EPS)


def test_driven_bound_oscillating_cap_closed_value() -> None:
    # Cap 2 is the least for Q = 10 at w0 over T = 20 s (written out here: w0 = 5, gamma = 0.25).
    g, wd, w, t_end = 0.25, math.sqrt(25.0 - 0.0625), 5.0, 20.0
    length = -math.expm1(-g * t_end) / g
    cap2 = (1 / (2 * wd)) * (
        min(length, 2 / math.hypot(g, wd - w)) + min(length, 2 / math.hypot(g, wd + w))
    )
    d = osc.driven_bound(_inputs(Case(1.0, 25.0, 0.5, 1.0, 5.0)), t_end)
    assert d == rel_approx(cap2, 1e-13)  # wd - w is formed differently (no cancellation)


def test_driven_bound_steady_plus_transient_cap_closed_value() -> None:
    # Cap 5 for the overdamped case above: A + min(energy, |xt0| + |vt0| G_max) with
    # G_max = exp(-atanh(r)/r)/w0, r = beta/gamma (the maximum of e^{-gamma u} sinh(beta u)/beta,
    # where tanh(beta u) = r), all written out here; w0 = 1.
    b, w = 19.69, 0.975
    g = b / 2
    r = math.sqrt(g * g - 1.0) / g
    g_max = math.exp(-math.atanh(r) / r)
    detuning, width = 1.0 - w * w, b * w
    hyp = math.hypot(detuning, width)
    a = 1.0 / hyp
    x_start, v_start = a * abs(detuning) / hyp, w * a * width / hyp
    cap5 = a + min(math.hypot(x_start, v_start), x_start + v_start * g_max)
    d = osc.driven_bound(_inputs(Case(1.0, 1.0, b, 1.0, w)), 34.45)
    assert d == rel_approx(cap5, 1e-12)  # atanh near r = 1 loses a few digits here


def test_driven_bound_coth_cap_closed_value() -> None:
    # Static force, zeta = 0.9 (w0 = 5, gamma = 4.5): the least cap is
    # (f/w0^2) coth(pi gamma/(2 wd)) = (1/25) coth(pi 4.5/(2 sqrt(4.75))).
    wd = math.sqrt(25.0 - 4.5**2)
    expected = (1 / 25.0) / math.tanh(math.pi * 4.5 / (2 * wd))
    d = osc.driven_bound(_inputs(Case(1.0, 25.0, 9.0, 1.0, 0.0)), 10.0)
    assert d == rel_approx(expected, 1e-13)


@pytest.mark.parametrize("w", [0.0, 0.5])
def test_driven_bound_is_continuous_across_critical_damping(w: float) -> None:
    # Re-review: D used to halve at zeta = 1 for a static force (0.08 below, 0.04 at and above).
    # With the coth cap, which tends to f/w0^2 as wd -> 0, it is continuous (1e-6 relative for
    # zeta = 1 -+ 1e-9, where coth(pi gamma/(2 wd)) = 1 to double precision).
    ds = [
        osc.driven_bound(_inputs(Case(1.0, 25.0, b, 1.0, w)), 10.0)
        for b in (10.0 * (1 - 1e-9), 10.0, 10.0 * (1 + 1e-9))
    ]
    assert ds[0] == pytest.approx(ds[1], rel=1e-6)
    assert ds[2] == pytest.approx(ds[1], rel=1e-6)


SCALE_BOUND_CASES = [
    ("undamped-free", Case(1.0, 25.0, 0.0, 0.0, 0.0, 0.3, -2.0), 5.0),
    ("underdamped-driven-at-w0", Case(1.0, 25.0, 0.5, 1.0, 5.0, 0.1, 0.5), 20.0),
    ("underdamped-driven-above", Case(1.0, 25.0, 0.5, 1.0, 12.0, -0.1, 1.0), 8.0),
    ("Q1e4-beats", Case(1.0, 25.0, 5e-4, 1.0, 4.0, 0.05, -0.3), 50.0),
    ("critical-driven", Case(1.0, 25.0, 10.0, 1.0, 5.0, 0.1, 0.3), 10.0),
    ("overdamped-driven", Case(2.0, 3.0, 40.0, 2.0, 1.7, 0.1, 0.2), 40.0),
    ("undamped-at-resonance", Case(1.0, 25.0, 0.0, 1.0, 5.0, 0.1, 0.4), 20.0),
    ("undamped-beats", Case(2.0, 3.0, 0.0, 1.5, 1.2, 0.1, 0.2), 40.0),
]


@pytest.mark.parametrize(
    ("case", "duration"), [pytest.param(c, d, id=i) for i, c, d in SCALE_BOUND_CASES]
)
def test_scale_bounds_the_whole_motion(case: Case, duration: float) -> None:
    # Decision B: |x(t)| <= X on [0, T], with x0, v0 and the drive all present (90-digit
    # reference; 1e-12 relative slack for X's own rounding). It is also not far above the
    # motion here: at least a quarter of X is reached (free + driven peaks need not align).
    t = np.linspace(0.0, duration, 1201)
    peak = float(max(abs(x) for x, _ in reference_states(case, t)))
    bound = _scale(case, duration)
    assert peak <= bound * (1 + 1e-12)
    assert peak >= 0.25 * bound


def test_scale_is_zero_when_nothing_moves() -> None:
    assert osc.scale(_inputs(Case(1.0, 25.0, 0.5)), 10.0) == 0.0


@pytest.mark.parametrize("duration", [0.0, -1.0, math.nan, math.inf])
def test_scale_and_driven_bound_need_a_positive_finite_duration(duration: float) -> None:
    with pytest.raises(ValueError, match="duration"):
        osc.scale(_inputs(DAMPED_PRESET), duration)
    with pytest.raises(ValueError, match="duration"):
        osc.driven_bound(_inputs(DAMPED_PRESET), duration)


def test_driven_bound_takes_the_smallest_proved_cap() -> None:
    # Closed values of the caps written out by hand, where one of them is clearly the least.
    p = _inputs(Case(1.0, 25.0, 0.5, 1.0, 5.0))
    assert osc.driven_bound(p, 0.01) == rel_approx(1.0 * 0.01**2 / 2, 2 * EPS)  # f T^2/2
    beats = _inputs(Case(1.0, 25.0, 0.0, 1.0, 5.3))  # b = 0, long run: 2f/|w0^2 - w^2|
    assert osc.driven_bound(beats, 200.0) == rel_approx(2.0 / abs(25.0 - 5.3**2), 4 * EPS)
    resonant = _inputs(Case(1.0, 25.0, 0.0, 1.0, 5.0))  # b = 0 at w0: f T/(w0 + w)
    assert osc.driven_bound(resonant, 20.0) == rel_approx(20.0 / 10.0, 2 * EPS)
    # Heavy overdamping, slow drive, short run (the motion creeps at ~f t/(2 gamma)):
    # f (1 - e^{-sT})/(2 beta s) with s = w0^2/(gamma + beta).
    g = 285.0
    beta = math.sqrt(g * g - 1.0)
    s_rate = 1.0 / (g + beta)
    creep = _inputs(Case(1.0, 1.0, 2 * g, 1.0, 0.01))
    expected = -math.expm1(-s_rate * 0.87) / (2 * beta * s_rate)
    assert osc.driven_bound(creep, 0.87) == rel_approx(expected, 8 * EPS)


BOUND_CASES = [
    # b = 0
    ("undamped-at-resonance", Case(1.0, 25.0, 0.0, 1.0, 5.0), 20.0),
    ("undamped-near", Case(2.0, 3.0, 0.0, 1.5, math.sqrt(1.5) * (1 + 1e-6)), 50.0),
    ("undamped-beats", Case(1.0, 25.0, 0.0, 1.0, 5.3), 60.0),
    ("undamped-far-above", Case(1.0, 25.0, 0.0, 1.0, 40.0), 10.0),
    ("undamped-static", Case(1.0, 25.0, 0.0, 1.0, 0.0), 10.0),
    # b > 0
    ("reviewer-beats-b1e-3-w4", Case(1.0, 25.0, 1e-3, 1.0, 4.0), 50.0),
    ("Q1e4-at-w0-short", Case(1.0, 25.0, 5e-4, 1.0, 5.0), 20.0),
    ("Q10-at-w0", Case(1.0, 25.0, 0.5, 1.0, 5.0), 20.0),
    ("Q10-above", Case(1.0, 25.0, 0.5, 1.0, 12.0), 8.0),
    ("Q10-static", Case(1.0, 25.0, 0.5, 1.0, 0.0), 20.0),
    ("Q10-very-short", Case(1.0, 25.0, 0.5, 1.0, 5.0), 0.05),
    ("near-critical", Case(1.0, 25.0, 9.9, 1.0, 5.0), 5.0),
    ("critical", Case(1.0, 25.0, 10.0, 1.0, 5.0), 10.0),
    ("overdamped", Case(2.0, 3.0, 40.0, 2.0, 1.7), 40.0),
    ("overdamped-fast-drive", Case(1.0, 1.0, 4.0, 1.0, 30.0), 20.0),
    ("overdamped-creep", Case(1.0, 1.0, 570.0, 1.0, 0.01), 0.87),
    # cap 5 is the least here and nearly met: an overdamped sup|G| half as large would be
    # exceeded by the motion (1.0136 D, re-review 2026-11-03)
    ("overdamped-cap5-tight", Case(1.0, 1.0, 19.69, 1.0, 0.975), 34.45),
]


@pytest.mark.parametrize(
    ("case", "duration"), [pytest.param(c, d, id=i) for i, c, d in BOUND_CASES]
)
def test_driven_bound_holds_and_is_reasonably_tight(case: Case, duration: float) -> None:
    # From rest (x0 = v0 = 0) the motion is exactly the driven part, which D must bound on
    # [0, T] (proved in the docstring; here against the 90-digit textbook formulas). The
    # slack 1e-12 covers the rounding of D itself (a few eps) with room. Tightness: the motion
    # reaches at least a quarter of D (a random scan of 4000 cases found at worst 0.34 of D,
    # median 0.86; several caps here, e.g. the beats and the linear growth, are nearly met).
    t = np.linspace(0.0, duration, 1201)
    peak = float(max(abs(x) for x, _ in reference_states(case, t)))
    bound = osc.driven_bound(_inputs(case), duration)
    assert peak <= bound * (1 + 1e-12)
    assert peak >= 0.25 * bound


def test_scale_has_no_jump_between_q_1e4_and_b_0_off_resonance() -> None:
    # Decision B: the b = 0 beat cap 2f/|w0^2 - w^2| is the b -> 0 limit of the damped caps,
    # so X barely changes between the lightest allowed damping and none (O(1/Q) = 1e-4 here).
    damped = _scale(Case(1.0, 25.0, 5e-4, 1.0, 3.0), 200.0)  # Q = 1e4
    undamped = _scale(Case(1.0, 25.0, 0.0, 1.0, 3.0), 200.0)
    assert damped == pytest.approx(undamped, rel=1e-3)


# --- OR2, OR3: the exact state against the 90-digit textbook branch formulas ---------------

# (id, case, duration). Durations keep w0 T <= ~100 rad, where the phase error that no formula
# removes (eps w0 t, from the rounded products w t and the rounded w0) stays near 1e-14.
STATE_CASES = [
    ("free-underdamped-preset", Case(1.0, 25.0, 0.5, 0.0, 5.0, 0.1, 0.0), 20.0),
    ("free-underdamped-v0", Case(0.3, 7.0, 0.4, 0.0, 0.0, -0.2, 1.5), 15.0),
    ("free-critical", Case(1.0, 25.0, 10.0, 0.0, 0.0, 0.1, 0.3), 5.0),
    ("free-near-critical-below", Case(1.0, 25.0, 10.0 * (1 - 1e-8), 0.0, 0.0, 0.1, 0.3), 5.0),
    ("free-near-critical-above", Case(1.0, 25.0, 10.0 * (1 + 1e-8), 0.0, 0.0, 0.1, 0.3), 5.0),
    ("free-one-ulp-below-critical", Case(1.0, 25.0, math.nextafter(10.0, 0.0), 0, 0, 0.1, 0.3), 5),
    ("free-overdamped-zeta4", Case(1.0, 25.0, 40.0, 0.0, 0.0, 0.1, -1.0), 20.0),
    ("free-overdamped-zeta1e6", Case(1.0, 1.0, 2e6, 0.0, 0.0, 1.0, 0.5), 8e6),
    ("free-undamped", Case(1.0, 25.0, 0.0, 0.0, 0.0, 0.1, 0.5), 20.0),
    ("driven-below", Case(1.0, 25.0, 0.5, 1.0, 2.0, 0.1, 0.0), 20.0),
    ("driven-at-w0", Case(1.0, 25.0, 0.5, 1.0, 5.0, 0.0, 0.0), 20.0),
    ("driven-Q1e4-at-w0", Case(1.0, 25.0, 5e-4, 1.0, 5.0, 0.0, 0.0), 20.0),  # Q-aware budget
    ("driven-above", Case(1.0, 25.0, 0.5, 1.0, 12.0, 0.1, -0.4), 8.0),
    ("driven-static-force", Case(1.0, 25.0, 0.5, 1.0, 0.0, 0.0, 0.0), 20.0),
    ("driven-critical", Case(1.0, 25.0, 10.0, 1.0, 5.0, 0.0, 0.0), 10.0),
    ("driven-overdamped", Case(2.0, 3.0, 40.0, 2.0, 1.7, 0.1, 0.2), 40.0),
    ("undamped-at-resonance", Case(1.0, 25.0, 0.0, 1.0, 5.0, 0.1, 0.0), 20.0),
    ("undamped-near-resonance", Case(1.0, 25.0, 0.0, 1.0, 5.0 * (1 + 1e-7), 0.0, 0.2), 20.0),
    ("undamped-off-resonance", Case(2.0, 3.0, 0.0, 1.5, 1.2, 0.1, 0.2), 40.0),
    ("small-scales", Case(1e-6, 1e-2, 1e-5, 1e-6, 80.0, 1e-3, 0.0), 1.0),
    ("large-scales", Case(1e6, 1e9, 1e6, 1e6, 30.0, 0.0, 0.5), 3.0),
]


def _times(duration: float, geometric: bool = False) -> np.ndarray:
    if geometric:  # resolve both the fast (1/(gamma + beta)) and slow (1/s) time scales
        return np.concatenate([[0.0], np.geomspace(duration * 1e-14, duration, 120)])
    # 81 even points plus early ones, offset so they hit no special phase.
    return np.concatenate(
        [
            [0.0, 1e-9 * duration, 1e-4 * duration],
            np.linspace(0.0, duration, 81)[1:] * (1 - 1 / 997),
        ]
    )


@pytest.mark.parametrize(
    ("case", "duration"), [pytest.param(c, d, id=i) for i, c, d in STATE_CASES]
)
def test_state_matches_90_digit_textbook_formulas(case: Case, duration: float) -> None:
    # Acceptance (slice 1): |x - x_ref| <= 1e-13 X and |v - v_ref| <= 1e-13 V, with
    # V = max(w0, w) X, the speed of a motion of size X at the frequencies present. Expected
    # rounding is a few eps (1 + w0 t) ~ 2e-14 at w0 T = 100: the target leaves a factor ~5.
    # Near resonance at high Q the cancellation adds ~eps (Q + A/X) (the error model, see
    # _error_budget): driven-Q1e4-at-w0 measures 3.3e-12 X (Q = 1e3 would give 3.0e-13 X),
    # so the tolerance is the larger of 1e-13 and that budget.
    t = _times(duration, geometric=case.damping_coefficient > 1e5)
    x, v = osc.state(_inputs(case), t)
    refs = reference_states(case, t)
    scale_x = _scale(case, duration)
    w0 = math.sqrt(case.spring_constant / case.mass)
    scale_v = max(w0, case.drive_angular_frequency) * scale_x
    tolerance = max(1e-13, _error_budget(case, duration))
    assert max_error(x, [r for r, _ in refs], scale_x) <= tolerance
    assert max_error(v, [r for _, r in refs], scale_v) <= tolerance


def test_state_returns_arrays_of_the_times_shape() -> None:
    x, v = osc.state(_inputs(DAMPED_PRESET), np.zeros((3, 2)))
    assert x.shape == (3, 2)
    assert v.shape == (3, 2)
    assert np.all(x == 0.1)


@pytest.mark.parametrize("bad", [[-1.0], [math.nan], [math.inf]])
def test_state_rejects_negative_or_non_finite_times(bad: list[float]) -> None:
    with pytest.raises(ValueError, match="times"):
        osc.state(_inputs(DAMPED_PRESET), np.array(bad))


# --- Pitfalls (i)-(iii): the naive textbook formula fails, the module does not ----------------


def _naive_underdamped(case: Case, t: np.ndarray) -> np.ndarray:
    """The free textbook underdamped formula in floats, e^{-gt}[x0 cos wd t + (v0+g x0)/wd sin]."""
    m, k, b = case.mass, case.spring_constant, case.damping_coefficient
    g = b / (2 * m)
    wd = np.sqrt(k / m - g * g)
    x0, v0 = case.initial_displacement, case.initial_velocity
    return np.exp(-g * t) * (x0 * np.cos(wd * t) + (v0 + g * x0) / wd * np.sin(wd * t))


def test_pitfall_i_critical_damping_has_no_zero_over_zero() -> None:
    case = Case(1.0, 25.0, 10.0, 0.0, 0.0, 0.1, 0.3)  # b^2 = 4mk exactly: wd = 0
    t = np.linspace(0.0, 3.0, 61)
    with np.errstate(all="ignore"):
        assert np.all(np.isnan(_naive_underdamped(case, t)[1:]))  # (v0 + g x0) * 0/0
    with np.errstate(all="raise"):  # the module divides by nothing that can be zero
        x, _ = osc.state(_inputs(case), t)
    refs = reference_states(case, t)
    assert max_error(x, [r for r, _ in refs], 0.1) <= 1e-13  # 0.1 = |x0| <= X: stricter


def test_pitfall_ii_heavy_damping_no_overflow_and_no_cancellation() -> None:
    # gamma T = 1e5: e^{-gamma t} cosh(beta t) is 0 * inf in floats beyond beta t ~ 710.
    case = Case(1.0, 1.0, 2e3, 0.0, 0.0, 1.0, -3.0)  # gamma = 1e3, zeta = 1e3
    t = np.concatenate([[0.0], np.geomspace(1e-6, 100.0, 200)])
    g = 1e3
    beta = math.sqrt(g * g - 1.0)
    with np.errstate(all="ignore"):
        naive = np.exp(-g * t) * np.cosh(beta * t)
    assert np.any(np.isnan(naive))
    with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
        x, v = osc.state(_inputs(case), t)
    assert np.all(np.isfinite(x))
    assert np.all(np.isfinite(v))
    refs = reference_states(case, t)
    assert max_error(x, [r for r, _ in refs], 3.0) <= 1e-13  # 3 = |v0|/w0 <= X: stricter
    assert max_error(v, [r for _, r in refs], 3.0) <= 1e-13  # w0 |v0|/w0 <= w0 X: stricter


def test_pitfall_ii_slow_rate_written_without_cancellation() -> None:
    # zeta = 1e6: gamma - beta = w0^2/(gamma + beta) ~ 5e-7, and the float gamma - beta keeps
    # only ~4 digits (it subtracts two numbers ~1e6 that agree to 12 digits). The motion after
    # the fast mode dies is x0' e^{-s t}; the module must get s right to rounding.
    case = Case(1.0, 1.0, 2e6, 0.0, 0.0, 1.0, 0.0)
    g = 1e6
    with localcontext(prec=70):
        s_exact = Decimal(g) - (Decimal(g) ** 2 - 1).sqrt()
    naive = g - math.sqrt(g * g - 1.0)
    assert abs(naive / float(s_exact) - 1) > 1e-6
    t = np.array([1.0 / float(s_exact)])  # one slow time constant
    x, _ = osc.state(_inputs(case), t)
    ref = reference_states(case, t)[0][0]
    assert max_error(x, [ref], 1.0) <= 1e-13


def test_pitfall_iii_undamped_near_and_at_resonance() -> None:
    # w = w0 (1 + 1e-10): f (cos wt - cos w0 t)/(w0^2 - w^2) divides two nearly equal
    # differences; in floats it loses ~6 digits. At w = w0 it is 0/0. The beat form is exact.
    t = np.linspace(0.0, 20.0, 81) * (1 - 1 / 997)
    for w in (5.0 * (1 + 1e-10), 5.0):
        case = Case(1.0, 25.0, 0.0, 1.0, w, 0.0, 0.0)
        with np.errstate(all="ignore"):
            naive = (np.cos(w * t) - np.cos(5.0 * t)) / (25.0 - w * w)
        x, _ = osc.state(_inputs(case), t)
        refs = [r for r, _ in reference_states(case, t)]
        scale_x = _scale(case, 20.0)
        naive_error = math.inf if np.any(np.isnan(naive[1:])) else max_error(naive, refs, scale_x)
        assert naive_error > 1e-9
        assert max_error(x, refs, scale_x) <= 1e-13


# --- OR8: the closed form satisfies the ODE and the initial conditions ---------------------


def _d4(fn: np.ndarray, h: float) -> np.ndarray:
    """Fourth-order central difference of samples at t-2h, t-h, t+h, t+2h (rows 0..3)."""
    return (fn[0] - 8 * fn[1] + 8 * fn[2] - fn[3]) / (12 * h)


ODE_CASES = [c for c in STATE_CASES if c[0] != "free-overdamped-zeta1e6"]


@pytest.mark.parametrize(("case", "duration"), [pytest.param(c, d, id=i) for i, c, d in ODE_CASES])
def test_closed_form_satisfies_the_ode_and_initial_conditions(case: Case, duration: float) -> None:
    # Residual m a + b v + k x - F0 cos wt with a from a 4th-order central difference of the
    # module's v (and v checked against the same difference of x). With W = the fastest rate
    # present, max(w0, w, 2 gamma), and h W = 2^-10: truncation (hW)^4/30 ~ 3e-14 and rounding
    # 1.5 eps/(hW) ~ 3e-13 of each term's size, so 1e-10 of the force scale
    # m W^2 X + b W X + k X + F0 leaves a factor > 100. h is a power of two and the times are
    # multiples of h, so t +- h and t +- 2h are exact. (zeta = 1e6 is excluded: its fast rate
    # needs h ~ 1e-10 s on an 8e6 s run, beyond what float times can space evenly; the
    # 90-digit test covers it.)
    m, k, b, f0, w = (
        case.mass,
        case.spring_constant,
        case.damping_coefficient,
        case.drive_amplitude,
        case.drive_angular_frequency,
    )
    w0 = math.sqrt(k / m)
    rate = max(w0, w, b / m)
    h = 2.0 ** math.floor(math.log2(2.0**-10 / rate))
    t = np.round(np.linspace(3 * h, duration, 50) / h) * h
    p = _inputs(case)
    offsets = np.array([-2, -1, 1, 2])[:, None] * h
    xs, vs = osc.state(p, t[None, :] + offsets)
    x, v = osc.state(p, t)
    scale_x = _scale(case, duration)
    force = m * rate**2 * scale_x + b * rate * scale_x + k * scale_x + f0
    residual = m * _d4(vs, h) + b * v + k * x - f0 * np.cos(w * t)
    # The stencil also amplifies the module's own rounding (the error model, _error_budget,
    # times X) by ~1.5/(hW) = 1.5 * 2^10: that matters only at high Q (Q = 1e4 here).
    allowed = max(1e-10, 2000 * _error_budget(case, duration))
    assert np.max(np.abs(residual)) <= allowed * force
    assert np.max(np.abs(_d4(xs, h) - v)) <= allowed * rate * scale_x
    # Initial conditions: x(0) = x0 and v(0) = v0 up to the rounding of x_p(0) + (x0 - x_p(0)).
    x_start, v_start = osc.state(p, 0.0)
    assert abs(x_start - case.initial_displacement) <= 4 * EPS * scale_x
    assert abs(v_start - case.initial_velocity) <= 4 * EPS * max(w0, w) * scale_x


@pytest.mark.parametrize(
    "case",
    [
        Case(1.0, 25.0, 0.5, 1.0, 4.0, 0.1, 0.0),
        Case(1.0, 25.0, 10.0, 1.0, 5.0, 0.0, 0.3),
        Case(2.0, 3.0, 0.0, 1.5, math.sqrt(1.5) * (1 + 1e-6), 0.1, 0.0),
    ],
)
def test_closed_form_matches_an_independent_tight_integration(case: Case) -> None:
    # The test's own right-hand side, integrated by DOP853 at rtol 1e-13 over 20 s (16 cycles):
    # the plan's scratch runs found such solves within ~1e-11 of max|x| for non-stiff cases,
    # so 1e-10 of X checks the closed form against something that shares nothing with it.
    from scipy.integrate import solve_ivp

    m, k, b, f0, w = (
        case.mass,
        case.spring_constant,
        case.damping_coefficient,
        case.drive_amplitude,
        case.drive_angular_frequency,
    )
    scale_x = _scale(case, 20.0)
    t = np.linspace(0.0, 20.0, 201)

    def rhs(time: float, y: np.ndarray) -> list[float]:
        return [y[1], (f0 * math.cos(w * time) - b * y[1] - k * y[0]) / m]

    sol = solve_ivp(
        rhs,
        (0.0, 20.0),
        [case.initial_displacement, case.initial_velocity],
        method="DOP853",
        rtol=1e-13,
        atol=1e-16 * scale_x,
        t_eval=t,
    )
    x, _ = osc.state(_inputs(case), t)
    assert np.max(np.abs(x - sol.y[0])) <= 1e-10 * scale_x


# --- OR4: free decay; OR6: energy ---------------------------------------------------------


@pytest.mark.parametrize("case", [DAMPED_PRESET, Case(0.3, 7.0, 1.2, 0.0, 0.0, -0.2, 1.5)])
def test_free_decay_repeats_every_damped_period_shrunk_by_exp_minus_gamma_td(case: Case) -> None:
    # The free underdamped motion is e^{-gamma t} times a function of period T_d, so
    # x(t + T_d) = e^{-gamma T_d} x(t) for every t (OR4, exact). T_d and gamma are computed
    # here from their definitions. Each side is within ~1e-15 X of the truth (90-digit test);
    # rounding t + T_d adds ~eps w0 t: 2e-14 X is the bound.
    m, k, b = case.mass, case.spring_constant, case.damping_coefficient
    g = b / (2 * m)
    td = 2 * math.pi / math.sqrt(k / m - g * g)
    p = _inputs(case)
    t = np.linspace(0.0, 3 * td, 97)
    x, v = osc.state(p, t)
    x_later, v_later = osc.state(p, t + td)
    scale_x = _scale(case, 4 * td)
    w0 = math.sqrt(k / m)
    ratio = math.exp(-g * td)
    assert np.max(np.abs(x_later - ratio * x)) <= 2e-14 * scale_x
    assert np.max(np.abs(v_later - ratio * v)) <= 2e-14 * w0 * scale_x


def test_successive_maxima_are_td_apart_with_ratio_exp_minus_gamma_td() -> None:
    # The maxima themselves (where v = 0 going from + to -), located by root-finding on the
    # module's v. Near a root, v's rounding (~eps w0 X) moves the root by ~eps/w0, a relative
    # error ~eps in the spacing: 1e-12 relative leaves room for brentq's tolerance (4 eps).
    from scipy.optimize import brentq

    p = _inputs(DAMPED_PRESET)
    g = 0.25
    td = 2 * math.pi / math.sqrt(25.0 - g * g)
    t = np.linspace(0.0, 8 * td, 4001)
    _, v = osc.state(p, t)
    falling = np.nonzero((v[:-1] > 0) & (v[1:] <= 0))[0]
    roots = [
        brentq(lambda s: float(osc.state(p, s)[1]), t[i], t[i + 1], xtol=1e-15) for i in falling
    ]
    assert len(roots) >= 6
    peaks = osc.state(p, np.array(roots))[0]
    np.testing.assert_allclose(np.diff(roots), td, rtol=1e-12, atol=0)
    np.testing.assert_allclose(peaks[1:] / peaks[:-1], math.exp(-g * td), rtol=1e-12, atol=0)


def test_energy_is_conserved_without_damping_or_drive() -> None:
    # E = (1/2) m v^2 + (1/2) k x^2 is constant when b = F0 = 0 (OR6). Each of x, v is within
    # a few eps (1 + w0 t) of X; over w0 T = 100 that is ~1e-14 of E.
    case = Case(0.3, 7.0, 0.0, 0.0, 0.0, -0.2, 1.5)
    t = np.linspace(0.0, 100 / math.sqrt(7.0 / 0.3), 401)
    x, v = osc.state(_inputs(case), t)
    energy = 0.5 * 0.3 * v**2 + 0.5 * 7.0 * x**2
    e0 = 0.5 * 0.3 * 1.5**2 + 0.5 * 7.0 * 0.2**2
    np.testing.assert_allclose(energy, e0, rtol=2e-14, atol=0)


@pytest.mark.parametrize(
    ("case", "duration"),
    [
        (Case(1.0, 25.0, 0.5, 1.0, 4.0, 0.1, 0.0), 10.0),
        (Case(2.0, 3.0, 40.0, 2.0, 1.7, 0.1, 0.2), 20.0),
        (Case(1.0, 25.0, 10.0, 1.0, 5.0, 0.0, 0.3), 5.0),
    ],
)
def test_energy_balance_change_equals_drive_work_minus_damping_work(
    case: Case, duration: float
) -> None:
    # OR6: E(T) - E(0) = integral_0^T (F0 cos(w t) v - b v^2) dt, the right side by 8-point
    # Gauss-Legendre on 400 panels of the module's v (quadrature error < 1e-20 of the scale
    # for these smooth integrands). Both sides are ~eps of k X^2: 1e-12 k X^2 is the bound.
    m, k, b, f0, w = (
        case.mass,
        case.spring_constant,
        case.damping_coefficient,
        case.drive_amplitude,
        case.drive_angular_frequency,
    )
    p = _inputs(case)
    nodes, weights = np.polynomial.legendre.leggauss(8)
    edges = np.linspace(0.0, duration, 401)
    mid, half = (edges[1:] + edges[:-1]) / 2, (edges[1:] - edges[:-1]) / 2
    tq = mid[:, None] + half[:, None] * nodes[None, :]
    _, vq = osc.state(p, tq)
    work = np.sum(half[:, None] * weights[None, :] * (f0 * np.cos(w * tq) * vq - b * vq**2))
    x_end, v_end = osc.state(p, duration)
    energy = lambda x, v: 0.5 * m * v**2 + 0.5 * k * x**2  # noqa: E731
    scale_x = _scale(case, duration)
    assert abs(
        energy(x_end, v_end) - energy(case.initial_displacement, case.initial_velocity) - work
    ) <= (1e-12 * k * scale_x**2)


# --- OR7: limits and continuity -------------------------------------------------------------

CONTINUITY_T = np.linspace(0.0, 4.0, 81) * (1 - 1 / 997)


@pytest.mark.parametrize("f0", [0.0, 1.0])
def test_continuous_and_smooth_across_critical_damping(f0: float) -> None:
    # b = 10 is critical (m = 1, k = 25); b = 10 -+ 2^-27 (zeta = 1 -+ 7.5e-10, exact floats)
    # are under- and overdamped and use the other branch. A smooth x(b) has a second
    # difference ~ (db)^2 x'' ~ 1e-18 X; a jump or kink at zeta = 1 would show at O(db) or
    # O(1). Each value carries ~1e-15 X of rounding: 1e-13 X bounds the sum of four.
    h = 2.0**-27
    xs = [
        osc.state(_inputs(Case(1.0, 25.0, b, f0, 4.0, 0.1, 0.3)), CONTINUITY_T)[0]
        for b in (10.0 - h, 10.0, 10.0 + h)
    ]
    assert osc.derived(_inputs(Case(1.0, 25.0, 10.0 - h))).regime == "underdamped"
    assert osc.derived(_inputs(Case(1.0, 25.0, 10.0 + h))).regime == "overdamped"
    scale_x = _scale(Case(1.0, 25.0, 10.0, f0, 4.0, 0.1, 0.3), 4.0)
    assert np.max(np.abs(xs[0] - 2 * xs[1] + xs[2])) <= 1e-13 * scale_x
    # and the two neighbours are within O(db) of the critical value (|dx/db| < X/b here)
    assert np.max(np.abs(xs[2] - xs[0])) <= 2 * h * scale_x


def test_continuous_and_smooth_through_resonance_without_damping() -> None:
    # b = 0, w = 5 -+ 2^-30 (exact floats) around w0 = 5: the beat form is one formula through
    # w = w0, so the second difference is ~ (dw t)^2 x ~ 1e-15 X; 1e-13 X allows the rounding.
    h = 2.0**-30
    xs = [
        osc.state(_inputs(Case(1.0, 25.0, 0.0, 1.0, w, 0.1, 0.0)), CONTINUITY_T)[0]
        for w in (5.0 - h, 5.0, 5.0 + h)
    ]
    scale_x = _scale(Case(1.0, 25.0, 0.0, 1.0, 5.0, 0.1, 0.0), 4.0)
    assert np.max(np.abs(xs[0] - 2 * xs[1] + xs[2])) <= 1e-13 * scale_x


@pytest.mark.parametrize("w", [0.0, 3.5, 5.0])
def test_damped_solution_tends_to_the_undamped_one_as_b_tends_to_zero(w: float) -> None:
    # The b > 0 code (steady state + transient) and the b = 0 code (beat form) are different
    # formulas; continuity at b = 0 means |x(b) - x(0)| -> 0, and for a smooth x(b) it does so
    # linearly: the slope max|x(zeta) - x(0)|/zeta must settle to a constant as zeta shrinks.
    # zeta stops at 5e-5 (Q = 1e4, the limit). The first correction to the slope is
    # O(zeta (w0 t)^2) <= 2e-4 * 400 ~ 8%, halving with zeta: successive slopes within 5%.
    def x_at(b: float) -> np.ndarray:
        return osc.state(_inputs(Case(1.0, 25.0, b, 1.0, w, 0.1, 0.2)), CONTINUITY_T)[0]

    undamped = x_at(0.0)
    slopes = [np.max(np.abs(x_at(10.0 * z) - undamped)) / z for z in (2e-4, 1e-4, 5e-5)]
    assert slopes[1] == pytest.approx(slopes[0], rel=0.05)
    assert slopes[2] == pytest.approx(slopes[1], rel=0.05)
    assert abs(slopes[2] - slopes[1]) <= 0.6 * abs(slopes[1] - slopes[0]) + 1e-9 * slopes[1]


def test_linear_in_the_drive_amplitude_and_free_as_it_tends_to_zero() -> None:
    # The ODE is linear in F0, so x(2F) - 2 x(F) + x(0) = 0 exactly (OR7, F0 -> 0); and a
    # vanishing F0 gives the free motion. Rounding: a few eps of X(2F) per value.
    t = CONTINUITY_T
    for b in (0.0, 0.5, 40.0):
        xs = [
            osc.state(_inputs(Case(1.0, 25.0, b, f, 4.0, 0.1, 0.2)), t)[0] for f in (0.0, 0.7, 1.4)
        ]
        scale_x = _scale(Case(1.0, 25.0, b, 1.4, 4.0, 0.1, 0.2), 4.0)
        assert np.max(np.abs(xs[2] - 2 * xs[1] + xs[0])) <= 1e-14 * scale_x
        tiny = osc.state(_inputs(Case(1.0, 25.0, b, 5e-324, 4.0, 0.1, 0.2)), t)[0]
        assert np.max(np.abs(tiny - xs[0])) <= 4 * EPS * 0.1


# --- The decay envelope ---------------------------------------------------------------------


@pytest.mark.parametrize("case", [DAMPED_PRESET, Case(0.3, 7.0, 1.2, 0.0, 0.0, -0.2, 1.5)])
def test_envelope_of_a_free_underdamped_run(case: Case) -> None:
    # For x_h = R e^{-gamma t} cos(wd t - phi): R e^{-gamma t} = sqrt(x^2 + ((v + gamma x)/wd)^2),
    # evaluated here in 70 digits from the reference x, v. A few roundings: 1e-14 relative.
    m, k, b = case.mass, case.spring_constant, case.damping_coefficient
    t = np.linspace(0.0, 10.0, 41)
    envelope = osc.transient_envelope(_inputs(case), t)
    assert envelope is not None
    with localcontext(prec=70):
        g = Decimal(b) / (2 * Decimal(m))
        wd = (Decimal(k) / Decimal(m) - g * g).sqrt()
        expected = [
            float((x * x + ((v + g * x) / wd) ** 2).sqrt()) for x, v in reference_states(case, t)
        ]
    np.testing.assert_allclose(envelope, expected, rtol=1e-14, atol=0)


def test_envelope_bounds_the_transient_of_a_driven_run() -> None:
    # |x - x_p| <= envelope, with x_p = A cos(w t - delta) from the 90-digit (A, delta).
    case = Case(1.0, 25.0, 0.5, 1.0, 3.0, 0.1, 0.0)
    t = np.linspace(0.0, 20.0, 801)
    a, d = (float(v) for v in reference_amplitude_phase(case))
    x, _ = osc.state(_inputs(case), t)
    envelope = osc.transient_envelope(_inputs(case), t)
    assert envelope is not None
    transient = np.abs(x - a * np.cos(3.0 * t - d))
    assert np.all(transient <= envelope + 1e-14 * _scale(case, 20.0))
    assert np.max(transient / envelope) >= 0.999  # it touches the envelope at the extremes


@pytest.mark.parametrize(
    "case",
    [
        Case(1.0, 25.0, 0.0, 0.0, 0.0, 0.1),
        Case(1.0, 25.0, 10.0, 0.0, 0.0, 0.1),
        Case(1.0, 25.0, 40.0, 0.0, 0.0, 0.1),
    ],
)
def test_no_envelope_unless_underdamped(case: Case) -> None:
    assert osc.transient_envelope(_inputs(case), np.array([0.0, 1.0])) is None


# --- Light damping near resonance (pitfall iv): the Q limit (decision A, 2026-11-03) ------

G3_SYSTEMS = [(1.0, 25.0), (0.3, 7.0)]  # w0 = 5 exactly, and w0 = sqrt(70/3) (rounded)


@pytest.mark.parametrize(("mass", "spring"), G3_SYSTEMS)
@pytest.mark.parametrize("quality", [10.0, 1e2, 1e3, 1e4])
@pytest.mark.parametrize("detune", ["at-w0", "half-power", "1e-6-below"])
@pytest.mark.parametrize("cycles", [16, 100, 1000])
def test_error_near_resonance_relative_to_the_motion_reached(
    mass: float, spring: float, quality: float, detune: str, cycles: int
) -> None:
    # From rest (x0 = v0 = 0, the worst cancellation: x_p and the transient start equal and
    # opposite), against the 90-digit reference on 201 times, relative both to the motion
    # actually reached, max|x_ref|, and to the scale X (>= the motion, so a smaller number).
    # Two error sources: the cancellation, ~eps A, which relative to a motion that has not yet
    # built up (runs shorter than ~Q/w0) is ~eps Q; and the phase rounding of the products w t
    # and wd t, ~eps w0 t. Measured (2026-11-03, this machine), error / max|x_ref|:
    #   Q = 10:  <= 6.9e-15 (16 cycles), 8.2e-14 (100), 4.6e-13 (1000);
    #   Q = 1e2: <= 3.2e-14, 8.8e-14, 4.6e-13;   Q = 1e3: <= 2.6e-13, 5.0e-13, 5.1e-13;
    #   Q = 1e4: <= 4.0e-12, 7.1e-12, 4.6e-12   (error / X is 0.6 to 1.0 times these).
    # So error / max|x_ref| <= c eps (Q + w0 T) with c <= 3.0 measured; 6 is asserted (twice
    # the worst). This eps Q growth is why Q > 1e4 is refused (decision A).
    w0 = math.sqrt(spring / mass)
    omega = {
        "at-w0": w0,
        "half-power": w0 * (1 + 1 / (2 * quality)),
        "1e-6-below": w0 * (1 - 1e-6),
    }[detune]
    case = Case(mass, spring, math.sqrt(mass * spring) / quality, 1.0, omega, 0.0, 0.0)
    duration = cycles * 2 * math.pi / w0
    t = np.linspace(0.0, duration, 201) * (1 - 1 / 997)
    p = _inputs(case)
    x, _ = osc.state(p, t)
    refs = [r for r, _ in reference_states(case, t)]
    motion = float(max(abs(r) for r in refs))
    error_motion = max_error(x, refs, motion)
    error_scale = max_error(x, refs, osc.scale(p, duration))
    assert error_motion <= 6 * EPS * (quality + w0 * duration)
    assert error_scale <= error_motion


def test_quality_factor_above_1e4_is_refused_when_damped() -> None:
    # Q = sqrt(mk)/b: m = 1, k = 1e8, b = 1 gives Q = 1e4 exactly (allowed); one ulp less
    # damping gives Q > 1e4 (refused). b = 0 stays allowed at any Q (it is exact, OR3).
    assert osc.derived(_inputs(Case(1.0, 1e8, 1.0))).quality_factor == 1e4
    with pytest.raises(ValueError, match="1e4"):
        osc.OscillatorInputs(
            mass=1.0, spring_constant=1e8, damping_coefficient=math.nextafter(1.0, 0.0)
        )
    with pytest.raises(ValueError, match="quality factor"):
        osc.OscillatorInputs(
            mass=1.0,
            spring_constant=1.0,
            damping_coefficient=1e-300,
            drive_amplitude=1e6,
            drive_angular_frequency=1.0,
        )
    assert osc.derived(_inputs(Case(1.0, 1e8, 0.0))).regime == "undamped"


# --- Short runs (decision of 2026-11-03: the model needs max(w0, w, gamma) T >= 1) -------------


def test_rate_duration_product_and_its_minimum() -> None:
    assert osc.MIN_DURATION_RATE_PRODUCT == 1.0
    p = _inputs(Case(1.0, 25.0, 30.0, 1.0, 7.0))  # w0 = 5, w = 7, gamma = 15
    assert osc.rate_duration_product(p, 0.2) == rel_approx(3.0, EPS)


SHORT_CASES = [
    ("Q10-static", Case(1.0, 25.0, 0.5, 1.0, 0.0)),
    ("Q1e4-w4", Case(1.0, 25.0, 5e-4, 1.0, 4.0)),
    ("Q1e4-at-w0", Case(1.0, 25.0, 5e-4, 1.0, 5.0)),
    ("overdamped", Case(2.0, 3.0, 40.0, 2.0, 1.7)),
    ("critical", Case(1.0, 25.0, 10.0, 1.0, 5.0)),
    ("undamped-at-resonance", Case(1.0, 25.0, 0.0, 1.0, 5.0)),
    ("Q10-fast-drive", Case(1.0, 25.0, 0.5, 1.0, 100.0)),
    ("heavily-overdamped-slow-drive", Case(1.0, 1e-6, 2.0, 1.0, 1e-4)),
]


@pytest.mark.parametrize("start", [(0.0, 0.0), (1e-3, 2e-3)])
@pytest.mark.parametrize("rate_t", [1e-3, 1.0, 10.0])
@pytest.mark.parametrize(("name", "case"), SHORT_CASES)
def test_short_runs_follow_the_error_model(
    name: str, case: Case, rate_t: float, start: tuple[float, float]
) -> None:
    # In a short driven run (b > 0) x_p and the transient, each ~A, cancel to a motion of
    # only ~f T^2/2, so the rounding ~eps A is large relative to X: the error model is
    # eps (Q + w0 T + A/X). Measured at the limit max(w0, w, gamma) T = 1 (2026-11-03):
    # <= 1.5e-14 X in every case here except Q = 1e4 at resonance (3.7e-12 X from rest,
    # 5.8e-12 X with x0, v0: its Q term, as in long runs); below the limit it grows as A/X
    # (rate_t = 1e-3 here; the re-review measured 1.2e-5 X at w0 T = 5e-6). Asserted: the
    # budget 4 eps (Q + w0 T + A/X + 1), and 1e-13 X at and above the limit when Q <= 100.
    w0 = math.sqrt(case.spring_constant / case.mass)
    rate = max(w0, case.drive_angular_frequency, case.damping_coefficient / (2 * case.mass))
    duration = rate_t / rate
    full = Case(
        case.mass,
        case.spring_constant,
        case.damping_coefficient,
        case.drive_amplitude,
        case.drive_angular_frequency,
        *start,
    )
    assert osc.rate_duration_product(_inputs(full), duration) == rel_approx(rate_t, 2 * EPS)
    t = np.linspace(0.0, duration, 101)
    x, _ = osc.state(_inputs(full), t)
    error = max_error(x, [r for r, _ in reference_states(full, t)], _scale(full, duration))
    assert error <= _error_budget(full, duration)
    quality = (
        math.sqrt(case.mass * case.spring_constant) / case.damping_coefficient
        if (case.damping_coefficient > 0)
        else 0.0
    )
    if rate_t >= osc.MIN_DURATION_RATE_PRODUCT and quality <= 100:
        assert error <= 1e-13


# --- Finiteness: inputs whose derived quantities overflow are refused ----------------------------


@pytest.mark.parametrize(
    ("values", "match"),
    [
        # gamma = b/2m = 5e299: gamma^2 overflows (float(q) raised OverflowError before)
        ({"mass": 1e-200, "spring_constant": 1e-100, "damping_coefficient": 1e100}, "gamma"),
        # A = f / (2 gamma w) ~ 5e313 overflows (the re-review's b = 1e-154, which gave NaN,
        # is now refused by Q > 1e4 first; b = 2e-154 has Q = 5e3)
        (
            {
                "mass": 1.0,
                "spring_constant": 1e-300,
                "damping_coefficient": 2e-154,
                "drive_amplitude": 1e10,
                "drive_angular_frequency": 1e-150,
            },
            "amplitude",
        ),
        # zeta^2 = gamma^2/w0^2 = 1e300 / 1e-10 overflows
        ({"mass": 1.0, "spring_constant": 1e-10, "damping_coefficient": 2e150}, "zeta"),
        # w^2 overflows
        (
            {
                "mass": 1.0,
                "spring_constant": 1.0,
                "drive_amplitude": 1.0,
                "drive_angular_frequency": 1e200,
            },
            "drive_angular_frequency",
        ),
        # f = F0/m overflows
        ({"mass": 1e-300, "spring_constant": 1e-300, "drive_amplitude": 1e300}, "F0/m"),
    ],
)
def test_inputs_whose_derived_quantities_overflow_are_refused(
    values: dict[str, float], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        osc.OscillatorInputs(**values)


def test_a_scale_that_overflows_is_refused() -> None:
    p = osc.OscillatorInputs(
        mass=1.0, spring_constant=1.0, initial_displacement=1.5e308, initial_velocity=1.5e308
    )
    with pytest.raises(ValueError, match="scale"):
        osc.scale(p, 1.0)
