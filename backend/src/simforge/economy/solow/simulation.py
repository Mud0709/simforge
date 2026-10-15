"""Discrete-time Solow growth model: the pure engine.

No HTTP, no database, no Pydantic. Plain floats in, plain floats and NumPy arrays out.

Model
-----
Production is Cobb-Douglas with labour-augmenting technology,
``Y_t = K_t^alpha (A_t L_t)^(1 - alpha)``, with ``L_{t+1} = (1 + n) L_t`` and
``A_{t+1} = (1 + g) A_t``. A share ``s_t`` of year-t output is invested and becomes capital
at the start of year t + 1; depreciation applies to ``K_t``:
``K_{t+1} = s_t Y_t + (1 - delta) K_t``.

Dividing by ``A_{t+1} L_{t+1} = D A_t L_t`` with ``D = (1 + n)(1 + g)`` gives the
recurrence for capital per effective worker ``k = K / (A L)``:

    k_{t+1} = f(k_t) = (s_t k_t^alpha + (1 - delta) k_t) / D

Steady state and convergence (exact consequences of the recurrence)
-------------------------------------------------------------------
With ``lambda = n + g + n g + delta`` (= D - (1 - delta)):

* ``k* = (s / lambda)^(1 / (1 - alpha))``, the unique positive fixed point when
  ``lambda > 0``.
* ``rho = f'(k*) = (alpha lambda + 1 - delta) / D`` and ``1 - rho = (1 - alpha) lambda / D``.
  ``0 < rho < 1``.

Numerical notes
---------------
* ``lambda`` is computed as ``n + g + n g + delta``, never as ``(1 + n)(1 + g) - (1 - delta)``.
  The subtraction cancels catastrophically when the rates are small (it lost ~900x the
  achievable precision on the validation grid; see SCIENTIFIC_VALIDATION.md).
* ``1 - rho`` is computed directly from ``(1 - alpha) lambda / D`` for the same reason, and
  the half-life uses ``log1p(-(1 - rho))``.
* Paths are produced by a single scalar loop (:func:`simulate_capital`) for every
  scenario, so two paths that share a savings-rate prefix are bit-identical over it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class SolowEconomy:
    """Structural parameters. Rates are fractions per year (0.02 means 2% per year)."""

    capital_share: float  # alpha, in (0, 1)
    depreciation: float  # delta, in [0, 1]
    population_growth: float  # n, > -1
    technology_growth: float  # g, > -1


def growth_factor(e: SolowEconomy) -> float:
    """D = (1 + n)(1 + g): growth factor of effective labour A L per year."""
    return (1.0 + e.population_growth) * (1.0 + e.technology_growth)


def effective_depreciation(e: SolowEconomy) -> float:
    """lambda = n + g + n g + delta, computed without cancellation."""
    n, g = e.population_growth, e.technology_growth
    return n + g + n * g + e.depreciation


def step(e: SolowEconomy, savings_rate: float, k: float) -> float:
    """One year of the recurrence: k_{t+1} = (s k^alpha + (1 - delta) k) / D."""
    return (
        savings_rate * math.pow(k, e.capital_share) + (1.0 - e.depreciation) * k
    ) / growth_factor(e)


def steady_state_capital(e: SolowEconomy, savings_rate: float) -> float:
    """k* = (s / lambda)^(1 / (1 - alpha)). Requires lambda > 0."""
    lam = effective_depreciation(e)
    if not lam > 0:
        raise ValueError(f"no positive steady state: lambda = {lam!r} must be > 0")
    return math.pow(savings_rate / lam, 1.0 / (1.0 - e.capital_share))


def golden_rule_savings_rate(e: SolowEconomy) -> float:
    """The savings rate that maximises steady-state consumption per effective worker: alpha."""
    return e.capital_share


def convergence_gap(e: SolowEconomy) -> float:
    """1 - rho = (1 - alpha) lambda / D, computed directly (no 1 - rho subtraction)."""
    return (1.0 - e.capital_share) * effective_depreciation(e) / growth_factor(e)


def convergence_factor(e: SolowEconomy) -> float:
    """rho = f'(k*) = (alpha lambda + 1 - delta) / D, the local contraction factor."""
    lam = effective_depreciation(e)
    return (e.capital_share * lam + 1.0 - e.depreciation) / growth_factor(e)


def half_life(e: SolowEconomy) -> float:
    """Years for a small deviation from k* to halve, from the linearisation: ln 0.5 / ln rho.

    An approximation: valid only near k*.
    """
    return math.log(0.5) / math.log1p(-convergence_gap(e))


def savings_schedule(
    initial_rate: float, new_rate: float, policy_year: int, horizon: int
) -> list[float]:
    """s_t for t = 0..horizon: ``initial_rate`` for t < policy_year, ``new_rate`` after.

    ``s_t`` is the share of year-t output that is saved, so it first affects ``k_{t+1}``.
    """
    if not 0 <= policy_year <= horizon:
        raise ValueError("policy_year must lie in [0, horizon]")
    return [initial_rate if t < policy_year else new_rate for t in range(horizon + 1)]


def simulate_capital(e: SolowEconomy, savings: Sequence[float], k0: float) -> FloatArray:
    """k_0..k_H for the schedule ``savings`` (length H + 1; its last entry is not used).

    A plain Python loop over floats on purpose: every scenario goes through this one code
    path, so equal inputs give bit-identical outputs.
    """
    if not (k0 > 0 and math.isfinite(k0)):
        raise ValueError("k0 must be positive and finite")
    k = [k0]
    for s in savings[:-1]:
        k.append(step(e, s, k[-1]))
    return np.array(k, dtype=np.float64)


@dataclass(frozen=True, slots=True)
class SolowPath:
    """One scenario, for t = 0..H. Per-effective-worker quantities unless stated."""

    savings_rate: FloatArray  # s_t
    capital: FloatArray  # k_t
    output: FloatArray  # y_t = k_t^alpha
    consumption: FloatArray  # c_t = (1 - s_t) y_t
    investment: FloatArray  # i_t = s_t y_t
    output_per_worker_index: FloatArray  # 100 (Y/L)_t / (Y/L)_0; A_t grows at rate g
    output_per_worker_growth: FloatArray  # G_t, t = 0..H-1


def path_from_capital(e: SolowEconomy, savings: Sequence[float], k: FloatArray) -> SolowPath:
    """Derived quantities for a capital path ``k`` produced by ``savings``."""
    s = np.array(savings, dtype=np.float64)
    a, g = e.capital_share, e.technology_growth
    y = k**a
    t = np.arange(len(k), dtype=np.float64)
    # (Y/L)_t = A_t y_t with A_t = A_0 (1 + g)^t; normalised so year 0 is 100.
    index = 100.0 * (1.0 + g) ** t * (y / y[0])
    # G_t = (Y/L)_{t+1} / (Y/L)_t - 1 = (1 + g) (k_{t+1} / k_t)^alpha - 1, from k directly.
    growth = (1.0 + g) * (k[1:] / k[:-1]) ** a - 1.0
    return SolowPath(
        savings_rate=s,
        capital=k,
        output=y,
        consumption=(1.0 - s) * y,
        investment=s * y,
        output_per_worker_index=index,
        output_per_worker_growth=growth,
    )
