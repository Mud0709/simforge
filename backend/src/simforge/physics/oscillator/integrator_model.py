"""Orchestrates the oscillator methods study: core dataclasses -> validated API contract.

No HTTP and no database: the API layer adds run metadata and persistence. Plan 2.4, D8-D10,
D13; the constants below are measured in ``SCIENTIFIC_VALIDATION.md``, section
"physics.oscillator.integrators v1.0.0".
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo, ValidationCheck
from simforge.numerics.convergence import MIN_FIT_POINTS, OrderFit
from simforge.numerics.fixed_step import harmonic_energy_factor
from simforge.physics.oscillator import integrator_study as study
from simforge.physics.oscillator.integrator_schemas import (
    EnergyEnvelopeSeries,
    MethodName,
    OscillatorEnergyRun,
    OscillatorFitRule,
    OscillatorIntegratorRequest,
    OscillatorIntegratorRun,
    OscillatorMethodResult,
)
from simforge.physics.projectile.integrator_schemas import OrderFitResult

MODEL_INFO = ModelInfo(
    id="physics.oscillator.integrators",
    version="1.0.0",
    name="Integrator methods study (undamped harmonic oscillator)",
    description="Forward Euler, RK4, symplectic Euler and velocity Verlet on x'' = -w^2 x: "
    "convergence orders over one period against the exact solution, and energy over a long "
    "run against the methods' exact discrete energy laws and proved bounds.",
)

UNITS: dict[str, str] = {
    "mass": "kg",
    "spring_constant": "N/m",
    "initial_displacement": "m",
    "initial_velocity": "m/s",
    "dt": "s",
    "h": "s",
    "energy_dt": "s",
    "theta": "dimensionless (w h)",
    "angular_frequency": "rad/s",
    "period": "s",
    "amplitude_scale": "m",
    "position_error": "m",
    "velocity_error": "m/s",
    "relative_energy_error": "dimensionless ((E_n - E_0)/E_0)",
}

ASSUMPTIONS: list[Assumption] = [
    Assumption(
        id="undamped_undriven",
        statement="A point mass on an ideal Hooke's-law spring, with no damping and no drive: "
        "x'' = -w^2 x, w = sqrt(k/m). The energy E = (1/2) k x^2 + (1/2) m v^2 is exactly "
        "conserved by the true motion, so any change is the method's.",
    ),
    Assumption(
        id="one_period_orders",
        statement="Every order run covers exactly one period T = 2 pi / w with N = ceil(T/dt) "
        "equal steps, against x0 cos wt + (v0/w) sin wt evaluated in float64. The order is "
        "fitted to the scaled phase-space error max_n sqrt((x_n - x(t_n))^2 + ((v_n - "
        "v(t_n))/w)^2) / X over ALL nodes, not at t = T alone: there symplectic Euler is "
        "O(h^2) (superconvergent), which would hide its true order 1. The largest |x - x_exact| "
        "(m) and |v - v_exact| (m/s) are reported too.",
    ),
    Assumption(
        id="energy_laws",
        statement="On this equation each method's energy follows a closed form, proved in "
        "the 2.4 plan: Euler multiplies E by exactly 1 + (wh)^2 per step (grows), RK4 by "
        "exactly 1 - (wh)^6/72 + (wh)^8/576 (decays); symplectic Euler and velocity Verlet "
        "conserve a modified energy H~ exactly, so their energy error stays within a proved "
        "bound for wh < 2, with no secular drift. Float runs add rounding of about N eps.",
    ),
]

FIT_RULE = OscillatorFitRule(
    max_theta=study.MAX_THETA_FOR_FIT,
    max_amplitude_growth=study.MAX_GROWTH_FOR_FIT,
    roundoff_safety_factor=study.ROUNDOFF_SAFETY,
    min_points=MIN_FIT_POINTS,
    description=(
        f"A run enters the fit only if it did not diverge, wh <= {study.MAX_THETA_FOR_FIT} "
        "(asymptotic regime), the closed-form amplitude change over the period "
        f"|rho^N - 1| is at most {study.MAX_GROWTH_FOR_FIT} (only Euler and RK4 change "
        f"amplitude; it bites Euler), and its error exceeds {study.ROUNDOFF_SAFETY:.0f} x N x "
        "machine epsilon (the error is already scaled by X). An order is reported only "
        f"with at least {MIN_FIT_POINTS} such steps. Linear stability is not used: Euler is "
        "unstable at every h on this equation yet converges at a fixed horizon. The rule was "
        "fixed before any results were inspected."
    ),
)

# Step caps: worst measured study at these caps took 2.16 s (RK4 alone, three runs of
# ~50 000 steps), below the plan's 5 s (SCIENTIFIC_VALIDATION.md,
# physics.oscillator.integrators v1.0.0, "Caps and timings").
MAX_STEPS_PER_RUN = 50_000
MAX_TOTAL_STEPS = 150_000
# C of the C N eps thresholds, 1-2-5 values >= 10x the measured worst (SCIENTIFIC_VALIDATION.md,
# physics.oscillator.integrators v1.0.0, "Rounding constants"). Energy identity: worst 21.3
# (RK4, wh = 56, N = 3; the corner grid's worst is 0.275), so 500.
ENERGY_IDENTITY_C = 500.0
# Modified energy: threshold C N eps kappa(theta) (kappa: H~'s conditioning, _conditioning);
# worst residual / (N eps kappa) over 24 182 runs, theta from 1e-3 to 2 - 1e-9, is 1.014
# (Verlet, theta = pi/2, N = 4), so 20. The same C is the R5 row's rounding allowance (worst
# excess over R5: 0.0114 N eps).
MODIFIED_ENERGY_C = 20.0

EPS = float(np.finfo(np.float64).eps)
# E_N (m^2) below this has subnormal parts, where rounding is absolute, not C N eps relative.
TINY_ENERGY = float(np.finfo(np.float64).tiny) / EPS
NAMES = {
    "euler": "Forward Euler",
    "rk4": "RK4",
    "symplectic_euler": "Symplectic Euler",
    "velocity_verlet": "Velocity Verlet",
}


@dataclass(frozen=True, slots=True)
class OscillatorIntegratorComputation:
    omega: float  # rad/s
    period: float  # s
    amplitude_scale: float  # m
    results: list[OscillatorMethodResult]
    energy: list[OscillatorEnergyRun]
    checks: list[ValidationCheck]
    elapsed_ms: float


def _fit(fit: OrderFit | None, theoretical: int) -> OrderFitResult | None:
    if fit is None:
        return None
    return OrderFitResult(
        order=fit.order,
        theoretical_order=theoretical,
        r_squared=fit.r_squared,
        n_points=fit.n_points,
        h_min=fit.h_min,
        h_max=fit.h_max,
    )


def _check_caps(osc: study.Oscillator, request: OscillatorIntegratorRequest) -> None:
    order_steps = [study.steps_for(osc.period, dt) for dt in request.dt_values]
    energy_steps = study.steps_for(request.periods * osc.period, request.energy_dt)
    largest = max(*order_steps, energy_steps)
    if largest > MAX_STEPS_PER_RUN:
        raise ModelDomainError(
            f"One run needs {largest} steps (order runs over T = {osc.period:.4g} s, the energy "
            f"run over {request.periods} periods); the limit is {MAX_STEPS_PER_RUN} per run. "
            "Use larger dt_values or energy_dt, or fewer periods."
        )
    total = len(request.methods) * (sum(order_steps) + energy_steps)
    if total > MAX_TOTAL_STEPS:
        raise ModelDomainError(
            f"This study needs {total} steps in total; the limit is {MAX_TOTAL_STEPS}. Use "
            "fewer or larger time steps, fewer periods, or fewer methods."
        )


def _energy_run(m: MethodName, e: study.EnergyRun) -> OscillatorEnergyRun:
    env = e.envelope
    return OscillatorEnergyRun(
        method=m,
        h=e.h,
        theta=e.theta,
        n_steps=e.n_steps,
        diverged=e.diverged,
        diverged_at_step=e.n_completed + 1 if e.diverged else None,
        n_completed=e.n_completed,
        final_energy_ratio=e.final_energy_ratio,
        max_relative_energy_error=e.max_relative_energy_error,
        energy_bound=e.energy_bound,
        modified_energy_residual=e.modified_energy_residual,
        envelope=EnergyEnvelopeSeries(
            t_start=env.t_start.tolist(),
            t_end=env.t_end.tolist(),
            lo=env.lo.tolist(),
            hi=env.hi.tolist(),
        ),
    )


def _conditioning(method: str, theta: float) -> float:
    """kappa: H~ >= E/kappa (R3, R4 with |q u| <= E/2), so rounding relative to |H~_0| is
    magnified by up to kappa; 1/(1 - theta/2) (symplectic Euler), 1/(1 - theta^2/4) (Verlet)."""
    if method == "symplectic_euler":
        return 1 / (1 - theta / 2)
    return 1 / (1 - theta * theta / 4)


def _verdict(value: float, threshold: float | None) -> bool | None:
    return None if threshold is None else value <= threshold


def _energy_checks(e: study.EnergyRun, amplitude: float) -> list[ValidationCheck]:
    m, n = e.method, e.n_steps
    name = NAMES[m]
    diverged = (
        f"The run diverged at step {e.n_completed + 1} of {n} (a state component passed "
        "1e100), so no verdict is given."
    )
    value = e.max_relative_energy_error
    if m in ("euler", "rk4"):
        law = "(1 + (wh)^2)^N" if m == "euler" else "(1 - (wh)^6/72 + (wh)^8/576)^N"
        ratio = e.final_energy_ratio
        identity, threshold = 0.0, None
        if ratio is None:
            note = diverged
        elif ratio * amplitude**2 < TINY_ENERGY:
            note = (
                "The energy decayed below the normal float range (m^2), where rounding is no "
                "longer relative, so no verdict is given."
            )
        else:
            # In logs: factor^N alone can under- or overflow while E_N/E_0 cannot.
            log_factor = math.log(harmonic_energy_factor(m, e.theta))
            identity = abs(math.expm1(math.log(ratio) - n * log_factor))
            threshold = ENERGY_IDENTITY_C * n * EPS
            note = (
                f"Value: |(E_N/E_0) / {law} - 1| over N = {n} steps at wh = {e.theta:.4g}. "
                "An exact identity of the method on this equation (plan R1, R2), whatever its "
                f"stability; the threshold {ENERGY_IDENTITY_C:g} N eps is measured rounding."
            )
        return [
            ValidationCheck(
                id=f"energy_identity_{m}",
                label=f"{name}: final energy ratio E_N/E_0 equals {law}",
                value=identity,
                threshold=threshold,
                passed=_verdict(identity, threshold),
                kind="exact_identity",
                note=note,
            )
        ]
    rounding = MODIFIED_ENERGY_C * n * EPS
    residual = e.modified_energy_residual
    if e.diverged or residual is None:
        mod_threshold, mod_passed = None, None
        mod_note = (
            diverged
            if e.diverged
            else f"wh = {e.theta:.4g} >= 2: H~ is not positive definite, so |H~_0| is no scale "
            "for a relative residual; no verdict is given."
        )
    elif (scaled := rounding * _conditioning(m, e.theta)) > 1:
        mod_threshold, mod_passed = None, None
        mod_note = (
            f"wh = {e.theta:.4g} is so close to 2 that H~ is ill-conditioned: the rounding "
            f"allowance {MODIFIED_ENERGY_C:g} N eps kappa = {scaled:.3g} exceeds 100%, so no "
            "verdict is given."
        )
    else:
        mod_threshold, mod_passed = scaled, residual <= scaled
        mod_note = (
            f"Value: max |H~_n - H~_0| / |H~_0| over N = {n} steps. H~ is conserved exactly by "
            f"the step map (plan R3, R4); the threshold {MODIFIED_ENERGY_C:g} N eps kappa is "
            f"measured rounding, kappa = {_conditioning(m, e.theta):.4g} the conditioning of H~ "
            "(how much smaller than the energy it can be)."
        )
    if e.diverged:
        bound_threshold, bound_note = None, diverged
    elif e.energy_bound is None:
        bound_threshold = None
        bound_note = (
            f"wh = {e.theta:.4g} >= 2: the method is unstable (R7) and the bound does not "
            "hold, so no verdict is given."
        )
    else:
        bound_threshold = e.energy_bound + rounding
        bound_note = (
            f"Value: max |E_n - E_0|/E_0 over N = {n} steps; threshold the proved bound "
            f"{e.energy_bound:.4g} (plan R5, exact arithmetic) plus {MODIFIED_ENERGY_C:g} N eps "
            "for rounding. Bounded for every N: no secular drift."
        )
    return [
        ValidationCheck(
            id=f"modified_energy_{m}",
            label=f"{name}: modified energy H~ conserved",
            value=0.0 if residual is None else residual,
            threshold=mod_threshold,
            passed=mod_passed,
            kind="exact_identity",
            note=mod_note,
        ),
        ValidationCheck(
            id=f"energy_bound_{m}",
            label=f"{name}: energy error within its proved bound",
            value=value,
            threshold=bound_threshold,
            passed=_verdict(value, bound_threshold),
            kind="numerical_diagnostic",
            note=bound_note,
        ),
    ]


def _order_checks(r: OscillatorMethodResult) -> list[ValidationCheck]:
    name = NAMES[r.method]
    out = []
    if r.fit is not None:
        gap = abs(r.fit.order - r.theoretical_order)
        out.append(
            ValidationCheck(
                id=f"order_{r.method}",
                label=f"{name}: fitted order near {r.theoretical_order}",
                value=gap,
                threshold=0.1,
                passed=gap <= 0.1,
                kind="numerical_diagnostic",
                note=f"Value: |fitted order {r.fit.order:.3f} - "
                f"{r.theoretical_order}|. A measured slope, not a proof.",
            )
        )
    fitted = sum(run.in_fit for run in r.runs)
    out.append(
        ValidationCheck(
            id=f"fit_points_{r.method}",
            label=f"{name}: step sizes in the order fit",
            value=float(fitted),
            threshold=None,
            passed=None,
            kind="informational",
            note=f"{fitted} of {len(r.runs)} runs met the fit rule (at least {MIN_FIT_POINTS} "
            "needed for an order).",
        )
    )
    return out


def run(request: OscillatorIntegratorRequest) -> OscillatorIntegratorComputation:
    start = time.perf_counter()
    p = request.parameters
    osc = study.Oscillator(
        omega=float(np.sqrt(p.spring_constant / p.mass)),
        x0=p.initial_displacement,
        v0=p.initial_velocity,
    )
    _check_caps(osc, request)

    results = []
    orders = study.run_orders(osc, request.dt_values, request.methods)
    for m, mc in zip(request.methods, orders, strict=True):
        order = study.THEORETICAL_ORDER[m]
        results.append(
            OscillatorMethodResult(
                method=m,
                theoretical_order=order,
                runs=[
                    OscillatorIntegratorRun(
                        dt_requested=r.dt_requested,
                        h=r.h,
                        n_steps=r.n_steps,
                        theta=osc.omega * r.h,
                        diverged=r.diverged,
                        n_completed=r.n_completed,
                        max_position_error=r.max_errors["position"],
                        max_velocity_error=r.max_errors["velocity"],
                        max_scaled_error=r.max_errors["scaled"],
                        in_fit=r.in_fit["scaled"],
                        exclusion_reason=r.exclusion_reason,
                    )
                    for r in mc.runs
                ],
                fit=_fit(mc.fits["scaled"], order),
            )
        )
    runs = [study.run_energy(osc, m, request.energy_dt, request.periods) for m in request.methods]
    checks = [ch for r in results for ch in _order_checks(r)]
    checks += [ch for e in runs for ch in _energy_checks(e, osc.amplitude)]
    return OscillatorIntegratorComputation(
        omega=osc.omega,
        period=osc.period,
        amplitude_scale=osc.amplitude,
        results=results,
        energy=[_energy_run(m, e) for m, e in zip(request.methods, runs, strict=True)],
        checks=checks,
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )
