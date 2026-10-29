"""Validated API contract for projectile motion with quadratic drag (roadmap 2.1, D6 and D7).

Units are part of the contract: every field states its SI unit. The solver settings
(``SolverSettings``) and the numerical result (``NumericalResult``) are the linear model's,
reused unchanged (plan D2), so this model adds its own combined rules on the request instead
of changing the shared settings.

Limits (plan D6, plus two rules found in slice 3). The single-field bounds are the linear
model's; c runs from 0 (vacuum) to 1e6 kg/m. Three combined rules:

* **Drag rate.** The largest drag rate in the flight, kappa max(v0, v_t) (1/s, with
  kappa = c/m), is at most 1e4 s^-1, the linear model's k = b/m limit: by R7 i the speed
  never exceeds max(v0, v_t). It is computed as max(kappa v0, sqrt(kappa g)), since
  kappa v_t = sqrt(kappa g): in vacuum that is 0, with no 0 * inf.
* **Absolute tolerance.** ``atol`` must be at most ``ATOL_FRACTION`` (1%) of the smallest
  velocity scale, min(v0, v_t). Far above it the solver does not control the velocity,
  and runs became pathologically slow (measured in slice 3 on a grid of the corners with
  the slice 2 model: at most 0.2 s up to 1 x the scale and 0.53 s at 5 x, but up to 10 s at
  10 x, and 20 s timeouts and overflow errors at 100 to 1000 x, mostly Radau). 1% is the
  largest fraction at which every run on that grid also passed its own checks: at 10% an
  RK45 run (v0 = 1e4 m/s, v_t = 0.1 m/s) missed the exact vertical flight time by 1.1%.
* **A resolvable flight.** The flight must last at least ``MIN_FLIGHT_TIME`` (1 microsecond)
  without drag. SciPy locates the landing only to about 1e-15 s, and much shorter flights
  crashed the run (a zero cap on the integration, or the flight-time bound's root search
  failing). With drag rates of at most 1e4 s^-1, drag changes a flight this short by under
  1%, so the drag-free time is a fair measure of it. A flat launch from the ground keeps
  the linear model's message ("zero flight time").
"""

from __future__ import annotations

import math
from typing import Self

import numpy as np
from pydantic import Field, ValidationError, model_validator

from simforge.core.schemas import Assumption, ModelInfo, RunMetadata, StrictModel, ValidationCheck
from simforge.physics.projectile import quadratic_reference as qr
from simforge.physics.projectile.schemas import (
    MAX_DRAG_RATE,
    MIN_MASS,
    MIN_SPEED,
    ErrorMetric,
    NumericalResult,
    SolverSettings,
    TrajectoryMetrics,
)

ATOL_FRACTION = 0.01  # atol <= ATOL_FRACTION x min(v0, v_t)
MIN_FLIGHT_TIME = 1e-6  # s, the drag-free flight time


class QuadraticDragParameters(StrictModel):
    initial_speed: float = Field(
        default=20.0, ge=MIN_SPEED, le=1e4, description="Launch speed |v0| in m/s."
    )
    launch_angle_deg: float = Field(
        default=45.0, ge=0, le=90, description="Launch angle above the horizontal, in degrees."
    )
    launch_height: float = Field(
        default=0.0, ge=0, le=1e5, description="Height of the launch point above the ground, in m."
    )
    mass: float = Field(default=1.0, ge=MIN_MASS, le=1e6, description="Projectile mass in kg.")
    drag_constant: float = Field(
        default=0.01,
        ge=0,
        le=1e6,
        description="Quadratic drag constant c in kg/m (drag force F = -c|v|v; for a ball "
        "c = rho C_d A / 2). Not the dimensionless drag coefficient C_d, and not the linear "
        "model's b in kg/s. 0 means vacuum.",
    )
    gravity: float = Field(
        default=9.80665,
        ge=0.01,
        le=1000,
        description="Gravitational acceleration in m/s^2 (default: standard gravity).",
    )

    @model_validator(mode="after")
    def _drag_rate_in_range(self) -> Self:
        kappa = self.drag_constant / self.mass  # <= 1e12 1/m within the field bounds
        rate = max(kappa * self.initial_speed, math.sqrt(kappa * self.gravity))
        if rate > MAX_DRAG_RATE:
            raise ValueError(
                f"the largest drag rate in the flight, kappa max(v0, v_t) = {rate:.3g} s^-1 "
                f"(kappa = c/m), is above the {MAX_DRAG_RATE:g} s^-1 limit (drag would act in "
                "under 0.1 ms); lower drag_constant or raise mass"
            )
        return self

    def terminal_speed(self) -> float:
        """sqrt(m g / c) in m/s; ``math.inf`` in vacuum."""
        return qr.terminal_speed(self.mass, self.drag_constant, self.gravity)

    def vacuum_flight_time(self) -> float:
        """Flight time with no drag, in s: (vy0 + sqrt(vy0^2 + 2 g h)) / g."""
        g, h = self.gravity, self.launch_height
        vy0 = self.initial_speed * math.sin(math.radians(self.launch_angle_deg))
        return (vy0 + math.sqrt(vy0 * vy0 + 2 * g * h)) / g

    def check_flies(self) -> None:
        if self.launch_height == 0 and self.launch_angle_deg == 0:
            raise ValueError(
                "launch_angle_deg = 0 with launch_height = 0 gives zero flight time; "
                "raise the angle or the launch height"
            )
        t = self.vacuum_flight_time()
        if t < MIN_FLIGHT_TIME:
            raise ValueError(
                f"the flight would last {t:.3g} s without drag, under one microsecond "
                f"({MIN_FLIGHT_TIME:g} s): too short to resolve, since the solver locates the "
                "landing only to about 1e-15 s; raise the angle, the speed or the launch height"
            )


