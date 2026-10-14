"""Base schema types shared by every model.

Every request and result schema in SimForge derives from :class:`StrictModel`, so
three guarantees hold everywhere without each model re-implementing them:

* unknown fields are rejected (a typo such as ``"masss"`` is an error, not a silent default);
* ``NaN`` and ``±inf`` are rejected for every float field — Python's ``json`` module
  happily parses the non-standard literals ``NaN`` and ``Infinity``, so this has to be
  enforced explicitly;
* instances are immutable once validated.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class ModelInfo(StrictModel):
    """Identifies exactly which model (and which version of its equations) produced a result."""

    id: str = Field(description="Stable dotted identifier, e.g. 'physics.projectile'.")
    version: str = Field(description="Semantic version of the model's equations and outputs.")
    name: str
    description: str


class Assumption(StrictModel):
    """A modelling assumption, stated so a reader can judge when the model stops applying."""

    id: str
    statement: str


class RunMetadata(StrictModel):
    """Everything needed to reproduce (or audit) a single run."""

    run_id: str = Field(description="Unique identifier for this run (UUID4).")
    created_at: str = Field(description="UTC timestamp, ISO 8601.")
    input_hash: str = Field(
        description="SHA-256 of the canonical JSON of the validated inputs. Identical inputs "
        "produce identical hashes, so repeated runs can be grouped and compared."
    )
    simforge_version: str
    python_version: str
    numpy_version: str
    scipy_version: str
    platform: str
    elapsed_ms: float = Field(description="Wall-clock compute time. Not reproducible by nature.")
    experiment_saved: bool
