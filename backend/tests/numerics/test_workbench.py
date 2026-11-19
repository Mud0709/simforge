"""The model-free convergence driver and energy envelope (roadmap 2.4, slice 1, plan D1, D7).

API the builder must implement, in ``simforge.numerics.workbench``:

* ``ErrorGroup(name: str, components: tuple[int, ...], scale: float)`` (frozen dataclass):
  an error measure; at each node the error is the Euclidean norm of (numerical - exact)
  over ``components``; ``scale`` (same units) sets the round-off floor.
* ``Problem`` (frozen dataclass) with fields ``rhs: RHS``, ``y0: FloatArray``,
  ``t0: float``, ``horizon: float`` (every run integrates over [t0, t0 + horizon]),
  ``exact: Callable[[FloatArray], FloatArray]`` (node times, shape (n+1,) -> exact states,
  shape (n+1, dim)), ``groups: tuple[ErrorGroup, ...]`` and
  ``exclusion: Callable[[str, float, int], str | None]`` (method name, effective h,
  n_steps -> a reason to leave the run out of every fit, or None).
* ``run_convergence(problem: Problem, steppers: Mapping[str, Stepper],
  dt_values: Sequence[float], *, roundoff_safety: float = 100.0) -> list[MethodConvergence]``,
  one entry per stepper in mapping order. For each dt (runs ordered coarsest to finest
  whatever the input order): ``n_steps = max(1, ceil(horizon / dt * (1 - 1e-12)))``,
  ``h = horizon / n_steps``, integrate with ``integrate_fixed``. Exclusion reasons, first
  match wins: ``"diverged"``; the problem's ``exclusion`` rule; ``"error below round-off
  floor"`` when no group's max error exceeds its floor
  ``roundoff_safety * n_steps * eps * scale``. A group is in its fit iff the run has no
  exclusion reason and its max error exceeds its floor. Fits use
  ``convergence.fit_order`` and local orders ``convergence.local_orders`` (diverged runs
  count as error 0, giving None).
* ``ConvergenceRun`` fields: ``dt_requested, h, n_steps, diverged, n_completed,
  max_errors: dict[str, float | None], final_errors: dict[str, float | None],
  roundoff_floors: dict[str, float], in_fit: dict[str, bool], exclusion_reason: str | None``
  (error dicts keyed by group name; None when diverged).
* ``MethodConvergence`` fields: ``method: str, runs: list[ConvergenceRun],
  local_orders: dict[str, list[float | None]], fits: dict[str, OrderFit | None]``.
* ``energy_envelope(t: FloatArray, values: FloatArray, max_bins: int = 200) ->
  EnergyEnvelope`` with float arrays ``t_start, t_end, lo, hi`` (one entry per bin): the
  nodes are split into ``min(len(t), max_bins)`` contiguous, non-empty, ordered bins
  covering every node; ``lo``/``hi`` are the min/max of ``values`` in the bin and
  ``t_start``/``t_end`` its first and last node time. ``ValueError`` whose message contains
  "max_bins" for ``max_bins < 1``, "empty" for no nodes and "length" for mismatched lengths.

References: a synthetic problem whose error law is exactly C T h^p by construction (the
stepper adds c h^(p+1) per step to the exact increment), and brute-force min/max per bin.
"""

from __future__ import annotations

import numpy as np
import pytest
from simforge.numerics.workbench import (
    ErrorGroup,
    Problem,
    energy_envelope,
    run_convergence,
)

from tests.approx import rel_approx

EPS = float(np.finfo(np.float64).eps)
P_A, C_A = 3, 0.5  # component "a": error c_a T h^3
P_B, C_B = 2, 0.25  # component "b": error c_b T h^2
HORIZON = 1.0
DT_VALUES = [0.1 / 2**i for i in range(6)]  # 0.1 ... 0.003125, all give n = horizon/dt


def rhs(_t: float, _y: np.ndarray) -> np.ndarray:
    return np.array([1.0, 2.0])


