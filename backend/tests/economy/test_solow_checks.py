"""Per-run checks of the Solow model: what each check reports, and that its note is true.

Expected values are hand-worked from the closed forms (half-life ln 2 / -ln(1 - (1 - alpha)
lambda / D)) or come from invariants (a run that starts at the steady state with no policy
change never moves), never from the code under test.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import ValidationCheck
from simforge.economy.solow import model
from simforge.economy.solow import simulation as sim
from simforge.economy.solow.schemas import SolowRequest

URL = "/api/v1/economy/solow/simulate"


def checks_of(client: TestClient, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    r = client.post(URL, json={**payload, "save_experiment": False})
    assert r.status_code == 200, r.text
    return {c["id"]: c for c in r.json()["checks"]}


# --- distance_to_new_steady_state ---------------------------------------------------------


def test_default_run_note_gives_the_true_reason_for_not_converging(client: TestClient) -> None:
    # Defaults: alpha 0.3, n 0.01, g 0.02, delta 0.05, policy year 20, horizon 100.
    # lambda = 0.0802, D = 1.0302, 1 - rho = 0.7 * 0.0802 / 1.0302 = 0.05449,
    # half-life = ln 2 / -ln(0.94551) = 12.37 years; 80 years after the change = 6.5.
    check = checks_of(client, {})["distance_to_new_steady_state"]
    assert 1e-3 < check["value"] < 1e-2  # not converged to 1e-6
    note = check["note"]
    assert "short" not in note  # 6.5 half-lives is not "short compared with the half-life"
    assert "80 years" in note
    assert "6.5 half-lives" in note
    assert "1e-6" in note
    # More half-lives needed: log2(6.774e-3 / 1e-6) = log2(6774) = 12.7, x 12.37 = 157 years.
    assert "12.7 more (157 years)" in note
    assert "estimate" in note


def test_the_estimated_extra_years_really_bring_the_gap_near_the_tolerance(
    client: TestClient,
) -> None:
    # Independent check of the note's estimate: simulate the 157 extra years it predicts.
    # A linearised estimate, so we accept a factor of 2 either side of 1e-6.
    check = checks_of(client, {"horizon_years": 100 + 157})["distance_to_new_steady_state"]
    assert 0.5e-6 < check["value"] < 2e-6


def test_long_run_note_reports_convergence_with_the_real_tolerance(client: TestClient) -> None:
    # 480 years after the change is about 39 half-lives: the gap shrinks by ~2^-39.
    check = checks_of(client, {"horizon_years": 500})["distance_to_new_steady_state"]
    assert check["value"] < model.CONVERGED_DISTANCE
    assert check["note"].startswith("Converged")
    assert "1e-6" in check["note"]


def test_convergence_note_follows_the_tolerance_constant(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(model, "CONVERGED_DISTANCE", 1e-300)
    note = checks_of(client, {"horizon_years": 500})["distance_to_new_steady_state"]["note"]
    assert not note.startswith("Converged")
    assert "1e-300" in note


# --- final_growth_gap ---------------------------------------------------------------------


def test_growth_gap_is_zero_for_a_run_that_starts_and_stays_at_the_steady_state(
    client: TestClient,
) -> None:
    # k_0 = k*(s0) and s1 = s0: k never moves, so G_t = g exactly up to rounding.
    payload = {"parameters": {"initial_capital_ratio": 1.0}, "policy": {"new_savings_rate": 0.2}}
    assert checks_of(client, payload)["final_growth_gap"]["value"] < 1e-14


def test_growth_gap_uses_the_final_year_not_the_first(client: TestClient) -> None:
    # Starting at half of k*, growth in year 0 is far above g; after 480 years at the new
    # steady state it is within rounding of g. Reading growth[0] would give a large gap.
    gap = checks_of(client, {"horizon_years": 500})["final_growth_gap"]["value"]
    assert gap < 1e-12


# --- identical_before_policy --------------------------------------------------------------


def _checks_with(
    request: SolowRequest, scenario: sim.SolowPath | None = None
) -> dict[str, ValidationCheck]:
    c = model.run(request)
    k0, k1 = c.baseline_steady_state.capital, c.scenario_steady_state.capital
    checks = model.per_run_checks(request, c.baseline, scenario or c.scenario, k0, k1)
    return {x.id: x for x in checks}


@pytest.mark.parametrize("field", ["capital", "output", "consumption", "investment"])
def test_identity_check_compares_every_quantity_before_the_change(field: str) -> None:
    request = SolowRequest()  # policy year 20
    scenario = model.run(request).scenario
    changed = getattr(scenario, field).copy()
    changed[5] *= 1.0 + 1e-15  # one entry, well before the change, off by ~1 ulp
    tampered = dataclasses.replace(scenario, **{field: changed})
    check = _checks_with(request, tampered)["identical_before_policy"]
    assert check.value == 1.0
    assert check.passed is False


def test_identity_check_ignores_consumption_in_the_policy_year() -> None:
    # c_T and i_T already use s1 (year-T output is saved at s1), so they may differ.
    request = SolowRequest()
    c = model.run(request)
    assert c.baseline.consumption[20] != c.scenario.consumption[20]
    assert _checks_with(request)["identical_before_policy"].passed is True


def test_identity_note_is_well_formed_when_the_policy_starts_in_year_0(
    client: TestClient,
) -> None:
    note = checks_of(client, {"policy": {"policy_year": 0}})["identical_before_policy"]["note"]
    assert "-1" not in note
    assert "k_0..k_0" not in note
    assert "y_0" in note


def test_identity_note_names_all_four_quantities(client: TestClient) -> None:
    note = checks_of(client, {})["identical_before_policy"]["note"]
    assert "k and y for t = 0..20" in note
    assert "c and i for t = 0..19" in note


# --- guards -------------------------------------------------------------------------------


def test_non_finite_half_life_is_a_domain_error_not_an_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unreachable within today's bounds; the guard protects against wider future bounds.
    monkeypatch.setattr(sim, "half_life", lambda e: float("inf"))
    with pytest.raises(ModelDomainError, match="half-life"):
        model.run(SolowRequest())


def test_overflowing_path_is_a_domain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real = sim.simulate_capital

    def overflowing(e: sim.SolowEconomy, savings: list[float], k0: float) -> np.ndarray:
        k = real(e, savings, k0)
        k[-1] = float("inf")
        return k

    monkeypatch.setattr(sim, "simulate_capital", overflowing)
    with pytest.raises(ModelDomainError, match="capital overflowed"):
        model.run(SolowRequest())


# --- steady states reported once ----------------------------------------------------------


def test_reported_steady_state_is_the_one_used_for_the_checks() -> None:
    request = SolowRequest()
    c = model.run(request)
    k_star_1 = c.scenario_steady_state.capital
    distance = {x.id: x for x in c.checks}["distance_to_new_steady_state"].value
    assert distance == abs(c.scenario.capital[-1] / k_star_1 - 1.0)
