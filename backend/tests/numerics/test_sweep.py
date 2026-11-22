"""Model-independent tests of the sweep driver (`simforge.numerics.sweep`, plan 2.5 D3).

References are independent of the driver: closed-form parabolas with a known maximum x* and
a known curvature K, and hand-made sequences whose peak count is read off by eye. Nothing
here depends on any physics model (plan 2.5, seam 1).
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest

from simforge.numerics import sweep
from simforge.numerics.sweep import WorkBudget, curvature, interior_peaks, refine_maximum
from tests.approx import rel_approx

# A dyadic step (1/8) makes every grid point exactly representable, so the grid itself adds
# no rounding and the bracket ends are exact grid values.
STEP = 0.125
GRID: list[float] = [j * STEP for j in range(9)]  # 0, 0.125, ..., 1

# Brent's bounded method (scipy fminbound) stops when the bracket half-width is at most
# 2 tol, with tol = sqrt(eps) |x| + xatol / 3; for |x| <= 1 the sqrt(eps) |x| term is at most
# 1.5e-8, so the guaranteed distance to the true optimum is <= 2/3 xatol + 3e-8 < xatol for
# xatol = 1e-6. Hence "within xatol" is a guarantee of the method, not a lucky observation.
XATOL = 1e-6


def parabola(x_star: float, k: float = 2.0, top: float = 0.0) -> Callable[[float], float]:
    """f(x) = top - (k / 2) (x - x*)^2: maximum `top` at x*, curvature |f''| = k."""
    return lambda x: top - 0.5 * k * (x - x_star) ** 2


def values_on(f: Callable[[float], float], grid: list[float]) -> list[float]:
    return [f(x) for x in grid]


def nearest_index(grid: list[float], x_star: float) -> int:
    return min(range(len(grid)), key=lambda j: abs(grid[j] - x_star))


# --- (1) an off-grid interior maximum is refined; the grid point wins over a worse refinement


@pytest.mark.parametrize("x_star", [0.3, 0.69, 0.5 + 1e-3])
def test_refine_maximum_finds_an_off_grid_maximum_within_xatol(x_star: float) -> None:
    f = parabola(x_star)
    values = values_on(f, GRID)
    assert x_star not in GRID  # the maximum really is off-grid

    x_best, f_best, i_grid = refine_maximum(f, GRID, values, XATOL)

    assert i_grid == nearest_index(GRID, x_star)  # best grid point of a symmetric parabola
    assert abs(x_best - x_star) <= XATOL  # Brent's guarantee (see XATOL)
    # f_best is the objective at x_best; within xatol of x*, f is at most (k/2) xatol^2 below
    # the top (k = 2 here), so f_best lies in [-xatol^2, 0] up to one rounding of f.
    assert f_best == pytest.approx(f(x_best), rel=0, abs=1e-15)
    assert -(XATOL**2) - 1e-15 <= f_best <= 0.0


def test_grid_point_is_kept_when_it_beats_the_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D3: the grid point is kept when it beats the refinement (angle_sweep.py:115-127).
    Brent is replaced by a stand-in that reports the bracket's left end, which on this grid
    is strictly worse than the best grid point, so the grid point must win exactly."""

    def left_end(
        fun: Callable[[float], float], bounds: tuple[float, float], **_kwargs: object
    ) -> SimpleNamespace:
        return SimpleNamespace(x=bounds[0], fun=fun(bounds[0]))

    monkeypatch.setattr(sweep, "minimize_scalar", left_end)
    x_star = 0.3  # best grid point 0.25 (index 2); bracket [0.125, 0.375]; left end 0.125
    f = parabola(x_star)
    values = values_on(f, GRID)
    assert f(GRID[1]) < values[2]  # the stand-in's answer really is worse

    x_best, f_best, i_grid = refine_maximum(f, GRID, values, XATOL)

    assert i_grid == 2
    assert (x_best, f_best) == (GRID[2], values[2])  # kept exactly, not recomputed


# --- (2) edge maxima and the curvature estimate --------------------------------------------


