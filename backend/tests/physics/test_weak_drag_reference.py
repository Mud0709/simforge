"""Tests of the weak-drag perturbation reference (roadmap 2.2, RS3, seam 1).

The helper (:mod:`tests.physics.weak_drag_reference`) gives the first-order effect of
quadratic drag on the range and on the best launch angle from the ground, with
eps = (v0/v_t)^2. Every expected value here comes from an *independent* source:

- 50-digit ``decimal`` evaluations (stdlib only) of the helper's closed forms and of the
  definition of F(theta), including a 50-digit central difference for F'(pi/4);
- ``scipy.integrate.quad`` of the integrals J0 and J2 straight from their integrands;
- a test-local DOP853 integration of the full equations of motion at rtol = 1e-13 with a
  bounded Brent search for the best angle, at several small eps: the helper's first-order
  prediction must leave a residual that shrinks like eps^2 (an order test).

Never from the helper's own output.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from decimal import Decimal, localcontext

import numpy as np
import pytest
from scipy.integrate import quad, solve_ivp
from scipy.optimize import minimize_scalar

from tests.approx import rel_approx
from tests.physics import weak_drag_reference as wd

G = 9.80665
V0 = 20.0
EPS = 2.0**-52  # 2.2e-16

# --- 50-digit references ------------------------------------------------------------------

PI_50 = "3.14159265358979323846264338327950288419716939937510582097494459"


def _series(first: Decimal, ratio: Callable[[int], Decimal]) -> Decimal:
    """Sum first + first*ratio(1) + ... until the terms stop changing the total."""
    term, total, n = first, first, 0
    while True:
        n += 1
        term *= ratio(n)
        if total + term == total:
            return total
        total += term


def _dsin(x: Decimal) -> Decimal:
    return _series(x, lambda n: -x * x / ((2 * n) * (2 * n + 1)))


def _dcos(x: Decimal) -> Decimal:
    return _series(Decimal(1), lambda n: -x * x / ((2 * n - 1) * (2 * n)))


def _dterms(theta: Decimal) -> list[Decimal]:
    """The four terms of F(theta) = c s^2 + c^3 s A + c(1 + s^2)/4 - c^5 A/(4 s), in decimal.

    A = asinh(tan theta) is computed as ln(tan + sec) = ln((1 + s)/c), a different route
    from the float helper's asinh(tan theta).
    """
    s, c = _dsin(theta), _dcos(theta)
    a = ((1 + s) / c).ln()
    return [c * s * s, c**3 * s * a, c * (1 + s * s) / 4, -(c**5) * a / (4 * s)]


def _dec_f(theta: Decimal) -> Decimal:
    return sum(_dterms(theta), Decimal(0))


def test_decimal_helpers_match_known_values() -> None:
    # Sanity check of this file's own references against float64 at ordinary arguments.
    with localcontext() as ctx:
        ctx.prec = 50
        assert float(_dsin(Decimal("0.5"))) == rel_approx(math.sin(0.5), rel=1e-15)
        assert float(_dcos(Decimal("0.5"))) == rel_approx(math.cos(0.5), rel=1e-15)
        assert float(Decimal(PI_50)) == math.pi
        # sin(pi/4) = cos(pi/4) = 1/sqrt(2): checks the series and the pi literal together.
        quarter = Decimal(PI_50) / 4
        assert abs(_dsin(quarter) - 1 / Decimal(2).sqrt()) < Decimal("1e-48")
        assert abs(_dcos(quarter) - 1 / Decimal(2).sqrt()) < Decimal("1e-48")


# --- Closed forms of the coefficients ------------------------------------------------------


def test_closed_forms_follow_from_the_definition_of_f_at_45_degrees() -> None:
    """F(pi/4) = 7/(8 sqrt 2) + (3/16) ln(1 + sqrt 2), F'(pi/4) = (3 sqrt 2 - ln(1 + sqrt 2))/8.

    Both sides in 50-digit decimal: the left from the general F(theta), the right from the
    plan's hand-derived closed forms, so this checks the derivation, not the float code.
    """
    with localcontext() as ctx:
        ctx.prec = 50
        r2 = Decimal(2).sqrt()
        ln = (1 + r2).ln()
        quarter = Decimal(PI_50) / 4
        # About 20 operations on O(1) numbers, each rounded to 1e-50: 1e-45 is a wide margin.
        f_closed = 7 / (8 * r2) + Decimal(3) / 16 * ln
        assert abs(_dec_f(quarter) - f_closed) < Decimal("1e-45")
        # Central difference with step d = 1e-20: truncation |F'''| d^2 / 6 ~ 1e-40 (F''' is
        # O(10) here) and rounding ~ 1e-50 / d = 1e-30. 1e-25 is far above both, and far
        # below any algebra slip in the closed form.
        d = Decimal("1e-20")
        f_prime_numerical = (_dec_f(quarter + d) - _dec_f(quarter - d)) / (2 * d)
        f_prime_closed = (3 * r2 - ln) / 8
        assert abs(f_prime_numerical - f_prime_closed) < Decimal("1e-25")


def test_float_coefficients_match_their_50_digit_closed_forms() -> None:
    with localcontext() as ctx:
        ctx.prec = 50
        r2 = Decimal(2).sqrt()
        ln = (1 + r2).ln()
        f_45 = 7 / (8 * r2) + Decimal(3) / 16 * ln
        f_prime = (3 * r2 - ln) / 8
        angle = Decimal(180) / Decimal(PI_50) * f_prime / 4
    # Each float coefficient is at most ~5 correctly rounded operations (<= 0.5 ulp each) on
    # well-conditioned sums (3 sqrt 2 - ln(1 + sqrt 2) has condition (4.24 + 0.88)/3.36 = 1.5),
    # so the error is under ~4 ulp: 4 eps relative (8.9e-16).
    loss, slope, shift = wd.RANGE_COEFFICIENT, wd.F_PRIME_AT_45, wd.ANGLE_COEFFICIENT_DEG
    assert loss == rel_approx(float(f_45), rel=4 * EPS)
    assert slope == rel_approx(float(f_prime), rel=4 * EPS)
    assert shift == rel_approx(float(angle), rel=4 * EPS)
    # The plan's rounded decimals (0.783976, 0.420158, 6.0183) agree to their last digit.
    assert loss == pytest.approx(0.783976, abs=5e-7)
    assert slope == pytest.approx(0.420158, abs=5e-7)
    assert shift == pytest.approx(6.0183, abs=5e-5)


def test_vacuum_limit_is_45_degrees_and_v0_squared_over_g() -> None:
    assert wd.first_order_best_angle_deg(0.0) == 45.0
    assert wd.first_order_best_range_ratio(0.0) == 1.0


# --- F(theta) at general angles ------------------------------------------------------------

ANGLES_DEG = [10.0, 20.0, 30.0, 45.0, 60.0, 75.0, 85.0]


@pytest.mark.parametrize("angle_deg", ANGLES_DEG)
def test_f_matches_a_50_digit_evaluation(angle_deg: float) -> None:
    theta = math.radians(angle_deg)
    with localcontext() as ctx:
        ctx.prec = 50
        terms = _dterms(Decimal(theta))  # Decimal(float) is exact
        expected = sum(terms, Decimal(0))
        condition = float(sum((abs(t) for t in terms), Decimal(0)) / abs(expected))
    # The float F sums four terms, each a few rounded operations plus asinh(tan theta), whose
    # relative sensitivity to rounding in tan is at most ~6 (85 degrees). 16 eps per unit of
    # the sum's condition number (sum |terms| / |F|: 7.0 at 10 degrees, where the last two
    # terms nearly cancel, 1.0 to 2.4 from 20 degrees up) covers both. Measured error: <= 2.4 eps.
    assert wd.range_correction(theta) == rel_approx(float(expected), rel=16 * EPS * condition)


@pytest.mark.parametrize("angle_deg", ANGLES_DEG)
def test_f_matches_quadrature_of_the_j_integrals(angle_deg: float) -> None:
    """F = c [s J0 + J2 / s] with v0 = 1 (u = c, w = s), J0 = int_{-s}^{s} sqrt(c^2 + q^2) dq,
    J2 = int_{-s}^{s} q^2 sqrt(c^2 + q^2) dq: the plan's delta R before its closed forms."""
    theta = math.radians(angle_deg)
    c, s = math.cos(theta), math.sin(theta)
    # epsrel = 1e-13 is just above QUADPACK's floor (50 eps = 1.1e-14 when epsabs = 0).
    j0, e0 = quad(lambda q: math.sqrt(c * c + q * q), -s, s, epsabs=0, epsrel=1e-13)
    j2, e2 = quad(lambda q: q * q * math.sqrt(c * c + q * q), -s, s, epsabs=0, epsrel=1e-13)
    assert e0 < 1e-13 * j0
    assert e2 < 1e-13 * j2
    # Quadrature (<= 1e-13 each, by its own error estimate) plus the float F's rounding
    # (16 eps x condition <= 2.5e-14, see the 50-digit test) plus assembling c [s J0 + J2/s]
    # (a few eps), with the two integrals adding: 3e-13 relative. Measured: <= 2.1e-16.
    assert wd.range_correction(theta) == rel_approx(c * (s * j0 + j2 / s), rel=3e-13)


