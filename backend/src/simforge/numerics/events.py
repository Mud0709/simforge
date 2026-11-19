"""Locating an event (a sign change of g) between two fixed-step nodes (plan 2.4, D11, R6).

With the crossing at fraction s of a step of size h, linear interpolation errs by
s(1 - s) h^2 g''/(2|g'|) + O(h^3) and cubic Hermite (values and slopes at both nodes) by
s^2(1 - s)^2 h^4 g''''/(24|g'|) + O(h^5) (derived in the plan; orders tested on e^t - 2).
Hermite is exact for polynomials of degree <= 3, up to rounding.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
from scipy.optimize import brentq

from simforge.numerics.fixed_step import FloatArray


def first_crossing(g: Sequence[float] | FloatArray) -> int | None:
    """Smallest i with g[i] > 0 and g[i + 1] <= 0 (first downward crossing), else None."""
    a = np.asarray(g, dtype=np.float64)
    hits = np.flatnonzero((a[:-1] > 0) & (a[1:] <= 0))
    return int(hits[0]) if hits.size else None


def locate_crossing(
    t0: float,
    t1: float,
    g0: float,
    g1: float,
    dg0: float,
    dg1: float,
    *,
    kind: Literal["linear", "hermite"],
) -> float:
    """Time of the root of the linear (secant) or cubic Hermite interpolant of g on [t0, t1].

    Needs t1 > t0 and a sign change g0 g1 <= 0. The Hermite root is found by ``brentq``
    with xtol = 1e-15 times the time scale max(|t0|, |t1|).
    """
    if kind not in ("linear", "hermite"):
        raise ValueError(f"unknown interpolant kind {kind!r}")
    if not t1 > t0:
        raise ValueError(f"need t1 > t0, got t0 = {t0}, t1 = {t1}")
    if g0 * g1 > 0:
        raise ValueError(f"no sign change: g0 = {g0}, g1 = {g1}")
    if g1 == 0:
        return t1
    if g0 == 0:
        return t0
    h = t1 - t0
    if kind == "linear":
        return t0 + h * g0 / (g0 - g1)

    def hermite(t: float) -> float:
        s = (t - t0) / h
        r = 1.0 - s
        return (
            (1 + 2 * s) * r * r * g0
            + s * r * r * h * dg0
            + s * s * (3 - 2 * s) * g1
            - s * s * r * h * dg1
        )

    return float(brentq(hermite, t0, t1, xtol=1e-15 * max(abs(t0), abs(t1))))
