"""Reference tests for the closed-form solution.

Every expected value here comes from an *independent* source: a textbook vacuum formula,
a physical limit, or a 50-digit ``decimal`` evaluation — never from the code under test.
"""

from __future__ import annotations

import itertools
import math
from decimal import Decimal, getcontext

import numpy as np
import pytest

from simforge.physics.projectile import analytical
from simforge.physics.projectile.analytical import ProjectileSetup
from tests.approx import rel_approx

G = 9.80665


def setup(
    v0: float = 20.0, angle: float = 45.0, h: float = 0.0, m: float = 1.0, b: float = 0.0
) -> ProjectileSetup:
    return ProjectileSetup(v0, math.radians(angle), h, m, b, G)


def range_of(s: ProjectileSetup) -> float:
    x, _, _, _ = analytical.state(s, np.array([analytical.flight_time(s)]))
    return float(x[0])


# --- Auxiliary functions -------------------------------------------------------------


def _phi_decimal(u: float) -> float:
    getcontext().prec = 50
    d = Decimal(u)
    return float(((-d).exp() - 1 + d) / (d * d))


def _psi_decimal(u: float) -> float:
    getcontext().prec = 50
    d = Decimal(u)
    return float((1 - (-d).exp()) / d)


# Empirical bounds, not proofs: on dense grids (4001 log-spaced points in [1e-12, 100] and
# 20001 points in [0.1, 1], where the direct formula takes over) the worst errors measured
# were 1.63e-15 for phi and 2.2e-16 for psi (2026-10-21). The bounds leave a small margin.
PHI_REL, PSI_REL = 2e-15, 4e-16
DENSE_U = np.concatenate([np.geomspace(1e-12, 100, 1001), np.linspace(0.09, 1.1, 1001)])


def test_auxiliary_functions_match_50_digit_reference_on_a_dense_grid() -> None:
    phi, psi = analytical.phi(DENSE_U), analytical.psi(DENSE_U)
    for i, u in enumerate(DENSE_U):
        assert phi[i] == rel_approx(_phi_decimal(float(u)), rel=PHI_REL), u
        assert psi[i] == rel_approx(_psi_decimal(float(u)), rel=PSI_REL), u


def test_auxiliary_functions_vacuum_limit_is_exact() -> None:
    assert analytical.phi(np.array([0.0]))[0] == 0.5
    assert analytical.psi(np.array([0.0]))[0] == 1.0


# --- Vacuum: textbook formulas ---------------------------------------------------------


@pytest.mark.parametrize("angle", [5.0, 30.0, 45.0, 60.0, 89.0])
def test_vacuum_range_and_height_match_textbook(angle: float) -> None:
    s = setup(v0=20.0, angle=angle)
    theta = math.radians(angle)
    assert range_of(s) == rel_approx(20.0**2 * math.sin(2 * theta) / G, rel=1e-13)
    assert analytical.flight_time(s) == rel_approx(2 * 20.0 * math.sin(theta) / G, rel=1e-14)
    _, y, _, _ = analytical.state(s, np.array([analytical.apex_time(s)]))
    assert y[0] == rel_approx((20.0 * math.sin(theta)) ** 2 / (2 * G), rel=1e-14)


def test_vacuum_complementary_angles_have_equal_range() -> None:
    assert range_of(setup(angle=30.0)) == rel_approx(range_of(setup(angle=60.0)), rel=1e-13)


def test_vacuum_45_degrees_maximises_range_from_ground() -> None:
    r45 = range_of(setup(angle=45.0))
    assert r45 > range_of(setup(angle=44.5))
    assert r45 > range_of(setup(angle=45.5))


def test_vacuum_launch_from_height_matches_quadratic_formula() -> None:
    v0, theta, h = 15.0, math.radians(20.0), 12.0
    vy0 = v0 * math.sin(theta)
    expected_t = (vy0 + math.sqrt(vy0**2 + 2 * G * h)) / G
    assert analytical.flight_time(setup(v0=15.0, angle=20.0, h=12.0)) == rel_approx(
        expected_t, rel=1e-14
    )


# --- Linear drag -------------------------------------------------------------------------


