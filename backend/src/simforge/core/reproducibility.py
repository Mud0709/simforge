"""Helpers that make runs reproducible and auditable."""

from __future__ import annotations

import functools
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import scipy

from simforge import __version__


def canonical_json(data: Any) -> str:
    """Serialise ``data`` deterministically: sorted keys, no whitespace, finite floats only.

    ``allow_nan=False`` makes a non-finite value a hard error instead of silently
    producing invalid JSON.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)


def input_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def output_digest(response_without_metadata: Any) -> str:
    """SHA-256 of a run's outputs: the canonical JSON of the full response minus its run
    metadata. JSON writes each float in its shortest exact form, so two digests are equal
    only if every output value is bit-identical. Anyone can recompute it from a response."""
    return input_hash(response_without_metadata)


@functools.cache
def code_version() -> str:
    """Which code ran: ``SIMFORGE_GIT_COMMIT`` if the deployment sets it, else the commit of
    the checkout (with ``-dirty`` if files differ from it), else ``unknown``."""
    configured = os.environ.get("SIMFORGE_GIT_COMMIT", "").strip()
    if configured:
        return configured
    here = Path(__file__).resolve().parent

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=here, capture_output=True, text=True, timeout=5, check=True
        ).stdout.strip()

    try:
        commit = git("rev-parse", "HEAD")
        dirty = git("status", "--porcelain", "--untracked-files=no") != ""
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return f"{commit}-dirty" if dirty else commit


@functools.cache
def cpu_model() -> str:
    """The processor model. Different CPUs can round the last bits of the same calculation
    differently (libraries pick CPU-specific routines that add numbers in another order), so
    a replay must know whether the CPU changed."""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def environment_info() -> dict[str, str]:
    """Versions of everything that can change a numerical result, and the code that ran."""
    return {
        "simforge_version": __version__,
        "git_commit": code_version(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "platform": f"{sys.platform}-{platform.machine()}",
        "cpu": cpu_model(),
    }
