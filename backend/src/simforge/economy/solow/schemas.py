"""Validated API contract for the Solow growth model.

Rates are fractions per year (0.02 = 2% per year) everywhere: the API never converts
percentages, so identical inputs always hash identically. Bounds keep every run inside the
range where the model's steady state exists and every quantity stays far from float64
overflow and underflow (see SCIENTIFIC_VALIDATION.md); they are not claims about which
values are economically realistic.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from simforge.core.schemas import Assumption, ModelInfo, RunMetadata, StrictModel

# Below this lambda = n + g + n g + delta, convergence is so slow (1 / (1 - rho) up to ~2e4
# years) and k* so large that runs stop being informative. Also the bound that, with
# alpha <= 0.95, keeps k* below ~1e60.
MIN_EFFECTIVE_DEPRECIATION = 1e-3


class SolowParameters(StrictModel):
    capital_share: float = Field(
        default=0.3,
        ge=0.05,
        le=0.95,
        description="Capital share alpha in Y = K^alpha (A L)^(1 - alpha). Dimensionless.",
    )
    savings_rate: float = Field(
        default=0.2,
        ge=0.01,
        le=0.99,
        description="Savings rate s0 before the policy change: share of output invested.",
    )
    depreciation: float = Field(
        default=0.05, ge=0, le=1, description="Depreciation rate delta, fraction per year."
    )
    population_growth: float = Field(
        default=0.01, ge=-0.05, le=0.1, description="Labour growth rate n, fraction per year."
    )
    technology_growth: float = Field(
        default=0.02, ge=0, le=0.1, description="Technology growth rate g, fraction per year."
    )
    initial_capital_ratio: float = Field(
        default=0.5,
        ge=0.01,
        le=10,
        description="Initial capital per effective worker as a multiple of the baseline "
        "steady state k*(s0). 1 starts at the steady state.",
    )

    @model_validator(mode="after")
    def _steady_state_must_exist(self) -> Self:
        n, g, d = self.population_growth, self.technology_growth, self.depreciation
        lam = n + g + n * g + d
        # The relative slack lets inputs whose exact sum is the bound (e.g. n = -0.05,
        # delta = 0.051) pass even though float rounding puts the sum a few ulps below it.
        if lam < MIN_EFFECTIVE_DEPRECIATION * (1 - 1e-12):
            raise ValueError(
                f"n + g + n*g + delta = {lam:.6g} is below {MIN_EFFECTIVE_DEPRECIATION:g}: "
                "capital per effective worker would not settle at a steady state within any "
                "useful horizon. Raise depreciation, population growth or technology growth."
            )
        return self


class SavingsPolicy(StrictModel):
    new_savings_rate: float = Field(
        default=0.3,
        ge=0.01,
        le=0.99,
        description="Savings rate s1 from the policy year onwards. Equal to s0 means no change.",
    )
    policy_year: int = Field(
        default=20,
        ge=0,
        le=499,
        description="First year t whose output is saved at s1. It first changes capital in "
        "year t + 1. Must be below horizon_years.",
    )


class SolowRequest(StrictModel):
    parameters: SolowParameters = Field(default_factory=SolowParameters)
    policy: SavingsPolicy = Field(default_factory=SavingsPolicy)
    horizon_years: int = Field(
        default=100, ge=1, le=500, description="Number of years simulated (t = 0..H)."
    )
    save_experiment: bool = True

    @model_validator(mode="after")
    def _policy_inside_horizon(self) -> Self:
        if self.policy.policy_year >= self.horizon_years:
            raise ValueError(
                f"policy_year ({self.policy.policy_year}) must be below horizon_years "
                f"({self.horizon_years}) so the change is visible"
            )
        return self


class SolowPathResponse(StrictModel):
    """One scenario, t = 0..H. Per effective worker unless stated."""

    savings_rate: list[float]
    capital: list[float]
    output: list[float]
    consumption: list[float]
    investment: list[float]
    output_per_worker_index: list[float] = Field(
        description="Output per actual worker, Y/L, as an index with year 0 = 100."
    )
    output_per_worker_growth: list[float] = Field(
        description="G_t = (Y/L)_{t+1} / (Y/L)_t - 1 for t = 0..H-1, fraction per year."
    )


class SteadyState(StrictModel):
    savings_rate: float
    capital: float
    output: float
    consumption: float
    capital_output_ratio: float = Field(description="k*/y* = s/lambda, in years.")


class Convergence(StrictModel):
    effective_depreciation: float = Field(description="lambda = n + g + n g + delta, per year.")
    growth_factor: float = Field(description="D = (1 + n)(1 + g), per year.")
    rho: float = Field(description="Local convergence factor f'(k*) per year (0 < rho < 1).")
    one_minus_rho: float = Field(description="(1 - alpha) lambda / D, computed directly.")
    half_life_years: float = Field(
        description="ln 0.5 / ln rho. A linearisation: valid only close to the steady state."
    )


class ValidationCheck(StrictModel):
    """A diagnostic of this run. Proofs and grid evidence live in the tests and docs."""

    id: str
    label: str
    value: float
    threshold: float | None = Field(description="Pass if value <= threshold; None = info only.")
    passed: bool | None
    kind: Literal["exact_identity", "numerical_diagnostic", "informational"]
    note: str


class SolowResponse(StrictModel):
    model: ModelInfo
    parameters: SolowParameters
    policy: SavingsPolicy
    horizon_years: int
    units: dict[str, str]
    assumptions: list[Assumption]
    years: list[int]
    baseline: SolowPathResponse
    scenario: SolowPathResponse
    baseline_steady_state: SteadyState
    scenario_steady_state: SteadyState
    golden_rule: SteadyState
    convergence: Convergence
    initial_capital: float = Field(description="k_0, per effective worker.")
    checks: list[ValidationCheck]
    method_note: str
    metadata: RunMetadata
