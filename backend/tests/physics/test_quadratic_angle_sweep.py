"""Tests of the quadratic-drag angle sweep (roadmap 2.2): the vacuum references (RS1, slice 1),
then the sweep core and its run (seams 2 and 3, slice 2; their references are stated below).

With no drag, the range at angle theta from height h is
R(theta) = v0 cos theta (v0 sin theta + sqrt(v0^2 sin^2 theta + 2 g h)) / g, and its maximum
is at tan theta* = v0 / sqrt(v0^2 + 2 g h) with R* = (v0/g) sqrt(v0^2 + 2 g h). Expected
values come from independent sources: the textbook forms v0^2 sin 2 theta / g and
v0 sqrt(2h/g), hand-worked cases with exact numbers, central differences of the range (the
best angle is where the slope vanishes and the curve bends down), and the linear-drag model's
exact solution at b = 0 (a different code path: a root-found landing time in ``analytical``).
"""

from __future__ import annotations

import dataclasses
import functools
import itertools
import math
from collections.abc import Callable
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.optimize import minimize_scalar

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import ValidationCheck
from simforge.physics.projectile import angle_sweep
from simforge.physics.projectile import quadratic_angle_sweep as qas
from simforge.physics.projectile import quadratic_model as qm
from simforge.physics.projectile import quadratic_numerical as qn
from simforge.physics.projectile.analytical import ProjectileSetup
from simforge.physics.projectile.quadratic_numerical import QuadraticSetup
from simforge.physics.projectile.schemas import SolverSettings
from tests.approx import rel_approx
from tests.physics import weak_drag_reference as wd

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


# ============================================================================================
# Slice 2, seam 2: the sweep core (``sweep``). One 2.1 run per angle, Brent refinement.
# ============================================================================================
#
# Shared cases: v0 = 20 m/s, m = 1 kg, g = 9.80665 m/s^2, from the ground unless stated, so
# eps = kappa v0^2 / g = (v0/v_t)^2 = c x 40.79 (c in kg/m): c = 0.01, 0.1, 1 give eps = 0.41,
# 4.1, 41. The setups carry a launch angle of 17 degrees on purpose: the sweep must ignore it.

V0 = 20.0
M = 1.0


def make_setup(c: float = 0.0, h: float = 0.0, v0: float = V0) -> QuadraticSetup:
    return QuadraticSetup(v0, math.radians(17.0), h, M, c, G)


def settings(method: str = "DOP853", tol: float = 1e-10) -> SolverSettings:
    return SolverSettings(method=method, rtol=tol, atol=tol)


def c_for(eps: float) -> float:
    """The drag constant (kg/m) giving drag strength eps = (c/m) v0^2 / g."""
    return eps * M * G / V0**2


def single_run(
    setup: QuadraticSetup, angle_deg: float, solver: SolverSettings
) -> qm.QuadraticComputation:
    """An independent single 2.1 run at one angle, built as the 2.1 route builds it."""
    at = dataclasses.replace(setup, launch_angle_rad=math.radians(angle_deg))
    return qm.run(at, solver)


def computed(
    c: float, h: float = 0.0, method: str = "DOP853", n_angles: int = 91, tol: float = 1e-10
) -> qas.QuadraticAngleSweepComputation:
    """Cached sweeps (several tests read the same one; a 91-angle sweep is ~100 solves).

    The arguments are normalised before the cache, so computed(0.01) and
    computed(0.01, 0.0, "DOP853", 91) share one entry (functools.cache keys on the call's
    exact positional and keyword form)."""
    return _computed(float(c), float(h), method, int(n_angles), float(tol))


@functools.cache
def _computed(
    c: float, h: float, method: str, n_angles: int, tol: float
) -> qas.QuadraticAngleSweepComputation:
    return qas.run_angle_sweep(make_setup(c, h), settings(method, tol), n_angles)


# Grid sizes. The API default (91, a 1-degree grid) is used where the property depends on the
# grid: the uncertainty estimate u (its curvature K is a grid second difference), per-angle
# comparisons, the peak count and the default budget. Where a test reads only the refined
# optimum, the grid merely seeds Brent's bracket (the best grid point +- one step, which holds
# the single peak), and Brent then converges to the peak of the same computed curve whatever
# the grid; there 11 angles (a 9-degree grid, 45 degrees on it) suffice. Measured (slice 2
# review, one machine): 11 instead of 91 angles moved the four RS3 optima by <= 9.7e-7
# degrees (Brent's stall on a flat top; ~1% of the smallest RS3 angle residual) and their
# ranges by <= 9e-16 relative.
N_DEFAULT = 91
N_COARSE = 11


