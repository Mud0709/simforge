"""Model-independent tests of the from-scratch integrators.

References: the methods' stability functions, polynomial exactness of RK4 and the
exact solution of y' = lambda y. Nothing here depends on projectile physics.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from simforge.numerics.convergence import fit_order
from simforge.numerics.fixed_step import (
    euler_stability,
    euler_step,
    integrate_fixed,
    rk4_stability,
    rk4_step,
)


def decay(lam: float):  # type: ignore[no-untyped-def]
    return lambda _t, y: lam * y


@pytest.mark.parametrize(
    ("step", "stability"), [(euler_step, euler_stability), (rk4_step, rk4_stability)]
)
@pytest.mark.parametrize("z", [-0.1, -1.0, -2.5, -3.0, 0.5])
def test_one_step_on_linear_equation_equals_stability_function(step, stability, z) -> None:  # type: ignore[no-untyped-def]
    y0 = np.array([1.7])
    assert step(decay(z), 0.0, y0, 1.0)[0] == pytest.approx(stability(z) * 1.7, rel=1e-15)


def test_rk4_is_exact_for_cubic_quadrature() -> None:
    """For y' = f(t), RK4 reduces to Simpson's rule, which is exact for cubics."""
    sol = integrate_fixed(
        rk4_step, lambda t, _y: np.array([4 * t**3 - t]), np.array([0.0]), 0.0, 0.25, 8
    )
    t = sol.t
    np.testing.assert_allclose(sol.y[:, 0], t**4 - t**2 / 2, rtol=1e-14, atol=1e-15)


def test_node_times_are_not_accumulated() -> None:
    sol = integrate_fixed(euler_step, decay(-1.0), np.array([1.0]), 2.0, 0.1, 1000)
    assert sol.t[-1] == 2.0 + 0.1 * 1000  # exact product, not 1000 rounded additions
    assert len(sol.t) == len(sol.y) == 1001


@pytest.mark.parametrize(("h", "n"), [(0.0, 10), (-0.1, 10), (math.nan, 10), (0.1, 0)])
def test_invalid_step_arguments_are_rejected(h: float, n: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        integrate_fixed(euler_step, decay(-1.0), np.array([1.0]), 0.0, h, n)


def test_divergence_is_detected_and_stops_early() -> None:
    # |R| = |1 - 10| = 9 per step: exceeds 1e100 after ~105 steps, well before 10_000.
    sol = integrate_fixed(euler_step, decay(-10.0), np.array([1.0]), 0.0, 1.0, 10_000)
    assert sol.diverged
    assert len(sol.t) < 200
    assert np.all(np.isfinite(sol.y))


@pytest.mark.parametrize(("step", "order"), [(euler_step, 1), (rk4_step, 4)])
def test_convergence_order_on_exponential_decay(step, order: int) -> None:  # type: ignore[no-untyped-def]
    """Global error at t = 1 for y' = -y, over eight step sizes (h = 1/10 ... 1/1280)."""
    hs, errs = [], []
    for n in [10 * 2**i for i in range(8)]:
        sol = integrate_fixed(step, decay(-1.0), np.array([1.0]), 0.0, 1.0 / n, n)
        hs.append(1.0 / n)
        errs.append(abs(sol.y[-1, 0] - math.exp(-1.0)))
    # RK4 hits round-off (~1e-16) at the finest steps, so fit only errors above 1e-13.
    keep = [i for i, e in enumerate(errs) if e > 1e-13]
    fit = fit_order([hs[i] for i in keep], [errs[i] for i in keep])
    assert fit is not None
    assert fit.n_points >= 4
    assert fit.order == pytest.approx(order, abs=0.05)
