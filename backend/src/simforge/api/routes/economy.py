from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from simforge.api.dependencies import Repository
from simforge.api.recording import record_run
from simforge.core.errors import ModelDomainError
from simforge.core.schemas import ModelInfo
from simforge.economy.solow import model as solow
from simforge.economy.solow.schemas import SolowRequest, SolowResponse

router = APIRouter(prefix="/economy", tags=["economy"])


@router.get("/solow/info")
def solow_info() -> ModelInfo:
    return solow.MODEL_INFO


@router.post("/solow/simulate")
async def simulate_solow(request: SolowRequest, repo: Repository) -> SolowResponse:
    try:
        result = await run_in_threadpool(solow.run, request)
    except ModelDomainError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    years = list(range(request.horizon_years + 1))
    # SQLite I/O runs in a worker thread so it never blocks the event loop.
    metadata = await run_in_threadpool(
        record_run,
        repo,
        solow.MODEL_INFO,
        request.model_dump(include={"parameters", "policy", "horizon_years"}),
        {
            "baseline_steady_state_capital": result.baseline_steady_state.capital,
            "scenario_steady_state_capital": result.scenario_steady_state.capital,
            "golden_rule_savings_rate": result.golden_rule.savings_rate,
            "half_life_years": result.convergence.half_life_years,
            "final_capital": float(result.scenario.capital[-1]),
        },
        save=request.save_experiment,
        elapsed_ms=result.elapsed_ms,
    )
    return SolowResponse(
        model=solow.MODEL_INFO,
        parameters=request.parameters,
        policy=request.policy,
        horizon_years=request.horizon_years,
        units=solow.UNITS,
        assumptions=solow.ASSUMPTIONS,
        years=years,
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