def exact(t: np.ndarray) -> np.ndarray:
    return np.column_stack([t, 2.0 * t])


def law_step(f, t: float, y: np.ndarray, h: float) -> np.ndarray:  # type: ignore[no-untyped-def]
    """Exact increment plus (c_a h^(p+1), c_b h^(q+1)): after n steps the error is
    n c h^(p+1), largest at n = N = T/h, where it equals c T h^p exactly (up to rounding)."""
    return y + h * f(t, y) + np.array([C_A * h ** (P_A + 1), C_B * h ** (P_B + 1)])


def exact_step(f, t: float, y: np.ndarray, h: float) -> np.ndarray:  # type: ignore[no-untyped-def]
    return y + h * f(t, y)


def blowup_step(_f, _t: float, y: np.ndarray, _h: float) -> np.ndarray:  # type: ignore[no-untyped-def]
    return (y + 1.0) * 1e60  # passes DIVERGENCE_THRESHOLD (1e100) on the second step


def make_problem(exclusion) -> Problem:  # type: ignore[no-untyped-def]
    return Problem(
        rhs=rhs,
        y0=np.array([0.0, 0.0]),
        t0=0.0,
        horizon=HORIZON,
        exact=exact,
        groups=(ErrorGroup("a", (0,), 1.0), ErrorGroup("b", (1,), 2.0)),
        exclusion=exclusion,
    )


def no_exclusion(_method: str, _h: float, _n: int) -> str | None:
    return None


def test_driver_recovers_the_error_law_and_orders() -> None:
    """Accumulated rounding is at most ~N eps ~ 7e-14 absolute against errors >= 1.5e-8, so
    the errors match c T h^p to rel 1e-4 (~20x margin over 5e-6) and the slopes to 1e-4."""
    shuffled = [DT_VALUES[i] for i in (3, 0, 5, 1, 4, 2)]
    (study,) = run_convergence(make_problem(no_exclusion), {"law": law_step}, shuffled)
    assert study.method == "law"
    assert [r.dt_requested for r in study.runs] == DT_VALUES  # coarsest to finest
    for r in study.runs:
        assert r.n_steps == round(HORIZON / r.dt_requested)
        assert r.h == HORIZON / r.n_steps
        assert not r.diverged
        assert r.n_completed == r.n_steps
        assert r.exclusion_reason is None
        assert r.in_fit == {"a": True, "b": True}
        assert r.max_errors["a"] == rel_approx(C_A * HORIZON * r.h**P_A, rel=1e-4)
        assert r.max_errors["b"] == rel_approx(C_B * HORIZON * r.h**P_B, rel=1e-4)
        assert r.final_errors["a"] == rel_approx(C_A * HORIZON * r.h**P_A, rel=1e-4)
        assert r.roundoff_floors["a"] == rel_approx(100.0 * r.n_steps * EPS * 1.0, rel=EPS)
        assert r.roundoff_floors["b"] == rel_approx(100.0 * r.n_steps * EPS * 2.0, rel=EPS)
    fit_a, fit_b = study.fits["a"], study.fits["b"]
    assert fit_a is not None
    assert fit_b is not None
    assert fit_a.n_points == fit_b.n_points == len(DT_VALUES)
    assert fit_a.order == pytest.approx(P_A, abs=1e-4)
    assert fit_b.order == pytest.approx(P_B, abs=1e-4)
    assert len(study.local_orders["a"]) == len(DT_VALUES) - 1
    for p in study.local_orders["a"]:
        assert p == pytest.approx(P_A, abs=1e-4)


def test_steps_round_up_so_the_horizon_is_hit_exactly() -> None:
    (study,) = run_convergence(make_problem(no_exclusion), {"law": law_step}, [0.3, 0.1])
    coarse, fine = study.runs
    assert (coarse.n_steps, coarse.h) == (4, 0.25)
    assert fine.n_steps == 10  # 1/0.1 is 10 to within rounding, not 11


