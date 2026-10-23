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

from typing import Literal

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
    output_digest: str = Field(
        description="SHA-256 of the canonical JSON of this response without its metadata "
        "(keys sorted, no whitespace). Equal digests mean bit-identical outputs; anyone can "
        "recompute it from the response."
    )
    simforge_version: str
    git_commit: str = Field(
        description="Commit of the code that ran ('-dirty' if the checkout had changes; "
        "'unknown' if it could not be determined)."
    )
    python_implementation: str
    python_version: str
    numpy_version: str
    scipy_version: str
    platform: str
    cpu: str = Field(description="Processor model; another CPU can change the last bits.")
    elapsed_ms: float = Field(description="Wall-clock compute time. Not reproducible by nature.")
    experiment_saved: bool


class ValidationCheck(StrictModel):
    """A diagnostic of this run. Proofs and grid evidence live in the tests and docs."""

    id: str
    label: str
    value: float
    threshold: float | None = Field(description="Pass if value <= threshold; None = info only.")
    passed: bool | None
    kind: Literal["exact_identity", "numerical_diagnostic", "informational"]
    note: str
