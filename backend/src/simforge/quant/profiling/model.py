"""Orchestrates one dataset profile: load bytes, parse, type each column, summarise, check.

Pure computation: no HTTP, no database, no files except the bundled samples (looked up by
a fixed identifier, never by a path from the request). The API layer adds run metadata.
The uploaded bytes live only in memory for the duration of the call.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import time
from collections import Counter
from dataclasses import dataclass
from importlib.resources import files

from simforge.core.schemas import Assumption, ModelInfo, ValidationCheck
from simforge.quant.profiling import statistics as st
from simforge.quant.profiling.inference import ColumnType, Kind, parse_date, type_column
from simforge.quant.profiling.inference import is_mixed as kinds_are_mixed
from simforge.quant.profiling.limits import (
    MAX_DISPLAY_CHARS,
    MAX_EXAMPLES,
    PREVIEW_ROWS,
)
from simforge.quant.profiling.parsing import (
    DELIMITER_CHARS,
    DatasetError,
    ParsedTable,
    parse_csv,
)
from simforge.quant.profiling.schemas import (
    CategoricalSummary,
    CategoryCount,
    ColumnProfile,
    DatasetIdentity,
    DateSummary,
    DuplicateSummary,
    Example,
    HistogramBins,
    KindCounts,
    NumericSummary,
    ParseOptions,
    Preview,
    ProfileRequest,
    SampleId,
    SampleInfo,
    UploadSource,
)

MODEL_INFO = ModelInfo(
    id="quant.dataset_profile",
    version="1.0.0",
    name="Dataset profile",
    description="Reads a CSV file and describes its structure and quality: column types, "
    "missing values, duplicate rows and descriptive statistics.",
)

SAMPLES: dict[SampleId, tuple[str, SampleInfo]] = {
    "lab_measurements": (
        "lab_measurements.csv",
        SampleInfo(
            id="lab_measurements",
            title="Lab measurements (clean)",
            description="12 invented pendulum trials: dates, materials, lengths and periods. "
            "No missing values.",
        ),
    ),
    "messy_survey": (
        "messy_survey.csv",
        SampleInfo(
            id="messy_survey",
            title="Survey (deliberately messy)",
            description="10 invented survey rows with missing values, a duplicate row, mixed "
            "and ambiguous columns, and 'NA' used for Namibia.",
        ),
    ),
}

ASSUMPTIONS: list[Assumption] = [
    Assumption(
        id="descriptive_only",
        statement="Every number describes the rows in this file and nothing else. No "
        "statistic here is an estimate for a wider population, a test or a prediction.",
    ),
    Assumption(
        id="header_and_shape",
        statement="The first non-blank row is the header. Every row must have as many fields "
        "as the header; a file where some do not is rejected rather than padded or trimmed. "
        "Blank lines are skipped and counted.",
    ),
    Assumption(
        id="missing_values",
        statement="A cell is missing if, after trimming spaces, it is empty or exactly equal "
        "(case-sensitive) to one of the missing-value markers. Markers can be wrong for your "
        "data: 'NA' is also the country code for Namibia, so edit the list when needed.",
    ),
    Assumption(
        id="type_rules",
        statement="Numbers are plain decimal or scientific notation (no thousands "
        "separators). Dates are ISO 8601 (YYYY-MM-DD, optional time) and must exist on the "
        "calendar. 01/02/2024-style dates are ambiguous and stay text. Numbers with leading "
        "zeros stay text unless you override the column. A column with any other value is "
        "categorical; nothing is converted silently.",
    ),
    Assumption(
        id="overrides_and_invalid",
        statement="Overriding a column's type never changes the data. Values that do not fit "
        "the chosen type are counted as invalid, shown, and left out of the statistics.",
    ),
    Assumption(
        id="duplicates",
        statement="A duplicate row is identical, character for character, to an earlier row "
        "(so ' UK' and 'UK' differ, and so do '1' and '1.0'). Duplicates are counted, not "
        "removed.",
    ),
    Assumption(
        id="statistics_definitions",
        statement="Mean; sample standard deviation with n - 1; quartiles by linear "
        "interpolation (Hyndman-Fan type 7, as in NumPy and spreadsheets' QUARTILE.INC, which "
        "can differ from the 'median of each half' method for small samples). Percentages are "
        "of all rows. Computed in double precision from the parsed values, so 0.1 is stored "
        "as the nearest binary fraction; agreement with exact arithmetic is to about 1e-15 "
        "relative, not exact.",
    ),
]

METHOD_NOTE = (
    "Counts (rows, missing, invalid, duplicates, categories) are exact. Means, standard "
    "deviations and quartiles are computed in double precision and are correct to rounding. "
    "A statistic whose true value does not fit in double precision is reported as missing, "
    "never as infinity. The file's SHA-256 identifies its exact bytes; it is not evidence "
    "that the data are accurate."
)


@dataclass(frozen=True, slots=True)
class ProfileComputation:
    dataset: DatasetIdentity
    options: ParseOptions
    table: ParsedTable
    columns: list[ColumnProfile]
    duplicates: DuplicateSummary
    preview: Preview
    missing_cells: int
    checks: list[ValidationCheck]
    elapsed_ms: float


def sample_bytes(sample_id: SampleId) -> bytes:
    filename, _ = SAMPLES[sample_id]
    return (files("simforge.quant.profiling") / "samples" / filename).read_bytes()


def decode_upload(source: UploadSource) -> bytes:
    try:
        data = base64.b64decode(source.content_base64, validate=True)
    except binascii.Error as exc:
        raise DatasetError(
            "The upload is not valid base64. The page encodes files automatically, so this "
            "suggests a damaged request."
        ) from exc
    # The decoded size is checked by parse_csv, which applies to bundled samples as well.
    return data


def _display(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_DISPLAY_CHARS:
        return text, False
    return text[: MAX_DISPLAY_CHARS - 1] + "…", True


def _overrides(options: ParseOptions, n_columns: int) -> dict[int, ColumnType]:
    out = {o.column: o.type for o in options.column_types}
    beyond = sorted(c for c in out if c >= n_columns)
    if beyond:
        raise DatasetError(
            f"Type override for column position {beyond[0]}, but the file has only "
            f"{n_columns} columns (positions 0 to {n_columns - 1})."
        )
    return out


def _profile_column(
    index: int, name: str, cells: list[str], markers: frozenset[str], override: ColumnType | None
) -> ColumnProfile:
    typing = type_column(cells, markers, override)
    n = len(cells)
    found = Counter(c.strip() for c in cells if c.strip() == "" or c.strip() in markers)
    valid = [cells[i].strip() for i in typing.valid_rows]

    numeric = date = categorical = None
    notes = list(typing.notes)
    if valid and typing.type == "numeric":
        s = st.numeric_stats([float(v) for v in valid])
        notes.extend(s.notes)
        numeric = NumericSummary(
            count=s.count,
            mean=s.mean,
            std=s.std,
            min=s.min,
            q1=s.q1,
            median=s.median,
            q3=s.q3,
            max=s.max,
            histogram=HistogramBins(edges=s.bin_edges, counts=s.bin_counts),
        )
    elif valid and typing.type == "date":
        pairs = [(v, parse_date(v)) for v in valid]
        d = st.date_stats([(v, p) for v, p in pairs if p is not None])
        date = DateSummary(
            count=d.count, unique=d.unique, min=d.min, max=d.max, span_days=d.span_days
        )
    elif valid and typing.type == "categorical":
        c = st.categorical_stats(valid)
        categorical = CategoricalSummary(
            count=c.count,
            unique=c.unique,
            top=[CategoryCount(value=_display(t.value)[0], count=t.count) for t in c.top],
            other_count=c.other_count,
        )
        if c.unique == c.count and c.count > 1:
            notes.append("Every value is different: this looks like an identifier or free text.")
    elif typing.type != "empty":
        notes.append("No valid values for this type, so there are no statistics.")

    k = typing.kinds
    return ColumnProfile(
        index=index,
        name=name,
        inferred_type=typing.inferred,
        inference_reason=typing.reason,
        type=typing.type,
        overridden=typing.overridden,
        missing_count=typing.missing,
        invalid_count=typing.invalid,
        valid_count=len(valid),
        missing_percent=100.0 * typing.missing / n,
        invalid_percent=100.0 * typing.invalid / n,
        missing_markers_found=dict(sorted(found.items())),
        kind_counts=KindCounts(
            number=k[Kind.NUMBER],
            leading_zero_number=k[Kind.LEADING_ZERO_NUMBER],
            non_finite_number=k[Kind.NON_FINITE_NUMBER],
            date=k[Kind.DATE],
            ambiguous_date=k[Kind.AMBIGUOUS_DATE],
            text=k[Kind.TEXT],
        ),
        invalid_examples=[
            Example(row=e.row, value=_display(e.value)[0]) for e in typing.invalid_examples
        ],
        notes=notes,
        numeric=numeric,
        date=date,
        categorical=categorical,
    )


def is_mixed(column: ColumnProfile) -> bool:
    """Categorical and mixed by the same rule as its inference reason (inference.is_mixed)."""
    k = column.kind_counts
    kinds = Counter(
        {
            Kind.NUMBER: k.number,
            Kind.LEADING_ZERO_NUMBER: k.leading_zero_number,
            Kind.NON_FINITE_NUMBER: k.non_finite_number,
            Kind.DATE: k.date,
            Kind.AMBIGUOUS_DATE: k.ambiguous_date,
            Kind.TEXT: k.text,
        }
    )
    return column.inferred_type == "categorical" and kinds_are_mixed(kinds)


def _checks(
    n_rows: int, columns: list[ColumnProfile], duplicates: DuplicateSummary
) -> list[ValidationCheck]:
    unbalanced = sum(
        1 for c in columns if c.missing_count + c.invalid_count + c.valid_count != n_rows
    )
    histogram_off = sum(
        1 for c in columns if c.numeric and sum(c.numeric.histogram.counts) != c.valid_count
    )
    category_off = sum(
        1
        for c in columns
        if c.categorical
        and sum(t.count for t in c.categorical.top) + c.categorical.other_count != c.valid_count
    )
    duplicate_off = abs(duplicates.distinct_rows + duplicates.duplicate_rows - n_rows)
    mixed = sum(1 for c in columns if is_mixed(c))
    invalid = sum(c.invalid_count for c in columns)
    return [
        ValidationCheck(
            id="cell_accounting",
            label="Missing + invalid + valid = rows",
            value=float(unbalanced),
            threshold=0.0,
            passed=unbalanced == 0,
            kind="exact_identity",
            note="Number of columns where the three counts do not add up to the row count. "
            "Every cell must be accounted for exactly once.",
        ),
        ValidationCheck(
            id="histogram_totals",
            label="Histogram counts = valid values",
            value=float(histogram_off),
            threshold=0.0,
            passed=histogram_off == 0,
            kind="exact_identity",
            note="Number of numeric columns whose histogram does not contain every valid value "
            "exactly once.",
        ),
        ValidationCheck(
            id="category_totals",
            label="Category counts = valid values",
            value=float(category_off),
            threshold=0.0,
            passed=category_off == 0,
            kind="exact_identity",
            note="Number of categorical columns where the listed categories plus 'other' do not "
            "add up to the valid values.",
        ),
        ValidationCheck(
            id="duplicate_accounting",
            label="Distinct + duplicate rows = rows",
            value=float(duplicate_off),
            threshold=0.0,
            passed=duplicate_off == 0,
            kind="exact_identity",
            note="Every row is either the first of its kind or a repeat of an earlier one.",
        ),
        ValidationCheck(
            id="mixed_columns",
            label="Mixed columns",
            value=float(mixed),
            threshold=None,
            passed=None,
            kind="informational",
            note="Columns holding both number- or date-like values and other text. They are "
            "kept as categories; check them, and override the type if appropriate.",
        ),
        ValidationCheck(
            id="invalid_values",
            label="Values invalid for an overridden type",
            value=float(invalid),
            threshold=None,
            passed=None,
            kind="informational",
            note="Excluded from the statistics, never converted or deleted.",
        ),
    ]


def run(request: ProfileRequest) -> ProfileComputation:
    start = time.perf_counter()
    source = request.source
    if isinstance(source, UploadSource):
        data, sample_id = decode_upload(source), None
    else:
        data, sample_id = sample_bytes(source.sample_id), source.sample_id
    options = request.options
    table = parse_csv(data, options.delimiter)
    overrides = _overrides(options, len(table.header))
    markers = frozenset(options.missing_markers)

    columns = [
        _profile_column(i, name, [row[i] for row in table.rows], markers, overrides.get(i))
        for i, name in enumerate(table.header)
    ]
    if len(columns) == 1 and table.blank_lines_skipped:
        # With one column, an empty value and a blank line are the same text: say so rather
        # than let missing values vanish from the count.
        columns[0].notes.append(
            f"{table.blank_lines_skipped} blank line(s) were skipped. In a one-column file a "
            "blank line may be an empty value; if so, it is not counted as missing here."
        )
    if len(columns) == 1:
        others = [n for n, ch in DELIMITER_CHARS.items() if n != options.delimiter]
        hinted = [n for n in others if DELIMITER_CHARS[n] in table.header[0]]
        if hinted:
            columns[0].notes.append(
                f"Only one column was found, but its name contains a {hinted[0]} character. "
                f"Is the delimiter really {options.delimiter}?"
            )
    d = st.duplicate_rows(table.rows, MAX_EXAMPLES)
    duplicates = DuplicateSummary(
        duplicate_rows=d.duplicate_rows,
        distinct_rows=d.distinct_rows,
        groups=d.groups,
        examples=d.examples,
    )
    truncated = 0
    preview_rows: list[list[str]] = []
    for row in table.rows[:PREVIEW_ROWS]:
        shown = [_display(cell) for cell in row]
        truncated += sum(1 for _, cut in shown if cut)
        preview_rows.append([text for text, _ in shown])

    return ProfileComputation(
        dataset=DatasetIdentity(
            source="sample" if sample_id else "upload",
            sample_id=sample_id,
            sha256=hashlib.sha256(data).hexdigest(),
            byte_size=len(data),
            had_bom=table.had_bom,
        ),
        options=options,
        table=table,
        columns=columns,
        duplicates=duplicates,
        preview=Preview(
            columns=[_display(h)[0] for h in table.header],
            rows=preview_rows,
            truncated_cells=truncated,
        ),
        missing_cells=sum(c.missing_count for c in columns),
        checks=_checks(len(table.rows), columns, duplicates),
        elapsed_ms=(time.perf_counter() - start) * 1e3,
    )
