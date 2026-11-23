"""A model-independent 1-D sweep driver (roadmap 2.5, plan D3): refine a grid maximum,
estimate its curvature, count interior peaks and cap the work done.

No physics, units or messages: the model passes in the grid, the objective and its values,
and turns :class:`WorkBudgetExceededError` into its own ``ModelDomainError`` message.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from scipy.optimize import minimize_scalar


def refine_maximum(
    objective: Callable[[float], float],
    grid: Sequence[float],
    values: Sequence[float],
    xatol: float,
) -> tuple[float, float, int]:
    """(x_best, f_best, i_grid): Brent's bounded method on the best grid point's neighbour
    interval [grid[i-1], grid[i+1]] (clamped at an edge); the grid point is kept exactly when
    its value beats the refinement. ``values[j]`` must be ``objective(grid[j])``."""
    n = len(grid)
    i = max(range(n), key=lambda j: values[j])
    result = minimize_scalar(
        lambda x: -objective(float(x)),
        bounds=(grid[max(i - 1, 0)], grid[min(i + 1, n - 1)]),
        method="bounded",
        options={"xatol": xatol},
    )
    if values[i] > -float(result.fun):  # the optimum sits on a grid point (to rounding)
        return grid[i], values[i], i
    return float(result.x), -float(result.fun), i


def curvature(values: Sequence[float], i: int, step: float) -> float | None:
    """K = -(values[i+1] - 2 values[i] + values[i-1]) / step^2, the centred second-difference
    estimate of |f''| at grid point i; None at an edge or when the curve is not bent down."""
    if i <= 0 or i >= len(values) - 1:
        return None
    d2 = values[i + 1] - 2 * values[i] + values[i - 1]
    return -d2 / step**2 if d2 < 0 else None


def interior_peaks(values: Sequence[float]) -> int:
    """Interior points strictly above both neighbours (plateaus and edges do not count)."""
    return sum(1 for j in range(1, len(values) - 1) if values[j - 1] < values[j] > values[j + 1])


class WorkBudgetExceededError(Exception):
    """Raised by :meth:`WorkBudget.charge` once the total exceeds the limit."""

    def __init__(self, total: int, limit: int) -> None:
        super().__init__(f"work {total} exceeds the budget of {limit}")
        self.total = total
        self.limit = limit


class WorkBudget:
    """A running total of work (e.g. right-hand-side evaluations) capped at ``limit``."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.total = 0

    def charge(self, n: int) -> None:
        """Add n; raise :class:`WorkBudgetExceededError` if the total is now above the limit."""
        self.total += n
        if self.total > self.limit:
            raise WorkBudgetExceededError(self.total, self.limit)
