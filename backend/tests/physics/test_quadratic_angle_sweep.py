"""Tests of the quadratic-drag angle sweep (roadmap 2.2). Slice 1: the vacuum references (RS1).

With no drag, the range at angle theta from height h is
R(theta) = v0 cos theta (v0 sin theta + sqrt(v0^2 sin^2 theta + 2 g h)) / g, and its maximum
is at tan theta* = v0 / sqrt(v0^2 + 2 g h) with R* = (v0/g) sqrt(v0^2 + 2 g h). Expected
values come from independent sources: the textbook forms v0^2 sin 2 theta / g and
v0 sqrt(2h/g), hand-worked cases with exact numbers, central differences of the range (the
best angle is where the slope vanishes and the curve bends down), and the linear-drag model's
exact solution at b = 0 (a different code path: a root-found landing time in ``analytical``).
"""

from __future__ import annotations

import itertools
import math

import pytest

from simforge.physics.projectile import angle_sweep
from simforge.physics.projectile import quadratic_angle_sweep as qas
from simforge.physics.projectile.analytical import ProjectileSetup
from tests.approx import rel_approx

G = 9.80665
EPS = 2.0**-52  # 2.2e-16


# --- Range at one angle --------------------------------------------------------------------


@pytest.mark.parametrize("angle", [15.0, 30.0, 45.0, 60.0, 75.0])
def test_range_from_the_ground_is_the_textbook_formula(angle: float) -> None:
    # R = v0^2 sin(2 theta) / g. Both sides are a few rounded operations; rounding of theta in
    # radians is amplified in sin(2 theta) by at most |2 theta cot 2 theta| ~ 2.3 (75 degrees),
    # so they agree to well under 1e-14 relative.
    v0 = 20.0
    expected = v0**2 * math.sin(2 * math.radians(angle)) / G
    assert qas.vacuum_range(v0, angle, 0.0, G) == rel_approx(expected, rel=1e-14)


def test_hand_worked_range_from_a_height() -> None:
    # v0 = 10 m/s, g = 10 m/s^2, h = 15 m, theta = 30 degrees: v0 sin = 5, v0 cos = 5 sqrt 3,
    # sqrt(25 + 300) = 5 sqrt 13, so R = 5 sqrt 3 (5 + 5 sqrt 13) / 10 = 2.5 sqrt 3 (1 + sqrt 13)
    # = 19.9431... m. A few rounded operations either way: 1e-14 relative.
    expected = 2.5 * math.sqrt(3.0) * (1 + math.sqrt(13.0))
    assert qas.vacuum_range(10.0, 30.0, 15.0, 10.0) == rel_approx(expected, rel=1e-14)


@pytest.mark.parametrize("h", [0.5, 3.0, 40.0])
def test_horizontal_launch_from_a_height(h: float) -> None:
    # theta = 0: the ball falls h in sqrt(2h/g) while moving at v0, so R = v0 sqrt(2h/g).
    v0 = 20.0
    assert qas.vacuum_range(v0, 0.0, h, G) == rel_approx(v0 * math.sqrt(2 * h / G), rel=1e-15)


def test_special_angles_give_exactly_zero_range() -> None:
    # 0 degrees from the ground: no flight. 90 degrees: straight up and down, exactly 0 (as the
    # 2.1 model treats 90 degrees as exactly vertical; cos(radians(90)) = 6.1e-17 is not 0).
    assert qas.vacuum_range(20.0, 0.0, 0.0, G) == 0.0
    assert qas.vacuum_range(20.0, 90.0, 0.0, G) == 0.0
    assert qas.vacuum_range(1e4, 90.0, 1e5, G) == 0.0


@pytest.mark.parametrize(("angle", "h"), [(10.0, 0.0), (37.0, 3.0), (60.0, 25.0), (85.0, 1e3)])
def test_range_matches_the_linear_drag_model_without_drag(angle: float, h: float) -> None:
    # Independent code path: x(T) with T root-found (brentq, rtol 4 eps) from the exact y(t).
    # T's error (<= ~4 eps relative) passes straight into x = vx0 T; 1e-14 leaves room for it
    # and the rounding of each side.
    v0 = 20.0
    linear = angle_sweep.evaluate(ProjectileSetup(v0, 0.0, h, 1.0, 0.0, G), angle).range
    assert qas.vacuum_range(v0, angle, h, G) == rel_approx(linear, rel=1e-14)


# --- The best angle and range --------------------------------------------------------------


@pytest.mark.parametrize("v0", [0.5, 20.0, 1e4])
def test_best_from_the_ground_is_45_degrees_and_v0_squared_over_g(v0: float) -> None:
    angle, best = qas.vacuum_optimum(v0, 0.0, G)
    # 45 degrees and v0^2/g, each one or two rounded operations away: 2 eps relative.
    assert angle == rel_approx(45.0, rel=2 * EPS)
    assert best == rel_approx(v0**2 / G, rel=2 * EPS)


