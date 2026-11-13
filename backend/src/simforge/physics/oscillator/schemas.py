"""Validated API contract for the harmonic oscillator (roadmap 2.3, plan D2, D6, D12).

Units are part of the contract: every field states its SI unit. The solver settings are the
projectile's ``SolverSettings``, reused unchanged (plan D11); here ``atol`` is dimensionless,
a fraction of the scale X (the solver integrates the scaled equation, plan D5).

Limits (plan D6; the single-field bounds are provisional and checked by the corners test of
slice 3). Combined rules, each refused with a message saying what to change:

* w0 = sqrt(k/m) from 1e-3 to 1e4 rad/s;
* gamma = b/2m at most ``MAX_DRAG_RATE`` (1e4 1/s, the projectile's drag-rate limit);
* w at most 100 w0 (keeps the forced motion within reach of the scale X);
* Q = sqrt(mk)/b at most 1e4 when b > 0 (``analytical.MAX_QUALITY_FACTOR``, slice 1's
  decision A), and the other representability rules of ``analytical.OscillatorInputs``;
* at most ``model.MAX_CYCLES`` cycles, duration max(w0, w) / 2 pi (measured in slice 2);
  w counts only when the run is driven (F0 > 0), here and in the next rule;
* max(w0, w, gamma) duration at least ``analytical.MIN_DURATION_RATE_PRODUCT`` (1);
* not all of x0, v0 and F0 zero (nothing would move).

The stiffness guard (explicit methods refused when the stiffness number exceeds 1e4) is the
model's (``model.run``), as for the other models, since it depends on the method.
Validation of these rules is tested in slice 3 (the API); slice 2 type-checks this module.
"""

from __future__ import annotations

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from simforge.core.schemas import Assumption, ModelInfo, RunMetadata, StrictModel, ValidationCheck
from simforge.physics.oscillator import analytical
from simforge.physics.oscillator.model import MAX_CYCLES
from simforge.physics.projectile.schemas import MAX_DRAG_RATE, MIN_MASS, SolverSettings

MIN_NATURAL_ANGULAR_FREQUENCY = 1e-3  # rad/s
MAX_NATURAL_ANGULAR_FREQUENCY = 1e4  # rad/s
MAX_DRIVE_RATIO = 100.0  # w <= 100 w0