# --- RS2: every point is a single 2.1 run ---------------------------------------------------


@pytest.mark.parametrize("method", ["DOP853", "RK45"])
def test_every_sweep_point_is_bit_identical_to_a_single_run(method: str) -> None:
    """RS2, by construction (plan D4): each point and each refinement is quadratic_model.run.

    Bit-identical comparisons are safe here: both sides perform the same floating-point
    operations on the same machine, whatever its libm."""
    s, solver = make_setup(c=0.05, h=1.5), settings(method)
    result = computed(0.05, 1.5, method, 10).sweep
    assert [p.angle_deg for p in result.points] == np.linspace(0.0, 90.0, 10).tolist()
    # One independent single run per distinct angle (memoised: each is compared below with
    # both the grid point and the sweep's own run at that angle).
    singles: dict[float, qm.QuadraticComputation] = {}

    def one(angle: float) -> qm.QuadraticComputation:
        if angle not in singles:
            singles[angle] = single_run(s, angle, solver)
        return singles[angle]

    for point in result.points:
        assert point.flew
        assert point.range == one(point.angle_deg).numerical.range
        assert point.flight_time == one(point.angle_deg).numerical.flight_time
        assert point.max_height == one(point.angle_deg).numerical.max_height
    # The best range is the range of a single run at the refined best angle.
    assert result.best_range == one(result.best_angle_deg).numerical.range
    # Every solve is listed once, and the evaluation count is theirs, run for run.
    assert len(result.runs) > len(result.points)  # the refinement ran
    for r in result.runs:
        assert r.computation.numerical == one(r.angle_deg).numerical
    assert result.n_rhs_evaluations == sum(
        r.computation.numerical.n_rhs_evaluations for r in result.runs
    )


def test_best_range_is_never_below_the_best_grid_point() -> None:
    # The refinement only replaces the best grid point if it beats it (plan D5), so this is
    # an exact comparison by construction (it holds on any CPU).
    for c, h, n in [(0.0, 0.0, N_DEFAULT), (0.01, 0.0, N_DEFAULT), (0.1, 5.0, 31)]:
        result = computed(c, h, "DOP853", n).sweep
        assert result.best_range >= max(p.range for p in result.points)


