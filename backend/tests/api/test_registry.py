"""The model registry: one entry per model, and stored inputs rebuild the same computation.

The expected values are the records the live endpoints stored, so the test checks that a
replay would ask exactly the question the original run asked (same inputs, same hash).
"""

from __future__ import annotations

import base64
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.api.registry import ENTRIES, get_entry
from simforge.core.reproducibility import input_hash

UPLOAD = b"a,b,d\n1,x,2024-01-02\n2.5,y,\n,x,2024-03-01\n"

CASES: list[tuple[str, str, dict[str, Any], bytes | None]] = [
    (
        "physics.projectile",
        "/api/v1/physics/projectile/simulate",
        {"parameters": {"drag_coefficient": 0.3, "launch_angle_deg": 30}},
        None,
    ),
    (
        "physics.projectile.integrators",
        "/api/v1/physics/projectile/integrators",
        {"dt_values": [0.1, 0.05, 0.025], "methods": ["rk4", "euler"]},
        None,
    ),
    (
        "physics.projectile.angle_sweep",
        "/api/v1/physics/projectile/angle-sweep",
        {"parameters": {"drag_coefficient": 0.2, "launch_angle_deg": 10}, "n_angles": 31},
        None,
    ),
    (
        "economy.solow",
        "/api/v1/economy/solow/simulate",
        {"policy": {"policy_year": 5, "new_savings_rate": 0.25}, "horizon_years": 40},
        None,
    ),
    (
        "quant.dataset_profile",
        "/api/v1/quant/datasets/profile",
        {
            "source": {"kind": "sample", "sample_id": "messy_survey"},
            "options": {"missing_markers": ["NA"]},
        },
        None,
    ),
    (
        "quant.dataset_profile",
        "/api/v1/quant/datasets/profile",
        {
            "source": {"kind": "upload", "content_base64": base64.b64encode(UPLOAD).decode()},
            "options": {"column_types": [{"column": 0, "type": "categorical"}]},
        },
        UPLOAD,
    ),
    # Appended, not inserted: other tests index the cases above by position.
    (
        "physics.projectile.quadratic_drag",
        "/api/v1/physics/projectile/quadratic-drag/simulate",
        {"parameters": {"drag_constant": 0.02, "launch_angle_deg": 30}},
        None,
    ),
]


def test_every_model_served_by_the_api_has_exactly_one_entry() -> None:
    ids = [entry.info.id for entry in ENTRIES]
    assert len(ids) == len(set(ids))
    assert set(ids) == {case[0] for case in CASES}


@pytest.mark.parametrize(("model_id", "url", "body", "dataset"), CASES)
def test_stored_inputs_rebuild_the_same_computation(
    client: TestClient, model_id: str, url: str, body: dict[str, Any], dataset: bytes | None
) -> None:
    run = client.post(url, json={**body, "save_experiment": True}).json()
    record = client.get(f"/api/v1/experiments/{run['metadata']['run_id']}").json()
    assert record["model_id"] == model_id

    entry = get_entry(model_id)
    assert entry is not None
    request = entry.rebuild(record["inputs"], dataset)
    assert request.save_experiment is False  # a rebuild never writes to the log by itself
    result = entry.compute(request)
    assert entry.inputs(request, result) == record["inputs"]
    assert input_hash(entry.inputs(request, result)) == record["input_hash"]


def test_unknown_model_has_no_entry() -> None:
    assert get_entry("physics.perpetual_motion") is None
