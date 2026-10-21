"""Cell and column typing: strict rules, ambiguity flagged, overrides never alter data."""

from __future__ import annotations

from collections import Counter

import pytest

from simforge.quant.profiling.inference import Kind, classify, infer, type_column

MARKERS = frozenset({"NA", "N/A", "NaN", "None", "null"})


@pytest.mark.parametrize(
    ("cell", "kind"),
    [
        ("", Kind.MISSING),
        ("   ", Kind.MISSING),
        ("NA", Kind.MISSING),
        (" null ", Kind.MISSING),
        ("na", Kind.TEXT),  # markers are case-sensitive
        ("n/a", Kind.TEXT),
        ("1", Kind.NUMBER),
        ("0", Kind.NUMBER),
        ("-1.5", Kind.NUMBER),
        ("+.5", Kind.NUMBER),
        ("0.25", Kind.NUMBER),
        ("1.", Kind.NUMBER),
        ("2e3", Kind.NUMBER),
        ("6.02E+23", Kind.NUMBER),
        (" 7 ", Kind.NUMBER),
        ("1e-400", Kind.NUMBER),  # underflows to 0.0: finite, so a number
        ("007", Kind.LEADING_ZERO_NUMBER),
        ("-01.5", Kind.LEADING_ZERO_NUMBER),
        ("1e400", Kind.NON_FINITE_NUMBER),
        ("1,000", Kind.TEXT),  # thousands separator or decimal comma: ambiguous
        ("1 000", Kind.TEXT),
        ("1_000", Kind.TEXT),  # Python's float() would accept this
        ("inf", Kind.TEXT),
        ("Infinity", Kind.TEXT),
        ("nan", Kind.TEXT),
        ("0x1A", Kind.TEXT),
        ("١٢", Kind.TEXT),  # Arabic-Indic digits: \d would match them, [0-9] does not
        ("£12", Kind.TEXT),
        ("12%", Kind.TEXT),
        ("2024-02-29", Kind.DATE),  # leap day
        ("2023-02-29", Kind.TEXT),  # not on the calendar
        ("2024-13-01", Kind.TEXT),
        ("2024-01-31T10:30", Kind.DATE),
        ("2024-01-31 10:30:15.25", Kind.DATE),
        ("2024-01-31T10:30Z", Kind.TEXT),  # time zones are not interpreted in this version
        ("01/02/2024", Kind.AMBIGUOUS_DATE),
        ("1.2.24", Kind.AMBIGUOUS_DATE),
        ("31-12-2024", Kind.AMBIGUOUS_DATE),
        ("UK", Kind.TEXT),
    ],
)
def test_classify(cell: str, kind: Kind) -> None:
    assert classify(cell, MARKERS) is kind


def test_nan_is_missing_only_when_it_is_a_marker() -> None:
    assert classify("NaN", MARKERS) is Kind.MISSING
    assert classify("NaN", frozenset()) is Kind.TEXT  # never parsed as a float NaN


@pytest.mark.parametrize(
    ("cells", "inferred", "reason"),
    [
        (["", "NA"], "empty", "Every cell is missing"),
        (["1", "2.5", "", "-3"], "numeric", "Every non-missing value is a number"),
        (["2024-01-01", "2024-01-02 09:00"], "date", "ISO 8601"),
        (["007", "012", "3"], "categorical", "leading zeros"),
        (["01/02/2024", "03/04/2024"], "categorical", "cannot be known"),
        (["1", "2", "three"], "categorical", "2 numeric-looking, 0 date-looking and 1 other"),
        (["1", "2024-01-01", "x"], "categorical", "1 numeric-looking, 1 date-looking and 1 "),
        (["1", "2024-01-01"], "categorical", "1 date-looking and 0 other values"),
        (["1", "1e999"], "categorical", "Mixed"),
        (["red", "blue"], "categorical", "Values are text"),
    ],
)
def test_column_inference(cells: list[str], inferred: str, reason: str) -> None:
    t = type_column(cells, MARKERS, None)
    assert t.inferred == inferred
    assert t.type == inferred
    assert reason in t.reason
    assert t.invalid == 0  # without an override nothing is ever invalid
    assert t.missing + len(t.valid_rows) == len(cells)


def test_infer_counts_only_non_missing_cells() -> None:
    assert infer(Counter({Kind.MISSING: 5, Kind.NUMBER: 1}))[0] == "numeric"


def test_numeric_override_on_mixed_column_counts_invalid_values() -> None:
    cells = ["10", "NA", "1,200", "20", "unknown", "", "1e999", "007"]
    t = type_column(cells, MARKERS, "numeric")
    assert t.inferred == "categorical"
    assert t.type == "numeric"
    assert t.overridden
    assert t.missing == 2
    assert t.invalid == 3  # "1,200", "unknown", "1e999"
    assert [e.row for e in t.invalid_examples] == [3, 5, 7]
    assert [e.value for e in t.invalid_examples] == ["1,200", "unknown", "1e999"]
    assert [cells[i] for i in t.valid_rows] == ["10", "20", "007"]  # leading zero accepted
    assert t.missing + t.invalid + len(t.valid_rows) == len(cells)
    assert any("1.8e308" in n for n in t.notes)
    assert any("3 non-missing value(s) do not fit" in n for n in t.notes)


def test_date_override_on_numeric_column_makes_everything_invalid() -> None:
    t = type_column(["1", "2", ""], MARKERS, "date")
    assert t.valid_rows == []
    assert t.invalid == 2
    assert t.missing == 1


def test_categorical_override_accepts_every_present_value() -> None:
    t = type_column(["1", "2", "NA"], MARKERS, "categorical")
    assert t.inferred == "numeric"
    assert t.valid_rows == [0, 1]
    assert t.invalid == 0


def test_some_ambiguous_dates_among_text_are_noted() -> None:
    t = type_column(["01/02/2024", "soon"], MARKERS, None)
    assert t.inferred == "categorical"
    assert any("ambiguous day/month order" in n for n in t.notes)
