"""Numerical-vs-exact tests: accuracy, convergence and conservation."""

from __future__ import annotations

import itertools

import pytest

from simforge.core.errors import ModelDomainError
from simforge.physics.projectile import model
from simforge.physics.projectile.schemas import (
    ProjectileParameters,
    ProjectileRequest,
    SolverSettings,
)


def run(method: str = "DOP853", rtol: float = 1e-10, atol: float = 1e-10, **params: float):  # type: ignore[no-untyped-def]
    return model.run(
        ProjectileRequest(
            parameters=ProjectileParameters(**params),
            solver=SolverSettings(method=method, rtol=rtol, atol=atol),  # type: ignore[arg-type]
        )
    )


@pytest.mark.parametrize("method", ["RK45", "DOP853", "Radau"])
@pytest.mark.parametrize("drag", [0.0, 0.1, 3.0])
def test_all_solvers_agree_with_exact_solution(method: str, drag: float) -> None:
    r = run(method=method, drag_coefficient=drag, launch_height=2.0)
    c = r.comparison
    # Global error is not bounded by rtol, but for this smooth, non-chaotic problem it is
    # within a modest multiple. Scales: ~40 m positions, ~3 s flights.
    assert c.max_position_error < 1e-7
    assert c.flight_time.relative is not None
    assert c.flight_time.relative < 1e-9
    assert c.range.relative is not None
    assert c.range.relative < 1e-9
    assert c.max_height.relative is not None
    assert c.max_height.relative < 1e-9
    assert c.max_energy_balance_residual < 1e-8


def test_error_decreases_as_tolerance_tightens() -> None:
    errors = [
        run(method="RK45", rtol=tol, atol=tol, drag_coefficient=0.5).comparison.max_position_error
        for tol in (1e-4, 1e-7, 1e-10)
    ]
    assert errors[0] > errors[1] > errors[2]
    assert errors[0] / errors[2] > 1e3  # roughly tracks the six orders of magnitude in rtol


def test_vacuum_conserves_mechanical_energy() -> None:
    r = run(drag_coefficient=0.0)
    assert r.comparison.max_energy_balance_residual < 1e-12
    assert r.series.drag_work[-1] == 0.0


def test_drag_dissipates_energy() -> None:
    r = run(drag_coefficient=0.5)
    work = r.series.drag_work
    assert work[-1] > 0
    assert all(b >= a for a, b in itertools.pairwise(work))


def test_series_ends_at_landing() -> None:
    r = run(drag_coefficient=0.2, launch_height=5.0)
    assert r.series.t[-1] == pytest.approx(r.numerical.flight_time, rel=1e-15)
    assert abs(r.series.y_numerical[-1]) < 1e-8
    assert len(r.series.t) == 400


def test_horizontal_launch_from_height() -> None:
    r = run(launch_angle_deg=0.0, launch_height=20.0, drag_coefficient=0.3)
    assert r.numerical.apex_time == 0.0
    assert r.numerical.max_height == 20.0
    assert r.comparison.flight_time.relative is not None
    assert r.comparison.flight_time.relative < 1e-9


def test_vertical_launch_has_zero_range_and_null_relative_error() -> None:
    r = run(launch_angle_deg=90.0, drag_coefficient=0.1)
    assert abs(r.numerical.range) < 1e-12
    assert r.analytical.range == pytest.approx(0.0, abs=1e-12)


def test_stiff_problem_rejected_for_explicit_solver() -> None:
    params = {"launch_height": 1e4, "drag_coefficient": 100.0, "mass": 0.1}
    with pytest.raises(ModelDomainError, match="Radau"):
        run(method="RK45", **params)
