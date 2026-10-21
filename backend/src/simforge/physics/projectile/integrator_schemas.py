"""Validated API contract for the integrator comparison study."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from simforge.core.schemas import Assumption, ModelInfo, RunMetadata, StrictModel
from simforge.physics.projectile.integrator_study import MethodName
from simforge.physics.projectile.schemas import ProjectileParameters

ALL_METHODS: tuple[MethodName, ...] = ("euler", "rk4", "verlet")
PositiveStep = Annotated[float, Field(ge=1e-9, le=100, description="Requested time step in s.")]

DEFAULT_DT_VALUES = [0.2 / 2**i for i in range(8)]  # 0.2 s down to 0.0015625 s, halving


def _default_study_parameters() -> ProjectileParameters:
    # Stronger drag than the simulator default (b = 0.1), so the e^{-kt} part of the
    # solution, which the integrators must actually approximate, is not negligible.
    return ProjectileParameters(drag_coefficient=1.0)


class IntegratorStudyRequest(StrictModel):
    parameters: ProjectileParameters = Field(default_factory=_default_study_parameters)
    dt_values: list[PositiveStep] = Field(
        default_factory=lambda: list(DEFAULT_DT_VALUES),
        min_length=2,
        max_length=12,
        description="Requested time steps (s). Each run uses h = T/N with N = ceil(T/dt), so "
        "that every run ends exactly at the horizon T.",
    )
    methods: list[MethodName] = Field(
        default_factory=lambda: list(ALL_METHODS), min_length=1, max_length=3
    )
    save_experiment: bool = True

    @model_validator(mode="after")
    def _check(self) -> Self:
        self.parameters.check_flies()
        # b > 0 is not enough: a tiny b over a large m makes k = b/m underflow to exactly 0.
        # (A tiny but nonzero k is allowed: the fit rule then excludes every run as marginal,
        # so no convergence order is reported.)
        if self.parameters.drag_coefficient / self.parameters.mass == 0:
            raise ValueError(
                "the integrator study requires a nonzero drag rate k = b/m (b = 0, or b so "
                "small that b/m rounds to 0): in vacuum the exact "
                "solution is a parabola, which RK4 and Verlet reproduce exactly, so their "
                "errors are pure round-off and no convergence order can be measured"
            )
        if len(set(self.dt_values)) != len(self.dt_values):
            raise ValueError("dt_values must not contain duplicates")
        if len(set(self.methods)) != len(self.methods):
            raise ValueError("methods must not contain duplicates")
        return self


class IntegratorRun(StrictModel):
    dt_requested: float = Field(description="s")
    h: float = Field(description="Effective step T/N, s. Convergence is fitted against this.")
    n_steps: int
    kh: float = Field(description="Step size in units of the drag time 1/k (dimensionless).")
    amplification_factor: float = Field(description="R(-kh), per-step velocity amplification.")
    stability: Literal["stable", "marginal", "unstable"]
    diverged: bool
    n_completed: int
    max_position_error: float | None = Field(description="m; null if the run diverged")
    max_velocity_error: float | None = Field(description="m/s; null if the run diverged")
    final_position_error: float | None = Field(description="m, at t = T")
    final_velocity_error: float | None = Field(description="m/s, at t = T")
    position_roundoff_floor: float = Field(description="m")
    velocity_roundoff_floor: float = Field(description="m/s")
    in_position_fit: bool
    in_velocity_fit: bool
    exclusion_reason: str | None


class OrderFitResult(StrictModel):
    order: float = Field(description="Least-squares slope of log10(error) against log10(h).")
    theoretical_order: int
    r_squared: float
    n_points: int
    h_min: float = Field(description="s")
    h_max: float = Field(description="s")


class ReferenceLine(StrictModel):
    """A line of the *theoretical* slope through the finest point in the fit range.
    It is a visual guide, not a fit."""

    order: int
    h: list[float]
    error: list[float]


class TrajectorySample(StrictModel):
    h: float = Field(description="Step size of the plotted run, s")
    x: list[float]
    y: list[float]


class MethodStudyResult(StrictModel):
    method: MethodName
    name: str
    theoretical_order: int
    stability_limit_kh: float | None = Field(
        description="Largest kh for which |R(-kh)| <= 1; null if stable for every kh."
    )
    runs: list[IntegratorRun] = Field(description="Ordered from coarsest to finest step.")
    position_local_orders: list[float | None]
    velocity_local_orders: list[float | None]
    position_fit: OrderFitResult | None
    velocity_fit: OrderFitResult | None
    position_reference: ReferenceLine | None
    velocity_reference: ReferenceLine | None
    fit_note: str | None = Field(description="Why no order was fitted, if none was.")
    trajectory: TrajectorySample | None = Field(
        description="Coarsest linearly stable, non-divergent run, for plotting."
    )


class FitRule(StrictModel):
    max_kh: float
    max_h_over_horizon: float
    roundoff_safety_factor: float
    min_points: int
    description: str


class XYSeries(StrictModel):
    x: list[float]
    y: list[float]


class IntegratorStudyResponse(StrictModel):
    model: ModelInfo
    parameters: ProjectileParameters
    dt_values: list[float]
    methods: list[MethodName]
    units: dict[str, str]
    assumptions: list[Assumption]
    horizon: float = Field(description="Exact flight time T (s); every run covers [0, T].")
    k: float = Field(description="Drag rate b/m, 1/s")
    position_scale: float = Field(description="max |r| of the exact solution, m")
    velocity_scale: float = Field(description="max |v| of the exact solution, m/s")
    fit_rule: FitRule
    results: list[MethodStudyResult]
    exact_trajectory: XYSeries
    metadata: RunMetadata