# --- Independent integration of the full equations of motion -------------------------------

# DOP853 at rtol = 1e-13 (atol 1e-13 m and m/s, on positions ~40 m and speeds ~20 m/s, so
# rtol governs). Measured (scratch, this machine): tightening rtol from 1e-12 to 1e-13 moved
# the best range by <= 1.3e-13 relative, far below the eps^2 residuals tested (>= 1e-6 of
# v0^2/g in range, >= 8e-5 degrees in angle).
RTOL = 1e-13
ATOL = 1e-13


def _range(theta: float, eps: float) -> float:
    """Range in m at v0 = 20 m/s, g = 9.80665 m/s^2 and kappa = eps g / v0^2 (eps = (v0/v_t)^2).

    Physical units on purpose: this also checks that eps = kappa v0^2 / g is the group in
    which the helper's dimensionless result applies.
    """
    kappa = eps * G / V0**2

    def rhs(_t: float, z: np.ndarray) -> list[float]:
        vx, vy = float(z[2]), float(z[3])
        speed = math.hypot(vx, vy)
        return [vx, vy, -kappa * speed * vx, -G - kappa * speed * vy]

    def ground(t: float, z: np.ndarray) -> float:
        return float(z[1]) if t > 0 else 1.0  # y = 0 at launch is not the landing

    ground.terminal = True  # type: ignore[attr-defined]
    ground.direction = -1.0  # type: ignore[attr-defined]
    t_vacuum = 2 * V0 * math.sin(theta) / G  # drag only shortens the flight
    z0 = [0.0, 0.0, V0 * math.cos(theta), V0 * math.sin(theta)]
    sol = solve_ivp(
        rhs, (0.0, 2 * t_vacuum), z0, method="DOP853", rtol=RTOL, atol=ATOL, events=ground
    )
    assert sol.status == 1, "no landing found"
    return float(sol.y_events[0][0][0])