def test_supplied_exclusion_rule_is_applied_per_method() -> None:
    def rule(method: str, h: float, _n: int) -> str | None:
        return f"too coarse for {method}" if method == "law" and h > 0.03 else None

    law, copy = run_convergence(
        make_problem(rule), {"law": law_step, "law_copy": law_step}, DT_VALUES
    )
    excluded = [r for r in law.runs if r.exclusion_reason is not None]
    assert [r.h for r in excluded] == [0.1, 0.05]
    for r in excluded:
        assert r.exclusion_reason == "too coarse for law"
        assert r.in_fit == {"a": False, "b": False}
        assert r.max_errors["a"] is not None  # still measured and reported
    fit = law.fits["a"]
    assert fit is not None
    assert fit.n_points == 4
    assert fit.h_max == 0.025
    assert fit.order == pytest.approx(P_A, abs=1e-4)
    copy_fit = copy.fits["a"]
    assert copy_fit is not None
    assert copy_fit.n_points == len(DT_VALUES)
    assert all(r.exclusion_reason is None for r in copy.runs)


def test_diverged_runs_are_excluded_before_the_supplied_rule() -> None:
    def rule(_method: str, _h: float, _n: int) -> str | None:
        return "rule"

    (study,) = run_convergence(make_problem(rule), {"blowup": blowup_step}, DT_VALUES[:3])
    for r in study.runs:
        assert r.diverged
        assert r.n_completed < r.n_steps
        assert r.exclusion_reason == "diverged"
        assert r.max_errors == {"a": None, "b": None}
        assert r.final_errors == {"a": None, "b": None}
        assert r.in_fit == {"a": False, "b": False}
    assert study.fits == {"a": None, "b": None}
    assert study.local_orders["a"] == [None, None]


def test_errors_below_the_roundoff_floor_are_excluded() -> None:
    (study,) = run_convergence(make_problem(no_exclusion), {"exact": exact_step}, DT_VALUES)
    for r in study.runs:
        assert r.exclusion_reason == "error below round-off floor"
        assert r.in_fit == {"a": False, "b": False}
    assert study.fits == {"a": None, "b": None}


# --- Energy envelope ----------------------------------------------------------------------


@pytest.mark.parametrize(("n", "max_bins"), [(1001, 200), (200, 200), (57, 200), (450, 7)])
def test_envelope_keeps_each_bins_min_and_max(n: int, max_bins: int) -> None:
    rng = np.random.default_rng(7)
    t = 0.05 * np.arange(n)
    values = 1e-3 * rng.standard_normal(n)
    values[n // 3] = 5.0  # isolated spikes must survive binning
    values[-1] = -4.0
    env = energy_envelope(t, values, max_bins)
    k = min(n, max_bins)
    assert len(env.t_start) == len(env.t_end) == len(env.lo) == len(env.hi) == k
    assert env.t_start[0] == t[0]
    assert env.t_end[-1] == t[-1]
    assert np.all(env.t_start <= env.t_end)
    assert np.all(env.t_end[:-1] < env.t_start[1:])  # ordered, disjoint
    covered = 0
    for i in range(k):
        mask = (t >= env.t_start[i]) & (t <= env.t_end[i])
        assert mask.any()
        covered += int(mask.sum())
        assert env.lo[i] == values[mask].min()
        assert env.hi[i] == values[mask].max()
    assert covered == n  # contiguous bins cover every node exactly once
    assert env.hi.max() == 5.0
    assert env.lo.min() == -4.0


def test_envelope_rejects_bad_input() -> None:
    t = np.arange(5.0)
    with pytest.raises(ValueError, match="max_bins"):
        energy_envelope(t, np.zeros(5), 0)
    with pytest.raises(ValueError, match="length"):
        energy_envelope(t, np.zeros(4), 3)
    with pytest.raises(ValueError, match="empty"):
        energy_envelope(np.array([]), np.array([]), 3)
