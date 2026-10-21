"""Turn the bytes of a CSV file into a table of text cells, or explain exactly why not.

Pure: bytes in, a :class:`ParsedTable` out, no I/O. Nothing here interprets a cell: every
value stays the exact text from the file, so later steps can show what was there. The rules:

* the file must be UTF-8 (a leading byte-order mark is allowed and removed);
* the first non-blank row is the header; names are trimmed and must be non-empty and unique;
* every data row must have exactly as many fields as the header. A row that does not is an
  error, never padded, truncated or dropped;
* lines with no fields at all (truly blank lines) are skipped and counted;
* quoting follows RFC 4180 (``"`` quotes, ``""`` escapes a quote) and is strict: a stray
  quote or an unclosed quoted field is an error.
"""

from __future__ import annotations

import codecs
import csv
import io
import re
from dataclasses import dataclass
from typing import Literal

from simforge.quant.profiling.limits import (
    MAX_COLUMN_NAME_CHARS,
    MAX_COLUMNS,
    MAX_DATA_ROWS,
    MAX_EXAMPLES,
    MAX_FILE_BYTES,
)

Delimiter = Literal["comma", "semicolon", "tab"]
DELIMITER_CHARS: dict[Delimiter, str] = {"comma": ",", "semicolon": ";", "tab": "\t"}


_LINE_BREAK = re.compile(r"\r\n|\r|\n")


class DatasetError(ValueError):
    """The file cannot be read as a table. The message is shown to the user as is."""


@dataclass(frozen=True, slots=True)
class ParsedTable:
    header: tuple[str, ...]
    rows: list[tuple[str, ...]]
    row_lines: list[int]  # physical line on which each data row starts (1-based)
    blank_lines_skipped: int
    had_bom: bool


def _decode(data: bytes) -> tuple[str, bool]:
    if len(data) == 0:
        raise DatasetError("The file is empty (0 bytes).")
    if len(data) > MAX_FILE_BYTES:
        raise DatasetError(
            f"The file is {len(data):,} bytes; the limit is {MAX_FILE_BYTES:,} bytes (2 MiB)."
        )
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        raise DatasetError("The file is UTF-16 text. Re-save it as UTF-8 CSV.")
    had_bom = data.startswith(codecs.BOM_UTF8)
    try:
        text = data.decode("utf-8-sig" if had_bom else "utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetError(
            f"The file is not valid UTF-8 text (invalid byte at position {exc.start}). "
            "Re-save it as UTF-8 CSV."
        ) from exc
    if "\x00" in text:
        raise DatasetError("The file contains NUL bytes, so it is probably not a text file.")
    if text.strip() == "":
        raise DatasetError("The file contains no data, only whitespace.")
    return text, had_bom


def _check_header(raw: list[str]) -> tuple[str, ...]:
    if len(raw) > MAX_COLUMNS:
        raise DatasetError(f"The header has {len(raw)} columns; the limit is {MAX_COLUMNS}.")
    names = tuple(name.strip() for name in raw)
    unnamed = [i + 1 for i, name in enumerate(names) if name == ""]
    if unnamed:
        raise DatasetError(
            f"Every column needs a name in the first row; column(s) {_list(unnamed)} have none."
        )
    long = [i + 1 for i, name in enumerate(names) if len(name) > MAX_COLUMN_NAME_CHARS]
    if long:
        raise DatasetError(
            f"Column name(s) {_list(long)} are longer than {MAX_COLUMN_NAME_CHARS} characters."
        )
    seen: set[str] = set()
    duplicates: list[str] = []
    for name in names:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        shown = ", ".join(repr(_short(d)) for d in duplicates[:MAX_EXAMPLES])
        raise DatasetError(
            f"Column names must be unique; repeated: {shown}. Rename them and try again."
        )
    return names


