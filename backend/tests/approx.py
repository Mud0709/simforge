"""Shared comparison helpers for tests."""

from __future__ import annotations

import pytest


def rel_approx(expected: object, rel: float) -> object:
    """pytest.approx with a purely relative tolerance.

    pytest.approx(x, rel=r) actually allows max(r |x|, 1e-12): its default absolute
    tolerance of 1e-12 dominates whenever |x| < 1e-12 / r, so a tight relative check
    (e.g. rel=1e-15 on a value of order 1) would silently be a ~1e-12 check. abs=0
    removes that floor, so the stated relative tolerance is the one enforced.
    """
    return pytest.approx(expected, rel=rel, abs=0)
