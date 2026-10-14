"""Helpers that make runs reproducible and auditable."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
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


def environment_info() -> dict[str, str]:
    """Versions of everything that can change a numerical result."""
    return {
        "simforge_version": __version__,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "platform": f"{sys.platform}-{platform.machine()}",
    }
