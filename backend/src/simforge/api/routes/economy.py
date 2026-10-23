from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from simforge.api.dependencies import Repository
from simforge.api.runs import ModelEntry, Tolerance, execute
from simforge.core import formatting as fmt
from simforge.core.schemas import ModelInfo, RunMetadata
from simforge.economy.solow import model as solow
from simforge.economy.solow import simulation as sim
from simforge.economy.solow.schemas import SolowParameters, SolowRequest, SolowResponse

router = APIRouter(prefix="/economy", tags=["economy"])


def _solow_response(
    request: SolowRequest, result: solow.SolowComputation, metadata: RunMetadata
) -> SolowResponse:
    return SolowResponse(
        model=solow.MODEL_INFO,
        parameters=request.parameters,
        policy=request.policy,
        horizon_years=request.horizon_years,
        units=solow.UNITS,
        assumptions=solow.ASSUMPTIONS,
        years=list(range(request.horizon_years + 1)),
        baseline=solow.path_response(result.baseline),
        scenario=solow.path_response(result.scenario),
        baseline_steady_state=result.baseline_steady_state,
        scenario_steady_state=result.scenario_steady_state,
        golden_rule=result.golden_rule,
        convergence=result.convergence,
        initial_capital=result.initial_capital,
        checks=result.checks,
        method_note=solow.METHOD_NOTE,
        metadata=metadata,
    )


_U = 2.0**-53  # unit roundoff


def _solow_tolerances(inputs: dict[str, Any], summary: dict[str, Any]) -> dict[str, Tolerance]:
    # The empirical rounding bounds in SCIENTIFIC_VALIDATION.md (held on the documented grid)
    # bound each run's error; two runs can differ by at most twice that.
    p = SolowParameters.model_validate(inputs["parameters"])
    alpha = p.capital_share
    gap = sim.convergence_gap(solow.to_economy(p))
    k_star = Tolerance(
        relative=2 * 8 * _U * (1 / (1 - alpha) + 2),
        absolute=0.0,
        reason="Twice the empirical bound on k*'s rounding error, 8u*(1/(1-alpha) + 2) "
        "(SCIENTIFIC_VALIDATION.md, economy.solow).",
    )
    return {
        "baseline_steady_state_capital": k_star,
        "scenario_steady_state_capital": k_star,
        "golden_rule_savings_rate": Tolerance.exact("Equal to alpha, copied from the inputs."),
        "half_life_years": Tolerance(
            relative=1e-12,
            absolute=0.0,
            reason="A closed form, ln 0.5 / log1p(-(1-rho)), with 1-rho computed directly: a few "
            "rounding errors; 1e-12 relative is the margin.",
        ),
        "final_capital": Tolerance(
            relative=2 * 64 * _U / gap,
            absolute=0.0,
            reason="Twice the empirical bound on a path's rounding error, 64u/(1-rho) "
            "(SCIENTIFIC_VALIDATION.md, economy.solow).",
        ),
    }


SOLOW = ModelEntry(
    info=solow.MODEL_INFO,
    request_type=SolowRequest,
    compute=solow.run,
    inputs=lambda req, _: req.model_dump(include={"parameters", "policy", "horizon_years"}),
    summary=lambda r: {
        "baseline_steady_state_capital": r.baseline_steady_state.capital,
        "scenario_steady_state_capital": r.scenario_steady_state.capital,
        "golden_rule_savings_rate": r.golden_rule.savings_rate,
        "half_life_years": r.convergence.half_life_years,
        "final_capital": float(r.scenario.capital[-1]),
    },
    respond=_solow_response,
    elapsed_ms=lambda r: r.elapsed_ms,
    rebuild=lambda inputs, _: SolowRequest.model_validate({**inputs, "save_experiment": False}),
    tolerances=_solow_tolerances,
    headline=lambda s: (
        f"k* {fmt.sig(s['baseline_steady_state_capital'], 4)} → "
        f"{fmt.sig(s['scenario_steady_state_capital'], 4)}, "
        f"half-life {fmt.sig(s['half_life_years'], 3)} y"
    ),
)


@router.get("/solow/info")
def solow_info() -> ModelInfo:
    return solow.MODEL_INFO


@router.post("/solow/simulate")
async def simulate_solow(request: SolowRequest, repo: Repository) -> SolowResponse:
    return await execute(SOLOW, request, repo, save=request.save_experiment)
