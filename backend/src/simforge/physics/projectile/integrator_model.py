"""Orchestrates the integrator study: engine dataclasses -> validated API contract.

No HTTP and no database: the API layer adds run metadata and persistence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import Assumption, ModelInfo, ValidationCheck
from simforge.numerics.convergence import MIN_FIT_POINTS, OrderFit
from simforge.physics.projectile import analytical
from simforge.physics.projectile import integrator_study as study
from simforge.physics.projectile.integrator_schemas import (
    EventRun,
    FitRule,
    IntegratorRun,
    IntegratorStudyRequest,
    MethodStudyResult,
    OrderFitResult,
    ReferenceLine,
    TrajectorySample,
    XYSeries,
)
from simforge.physics.projectile.model import ASSUMPTIONS as PROJECTILE_ASSUMPTIONS
from simforge.physics.projectile.model import to_setup

MODEL_INFO = ModelInfo(
    id="physics.projectile.integrators",
    version="1.1.0",
    name="Integrator convergence study (projectile with linear drag)",
    description="Forward Euler, RK4 and velocity Verlet, implemented from scratch, compared "
    "against the exact linear-drag solution over a range of fixed time steps, with the "
    "landing located between steps by linear and cubic Hermite interpolation.",
)

UNITS: dict[str, str] = {
    "dt": "s",
    "h": "s",
    "kh": "dimensionless",
    "horizon": "s",
    "landing_time": "s",
    "landing_error": "s",
    "k": "1/s",
    "position_error": "m",
    "velocity_error": "m/s",
    "x": "m",
    "y": "m",
}

ASSUMPTIONS: list[Assumption] = [
    *PROJECTILE_ASSUMPTIONS,
    Assumption(
        id="fixed_horizon",
        statement="Every order run integrates over the same window [0, T], where T is the "
        "exact flight time, using N = ceil(T/dt) equal steps, so no landing detection "
        "error enters the method's order.",
    ),
    Assumption(
        id="event_location",
        statement="Each order run has a matching event run with h = T/(N + 1/2), so the "
        "exact landing sits mid-step. The landing is located between the two nodes "
        "straddling y = 0 by linear interpolation (order 2) and cubic Hermite "
        "interpolation using vy (order 4); the landing error is then O(h^min(p, q)). "
        "A run whose integrator and interpolation errors cancel (|e| < 0.5 x their sum) "
        "or whose error is at the round-off floor 100 (i + 1) eps T, or whose decay factor "
        "is off by more than 10% (|R(-kh)^N e^(kNh) - 1| > 0.1, pre-asymptotic), is left out "
        "of the fit.",
    ),
    Assumption(
        id="error_metric",
        statement="Errors are Euclidean distances from the exact solution at the grid "
        "nodes. The 'max' errors are the largest over all nodes; the 'final' errors are at "
        "t = T. The exact solution is evaluated in float64 (relative error ~1e-15), which "
        "is negligible next to the round-off floor.",
    ),
    Assumption(
        id="linear_invariant",
        statement="v + k r + g t y_hat is constant along the exact solution, and every "
        "Runge-Kutta method (including Euler and RK4) preserves it exactly. Their velocity "
        "error is therefore exactly k times their position error, so their velocity "
        "convergence is not independent evidence. Velocity Verlet does not preserve it.",
    ),
]

FIT_RULE = FitRule(
    max_kh=study.MAX_KH_FOR_FIT,
    max_h_over_horizon=study.MAX_H_OVER_T_FOR_FIT,
    roundoff_safety_factor=study.ROUNDOFF_SAFETY,
    min_points=MIN_FIT_POINTS,
    description=(
        f"A run enters the fit only if it is linearly stable (|R(-kh)| < 1), in the "
        f"asymptotic regime (kh <= {study.MAX_KH_FOR_FIT} and h <= T/"
        f"{round(1 / study.MAX_H_OVER_T_FOR_FIT)}), and its error exceeds "
        f"{study.ROUNDOFF_SAFETY:.0f} x N x machine epsilon x the solution's scale. An "
        f"order is reported only with at least {MIN_FIT_POINTS} such step sizes. The rule "
        "was fixed before any results were inspected."
    ),
)

EVENT_CANCELLATION_RATIO = study.EVENT_CANCELLATION_RATIO
# ||dv + k dr||_inf <= C N eps V for Euler and RK4 (an exact identity up to rounding).
# Measured worst 0.83 (test_projectile_event_location.py); >= 10x on the 1-2-5 series.
VELOCITY_POSITION_IDENTITY_C = 10.0
ORDER_TOL = 0.1

MAX_STEPS_PER_RUN = 50_000
MAX_TOTAL_STEPS = 150_000


@dataclass(frozen=True, slots=True)
class StudyComputation:
    horizon: float
    k: float
    position_scale: float
    velocity_scale: float
    results: list[MethodStudyResult]
    exact_trajectory: XYSeries
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


def _reference(
    runs: list[study.RunResult], fit: OrderFit | None, attr: str, flag: str, order: int
) -> ReferenceLine | None:
    """Theoretical-slope line over the fit range, anchored at the finest fitted point.

    Drawn only when a fit exists: the theoretical order is a statement about the
    asymptotic regime, so the line is only meaningful where the data are in it.
    """
    if fit is None:
        return None
    anchor = min((r for r in runs if getattr(r, flag)), key=lambda r: r.h)
    e0: float = getattr(anchor, attr)
    hs = [fit.h_min, fit.h_max]
    return ReferenceLine(order=order, h=hs, error=[e0 * (h / anchor.h) ** order for h in hs])


def _fit_note(m: study.MethodStudy) -> str | None:
    if m.position_fit is not None:
        return None
    n = sum(r.in_position_fit for r in m.runs)
    return (
        f"Only {n} step size(s) satisfied the fit rule (need {MIN_FIT_POINTS}); no order is "
        "claimed. Add smaller steps within the stability and asymptotic limits."
    )


def _order_check(cid: str, label: str, fit: OrderFitResult, what: str) -> ValidationCheck:
    gap = abs(fit.order - fit.theoretical_order)
    return ValidationCheck(
        id=cid,
        label=label,
        value=gap,
        threshold=ORDER_TOL,
        passed=gap <= ORDER_TOL,
        kind="numerical_diagnostic",
        note=f"Value: |fitted {what} order {fit.order:.3f} - {fit.theoretical_order}|. "
        "A measured slope, not a proof.",
    )


def _points_check(cid: str, label: str, fitted: int, total: int) -> ValidationCheck:
    return ValidationCheck(
        id=cid,
        label=label,
        value=float(fitted),
        threshold=None,
        passed=None,
        kind="informational",
        note=f"{fitted} of {total} runs met the fit rule (at least {MIN_FIT_POINTS} needed "
        "for an order).",
    )


def _checks(m: study.MethodStudy, r: MethodStudyResult) -> list[ValidationCheck]:
    name, out = r.name, []
    if r.position_fit is not None:
        out.append(
            _order_check(f"order_{r.method}", f"{name}: position order", r.position_fit, "position")
        )
    out.append(
        _points_check(
            f"fit_points_{r.method}",
            f"{name}: step sizes in the order fit",
            sum(x.in_position_fit for x in m.runs),
            len(m.runs),
        )
    )
    if r.method in study.RK_METHODS:
        res = m.identity_residual
        out.append(
            ValidationCheck(
                id=f"velocity_position_identity_{r.method}",
                label=f"{name}: velocity error = -k x position error",
                value=0.0 if res is None else res,
                threshold=VELOCITY_POSITION_IDENTITY_C,
                passed=None if res is None else res <= VELOCITY_POSITION_IDENTITY_C,
                kind="exact_identity",
                note="No stable, non-diverged run to check."
                if res is None
                else "Value: max over stable runs and nodes of ||dv + k dr||_inf / (N eps V), "
                "V = max|v| + k max|r| + g T. Runge-Kutta methods preserve v + k r + g t y_hat "
                "exactly, so only rounding remains.",
            )
        )
    for q in study.EVENT_KINDS:
        fit: OrderFitResult | None = getattr(r, f"landing_fit_{q}")
        evs = m.event_runs
        n_in = sum(getattr(e, f"in_{q}_fit") for e in evs)
        cid, label = f"event_order_{r.method}_{q}", f"{name}: landing-time order ({q})"
        if fit is not None:
            out.append(_order_check(cid, label, fit, f"{q} landing"))
        else:
            reasons = [getattr(e, f"{q}_exclusion_reason") or "" for e in evs]
            counts = {w: sum(w in x for x in reasons) for w in ("round-off", "cancel", "crossing")}
            out.append(
                ValidationCheck(
                    id=cid,
                    label=label,
                    value=float(n_in),
                    threshold=None,
                    passed=None,
                    kind="numerical_diagnostic",
                    note=f"No order fitted: {n_in} run(s) met the rule (need {MIN_FIT_POINTS}); "
                    f"excluded at the round-off floor: {counts['round-off']}, errors cancelling: "
                    f"{counts['cancel']}, no crossing: {counts['crossing']}, other reasons: "
                    f"{len(evs) - n_in - sum(counts.values())}.",
                )
            )
        out.append(
            _points_check(
                f"event_fit_points_{r.method}_{q}",
                f"{name}: event runs in the {q} landing fit",
                n_in,
                len(evs),
            )
        )
    return out


def run(request: IntegratorStudyRequest) -> StudyComputation:
    start = time.perf_counter()
    setup = to_setup(request.parameters)
    horizon = analytical.flight_time(setup)

    steps = [study.steps_for(horizon, dt) for dt in request.dt_values]
    if max(steps) > MAX_STEPS_PER_RUN:
        raise ModelDomainError(
            f"dt = {min(request.dt_values):.3g} s needs {max(steps)} steps over T = "
            f"{horizon:.4g} s; the limit is {MAX_STEPS_PER_RUN} per run. Use larger steps."
        )
    total = sum(steps) * len(request.methods)
    if total > MAX_TOTAL_STEPS:
        raise ModelDomainError(
            f"This study needs {total} steps in total; the limit is {MAX_TOTAL_STEPS}. "
            "Use fewer or larger time steps, or fewer methods."
        )

    result = study.run_study(setup, request.dt_values, request.methods, horizon=horizon)

    methods: list[MethodStudyResult] = []
    checks: list[ValidationCheck] = []
    for m in result.methods:
        p = m.theory.order
        methods.append(
            MethodStudyResult(
                method=m.method,
                name=m.theory.name,
                theoretical_order=p,
                stability_limit_kh=m.theory.stability_limit_kh,
                runs=[IntegratorRun.model_validate(r, from_attributes=True) for r in m.runs],
                position_local_orders=m.position_local_orders,
                velocity_local_orders=m.velocity_local_orders,
                position_fit=_fit(m.position_fit, p),
                velocity_fit=_fit(m.velocity_fit, p),
                position_reference=_reference(
                    m.runs, m.position_fit, "max_position_error", "in_position_fit", p
                ),
                velocity_reference=_reference(
                    m.runs, m.velocity_fit, "max_velocity_error", "in_velocity_fit", p
                ),
                fit_note=_fit_note(m),
                trajectory=(
                    TrajectorySample(
                        h=m.trajectory[2], x=m.trajectory[0].tolist(), y=m.trajectory[1].tolist()
                    )
                    if m.trajectory is not None
                    else None
                ),
                event_runs=[EventRun.model_validate(e, from_attributes=True) for e in m.event_runs],
                landing_fit_linear=_fit(m.landing_fit_linear, min(p, 2)),
                landing_fit_hermite=_fit(m.landing_fit_hermite, min(p, 4)),
            )
        )
        checks += _checks(m, methods[-1])

    x_ref, y_ref = result.exact_trajectory
    return StudyComputation(
        horizon=result.horizon,
        k=result.k,
        position_scale=result.position_scale,
        velocity_scale=result.velocity_scale,
        results=methods,
        exact_trajectory=XYSeries(x=x_ref.tolist(), y=y_ref.tolist()),
        checks=checks,
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )
