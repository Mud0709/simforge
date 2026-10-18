"""The bundled synthetic datasets, profiled, against answers worked out by hand.

Every expected value below was derived from the CSV text in
``src/simforge/quant/profiling/samples/`` without running the code.
"""

from __future__ import annotations

import math

import pytest

from simforge.quant.profiling import model
from simforge.quant.profiling.schemas import (
    ColumnOverride,
    ParseOptions,
    ProfileRequest,
    SampleSource,
)


def profile(sample: str, **options: object) -> model.ProfileComputation:
    return model.run(
        ProfileRequest(
            source=SampleSource(kind="sample", sample_id=sample),
            options=ParseOptions(**options),
        )
    )


def test_lab_measurements() -> None:
    p = profile("lab_measurements")
    assert (len(p.table.rows), len(p.table.header), p.missing_cells) == (12, 5, 0)
    assert p.duplicates.duplicate_rows == 0
    by = {c.name: c for c in p.columns}
    assert [c.type for c in p.columns] == ["numeric", "date", "categorical", "numeric", "numeric"]

    trial = by["trial"].numeric
    assert trial is not None
    # 1..12: mean 6.5; sample variance n(n+1)/12 = 13; type 7 Q1 at h = 2.75 -> 3.75.
    assert (trial.mean, trial.q1, trial.median, trial.q3) == (6.5, 3.75, 6.5, 9.25)
    assert trial.std == pytest.approx(math.sqrt(13), rel=1e-15)

    length = by["length_cm"].numeric
    assert length is not None
    assert (length.mean, length.min, length.max) == (50.0, 20.0, 80.0)

    period = by["period_s"].numeric
    assert period is not None
    # (3 * 0.90 + 3 * 1.27 + 3 * 1.55 + 3 * 1.79) / 12 = 16.53 / 12 = 1.3775
    assert period.mean == pytest.approx(1.3775, rel=1e-15)

    date = by["date"].date
    assert date is not None
    assert (date.count, date.unique, date.span_days) == (12, 3, 2.0)
    assert (date.min, date.max) == ("2026-09-01T00:00:00", "2026-09-03T00:00:00")

    material = by["material"].categorical
    assert material is not None
    assert [(t.value, t.count) for t in material.top] == [
        ("steel", 5),
        ("copper", 4),
        ("aluminium", 3),
    ]
    assert all(c.passed for c in p.checks if c.kind == "exact_identity")


def test_messy_survey_with_default_options() -> None:
    p = profile("messy_survey")
    assert (len(p.table.rows), len(p.table.header)) == (10, 6)
    assert p.table.blank_lines_skipped == 1
    # Row 7 repeats row 3 exactly (respondent 003 entered twice).
    assert (p.duplicates.duplicate_rows, p.duplicates.examples) == (1, [[3, 7]])
    by = {c.name: c for c in p.columns}

    rid = by["respondent_id"]
    assert rid.type == "categorical"
    assert "leading zeros" in rid.inference_reason
    assert rid.kind_counts.leading_zero_number == 10

    age = by["age"]
    assert age.type == "numeric"
    assert (age.missing_count, age.missing_markers_found) == (3, {"": 1, "NA": 2})
    assert age.missing_percent == 30.0
    assert age.numeric is not None
    # 34, 29, 51, 42, 29, 38, 45 -> sorted 29 29 34 38 42 45 51, sum 268.
    assert age.numeric.mean == pytest.approx(268 / 7, rel=1e-15)
    assert (age.numeric.q1, age.numeric.median, age.numeric.q3) == (31.5, 38.0, 43.5)

    # 'NA' is Namibia here, but the default markers read it as missing: the documented
    # ambiguity. ' UK ' is trimmed to 'UK' for categories.
    country = by["country"]
    assert country.missing_count == 3
    assert country.categorical is not None
    assert [(t.value, t.count) for t in country.categorical.top] == [
        ("UK", 4),
        ("FR", 2),
        ("DE", 1),
    ]

    income = by["income_gbp"]
    assert income.type == "categorical"
    assert income.missing_count == 1
    assert (income.kind_counts.number, income.kind_counts.text) == (6, 3)
    assert "Mixed: 6 numeric-looking" in income.inference_reason

    visit = by["visit_date"]
    assert visit.type == "categorical"
    assert visit.kind_counts.ambiguous_date == 10
    assert visit.categorical is not None
    assert visit.categorical.unique == 8

    rating = by["rating"]
    assert rating.type == "categorical"  # the lower-case 'n/a' is not a default marker
    assert (rating.kind_counts.number, rating.kind_counts.text) == (9, 1)

    assert p.missing_cells == 7
    checks = {c.id: c for c in p.checks}
    assert checks["mixed_columns"].value == 2.0  # income_gbp, rating
    assert all(c.passed for c in p.checks if c.kind == "exact_identity")


def test_messy_survey_with_overrides_and_namibia_kept() -> None:
    p = profile(
        "messy_survey",
        missing_markers=["NaN", "n/a"],  # 'NA' removed: Namibia is a country again
        column_types=[
            ColumnOverride(column=3, type="numeric"),
            ColumnOverride(column=5, type="numeric"),
        ],
    )
    by = {c.name: c for c in p.columns}
    country = by["country"]
    assert country.missing_count == 0
    assert country.categorical is not None
    assert ("NA", 3) in [(t.value, t.count) for t in country.categorical.top]
    assert by["age"].type == "categorical"  # 'NA' in age is now text, so age is mixed

    income = by["income_gbp"]
    assert (income.type, income.overridden, income.invalid_count) == ("numeric", True, 3)
    assert [e.row for e in income.invalid_examples] == [3, 4, 7]
    assert income.numeric is not None
    assert income.numeric.mean == 222750 / 6  # 37125, exactly representable

    rating = by["rating"]  # 'n/a' is now a marker: missing, not invalid
    assert (rating.missing_count, rating.invalid_count) == (1, 0)
    assert rating.numeric is not None
    assert rating.numeric.mean == pytest.approx(31 / 9, rel=1e-15)
    assert {c.id: c.value for c in p.checks}["invalid_values"] == 3.0
