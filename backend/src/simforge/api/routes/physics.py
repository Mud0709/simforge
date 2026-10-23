from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from simforge.api.dependencies import Repository
from simforge.api.runs import ModelEntry, Tolerance, execute
from simforge.core import formatting as fmt
from simforge.core.schemas import ModelInfo, RunMetadata
from simforge.physics.projectile import integrator_model
from simforge.physics.projectile import model as projectile
from simforge.physics.projectile.integrator_schemas import (
    IntegratorStudyRequest,
    IntegratorStudyResponse,
)
from simforge.physics.projectile.schemas import (
    AngleSweepRequest,
    AngleSweepResponse,
    ProjectileRequest,
    ProjectileResponse,
)

router = APIRouter(prefix="/physics", tags=["physics"])


# --- Projectile ---------------------------------------------------------------------------


def _projectile_response(
    request: ProjectileRequest, result: projectile.ProjectileComputation, metadata: RunMetadata
) -> ProjectileResponse:
    return ProjectileResponse(
        model=projectile.MODEL_INFO,
        parameters=request.parameters,
        solver=request.solver,
        units=projectile.UNITS,
        assumptions=projectile.ASSUMPTIONS,
        analytical=result.analytical,
        numerical=result.numerical,
        comparison=result.comparison,
        series=result.series,
        metadata=metadata,
    )


_QUANTITIES = ("flight_time", "impact_speed", "max_height", "range")
_ROUNDING = (
    "Closed-form expressions (the flight time from Brent's method, converged to about "
    "1e-15). Another machine changes them by a few rounding errors of about 1e-16 each; "
    "1e-12 relative leaves a wide margin."
)


def _projectile_tolerances(inputs: dict[str, Any], summary: dict[str, Any]) -> dict[str, Tolerance]:
    rtol, atol = inputs["solver"]["rtol"], inputs["solver"]["atol"]
    exact = summary["analytical"]
    scale = max(1.0, *(abs(exact[q]) for q in _QUANTITIES))
    solver = (
        "The adaptive solver controls its error to about rtol*|x| + atol. Rounding on another "
        "machine can change one accept/reject decision and so move a result by up to that "
        "much; a factor of 10 is the margin."
    )
    rules: dict[str, Tolerance] = {
        "analytical.*": Tolerance(relative=1e-12, absolute=0.0, reason=_ROUNDING),
        "numerical.method": Tolerance.exact("The chosen solver, copied from the inputs."),
        "numerical.rtol": Tolerance.exact("A solver setting, copied from the inputs."),
        "numerical.atol": Tolerance.exact("A solver setting, copied from the inputs."),
        "numerical.n_steps": Tolerance.exact(
            "A count: a different number of steps is a different computation."
        ),
        "numerical.n_rhs_evaluations": Tolerance.exact(
            "A count: a different number of evaluations is a different computation."
        ),
        "numerical.apex_time": Tolerance(relative=10 * rtol, absolute=10 * atol, reason=solver),
        "comparison.max_position_error": Tolerance(
            relative=0.0,
            absolute=10 * (rtol * max(abs(exact["range"]), abs(exact["max_height"])) + atol),
            reason="An error estimate, itself near rounding size, so only an absolute "
            "tolerance makes sense: it may move by the solver's error control, "
            "rtol x max(range, height) + atol (m), with a factor of 10 margin.",
        ),
        "comparison.max_energy_balance_residual": Tolerance(
            relative=0.0,
            absolute=10 * (rtol + atol / scale),
            reason="A relative energy error near rounding size: absolute tolerance "
            "10*(rtol + atol/S), S = the largest of range, height, speed and time (at least 1).",
        ),
    }
    for q in _QUANTITIES:
        size = max(abs(exact[q]), atol)
        rules[f"numerical.{q}"] = Tolerance(relative=10 * rtol, absolute=10 * atol, reason=solver)
        rules[f"comparison.{q}.absolute"] = Tolerance(
            relative=0.0,
            absolute=10 * (rtol * size + atol),
            reason="An error estimate, itself near rounding size, so only an absolute "
            "tolerance makes sense (2e-11 becoming 3e-11 is a 50% change and still correct): "
            "10*(rtol*|x| + atol), the solver's error control with a factor of 10.",
        )
        rules[f"comparison.{q}.relative"] = Tolerance(
            relative=0.0,
            absolute=10 * (rtol + atol / size),
            reason="The same error estimate divided by |x|: absolute tolerance "
            "10*(rtol + atol/|x|).",
        )
    return rules


