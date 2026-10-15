"""Validated API contract for the projectile model.

Bounds are chosen to keep runs physically meaningful *and* computationally bounded;
they are not claims about where the physics stops being valid (see ``ASSUMPTIONS``).
Units are part of the contract: every field name and description states its SI unit.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from simforge.core.schemas import Assumption, ModelInfo, RunMetadata, StrictModel


class ProjectileParameters(StrictModel):
    initial_speed: float = Field(
        default=20.0, gt=0, le=1e4, description="Launch speed |v0| in m/s."
    )
    launch_angle_deg: float = Field(
        default=45.0, ge=0, le=90, description="Launch angle above the horizontal, in degrees."
    )
    launch_height: float = Field(
        default=0.0, ge=0, le=1e5, description="Height of the launch point above the ground, in m."
    )
    mass: float = Field(default=1.0, gt=0, le=1e6, description="Projectile mass in kg.")
    drag_coefficient: float = Field(
        default=0.1,
        ge=0,
        le=1e6,
        description="Linear drag coefficient b in kg/s (drag force F = -b v). 0 means vacuum.",
    )
    gravity: float = Field(
        default=9.80665,
        ge=0.01,
        le=1000,
        description="Gravitational acceleration in m/s^2 (default: standard gravity).",
    )

    @model_validator(mode="after")
    def _projectile_must_fly(self) -> Self:
        if self.launch_height == 0 and self.launch_angle_deg == 0:
            raise ValueError(
                "launch_angle_deg = 0 with launch_height = 0 gives zero flight time; "
                "raise the angle or the launch height"
            )
        return self


class SolverSettings(StrictModel):
    method: Literal["RK45", "DOP853", "Radau"] = Field(
        default="DOP853",
        description="SciPy solve_ivp method. RK45: Dormand-Prince 5(4). DOP853: 8th-order "
        "Dormand-Prince. Radau: implicit, for stiff problems (very strong drag).",
    )
    rtol: float = Field(default=1e-10, ge=1e-13, le=1e-3, description="Relative tolerance.")
    atol: float = Field(
        default=1e-10, ge=1e-14, le=1e-1, description="Absolute tolerance (state units)."
    )


class ProjectileRequest(StrictModel):
    parameters: ProjectileParameters = Field(default_factory=ProjectileParameters)
    solver: SolverSettings = Field(default_factory=SolverSettings)
    n_samples: int = Field(
        default=400, ge=10, le=5000, description="Number of points in the resampled series."
    )
    save_experiment: bool = Field(
        default=True, description="Record inputs and summary metrics in the experiment log."
    )


class TrajectoryMetrics(StrictModel):
    flight_time: float = Field(description="s")
    range: float = Field(description="Horizontal distance at landing, m")
    max_height: float = Field(description="m")
    apex_time: float = Field(description="s")
    impact_speed: float = Field(description="m/s")


class AnalyticalResult(TrajectoryMetrics):
    method_note: str


class NumericalResult(TrajectoryMetrics):
    method: str
    rtol: float
    atol: float
    n_steps: int
    n_rhs_evaluations: int


class ErrorMetric(StrictModel):
    absolute: float
    relative: float | None = Field(
        description="|numerical - analytical| / |analytical|; null when the reference is 0."
    )


class Comparison(StrictModel):
    flight_time: ErrorMetric
    range: ErrorMetric
    max_height: ErrorMetric
    impact_speed: ErrorMetric
    max_position_error: float = Field(
        description="Max Euclidean distance (m) between numerical and exact positions, "
        "evaluated at the solver's accepted step nodes (no interpolation error)."
    )
    max_energy_balance_residual: float = Field(
        description="max |KE + PE + W_drag - E0| / E0 over step nodes. Exactly 0 for the "
        "true solution, so this measures integration error only."
    )


class ProjectileSeries(StrictModel):
    """Uniformly resampled series for plotting. Numerical values come from the solver's
    dense-output interpolant; analytical values from the exact solution at the same times."""

    t: list[float]
    x_numerical: list[float]
    y_numerical: list[float]
    x_analytical: list[float]
    y_analytical: list[float]
    speed_numerical: list[float]
    kinetic_energy: list[float]
    potential_energy: list[float]
    drag_work: list[float]


class ProjectileResponse(StrictModel):
    model: ModelInfo
    parameters: ProjectileParameters
    solver: SolverSettings
    units: dict[str, str]
    assumptions: list[Assumption]
    analytical: AnalyticalResult
    numerical: NumericalResult
    comparison: Comparison
    series: ProjectileSeries
    metadata: RunMetadata


# --- Angle sweep ---------------------------------------------------------------------------


class AngleSweepRequest(StrictModel):
    parameters: ProjectileParameters = Field(
        default_factory=ProjectileParameters,
        description="Projectile settings. launch_angle_deg is ignored: the sweep varies it.",
    )
    n_angles: int = Field(
        default=91,
        ge=10,
        le=361,
        description="Number of evenly spaced angles from 0 to 90 degrees (91 = 1-degree steps).",
    )
    save_experiment: bool = True


class AngleSweepResponse(StrictModel):
    model: ModelInfo
    parameters: ProjectileParameters
    units: dict[str, str]
    assumptions: list[Assumption]
    angles_deg: list[float]
    ranges: list[float] = Field(description="m")
    flight_times: list[float] = Field(description="s")
    max_heights: list[float] = Field(description="m")
    best_angle_deg: float = Field(
        description="Angle maximising the range, refined by a bounded Brent search (~1e-7 deg)."
    )
    best_range: float = Field(description="m")
    vacuum_best_angle_deg: float = Field(
        description="Closed-form best angle with no drag: tan(theta) = v0 / sqrt(v0^2 + 2 g h)."
    )
    vacuum_best_range: float = Field(description="m, closed form with no drag")
    method_note: str
    metadata: RunMetadata
