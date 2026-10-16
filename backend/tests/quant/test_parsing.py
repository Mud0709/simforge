"""CSV parsing: shape, encoding and malformed input are explicit errors, never repaired."""

from __future__ import annotations

import codecs

import pytest

from simforge.quant.profiling.limits import (
    MAX_COLUMN_NAME_CHARS,
    MAX_COLUMNS,
    MAX_DATA_ROWS,
    MAX_FILE_BYTES,
)
from simforge.quant.profiling.parsing import DatasetError, parse_csv


def test_simple_file_keeps_exact_text() -> None:
    t = parse_csv(b"a,b\n1, x \n2,\n", "comma")
    assert t.header == ("a", "b")
    assert t.rows == [("1", " x "), ("2", "")]  # no trimming, no interpretation
    assert t.row_lines == [2, 3]
    assert t.blank_lines_skipped == 0
    assert not t.had_bom


def test_header_names_are_trimmed() -> None:
    assert parse_csv(b" a , b\n1,2\n", "comma").header == ("a", "b")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", r"empty \(0 bytes\)"),
        (b"  \n\r\n\t", "only whitespace"),
        (b"a,b\n", "no data rows"),
        (b"a,b\n\n\n", "no data rows"),
    ],
)
def test_empty_inputs_are_rejected(data: bytes, message: str) -> None:
    with pytest.raises(DatasetError, match=message):
        parse_csv(data, "comma")


def test_utf8_bom_is_removed_and_reported() -> None:
    t = parse_csv(codecs.BOM_UTF8 + b"name\nx\n", "comma")
    assert t.header == ("name",)  # not "﻿name"
    assert t.had_bom


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (codecs.BOM_UTF16_LE + "a\n1\n".encode("utf-16-le"), "UTF-16"),
        (b"a\n\xff\n", r"not valid UTF-8 text \(invalid byte at position 2\)"),
        (b"a\n1\x002\n", "NUL bytes"),
    ],
)
def test_encoding_problems_are_rejected(data: bytes, message: str) -> None:
    with pytest.raises(DatasetError, match=message):
        parse_csv(data, "comma")


def test_non_ascii_utf8_is_fine() -> None:
    t = parse_csv("city,temp\nZürich,\u22123\n".encode(), "comma")  # U+2212 minus sign
    assert t.rows == [("Zürich", "\u22123")]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"a,b,a\n1,2,3\n", "unique; repeated: 'a'"),
        (b"a, a ,b\n1,2,3\n", "unique; repeated: 'a'"),  # equal after trimming
        (b"a,,c\n1,2,3\n", r"column\(s\) 2 have none"),
        (b"a,  \n1,2\n", r"column\(s\) 2 have none"),
    ],
)
def test_bad_headers_are_rejected(data: bytes, message: str) -> None:
    with pytest.raises(DatasetError, match=message):
        parse_csv(data, "comma")


def test_column_name_and_count_limits() -> None:
    long = b"x" * (MAX_COLUMN_NAME_CHARS + 1)
    with pytest.raises(DatasetError, match="longer than"):
        parse_csv(b"a," + long + b"\n1,2\n", "comma")
    ok = ",".join(f"c{i}" for i in range(MAX_COLUMNS)).encode()
    assert len(parse_csv(ok + b"\n" + b"," * (MAX_COLUMNS - 1) + b"\n", "comma").header) == 100
    too_many = ",".join(f"c{i}" for i in range(MAX_COLUMNS + 1)).encode()
    with pytest.raises(DatasetError, match="101 columns; the limit is 100"):
        parse_csv(too_many + b"\n", "comma")


def test_inconsistent_rows_are_rejected_with_their_positions() -> None:
    data = b"a,b,c\n1,2,3\n4,5\n6,7,8,9\n10,11,12\n"
    with pytest.raises(DatasetError) as info:
        parse_csv(data, "comma")
    msg = str(info.value)
    assert "Every row must have 3 fields" in msg
    assert "2 row(s) do not: row 2 (line 3) has 2; row 3 (line 4) has 4." in msg
    assert "never padded or dropped" in msg


def test_many_inconsistent_rows_are_summarised() -> None:
    data = b"a,b\n" + b"1\n" * 8
    with pytest.raises(
        DatasetError, match=r"8 row\(s\) do not: .*row 5 \(line 6\) has 1, and 3 more"
    ):
        parse_csv(data, "comma")


def test_overlong_cell_is_rejected() -> None:
    with pytest.raises(DatasetError, match="longer than 131,072 characters"):
        parse_csv(b"a\n" + b"x" * 131_073 + b"\n", "comma")


@pytest.mark.parametrize(
    "data",
    [
        b'a,b\n"unclosed,2\n3,4\n',  # the quote swallows the rest of the file
        b'a,b\n"x"y,2\n',  # text after a closing quote
    ],
)
def test_malformed_quoting_is_rejected(data: bytes) -> None:
    with pytest.raises(DatasetError, match="not well-formed CSV near line"):
        parse_csv(data, "comma")


def test_quoted_fields_may_contain_delimiters_quotes_and_newlines() -> None:
    data = b'id,note\n1,"a, b"\n2,"say ""hi"""\n3,"two\nlines"\n4,x\n'
    t = parse_csv(data, "comma")
    assert t.rows == [("1", "a, b"), ("2", 'say "hi"'), ("3", "two\nlines"), ("4", "x")]
    assert t.row_lines == [2, 3, 4, 6]  # row 3 spans lines 4-5


def test_blank_lines_are_skipped_and_counted() -> None:
    t = parse_csv(b"\na,b\n1,2\n\n\n3,4\n", "comma")
    assert t.rows == [("1", "2"), ("3", "4")]
    assert t.blank_lines_skipped == 3
    assert t.row_lines == [3, 6]


def test_crlf_line_endings() -> None:
    t = parse_csv(b"a,b\r\n1,2\r\n3,4\r\n", "comma")
    assert t.rows == [("1", "2"), ("3", "4")]


@pytest.mark.parametrize(("delimiter", "sep"), [("semicolon", b";"), ("tab", b"\t")])
def test_other_delimiters(delimiter: str, sep: bytes) -> None:
    t = parse_csv(sep.join([b"a", b"b"]) + b"\n" + sep.join([b"1,5", b"2"]) + b"\n", delimiter)  # type: ignore[arg-type]
    assert t.header == ("a", "b")
    assert t.rows == [("1,5", "2")]  # the comma is just text here


def test_wrong_delimiter_gives_one_column_not_an_error() -> None:
    t = parse_csv(b"a;b\n1;2\n", "comma")
    assert t.header == ("a;b",)


def test_row_limit() -> None:
    at_limit = b"x\n" + b"1\n" * MAX_DATA_ROWS
    assert len(parse_csv(at_limit, "comma").rows) == MAX_DATA_ROWS
    with pytest.raises(DatasetError, match="more than 50,000 data rows"):
        parse_csv(at_limit + b"1\n", "comma")


def test_file_size_limit_on_decoded_bytes() -> None:
    body = b"x\n" + b"1\n" * ((MAX_FILE_BYTES - 2) // 2)
    assert len(body) == MAX_FILE_BYTES
    with pytest.raises(DatasetError, match="more than 50,000 data rows"):  # size is fine
        parse_csv(body, "comma")
    with pytest.raises(DatasetError, match="limit is 2,097,152 bytes"):
        parse_csv(body + b"\n", "comma")