def test_grid_point_is_kept_when_it_beats_the_refinement(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fallback itself, on any CPU. Without drag from the ground the optimum, 45 degrees,
    is on odd grids, and Brent's nearby point (~7e-7 degrees away, ~1e-16 R* shorter) can lose
    to it by rounding; whether it does depends on the CPU's last bits, so a natural case
    cannot test the fallback everywhere. Here Brent is replaced by a stand-in that reports the
    bracket's left end (36 degrees on this 9-degree grid, ~4.9% shorter than 45 degrees:
    R ~ sin 2 theta), so the grid point must win on every machine."""

    def left_end(
        fun: Callable[[float], float], bounds: tuple[float, float], **_kwargs: object
    ) -> SimpleNamespace:
        return SimpleNamespace(x=bounds[0], fun=fun(bounds[0]))

    monkeypatch.setattr(qas, "minimize_scalar", left_end)
    result = qas.sweep(make_setup(), settings(), N_COARSE)
    grid_best = max(result.points, key=lambda p: p.range)
    assert grid_best.angle_deg == 45.0
    assert (result.best_angle_deg, result.best_range) == (45.0, grid_best.range)
    assert result.best_angle_uncertainty_deg is not None  # still an interior grid point


# --- RS1: no drag gives the textbook curve and optimum --------------------------------------


# From the ground, every method on the default 1-degree grid (shared with RS6). From the
# heights, DOP853 on a 3-degree grid (31 angles): the per-angle closed-form comparison still
# spans 0 to 90 degrees, and the best angle (39.3 degrees at h = 10 m, lower above) is
# refined from its own bracket, so the optimum's test does not depend on the grid.
RS1_CASES = [
    # (h in m, method, n_angles)
    (0.0, "DOP853", N_DEFAULT),
    (0.0, "RK45", N_DEFAULT),
    (0.0, "Radau", N_DEFAULT),
    (1.0, "DOP853", 31),
    (10.0, "DOP853", 31),
    (100.0, "DOP853", 31),
    (1000.0, "DOP853", 31),
]


@pytest.mark.parametrize(("h", "method", "n_angles"), RS1_CASES)
def test_vacuum_sweep_is_the_closed_form(h: float, method: str, n_angles: int) -> None:
    result = computed(0.0, h, method, n_angles).sweep
    # At c = 0 every method integrates the parabola exactly apart from rounding (the motion
    # is a polynomial of degree 2 in t, within each method's order), and SciPy locates the
    # landing to ~4 eps. Measured (slice 2, one machine): <= 5.8e-15 relative at every
    # angle of these seven sweeps (then all at 91 angles), so 1e-13 leaves ~17x for another
    # CPU's rounding.
    for p in result.points:
        assert p.range == rel_approx(qas.vacuum_range(V0, p.angle_deg, h, G), rel=1e-13)
    angle, best = qas.vacuum_optimum(V0, h, G)
    # Brent stops ~sqrt(eps_mach) x 45 = 7e-7 degrees from the peak of a flat top (plan RS1);
    # measured up to 1.85e-6 degrees (h = 100 m). 1e-5 degrees is the linear sweep's replay
    # rule and leaves ~5x.
    assert result.best_angle_deg == pytest.approx(angle, abs=1e-5)
    # An angle error of 1e-5 degrees (1.7e-7 rad) costs ~ (1/2) K d^2 = 2 R* d^2 = 6e-14 R*,
    # plus rounding: 1e-13.
    assert result.best_range == rel_approx(best, rel=1e-13)


def test_vacuum_uncertainty_estimate_follows_its_formula() -> None:
    """u = 2 sqrt(eps_R / K) (plan D6, RS4), with eps_R = 10 (rtol R* + atol) and, in vacuum
    from the ground, K = |R''(45 deg)| = 4 v0^2/g per rad^2 (from R = (v0^2/g) sin 2 theta).

    The grid's second difference over D = 1 degree gives K sin^2(D)/D^2, 1e-4 low (an exact
    identity for sin 2 theta), so u is 5e-5 high; with best range vs R* (1e-13) a 1e-3
    relative tolerance is wide yet catches a wrong factor (2, sqrt 2) or a degree/radian slip.
    """
    result = computed(0.0).sweep
    r_star = V0**2 / G
    eps_r = 10 * (1e-10 * r_star + 1e-10)
    expected = math.degrees(2 * math.sqrt(eps_r / (4 * r_star)))
    assert result.best_angle_uncertainty_deg == rel_approx(expected, rel=1e-3)
    assert "estimate, not a bound" in result.best_angle_note.lower()


# --- RS3: weak drag, first-order prediction with an eps^2 residual -------------------------

RS3_EPS = [5e-3, 1e-2, 2e-2, 4e-2]  # the plan's order-test values (seam 2)


def _log_slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of log|y| against log x."""
    return float(np.polyfit(np.log(xs), np.log(np.abs(ys)), 1)[0])


def _rs3_residuals(results: list[qas.QuadraticSweep]) -> tuple[list[float], list[float]]:
    angle = [
        r.best_angle_deg - wd.first_order_best_angle_deg(e)
        for r, e in zip(results, RS3_EPS, strict=True)
    ]
    best = [
        r.best_range / (V0**2 / G) - wd.first_order_best_range_ratio(e)
        for r, e in zip(results, RS3_EPS, strict=True)
    ]
    return angle, best


def test_weak_drag_optimum_matches_first_order_with_an_eps_squared_residual() -> None:
    """RS3 as an order test: the residual from theta* = 45 - 6.0183 eps degrees and
    R*/(v0^2/g) = 1 - 0.783976 eps must shrink about 4-fold per halving of eps.

    Slopes: the residuals measured in slice 1 by an independent rtol = 1e-13 integration are
    ~3.3 eps^2 degrees (>= 8e-5 degrees at eps = 5e-3) and ~0.77 eps^2 (>= 1.9e-5); their
    O(eps^3) drift moves the fitted slope by ~0.02. The sweep adds its own error: the angle
    within ~2e-6 degrees of the peak (Brent's stall on a flat top), up to 2.5% of the smallest
    angle residual, so ~0.05 on the slope, and the range ~1e-9 relative (negligible). The
    plan's 2 +- 0.3 for the angle covers that 6-fold; the range keeps slice 1's 2 +- 0.1.
    """
    results = [computed(c_for(e), 0.0, "DOP853", N_COARSE).sweep for e in RS3_EPS]
    angle, best = _rs3_residuals(results)
    # Measured (slice 2): slopes 1.983 (angle; residual / eps^2 = 3.32 -> 3.20) and 1.983
    # (range) on 91 angles, as slice 1's independent reference gave; 1.986 and 1.983 on the
    # 11 angles used here (see N_COARSE: the grid only seeds the bracket).
    assert _log_slope(RS3_EPS, angle) == pytest.approx(2.0, abs=0.3)
    assert _log_slope(RS3_EPS, best) == pytest.approx(2.0, abs=0.1)
    # And drag lowers the best angle and the range (the residual is second order).
    assert all(r.best_angle_deg < 45.0 for r in results)


