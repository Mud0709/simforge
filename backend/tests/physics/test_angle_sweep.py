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
from simforge.physics.projectile.analytical import ProjectileSetup, flight_time, state

G = 9.80665
GRID = list(np.linspace(0.0, 90.0, 91))


def setup(v0: float = 20.0, h: float = 0.0, b: float = 0.0, m: float = 1.0) -> ProjectileSetup:
    # The launch angle is irrelevant here: the sweep replaces it.
    return ProjectileSetup(v0, math.radians(45.0), h, m, b, G)


# --- Vacuum: exact references ---------------------------------------------------------


def test_vacuum_from_ground_is_optimal_at_45_degrees() -> None:
    result = angle_sweep.sweep(setup(), GRID)
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
def test_refined_optimum_beats_every_grid_point_and_is_a_true_maximum(b: float) -> None:
    result = angle_sweep.sweep(setup(b=b), GRID)
    assert result.best_range >= max(p.range for p in result.points)
    # Small steps either side must not do better.
    for d in (1e-3, -1e-3):
        assert (
            angle_sweep.evaluate(setup(b=b), result.best_angle_deg + d).range <= result.best_range
        )


def test_sweep_points_match_the_exact_solution() -> None:
    s = setup(b=0.7, h=3.0)
    point = angle_sweep.evaluate(s, 37.0)
    s37 = angle_sweep.with_angle(s, 37.0)
    t = flight_time(s37)
    x, _, _, _ = state(s37, np.array([t]))
    assert point.flight_time == t
    assert point.range == float(x[0])


def test_drag_never_increases_the_maximum_range() -> None:
    for b in DRAGS:
        result = angle_sweep.sweep(setup(b=b, h=4.0), GRID)
        assert result.best_range < result.vacuum_best_range


# --- Edge cases -----------------------------------------------------------------------------


def test_zero_angle_from_ground_has_zero_range() -> None:
    assert angle_sweep.evaluate(setup(), 0.0).range == 0.0


def test_vertical_launch_has_negligible_range() -> None:
    assert abs(angle_sweep.evaluate(setup(b=0.5), 90.0).range) < 1e-12


def test_optimum_on_a_coarse_grid_is_still_found() -> None:
    result = angle_sweep.sweep(setup(b=1.0), [0.0, 30.0, 60.0, 90.0])
    fine = angle_sweep.sweep(setup(b=1.0), GRID)
    assert result.best_angle_deg == pytest.approx(fine.best_angle_deg, abs=1e-5)


def test_too_few_angles_rejected() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        angle_sweep.sweep(setup(), [10.0, 20.0])
