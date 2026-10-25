"""Descriptive statistics against independent references.

References: Python's ``statistics`` module (exact rational arithmetic for the mean and
standard deviation; ``quantiles(method="inclusive")`` is Hyndman-Fan type 7), and values
worked out by hand.
"""

from __future__ import annotations

import math
import random
import statistics
import sys
from datetime import datetime

import numpy as np
import pytest

from simforge.quant.profiling.statistics import (
    categorical_stats,
    date_stats,
    duplicate_rows,
    numeric_stats,
    quantile,
    sturges_bins,
)
from tests.approx import rel_approx

MAX = sys.float_info.max


def test_hand_worked_example() -> None:
    # 2, 4, 4, 4, 5, 5, 7, 9: mean 5, sum of squared deviations 32, s = sqrt(32/7).
    s = numeric_stats([9, 2, 4, 4, 5, 4, 5, 7])
    assert s.count == 8
    assert s.mean == 5.0
    assert s.std == rel_approx(math.sqrt(32 / 7), rel=1e-15)
    # Type 7: Q1 at h = 7 * 0.25 = 1.75 -> 4 + 0.75 (4 - 4) = 4; Q3 at h = 5.25 -> 5 + 0.25 * 2.
    assert (s.min, s.q1, s.median, s.q3, s.max) == (2.0, 4.0, 4.5, 5.5, 9.0)


def test_quartile_convention_differs_from_median_of_halves() -> None:
    # 1..7. Type 7 interpolates: Q1 = 2.5, Q3 = 5.5. The "median of each half" rule (lower
    # half 1,2,3; upper half 5,6,7) gives 2 and 6. Same data, different convention.
    s = numeric_stats([1, 2, 3, 4, 5, 6, 7])
    assert (s.q1, s.median, s.q3) == (2.5, 4.0, 5.5)


@pytest.mark.parametrize("seed", range(20))
def test_against_the_statistics_module(seed: int) -> None:
    rng = random.Random(seed)
    n = rng.randint(2, 400)
    values = [rng.uniform(-1e6, 1e6) * 10 ** rng.randint(-3, 3) for _ in range(n)]
    s = numeric_stats(values)
    assert s.mean == pytest.approx(statistics.fmean(values), rel=1e-12, abs=1e-6)
    assert s.std == rel_approx(statistics.stdev(values), rel=1e-12)
    q1, q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
    assert s.q1 == pytest.approx(q1, rel=1e-14, abs=1e-9)
    assert s.median == pytest.approx(q2, rel=1e-14, abs=1e-9)
    assert s.q3 == pytest.approx(q3, rel=1e-14, abs=1e-9)
    assert (s.min, s.max) == (min(values), max(values))


@pytest.mark.parametrize("p", [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 10, 11])
def test_quantile_matches_numpy_linear(p: float, n: int) -> None:
    x = np.sort(np.random.default_rng(n).normal(size=n))
    assert quantile(x, p) == pytest.approx(float(np.quantile(x, p, method="linear")), abs=1e-15)


def test_single_value() -> None:
    s = numeric_stats([3.5])
    assert (s.count, s.mean, s.std, s.min, s.median, s.max) == (1, 3.5, None, 3.5, 3.5, 3.5)
    assert s.bin_edges == [3.5, 3.5]
    assert s.bin_counts == [1]
    assert any("at least two values" in n for n in s.notes)


@pytest.mark.parametrize("value", [0.1, 1 / 3, -2.7e-5, 123456.789])
def test_constant_column_has_exactly_zero_spread(value: float) -> None:
    # Every value is the same, so the spread is 0 by definition. Values like 0.1 are not
    # exact binary fractions; summing them must not leave a rounding residue in the SD.
    s = numeric_stats([value] * 7)
    assert (s.mean, s.std, s.min, s.max) == (value, 0.0, value, value)


def test_constant_and_zero_columns() -> None:
    assert numeric_stats([0.0, 0.0, -0.0]).std == 0.0
    c = numeric_stats([7.0] * 5)
    assert (c.mean, c.std, c.bin_counts) == (7.0, 0.0, [5])


def test_huge_values_do_not_overflow() -> None:
    # Unscaled, 1e308 + 1e308 = inf and (1e308)^2 = inf.
    s = numeric_stats([1e308, 1e308, 1e308])
    assert (s.mean, s.std) == (1e308, 0.0)
    m = numeric_stats([MAX, MAX])
    assert m.mean == MAX
    t = numeric_stats([1e308, 5e307])
    assert t.mean == 7.5e307
    assert t.std == rel_approx(math.sqrt(2) * 2.5e307, rel=1e-15)
    assert sum(t.bin_counts) == 2