def wrong_coupling(vx: float, vy: float, kappa: float) -> tuple[float, float]:
    """The classic bug (as in test_quadratic_numerical.py): -kappa|vx|vx, -kappa|vy|vy."""
    return -kappa * abs(vx) * vx, -kappa * abs(vy) * vy


def test_wrong_coupling_fails_the_weak_drag_order_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """The order test has teeth: the mutant's first-order loss F differs from the true one,
    so its residual keeps a part linear in eps and the fitted slopes fall towards 1.
    Measured (slice 2): 1.010 (angle) and 1.047 (range) on 91 angles, the same to 1e-4 on
    the 11 used here, against 2 +- 0.3 and 2 +- 0.1. (The mutant's optima, 44.86 to 44.98
    degrees, lie inside the 36-54 degree bracket.)"""
    monkeypatch.setattr(qn, "drag_acceleration", wrong_coupling)
    sweeps = [qas.sweep(make_setup(c_for(e)), settings(), N_COARSE) for e in RS3_EPS]
    angle, best = _rs3_residuals(sweeps)
    assert _log_slope(RS3_EPS, angle) < 1.5
    assert _log_slope(RS3_EPS, best) < 1.5


# --- RS4: stronger drag against an independent integration ---------------------------------

REF_RTOL = 1e-13  # the slice 1 reference's settings (see test_weak_drag_reference.py)


def reference_range(angle_deg: float, c: float, h: float) -> float:
    """Range in m by a test-local DOP853 integration (its own right-hand side and landing
    event) at rtol = atol = 1e-13, at v0 = 20 m/s, m = 1 kg."""
    kappa, theta = c / M, math.radians(angle_deg)

    def rhs(_t: float, z: np.ndarray) -> list[float]:
        vx, vy = float(z[2]), float(z[3])
        speed = math.hypot(vx, vy)
        return [vx, vy, -kappa * speed * vx, -G - kappa * speed * vy]

    def ground(t: float, z: np.ndarray) -> float:
        return float(z[1]) if t > 0 else 1.0

    ground.terminal = True  # type: ignore[attr-defined]
    ground.direction = -1.0  # type: ignore[attr-defined]
    vy0 = V0 * math.sin(theta)
    t_vacuum = (vy0 + math.sqrt(vy0 * vy0 + 2 * G * h)) / G  # drag only shortens the flight
    sol = solve_ivp(
        rhs,
        (0.0, 2 * t_vacuum),
        [0.0, h, V0 * math.cos(theta), vy0],
        method="DOP853",
        rtol=REF_RTOL,
        atol=REF_RTOL,
        events=ground,
    )
    assert sol.status == 1, "no landing found"
    return float(sol.y_events[0][0][0])


@functools.cache  # shared by the DOP853 and RK45 cases at c = 0.1 kg/m
def reference_optimum(c: float, h: float) -> tuple[float, float]:
    """(best angle in degrees, best range in m) by the reference integration.

    Brent alone stalls ~1e-6 degrees from a flat peak (slice 1: up to 1.75e-6 degrees between
    brackets), so it only centres a least-squares cubic through 21 ranges within +-0.2
    degrees, whose stationary point is the reference (slice 1 measured agreement between
    brackets and widths to 2.4e-11 degrees). The bracket 5-50 degrees is fixed, not taken
    from the sweep: every optimum here lies inside it (RS5 table, h = 0 and small h).
    """
    brent = minimize_scalar(
        lambda a: -reference_range(float(a), c, h),
        bounds=(5.0, 50.0),
        method="bounded",
        options={"xatol": 1e-8},
    )
    centre = float(brent.x)
    offsets = np.linspace(-0.2, 0.2, 21)
    ranges = [reference_range(centre + d, c, h) for d in offsets]
    cubic = np.polyfit(offsets, ranges, 3)
    roots = np.roots(np.polyder(cubic))
    peak = float(min(roots[np.isreal(roots)].real, key=abs))
    return centre + peak, float(np.polyval(cubic, peak))


