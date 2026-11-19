"""The oscillator's run-cost rule (roadmap 2.3, slice 3; the author's decision of 2026-11-10).

One budget of right-hand-side evaluations per run, ``model.MAX_RUN_RHS_EVALUATIONS``, counted
inside the right-hand side during the solve, so an over-budget solve stops at the budget
instead of running to its end (slice 2's review measured Radau at the tightest pair, 500
cycles and w = 100 w0, at 792 s). A run over the budget is refused with a ``ModelDomainError``
(422 at the API) that names the budget and what to change.

The reference count is independent of the code's counter: ``numerical.damping_acceleration``
is looked up by the right-hand side at every call (the mutation seam of slice 2), so wrapping
it counts the right-hand-side calls the solver really made, Jacobian columns included.
``model.run`` takes the budget as the keyword ``max_rhs_evaluations`` (default
``MAX_RUN_RHS_EVALUATIONS``), as the 2.2 sweep does (``quadratic_angle_sweep.sweep``).
"""

from __future__ import annotations

import inspect
import math
import time
from collections.abc import Callable

import pytest

from simforge.core.errors import ModelDomainError
from simforge.physics.oscillator import model, numerical
from simforge.physics.oscillator.analytical import OscillatorInputs
from simforge.physics.projectile.schemas import SolverSettings

DEFAULT = OscillatorInputs(
    mass=1.0,
    spring_constant=25.0,
    damping_coefficient=0.5,
    drive_angular_frequency=5.0,
    initial_displacement=0.1,
)  # the Damped preset (plan D2), 20 s
DEFAULT_DURATION = 20.0
# Slice 2's item 1: w0 = 1 rad/s, w = 100 w0, just under 500 cycles (T 100 / 2 pi = 499.7).
FAST_DRIVE = OscillatorInputs(
    mass=1.0,
    spring_constant=1.0,
    damping_coefficient=0.1,
    drive_amplitude=1.0,
    drive_angular_frequency=100.0,
)
FAST_DRIVE_DURATION = 31.4
TIGHT = SolverSettings(method="Radau", rtol=1e-13, atol=1e-14)


def counted(monkeypatch: pytest.MonkeyPatch) -> Callable[[], int]:
    """Count the right-hand-side calls from here on; returns a reader of the count."""
    calls = 0
    law = numerical.damping_acceleration

    def counting(eta: float, zeta: float) -> float:
        nonlocal calls
        calls += 1
        return law(eta, zeta)

    monkeypatch.setattr(numerical, "damping_acceleration", counting)
    return lambda: calls


def test_the_budget_is_a_named_positive_integer() -> None:
    assert isinstance(model.MAX_RUN_RHS_EVALUATIONS, int)
    assert model.MAX_RUN_RHS_EVALUATIONS > 0


@pytest.mark.parametrize("method", ["RK45", "DOP853", "Radau"])
def test_a_run_needing_exactly_the_budget_runs_and_one_less_is_refused(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    solver = SolverSettings(method=method)
    count = counted(monkeypatch)
    free = model.run(DEFAULT, DEFAULT_DURATION, solver, max_rhs_evaluations=10**9)
    needed = count()
    assert needed > 0
    if method != "Radau":
        # Explicit methods call the right-hand side only for their stages, so SciPy's nfev
        # is the true count. (Radau's nfev leaves out the Jacobian's finite-difference
        # columns; those still count against the budget, being right-hand-side calls.)
        assert free.numerical.n_rhs_evaluations == needed
    # Exactly the budget: the same computation, bit for bit (the count is deterministic).
    at_budget = model.run(DEFAULT, DEFAULT_DURATION, solver, max_rhs_evaluations=needed)
    assert at_budget.numerical == free.numerical
    assert at_budget.diagnostics == free.diagnostics
    # One less: refused, and the solve stopped there instead of finishing.
    before = count()
    with pytest.raises(ModelDomainError):
        model.run(DEFAULT, DEFAULT_DURATION, solver, max_rhs_evaluations=needed - 1)
    assert count() - before <= needed  # at most the budget plus the call that crossed it


def test_an_over_budget_solve_stops_at_the_budget_not_at_its_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unbounded, this run took 792 s (slice 2 review, item 1). With a budget of 2000 calls it
    # must stop after at most 2001 of them (the call that crosses the budget may complete).
    budget = 2000
    count = counted(monkeypatch)
    start = time.perf_counter()
    with pytest.raises(ModelDomainError):
        model.run(FAST_DRIVE, FAST_DRIVE_DURATION, TIGHT, max_rhs_evaluations=budget)
    assert count() <= budget + 1
    # 2000 Radau calls take well under a second (measured when this test was written: this
    # run at rtol = 1e-3, atol = 0.1 made 68 692 calls in 2.3 s, about 33 us each with the LU
    # factorisations); 10 s only guards against the solve running on.
    assert time.perf_counter() - start < 10.0


@pytest.mark.parametrize(("budget", "written"), [(1000, "1,000"), (1234, "1,234")])
def test_the_refusal_names_the_budget_and_the_three_remedies(budget: int, written: str) -> None:
    # Both budgets are far below what the run needs (unbounded it ran for 792 s). The number
    # is written with thousands separators ({:,}), as the 2.2 sweep's refusal is.
    with pytest.raises(ModelDomainError) as refused:
        model.run(FAST_DRIVE, FAST_DRIVE_DURATION, TIGHT, max_rhs_evaluations=budget)
    text = str(refused.value)
    assert written in text
    assert "right-hand-side evaluations" in text
    assert "looser tolerance" in text
    assert "fewer cycles" in text
    assert "another method" in text


def test_the_default_budget_is_the_constant() -> None:
    # The keyword's default is MAX_RUN_RHS_EVALUATIONS, so the API (which passes no budget)
    # enforces the measured constant. The HTTP refusal at the default budget is in
    # tests/api/test_oscillator_limits.py.
    default = inspect.signature(model.run).parameters["max_rhs_evaluations"].default
    assert default == model.MAX_RUN_RHS_EVALUATIONS


def test_the_default_budget_admits_500_cycles_at_the_default_settings() -> None:
    # N_max = 500 cycles was set from the default settings (DOP853, rtol = atol = 1e-10;
    # 0.8 to 1.4 s, slice 2): the budget must not refuse what the cycle limit was built for.
    # A free undamped run at w0 = 1 rad/s, just under 500 cycles.
    inputs = OscillatorInputs(mass=1.0, spring_constant=1.0, initial_displacement=1.0)
    duration = 500 * 2 * math.pi * (1 - 1e-9)
    result = model.run(inputs, duration, SolverSettings())
    assert result.numerical.n_rhs_evaluations <= model.MAX_RUN_RHS_EVALUATIONS


def test_the_stiffness_guard_still_refuses_before_any_solve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The budget adds a limit; it does not replace the guard (plan D6). gamma = 500 1/s,
    # (gamma + beta) T ~ 2e4 > 1e4 for RK45: refused with the guard's message, no rhs call.
    count = counted(monkeypatch)
    stiff = OscillatorInputs(
        mass=1.0, spring_constant=25.0, damping_coefficient=1000.0, initial_displacement=0.1
    )
    with pytest.raises(ModelDomainError, match="stiffness number"):
        model.run(stiff, 20.0, SolverSettings(method="RK45"), max_rhs_evaluations=10**9)
    assert count() == 0