def _slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of log|y| against log x."""
    return float(np.polyfit(np.log(xs), np.log(np.abs(ys)), 1)[0])


def _linear_part(xs: list[float], ys: list[float]) -> float:
    """The eps-coefficient of a residual y(eps) = a1 eps + a2 eps^2 + a3 eps^3 + ...

    Three-point Richardson extrapolation of y/eps to eps = 0 from xs[0], 2 xs[0], 4 xs[0]:
    (8 q(e) - 6 q(2e) + q(4e)) / 3 = a1 + O(e^3), with q = y/eps. If the first-order
    prediction is right, a1 = 0; an error of delta in its coefficient gives a1 = delta.
    """
    assert xs[1] == 2 * xs[0]
    assert xs[2] == 4 * xs[0]
    q = [y / x for x, y in zip(xs, ys, strict=True)]
    return (8 * q[0] - 6 * q[1] + q[2]) / 3


# Two complementary order tests per prediction:
# - the fitted slope of log|residual| against log eps must be 2 +- 0.1. Over each eps range
#   used, the measured residual / eps^2 drifts by at most ~4% (the O(eps^3) term; 3.28 -> 3.20
#   for the angle, 0.765 -> 0.738 for the range over eps = 5e-3 to 4e-2), which moves the
#   slope by ~0.02; the reference's own error (~1e-10 degrees, ~1e-13 in range) by far less.
#   A first-order error pulls the slope towards 1, but only visibly once it is comparable
#   with the eps^2 term (mutation-checked: a 0.1% error in the range coefficient passes it);
# - so the residual's linear part (``_linear_part``) must also vanish, to a tolerance set by
#   the O(eps^3) remainder of the extrapolation (each test states it). That is the sharp test
#   of the coefficients and of F.
SLOPE_TOLERANCE = 0.1
RANGE_EPS = [1e-3, 2e-3, 4e-3, 8e-3]


@pytest.mark.parametrize("angle_deg", [20.0, 45.0, 70.0])
def test_first_order_range_leaves_an_eps_squared_residual(angle_deg: float) -> None:
    """R(theta) / (v0^2/g) = sin 2 theta - eps F(theta) + O(eps^2) at a fixed angle."""
    theta = math.radians(angle_deg)
    scale = V0**2 / G
    residuals = [
        _range(theta, e) / scale - (math.sin(2 * theta) - e * wd.range_correction(theta))
        for e in RANGE_EPS
    ]
    assert _slope(RANGE_EPS, residuals) == pytest.approx(2.0, abs=SLOPE_TOLERANCE)
    # Measured (scratch): the linear part from eps = 1e-3 is <= 6.6e-9 at these angles, and
    # from 2e-3 <= 5.2e-8 (~8x, the eps^3 remainder); the reference adds ~1e-13 / 1e-3 = 1e-10.
    # 5e-8 is ~7x the measured value and ~1e-7 of F (0.28 to 0.78 here).
    assert abs(_linear_part(RANGE_EPS, residuals)) < 5e-8


OPTIMUM_EPS = [5e-3, 1e-2, 2e-2, 4e-2]  # the plan's order-test values (RS3: eps >= 5e-3)


def _best(eps: float) -> tuple[float, float]:
    """(best angle in degrees, best range / (v0^2/g)) from the ground, by the integration.

    Brent alone stalls ~1e-6 degrees from the peak (measured: up to 1.75e-6 degrees between
    brackets), because the top is flat: the range changes only by ~angle error squared. So
    Brent only centres a least-squares cubic through 21 ranges within +-0.2 degrees, and the
    cubic's stationary point is the reference. Measured (scratch): three Brent brackets and
    half-widths 0.2 and 0.4 degrees agree to <= 2.4e-11 degrees at every eps used here.
    """
    brent = minimize_scalar(
        lambda a: -_range(math.radians(float(a)), eps),
        bounds=(40.0, 45.5),
        method="bounded",
        options={"xatol": 1e-9},
    )
    centre = float(brent.x)
    offsets = np.linspace(-0.2, 0.2, 21)
    ranges = [_range(math.radians(centre + d), eps) / (V0**2 / G) for d in offsets]
    cubic = np.polyfit(offsets, ranges, 3)
    roots = np.roots(np.polyder(cubic))
    peak = float(min(roots[np.isreal(roots)].real, key=abs))
    return centre + peak, float(np.polyval(cubic, peak))


@pytest.fixture(scope="module")
def optima() -> list[tuple[float, float]]:
    """The reference optimum at each eps in OPTIMUM_EPS."""
    return [_best(e) for e in OPTIMUM_EPS]


# The linear parts below, measured (scratch): from eps = 5e-3 they are 1.6e-6 (angle, in
# degrees) and 8.8e-7 (range ratio), and from 1e-2 they are 1.3e-5 and 6.8e-6, the factor ~8
# that an eps^3 remainder predicts; the reference adds ~1e-10 / 5e-3 = 2e-8 degrees and
# ~1e-13 / 5e-3 in range. Tolerances 1e-5 degrees and 5e-6 leave ~6x margin; relative to the
# coefficients (6.0183 degrees, 0.783976) that is 1.7e-6 and 6.4e-6.


def test_first_order_best_angle_leaves_an_eps_squared_residual(
    optima: list[tuple[float, float]],
) -> None:
    residuals = [
        a - wd.first_order_best_angle_deg(e) for (a, _), e in zip(optima, OPTIMUM_EPS, strict=True)
    ]
    assert _slope(OPTIMUM_EPS, residuals) == pytest.approx(2.0, abs=SLOPE_TOLERANCE)
    assert abs(_linear_part(OPTIMUM_EPS, residuals)) < 1e-5


def test_first_order_best_range_leaves_an_eps_squared_residual(
    optima: list[tuple[float, float]],
) -> None:
    residuals = [
        r - wd.first_order_best_range_ratio(e)
        for (_, r), e in zip(optima, OPTIMUM_EPS, strict=True)
    ]
    assert _slope(OPTIMUM_EPS, residuals) == pytest.approx(2.0, abs=SLOPE_TOLERANCE)
    assert abs(_linear_part(OPTIMUM_EPS, residuals)) < 5e-6
