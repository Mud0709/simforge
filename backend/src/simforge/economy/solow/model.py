"""Orchestrates one Solow run: baseline and savings-policy scenario, plus diagnostics.

Pure computation: no HTTP, no database. The API layer adds run metadata and persistence.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo
from simforge.economy.solow import simulation as sim
from simforge.economy.solow.schemas import (
    Convergence,
    SolowParameters,
    SolowPathResponse,
    SolowRequest,
    SteadyState,
    ValidationCheck,
)

MODEL_INFO = ModelInfo(
    id="economy.solow",
    version="1.0.0",
    name="Solow growth model (discrete time)",
    description="Capital accumulation with Cobb-Douglas production, exogenous labour and "
    "technology growth, and a permanent change in the savings rate.",
)

UNITS: dict[str, str] = {
    "capital_share": "dimensionless",
    "savings_rate": "fraction of output",
    "depreciation": "fraction per year",
    "population_growth": "fraction per year",
    "technology_growth": "fraction per year",
    "initial_capital_ratio": "multiple of k*(s0)",
    "years": "year",
    "capital": "capital per effective worker (model units, A_0 = L_0 = 1)",
    "output": "output per effective worker per year (model units)",
    "consumption": "consumption per effective worker per year (model units)",
    "investment": "investment per effective worker per year (model units)",
    "output_per_worker_index": "index, year 0 = 100",
    "output_per_worker_growth": "fraction per year",
    "capital_output_ratio": "years",
    "half_life_years": "years",
}

ASSUMPTIONS: list[Assumption] = [
    Assumption(
        id="closed_one_good",
        statement="A closed economy producing one good, used for both consumption and "
        "investment. No government, trade or money: every quantity is real.",
    ),
    Assumption(
        id="cobb_douglas",
        statement="Production is Cobb-Douglas, Y = K^alpha (A L)^(1 - alpha), with constant "
        "returns to scale and diminishing returns to capital (0 < alpha < 1).",
    ),
    Assumption(
        id="exogenous_rates",
        statement="The savings rate, depreciation, population growth and technology growth "
        "are fixed numbers set outside the model. Nobody chooses them by optimising.",
    ),
    Assumption(
        id="full_employment",
        statement="All labour and capital are always fully employed; there are no business "
        "cycles, unemployment or idle capacity.",
    ),
    Assumption(
        id="annual_timing",
        statement="Time is in whole years. Output saved in year t becomes capital at the start "
        "of year t + 1, and depreciation applies to the capital of year t. The steady state "
        "therefore uses n + g + n g + delta, not the continuous-time n + g + delta.",
    ),
    Assumption(
        id="permanent_unannounced_policy",
        statement="The savings rate changes once, permanently, at the policy year. Because "
        "savings are fixed by assumption, nobody anticipates or reacts to the change.",
    ),
]

METHOD_NOTE = (
    "Paths come from iterating the exact discrete-time recurrence; there is no "
    "discretisation error, only floating-point rounding. Steady states, the golden-rule "
    "savings rate and the convergence factor rho are exact formulas. The half-life uses the "
    "linearisation around the steady state, so it is an approximation valid only close to "
    "it."
)

# Single-evaluation steady-state residual |f(k*) - k*| / k*. On the documented grid the
# worst case observed was 4 u (u = 2^-53); 1e-13 leaves a wide margin.
RESIDUAL_THRESHOLD = 1e-13
# Below this distance from the new steady state we report the path as converged.
CONVERGED_DISTANCE = 1e-6


@dataclass(frozen=True, slots=True)
class SolowComputation:
    economy: sim.SolowEconomy
    initial_capital: float
    baseline: sim.SolowPath
    scenario: sim.SolowPath
    baseline_steady_state: SteadyState
    scenario_steady_state: SteadyState
    golden_rule: SteadyState
    convergence: Convergence
    checks: list[ValidationCheck]
    elapsed_ms: float


def to_economy(p: SolowParameters) -> sim.SolowEconomy:
    return sim.SolowEconomy(
        capital_share=p.capital_share,
        depreciation=p.depreciation,
        population_growth=p.population_growth,
        technology_growth=p.technology_growth,
    )


def steady_state(e: sim.SolowEconomy, s: float) -> SteadyState:
    k = sim.steady_state_capital(e, s)
    y = math.pow(k, e.capital_share)
    return SteadyState(
        savings_rate=s,
        capital=k,
        output=y,
        consumption=(1.0 - s) * y,
        capital_output_ratio=s / sim.effective_depreciation(e),
    )


def path_response(p: sim.SolowPath) -> SolowPathResponse:
    return SolowPathResponse(
        savings_rate=p.savings_rate.tolist(),
        capital=p.capital.tolist(),
        output=p.output.tolist(),
        consumption=p.consumption.tolist(),
        investment=p.investment.tolist(),
        output_per_worker_index=p.output_per_worker_index.tolist(),
        output_per_worker_growth=p.output_per_worker_growth.tolist(),
    )


def _residual(e: sim.SolowEconomy, s: float, k_star: float) -> float:
    return abs(sim.step(e, s, k_star) / k_star - 1.0)


def _checks(
    e: sim.SolowEconomy,
    request: SolowRequest,
    baseline: sim.SolowPath,
    scenario: sim.SolowPath,
    k_star_0: float,
    k_star_1: float,
) -> list[ValidationCheck]:
    t_c = request.policy.policy_year
    s0, s1 = request.parameters.savings_rate, request.policy.new_savings_rate
    # Bit-identity before the change: k and y for t <= T_c, c and i for t < T_c.
    mismatches = int(
        np.count_nonzero(baseline.capital[: t_c + 1] != scenario.capital[: t_c + 1])
        + np.count_nonzero(baseline.consumption[:t_c] != scenario.consumption[:t_c])
    )
    distance = abs(scenario.capital[-1] / k_star_1 - 1.0)
    growth_gap = abs(float(scenario.output_per_worker_growth[-1]) - e.technology_growth)
    r0, r1 = _residual(e, s0, k_star_0), _residual(e, s1, k_star_1)
    return [
        ValidationCheck(
            id="steady_state_residual_baseline",
            label="Steady-state residual, s0",
            value=r0,
            threshold=RESIDUAL_THRESHOLD,
            passed=r0 <= RESIDUAL_THRESHOLD,
            kind="numerical_diagnostic",
            note="|f(k*) - k*| / k*: how exactly the closed-form k*(s0) is a fixed point of "
            "the recurrence in floating point.",
        ),
        ValidationCheck(
            id="steady_state_residual_scenario",
            label="Steady-state residual, s1",
            value=r1,
            threshold=RESIDUAL_THRESHOLD,
            passed=r1 <= RESIDUAL_THRESHOLD,
            kind="numerical_diagnostic",
            note="The same check for the new steady state k*(s1).",
        ),
        ValidationCheck(
            id="identical_before_policy",
            label="Baseline = scenario before the change",
            value=float(mismatches),
            threshold=0.0,
            passed=mismatches == 0,
            kind="exact_identity",
            note=f"Number of entries that differ in k_0..k_{t_c} and c_0..c_{t_c - 1}. "
            "Both paths come from the same code, so they must be bit-identical there.",
        ),
        ValidationCheck(
            id="distance_to_new_steady_state",
            label="Final distance from k*(s1)",
            value=distance,
            threshold=None,
            passed=None,
            kind="informational",
            note=(
                "Converged to within 1e-6."
                if distance < CONVERGED_DISTANCE
                else "Not yet converged: the horizon is short compared with the half-life."
            ),
        ),
        ValidationCheck(
            id="final_growth_gap",
            label="|G - g| in the final year",
            value=growth_gap,
            threshold=None,
            passed=None,
            kind="informational",
            note="Growth of output per actual worker tends to g as k tends to k*.",
        ),
    ]


def run(request: SolowRequest) -> SolowComputation:
    start = time.perf_counter()
    p, pol, horizon = request.parameters, request.policy, request.horizon_years
    e = to_economy(p)

    k_star_0 = sim.steady_state_capital(e, p.savings_rate)
    k_star_1 = sim.steady_state_capital(e, pol.new_savings_rate)
    k0 = p.initial_capital_ratio * k_star_0

    base_s = sim.savings_schedule(p.savings_rate, p.savings_rate, 0, horizon)
    scen_s = sim.savings_schedule(p.savings_rate, pol.new_savings_rate, pol.policy_year, horizon)
    baseline = sim.path_from_capital(e, base_s, sim.simulate_capital(e, base_s, k0))
    scenario = sim.path_from_capital(e, scen_s, sim.simulate_capital(e, scen_s, k0))

    # The input bounds keep every value finite (see SCIENTIFIC_VALIDATION.md); this guards
    # against a future change of bounds silently producing inf or NaN.
    for path in (baseline, scenario):
        for name in ("capital", "output", "output_per_worker_index", "output_per_worker_growth"):
            if not np.all(np.isfinite(getattr(path, name))):
                raise ModelDomainError(f"{name} overflowed for these inputs")

    gap = sim.convergence_gap(e)
    convergence = Convergence(
        effective_depreciation=sim.effective_depreciation(e),
        growth_factor=sim.growth_factor(e),
        rho=sim.convergence_factor(e),
        one_minus_rho=gap,
        half_life_years=sim.half_life(e),
    )
    assert math.isfinite(convergence.half_life_years)

    return SolowComputation(
        economy=e,
        initial_capital=k0,
        baseline=baseline,
        scenario=scenario,
        baseline_steady_state=steady_state(e, p.savings_rate),
        scenario_steady_state=steady_state(e, pol.new_savings_rate),
        golden_rule=steady_state(e, sim.golden_rule_savings_rate(e)),
        convergence=convergence,
        checks=_checks(e, request, baseline, scenario, k_star_0, k_star_1),
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )
