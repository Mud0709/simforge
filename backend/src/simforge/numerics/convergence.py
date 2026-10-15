"""Empirical order of convergence.

If the error behaves like e(h) = C h^p, then log e = log C + p log h, a straight line of
slope p on log-log axes. Two estimators are provided:

* :func:`local_orders` — p between consecutive step sizes, log(e1/e2) / log(h1/h2).
  These show *whether* the errors have reached the asymptotic regime: they should settle
  to a constant as h shrinks.
* :func:`fit_order` — least-squares slope through all points in a chosen fitting range.
  A single pair of points is never used to claim an order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

MIN_FIT_POINTS = 3


@dataclass(frozen=True, slots=True)
class OrderFit:
    order: float  # fitted slope p
    log10_constant: float  # intercept: log10 C
    r_squared: float
    n_points: int
    h_min: float
    h_max: float


def local_orders(h: Sequence[float], e: Sequence[float]) -> list[float | None]:
    """Orders between consecutive (h, e) pairs; None where undefined (zero error or equal h)."""
    out: list[float | None] = []
    for (h1, e1), (h2, e2) in zip(
        zip(h, e, strict=True), zip(h[1:], e[1:], strict=True), strict=False
    ):
        if e1 > 0 and e2 > 0 and h1 != h2:
            out.append(float(np.log(e1 / e2) / np.log(h1 / h2)))
        else:
            out.append(None)
    return out


def fit_order(h: Sequence[float], e: Sequence[float]) -> OrderFit | None:
    """Least-squares fit of log10 e = log10 C + p log10 h.

    Returns None if fewer than :data:`MIN_FIT_POINTS` distinct, positive points are given;
    choosing *which* points belong in the fit is the caller's responsibility.
    """
    pts = sorted({(float(hi), float(ei)) for hi, ei in zip(h, e, strict=True) if hi > 0 and ei > 0})
    if len({hi for hi, _ in pts}) < MIN_FIT_POINTS:
        return None
    x = np.log10([hi for hi, _ in pts])
    y = np.log10([ei for _, ei in pts])
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (slope * x + intercept)
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - float(np.sum(residual**2)) / ss_tot if ss_tot > 0 else 1.0
    return OrderFit(
        order=float(slope),
        log10_constant=float(intercept),
        r_squared=r_squared,
        n_points=len(pts),
        h_min=pts[0][0],
        h_max=pts[-1][0],
    )