def _check_quotes(text: str, delimiter: str) -> None:
    """Reject quotes that RFC 4180 does not allow. Python's csv module, even with
    strict=True, keeps a quote inside an unquoted field (``x"y``) as ordinary text.

    A quote may open a field (first character, or right after a delimiter or line break),
    appear doubled inside a quoted field, or close one. Only quote characters are visited.
    """
    in_quotes = False
    i = text.find('"')
    while i != -1:
        if in_quotes:
            if text.startswith('""', i):  # an escaped quote inside a quoted field
                i = text.find('"', i + 2)
                continue
            in_quotes = False
        elif i == 0 or text[i - 1] in (delimiter, "\n", "\r"):
            in_quotes = True
        else:
            # Count line breaks of every style the csv reader accepts: \r\n, \n and \r.
            line = len(_LINE_BREAK.findall(text, 0, i)) + 1
            raise DatasetError(
                f"The file has a stray quotation mark on line {line}: a quote may only start "
                "a quoted field or be doubled inside one. Quote the whole field, or remove it."
            )
        i = text.find('"', i + 1)


def parse_csv(data: bytes, delimiter: Delimiter) -> ParsedTable:
    text, had_bom = _decode(data)
    _check_quotes(text, DELIMITER_CHARS[delimiter])
    # newline="" hands line endings to the csv module, which handles \n, \r\n and newlines
    # inside quoted fields itself.
    reader = csv.reader(
        io.StringIO(text, newline=""),
        delimiter=DELIMITER_CHARS[delimiter],
        quotechar='"',
        doublequote=True,
        strict=True,
    )
    header: tuple[str, ...] | None = None
    rows: list[tuple[str, ...]] = []
    row_lines: list[int] = []
    blank = 0
    bad: list[tuple[int, int, int]] = []  # (data row number, line, field count)
    bad_total = 0
    previous_line = 0
    try:
        for record in reader:
            start_line = previous_line + 1
            previous_line = reader.line_num
            if len(record) == 0:
                blank += 1
                continue
            if header is None:
                header = _check_header(record)
                continue
            if len(rows) >= MAX_DATA_ROWS:
                raise DatasetError(
                    f"The file has more than {MAX_DATA_ROWS:,} data rows, the limit for "
                    "this version. Use a sample of the data."
                )
            if len(record) != len(header):
                bad_total += 1
                if len(bad) < MAX_EXAMPLES:
                    bad.append((len(rows) + bad_total, start_line, len(record)))
                continue
            rows.append(tuple(record))
            row_lines.append(start_line)
    except csv.Error as exc:
        if "field larger than field limit" in str(exc):
            raise DatasetError(
                f"A cell near line {reader.line_num} is longer than {csv.field_size_limit():,} "
                "characters. This often means a quotation mark was opened and never closed."
            ) from exc
        raise DatasetError(
            f"The file is not well-formed CSV near line {reader.line_num}: {exc}. A common "
            "cause is an unclosed or stray quotation mark."
        ) from exc

    if header is None:  # pragma: no cover - _decode already rejects whitespace-only text
        raise DatasetError("The file contains no rows.")
    if bad_total:
        details = "; ".join(f"row {r} (line {line}) has {n}" for r, line, n in bad)
        more = f", and {bad_total - len(bad)} more" if bad_total > len(bad) else ""
        raise DatasetError(
            f"Every row must have {len(header)} fields, like the header. "
            f"{bad_total} row(s) do not: {details}{more}. Rows are never padded or dropped "
            "automatically; check the delimiter setting, or fix these rows."
        )
    if not rows:
        raise DatasetError("The file has a header row but no data rows.")
    return ParsedTable(
        header=header, rows=rows, row_lines=row_lines, blank_lines_skipped=blank, had_bom=had_bom
    )


def _list(items: list[int]) -> str:
    shown = ", ".join(str(i) for i in items[:MAX_EXAMPLES])
    return shown + (f" and {len(items) - MAX_EXAMPLES} more" if len(items) > MAX_EXAMPLES else "")


def _short(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
