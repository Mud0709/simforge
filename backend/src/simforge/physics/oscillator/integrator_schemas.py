"""Validated API contract for the oscillator methods study (roadmap 2.4, plan D8, D14).

Units are part of the contract: every field states its SI unit. The single-field bounds and
the w0 range are the oscillator's (``oscillator.schemas``). The step caps depend on the
number of steps, so they are checked by ``integrator_model.run`` (422, naming N).
"""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from simforge.core.schemas import Assumption, ModelInfo, RunMetadata, StrictModel, ValidationCheck
from simforge.physics.oscillator.schemas import (
    MAX_NATURAL_ANGULAR_FREQUENCY,
    MIN_NATURAL_ANGULAR_FREQUENCY,
)
from simforge.physics.projectile.integrator_schemas import OrderFitResult
from simforge.physics.projectile.schemas import MIN_MASS

MethodName = Literal["euler", "rk4", "symplectic_euler", "velocity_verlet"]
ALL_METHODS: tuple[MethodName, ...] = ("euler", "rk4", "symplectic_euler", "velocity_verlet")
# A diverged state reaches |x|, |v| ~ 1e100, so E ~ x^2 + (v/w)^2 <= 1e206 m^2 (w >= 1e-3 rad/s);
# X >= 1e-50 m keeps E/E_0 <= 1e306, finite in float64.
MIN_AMPLITUDE = 1e-50  # m
Step = Annotated[float, Field(gt=0, le=1e4, description="Requested time step in s.")]


class OscillatorIntegratorParameters(StrictModel):
    """Undamped, undriven oscillator, SI units. Defaults: w0 = 5 rad/s, x0 = 0.1 m."""

    mass: float = Field(default=1.0, ge=MIN_MASS, le=1e6, description="Mass m in kg.")
    spring_constant: float = Field(
        default=25.0, ge=1e-6, le=1e9, description="Spring constant k in N/m."
    )
    initial_displacement: float = Field(
        default=0.1, ge=-1e3, le=1e3, description="Displacement x0 at t = 0, in m."
    )
    initial_velocity: float = Field(
        default=0.0, ge=-1e4, le=1e4, description="Velocity v0 at t = 0, in m/s."
    )

    @model_validator(mode="after")
    def _combined_rules(self) -> Self:
        w0 = math.sqrt(self.spring_constant / self.mass)
        if not MIN_NATURAL_ANGULAR_FREQUENCY <= w0 <= MAX_NATURAL_ANGULAR_FREQUENCY:
            raise ValueError(
                f"the natural angular frequency w0 = sqrt(k/m) = {w0:.3g} rad/s must be from "
                f"{MIN_NATURAL_ANGULAR_FREQUENCY:g} to {MAX_NATURAL_ANGULAR_FREQUENCY:g} rad/s; "
                "change spring_constant or mass"
            )
        if self.initial_displacement == self.initial_velocity == 0:
            raise ValueError(
                "nothing moves: initial_displacement and initial_velocity are both 0, so there "
                "is no energy to measure; set at least one of them"
            )
        amplitude = math.hypot(self.initial_displacement, self.initial_velocity / w0)
        if amplitude < MIN_AMPLITUDE:
            raise ValueError(
                f"the amplitude X = sqrt(x0^2 + (v0/w0)^2) = {amplitude:.3g} m is below "
                f"{MIN_AMPLITUDE:g} m (energy ratios would overflow); raise "
                "initial_displacement or initial_velocity"
            )
        return self


class OscillatorIntegratorRequest(StrictModel):
    parameters: OscillatorIntegratorParameters = Field(
        default_factory=OscillatorIntegratorParameters
    )
    dt_values: list[Step] = Field(
        default_factory=lambda: [0.04 / 2**i for i in range(8)],
        min_length=2,
        max_length=12,
        description="Requested time steps (s) of the order study over one period T. Each run "
        "uses h = T/N with N = ceil(T/dt), so that every run ends exactly at T.",
    )
    methods: list[MethodName] = Field(
        default_factory=lambda: list(ALL_METHODS), min_length=1, max_length=4
    )
    energy_dt: Step = Field(default=0.05, description="Time step (s) of the long energy run.")
    periods: int = Field(default=200, ge=1, le=1000, description="Length of the long run.")
    save_experiment: bool = True

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(set(self.dt_values)) != len(self.dt_values):
            raise ValueError("dt_values must not contain duplicates")
        if len(set(self.methods)) != len(self.methods):
            raise ValueError("methods must not contain duplicates")
        return self


class OscillatorIntegratorRun(StrictModel):
    dt_requested: float = Field(description="s")
    h: float = Field(description="Effective step T/N, s. Convergence is fitted against this.")
    n_steps: int
    theta: float = Field(description="w h, dimensionless (rad per step at small w h)")
    diverged: bool
    n_completed: int
    max_position_error: float | None = Field(description="m; null if the run diverged")
    max_velocity_error: float | None = Field(description="m/s; null if the run diverged")
    max_scaled_error: float | None = Field(
        description="max over the nodes of sqrt((x - x_exact)^2 + ((v - v_exact)/w)^2) / X, "
        "dimensionless; the fitted error. Null if the run diverged"
    )
    in_fit: bool
    exclusion_reason: str | None


class OscillatorMethodResult(StrictModel):
    method: MethodName
    theoretical_order: int
    runs: list[OscillatorIntegratorRun] = Field(description="Coarsest to finest step.")
    fit: OrderFitResult | None = Field(description="Order fitted to max_scaled_error vs h.")


class EnergyEnvelopeSeries(StrictModel):
    """Min and max of (E_n - E_0)/E_0 in at most 200 contiguous bins of nodes."""

    t_start: list[float] = Field(description="s")
    t_end: list[float] = Field(description="s")
    lo: list[float]
    hi: list[float]


class OscillatorEnergyRun(StrictModel):
    method: MethodName
    h: float = Field(description="s")
    theta: float = Field(description="w h, dimensionless")
    n_steps: int
    diverged: bool
    diverged_at_step: int | None
    n_completed: int
    final_energy_ratio: float | None = Field(description="E_N/E_0; null if diverged")
    max_relative_energy_error: float = Field(description="max |E_n - E_0|/E_0, completed nodes")
    energy_bound: float | None = Field(
        description="Proved bound R5 on |E_n - E_0|/E_0 (symplectic methods, w h < 2)"
    )
    modified_energy_residual: float | None = Field(
        description="max |H~_n - H~_0|/|H~_0| (symplectic methods); exactly 0 in exact arithmetic"
    )
    envelope: EnergyEnvelopeSeries


class OscillatorFitRule(StrictModel):
    max_theta: float
    max_amplitude_growth: float
    roundoff_safety_factor: float
    min_points: int
    description: str


class OscillatorIntegratorResponse(StrictModel):
    model: ModelInfo
    parameters: OscillatorIntegratorParameters
    dt_values: list[float]
    methods: list[MethodName]
    energy_dt: float = Field(description="s")
    periods: int
    units: dict[str, str]
    assumptions: list[Assumption]
    angular_frequency: float = Field(description="w = sqrt(k/m), rad/s")
    period: float = Field(description="T = 2 pi / w, s")
    amplitude_scale: float = Field(description="X = sqrt(x0^2 + (v0/w)^2), m")
    fit_rule: OscillatorFitRule
    results: list[OscillatorMethodResult]
    energy: list[OscillatorEnergyRun]
    checks: list[ValidationCheck]
    metadata: RunMetadata
