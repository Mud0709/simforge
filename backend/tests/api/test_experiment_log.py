"""The generic experiment log: model-written headlines, filtering by lab and paging.

Headline strings are hand-written literals (the same ones the frontend used to produce), so a
change of wording or rounding is caught rather than copied.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.persistence.experiments import ExperimentRecord, ExperimentRepository

LOG = "/api/v1/experiments"


def store(client: TestClient, model_id: str, summary: dict[str, Any], **extra: Any) -> str:
    repo: ExperimentRepository = client.app.state.experiments  # type: ignore[attr-defined]
    run_id = str(uuid.uuid4())
    repo.add(
        ExperimentRecord(
            run_id=run_id,
            model_id=model_id,
            model_version="1.0.0",
            created_at=extra.pop("created_at", "2026-10-23T00:00:00+00:00"),
            input_hash="a" * 64,
            inputs={},
            summary=summary,
            environment={},
            **extra,
        )
    )
    return run_id


def logged(client: TestClient, run_id: str) -> dict[str, Any]:
    entry: dict[str, Any] = next(r for r in client.get(LOG).json() if r["run_id"] == run_id)
    return entry


@pytest.mark.parametrize(
    ("model_id", "summary", "headline"),
    [
        (
            "physics.projectile",
            {"analytical": {"range": 36.3885591}, "comparison": {"max_position_error": 2.2e-11}},
            "range 36.3886 m, error 2.2e-11 m",
        ),
        (
            "physics.projectile.integrators",
            {"methods": {"euler": {"position_order": 1.0089}, "rk4": {"position_order": None}}},
            "euler p≈1.01, rk4 p≈n/a",
        ),
        (
            "physics.projectile.angle_sweep",
            {"best_angle_deg": 42.482715067753304, "best_range": 34.20957706621005},
            "best angle 42.48°, range 34.2096 m",
        ),
        (
            "economy.solow",
            {
                "baseline_steady_state_capital": 3.689237466703935,
                "scenario_steady_state_capital": 6.584086866307975,
                "half_life_years": 12.369823364170164,
            },
            "k* 3.689 → 6.584, half-life 12.4 y",
        ),
        (
            "quant.dataset_profile",
            {"rows": 10, "columns": 6, "missing_cells": 7, "duplicate_rows": 1},
            "10 rows \N{MULTIPLICATION SIGN} 6 columns, 7 missing cells, 1 duplicate rows",
        ),
        (
            "physics.projectile.quadratic_drag",
            {"numerical": {"range": 30.12345678}, "terminal_speed": 31.31557},
            "range 30.1235 m, v_t 31.3156 m/s",
        ),
        (
            "physics.projectile.quadratic_drag",
            {"numerical": {"range": 10.183098861837907}, "terminal_speed": None},
            "range 10.1831 m, no drag",
        ),
    ],
)
def test_each_model_writes_its_own_headline(
    client: TestClient, model_id: str, summary: dict[str, Any], headline: str
) -> None:
    entry = logged(client, store(client, model_id, summary))
    assert entry["headline"] == headline
    assert entry["lab"] == model_id.split(".")[0]


def test_a_real_run_gets_a_headline(client: TestClient) -> None:
    run = client.post("/api/v1/economy/solow/simulate", json={}).json()
    assert logged(client, run["metadata"]["run_id"])["headline"].startswith("k* 3.689 → ")


@pytest.mark.parametrize(
    ("model_id", "summary"),
    [("economy.retired_model", {"x": 1}), ("economy.solow", {"unexpected": "shape"})],
)
def test_an_unknown_model_or_old_summary_gets_a_dash(
    client: TestClient, model_id: str, summary: dict[str, Any]
) -> None:
    assert logged(client, store(client, model_id, summary))["headline"] == "—"


def test_the_log_can_be_filtered_by_lab(client: TestClient) -> None:
    store(client, "economy.solow", {})
    store(client, "physics.projectile", {})
    store(client, "quant.dataset_profile", {})
    labs = {r["lab"] for r in client.get(LOG, params={"lab": "physics"}).json()}
    assert labs == {"physics"}
    assert client.get(LOG, params={"lab": "chemistry"}).status_code == 422


def test_the_log_pages_newest_first(client: TestClient) -> None:
    ids = [
        store(client, "economy.solow", {}, created_at=f"2026-10-2{i}T00:00:00+00:00")
        for i in range(1, 4)
    ]  # ids[2] is the newest
    first = [r["run_id"] for r in client.get(LOG, params={"limit": 2}).json()]
    rest = [r["run_id"] for r in client.get(LOG, params={"limit": 2, "offset": 2}).json()]
    assert first == [ids[2], ids[1]]
    assert rest == [ids[0]]


def test_a_single_run_has_its_headline_too(client: TestClient) -> None:
    run_id = store(client, "economy.solow", {"half_life_years": 1.0})
    assert client.get(f"{LOG}/{run_id}").json()["headline"] == "—"


def test_the_log_says_which_runs_need_their_file_to_replay(client: TestClient) -> None:
    import base64

    upload = base64.b64encode(b"a,b\n1,2\n").decode()
    runs = {
        "upload": (
            "/api/v1/quant/datasets/profile",
            {"source": {"kind": "upload", "content_base64": upload}},
        ),
        "sample": (
            "/api/v1/quant/datasets/profile",
            {"source": {"kind": "sample", "sample_id": "messy_survey"}},
        ),
        "solow": ("/api/v1/economy/solow/simulate", {}),
    }
    needs = {}
    for name, (url, body) in runs.items():
        run_id = client.post(url, json={**body, "save_experiment": True}).json()["metadata"][
            "run_id"
        ]
        needs[name] = client.get(f"{LOG}/{run_id}").json()["replay_needs_file"]
    assert needs == {"upload": True, "sample": False, "solow": False}