@pytest.mark.parametrize(("x_star", "edge"), [(-0.3, 0), (1.3, len(GRID) - 1)])
def test_edge_maximum_refines_inside_the_edge_interval(x_star: float, edge: int) -> None:
    """With x* outside the grid, f is monotone on it: the best grid point is an edge, the
    bracket is clamped to the single edge interval, and the answer stays inside it."""
    f = parabola(x_star)
    values = values_on(f, GRID)

    x_best, f_best, i_grid = refine_maximum(f, GRID, values, XATOL)

    inner = 1 if edge == 0 else len(GRID) - 2
    lo, hi = sorted((GRID[edge], GRID[inner]))
    assert i_grid == edge
    assert lo <= x_best <= hi  # inside the edge interval, never beyond the grid
    # f is strictly monotone on the interval, so the edge itself is the constrained maximum;
    # Brent stops within its tolerance (see XATOL) of it, or the grid point is kept exactly.
    assert abs(x_best - GRID[edge]) <= XATOL
    assert f_best >= values[edge]  # never worse than the best grid point
    assert curvature(values, edge, STEP) is None  # no centred difference at an edge


@pytest.mark.parametrize("k", [0.5, 3.0, 40.0])
@pytest.mark.parametrize("x_star", [0.3, 0.69])
def test_curvature_of_a_parabola_is_k(k: float, x_star: float) -> None:
    """The centred second difference f(x+h) - 2 f(x) + f(x-h) of a quadratic equals f'' h^2
    exactly in exact arithmetic (the Taylor series stops at the second term). In floating
    point each value |f| <= (k/2) * 1 carries at most ~1 ulp of rounding, so the difference
    -k h^2 is off by about 4 eps (k/2) / (k h^2) = 2 eps / h^2 = 128 eps ~ 3e-14 relative
    (h = 1/8, and dividing by the dyadic h^2 is exact). 1e-12 leaves a ~30x margin."""
    values = values_on(parabola(x_star, k=k, top=0.0), GRID)
    for i in range(1, len(GRID) - 1):
        estimate = curvature(values, i, STEP)
        assert estimate is not None
        assert estimate == rel_approx(k, 1e-12)


def test_curvature_is_none_when_not_bent_down() -> None:
    # Exact small integers, so each second difference is computed exactly.
    convex = [4.0, 1.0, 0.0, 1.0, 4.0]  # second difference +2 at index 2
    straight = [0.0, 1.0, 2.0, 3.0, 4.0]  # second difference exactly 0
    assert curvature(convex, 2, 1.0) is None
    assert curvature(straight, 2, 1.0) is None
    assert curvature([0.0, 1.0, 0.0], 1, 1.0) == 2.0  # -(0 - 2 + 0) / 1^2, exact


# --- (3) interior peaks on hand-made sequences ----------------------------------------------


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1.0, 2.0, 3.0], 0),  # monotone: the maximum is an edge, not an interior peak
        ([3.0, 2.0, 1.0], 0),
        ([1.0, 3.0, 2.0], 1),
        ([0.0, 2.0, 1.0, 3.0, 1.0], 2),
        ([1.0, 2.0, 2.0, 1.0], 0),  # plateau: neither point strictly beats both neighbours
        ([1.0, 2.0, 2.0, 1.0, 3.0, 1.0], 1),  # a plateau plus one strict peak
        ([5.0, 5.0, 5.0], 0),  # flat
    ],
)
def test_interior_peaks_counts_strict_interior_maxima(values: list[float], expected: int) -> None:
    assert interior_peaks(values) == expected


# --- (4) the work budget ------------------------------------------------------------------


def _driver_exception(exc: BaseException) -> bool:
    """D3: charge raises a driver exception (defined in the driver, for the model to turn
    into its own ModelDomainError message), not a generic built-in error."""
    return type(exc).__module__ == sweep.__name__


def test_work_budget_raises_on_the_first_charge_that_exceeds_the_limit() -> None:
    budget = WorkBudget(100)
    budget.charge(60)
    budget.charge(40)  # total 100 == limit: not exceeded, so no error yet
    with pytest.raises(Exception) as caught:  # noqa: PT011 - the class is checked below
        budget.charge(1)  # total 101 > 100
    assert _driver_exception(caught.value)


def test_work_budget_single_charge_over_the_limit_raises() -> None:
    with pytest.raises(Exception) as caught:  # noqa: PT011 - the class is checked below
        WorkBudget(10).charge(11)
    assert _driver_exception(caught.value)


def test_work_budget_many_small_charges_up_to_the_limit_do_not_raise() -> None:
    budget = WorkBudget(1000)
    for _ in range(1000):
        budget.charge(1)  # reaches the limit exactly, never beyond it
    with pytest.raises(Exception) as caught:  # noqa: PT011 - the class is checked below
        budget.charge(1)
    assert _driver_exception(caught.value)
