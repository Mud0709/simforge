"""Numbers as people read them, for one-line headlines. Trailing zeros are dropped: they
would imply precision the number does not have."""

from __future__ import annotations

import math


def sig(x: float, digits: int = 6) -> str:
    """``digits`` significant figures; scientific notation outside [1e-3, 1e6)."""
    if not math.isfinite(x):
        return "—"
    if x == 0:
        return "0"
    if not 1e-3 <= abs(x) < 1e6:
        return exp(x, digits)
    text = repr(float(f"{x:.{digits}g}"))
    return text.removesuffix(".0")


def exp(x: float, digits: int = 2) -> str:
    """Scientific notation with ``digits`` significant figures, e.g. 2.2e-12."""
    if not math.isfinite(x):
        return "—"
    if x == 0:
        return "0"
    mantissa, exponent = f"{x:.{digits - 1}e}".split("e")
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}e{int(exponent)}"