def test_hand_worked_best_from_a_height() -> None:
    # v0 = 10 m/s, g = 10 m/s^2, h = 15 m: v0^2 + 2gh = 400, so tan theta* = 10/20 = 1/2,
    # theta* = atan(1/2) = 26.565051177077989... degrees (a standard value), and
    # R* = (10/10) x 20 = 20 m exactly. At that angle cos = 2/sqrt 5 and sin = 1/sqrt 5, so
    # by hand R(theta*) = (20/sqrt 5)(10/sqrt 5) / 10 = 20 m too.
    angle, best = qas.vacuum_optimum(10.0, 15.0, 10.0)
    assert angle == rel_approx(26.565051177077989, rel=2 * EPS)
    assert best == rel_approx(20.0, rel=2 * EPS)
    # The range function evaluated at that angle agrees (a few rounded operations).
    assert qas.vacuum_range(10.0, angle, 15.0, 10.0) == rel_approx(20.0, rel=1e-14)


def test_best_angle_falls_below_45_degrees_from_a_height() -> None:
    angles = [qas.vacuum_optimum(20.0, h, G)[0] for h in [0.0, 1.0, 10.0, 100.0, 1e4]]
    assert angles[0] == rel_approx(45.0, rel=2 * EPS)
    assert all(a > b for a, b in itertools.pairwise(angles))


@pytest.mark.parametrize(("v0", "h"), [(20.0, 0.0), (20.0, 10.0), (20.0, 200.0), (3.0, 50.0)])
def test_range_slope_vanishes_and_curve_bends_down_at_the_best_angle(v0: float, h: float) -> None:
    angle, best = qas.vacuum_optimum(v0, h, G)

    def r(a: float) -> float:
        return qas.vacuum_range(v0, a, h, G)

    # Central difference in degrees with step d = 1e-4 degrees. Rounding: |R| eps / d per
    # degree; truncation |R'''| d^2 / 6 with |R'''| <= ~8 R* rad^-3 (sin 2 theta's bound;
    # measured below that for these heights) = 8 R* (pi/180)^3 per degree^3, i.e. ~7e-14 R*
    # per degree. An angle error of delta degrees shows as a slope of K delta, where
    # K = |R''| ~ 4 R* (pi/180)^2 ~ 1.2e-3 R* per degree^2 (the h = 0 value; similar here), so
    # a tolerance of 1e-10 R* per degree catches errors in theta* above ~1e-7 degrees.
    d = 1e-4
    slope = (r(angle + d) - r(angle - d)) / (2 * d)
    rounding = 4 * best * EPS / d
    assert abs(slope) <= 1e-10 * best + rounding
    # A maximum, not a minimum: 0.1 degree either side gives a smaller range (by ~6e-6 R*).
    assert r(angle - 0.1) < best
    assert r(angle + 0.1) < best
    # And the stated best range is the range at the stated best angle.
    assert r(angle) == rel_approx(best, rel=1e-14)


def test_best_matches_the_linear_drag_model_without_drag() -> None:
    # The linear sweep's exact-range curve, refined by Brent at b = 0, is an independent
    # search (angle_sweep.sweep): its best angle is good to ~1e-6 degrees (Brent's limit;
    # the peak is flat) and its best range to rounding.
    for h in [0.0, 5.0, 50.0]:
        linear = angle_sweep.sweep(
            ProjectileSetup(20.0, 0.0, h, 1.0, 0.0, G), [i * 1.0 for i in range(91)]
        )
        angle, best = qas.vacuum_optimum(20.0, h, G)
        assert angle == pytest.approx(linear.best_angle_deg, abs=1e-5)
        assert best == rel_approx(linear.best_range, rel=1e-12)


# --- Input checks --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        (math.nan, 45.0, 0.0, G),
        (math.inf, 45.0, 0.0, G),
        (-1.0, 45.0, 0.0, G),
        (20.0, math.nan, 0.0, G),
        (20.0, -1.0, 0.0, G),
        (20.0, 90.5, 0.0, G),
        (20.0, 45.0, -1.0, G),
        (20.0, 45.0, math.inf, G),
        (20.0, 45.0, 0.0, 0.0),
        (20.0, 45.0, 0.0, math.nan),
    ],
)
def test_vacuum_range_rejects_bad_inputs(args: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match="must be"):
        qas.vacuum_range(*args)


@pytest.mark.parametrize(
    "args",
    [(math.nan, 0.0, G), (-1.0, 0.0, G), (20.0, -1.0, G), (20.0, math.nan, G), (20.0, 0.0, 0.0)],
)
def test_vacuum_optimum_rejects_bad_inputs(args: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError, match="must be"):
        qas.vacuum_optimum(*args)