RS4_CASES = [
    # (c in kg/m, h in m, method, n_angles). The 2.1 defaults on the default 91-angle grid
    # with both explicit methods (u as the API reports it). The stronger drags on a 3-degree
    # grid: Brent refines the same computed peak from any bracket that holds it, so only u's
    # curvature estimate K sees the grid, and u is checked as the run states it (measured,
    # slice 2 review: u on 31 angles within 1.8% of u on 91 at c = 1 kg/m, 0.1% elsewhere).
    (0.01, 0.0, "DOP853", N_DEFAULT),
    (0.01, 0.0, "RK45", N_DEFAULT),
    (0.1, 0.0, "DOP853", 31),
    (1.0, 0.0, "DOP853", 31),
    (0.1, 0.0, "RK45", 31),
    (0.1, 5.0, "DOP853", 31),
    (0.01, 0.0, "Radau", 10),  # Radau is ~35 us per evaluation and ~10x the evaluations
]


@pytest.mark.parametrize(("c", "h", "method", "n_angles"), RS4_CASES)
def test_best_angle_matches_an_independent_integration(
    c: float, h: float, method: str, n_angles: int
) -> None:
    result = computed(c, h, method, n_angles).sweep
    ref_angle, ref_range = reference_optimum(c, h)
    error = abs(result.best_angle_deg - ref_angle)
    # The stated estimate u holds (it is pessimistic by design, ~1e-3 degrees: plan D6).
    assert result.best_angle_uncertainty_deg is not None
    assert error <= result.best_angle_uncertainty_deg
    # Observed accuracy: the sweep's angle sits within Brent's stall of the computed curve's
    # peak (a flat top: ranges differ only by ~angle error squared), and the solver's error,
    # smooth in the angle, moves that peak far less. Measured (slice 2, one machine): 1.2e-7
    # to 3.4e-6 degrees on the original six cases, all on 91 angles (RK45 at c = 0.1 kg/m the
    # largest); 2.0e-8 to 8.5e-7 degrees on these seven. The plan's last-bit emulation
    # (another CPU's libm) moved the best angle by up to 1.0e-5 degrees, so 2e-5 degrees
    # covers both with ~2x margin, still ~100x tighter than u.
    assert error <= 2e-5
    # The best range: the solver rule 10 (rtol R + atol) (plan D11) at rtol = atol = 1e-10,
    # plus the reference's ~1e-13. Measured: <= 1.5e-11 relative (~70x margin). An angle
    # error of 2e-5 degrees costs only ~2 R (3.5e-7 rad)^2 = 2.4e-13 R of range.
    assert result.best_range == rel_approx(ref_range, rel=10 * (1e-10 + 1e-10 / ref_range))


# --- RS5: exact special points, and an observed property ------------------------------------


def test_zero_degrees_from_the_ground_is_no_flight_and_ninety_degrees_lands_at_zero() -> None:
    result = computed(0.01).sweep
    first, last = result.points[0], result.points[-1]
    # 0 degrees from the ground is not run (2.1 refuses it): range, time and height exactly 0.
    assert (first.angle_deg, first.flew) == (0.0, False)
    assert (first.range, first.flight_time, first.max_height) == (0.0, 0.0, 0.0)
    assert all(r.angle_deg != 0.0 for r in result.runs)
    # 90 degrees is exactly vertical (math.radians(90.0) == pi/2 exactly), so vx stays exactly
    # 0 and so does x: IEEE-exact by construction.
    assert (last.angle_deg, last.flew, last.range) == (90.0, True, 0.0)
    vertical = next(r for r in result.runs if r.angle_deg == 90.0).computation
    assert vertical.vertical_reference is not None  # checked against the exact R3 flight


def test_zero_degrees_from_a_height_is_a_real_flight() -> None:
    result = computed(0.1, 5.0, "DOP853", 31).sweep
    assert result.points[0].flew
    assert result.points[0].range > 0


def test_best_angle_falls_as_drag_grows_from_the_ground_observed() -> None:
    """Observed, not proved (plan RS5): on this grid of drag strengths from the ground. The
    successive optima differ by >= 0.0298 degrees, ~3e4 times Brent's stall, and each is the
    refined peak, which does not depend on the grid (see N_COARSE)."""
    drags = [0.0, *[c_for(e) for e in RS3_EPS], 0.01, 0.1, 1.0]
    angles = [computed(c, 0.0, "DOP853", N_COARSE).sweep.best_angle_deg for c in drags]
    assert all(a > b for a, b in itertools.pairwise(angles))


# --- The best angle at the edge of the grid ---------------------------------------------------


