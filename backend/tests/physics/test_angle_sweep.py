"""Range versus launch angle, and the optimal angle.

References: the textbook vacuum results (45 degrees, v^2/g, complementary angles), the
closed-form vacuum optimum from a height, and qualitative properties of linear drag
checked across several drag strengths.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from simforge.physics.projectile import angle_sweep
from simforge.physics.projectile.analytical import ProjectileSetup

G = 9.80665
GRID = list(np.linspace(0.0, 90.0, 91))


def setup(v0: float = 20.0, h: float = 0.0, b: float = 0.0, m: float = 1.0) -> ProjectileSetup:
    # The launch angle is irrelevant here: the sweep replaces it.
    return ProjectileSetup(v0, math.radians(45.0), h, m, b, G)


EPS = 2.0**-52


# --- Vacuum: exact references ---------------------------------------------------------


def test_vacuum_from_ground_is_optimal_at_45_degrees() -> None:
    # A 10-degree grid does not contain 45, so the answer must come from the Brent
    # refinement, not from a grid point. SciPy's bounded Brent stops within
    # sqrt(eps)|x| + xatol/3 ~ 7e-7 degrees near 45; 1e-6 allows for that. The range is flat
    # at the peak (error ~ angle error squared), so it still matches v^2/g to rounding.
    result = angle_sweep.sweep(setup(), list(np.linspace(0.0, 90.0, 10)))
    assert 45.0 not in [p.angle_deg for p in result.points]
    assert result.best_angle_deg == pytest.approx(45.0, abs=1e-6)
    assert result.best_range == pytest.approx(20.0**2 / G, rel=1e-12)


@pytest.mark.parametrize("h", [5.0, 10.0, 50.0, 200.0])
def test_vacuum_from_height_matches_closed_form(h: float) -> None:
    """tan(theta*) = v / sqrt(v^2 + 2gh) and R* = (v/g) sqrt(v^2 + 2gh)."""
    v = 20.0
    expected_angle = math.degrees(math.atan(v / math.sqrt(v * v + 2 * G * h)))
    expected_range = v * math.sqrt(v * v + 2 * G * h) / G
    result = angle_sweep.sweep(setup(v0=v, h=h), GRID)
    # The range is known almost exactly; the angle less so, because the peak is flat.
    assert result.best_range == pytest.approx(expected_range, rel=1e-12)
    assert result.best_angle_deg == pytest.approx(expected_angle, abs=1e-5)
    assert result.vacuum_best_angle_deg == pytest.approx(expected_angle, abs=1e-12)
    assert result.vacuum_best_range == pytest.approx(expected_range, rel=1e-14)


@pytest.mark.parametrize("angle", [15.0, 30.0, 40.0])
def test_vacuum_complementary_angles_have_equal_range(angle: float) -> None:
    a = angle_sweep.evaluate(setup(), angle)
    b = angle_sweep.evaluate(setup(), 90.0 - angle)
    assert a.range == pytest.approx(b.range, rel=1e-12)


def test_vacuum_peak_is_lower_than_45_degrees_when_launched_from_height() -> None:
    assert angle_sweep.sweep(setup(h=10.0), GRID).best_angle_deg < 45.0


# --- Linear drag: properties --------------------------------------------------------------

DRAGS = [0.01, 0.1, 0.5, 1.0, 3.0]


def test_drag_lowers_the_best_angle_monotonically() -> None:
    angles = [angle_sweep.sweep(setup(b=b), GRID).best_angle_deg for b in DRAGS]
    assert all(a < 45.0 for a in angles)
    assert all(x > y for x, y in itertools.pairwise(angles))


def test_weak_drag_tends_to_vacuum_optimum() -> None:
    result = angle_sweep.sweep(setup(b=1e-6), GRID)
    assert result.best_angle_deg == pytest.approx(45.0, abs=1e-3)
    assert result.best_range == pytest.approx(20.0**2 / G, rel=1e-5)


@pytest.mark.parametrize("b", DRAGS)
def test_range_curve_has_a_single_peak(b: float) -> None:
    """The refinement assumes one maximum; check it on a fine grid."""
    ranges = [angle_sweep.evaluate(setup(b=b), a).range for a in np.arange(0.0, 90.25, 0.25)]
    peaks = [i for i in range(1, len(ranges) - 1) if ranges[i - 1] < ranges[i] > ranges[i + 1]]
    assert len(peaks) == 1


@pytest.mark.parametrize("b", DRAGS)
def test_optimum_agrees_with_an_independent_dense_scan(b: float) -> None:
    # Independent search method (a plain scan, not Brent) over the same range function,
    # which is itself checked against closed forms above. The scan steps (1e-6 degrees) are
    # finer than the error to catch: had the refinement stopped 1e-5 degrees from the peak,
    # some scan point would beat it by ~5e-14 R, far above rounding. Mutation-checked: a
    # reported angle shifted by +-1e-5 or 3e-5 degrees fails for every drag value below.
    result = angle_sweep.sweep(setup(b=b), GRID)
    scan = np.linspace(result.best_angle_deg - 1e-4, result.best_angle_deg + 1e-4, 201)
    best_scanned = max(angle_sweep.evaluate(setup(b=b), float(a)).range for a in scan)
    assert best_scanned <= result.best_range * (1 + 8 * EPS)


@pytest.mark.parametrize(("angle", "h"), [(37.0, 3.0), (60.0, 0.0), (10.0, 25.0)])
def test_vacuum_sweep_points_match_textbook_formulas(angle: float, h: float) -> None:
    # Independent reference: projectile motion without drag.
    v = 20.0
    vy = v * math.sin(math.radians(angle))
    point = angle_sweep.evaluate(setup(v0=v, h=h), angle)
    assert point.flight_time == pytest.approx((vy + math.sqrt(vy * vy + 2 * G * h)) / G, rel=1e-13)
    assert point.max_height == pytest.approx(h + vy * vy / (2 * G), rel=1e-13)


def test_drag_never_increases_the_maximum_range() -> None:
    for b in DRAGS:
        result = angle_sweep.sweep(setup(b=b, h=4.0), GRID)
        assert result.best_range < result.vacuum_best_range


# --- Edge cases -----------------------------------------------------------------------------


def test_zero_angle_from_ground_has_zero_range() -> None:
    assert angle_sweep.evaluate(setup(), 0.0).range == 0.0


def test_vertical_launch_has_zero_range() -> None:
    assert angle_sweep.evaluate(setup(b=0.5), 90.0).range == 0.0


def test_optimum_on_a_coarse_grid_is_still_found() -> None:
    result = angle_sweep.sweep(setup(b=1.0), [0.0, 30.0, 60.0, 90.0])
    fine = angle_sweep.sweep(setup(b=1.0), GRID)
    assert result.best_angle_deg == pytest.approx(fine.best_angle_deg, abs=1e-5)


def test_too_few_angles_rejected() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        angle_sweep.sweep(setup(), [10.0, 20.0])


def test_vertical_point_of_a_sweep_has_exactly_zero_range() -> None:
    # Large v0 T magnifies cos(pi/2) ~ 6e-17 into a visible fake range unless 90 is exact.
    s = ProjectileSetup(1e4, 0.0, 1e5, 1.0, 0.0, 0.01)
    assert angle_sweep.evaluate(s, 90.0).range == 0.0