PROJECTILE = ModelEntry(
    info=projectile.MODEL_INFO,
    request_type=ProjectileRequest,
    compute=projectile.run,
    # Only the inputs that affect the numbers are hashed (not save_experiment).
    inputs=lambda req, _: req.model_dump(include={"parameters", "solver", "n_samples"}),
    summary=lambda r: {
        "analytical": r.analytical.model_dump(exclude={"method_note"}),
        "numerical": r.numerical.model_dump(),
        "comparison": r.comparison.model_dump(),
    },
    respond=_projectile_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=lambda inputs, _: ProjectileRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
    tolerances=_projectile_tolerances,
    headline=lambda s: (
        f"range {fmt.sig(s['analytical']['range'])} m, "
        f"error {fmt.exp(s['comparison']['max_position_error'])} m"
    ),
)


@router.get("/projectile/info")
def projectile_info() -> ModelInfo:
    return projectile.MODEL_INFO


@router.post("/projectile/simulate")
async def simulate_projectile(request: ProjectileRequest, repo: Repository) -> ProjectileResponse:
    return await execute(PROJECTILE, request, repo, save=request.save_experiment)


# --- Integrator study ---------------------------------------------------------------------


def _study_summary(result: integrator_model.StudyComputation) -> dict[str, Any]:
    return {
        "horizon": result.horizon,
        "methods": {
            m.method: {
                "theoretical_order": m.theoretical_order,
                "position_order": m.position_fit.order if m.position_fit else None,
                "position_fit_points": m.position_fit.n_points if m.position_fit else 0,
                "velocity_order": m.velocity_fit.order if m.velocity_fit else None,
                "finest_max_position_error": m.runs[-1].max_position_error,
            }
            for m in result.results
        },
    }


def _study_response(
    request: IntegratorStudyRequest,
    result: integrator_model.StudyComputation,
    metadata: RunMetadata,
) -> IntegratorStudyResponse:
    return IntegratorStudyResponse(
        model=integrator_model.MODEL_INFO,
        parameters=request.parameters,
        dt_values=request.dt_values,
        methods=request.methods,
        units=integrator_model.UNITS,
        assumptions=integrator_model.ASSUMPTIONS,
        horizon=result.horizon,
        k=result.k,
        position_scale=result.position_scale,
        velocity_scale=result.velocity_scale,
        fit_rule=integrator_model.FIT_RULE,
        results=result.results,
        exact_trajectory=result.exact_trajectory,
        metadata=metadata,
    )


_STUDY_TOLERANCES = {
    "horizon": Tolerance(relative=1e-12, absolute=0.0, reason=_ROUNDING),
    "methods.*.theoretical_order": Tolerance.exact("A fixed property of the method."),
    "methods.*.position_fit_points": Tolerance.exact(
        "A count. If rounding moved a step size across the fit rule's boundary, the fit "
        "would use different points: a different result, reported as such."
    ),
    "methods.*.position_order": Tolerance(
        relative=1e-6,
        absolute=0.0,
        reason="Fitted only over steps whose errors are far above rounding (the fit rule), "
        "so rounding moves the slope by far less than 1e-9; 1e-6 relative is the margin.",
    ),
    "methods.*.velocity_order": Tolerance(
        relative=1e-6,
        absolute=0.0,
        reason="As for the position order: fitted only where errors are far above rounding.",
    ),
    "methods.*.finest_max_position_error": Tolerance(
        relative=0.0,
        absolute=1e-9,
        reason="At the finest step this error can be rounding-dominated (RK4 reaches about "
        "1e-13 m). Rounding of about 1e-14 m per step over at most 5e4 steps stays below "
        "about 5e-10 m, so 1e-9 m absolute.",
    ),
}