class QuadraticDragRequest(StrictModel):
    parameters: QuadraticDragParameters = Field(default_factory=QuadraticDragParameters)
    solver: SolverSettings = Field(default_factory=SolverSettings)
    n_samples: int = Field(
        default=400, ge=10, le=5000, description="Number of points in the resampled series."
    )
    save_experiment: bool = Field(
        default=True, description="Record inputs and summary metrics in the experiment log."
    )

    @model_validator(mode="after")
    def _resolvable(self) -> Self:
        p = self.parameters
        p.check_flies()
        v0, v_t = p.initial_speed, p.terminal_speed()
        limit = ATOL_FRACTION * min(v0, v_t)
        if self.solver.atol > limit:
            if v_t < v0:
                scale = f"the terminal speed v_t = {v_t:.3g} m/s (below v0 = {v0:.3g} m/s)"
            else:
                speed = "no drag" if math.isinf(v_t) else f"terminal speed v_t = {v_t:.3g} m/s"
                scale = f"the launch speed v0 = {v0:.3g} m/s ({speed})"
            raise ValueError(
                f"atol = {self.solver.atol:.3g} is above {ATOL_FRACTION:g} x min(v0, v_t), "
                f"the smallest velocity scale, here {scale}: the solver would not control "
                f"the velocity, and the run can be very slow; use atol <= "
                f"{_three_figures_down(limit)}"
            )
        return self


def _three_figures_down(x: float) -> str:
    """``x`` > 0 shown to 3 significant figures, rounded *down*: the advice "use atol <= ..."
    must itself be accepted (0.0012356 must read 0.00123, not 0.00124)."""
    exponent = math.floor(math.log10(x)) - 2
    digits = math.floor(x / 10.0**exponent)
    text = f"{digits * 10.0**exponent:.3g}"
    while float(text) > x:  # the division or the product rounded up: one unit lower
        digits -= 1
        text = f"{digits * 10.0**exponent:.3g}"
    return text


# --- Response ----------------------------------------------------------------------------


class QuadraticVacuumFlight(TrajectoryMetrics):
    """The same launch with no drag (exact closed forms)."""

    method_note: str


class QuadraticVerticalFlight(StrictModel):
    """The exact vertical flight with quadratic drag (R3)."""

    apex_time: float = Field(description="s, from launch to the top")
    max_height: float = Field(description="m above the ground")
    fall_time: float = Field(description="s, from the top to the ground")
    flight_time: float = Field(description="s")
    impact_speed: float = Field(description="m/s")


class QuadraticVerticalReference(StrictModel):
    exact: QuadraticVerticalFlight
    flight_time: ErrorMetric
    apex_time: ErrorMetric
    max_height: ErrorMetric
    impact_speed: ErrorMetric
    method_note: str


class QuadraticDiagnostics(StrictModel):
    max_energy_balance_residual: float = Field(
        description="max |KE + PE + W - E0| / E0 over the solver's step nodes, with W the "
        "work against drag integrated from c|v|^3. Exactly 0 for the true motion."
    )
    max_invariant_residual: float | None = Field(
        description="max |I - I0| / max(1/vx^2) over the step nodes, for the hodograph "
        "invariant I (constant for the true motion). Null when I is undefined: a vertical "
        "launch (vx = 0), or a run whose vx decayed below the solver's control."
    )
    invariant_note: str
    drag_time_bound: float = Field(
        description="Proved upper bound on the drag time, the integral of kappa |v| dt "
        "(dimensionless: the path length in drag lengths m/c)."
    )
    flight_time_bound: float = Field(description="Proved upper bound on the flight time, s.")


class QuadraticDragSeries(StrictModel):
    """Uniformly resampled series for plotting, from the solver's dense output; the vacuum
    trajectory (exact) on its own time grid, since it lasts longer."""

    t: list[float]
    x: list[float]
    y: list[float]
    speed: list[float]
    kinetic_energy: list[float]
    potential_energy: list[float]
    drag_work: list[float]
    vacuum_t: list[float]
    vacuum_x: list[float]
    vacuum_y: list[float]


class QuadraticDragResponse(StrictModel):
    model: ModelInfo
    parameters: QuadraticDragParameters
    solver: SolverSettings
    units: dict[str, str]
    assumptions: list[Assumption]
    numerical: NumericalResult
    numerical_note: str
    terminal_speed: float | None = Field(
        description="sqrt(m g / c) in m/s (exact). Null in vacuum, where it is infinite."
    )
    vacuum: QuadraticVacuumFlight
    vertical_reference: QuadraticVerticalReference | None = Field(
        description="The exact vertical flight and the numerical errors against it; null "
        "unless the launch angle is exactly 90 degrees (no exact 2-D solution exists)."
    )
    diagnostics: QuadraticDiagnostics
    checks: list[ValidationCheck]
    series: QuadraticDragSeries
    metadata: RunMetadata