def test_unrepresentable_std_is_reported_not_infinite() -> None:
    # True s = sqrt(2) * 1.7e308 ~ 2.4e308 > MAX: not representable.
    s = numeric_stats([-1.7e308, 1.7e308])
    assert s.mean == 0.0
    assert s.std is None
    assert any("not representable" in n for n in s.notes)
    assert s.median == 0.0
    assert s.q1 == rel_approx(-0.85e308, rel=1e-15)
    assert s.q3 == rel_approx(0.85e308, rel=1e-15)
    assert all(math.isfinite(e) for e in s.bin_edges)


def test_quantile_between_extremes_stays_finite() -> None:
    # Naive a + g (b - a) computes b - a = 2 MAX = inf.
    assert quantile(np.array([-MAX, MAX]), 0.5) == 0.0
    assert quantile(np.array([-MAX, MAX]), 0.25) == rel_approx(-MAX / 2, rel=1e-15)
    assert quantile(np.array([MAX, MAX]), 0.3) == MAX  # clamped: never rounds up to inf


def test_tiny_values_keep_their_precision() -> None:
    values = [3e-310, 1e-310, 2e-310]  # subnormal numbers
    s = numeric_stats(values)
    assert s.mean == rel_approx(2e-310, rel=1e-6)
    assert s.median == 2e-310


def test_scaling_by_a_power_of_two_is_exact() -> None:
    # Scaling by 52000 would make this 37124.99999999999; scaling by 2^16 does not round.
    values = [28000.0, 31500.0, 45250.0, 39000.0, 27000.0, 52000.0]
    assert numeric_stats(values).mean == 37125.0
    assert numeric_stats(values).mean == float(np.mean(values))


def test_non_finite_and_empty_inputs_are_refused() -> None:
    with pytest.raises(ValueError, match="finite"):
        numeric_stats([1.0, math.inf])
    with pytest.raises(ValueError, match="at least one"):
        numeric_stats([])


def test_histogram_bins_and_edges() -> None:
    assert [sturges_bins(n) for n in (2, 3, 4, 5, 12, 1000, 50_000)] == [2, 3, 3, 4, 5, 11, 17]
    s = numeric_stats([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10])
    assert len(s.bin_counts) == 5
    assert s.bin_edges == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    # [0,2) [2,4) [4,6) [6,8) [8,10]: interior edges go to the right; max is in the last bin.
    assert s.bin_counts == [2, 2, 2, 2, 4]
    assert sum(s.bin_counts) == s.count


def test_dates_are_shown_as_written_and_distinct_means_distinct_moments() -> None:
    values = ["2024-01-01", "2024-01-01 00:00", "2023-12-31T18:00"]
    d = date_stats([(v, datetime.fromisoformat(v)) for v in values])
    assert (d.min, d.max) == ("2023-12-31T18:00", "2024-01-01")  # text from the file
    assert d.unique == 2  # the first two are the same moment
    assert d.span_days == 0.25


def test_date_stats() -> None:
    raw = ["2026-09-03", "2026-09-01", "2026-09-01 12:00"]
    d = date_stats([(v, datetime.fromisoformat(v)) for v in raw])
    assert (d.count, d.unique, d.min, d.max) == (
        3,
        3,
        "2026-09-01",
        "2026-09-03",
    )
    assert d.span_days == 2.0


def test_categorical_stats_rank_by_count_then_value() -> None:
    values = ["b", "a", "c", "b", "a", "d"] + [f"x{i:02d}" for i in range(12)]
    c = categorical_stats(values)
    assert (c.count, c.unique) == (18, 16)
    assert [(t.value, t.count) for t in c.top[:4]] == [("a", 2), ("b", 2), ("c", 1), ("d", 1)]
    assert len(c.top) == 10
    assert c.other_count == 18 - sum(t.count for t in c.top) == 6


def test_duplicates_are_exact_and_counted_not_removed() -> None:
    rows: list[tuple[str, ...]] = [
        ("1", "a"),
        ("2", "b"),
        ("1", "a"),
        ("1", "a "),
        ("2", "b"),
        ("1", "a"),
    ]
    d = duplicate_rows(rows, max_examples=5)
    assert d.duplicate_rows == 3  # rows 3, 5, 6
    assert d.distinct_rows == 3  # ("1","a"), ("2","b"), ("1","a ")
    assert d.groups == 2
    assert d.examples == [[1, 3, 6], [2, 5]]
    assert d.duplicate_rows + d.distinct_rows == len(rows)
    assert len(rows) == 6  # the input is untouched
