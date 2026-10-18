"""Descriptive statistics for one column, and duplicate rows for the whole table.

Pure functions. Every statistic describes the values in the file; none is an estimate of
anything beyond it (no inference, no prediction).

Definitions (n = number of valid values, x_(0) <= ... <= x_(n-1) the sorted values):
* mean = (1/n) sum x_i;
* sample standard deviation s = sqrt( sum (x_i - mean)^2 / (n - 1) ), defined for n >= 2;
* quantile p: h = (n - 1) p, j = floor(h), Q(p) = x_(j) + (h - j)(x_(j+1) - x_(j)). This is
  Hyndman and Fan's type 7, the default of NumPy, R and spreadsheet QUARTILE.INC. Other
  conventions exist (the "median of each half" rule taught in many schools gives different
  quartiles for small n);
* histogram: k = min(50, ceil(log2 n) + 1) equal-width bins from min to max (Sturges' rule);
  every bin is [left, right) except the last, which includes max.

Overflow: values can be as large as about 1.8e308. Sums and squares are therefore computed
on y = x / 2^e, with 2^e >= max |x_i|, and scaled back. Dividing by a power of two is exact
in binary floating point, so the scaling itself adds no rounding (unless a value is over
1e300 times smaller than the largest one and falls into the subnormal range). If the true
result of a statistic is itself outside double precision (the standard deviation of
[-1.7e308, 1.7e308] is about 2.4e308), it is reported as not representable, never as
infinity.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import numpy.typing as npt

from simforge.quant.profiling.limits import MAX_HISTOGRAM_BINS, TOP_CATEGORIES

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class NumericStats:
    count: int
    mean: float
    std: float | None
    min: float
    q1: float
    median: float
    q3: float
    max: float
    bin_edges: list[float]
    bin_counts: list[int]
    notes: list[str]


@dataclass(frozen=True, slots=True)
class DateStats:
    count: int
    unique: int
    min: str
    max: str
    span_days: float


@dataclass(frozen=True, slots=True)
class CategoryCount:
    value: str
    count: int


@dataclass(frozen=True, slots=True)
class CategoricalStats:
    count: int
    unique: int
    top: list[CategoryCount]
    other_count: int


@dataclass(frozen=True, slots=True)
class Duplicates:
    duplicate_rows: int  # rows identical to an earlier row
    distinct_rows: int
    groups: int  # distinct rows that occur more than once
    examples: list[list[int]]  # 1-based row numbers of the first few groups


def quantile(sorted_x: FloatArray, p: float) -> float:
    """Type 7 quantile of already sorted, finite values; never overflows.

    Interpolates as (1 - g) a + g b, a weighted average of two neighbours, so the result lies
    between them. Clamping to [a, b] removes any rounding step outside that interval.
    """
    n = len(sorted_x)
    h = (n - 1) * p
    j = math.floor(h)
    g = h - j
    a = float(sorted_x[j])
    if g == 0.0:
        return a
    b = float(sorted_x[j + 1])
    q = (1.0 - g) * a + g * b
    return min(max(q, a), b)


def sturges_bins(n: int) -> int:
    return min(MAX_HISTOGRAM_BINS, math.ceil(math.log2(n)) + 1)


def _unscale(value: float, e: int) -> float | None:
    """value * 2^e, or None if that is beyond double precision."""
    try:
        return math.ldexp(value, e)
    except OverflowError:
        return None


def numeric_stats(values: list[float]) -> NumericStats:
    x: FloatArray = np.sort(np.asarray(values, dtype=np.float64))
    n = len(x)
    if n == 0:
        raise ValueError("numeric_stats needs at least one value")
    if not np.all(np.isfinite(x)):
        raise ValueError("values must be finite")
    notes: list[str] = []
    lo, hi = float(x[0]), float(x[-1])
    # Scale by a power of two, 2^e >= max |x|: multiplying by 2^-e only changes the binary
    # exponent, so it is exact (it cannot round), and every |y| <= 1 keeps the sums finite.
    _, e = math.frexp(float(np.max(np.abs(x))))
    y = np.ldexp(x, -e)
    std: float | None = None
    mean_y = float(np.mean(y))
    # The exact mean lies in [min, max]; clamping only removes a rounding step outside it.
    unscaled = _unscale(mean_y, e)
    mean = hi if unscaled is None else min(max(unscaled, lo), hi)
    if n >= 2:
        std = _unscale(math.sqrt(float(np.sum((y - mean_y) ** 2)) / (n - 1)), e)
        if std is None:
            notes.append(
                "The standard deviation exceeds the largest double-precision number "
                "(about 1.8e308), so it is not representable and is not reported."
            )
    if n < 2:
        notes.append("The standard deviation needs at least two values.")

    if lo == hi:
        edges, counts = [lo, hi], [n]
    else:
        k = sturges_bins(n)
        # Bin in scaled units so that hi - lo cannot overflow.
        counts_arr, edges_y = np.histogram(y, bins=k, range=(float(y[0]), float(y[-1])))
        edges = [math.ldexp(float(b), e) for b in edges_y]
        edges[0], edges[-1] = lo, hi
        counts = [int(c) for c in counts_arr]
    return NumericStats(
        count=n,
        mean=mean,
        std=std,
        min=lo,
        q1=quantile(x, 0.25),
        median=quantile(x, 0.5),
        q3=quantile(x, 0.75),
        max=hi,
        bin_edges=edges,
        bin_counts=counts,
        notes=notes,
    )


def date_stats(values: list[datetime]) -> DateStats:
    if not values:
        raise ValueError("date_stats needs at least one value")
    lo, hi = min(values), max(values)
    return DateStats(
        count=len(values),
        unique=len(set(values)),
        min=lo.isoformat(),
        max=hi.isoformat(),
        span_days=(hi - lo).total_seconds() / 86_400,
    )


def categorical_stats(values: list[str]) -> CategoricalStats:
    counts = Counter(values)
    # Most frequent first; ties in alphabetical order, so the output never depends on the
    # order rows happen to appear in.
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    top = [CategoryCount(value=v, count=c) for v, c in ranked[:TOP_CATEGORIES]]
    return CategoricalStats(
        count=len(values),
        unique=len(counts),
        top=top,
        other_count=len(values) - sum(t.count for t in top),
    )


def duplicate_rows(rows: list[tuple[str, ...]], max_examples: int) -> Duplicates:
    """Rows whose cells are identical, character for character, to an earlier row."""
    positions: dict[tuple[str, ...], list[int]] = {}
    for i, row in enumerate(rows):
        positions.setdefault(row, []).append(i + 1)
    repeated = [rows_ for rows_ in positions.values() if len(rows_) > 1]
    return Duplicates(
        duplicate_rows=len(rows) - len(positions),
        distinct_rows=len(positions),
        groups=len(repeated),
        examples=[r[:max_examples] for r in repeated[:max_examples]],
    )
