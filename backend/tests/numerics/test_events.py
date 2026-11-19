"""Event location between fixed-step nodes (roadmap 2.4, slice 1, plan D11 and R6).

API the builder must implement, in ``simforge.numerics.events`` (plan D7):

* ``first_crossing(g: Sequence[float] | FloatArray) -> int | None``: ``g`` holds the event
  function's values at consecutive nodes (for the projectile, the height component).
  Returns the smallest ``i`` with ``g[i] > 0`` and ``g[i + 1] <= 0`` (the first downward
  crossing, so a launch from g = 0 does not count), or ``None`` if there is none.
* ``locate_crossing(t0: float, t1: float, g0: float, g1: float, dg0: float, dg1: float,
  *, kind: Literal["linear", "hermite"]) -> float``: the time of the root of the
  interpolant of g on [t0, t1], given values ``g0, g1`` and slopes ``dg0, dg1`` at the two
  nodes. ``"linear"`` uses the secant through (t0, g0), (t1, g1) and ignores the slopes;
  ``"hermite"`` uses the cubic Hermite interpolant and finds its root with
  ``scipy.optimize.brentq`` on [t0, t1] (``xtol`` <= 1e-15 * the time scale, D11).
  Requires a sign change (g0 * g1 <= 0, either direction) and ``t1 > t0``; returns ``t1``
  if ``g1 == 0`` and ``t0`` if ``g0 == 0``; raises ``ValueError`` whose message contains
  "sign change" without one, "t1" when ``t1 <= t0``, and the given name for an unknown
  ``kind``.

References (independent): the exact root ln 2 of e^t - 2, R6's leading error terms
h^2 g''/(8|g'|) and h^4 g''''/(384|g'|) at s = 1/2, a cubic with a known root, and the vacuum
landing time of a parabola evaluated in 50-digit ``decimal``.
"""

from __future__ import annotations

import math
from decimal import Decimal, localcontext

import numpy as np
import pytest
from simforge.numerics.events import first_crossing, locate_crossing

from simforge.numerics.convergence import fit_order
from tests.approx import rel_approx

EPS = float(np.finfo(np.float64).eps)
LN2 = math.log(2.0)  # root of e^t - 2, correctly rounded by the C library to < 1 ulp
HS = [0.2 / 2**i for i in range(6)]  # 0.2 ... 0.00625


@pytest.mark.parametrize(
    ("g", "expected"),
    [
        ([1.0, 0.5, -0.1, 0.2, -1.0], 1),
        ([0.0, 1.0, 2.0, -1.0], 2),  # starts on the ground: not a downward crossing
        ([3.0, 2.0, 0.0, -1.0], 1),  # landing exactly on a node
        ([-1.0, 1.0, -1.0], 1),  # an upward crossing first is skipped
        ([1.0, 2.0, 3.0], None),
        ([-1.0, -2.0], None),
        ([0.0, -1.0], None),
        ([5.0], None),
    ],
)
def test_first_crossing_finds_the_first_downward_sign_change(
    g: list[float], expected: int | None
) -> None:
    assert first_crossing(g) == expected
    assert first_crossing(np.array(g)) == expected


def _errors_on_exp(kind: str) -> list[float]:
    """|located - ln 2| for g = e^t - 2 bracketed with the root at the midpoint (s = 1/2)."""
    out = []
    for h in HS:
        t0, t1 = LN2 - h / 2, LN2 + h / 2
        root = locate_crossing(
            t0, t1, math.exp(t0) - 2, math.exp(t1) - 2, math.exp(t0), math.exp(t1), kind=kind
        )
        assert t0 <= root <= t1
        out.append(abs(root - LN2))
    return out


@pytest.mark.parametrize(("kind", "order"), [("linear", 2), ("hermite", 4)])
def test_crossing_error_order_on_exponential(kind: str, order: int) -> None:
    """R6: linear errs as O(h^2), Hermite as O(h^4). Six halvings of h; measured with an
    independent scratch implementation the fitted slopes are 1.9998 and 4.0002 (the O(h^3)
    and O(h^5) terms pull the coarsest points), so +-0.02 is ~100x that deviation."""
    fit = fit_order(HS, _errors_on_exp(kind))
    assert fit is not None
    assert fit.n_points == len(HS)
    assert fit.order == pytest.approx(order, abs=0.02)