class OscillatorParameters(StrictModel):
    """Physical inputs and duration, SI units. Defaults: the Damped preset (plan D2)."""

    mass: float = Field(default=1.0, ge=MIN_MASS, le=1e6, description="Mass m in kg.")
    spring_constant: float = Field(
        default=25.0, ge=1e-6, le=1e9, description="Spring constant k in N/m."
    )
    damping_coefficient: float = Field(
        default=0.5,
        ge=0,
        le=1e6,
        description="Damping coefficient b in kg/s (damping force F = -b v). 0 means undamped.",
    )
    drive_amplitude: float = Field(
        default=0.0,
        ge=0,
        le=1e6,
        description="Amplitude F0 of the driving force F0 cos(w t), in N. 0 means undriven.",
    )
    drive_angular_frequency: float = Field(
        default=5.0, ge=0, le=1e4, description="Angular frequency w of the drive, in rad/s."
    )
    initial_displacement: float = Field(
        default=0.1, ge=-1e3, le=1e3, description="Displacement x0 at t = 0, in m."
    )
    initial_velocity: float = Field(
        default=0.0, ge=-1e4, le=1e4, description="Velocity v0 at t = 0, in m/s."
    )
    duration: float = Field(default=20.0, gt=0, le=1e6, description="Length of the run, in s.")

    @model_validator(mode="after")
    def _combined_rules(self) -> Self:
        w0 = math.sqrt(self.spring_constant / self.mass)
        if not MIN_NATURAL_ANGULAR_FREQUENCY <= w0 <= MAX_NATURAL_ANGULAR_FREQUENCY:
            raise ValueError(
                f"the natural angular frequency w0 = sqrt(k/m) = {w0:.3g} rad/s must be from "
                f"{MIN_NATURAL_ANGULAR_FREQUENCY:g} to {MAX_NATURAL_ANGULAR_FREQUENCY:g} rad/s; "
                "change spring_constant or mass"
            )
        gamma = self.damping_coefficient / (2 * self.mass)
        if gamma > MAX_DRAG_RATE:
            raise ValueError(
                f"the damping rate gamma = b/2m = {gamma:.3g} 1/s is above the "
                f"{MAX_DRAG_RATE:g} 1/s limit; lower damping_coefficient or raise mass"
            )
        # A drive that is off (F0 = 0) has no effect, so its frequency limits nothing.
        w = self.drive_angular_frequency if self.drive_amplitude != 0 else 0.0
        if w > MAX_DRIVE_RATIO * w0:
            raise ValueError(
                f"the drive frequency w = {w:.3g} rad/s is above {MAX_DRIVE_RATIO:g} w0 = "
                f"{MAX_DRIVE_RATIO * w0:.3g} rad/s; lower drive_angular_frequency"
            )
        if self.initial_displacement == self.initial_velocity == self.drive_amplitude == 0:
            raise ValueError(
                "nothing moves: initial_displacement, initial_velocity and drive_amplitude are "
                "all 0; set at least one of them"
            )
        inputs = self.to_inputs()  # raises ValueError for Q > 1e4 and unrepresentable inputs
        cycles = analytical.cycles(inputs, self.duration)
        if cycles > MAX_CYCLES:
            raise ValueError(
                f"the run lasts {cycles:.4g} cycles (duration max(w0, w) / 2 pi), above the "
                f"{MAX_CYCLES} limit (the run time grows with the cycles); shorten duration"
            )
        product = analytical.rate_duration_product(inputs, self.duration)
        if product < analytical.MIN_DURATION_RATE_PRODUCT:
            raise ValueError(
                f"the run is too short: max(w0, w, gamma) duration = {product:.3g}, below "
                f"{analytical.MIN_DURATION_RATE_PRODUCT:g} (the exact solution's rounding "
                "would dominate such a short motion); lengthen duration"
            )
        return self

    def to_inputs(self) -> analytical.OscillatorInputs:
        """The physical inputs, without the duration."""
        return analytical.OscillatorInputs(
            mass=self.mass,
            spring_constant=self.spring_constant,
            damping_coefficient=self.damping_coefficient,
            drive_amplitude=self.drive_amplitude,
            drive_angular_frequency=self.drive_angular_frequency,
            initial_displacement=self.initial_displacement,
            initial_velocity=self.initial_velocity,
        )


class OscillatorRequest(StrictModel):
    parameters: OscillatorParameters = Field(default_factory=OscillatorParameters)
    solver: SolverSettings = Field(default_factory=SolverSettings)
    n_samples: int = Field(
        default=400, ge=10, le=5000, description="Number of points in the resampled series."
    )
    save_experiment: bool = Field(
        default=True, description="Record inputs and summary metrics in the experiment log."
    )


# --- Response ----------------------------------------------------------------------------


class OscillatorDerived(StrictModel):
    """Exact formulas of the inputs (``analytical.derived``) and the scale X."""

    natural_angular_frequency: float = Field(description="w0 = sqrt(k/m), rad/s")
    damping_rate: float = Field(description="gamma = b/2m, 1/s")
    damping_ratio: float = Field(description="zeta = b / (2 sqrt(mk)), dimensionless")
    quality_factor: float | None = Field(
        description="Q = sqrt(mk)/b (exact, by definition); null when b = 0"
    )
    regime: Literal["undamped", "underdamped", "critically_damped", "overdamped"]
    damped_angular_frequency: float | None = Field(
        description="wd = sqrt(w0^2 - gamma^2), rad/s; null unless under- or undamped"
    )
    overdamped_rate: float | None = Field(
        description="beta = sqrt(gamma^2 - w0^2), 1/s; null unless overdamped"
    )
    damped_period: float | None = Field(description="T_d = 2 pi / wd, s; null when wd is null")
    scale: float = Field(description="X, m: a proved bound on |x| over the run, from the inputs")


