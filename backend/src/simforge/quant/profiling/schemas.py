"""API contract for dataset profiling.

Identity. A profile is fully determined by (model version, file bytes, options):

* ``DatasetIdentity.sha256`` is the SHA-256 of the exact bytes received. It identifies the
  file: change one byte and it changes. It says nothing about whether the data are accurate;
  a perfectly hashed file can still be wrong;
* ``ParseOptions`` are canonicalised (markers trimmed, de-duplicated and sorted; overrides
  sorted by column), so settings that mean the same thing are represented identically;
* ``RunMetadata.input_hash`` hashes the file's SHA-256 and size together with the options.
  Change any setting and the hash changes, so a result can be matched to the exact
  settings that produced it.

Overrides name columns by position, not by name, so the experiment log never stores
column names.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator

from simforge.core.schemas import Assumption, ModelInfo, RunMetadata, StrictModel, ValidationCheck
from simforge.quant.profiling.inference import ColumnType, InferredType
from simforge.quant.profiling.limits import MAX_BASE64_CHARS, MAX_COLUMNS
from simforge.quant.profiling.parsing import Delimiter

SampleId = Literal["lab_measurements", "messy_survey"]

DEFAULT_MISSING_MARKERS = ["N/A", "NA", "NaN", "None", "null"]
MAX_MARKERS = 20
MAX_MARKER_CHARS = 32


class ColumnOverride(StrictModel):
    column: int = Field(ge=0, lt=MAX_COLUMNS, description="0-based column position.")
    type: ColumnType


class ParseOptions(StrictModel):
    delimiter: Delimiter = "comma"
    missing_markers: list[Annotated[str, Field(max_length=MAX_MARKER_CHARS)]] = Field(
        default_factory=lambda: list(DEFAULT_MISSING_MARKERS),
        max_length=MAX_MARKERS,
        description="Cell values (after trimming spaces, case-sensitive) read as missing, in "
        "addition to empty cells, which are always missing.",
    )
    column_types: list[ColumnOverride] = Field(
        default_factory=list,
        max_length=MAX_COLUMNS,
        description="Type overrides; columns not listed keep their inferred type.",
    )

    @field_validator("missing_markers")
    @classmethod
    def _canonical_markers(cls, markers: list[str]) -> list[str]:
        return sorted({m.strip() for m in markers} - {""})

    @field_validator("column_types")
    @classmethod
    def _canonical_overrides(cls, overrides: list[ColumnOverride]) -> list[ColumnOverride]:
        columns = [o.column for o in overrides]
        if len(set(columns)) != len(columns):
            raise ValueError("each column may be overridden at most once")
        return sorted(overrides, key=lambda o: o.column)


class UploadSource(StrictModel):
    kind: Literal["upload"]
    content_base64: str = Field(
        min_length=1,
        max_length=MAX_BASE64_CHARS,
        description="The file's bytes, base64-encoded (2 MiB of file at most). The file name "
        "is not sent: the server does not need it.",
    )


class SampleSource(StrictModel):
    kind: Literal["sample"]
    sample_id: SampleId


class ProfileRequest(StrictModel):
    source: Annotated[UploadSource | SampleSource, Field(discriminator="kind")]
    options: ParseOptions = Field(default_factory=ParseOptions)
    save_experiment: bool = Field(
        default=False,
        description="Opt in to logging this run. Only the file's hash and size, the options "
        "(including any missing-value markers typed) and a few counts are stored: no rows, "
        "file name or column names.",
    )


class SampleInfo(StrictModel):
    id: SampleId
    title: str
    description: str


class DatasetIdentity(StrictModel):
    source: Literal["upload", "sample"]
    sample_id: SampleId | None
    sha256: str = Field(description="SHA-256 of the exact bytes: an identity, not a quality check.")
    byte_size: int
    had_bom: bool


class Example(StrictModel):
    row: int = Field(description="1-based data row; the header is not counted.")
    value: str


class HistogramBins(StrictModel):
    edges: list[float]
    counts: list[int]


class NumericSummary(StrictModel):
    count: int
    mean: float
    std: float | None = Field(
        description="Sample standard deviation (n - 1); None if n < 2 or not representable."
    )
    min: float
    q1: float
    median: float
    q3: float
    max: float
    histogram: HistogramBins


class DateSummary(StrictModel):
    count: int
    unique: int
    min: str
    max: str
    span_days: float


class CategoryCount(StrictModel):
    value: str
    count: int


class CategoricalSummary(StrictModel):
    count: int
    unique: int
    top: list[CategoryCount]
    other_count: int


class KindCounts(StrictModel):
    """How the non-missing cells were classified, before any override."""

    number: int
    leading_zero_number: int
    non_finite_number: int
    date: int
    ambiguous_date: int
    text: int


class ColumnProfile(StrictModel):
    index: int
    name: str
    inferred_type: InferredType
    inference_reason: str
    type: InferredType
    overridden: bool
    missing_count: int
    invalid_count: int
    valid_count: int
    missing_percent: float
    invalid_percent: float
    missing_markers_found: dict[str, int] = Field(
        description="How often each missing-value representation occurred; '' = empty cell."
    )
    kind_counts: KindCounts
    invalid_examples: list[Example]
    notes: list[str]
    numeric: NumericSummary | None
    date: DateSummary | None
    categorical: CategoricalSummary | None


class DuplicateSummary(StrictModel):
    duplicate_rows: int = Field(
        description="Rows identical, character for character, to an earlier row. Not removed."
    )
    distinct_rows: int
    groups: int
    examples: list[list[int]]


class Preview(StrictModel):
    columns: list[str]
    rows: list[list[str]]
    truncated_cells: int = Field(description="Cells shortened for display.")


class ProfileResponse(StrictModel):
    model: ModelInfo
    dataset: DatasetIdentity
    options: ParseOptions
    n_rows: int
    n_columns: int
    blank_lines_skipped: int
    missing_cells: int
    duplicates: DuplicateSummary
    columns: list[ColumnProfile]
    preview: Preview
    assumptions: list[Assumption]
    checks: list[ValidationCheck]
    method_note: str
    metadata: RunMetadata
