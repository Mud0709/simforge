from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter

from simforge.api.dependencies import Repository
from simforge.api.runs import ModelEntry, Tolerance, execute
from simforge.core import formatting as fmt
from simforge.core.schemas import ModelInfo, RunMetadata
from simforge.physics.projectile import integrator_model
from simforge.physics.projectile import model as projectile
from simforge.physics.projectile import quadratic_angle_sweep as qas
from simforge.physics.projectile import quadratic_model as quadratic
from simforge.physics.projectile.integrator_schemas import (
    IntegratorStudyRequest,
    IntegratorStudyResponse,
)
from simforge.physics.projectile.quadratic_numerical import QuadraticSetup
from simforge.physics.projectile.quadratic_schemas import (
    QuadraticAngleSweepRequest,
    QuadraticAngleSweepResponse,
    QuadraticDiagnostics,
    QuadraticDragParameters,
    QuadraticDragRequest,
    QuadraticDragResponse,
    QuadraticDragSeries,
    QuadraticVacuumFlight,
    QuadraticVerticalFlight,
    QuadraticVerticalReference,
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


# --- Quadratic drag (roadmap 2.1) -----------------------------------------------------------


def _quadratic_setup(p: QuadraticDragParameters) -> QuadraticSetup:
    return QuadraticSetup(
        initial_speed=p.initial_speed,
        launch_angle_rad=math.radians(p.launch_angle_deg),  # 90 -> pi/2 exactly
        launch_height=p.launch_height,
        mass=p.mass,
        drag_constant=p.drag_constant,
        gravity=p.gravity,
    )


def _quadratic_run(request: QuadraticDragRequest) -> quadratic.QuadraticComputation:
    setup = _quadratic_setup(request.parameters)
    return quadratic.run(setup, request.solver, n_samples=request.n_samples)


def _vertical_reference(
    ref: quadratic.VerticalReference | None,
) -> QuadraticVerticalReference | None:
    if ref is None:
        return None
    e = ref.exact
    return QuadraticVerticalReference(
        exact=QuadraticVerticalFlight(
            apex_time=e.apex_time,
            max_height=e.max_height,
            fall_time=e.fall_time,
            flight_time=e.flight_time,
            impact_speed=e.impact_speed,
        ),
        flight_time=ref.flight_time,
        apex_time=ref.apex_time,
        max_height=ref.max_height,
        impact_speed=ref.impact_speed,
        method_note=ref.method_note,
    )


def _quadratic_response(
    request: QuadraticDragRequest, r: quadratic.QuadraticComputation, metadata: RunMetadata
) -> QuadraticDragResponse:
    v, d, s = r.vacuum, r.diagnostics, r.series
    return QuadraticDragResponse(
        model=quadratic.MODEL_INFO,
        parameters=request.parameters,
        solver=request.solver,
        units=quadratic.UNITS,
        assumptions=quadratic.ASSUMPTIONS,
        numerical=r.numerical,
        numerical_note=quadratic.NUMERICAL_NOTE,
        terminal_speed=r.terminal_speed,
        vacuum=QuadraticVacuumFlight(
            flight_time=v.flight_time,
            range=v.range,
            max_height=v.max_height,
            apex_time=v.apex_time,
            impact_speed=v.impact_speed,
            method_note=v.method_note,
        ),
        vertical_reference=_vertical_reference(r.vertical_reference),
        diagnostics=QuadraticDiagnostics(
            max_energy_balance_residual=d.max_energy_balance_residual,
            max_invariant_residual=d.max_invariant_residual,
            invariant_note=d.invariant_note,
            drag_time_bound=d.drag_time_bound,
            flight_time_bound=d.flight_time_bound,
        ),
        checks=r.checks,
        series=QuadraticDragSeries(
            t=s.t,
            x=s.x,
            y=s.y,
            speed=s.speed,
            kinetic_energy=s.kinetic_energy,
            potential_energy=s.potential_energy,
            drag_work=s.drag_work,
            vacuum_t=s.vacuum_t,
            vacuum_x=s.vacuum_x,
            vacuum_y=s.vacuum_y,
        ),
        metadata=metadata,
    )


_VACUUM_FIELDS = ("flight_time", "range", "max_height", "apex_time", "impact_speed")


def _quadratic_summary(r: quadratic.QuadraticComputation) -> dict[str, Any]:
    d = r.diagnostics
    return {
        "numerical": r.numerical.model_dump(),
        "terminal_speed": r.terminal_speed,
        "vacuum": {q: getattr(r.vacuum, q) for q in _VACUUM_FIELDS},
        "diagnostics": {
            "max_energy_balance_residual": d.max_energy_balance_residual,
            "max_invariant_residual": d.max_invariant_residual,
            "drag_time_bound": d.drag_time_bound,
            "flight_time_bound": d.flight_time_bound,
        },
    }


_CLOSED_FORM = (
    "A closed form (square roots, and for the vacuum flight the textbook formulas): a few "
    "rounding errors of about 1e-16 each on another machine; 1e-12 relative leaves a wide "
    "margin."
)


# Below rtol = 1e-10 the solver's results are set by rounding, not by its error control, so
# the replay rules use max(rtol, this) in place of rtol. Measured in the slice 3 review by
# emulating another CPU (each drag evaluation multiplied by 1 +- 1 or 2 ulp; 1728 reruns on a
# grid of speeds, angles up to 90, heights, drag, all three methods, rtol 1e-13 to 1e-3): at
# rtol = 1e-13 results moved by up to 1e-10 relative (a nearly vertical flight's range, DOP853)
# and Radau's energy residual once from 1.2e-13 to 6.5e-10, up to 650 times the plain rule.
# At rtol >= 1e-10 (the default and the golden run) the rules are unchanged.
_REPLAY_RTOL_FLOOR = 1e-10


def _quadratic_tolerances(inputs: dict[str, Any], summary: dict[str, Any]) -> dict[str, Tolerance]:
    rtol = max(inputs["solver"]["rtol"], _REPLAY_RTOL_FLOOR)
    atol = inputs["solver"]["atol"]
    setup = _quadratic_setup(QuadraticDragParameters.model_validate(inputs["parameters"]))
    solver = (
        "The adaptive solver controls its error to about rtol*|x| + atol. Rounding on another "
        "machine can change one accept/reject decision and so move a result by up to that "
        "much; a factor of 10 is the margin (the linear model's rule). Below rtol = 1e-10 "
        "rounding, not rtol, sets the accuracy, so rtol is taken as at least 1e-10 here "
        "(measured: up to 1e-10 relative at rtol = 1e-13 with last-bit differences)."
    )
    if setup.vx0 > 0:
        # The velocities I depends on are vx (relative to itself, and vx0 is small for a
        # nearly vertical launch) and, late in a long fall, vy against -v_t, so the model's
        # check uses rtol + atol / min(vx0, v_t) as their requested accuracy.
        invariant_scale = rtol + atol / min(setup.vx0, setup.terminal_speed)
        invariant = Tolerance(
            relative=0.0,
            absolute=10 * invariant_scale,
            reason="A relative error of the velocities, near the solver's error control, so "
            "only an absolute tolerance makes sense: 10*(rtol + atol/min(vx0, v_t)), the "
            "requested accuracy of vx and vy that the invariant check itself uses, with a "
            "factor of 10 and rtol taken as at least 1e-10, below which rounding sets the "
            "accuracy (null, when the invariant is undefined, must stay null).",
        )
    else:
        invariant = Tolerance.exact(
            "Null for a vertical launch (vx = 0, and the invariant divides by vx)."
        )
    rules: dict[str, Tolerance] = {
        "numerical.method": Tolerance.exact("The chosen solver, copied from the inputs."),
        "numerical.rtol": Tolerance.exact("A solver setting, copied from the inputs."),
        "numerical.atol": Tolerance.exact("A solver setting, copied from the inputs."),
        "numerical.n_steps": Tolerance.exact(
            "A count: a different number of steps is a different computation."
        ),
        "numerical.n_rhs_evaluations": Tolerance.exact(
            "A count: a different number of evaluations is a different computation."
        ),
        "terminal_speed": Tolerance(
            relative=1e-12,
            absolute=0.0,
            reason="sqrt(m g / c), a closed form with a few roundings (null in vacuum must "
            "stay null); 1e-12 relative leaves a wide margin.",
        ),
        "vacuum.*": Tolerance(relative=1e-12, absolute=0.0, reason=_CLOSED_FORM),
        "diagnostics.max_energy_balance_residual": Tolerance(
            relative=0.0,
            absolute=10 * (rtol + atol / setup.initial_speed),
            reason="A relative energy error near the solver's error control, so only an "
            "absolute tolerance makes sense: 10*(rtol + atol/v0), the requested relative "
            "accuracy of the state that the energy check itself uses, with a factor of 10 "
            "and rtol taken as at least 1e-10 (measured: Radau at rtol = 1e-13 moved it from "
            "1.2e-13 to 6.5e-10 with last-bit differences).",
        ),
        "diagnostics.max_invariant_residual": invariant,
        "diagnostics.drag_time_bound": Tolerance(
            relative=1e-12,
            absolute=0.0,
            reason="A proved bound in closed form (logarithms of the flight-time bound and "
            "the launch values): a few roundings; 1e-12 relative leaves a wide margin.",
        ),
        "diagnostics.flight_time_bound": Tolerance(
            relative=1e-12,
            absolute=0.0,
            reason="The rise bound vy0/g plus an exact linear-drag fall time found by "
            "Brent's method (converged to about 1e-15, as the linear model's flight time); "
            "1e-12 relative leaves a wide margin.",
        ),
    }
    for q in _VACUUM_FIELDS:
        rules[f"numerical.{q}"] = Tolerance(relative=10 * rtol, absolute=10 * atol, reason=solver)
    return rules


def _quadratic_headline(s: dict[str, Any]) -> str:
    v_t = s["terminal_speed"]
    drag = "no drag" if v_t is None else f"v_t {fmt.sig(v_t)} m/s"
    return f"range {fmt.sig(s['numerical']['range'])} m, {drag}"


QUADRATIC_DRAG = ModelEntry(
    info=quadratic.MODEL_INFO,
    request_type=QuadraticDragRequest,
    compute=_quadratic_run,
    # Only the inputs that affect the numbers are hashed (not save_experiment).
    inputs=lambda req, _: req.model_dump(include={"parameters", "solver", "n_samples"}),
    summary=_quadratic_summary,
    respond=_quadratic_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=lambda inputs, _: QuadraticDragRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
    tolerances=_quadratic_tolerances,
    headline=_quadratic_headline,
)


@router.post("/projectile/quadratic-drag/simulate")
async def simulate_quadratic_drag(
    request: QuadraticDragRequest, repo: Repository
) -> QuadraticDragResponse:
    return await execute(QUADRATIC_DRAG, request, repo, save=request.save_experiment)


# --- Quadratic-drag angle sweep (roadmap 2.2) -----------------------------------------------


def _quadratic_sweep_run(
    request: QuadraticAngleSweepRequest,
) -> qas.QuadraticAngleSweepComputation:
    setup = _quadratic_setup(request.parameters)  # its launch angle is ignored by the sweep
    return qas.run_angle_sweep(setup, request.solver, request.n_angles)


def _quadratic_sweep_response(
    request: QuadraticAngleSweepRequest,
    c: qas.QuadraticAngleSweepComputation,
    metadata: RunMetadata,
) -> QuadraticAngleSweepResponse:
    s = c.sweep
    return QuadraticAngleSweepResponse(
        model=qas.MODEL_INFO,
        parameters=request.parameters,
        solver=request.solver,
        units=qas.UNITS,
        assumptions=quadratic.ASSUMPTIONS,
        angles_deg=[p.angle_deg for p in s.points],
        ranges=[p.range for p in s.points],
        flight_times=[p.flight_time for p in s.points],
        max_heights=[p.max_height for p in s.points],
        vacuum_ranges=c.vacuum_ranges,
        best_angle_deg=s.best_angle_deg,
        best_range=s.best_range,
        best_angle_uncertainty_deg=s.best_angle_uncertainty_deg,
        best_angle_note=s.best_angle_note,
        vacuum_best_angle_deg=c.vacuum_best_angle_deg,
        vacuum_best_range=c.vacuum_best_range,
        terminal_speed=c.terminal_speed,
        n_runs=len(s.runs),
        n_rhs_evaluations=s.n_rhs_evaluations,
        checks=c.checks,
        method_note=qas.METHOD_NOTE,
        metadata=metadata,
    )


def _quadratic_sweep_summary(c: qas.QuadraticAngleSweepComputation) -> dict[str, Any]:
    # Plan D10: the headline numbers; the curves and checks are shown, not stored.
    return {
        "best_angle_deg": c.sweep.best_angle_deg,
        "best_range": c.sweep.best_range,
        "best_angle_uncertainty_deg": c.sweep.best_angle_uncertainty_deg,
        "vacuum_best_angle_deg": c.vacuum_best_angle_deg,
        "vacuum_best_range": c.vacuum_best_range,
        "terminal_speed": c.terminal_speed,
        "n_rhs_evaluations": c.sweep.n_rhs_evaluations,
    }


# Brent's stall on a flat top and last bits on another CPU: the linear sweep's floor for the
# best angle, in degrees. Measured for this model in slice 3 by last-bit emulation (scratch,
# one machine: 223 sweeps x 4 reruns with each drag evaluation x (1 +- 1 or 2 ulp); v0 in
# {1, 10, 20, 300} m/s, c from 0 to 1 kg/m, h from 0 to 1e5 m, all three methods, (rtol, atol)
# in {(1e-6, 1e-6), (1e-10, 1e-10), (1e-13, 1e-14)}, 10 to 361 angles; 17 sweeps over budget):
# every value stayed within its rule (largest fraction used: best angle 0.08, best range
# 0.0023, u 0.0025); n_rhs_evaluations changed in 479 of the 892 reruns, so on another CPU a
# replay will often report "differs" on that count (exact by design, plan D11 and Risks).
_BEST_ANGLE_FLOOR = 1e-5


def _uncertainty_rule(inputs: dict[str, Any], summary: dict[str, Any]) -> Tolerance:
    """The replay rule for u = 2 sqrt(eps_R / K), derived from how K is computed.

    K = |d2| / step^2, with d2 = R(i+1) - 2 R(i) + R(i-1) the grid's second difference. If
    each range may move by dR = 10 (rtol' R + atol) on a replay (the best_range rule), d2
    moves by at most 4 dR, so u (proportional to K^-1/2) moves by at most 2 dR / |d2| relative,
    to first order. |d2| is not stored, but it follows from u itself: K = 4 eps_R / u^2 (u in
    radians), with eps_R = 10 (rtol R + atol) the value the model used (its real rtol)."""
    u = summary["best_angle_uncertainty_deg"]
    if u is None:
        return Tolerance.exact(
            "Null when the best grid point is at an edge, or the grid curve is not bent "
            "downwards there: null must stay null (a replay that finds the best grid point "
            "elsewhere is a different computation)."
        )
    rtol, atol = inputs["solver"]["rtol"], inputs["solver"]["atol"]
    rtol_replay = max(rtol, _REPLAY_RTOL_FLOOR)
    best = abs(summary["best_range"])
    step = math.radians(90.0 / (inputs["n_angles"] - 1))
    u_rad = math.radians(u)
    relative = (rtol_replay * best + atol) * u_rad**2 / (2 * (rtol * best + atol) * step**2)
    return Tolerance(
        relative=relative,
        absolute=0.0,
        reason="u comes from a second difference d2 of three grid ranges. If each range moves "
        "by up to dR = 10 (rtol' R + atol) (the best_range rule, rtol' = max(rtol, 1e-10)), "
        "d2 moves by at most 4 dR and u by at most 2 dR / |d2| relative, to first order; |d2| "
        "follows from u itself (K = 4 eps_R / u^2). Measured in slice 3 by emulating another "
        "CPU (each drag evaluation x (1 +- 1 or 2 ulp); 892 reruns of 223 sweeps, all "
        "three methods, rtol 1e-13 to 1e-6, 10 to 361 angles): u moved by at most 0.0025 of "
        "this tolerance (3.4e-6 relative), and the best grid point never moved. A replay "
        "whose best grid point moves to a neighbour is a different computation and is "
        "reported as differing.",
    )


def _quadratic_sweep_tolerances(
    inputs: dict[str, Any], summary: dict[str, Any]
) -> dict[str, Tolerance]:
    rtol = max(inputs["solver"]["rtol"], _REPLAY_RTOL_FLOOR)
    atol = inputs["solver"]["atol"]
    u = summary["best_angle_uncertainty_deg"]
    return {
        "best_range": Tolerance(
            relative=10 * rtol,
            absolute=10 * atol,
            reason="A numerical range at a flat maximum: the solver rule 10 (rtol' |x| + atol) "
            "of the quadratic-drag model, with rtol' = max(rtol, 1e-10), below which rounding "
            "sets the accuracy. An angle error of 1e-5 degrees changes the range only by "
            "about 1e-14 relative, so the solver rule alone sets it (last-bit emulation: at "
            "most 0.0023 of this tolerance).",
        ),
        "best_angle_deg": Tolerance(
            relative=0.0,
            absolute=_BEST_ANGLE_FLOOR if u is None else max(_BEST_ANGLE_FLOOR, u),
            reason="max(1e-5 degrees, u) absolute: the run's own stated uncertainty u (an "
            "estimate of how far the solver's error can move the peak), floored by the "
            "linear sweep's rule for Brent's stall on a flat top; 1e-5 degrees when u is null "
            "(an edge). Measured in slice 3 with last-bit emulation (the 892 reruns of the u "
            "rule): the best angle moved by at most 0.08 of this tolerance (5.6e-6 degrees "
            "at rtol = 1e-13, 6.8e-3 degrees at rtol = 1e-6, where u is larger still).",
        ),
        "best_angle_uncertainty_deg": _uncertainty_rule(inputs, summary),
        "vacuum_best_*": Tolerance(relative=1e-12, absolute=0.0, reason=_CLOSED_FORM),
        "terminal_speed": Tolerance(
            relative=1e-12,
            absolute=0.0,
            reason="sqrt(m g / c), a closed form with a few roundings (null in vacuum must "
            "stay null); 1e-12 relative leaves a wide margin.",
        ),
        "n_rhs_evaluations": Tolerance.exact(
            "A count over every run of the sweep: a different number of evaluations is a "
            "different computation."
        ),
    }


def _quadratic_sweep_headline(s: dict[str, Any]) -> str:
    v_t = s["terminal_speed"]
    drag = "no drag" if v_t is None else f"v_t {fmt.sig(v_t)} m/s"
    return f"best angle {s['best_angle_deg']:.2f}°, range {fmt.sig(s['best_range'])} m, {drag}"


QUADRATIC_ANGLE_SWEEP = ModelEntry(
    info=qas.MODEL_INFO,
    request_type=QuadraticAngleSweepRequest,
    compute=_quadratic_sweep_run,
    # The launch angle does not affect a sweep, so it is left out of the hashed inputs (and a
    # rebuilt request uses the default angle), as for the linear sweep.
    inputs=lambda req, _: {
        "parameters": req.parameters.model_dump(exclude={"launch_angle_deg"}),
        "solver": req.solver.model_dump(),
        "n_angles": req.n_angles,
    },
    summary=_quadratic_sweep_summary,
    respond=_quadratic_sweep_response,
    elapsed_ms=lambda c: c.elapsed_ms,
    rebuild=lambda inputs, _: QuadraticAngleSweepRequest.model_validate(
        {**inputs, "save_experiment": False}
    ),
    tolerances=_quadratic_sweep_tolerances,
    # The response echoes the request's launch angle, which a sweep does not use.
    digest_exclude={"parameters": {"launch_angle_deg": True}},
    headline=_quadratic_sweep_headline,
)


@router.post("/projectile/quadratic-drag/angle-sweep")
async def quadratic_drag_angle_sweep(
    request: QuadraticAngleSweepRequest, repo: Repository
) -> QuadraticAngleSweepResponse:
    return await execute(QUADRATIC_ANGLE_SWEEP, request, repo, save=request.save_experiment)