class OscillatorSteadyState(StrictModel):
    """x_p = A cos(w t - delta) (formula, OR1); the amplitude peak (OR5)."""

    amplitude: float = Field(description="A, m")
    phase_lag: float = Field(description="delta in [0, pi], rad")
    peak_angular_frequency: float | None = Field(
        description="w_r = sqrt(w0^2 - 2 gamma^2), rad/s; null when zeta >= 1/sqrt(2)"
    )
    peak_amplitude: float | None = Field(
        description="A_max = (F0/m) / (2 gamma wd), m; null when zeta >= 1/sqrt(2)"
    )


class OscillatorNumerical(StrictModel):
    final_displacement: float = Field(description="x at t = duration, m (numerical)")
    final_velocity: float = Field(description="v at t = duration, m/s (numerical)")
    n_steps: int
    n_rhs_evaluations: int
    method: str
    rtol: float
    atol: float = Field(description="dimensionless, a fraction of the scale X")


class OscillatorDiagnostics(StrictModel):
    max_displacement_error: float = Field(
        description="max |x - x_exact| / X over the solver's step nodes"
    )
    max_velocity_error: float = Field(description="max |v - v_exact| / (w0 X) over the nodes")
    max_energy_balance_residual: float = Field(
        description="max |KE + PE + W_damp - W_drive - E0| / (k X^2) over the nodes; exactly 0 "
        "for the true motion"
    )
    free_decay_period_residual: float | None = Field(
        description="w0 |(t2 - t1) - T_d| for the first two maxima; null unless free, "
        "underdamped and with at least two maxima"
    )
    free_decay_ratio_residual: float | None = Field(
        description="|x2 - e^(-gamma T_d) x1| / X for the first two maxima; null as above"
    )
    remaining_transient: float | None = Field(
        description="The transient left at the end as a fraction of A (exact); null unless "
        "driven and damped"
    )
    cycles: float = Field(description="duration max(w0, w) / 2 pi (w0 alone when F0 = 0)")
    stiffness_number: float = Field(
        description="(gamma + beta) duration when overdamped, w0 duration otherwise"
    )


class OscillatorSeries(StrictModel):
    """Evenly resampled series (SI): numerical from the solver's dense output, exact from the
    closed form at the same times."""

    t: list[float]
    x: list[float]
    v: list[float]
    x_exact: list[float]
    v_exact: list[float]
    envelope: list[float] | None = Field(
        description="R e^(-gamma t), m, the transient's decay envelope; null unless underdamped"
    )
    kinetic_energy: list[float]
    potential_energy: list[float]
    damping_work: list[float] = Field(description="J, energy removed by damping since t = 0")
    drive_work: list[float] = Field(description="J, work done by the drive since t = 0")


class OscillatorResonance(StrictModel):
    """The steady state against drive frequency (formula, OR1; plan D9)."""

    angular_frequency: list[float] = Field(description="rad/s, from 0 to max(3 w0, 1.2 w)")
    amplitude: list[float] = Field(description="m")
    phase_lag: list[float] = Field(description="rad")


class OscillatorResponse(StrictModel):
    model: ModelInfo
    parameters: OscillatorParameters
    solver: SolverSettings
    units: dict[str, str]
    assumptions: list[Assumption]
    derived: OscillatorDerived
    steady_state: OscillatorSteadyState | None = Field(
        description="Null when undriven (F0 = 0) or undamped (b = 0: no steady state)"
    )
    numerical: OscillatorNumerical
    diagnostics: OscillatorDiagnostics
    checks: list[ValidationCheck]
    series: OscillatorSeries
    resonance: OscillatorResonance | None = Field(
        description="Null when undriven or undamped (A has a pole at w0 without damping)"
    )
    method_note: str
    metadata: RunMetadata
