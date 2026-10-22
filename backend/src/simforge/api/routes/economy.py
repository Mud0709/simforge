from __future__ import annotations

from fastapi import APIRouter

from simforge.api.dependencies import Repository
from simforge.api.runs import ModelEntry, execute
from simforge.core.schemas import ModelInfo, RunMetadata
from simforge.economy.solow import model as solow
from simforge.economy.solow.schemas import SolowRequest, SolowResponse

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
)


@router.get("/solow/info")
def solow_info() -> ModelInfo:
    return solow.MODEL_INFO


@router.post("/solow/simulate")
async def simulate_solow(request: SolowRequest, repo: Repository) -> SolowResponse:
    return await execute(SOLOW, request, repo, save=request.save_experiment)