def test_best_grid_point_at_the_edge_gives_no_uncertainty_estimate() -> None:
    """v0 = 10 m/s from 1e5 m without drag: theta* = atan(10 / sqrt(100 + 2 g h)) = 0.409
    degrees, so on a 10-degree grid the best grid point is 0 degrees (R(0) = 1428 m against
    1408 m at 10 degrees). The second difference cannot be centred there: u is null, with the
    reason; the refinement on [0, 10] degrees still finds the closed-form optimum."""
    s = QuadraticSetup(10.0, 0.0, 1e5, M, 0.0, G)
    result = qas.sweep(s, settings(), 10)
    assert max(result.points, key=lambda p: p.range).angle_deg == 0.0
    assert result.best_angle_uncertainty_deg is None
    assert "edge" in result.best_angle_note
    assert result.interior_peaks == 0
    angle, best = qas.vacuum_optimum(10.0, 1e5, G)
    assert result.best_angle_deg == pytest.approx(angle, abs=1e-5)  # Brent, as in RS1
    assert result.best_range == rel_approx(best, rel=1e-13)


# --- The stiffness guard, before any solve --------------------------------------------------


def _no_solve(vx: float, vy: float, kappa: float) -> tuple[float, float]:
    raise AssertionError("a solve started")


@pytest.mark.parametrize("method", ["DOP853", "RK45"])
def test_guard_refuses_before_any_solve_and_names_the_worst_angle(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    """v0 = 100 m/s, h = 1e5 m, kappa = 0.0999 1/m: kappa h = 9990 drag lengths, so the
    drag-time bound (2.1's, proved) exceeds 1e4 at every grid angle except 90 degrees
    (9994.6), where the horizontal log term vanishes. The sweep must refuse at once (no solve
    at the angles that would pass) and name the angle with the largest bound."""
    monkeypatch.setattr(qn, "drag_acceleration", _no_solve)
    s = QuadraticSetup(100.0, 0.0, 1e5, M, 0.0999, G)
    bounds = {
        a: qm.drag_time_bound(dataclasses.replace(s, launch_angle_rad=math.radians(a)))
        for a in np.linspace(0.0, 90.0, 10).tolist()
    }
    assert bounds[90.0] < 1e4 < min(b for a, b in bounds.items() if a != 90.0)
    worst = max(bounds, key=lambda a: bounds[a])
    with pytest.raises(ModelDomainError, match=rf"at {worst:g}°") as refused:
        qas.sweep(s, settings(method), 10)
    assert method in str(refused.value)
    assert "Radau" in str(refused.value)


# --- The evaluation budget --------------------------------------------------------------------


def test_budget_refuses_between_runs_and_deterministically() -> None:
    """The budget is checked after each run: a sweep is refused as soon as its total exceeds
    it. The counts come from independent single runs at the same angles."""
    s, solver, n = make_setup(c=0.05, h=1.5), settings(), 10
    grid = np.linspace(0.0, 90.0, n).tolist()
    per_run = [single_run(s, a, solver).numerical.n_rhs_evaluations for a in grid[:3]]
    full = computed(0.05, 1.5, "DOP853", n).sweep  # the RS2 sweep: well within the default
    total = full.n_rhs_evaluations
    # Exactly the whole sweep's count is allowed; one fewer refuses at the last run.
    assert qas.sweep(s, solver, n, max_rhs_evaluations=total).best_range == full.best_range
    with pytest.raises(ModelDomainError, match="refinement"):
        qas.sweep(s, solver, n, max_rhs_evaluations=total - 1)
    # A budget equal to the first three runs passes them and refuses after the fourth.
    budget = sum(per_run[:3])
    messages = []
    for _ in range(2):
        with pytest.raises(ModelDomainError, match="after 4 of 10 angles") as refused:
            qas.sweep(s, solver, n, max_rhs_evaluations=budget)
        messages.append(str(refused.value))
    assert messages[0] == messages[1]
    assert f"{budget:,}" in messages[0]


def test_default_budget_admits_the_default_sweep_with_every_explicit_method() -> None:
    # The 2.1 defaults (v0 = 20 m/s, c = 0.01 kg/m, m = 1 kg, h = 0), 91 angles.
    for method in ["DOP853", "RK45"]:
        assert computed(0.01, 0.0, method, N_DEFAULT).sweep.n_rhs_evaluations <= (
            qas.MAX_SWEEP_RHS_EVALUATIONS
        )


def test_too_few_angles_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        qas.sweep(make_setup(), settings(), 2)


# ============================================================================================
# Slice 2, seam 3: the model run (``run_angle_sweep``): references and aggregated checks.
# ============================================================================================

RS6_CASES = [
    # (c in kg/m, h in m, method, n_angles): every 2.1 check at every run must pass. The
    # sweeps of RS1 and RS4 (cached, so no extra solves): vacuum and the 2.1 defaults on the
    # 1-degree grid with every explicit method, the stronger drags on a 3-degree grid, Radau
    # on 10 angles. On the 3-degree grid this is evidence at ~40 runs per sweep rather than
    # ~100; the 2.1 checks vary smoothly with the angle, and the plan's scratch run (D10)
    # passed them at all 361 angles of four cases with each method.
    (0.0, 0.0, "DOP853", N_DEFAULT),
    (0.0, 0.0, "RK45", N_DEFAULT),
    (0.0, 0.0, "Radau", N_DEFAULT),
    *RS4_CASES,
]


@pytest.mark.parametrize(("c", "h", "method", "n_angles"), RS6_CASES)
def test_every_run_passes_the_2_1_checks(c: float, h: float, method: str, n_angles: int) -> None:
    result = computed(c, h, method, n_angles)
    assert result.checks
    for check in result.checks:
        assert check.passed is not False, check


def test_aggregated_checks_report_the_worst_run_and_its_angle() -> None:
    """Each aggregate takes value and threshold from the run with the largest value /
    threshold, recomputed here from independent single runs at the same angles."""
    s, solver = make_setup(c=0.05, h=0.0), settings()
    result = qas.run_angle_sweep(s, solver, 10)
    angles = [r.angle_deg for r in result.sweep.runs]
    per_angle = [(a, single_run(s, a, solver).checks) for a in angles]
    by_id = {c.id: c for c in result.checks}
    for check_id in ["energy_balance", "hodograph_invariant", "speed_bound", "flight_time_bound"]:
        graded = [
            (c.value / c.threshold, a, c)
            for a, checks in per_angle
            for c in checks
            if c.id == check_id and c.threshold is not None
        ]
        _, worst_angle, worst = max(graded, key=lambda t: t[0])
        agg = by_id[check_id]
        assert (agg.value, agg.threshold, agg.passed) == (worst.value, worst.threshold, True)
        assert f"{worst_angle:.10g}°" in agg.note
        assert f"{len(graded)} runs" in agg.note
    # The invariant is undefined at 90 degrees (vx = 0): the aggregate says so.
    assert "90°" in by_id["hodograph_invariant"].note
    # The exact vertical flight exists only at 90 degrees: one run.
    assert "Across the sweep: 1 run, 0 failed" in by_id["vertical_flight_time"].note
    # The drag time is informational: the largest bound over the runs.
    bounds = [c.value for _, checks in per_angle for c in checks if c.id == "drag_time"]
    assert by_id["drag_time"].value == max(bounds)
    assert by_id["drag_time"].passed is None


def test_one_failing_run_fails_the_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seam 3's planted failure: one run, at 30 degrees, is marked failed in its energy check
    (its value is left as it was, below the threshold, so it is not the worst run). The
    aggregate must fail because *every* run must pass, not because of the worst run, and the
    other checks must be unaffected."""
    real_run = qm.run

    def planted(setup: QuadraticSetup, solver: SolverSettings, **kwargs: int) -> object:
        out = real_run(setup, solver, **kwargs)
        if setup.launch_angle_rad != math.radians(30.0):
            return out
        checks = [
            c.model_copy(update={"passed": False}) if c.id == "energy_balance" else c
            for c in out.checks
        ]
        return dataclasses.replace(out, checks=checks)

    monkeypatch.setattr(qm, "run", planted)
    by_id = {c.id: c for c in qas.run_angle_sweep(make_setup(c=0.05), settings(), 10).checks}
    energy = by_id["energy_balance"]
    assert energy.passed is False
    assert energy.threshold is not None
    assert energy.value <= energy.threshold  # the worst run itself passed
    assert ", 1 failed;" in energy.note
    assert by_id["hodograph_invariant"].passed is True
    assert by_id["flight_time_bound"].passed is True


def test_vacuum_sweep_has_the_closed_form_references_and_nulls() -> None:
    result = computed(0.0, 10.0, "DOP853", 31)
    assert result.terminal_speed is None
    assert "speed_bound" not in {c.id for c in result.checks}  # 2.1 has it only with drag
    angle, best = qas.vacuum_optimum(V0, 10.0, G)
    assert (result.vacuum_best_angle_deg, result.vacuum_best_range) == (angle, best)
    for p, r in zip(result.sweep.points, result.vacuum_ranges, strict=True):
        assert r == qas.vacuum_range(V0, p.angle_deg, 10.0, G)


def test_terminal_speed_is_the_closed_form() -> None:
    # v_t = sqrt(m g / c), from the definition: c = 0.1 kg/m, m = 1 kg.
    assert computed(0.1, 0.0, "DOP853", 31).terminal_speed == rel_approx(
        math.sqrt(G / 0.1), rel=2 * EPS
    )


def test_wrong_coupling_is_caught_by_the_aggregated_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mutant -kappa|vx|vx, -kappa|vy|vy (as in test_quadratic_numerical.py) agrees with
    the true law at 90 degrees (vx = 0) only; elsewhere 2.1 measured energy and invariant
    residuals of 0.16 to 0.34 against thresholds ~1e-6, so the aggregates must fail."""
    monkeypatch.setattr(qn, "drag_acceleration", wrong_coupling)
    by_id = {c.id: c for c in qas.run_angle_sweep(make_setup(c=0.05), settings(), 10).checks}
    assert by_id["energy_balance"].passed is False
    assert by_id["hodograph_invariant"].passed is False


def test_peak_count_is_one_for_a_real_curve() -> None:
    peaks = {c.id: c for c in computed(0.01).checks}["interior_peaks"]
    assert (peaks.value, peaks.passed) == (1.0, True)


def test_two_peaks_are_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    """A planted force (not physics): no drag, but an upward push of up to g/2 that acts only
    when vx is near v0 cos 70 degrees, so a launch near 70 degrees feels half gravity. Then
    R = v0^2 sin 2 theta / g_eff has a local peak near 45 degrees (g_eff ~ g, R ~ v0^2/g) and
    a higher one near 70 degrees (R ~ 1.29 v0^2/g): two interior peaks on a 1-degree grid."""

    def lift(vx: float, vy: float, kappa: float) -> tuple[float, float]:
        return 0.0, 0.5 * G * math.exp(-(((vx - V0 * math.cos(math.radians(70))) / V0 / 0.05) ** 2))

    monkeypatch.setattr(qn, "drag_acceleration", lift)
    result = qas.run_angle_sweep(make_setup(), settings(), 91)
    peaks = {c.id: c for c in result.checks}["interior_peaks"]
    assert (peaks.value, peaks.passed) == (2.0, False)
    assert result.sweep.interior_peaks == 2


def test_cost_is_reported_against_the_budget() -> None:
    result = computed(0.01)
    cost = {c.id: c for c in result.checks}["sweep_cost"]
    assert cost.value == result.sweep.n_rhs_evaluations
    assert f"{len(result.sweep.runs)} runs" in cost.note
    assert f"{qas.MAX_SWEEP_RHS_EVALUATIONS:,}" in cost.note


# --- Review 2026-11-10: aggregates of checks that cannot fail ---------------------------------


def test_aggregate_gives_no_verdict_when_a_run_could_not_be_graded() -> None:
    """At rtol = 1e-3 every 2.1 threshold allows an error above 100% (1e4 x rtol = 10), so
    each run reports passed = None. The aggregate must not turn that into "passed" (nor into
    "failed": nothing failed); it is None and says how many runs gave no verdict."""
    solver = SolverSettings(method="RK45", rtol=1e-3, atol=1e-10)
    result = qas.run_angle_sweep(make_setup(c=0.02), solver, 10)
    by_id = {c.id: c for c in result.checks}
    for check_id in ("energy_balance", "hodograph_invariant", "speed_bound", "flight_time_bound"):
        check = by_id[check_id]
        assert check.passed is None, check_id
        assert "no verdict" in check.note.lower()
        assert "0 failed" in check.note


def test_a_failed_run_still_fails_an_aggregate_with_ungraded_runs() -> None:
    """Unit test of the rule on hand-made checks: failed beats no-verdict beats passed."""

    def check(passed: bool | None, value: float) -> ValidationCheck:
        return ValidationCheck(
            id="energy_balance",
            label="x",
            value=value,
            threshold=2.0,
            passed=passed,
            kind="numerical_diagnostic",
            note="n.",
        )

    agg = qas._aggregate
    assert agg([(10.0, check(True, 0.1)), (20.0, check(True, 0.2))]).passed is True
    assert agg([(10.0, check(True, 0.1)), (20.0, check(None, 0.2))]).passed is None
    assert agg([(10.0, check(False, 3.0)), (20.0, check(None, 0.2))]).passed is False
