"""Decide what each cell and each column *is*: missing, a number, a date, or other text.

Pure functions over strings. The rules are deliberately strict and explicit; a value that
could be read two ways is never silently forced into one of them.

Cells (always after trimming surrounding whitespace):
* **missing**: the empty string, or exactly one of the user's missing-value markers;
* **number**: plain decimal or scientific notation in ASCII digits (``-1.5``, ``2e3``,
  ``.5``) whose value is finite in double precision. Not numbers: ``1,000`` (thousands
  separator or decimal comma?), ``inf``, ``nan``, ``1e999`` (overflows);
* **number with leading zero** (``007``): reads as a number, but the zero suggests an
  identifier (postcode, ID), so it only counts as numeric if the user says so;
* **date**: ISO 8601 ``YYYY-MM-DD``, optionally with a time ``THH:MM[:SS[.ffffff]]`` (a space
  may replace the ``T``), that exists on the calendar. ``01/02/2024`` is *not* a date here,
  because day-first and month-first readings disagree; it is flagged as ambiguous;
* **text**: everything else.

Columns: ``empty`` if every cell is missing; ``numeric`` if every non-missing cell is a
number; ``date`` if every one is a date; otherwise ``categorical``, with counts of how mixed
it is. A user override changes the column's type; values that do not fit it are counted as
*invalid*, separately from missing, and excluded from that column's statistics.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

from simforge.quant.profiling.limits import MAX_EXAMPLES

ColumnType = Literal["numeric", "date", "categorical"]
InferredType = Literal["numeric", "date", "categorical", "empty"]

_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_LEADING_ZERO = re.compile(r"[+-]?0[0-9]")
_ISO_DATE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?)?"
)
_AMBIGUOUS_DATE = re.compile(r"[0-9]{1,2}[/.-][0-9]{1,2}[/.-][0-9]{2,4}")


class Kind(Enum):
    MISSING = "missing"
    NUMBER = "number"
    LEADING_ZERO_NUMBER = "leading_zero_number"
    NON_FINITE_NUMBER = "non_finite_number"
    DATE = "date"
    AMBIGUOUS_DATE = "ambiguous_date"
    TEXT = "text"


def classify(cell: str, missing_markers: frozenset[str]) -> Kind:
    value = cell.strip()
    if value == "" or value in missing_markers:
        return Kind.MISSING
    if _NUMBER.fullmatch(value):
        if not math.isfinite(float(value)):
            return Kind.NON_FINITE_NUMBER
        return Kind.LEADING_ZERO_NUMBER if _LEADING_ZERO.match(value) else Kind.NUMBER
    if _ISO_DATE.fullmatch(value):
        return Kind.DATE if parse_date(value) is not None else Kind.TEXT
    if _AMBIGUOUS_DATE.fullmatch(value):
        return Kind.AMBIGUOUS_DATE
    return Kind.TEXT


def parse_date(value: str) -> datetime | None:
    """The calendar check: ``2023-02-30`` matches the pattern but is not a date."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# Which cell kinds are valid values for each column type.
_VALID: dict[InferredType, frozenset[Kind]] = {
    "empty": frozenset(),
    "numeric": frozenset({Kind.NUMBER, Kind.LEADING_ZERO_NUMBER}),
    "date": frozenset({Kind.DATE}),
    "categorical": frozenset(k for k in Kind if k is not Kind.MISSING),
}


@dataclass(frozen=True, slots=True)
class Example:
    row: int  # 1-based data row (the header is not counted)
    value: str


@dataclass(frozen=True, slots=True)
class ColumnTyping:
    inferred: InferredType
    reason: str
    type: InferredType  # after any override; "empty" only if nothing was overridden
    overridden: bool
    kinds: Counter[Kind]
    missing: int
    invalid: int
    valid_rows: list[int]  # 0-based indices of rows holding a valid value
    invalid_examples: list[Example]
    notes: list[str]


def infer(kinds: Counter[Kind]) -> tuple[InferredType, str]:
    present = sum(n for k, n in kinds.items() if k is not Kind.MISSING)
    if present == 0:
        return "empty", "Every cell is missing."
    numbers = kinds[Kind.NUMBER]
    if numbers == present:
        return "numeric", "Every non-missing value is a number."
    if kinds[Kind.DATE] == present:
        return "date", "Every non-missing value is an ISO 8601 date."
    numeric_like = numbers + kinds[Kind.LEADING_ZERO_NUMBER]
    if numeric_like == present:
        return "categorical", (
            "All values are numbers, but some have leading zeros (like 007), which suggests "
            "identifiers. Kept as categories so the zeros are not lost; override to numeric "
            "if they really are quantities."
        )
    if kinds[Kind.AMBIGUOUS_DATE] == present:
        return "categorical", (
            "Values look like dates written as dd/mm/yyyy or mm/dd/yyyy. The day and month "
            "order cannot be known from the file, so they are kept as categories."
        )
    if numeric_like or kinds[Kind.DATE]:
        return "categorical", (
            f"Mixed: {numeric_like} numeric-looking and {kinds[Kind.DATE]} date-looking values "
            f"among {present} non-missing values; the rest are text. Nothing was converted."
        )
    return "categorical", "Values are text."


def type_column(
    cells: list[str], missing_markers: frozenset[str], override: ColumnType | None
) -> ColumnTyping:
    cell_kinds = [classify(c, missing_markers) for c in cells]
    kinds = Counter(cell_kinds)
    inferred, reason = infer(kinds)
    effective: InferredType = override if override is not None else inferred
    valid_kinds = _VALID[effective]
    valid_rows: list[int] = []
    invalid_examples: list[Example] = []
    invalid = 0
    for i, kind in enumerate(cell_kinds):
        if kind is Kind.MISSING:
            continue
        if kind in valid_kinds:
            valid_rows.append(i)
        else:
            invalid += 1
            if len(invalid_examples) < MAX_EXAMPLES:
                invalid_examples.append(Example(row=i + 1, value=cells[i].strip()))

    notes: list[str] = []
    if kinds[Kind.NON_FINITE_NUMBER]:
        notes.append(
            f"{kinds[Kind.NON_FINITE_NUMBER]} value(s) are too large for double precision "
            "(beyond about 1.8e308) and are not treated as numbers."
        )
    ambiguous = kinds[Kind.AMBIGUOUS_DATE]
    if ambiguous and ambiguous != len(cells) - kinds[Kind.MISSING]:
        notes.append(
            f"{ambiguous} value(s) look like dates in an ambiguous day/month order "
            "(like 01/02/2024) and are treated as text."
        )
    if override is not None and invalid:
        notes.append(
            f"{invalid} non-missing value(s) do not fit the chosen type {override!r}. They are "
            "counted as invalid and left out of the statistics, not converted or deleted."
        )
    return ColumnTyping(
        inferred=inferred,
        reason=reason,
        type=effective,
        overridden=override is not None,
        kinds=kinds,
        missing=kinds[Kind.MISSING],
        invalid=invalid,
        valid_rows=valid_rows,
        invalid_examples=invalid_examples,
        notes=notes,
    )
