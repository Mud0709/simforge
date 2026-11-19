"""The harmonic oscillator over HTTP (roadmap 2.3, slice 3; plan D11, D12, D13)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from simforge.api.dependencies import Repository
from simforge.api.runs import ModelEntry, Tolerance, execute
from simforge.core import formatting as fmt
from simforge.core.schemas import RunMetadata
from simforge.physics.oscillator import integrator_model, model
from simforge.physics.oscillator.integrator_schemas import (
    OscillatorIntegratorRequest,
    OscillatorIntegratorResponse,
)
from simforge.physics.oscillator.schemas import (
    OscillatorDerived,
    OscillatorDiagnostics,
    OscillatorNumerical,
    OscillatorRequest,
    OscillatorResonance,
    OscillatorResponse,
    OscillatorSeries,
    OscillatorSteadyState,
)

router = APIRouter(prefix="/physics", tags=["physics"])


def _run(request: OscillatorRequest) -> model.OscillatorComputation:
    p = request.parameters
    return model.run(p.to_inputs(), p.duration, request.solver, n_samples=request.n_samples)


def _derived(r: model.OscillatorComputation) -> OscillatorDerived:
    return OscillatorDerived(**asdict(r.derived), scale=r.scale)


def _steady_state(r: model.OscillatorComputation) -> OscillatorSteadyState | None:
    return None if r.steady_state is None else OscillatorSteadyState(**asdict(r.steady_state))


def _response(
    request: OscillatorRequest, r: model.OscillatorComputation, metadata: RunMetadata
) -> OscillatorResponse:
    return OscillatorResponse(
        model=model.MODEL_INFO,
        parameters=request.parameters,
        solver=request.solver,
        units=model.UNITS,
        assumptions=model.ASSUMPTIONS,
        derived=_derived(r),
        steady_state=_steady_state(r),
        numerical=OscillatorNumerical(**asdict(r.numerical)),
        diagnostics=OscillatorDiagnostics(**asdict(r.diagnostics)),
        checks=r.checks,
        series=OscillatorSeries(**asdict(r.series)),
        resonance=None if r.resonance is None else OscillatorResonance(**asdict(r.resonance)),
        method_note=model.METHOD_NOTE,
        metadata=metadata,
    )


_ERRORS = (
    "max_displacement_error",
    "max_velocity_error",
    "max_energy_balance_residual",
    "free_decay_period_residual",
    "free_decay_ratio_residual",
)


def _summary(r: model.OscillatorComputation) -> dict[str, Any]:
    # Plan D12; the initial displacement is kept for the headline (an echo of the inputs).
    d = r.diagnostics
    return {
        "initial_displacement": r.inputs.initial_displacement,
        "derived": _derived(r).model_dump(),
        "steady_state": None if r.steady_state is None else asdict(r.steady_state),
        "diagnostics": {name: getattr(d, name) for name in _ERRORS},
        "numerical": {
            "n_steps": r.numerical.n_steps,
            "n_rhs_evaluations": r.numerical.n_rhs_evaluations,
        },
    }


_CLOSED_FORM = Tolerance(
    relative=1e-12,
    absolute=0.0,
    reason="A closed form of the inputs (exact rationals, square roots, a few roundings of "
    "about 1e-16 each on another machine); 1e-12 relative leaves a wide margin. Null (no "
    "damping, no drive, or no such regime) must stay null.",
)
# Below rtol = 1e-10 rounding, not the solver's error control, sets the results (2.1's floor,
# measured there and in 2.2), so the replay rules use max(rtol, this) in place of rtol.
_REPLAY_RTOL_FLOOR = 1e-10


def _tolerances(inputs: dict[str, Any], summary: dict[str, Any]) -> dict[str, Tolerance]:
    rtol = max(inputs["solver"]["rtol"], _REPLAY_RTOL_FLOOR)
    atol = inputs["solver"]["atol"]
    error = Tolerance(
        relative=0.0,
        absolute=10 * (rtol + atol),
        reason="An error or residual in scaled units (fractions of X, w0 X or k X^2), near the "
        "solver's error control, so only an absolute tolerance makes sense: rounding on another "
        "machine can change one accept/reject decision and move it by about rtol + atol; a "
        "factor of 10 is the margin, with rtol taken as at least 1e-10 (plan D13). Null must "
        "stay null.",
    )
    rules: dict[str, Tolerance] = {
        "initial_displacement": Tolerance.exact("An input, copied for the headline.")
    }
    count = Tolerance.exact("A count: a different number is a different computation.")
    rules |= {f"derived.{name}": _CLOSED_FORM for name in OscillatorDerived.model_fields}
    rules["derived.regime"] = Tolerance.exact(
        "Decided exactly from the inputs (b^2 against 4mk in exact rationals)."
    )
    # One pattern for both shapes: null (undriven or undamped) and the four closed forms.
    rules["steady_state*"] = _CLOSED_FORM
    rules |= {f"diagnostics.{name}": error for name in _ERRORS}
    rules["numerical.n_steps"] = count
    rules["numerical.n_rhs_evaluations"] = count
    return rules


def _headline(s: dict[str, Any]) -> str:
    d = s["derived"]
    q = d["quality_factor"]
    regime = d["regime"].replace("_", " ")
    damping = "no damping" if q is None else f"Q {fmt.sig(q)}"
    return (
        f"x0 {fmt.sig(s['initial_displacement'])} m, zeta {fmt.sig(d['damping_ratio'])} "
        f"({regime}), {damping}"
    )


OSCILLATOR = ModelEntry(
    info=model.MODEL_INFO,
    request_type=OscillatorRequest,
    compute=_run,
    # Only the inputs that affect the numbers are hashed (not save_experiment).
    inputs=lambda req, _: req.model_dump(include={"parameters", "solver", "n_samples"}),
    summary=_summary,
    respond=_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=lambda inputs, _: OscillatorRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
    tolerances=_tolerances,
    headline=_headline,
)


@router.post("/oscillator/simulate")
async def simulate_oscillator(request: OscillatorRequest, repo: Repository) -> OscillatorResponse:
    return await execute(OSCILLATOR, request, repo, save=request.save_experiment)


# --- Methods study (roadmap 2.4, slice 2; plan D8-D14) -----------------------------------


def _study_response(
    request: OscillatorIntegratorRequest,
    r: integrator_model.OscillatorIntegratorComputation,
    metadata: RunMetadata,
) -> OscillatorIntegratorResponse:
    return OscillatorIntegratorResponse(
        model=integrator_model.MODEL_INFO,
        parameters=request.parameters,
        dt_values=request.dt_values,
        methods=request.methods,
        energy_dt=request.energy_dt,
        periods=request.periods,
        units=integrator_model.UNITS,
        assumptions=integrator_model.ASSUMPTIONS,
        angular_frequency=r.omega,
        period=r.period,
        amplitude_scale=r.amplitude_scale,
        fit_rule=integrator_model.FIT_RULE,
        results=r.results,
        energy=r.energy,
        checks=r.checks,
        metadata=metadata,
    )


def _study_summary(r: integrator_model.OscillatorIntegratorComputation) -> dict[str, Any]:
    energy = {e.method: e for e in r.energy}
    return {
        "methods": {
            m.method: {
                "order": m.fit.order if m.fit else None,
                "fit_points": m.fit.n_points if m.fit else 0,
                "final_energy_ratio": energy[m.method].final_energy_ratio,
                "max_relative_energy_error": energy[m.method].max_relative_energy_error,
            }
            for m in r.results
        },
    }


_STUDY_TOLERANCES = {
    "methods.*.fit_points": Tolerance.exact(
        "A count. If rounding moved a step size across the fit rule's boundary, the fit "
        "would use different points: a different result, reported as such."
    ),
    "methods.*.order": Tolerance(
        relative=1e-6,
        absolute=0.0,
        reason="Fitted only over steps whose errors are far above rounding (the fit rule), "
        "so rounding moves the slope by far less than 1e-9; 1e-6 relative is the margin.",
    ),
    "methods.*.final_energy_ratio": Tolerance(
        relative=2e-8,
        absolute=0.0,
        reason="E_N/E_0 is within ENERGY_IDENTITY_C N eps of its exact value on any machine "
        "(500 x 5e4 x 2.2e-16 ~ 5.6e-9 at the per-run cap), so two machines differ by at most "
        "~1.1e-8; 2e-8 relative. Null (diverged) must stay null.",
    ),
    "methods.*.max_relative_energy_error": Tolerance(
        relative=2e-8,
        absolute=2e-8,
        reason="A maximum over the nodes of |E_n - E_0|/E_0: rounding moves it by at most "
        "MODIFIED_ENERGY_C or ENERGY_IDENTITY_C N eps (<= 5.6e-9 at the per-run cap) on each "
        "machine, so 2e-8 absolute; 2e-8 relative for the large values of a growing (Euler) "
        "run. A divergence step moved by rounding would be a different result, reported.",
    ),
}


OSCILLATOR_INTEGRATORS = ModelEntry(
    info=integrator_model.MODEL_INFO,
    request_type=OscillatorIntegratorRequest,
    compute=integrator_model.run,
    inputs=lambda req, _: req.model_dump(
        include={"parameters", "dt_values", "methods", "energy_dt", "periods"}
    ),
    summary=_study_summary,
    respond=_study_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=lambda inputs, _: OscillatorIntegratorRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
    tolerances=lambda inputs, summary: _STUDY_TOLERANCES,
    headline=lambda s: ", ".join(
        f"{method} p≈{'n/a' if m['order'] is None else f'{m["order"]:.2f}'}"
        for method, m in s["methods"].items()
    ),
)


@router.post("/oscillator/integrators")
async def oscillator_integrator_study(
    request: OscillatorIntegratorRequest, repo: Repository
) -> OscillatorIntegratorResponse:
    return await execute(OSCILLATOR_INTEGRATORS, request, repo, save=request.save_experiment)