@pytest.mark.parametrize("kind", ["linear", "hermite"])
def test_crossing_error_matches_r6_leading_term_at_finest_h(kind: str) -> None:
    """At s = 1/2, g'' = g'''' = g' = e^{ln 2} = 2 at the root: the leading terms are
    h^2/8 (linear) and h^4/384 (Hermite). The next correction is relatively O(h^2) ~ 1e-5
    at h = 0.00625, and the Hermite error there (~4e-12) is ~2e4 ulps of ln 2, so rounding
    is ~1e-5 relative too; 1% leaves margin for both."""
    h = HS[-1]
    leading = h**2 / 8 if kind == "linear" else h**4 / 384
    assert _errors_on_exp(kind)[-1] == rel_approx(leading, rel=0.01)


def test_hermite_is_exact_on_a_cubic() -> None:
    """g = (r - t)(1 + t^2) is a cubic, so its Hermite interpolant is g itself and the only
    error is rounding plus brentq's stopping rule (rtol 4 eps): <= 8 eps relative. Brackets
    put the root at several fractions s, including far from the middle."""
    r = 0.7

    def g(t: float) -> float:
        return (r - t) * (1 + t * t)

    def dg(t: float) -> float:
        return -(1 + t * t) + (r - t) * 2 * t

    for t0, t1 in [(0.5, 1.0), (0.6, 0.75), (0.1, 2.0), (0.69, 0.71), (0.0, 0.72)]:
        root = locate_crossing(t0, t1, g(t0), g(t1), dg(t0), dg(t1), kind="hermite")
        assert root == rel_approx(r, rel=8 * EPS)


def test_hermite_on_vacuum_parabola_nodes_gives_the_exact_landing_time() -> None:
    """y(t) = h0 + vy t - g t^2/2 is a polynomial of degree 2, so Hermite on exact nodes is
    exact up to rounding (8 eps relative, as for the cubic); the landing time
    (vy + sqrt(vy^2 + 2 g h0))/g is evaluated in 50-digit decimal."""
    h0, vy, grav = 1.5, 12.0, 9.81
    with localcontext() as ctx:
        ctx.prec = 50
        d_vy, d_g = Decimal(vy), Decimal(grav)
        landing = float((d_vy + (d_vy**2 + 2 * d_g * Decimal(h0)).sqrt()) / d_g)
    for h in [0.3, 0.1, 0.07, 0.013]:
        t = h * np.arange(math.ceil(landing / h) + 3)
        y = h0 + vy * t - 0.5 * grav * t**2
        v = vy - grav * t
        i = first_crossing(y)
        assert i is not None
        assert t[i] < landing <= t[i + 1]
        root = locate_crossing(t[i], t[i + 1], y[i], y[i + 1], v[i], v[i + 1], kind="hermite")
        assert root == rel_approx(landing, rel=8 * EPS)


def test_linear_interpolation_is_the_secant_root() -> None:
    # Dyadic inputs: the secant root 1 + 2 * 3/(3 + 1) = 2.5 is exact in binary.
    assert locate_crossing(1.0, 3.0, 3.0, -1.0, 123.0, -456.0, kind="linear") == 2.5


@pytest.mark.parametrize("kind", ["linear", "hermite"])
def test_endpoint_roots_and_invalid_brackets(kind: str) -> None:
    assert locate_crossing(1.0, 2.0, 1.0, 0.0, -1.0, -1.0, kind=kind) == 2.0
    assert locate_crossing(1.0, 2.0, 0.0, -1.0, -1.0, -1.0, kind=kind) == 1.0
    with pytest.raises(ValueError, match="sign change"):
        locate_crossing(1.0, 2.0, 1.0, 0.5, -0.5, -0.5, kind=kind)  # no sign change
    with pytest.raises(ValueError, match="t1"):
        locate_crossing(2.0, 1.0, 1.0, -1.0, -2.0, -2.0, kind=kind)  # t1 <= t0


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="quadratic"):
        locate_crossing(0.0, 1.0, 1.0, -1.0, -2.0, -2.0, kind="quadratic")  # type: ignore[arg-type]