INTEGRATOR_STUDY = ModelEntry(
    info=integrator_model.MODEL_INFO,
    request_type=IntegratorStudyRequest,
    compute=integrator_model.run,
    inputs=lambda req, _: req.model_dump(include={"parameters", "dt_values", "methods"}),
    summary=_study_summary,
    respond=_study_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=lambda inputs, _: IntegratorStudyRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
    tolerances=lambda inputs, summary: _STUDY_TOLERANCES,
    headline=lambda s: ", ".join(
        f"{method} p≈{'n/a' if m['position_order'] is None else f'{m["position_order"]:.2f}'}"
        for method, m in s["methods"].items()
    ),
)


@router.post("/projectile/integrators")
async def integrator_study(
    request: IntegratorStudyRequest, repo: Repository
) -> IntegratorStudyResponse:
    return await execute(INTEGRATOR_STUDY, request, repo, save=request.save_experiment)


# --- Angle sweep --------------------------------------------------------------------------


def _sweep_response(
    request: AngleSweepRequest, computation: projectile.AngleSweepComputation, metadata: RunMetadata
) -> AngleSweepResponse:
    r = computation.result
    return AngleSweepResponse(
        model=projectile.ANGLE_SWEEP_INFO,
        parameters=request.parameters,
        units=projectile.ANGLE_SWEEP_UNITS,
        assumptions=projectile.ASSUMPTIONS,
        angles_deg=computation.angles_deg,
        ranges=[p.range for p in r.points],
        flight_times=[p.flight_time for p in r.points],
        max_heights=[p.max_height for p in r.points],
        best_angle_deg=r.best_angle_deg,
        best_range=r.best_range,
        vacuum_best_angle_deg=r.vacuum_best_angle_deg,
        vacuum_best_range=r.vacuum_best_range,
        method_note=projectile.ANGLE_SWEEP_NOTE,
        metadata=metadata,
    )


_SWEEP_TOLERANCES = {
    "best_angle_deg": Tolerance(
        relative=0.0,
        absolute=1e-5,
        reason="Brent's method finds the best angle to about 1e-6 degrees (the maximum is "
        "flat, so rounding hides smaller moves); 1e-5 degrees absolute is the margin.",
    ),
    "best_range": Tolerance(
        relative=1e-10,
        absolute=0.0,
        reason="At a flat maximum the range changes only with the square of the angle error "
        "(about 1e-16 relative for 1e-6 degrees), plus rounding; 1e-10 is the margin.",
    ),
    "vacuum_best_*": Tolerance(relative=1e-12, absolute=0.0, reason=_ROUNDING),
}


ANGLE_SWEEP = ModelEntry(
    info=projectile.ANGLE_SWEEP_INFO,
    request_type=AngleSweepRequest,
    compute=projectile.run_angle_sweep,
    # The launch angle does not affect a sweep, so it is left out of the hashed inputs (and a
    # rebuilt request uses the default angle).
    inputs=lambda req, _: {
        "parameters": req.parameters.model_dump(exclude={"launch_angle_deg"}),
        "n_angles": req.n_angles,
    },
    summary=lambda c: {
        "best_angle_deg": c.result.best_angle_deg,
        "best_range": c.result.best_range,
        "vacuum_best_angle_deg": c.result.vacuum_best_angle_deg,
        "vacuum_best_range": c.result.vacuum_best_range,
    },
    respond=_sweep_response,
    elapsed_ms=lambda c: c.elapsed_ms,
    rebuild=lambda inputs, _: AngleSweepRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
    tolerances=lambda inputs, summary: _SWEEP_TOLERANCES,
    # The response echoes the request's launch angle, which a sweep does not use.
    digest_exclude={"parameters": {"launch_angle_deg": True}},
    headline=lambda s: f"best angle {s['best_angle_deg']:.2f}°, range {fmt.sig(s['best_range'])} m",
)


@router.post("/projectile/angle-sweep")
async def projectile_angle_sweep(
    request: AngleSweepRequest, repo: Repository
) -> AngleSweepResponse:
    return await execute(ANGLE_SWEEP, request, repo, save=request.save_experiment)
