"""Reference tests for the quadratic-drag closed forms and bounds (roadmap 2.1, seam 1).

Model: F = -c|v|v, so dv/dt = -g y_hat - kappa |v| v with kappa = c/m and terminal speed
v_t = sqrt(m g / c). Every expected value here comes from an *independent* source:

- the equations of motion themselves, written out in this file (central differences);
- textbook vacuum formulas and their Taylor corrections, derived by hand (c -> 0);
- closed forms derived separately from the code's (for example t_fall = tau asinh(v0/v_t)
  from the ground, or the impact speed v0 v_t / sqrt(v0^2 + v_t^2));
- 50-digit ``decimal`` evaluations of the plain textbook formulas (stdlib only), and a
  50-digit bisection of the linear-drag fall that the R7 flight-time bound is built from;
- a test-local SciPy integration of the 2-D equations (for the R7 bounds only).

Never from the code under test.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from decimal import MAX_EMAX, MIN_EMIN, Decimal, localcontext

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from simforge.physics.projectile import quadratic_reference as qr

G = 9.80665
EPS = float(np.finfo(float).eps)  # 2.2e-16


def rel_approx(expected: float, rel: float) -> object:
    """pytest.approx with a purely relative tolerance.

    pytest.approx(x, rel=r) still allows max(r |x|, 1e-12): for r = 4e-15 that absolute
    floor dominates whenever |x| < 250, so tight relative checks on seconds and metres
    would silently be ~1e-12 checks. abs=0 removes the floor.
    """
    return pytest.approx(expected, rel=rel, abs=0)


# --- 50-digit references (stdlib decimal; series where decimal has no function) ---------


def _dec(x: float) -> Decimal:
    return Decimal(x)  # exact: every float is a finite binary fraction


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


def _datan(x: Decimal) -> Decimal:
    # Halve the angle until the series converges fast: atan x = 2 atan(x / (1 + sqrt(1 + x^2))).
    doublings = 0
    while abs(x) > Decimal("0.1"):
        x = x / (1 + (1 + x * x).sqrt())
        doublings += 1
    total = _series(x, lambda n: -x * x * (2 * n - 1) / (2 * n + 1))
    return total * 2**doublings


def _dcosh(x: Decimal) -> Decimal:
    return (x.exp() + (-x).exp()) / 2


def _darcosh(z: Decimal) -> Decimal:
    return (z + (z * z - 1).sqrt()).ln()


class _Fifty:
    """A 50-digit decimal context with an exponent range wide enough for e^(2e6)."""

    def __enter__(self) -> None:
        self._cm = localcontext()
        ctx = self._cm.__enter__()
        ctx.prec, ctx.Emax, ctx.Emin = 50, MAX_EMAX, MIN_EMIN

    def __exit__(self, *exc: object) -> None:
        self._cm.__exit__(None, None, None)


def ref_apex_time(v0: float, v_t: float, g: float) -> float:
    with _Fifty():
        dv0, dvt, dg = _dec(v0), _dec(v_t), _dec(g)
        return float(dvt / dg * _datan(dv0 / dvt))


def ref_apex_height(v0: float, v_t: float, g: float) -> float:
    with _Fifty():
        dv0, dvt, dg = _dec(v0), _dec(v_t), _dec(g)
        return float(dvt * dvt / (2 * dg) * (1 + (dv0 / dvt) ** 2).ln())


def ref_rise_height(t: float, v0: float, h: float, v_t: float, g: float) -> float:
    with _Fifty():
        dt, dv0, dh, dvt, dg = _dec(t), _dec(v0), _dec(h), _dec(v_t), _dec(g)
        s = dg * dt / dvt
        return float(dh + dvt * dvt / dg * (_dcos(s) + dv0 / dvt * _dsin(s)).ln())


def ref_fall_distance(t: float, v_t: float, g: float) -> float:
    with _Fifty():
        dt, dvt, dg = _dec(t), _dec(v_t), _dec(g)
        return float(dvt * dvt / dg * _dcosh(dg * dt / dvt).ln())


def ref_fall_time(drop: float, v_t: float, g: float) -> float:
    with _Fifty():
        dy, dvt, dg = _dec(drop), _dec(v_t), _dec(g)
        return float(dvt / dg * _darcosh((dg * dy / (dvt * dvt)).exp()))


def ref_impact_speed(drop: float, v_t: float, g: float) -> float:
    with _Fifty():
        dy, dvt, dg = _dec(drop), _dec(v_t), _dec(g)
        return float(dvt * (1 - (-2 * dg * dy / (dvt * dvt)).exp()).sqrt())


def test_decimal_helpers_match_known_values() -> None:
    # Sanity check of the test's own references against float64 at ordinary arguments.
    with _Fifty():
        assert float(_dsin(Decimal("0.5"))) == rel_approx(math.sin(0.5), rel=1e-15)
        assert float(_dcos(Decimal("0.5"))) == rel_approx(math.cos(0.5), rel=1e-15)
        assert float(_datan(Decimal(3))) == rel_approx(math.atan(3.0), rel=1e-15)
        assert float(_darcosh(Decimal(2))) == rel_approx(math.acosh(2.0), rel=1e-15)


# --- R4: terminal speed -----------------------------------------------------------------


@pytest.mark.parametrize(("m", "c"), [(1.0, 0.01), (0.145, 1.2e-3), (1e-6, 1e6), (1e6, 1e-9)])
def test_terminal_speed_balances_weight_and_drag(m: float, c: float) -> None:
    v_t = qr.terminal_speed(m, c, G)
    # c v_t^2 = m g. Each side is a few correctly rounded operations (<= 1.1e-16 each),
    # and squaring doubles the sqrt's error, so they agree to < 1e-15.
    assert c * v_t**2 == rel_approx(m * G, rel=1e-15)


def test_terminal_speed_is_infinite_in_vacuum() -> None:
    assert qr.terminal_speed(1.0, 0.0, G) == math.inf


@pytest.mark.parametrize(("m", "c"), [(1.0, 1e-320), (1e10, 1e-300), (1e307, 1e-3), (1e308, 1.0)])
def test_terminal_speed_stays_finite_when_m_g_over_c_overflows(m: float, c: float) -> None:
    # m g / c exceeds the largest float (1.8e308) here, but v_t (1e154 to 1e160 m/s) does not:
    # with c > 0 it must not be reported as vacuum (inf). Reference: 50-digit decimal. The
    # result is at most ~5 correctly rounded operations (<= 2.5 ulp ~ 5.6e-16): rel 1e-15.
    with _Fifty():
        expected = float((_dec(m) * _dec(G) / _dec(c)).sqrt())
    assert qr.terminal_speed(m, c, G) == rel_approx(expected, rel=1e-15)


def test_long_fall_reaches_terminal_speed() -> None:
    v_t = 20.0
    tau = v_t / G
    # v_t - w = v_t (1 - tanh(20)) ~ 2 v_t e^-40 ~ 1.7e-16 m/s: below one ulp of v_t (3.6e-15),
    # so the exact result rounds to v_t itself. 2 eps leaves room for the rounding of tanh.
    assert qr.fall_speed(np.array([20 * tau]), v_t, G)[0] == rel_approx(v_t, rel=2 * EPS)
    # A drop of 50 v_t^2/g: 1 - sqrt(1 - e^-100) ~ 2e-44, far below rounding.
    assert qr.fall_impact_speed(50 * v_t**2 / G, v_t, G) == rel_approx(v_t, rel=2 * EPS)


def test_long_fall_distance_approaches_its_asymptote() -> None:
    # ln cosh u = u - ln 2 + ln(1 + e^-2u), so d -> v_t t - (v_t^2/g) ln 2; at u = 20 the
    # neglected term is (v_t^2/g) e^-40 ~ 2e-16 m. The asymptote subtracts 28 m from 816 m
    # (condition ~1.04), so rounding stays < 1e-15 relative; 1e-14 is a 10x margin.
    v_t = 20.0
    t = 20 * v_t / G
    expected = v_t * t - v_t**2 / G * math.log(2.0)
    assert qr.fall_distance(np.array([t]), v_t, G)[0] == rel_approx(expected, rel=1e-14)


# --- R1, R2: the closed forms satisfy their equations of motion -------------------------

# Central differences: error = truncation dt^2 |f'''| / 6 + rounding ~ eps |f| / dt.
# Each test below works out both terms for its own case.
DT = 1e-5


@pytest.mark.parametrize(("v0", "h", "v_t"), [(30.0, 2.0, 20.0), (60.0, 0.0, 20.0)])
def test_rise_satisfies_its_equation_of_motion(v0: float, h: float, v_t: float) -> None:
    """dv/dt = -g (1 + v^2/v_t^2) and dy/dt = v while rising."""
    t_a = qr.apex_time(v0, v_t, G)
    t = np.linspace(0.02 * t_a, 0.98 * t_a, 40)
    v = qr.rise_velocity(t, v0, v_t, G)
    dv = (qr.rise_velocity(t + DT, v0, v_t, G) - qr.rise_velocity(t - DT, v0, v_t, G)) / (2 * DT)
    dy = (qr.rise_height(t + DT, v0, h, v_t, G) - qr.rise_height(t - DT, v0, h, v_t, G)) / (2 * DT)
    # Here |v'''| <= ~1.3e3 m/s^4 (tan''' at r = v0/v_t = 3), so truncation <= 2.2e-8 m/s^2,
    # and rounding <= eps * 60 / 1e-5 ~ 1.3e-9 m/s^2, against |dv/dt| >= g ~ 9.8 m/s^2:
    # < 3e-9 relative, so rtol = 1e-8 has a 3x margin.
    np.testing.assert_allclose(dv, -G * (1 + v**2 / v_t**2), rtol=1e-8)
    # |y'''| = |v''| <= ~3e2 m/s^3 gives truncation <= 5e-9 m/s; rounding <= eps * 100 m / 1e-5
    # ~ 2e-9 m/s. v passes near 0 close to the apex, so the bound is absolute: 1e-7 m/s.
    np.testing.assert_allclose(dy, v, rtol=0, atol=1e-7)


def test_rise_starts_at_launch_and_stops_at_the_apex() -> None:
    v0, h, v_t = 30.0, 2.0, 20.0
    t_a = qr.apex_time(v0, v_t, G)
    v = qr.rise_velocity(np.array([0.0, t_a]), v0, v_t, G)
    y = qr.rise_height(np.array([0.0, t_a]), v0, h, v_t, G)
    assert v[0] == rel_approx(v0, rel=2 * EPS)  # a couple of roundings
    # At the apex v = 0 exactly; numerically the subtraction of terms of size v0 leaves
    # a few ulps of v0 (eps * 30 ~ 7e-15 m/s). 1e-13 m/s is a ~15x margin.
    assert abs(v[1]) < 1e-13
    assert y[0] == h
    # The rise curve at t_a (log of cos and sin) and the apex height (log1p of v0^2/v_t^2)
    # are different formulas for the same number; both are accurate to a few ulps.
    assert y[1] - h == rel_approx(qr.apex_height(v0, v_t, G), rel=1e-14)


@pytest.mark.parametrize("v_t", [20.0, 3.0])
def test_fall_satisfies_its_equation_of_motion(v_t: float) -> None:
    """With w = -v > 0 falling from rest: dw/dt = g (1 - w^2/v_t^2) and dd/dt = w."""
    tau = v_t / G
    t = np.linspace(0.02 * tau, 6 * tau, 40)  # crosses u = t/tau = 1 (any internal branch)
    w = qr.fall_speed(t, v_t, G)
    dw = (qr.fall_speed(t + DT, v_t, G) - qr.fall_speed(t - DT, v_t, G)) / (2 * DT)
    dd = (qr.fall_distance(t + DT, v_t, G) - qr.fall_distance(t - DT, v_t, G)) / (2 * DT)
    # |w'''| <= 2 g / tau^2 ~ 2e2 m/s^4 (v_t = 3) gives truncation <= 4e-9 m/s^2; rounding
    # <= eps * 20 / 1e-5 ~ 4.4e-10 m/s^2. dw/dt tends to 0 late in the fall, so the bound is
    # absolute: 1e-7 m/s^2 (> 20x margin).
    np.testing.assert_allclose(dw, G * (1 - w**2 / v_t**2), rtol=0, atol=1e-7)
    # |d'''| = |w''| <= ~2 g / tau ~ 70 m/s^3 gives <= 1.2e-9 m/s; rounding on d <= 120 m is
    # <= eps * 120 / 1e-5 ~ 2.7e-9 m/s; w >= 0.02 g tau, so rtol 1e-8 plus atol 1e-8 m/s.
    np.testing.assert_allclose(dd, w, rtol=1e-8, atol=1e-8)


@pytest.mark.parametrize(("drop", "v_t"), [(10.0, 20.0), (1e3, 20.0), (1e5, 1.0), (1e-6, 50.0)])
def test_fall_time_and_impact_speed_are_consistent_with_the_fall_curve(
    drop: float, v_t: float
) -> None:
    # fall_time inverts d(t) (arcosh form) and fall_impact_speed is w at that time
    # (expm1 form): different formulas from fall_distance (ln cosh) and fall_speed (tanh).
    t_land = qr.fall_time(drop, v_t, G)
    # d'(t) t / d is between 1 and 2, so a ~1e-15 relative error in t_land becomes
    # <= 2e-15 in d; 1e-14 leaves a 5x margin for the few roundings in each function.
    assert qr.fall_distance(np.array([t_land]), v_t, G)[0] == rel_approx(drop, rel=1e-14)
    assert qr.fall_speed(np.array([t_land]), v_t, G)[0] == rel_approx(
        qr.fall_impact_speed(drop, v_t, G), rel=1e-14
    )


# --- R3: the vertical flight ------------------------------------------------------------


@pytest.mark.parametrize("r", [1e-3, 0.1, 1.0, 10.0, 1e3])
def test_impact_speed_from_the_ground_is_v0_vt_over_root_sum_of_squares(r: float) -> None:
    v_t = 20.0
    v0 = r * v_t
    f = qr.vertical_flight(v0, 0.0, v_t, G)
    # From the ground e^(2X) = 1 + v0^2/v_t^2, so the impact speed is v0 v_t / sqrt(v0^2+v_t^2).
    # Both sides are ~10 correctly rounded operations: <= ~1.1e-15 apart; 4e-15 is a margin.
    assert f.impact_speed == rel_approx(v0 * v_t / math.sqrt(v0**2 + v_t**2), rel=4e-15)
    assert f.impact_speed < v0  # energy is lost to drag


@pytest.mark.parametrize("r", [1e-3, 0.1, 1.0, 10.0, 1e3])
def test_from_the_ground_the_fall_takes_longer_than_the_rise(r: float) -> None:
    v_t = 20.0
    v0 = r * v_t
    tau = v_t / G
    f = qr.vertical_flight(v0, 0.0, v_t, G)
    # Independent closed forms from the ground: rise tau*atan(r), fall tau*asinh(r)
    # (arcosh(e^X) = asinh(sqrt(e^(2X) - 1)) = asinh(r)). Few roundings each: rel 4e-15.
    assert f.apex_time == rel_approx(tau * math.atan(r), rel=4e-15)
    assert f.fall_time == rel_approx(tau * math.asinh(r), rel=4e-15)
    # asinh r - atan r = r^3/6 + ... > 0: the smallest gap here (r = 1e-3) is 1.7e-7 relative,
    # far above rounding, so a strict inequality is a real check.
    assert f.fall_time > f.apex_time
    assert f.flight_time == rel_approx(f.apex_time + f.fall_time, rel=EPS)


def test_vertical_flight_from_a_height_matches_the_rise_and_fall_curves() -> None:
    v0, h, v_t = 25.0, 40.0, 15.0
    f = qr.vertical_flight(v0, h, v_t, G)
    assert f.max_height == rel_approx(h + qr.apex_height(v0, v_t, G), rel=EPS)
    y_apex = qr.rise_height(np.array([f.apex_time]), v0, h, v_t, G)[0]
    assert y_apex == rel_approx(f.max_height, rel=1e-14)  # two different formulas (above)
    assert qr.fall_distance(np.array([f.fall_time]), v_t, G)[0] == rel_approx(
        f.max_height, rel=1e-14
    )
    # Drag removes energy: slower than the vacuum impact sqrt(v0^2 + 2 g h), and below v_t.
    assert f.impact_speed < math.sqrt(v0**2 + 2 * G * h)
    assert f.impact_speed < v_t


# --- c -> 0: Taylor limits against the textbook vacuum formulas -------------------------


def test_weak_drag_taylor_corrections_from_the_ground() -> None:
    """With r = v0/v_t, by hand: atan(r)/r = 1 - r^2/3, ln(1+r^2)/r^2 = 1 - r^2/2,
    (1+r^2)^(-1/2) = 1 - r^2/2, asinh(r)/r = 1 - r^2/6, each + O(r^4)."""
    v0 = 20.0
    v_t = 1e4 * v0  # r = 1e-4: corrections 1e-8 relative, the next terms <= 3r^4/8 ~ 4e-17
    r2 = (v0 / v_t) ** 2
    f = qr.vertical_flight(v0, 0.0, v_t, G)
    expected = {
        "apex_time": v0 / G * (1 - r2 / 3),
        "max_height": v0**2 / (2 * G) * (1 - r2 / 2),
        "fall_time": v0 / G * (1 - r2 / 6),
        "flight_time": 2 * v0 / G * (1 - r2 / 4),
        "impact_speed": v0 * (1 - r2 / 2),
    }
    for name, value in expected.items():
        got = getattr(f, name)
        # Truncation < 4e-17 plus ~10 roundings: rel 2e-15. The r^2 correction itself is
        # >= 1.7e-9 relative, ~1e6 times the tolerance, so the limit is really tested.
        assert got == rel_approx(value, rel=2e-15), name
        assert abs(got - value) < 1e-6 * abs(value * r2), name


@pytest.mark.parametrize(("m", "c"), [(1.0, 0.0), (1.0, 1e-25), (1.0, 1e-320)])
@pytest.mark.parametrize("h", [0.0, 50.0])
def test_vertical_flight_tends_to_the_textbook_vacuum_flight(m: float, c: float, h: float) -> None:
    # c = 1e-25 gives v_t ~ 3e12 m/s, so drag corrections are O(g Y / v_t^2) ~ 1e-22 relative;
    # c = 1e-320 is subnormal (v_t ~ 3e160): the formulas must still not overflow or lose
    # digits. In both cases only rounding remains: ~10 operations, rel 4e-15.
    v0 = 20.0
    v_t = qr.terminal_speed(m, c, G)
    assert math.isinf(v_t) == (c == 0)  # the finite-v_t path really is exercised for c > 0
    f = qr.vertical_flight(v0, h, v_t, G)
    t_vac = (v0 + math.sqrt(v0**2 + 2 * G * h)) / G
    assert f.apex_time == rel_approx(v0 / G, rel=4e-15)
    assert f.max_height == rel_approx(h + v0**2 / (2 * G), rel=4e-15)
    assert f.flight_time == rel_approx(t_vac, rel=4e-15)
    assert f.impact_speed == rel_approx(math.sqrt(v0**2 + 2 * G * h), rel=4e-15)


@pytest.mark.parametrize("v_t", [math.inf, 1e12])
def test_rise_and_fall_curves_tend_to_the_vacuum_curves(v_t: float) -> None:
    v0, h = 20.0, 3.0
    t = np.linspace(0.0, v0 / G, 25)  # the vacuum rise; for v_t = 1e12 it ends just short
    t = t[t <= qr.apex_time(v0, v_t, G)]
    # Drag corrections are O((v0/v_t)^2) <= 4e-22 relative. What remains is rounding in
    # differences of terms of size v0 (or v0 t): a few ulps, so atol = 1e-14 * scale.
    np.testing.assert_allclose(qr.rise_velocity(t, v0, v_t, G), v0 - G * t, rtol=0, atol=1e-14 * v0)
    np.testing.assert_allclose(
        qr.rise_height(t, v0, h, v_t, G), h + v0 * t - G * t**2 / 2, rtol=0, atol=1e-14 * 30
    )
    np.testing.assert_allclose(qr.fall_speed(t, v_t, G), G * t, rtol=4 * EPS)
    np.testing.assert_allclose(qr.fall_distance(t, v_t, G), G * t**2 / 2, rtol=4 * EPS)


# --- Cancellation-prone forms against 50-digit decimal ----------------------------------

WEAK = [(20.0, 2e5), (20.0, 2e8)]  # (v0, v_t): r = 1e-4 and 1e-7


@pytest.mark.parametrize(("v0", "v_t"), [*WEAK, (30.0, 20.0), (500.0, 2.0)])
def test_apex_time_and_height_match_50_digit_reference(v0: float, v_t: float) -> None:
    # A handful of correctly rounded operations (<= 1.1e-16 each) with no subtraction: <=1e-15.
    assert qr.apex_time(v0, v_t, G) == rel_approx(ref_apex_time(v0, v_t, G), rel=2e-15)
    assert qr.apex_height(v0, v_t, G) == rel_approx(ref_apex_height(v0, v_t, G), rel=2e-15)


def test_naive_apex_height_loses_digits_for_weak_drag() -> None:
    """The problem being avoided: ln(1 + r^2) rounds 1 + r^2 first (relative error eps/r^2)."""
    v0, v_t = 20.0, 2e5
    naive = v_t**2 / (2 * G) * math.log(1 + (v0 / v_t) ** 2)
    reference = ref_apex_height(v0, v_t, G)
    # Rounding 1 + r^2 (r = 1e-4) can cost up to eps / r^2 ~ 2.2e-8 relative; asserting > 1e-10
    # (50000x the stable form's tolerance) shows the loss without relying on the exact rounding.
    assert abs(naive - reference) / reference > 1e-10
    assert qr.apex_height(v0, v_t, G) == rel_approx(reference, rel=2e-15)


@pytest.mark.parametrize(("v0", "v_t"), [*WEAK, (30.0, 20.0)])
@pytest.mark.parametrize("fraction", [0.1, 0.5, 1.0])
def test_rise_height_matches_50_digit_reference(v0: float, v_t: float, fraction: float) -> None:
    h = 1.5
    t = fraction * qr.apex_time(v0, v_t, G)
    # y - h is v0 t - g t^2/2 up to drag corrections: the subtraction has condition <= 3 at
    # these times, on top of ~10 roundings, so <= ~3e-15 relative; tolerance 6e-15.
    got = qr.rise_height(np.array([t]), v0, h, v_t, G)[0] - h
    assert got == rel_approx(ref_rise_height(t, v0, h, v_t, G) - h, rel=6e-15)


# (drop, v_t): weak drag X = g Y / v_t^2 of 1e-12 and 2e-7; strong drag X ~ 1e3 and 1e6,
# where the plan's sqrt(expm1(2X)) form overflows (2X > 709.8).
FALLS = [(10.0, 9.9e6), (10.0, 7.0e3), (12.0, 20.0), (1.0e5, 1.0), (1.0e5, 0.99)]
FALLS += [(1.0e5, 0.0313)]  # X ~ 1e9


@pytest.mark.parametrize(("drop", "v_t"), FALLS)
def test_fall_time_and_impact_speed_match_50_digit_reference(drop: float, v_t: float) -> None:
    # Positive terms only (X + log1p(...), a sqrt, an expm1): ~8 roundings, <= 1e-15;
    # 4e-15 leaves a margin.
    assert qr.fall_time(drop, v_t, G) == rel_approx(ref_fall_time(drop, v_t, G), rel=4e-15)
    assert qr.fall_impact_speed(drop, v_t, G) == rel_approx(
        ref_impact_speed(drop, v_t, G), rel=4e-15
    )


def test_plan_form_of_the_fall_time_overflows_for_strong_drag() -> None:
    """Why the code does not use tau asinh(sqrt(expm1(2X))): it overflows once 2X > 709.8."""
    with pytest.raises(OverflowError):
        math.asinh(math.sqrt(math.expm1(2 * 1e3)))
    assert math.isfinite(qr.fall_time(1e5, 1.0, G))  # X ~ 1e6


@pytest.mark.parametrize("v_t", [9.9e6, 7.0e3, 20.0, 1.0])
@pytest.mark.parametrize("u", [1e-6, 0.3, 1.0, 5.0, 1e3, 1e6])
def test_fall_distance_matches_50_digit_reference(v_t: float, u: float) -> None:
    # u = t/tau. ln cosh u ~ u^2/2 for small u: computing ln(cosh u) directly would cancel.
    # Each branch is a few roundings of positive terms (the large-u branch subtracts ln 2
    # from u >= 1, condition <= 3.3): <= ~2e-15; tolerance 6e-15.
    t = u * v_t / G
    assert qr.fall_distance(np.array([t]), v_t, G)[0] == rel_approx(
        ref_fall_distance(t, v_t, G), rel=6e-15
    )


# --- R6: the hodograph invariant --------------------------------------------------------


def _quadratic_drag(vx: float, vy: float, v_t: float) -> tuple[float, float]:
    kappa = G / v_t**2
    v = math.hypot(vx, vy)
    return -kappa * v * vx, -G - kappa * v * vy


def _wrong_coupling(vx: float, vy: float, v_t: float) -> tuple[float, float]:
    kappa = G / v_t**2  # the classic bug: each component dragged by its own speed
    return -kappa * abs(vx) * vx, -G - kappa * abs(vy) * vy


def _invariant_rate(
    force: Callable[[float, float, float], tuple[float, float]], vx: float, vy: float, v_t: float
) -> tuple[float, float, float]:
    """dI/dt along the given force, by central differences in velocity space.

    Returns (rate, scale, allowed): scale is |dI/dvx ax| + |dI/dvy ay|, the size of the two
    terms that must cancel; allowed is the error budget of the finite differences:
    - truncation: I's terms vary on the scale vx (1/vx^2, asinh(vy/vx)), so with the step
      dv = 1e-6 vx the relative error of each partial derivative is ~2 (dv/vx)^2 = 2e-12;
      budget 1e-11 of the scale;
    - rounding: each evaluation of I is ~8 operations on terms of total size M, so it is
      off by <= 8 eps M, and each partial derivative by <= 8 eps M / dv.
    """

    def inv(a: float, b: float) -> float:
        return float(qr.hodograph_invariant(np.array([a]), np.array([b]), v_t, G)[0])

    dv = 1e-6 * vx
    di_dvx = (inv(vx + dv, vy) - inv(vx - dv, vy)) / (2 * dv)
    di_dvy = (inv(vx, vy + dv) - inv(vx, vy - dv)) / (2 * dv)
    ax, ay = force(vx, vy, v_t)
    scale = abs(di_dvx * ax) + abs(di_dvy * ay)
    m = 1 / vx**2 + (abs(math.hypot(vx, vy) * vy) / vx**2 + abs(math.asinh(vy / vx))) / v_t**2
    allowed = 1e-11 * scale + 8 * EPS * m * (abs(ax) + abs(ay)) / dv
    return di_dvx * ax + di_dvy * ay, scale, allowed


STATES = [(vx, vy) for vx in (0.5, 5.0, 30.0) for vy in (-40.0, -5.0, 0.0, 5.0, 40.0)]


@pytest.mark.parametrize(("vx", "vy"), STATES)
def test_hodograph_invariant_is_constant_along_quadratic_drag(vx: float, vy: float) -> None:
    rate, scale, allowed = _invariant_rate(_quadratic_drag, vx, vy, 20.0)
    assert allowed < 1e-6 * scale  # the budget is small enough for the check to mean something
    assert abs(rate) < allowed


@pytest.mark.parametrize(("vx", "vy"), [(5.0, 40.0), (30.0, -5.0), (5.0, -40.0)])
def test_hodograph_invariant_catches_the_wrong_coupling(vx: float, vy: float) -> None:
    # With -kappa |vx| vx and -kappa |vy| vy the invariant drifts at a rate comparable to
    # its terms (measured 0.2 to 0.8 of the scale here), so 1e-2 of the scale is a safe floor
    # and lies far above the error budget of the test above.
    rate, scale, allowed = _invariant_rate(_wrong_coupling, vx, vy, 20.0)
    assert abs(rate) > 1e-2 * scale > 1e3 * allowed


def test_hodograph_invariant_in_vacuum_is_one_over_vx_squared() -> None:
    vx, vy = np.array([3.0, 3.0]), np.array([10.0, -50.0])
    np.testing.assert_allclose(qr.hodograph_invariant(vx, vy, math.inf, G), 1 / 9.0, rtol=EPS)


def test_hodograph_invariant_needs_finite_velocity_and_positive_vx() -> None:
    with pytest.raises(ValueError, match="vx must be positive"):
        qr.hodograph_invariant(np.array([0.0]), np.array([1.0]), 20.0, G)
    with pytest.raises(ValueError, match="must be finite"):
        qr.hodograph_invariant(np.array([1.0]), np.array([math.nan]), 20.0, G)


# --- R7: speed and flight-time bounds ---------------------------------------------------


def test_speed_bound_is_the_larger_of_launch_and_terminal_speed() -> None:
    assert qr.speed_bound(30.0, 20.0) == 30.0
    assert qr.speed_bound(5.0, 20.0) == 20.0
    assert qr.speed_bound(5.0, math.inf) == math.inf  # no bound in vacuum


def test_speed_decreases_whenever_it_exceeds_terminal_speed() -> None:
    """The step in the proof of R7(i): d(v^2/2)/dt = v . a < 0 whenever |v| > v_t."""
    v_t = 20.0
    for speed in (20.001, 25.0, 100.0, 1e4):
        for angle in np.linspace(-math.pi / 2, math.pi / 2, 181):
            vx, vy = speed * math.cos(angle), speed * math.sin(angle)
            ax, ay = _quadratic_drag(vx, vy, v_t)
            assert vx * ax + vy * ay < 0


@pytest.mark.parametrize(("v0", "v_t"), [(30.0, 20.0), (5.0, 20.0)])
def test_exact_vertical_speeds_respect_the_speed_bound(v0: float, v_t: float) -> None:
    f = qr.vertical_flight(v0, 10.0, v_t, G)
    rise = qr.rise_velocity(np.linspace(0, f.apex_time, 200), v0, v_t, G)
    fall = qr.fall_speed(np.linspace(0, f.fall_time, 200), v_t, G)
    bound = qr.speed_bound(v0, v_t)
    assert np.all(np.abs(rise) <= bound * (1 + 2 * EPS))  # equality at launch, to rounding
    assert np.all(fall <= bound)


@pytest.mark.parametrize(
    ("angle", "h"), [(0.0, 25.0), (20.0, 0.0), (20.0, 25.0), (45.0, 0.0), (90.0, 0.0), (90.0, 25.0)]
)
def test_flight_time_bound_is_exact_in_vacuum(angle: float, h: float) -> None:
    v0 = 20.0
    theta = math.radians(angle)
    vy0 = v0 * math.sin(theta)
    expected = (vy0 + math.sqrt(vy0**2 + 2 * G * h)) / G  # textbook vacuum flight time
    # In vacuum every step of the proof is an equality. Linear-drag fall with k = 0 is solved
    # by Brent to 4 eps; plus a few roundings: rel 1e-14.
    got = qr.flight_time_bound(v0, theta, h, math.inf, G)
    assert got == rel_approx(expected, rel=1e-14)


def _linear_drag_fall_time(drop: float, k: float) -> float:
    """50-digit bisection for the time to fall ``drop`` from rest with linear drag rate k:
    d(T) = (g/k) T - (g/k^2)(1 - e^(-kT)) = drop. d is increasing, and d(T) >= (g/k)(T - 1/k)
    puts the root below drop k/g + 1/k."""
    with _Fifty():
        dk, dg, dy = _dec(k), _dec(G), _dec(drop)
        lo, hi = Decimal(0), dy * dk / dg + 1 / dk
        for _ in range(200):  # 2^-200 of the bracket: far below 50 digits of the root
            mid = (lo + hi) / 2
            if dg / dk * mid - dg / (dk * dk) * (1 - (-dk * mid).exp()) < dy:
                lo = mid
            else:
                hi = mid
        return float((lo + hi) / 2)


@pytest.mark.parametrize(
    ("v0", "angle", "h", "v_t"),
    [
        (1e3, 60.0, 0.0, 30.0),
        (100.0, 30.0, 10.0, 20.0),
        (5.0, 0.0, 50.0, 8.0),
        (30.0, 90.0, 0.0, 3.0),
    ],
)
def test_flight_time_bound_is_the_proved_formula(
    v0: float, angle: float, h: float, v_t: float
) -> None:
    """The bound's value, rebuilt from the proof: vy0/g plus the linear-drag fall from rest
    through h + vy0^2/2g with k = (g/v_t^2) max(v0, v_t). The 'holds' checks cannot see a
    smaller k (for example V = v_t when v0 > v_t): the bound is so loose it still holds,
    but it is no longer proved."""
    theta = math.radians(angle)
    vy0 = v0 * math.sin(theta)
    k = G / v_t**2 * max(v0, v_t)
    expected = vy0 / G + _linear_drag_fall_time(h + vy0**2 / (2 * G), k)
    # The code solves the same fall with Brent's method to rtol = 4 eps (8.9e-16), plus a few
    # roundings in k and the height: measured <= 3.4e-16 here, so rel 1e-14 is a wide margin,
    # while the smaller-k mutant above moves the bound by factors, not ulps.
    assert qr.flight_time_bound(v0, theta, h, v_t, G) == rel_approx(expected, rel=1e-14)


@pytest.mark.parametrize(
    ("v0", "h", "v_t"), [(30.0, 0.0, 20.0), (5.0, 40.0, 20.0), (1e3, 0.0, 30.0)]
)
def test_flight_time_bound_holds_for_exact_vertical_flights(
    v0: float, h: float, v_t: float
) -> None:
    # The proved bound against the exact R3 flight time: a strict inequality (the bound is
    # loose by >= 10% in these cases, measured, far above rounding; at v0 = 1e3 m/s,
    # v_t = 30 m/s it is ~3000x the flight time).
    exact = qr.vertical_flight(v0, h, v_t, G).flight_time
    assert exact < qr.flight_time_bound(v0, math.pi / 2, h, v_t, G)


def _two_d_flight(v0: float, theta: float, h: float, v_t: float) -> tuple[float, float]:
    """Test-local reference: SciPy DOP853 at rtol = atol = 1e-12. Returns the flight time
    and the largest speed seen on a dense grid."""

    def rhs(_t: float, s: np.ndarray) -> list[float]:
        ax, ay = _quadratic_drag(s[2], s[3], v_t)
        return [s[2], s[3], ax, ay]

    def landing(_t: float, s: np.ndarray) -> float:
        return float(s[1])

    landing.terminal = True  # type: ignore[attr-defined]
    landing.direction = -1  # type: ignore[attr-defined]
    t_end = 2 * qr.flight_time_bound(v0, theta, h, v_t, G)
    sol = solve_ivp(
        rhs,
        (0.0, t_end),
        [0.0, h, v0 * math.cos(theta), v0 * math.sin(theta)],
        method="DOP853",
        rtol=1e-12,
        atol=1e-12,
        events=landing,
        dense_output=True,
    )
    assert sol.status == 1, "did not land before twice the bound"
    t_land = float(sol.t_events[0][0])
    states = sol.sol(np.linspace(0.0, t_land, 2001))
    return t_land, float(np.max(np.hypot(states[2], states[3])))


@pytest.mark.parametrize(
    ("v0", "angle", "h", "v_t"),
    [
        (20.0, 45.0, 0.0, 20.0),
        (100.0, 30.0, 10.0, 20.0),
        (1e3, 60.0, 0.0, 30.0),
        (5.0, 0.0, 50.0, 8.0),
    ],
)
def test_bounds_hold_for_two_d_flights(v0: float, angle: float, h: float, v_t: float) -> None:
    theta = math.radians(angle)
    t_land, max_speed = _two_d_flight(v0, theta, h, v_t)
    # The reference's own error is ~1e-10 relative (rtol = 1e-12 on a smooth flight of a few
    # hundred steps); the flight-time bound is loose by >= 2.8% here (measured), so a strict
    # check is safe.
    assert t_land < qr.flight_time_bound(v0, theta, h, v_t, G)
    # The speed reaches the bound only at launch (v0 = V) or asymptotically (V = v_t):
    # allow the reference's error, 1e-9 relative.
    assert max_speed <= qr.speed_bound(v0, v_t) * (1 + 1e-9)


# --- Inputs are validated -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("func", "args"),
    [
        (qr.terminal_speed, (math.nan, 0.1, G)),
        (qr.terminal_speed, (1.0, math.inf, G)),
        (qr.terminal_speed, (1.0, -0.1, G)),
        (qr.terminal_speed, (0.0, 0.1, G)),
        (qr.apex_time, (math.inf, 20.0, G)),
        (qr.apex_height, (20.0, math.nan, G)),
        (qr.apex_height, (20.0, 0.0, G)),
        (qr.fall_time, (-1.0, 20.0, G)),
        (qr.fall_impact_speed, (10.0, 20.0, 0.0)),
        (qr.vertical_flight, (20.0, math.nan, 20.0, G)),
        (qr.flight_time_bound, (20.0, 2.0, 0.0, 20.0, G)),  # angle above pi/2
    ],
)
def test_rejects_non_finite_and_out_of_domain_scalars(
    func: Callable[..., object], args: tuple[float, ...]
) -> None:
    with pytest.raises(ValueError, match="must be"):
        func(*args)


def test_rejects_times_outside_the_rise() -> None:
    t_a = qr.apex_time(30.0, 20.0, G)
    for bad in (np.array([-1e-3]), np.array([t_a * 1.01]), np.array([math.nan])):
        with pytest.raises(ValueError, match="must be"):
            qr.rise_velocity(bad, 30.0, 20.0, G)
    with pytest.raises(ValueError, match="must be"):
        qr.fall_speed(np.array([math.inf]), 20.0, G)
