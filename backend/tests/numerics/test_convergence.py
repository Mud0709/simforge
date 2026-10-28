import pytest

from simforge.numerics.convergence import fit_order, local_orders
from tests.approx import rel_approx


def test_fit_recovers_exact_power_law() -> None:
    h = [0.1, 0.05, 0.025, 0.0125]
    fit = fit_order(h, [3.0 * x**2 for x in h])
    assert fit is not None
    assert fit.order == pytest.approx(2.0, abs=1e-12)
    assert fit.r_squared == pytest.approx(1.0, abs=1e-12)
    assert 10**fit.log10_constant == rel_approx(3.0, rel=1e-10)
    assert (fit.h_min, fit.h_max, fit.n_points) == (0.0125, 0.1, 4)


def test_fit_refuses_fewer_than_three_distinct_points() -> None:
    assert fit_order([0.1, 0.05], [1e-2, 2.5e-3]) is None
    assert fit_order([0.1, 0.1, 0.05], [1e-2, 1e-2, 2.5e-3]) is None  # duplicates collapse
    assert fit_order([0.1, 0.05, 0.025], [1e-2, 0.0, 1e-4]) is None  # zero error unusable


def test_fit_reports_poor_linearity() -> None:
    fit = fit_order([0.1, 0.05, 0.025, 0.0125], [1e-2, 1e-6, 1e-3, 1e-8])
    assert fit is not None
    assert fit.r_squared < 0.9


def test_local_orders() -> None:
    assert local_orders([0.2, 0.1, 0.05], [4e-2, 1e-2, 2.5e-3]) == pytest.approx([2.0, 2.0])
    assert local_orders([0.2, 0.1], [1e-2, 0.0]) == [None]
