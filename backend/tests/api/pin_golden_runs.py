"""Re-pin the golden runs: ``uv run python -m tests.api.pin_golden_runs`` (from backend/).

Only after a deliberate output change with a model version bump; see test_golden_digests.py.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
from typing import Any

from fastapi.testclient import TestClient

from simforge.config import Settings
from simforge.main import create_app
from tests.api.test_registry import CASES

GOLDEN_FILE = pathlib.Path(__file__).with_name("golden_runs.json")
ENVIRONMENT_KEYS = ("numpy_version", "scipy_version", "platform", "cpu")


def current_runs() -> list[dict[str, Any]]:
    """Each case's model version, output digest, inputs, summary and environment, as now."""
    runs = []
    with tempfile.TemporaryDirectory() as d:
        app = create_app(Settings(db_path=pathlib.Path(d) / "golden.sqlite3"))
        with TestClient(app) as client:
            for model_id, url, body, _ in CASES:
                meta = client.post(url, json={**body, "save_experiment": True}).json()["metadata"]
                record = client.get(f"/api/v1/experiments/{meta['run_id']}").json()
                runs.append(
                    {
                        "model_id": model_id,
                        "model_version": record["model_version"],
                        "output_digest": meta["output_digest"],
                        "inputs": record["inputs"],
                        "summary": record["summary"],
                        "environment": {k: meta[k] for k in ENVIRONMENT_KEYS},
                    }
                )
    return runs


if __name__ == "__main__":
    GOLDEN_FILE.write_text(json.dumps(current_runs(), indent=1, sort_keys=True) + "\n")
    print(f"pinned {GOLDEN_FILE}")