def test_initial_conditions_are_satisfied_with_drag() -> None:
    s = setup(v0=30.0, angle=35.0, h=4.0, b=0.7, m=2.0)
    x, y, vx, vy = analytical.state(s, np.array([0.0]))
    assert (x[0], y[0], vx[0], vy[0]) == (0.0, 4.0, s.vx0, s.vy0)


def test_closed_form_satisfies_equations_of_motion() -> None:
    """Central differences of the exact velocity must reproduce the force law."""
    s = setup(v0=30.0, angle=35.0, h=4.0, b=0.7, m=2.0)
    t = np.linspace(0.1, 3.0, 30)
    dt = 1e-5
    _, _, vx_p, vy_p = analytical.state(s, t + dt)
    _, _, vx_m, vy_m = analytical.state(s, t - dt)
    _, _, vx, vy = analytical.state(s, t)
    np.testing.assert_allclose((vx_p - vx_m) / (2 * dt), -s.k * vx, rtol=1e-8)
    np.testing.assert_allclose((vy_p - vy_m) / (2 * dt), -G - s.k * vy, rtol=1e-8)


@pytest.mark.parametrize(
    ("b", "h", "angle"), [(0.05, 0.0, 45.0), (0.5, 0.0, 70.0), (2.0, 10.0, 30.0), (5.0, 3.0, 0.0)]
)
def test_flight_time_matches_lambert_w_closed_form(b: float, h: float, angle: float) -> None:
    s = setup(v0=25.0, angle=angle, h=h, b=b)
    assert analytical.flight_time(s) == rel_approx(analytical.flight_time_lambert_w(s), rel=1e-12)


def test_weak_drag_converges_to_vacuum() -> None:
    vacuum, weak = setup(b=0.0), setup(b=1e-12)
    assert range_of(weak) == rel_approx(range_of(vacuum), rel=1e-10)
    assert range_of(weak) < range_of(vacuum)


def test_stable_form_avoids_catastrophic_cancellation() -> None:
    """The textbook drag formula loses most significant digits for weak drag; ours must not.

    y(t) = tau (vy0 + v_t)(1 - e^{-t/tau}) - v_t t  subtracts two numbers of size ~v_t t
    (here ~1e10 m) to produce a result of ~10 m, so float64 rounding of ~1e-6 m in each
    term survives as a ~1e-7 relative error. The reference is evaluated with 50 digits.
    """
    s = setup(b=1e-9)
    t = 1.0
    getcontext().prec = 50
    k, vy0, g = Decimal(s.k), Decimal(s.vy0), Decimal(G)
    tau, vt = 1 / k, g / k
    reference = float(tau * (vy0 + vt) * (1 - (-k).exp()) - vt)

    tau_f, vt_f = 1 / s.k, s.terminal_speed
    textbook = tau_f * (s.vy0 + vt_f) * (-math.expm1(-t / tau_f)) - vt_f * t
    stable = float(analytical.state(s, np.array([t]))[1][0])

    assert stable == rel_approx(reference, rel=1e-14)
    assert abs(textbook - reference) / reference > 1e-9  # the problem being avoided


def test_range_decreases_monotonically_with_drag() -> None:
    ranges = [range_of(setup(b=b)) for b in [0.0, 0.01, 0.1, 0.5, 2.0]]
    assert all(a > b for a, b in itertools.pairwise(ranges))


def test_long_fall_approaches_terminal_velocity() -> None:
    s = setup(v0=1.0, angle=0.0, h=1e4, b=1.0, m=1.0)  # v_t = g / k = 9.80665 m/s
    t = analytical.flight_time(s)
    _, _, vx, vy = analytical.state(s, np.array([t]))
    assert s.k * t > 500  # many relaxation times: transient fully decayed
    assert vy[0] == rel_approx(-s.terminal_speed, rel=1e-12)
    assert abs(vx[0]) < 1e-200


def test_strong_drag_can_lengthen_flight_from_height() -> None:
    """Not a bug: drag lowers the apex but slows the descent even more."""
    assert analytical.flight_time(setup(h=3.0, b=5.0)) > analytical.flight_time(setup(h=3.0))
