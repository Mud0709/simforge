"""Validated API contract for the simulated resonance curve (roadmap 2.5, slice 4; plan D6, D12).

Units are part of the contract: every field states its SI unit. The single-field bounds and the
w0, gamma and w <= 100 w0 rules are the oscillator's (``oscillator.schemas``), since every point
is one 2.3 run. Added here (D6): b > 0 and F0 > 0, 0 < omega_min < omega_max <= 1e4 rad/s, and
Q <= 300 (no sweep above it fits 2.3's cycle limit at any allowed settle_tolerance). Refused
by the model before any solve (``resonance_sweep.run``, 422 saying what to change): Radau, an
input that is not underdamped, and a grid point over the cycle limit; and, after each run, the
work budget.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Self

from pydantic import Field, model_validator

from simforge.core.schemas import Assumption, ModelInfo, RunMetadata, StrictModel, ValidationCheck
from simforge.physics.oscillator.resonance_sweep import MAX_N_FREQUENCIES, ResonanceSweepInputs
from simforge.physics.oscillator.schemas import (
    MAX_DRIVE_RATIO,
    MAX_NATURAL_ANGULAR_FREQUENCY,
    MIN_NATURAL_ANGULAR_FREQUENCY,
    OscillatorResonance,
)
from simforge.physics.projectile.schemas import MAX_DRAG_RATE, MIN_MASS, SolverSettings

# D6: a point at w <= w0 needs about Q ln(2/eps_s) / pi cycles, so 2.3's 500-cycle limit admits
# Q up to ~300 at the loosest eps_s = 1e-2; above 300 no sweep fits at any allowed eps_s.
MAX_SWEEP_QUALITY_FACTOR = 300


class ResonanceSweepParameters(StrictModel):
    """Physical inputs and the frequency range, SI units. Every run starts from rest.
    Defaults (plan D11): w0 = 5 rad/s, zeta = 0.1 (Q = 5), 0.5 to 15 rad/s."""

    mass: float = Field(default=1.0, ge=MIN_MASS, le=1e6, description="Mass m in kg.")
    spring_constant: float = Field(
        default=25.0, ge=1e-6, le=1e9, description="Spring constant k in N/m."
    )
    damping_coefficient: float = Field(
        default=1.0,
        gt=0,
        le=1e6,
        description="Damping coefficient b in kg/s (> 0: without damping there is no steady "
        "state to settle to). Must leave the oscillator underdamped (b < 2 sqrt(mk)).",
    )
    drive_amplitude: float = Field(
        default=1.0, gt=0, le=1e6, description="Amplitude F0 of the drive F0 cos(w t), in N."
    )
    omega_min: float = Field(
        default=0.5, gt=0, le=1e4, description="Lowest drive angular frequency, rad/s."
    )
    omega_max: float = Field(
        default=15.0, gt=0, le=1e4, description="Highest drive angular frequency, rad/s."
    )
    settle_tolerance: float = Field(
        default=1e-6,
        ge=1e-12,
        le=1e-2,
        description="eps_s, dimensionless: each run waits until the transient is below eps_s "
        "times the steady amplitude A before it is measured.",
    )

    @model_validator(mode="after")
    def _combined_rules(self) -> Self:
        if self.omega_min >= self.omega_max:
            raise ValueError(
                f"omega_min ({self.omega_min:g} rad/s) must be below omega_max "
                f"({self.omega_max:g} rad/s); widen the range"
            )
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
        if self.omega_max > MAX_DRIVE_RATIO * w0:
            raise ValueError(
                f"omega_max = {self.omega_max:.3g} rad/s is above {MAX_DRIVE_RATIO:g} w0 = "
                f"{MAX_DRIVE_RATIO * w0:.3g} rad/s (the oscillator run's limit); lower omega_max"
            )
        m, k, b = (Fraction(v) for v in (self.mass, self.spring_constant, self.damping_coefficient))
        if m * k > (MAX_SWEEP_QUALITY_FACTOR * b) ** 2:  # Q > 300, exact
            q = math.sqrt(self.mass) * math.sqrt(self.spring_constant) / self.damping_coefficient
            raise ValueError(
                f"the quality factor Q = sqrt(mk)/b = {q:.4g} is above "
                f"{MAX_SWEEP_QUALITY_FACTOR}: the transient then needs more than one run's "
                "500-cycle limit to settle at any allowed settle_tolerance; raise "
                "damping_coefficient"
            )
        # The other representability rules of one run, at the highest frequency (raises
        # ValueError, which becomes a 422).
        self.to_inputs(3).at(self.omega_max)
        return self

    def to_inputs(self, n_frequencies: int) -> ResonanceSweepInputs:
        return ResonanceSweepInputs(**self.model_dump(), n_frequencies=n_frequencies)


class ResonanceSweepRequest(StrictModel):
    parameters: ResonanceSweepParameters = Field(default_factory=ResonanceSweepParameters)
    solver: SolverSettings = Field(
        default_factory=SolverSettings,
        description="DOP853 or RK45 (Radau is refused: an underdamped run is not stiff). atol "
        "is a fraction of the run's scale X, as in the oscillator model.",
    )
    n_frequencies: int = Field(
        default=21,
        ge=3,
        le=MAX_N_FREQUENCIES,
        description="Number of evenly spaced drive frequencies from omega_min to omega_max.",
    )
    save_experiment: bool = Field(
        default=True, description="Record inputs and summary metrics in the experiment log."
    )


class ResonanceSweepPeak(StrictModel):
    angular_frequency: float = Field(
        description="rad/s, numerical: the best grid point refined by a bounded Brent search"
    )
    amplitude: float = Field(description="m, numerical: the lock-in amplitude there")
    amplitude_bound: float = Field(description="B1 of the run at the refined peak, m (proved)")
    uncertainty: float | None = Field(
        description="u = 2 sqrt(B1/K), rad/s: an estimate, not a bound; null at an edge or "
        "where the grid curve is not bent downwards (reason in uncertainty_note)"
    )
    uncertainty_note: str
    exact_angular_frequency: float | None = Field(
        description="w_r = sqrt(w0^2 - 2 gamma^2), rad/s (exact); null when zeta >= 1/sqrt(2)"
    )
    exact_amplitude: float | None = Field(
        description="A_max = (F0/m) / (2 gamma wd), m (exact); null when zeta >= 1/sqrt(2)"
    )


class ResonanceSweepResponse(StrictModel):
    model: ModelInfo
    parameters: ResonanceSweepParameters
    solver: SolverSettings
    units: dict[str, str]
    assumptions: list[Assumption]
    angular_frequencies: list[float] = Field(description="rad/s, the evenly spaced grid")
    amplitudes: list[float] = Field(description="m, numerical: lock-in of each run")
    phase_lags: list[float] = Field(description="rad, numerical, in [-pi/2, 3pi/2)")
    exact_amplitudes: list[float] = Field(description="m, exact: A(w) (formula)")
    exact_phase_lags: list[float] = Field(description="rad, exact: delta(w) in [0, pi]")
    settle_times: list[float] = Field(description="s, a whole number of drive periods")
    amplitude_bounds: list[float] = Field(
        description="B1 = 2 e_x + eps_s A + r_A, m: |A_sim - A| <= B1, proved given the "
        "measured trajectory error e_x"
    )
    resonance: OscillatorResonance = Field(
        description="The exact curve (formula) on a fine grid, for the dashed line"
    )
    peak: ResonanceSweepPeak
    grid_step_over_gamma: float = Field(
        description="Grid step / gamma, dimensionless: above 1 the grid may flatten or miss "
        "the peak"
    )
    n_rhs_evaluations: int = Field(description="Right-hand-side evaluations over every run")
    checks: list[ValidationCheck]
    metadata: RunMetadata