# --- Angle sweep (roadmap 2.2, plan D7, D8, D10) ------------------------------------------


class QuadraticAngleSweepRequest(StrictModel):
    """Every input rule is the 2.1 request's, checked once at the sweep's smallest flown angle
    (plan D7): the drag-rate and atol rules do not depend on the angle, and the drag-free
    flight time grows with it, so the 1-microsecond rule then holds at every grid angle. The
    stiffness guard and the work budget are the sweep's own (checked when it runs); the
    budget is a server limit, not a request field."""

    parameters: QuadraticDragParameters = Field(
        default_factory=QuadraticDragParameters,
        description="Projectile settings. launch_angle_deg is ignored: the sweep varies it.",
    )
    solver: SolverSettings = Field(default_factory=SolverSettings)
    n_angles: int = Field(
        default=91,
        ge=10,
        le=361,
        description="Number of evenly spaced angles from 0 to 90 degrees (91 = 1-degree steps).",
    )
    save_experiment: bool = Field(
        default=True, description="Record inputs and summary metrics in the experiment log."
    )

    def smallest_flown_angle(self) -> float:
        """0 degrees from a height; from the ground (where 0 degrees is no flight) the first
        grid step, taken from the sweep's own grid so it is the very angle that is run."""
        if self.parameters.launch_height > 0:
            return 0.0
        return float(np.linspace(0.0, 90.0, self.n_angles)[1])

    @model_validator(mode="after")
    def _valid_at_the_smallest_angle(self) -> Self:
        # From the ground, Brent's refinement can fly angles *below* the first grid step when
        # the best grid point is that step (seen at v0/v_t = 1e5 on a 10-angle grid: best grid
        # point 10°, a refinement run at 4.7°), which the argument above does not cover. The
        # drag-rate rule does: from the ground the drag-free flight time at angle theta is
        # 2 v0 sin(theta) / g, so one under a microsecond at theta >= 1° needs v0/g < 2.9e-5 s,
        # and then (v0/v_t)^2 = (kappa v0)(v0/g) <= 1e4 x 2.9e-5 = 0.29: weak drag, whose best
        # angle is near 45° (observed: 43.0° at 0.41), far from the low peak that sends Brent
        # below the first step (observed, not proved: the lowest best angle from the ground
        # at the strongest drag allowed, v0/v_t = 1e5, was 9.6°).
        angle = self.smallest_flown_angle()
        at = self.parameters.model_copy(update={"launch_angle_deg": angle})
        try:
            QuadraticDragRequest(parameters=at, solver=self.solver, save_experiment=False)
        except ValidationError as exc:
            reasons = "; ".join(str(e.get("ctx", {}).get("error", e["msg"])) for e in exc.errors())
            raise ValueError(f"at the sweep's smallest angle {angle:.10g}°: {reasons}") from None
        return self


class QuadraticAngleSweepResponse(StrictModel):
    model: ModelInfo
    parameters: QuadraticDragParameters
    solver: SolverSettings
    units: dict[str, str]
    assumptions: list[Assumption]
    angles_deg: list[float]
    ranges: list[float] = Field(
        description="m, numerical: each a single quadratic-drag run at that angle (exactly 0 at "
        "90 degrees, and at 0 degrees from the ground, which is no flight)"
    )
    flight_times: list[float] = Field(description="s, numerical")
    max_heights: list[float] = Field(description="m, numerical")
    vacuum_ranges: list[float] = Field(description="m, exact: the same angles with no drag")
    best_angle_deg: float = Field(
        description="Numerical: the best grid point refined by a bounded Brent search."
    )
    best_range: float = Field(description="m, numerical: the range at best_angle_deg")
    best_angle_uncertainty_deg: float | None = Field(
        description="Estimate, not a bound: u = 2 sqrt(eps_R / K), eps_R = 10 (rtol R + atol), "
        "K = |R''| from the grid's second difference. Null, with the reason in "
        "best_angle_note, when the best grid point is at an edge or the curve is not bent "
        "downwards there."
    )
    best_angle_note: str
    vacuum_best_angle_deg: float = Field(
        description="Exact best angle with no drag: tan(theta) = v0 / sqrt(v0^2 + 2 g h)."
    )
    vacuum_best_range: float = Field(description="m, exact: (v0 / g) sqrt(v0^2 + 2 g h)")
    terminal_speed: float | None = Field(
        description="sqrt(m g / c) in m/s (exact). Null in vacuum, where it is infinite."
    )
    n_runs: int = Field(description="Quadratic-drag runs: the flown grid angles plus Brent's.")
    n_rhs_evaluations: int = Field(description="Right-hand-side evaluations of the whole sweep.")
    checks: list[ValidationCheck]
    method_note: str
    metadata: RunMetadata
