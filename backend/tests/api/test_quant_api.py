"""Dataset profiling API: success, every failure mode, identity, limits and privacy."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from simforge.quant.profiling.limits import MAX_BASE64_CHARS, MAX_FILE_BYTES, MAX_REQUEST_BYTES
from simforge.quant.profiling.model import sample_bytes
from tests.approx import rel_approx

URL = "/api/v1/quant/datasets/profile"
CSV = b"city,temp_c,when\nOslo,-3.5,2026-01-05\nLima,19,2026-01-05\nOslo,-3.5,2026-01-05\n"


def strict(text: str) -> Any:
    return json.loads(text, parse_constant=lambda c: pytest.fail(f"non-finite literal {c}"))


def upload(data: bytes, **extra: Any) -> dict[str, Any]:
    return {
        "source": {"kind": "upload", "content_base64": base64.b64encode(data).decode()},
        **extra,
    }


def test_samples_are_listed(client: TestClient) -> None:
    r = client.get("/api/v1/quant/datasets/samples")
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == ["lab_measurements", "messy_survey"]


def test_upload_profile(client: TestClient) -> None:
    r = client.post(URL, json=upload(CSV))
    assert r.status_code == 200
    b = strict(r.text)
    assert b["model"]["id"] == "quant.dataset_profile"
    assert (b["n_rows"], b["n_columns"]) == (3, 3)
    assert b["dataset"] == {
        "source": "upload",
        "sample_id": None,
        "sha256": hashlib.sha256(CSV).hexdigest(),
        "byte_size": len(CSV),
        "had_bom": False,
    }
    assert b["duplicates"]["duplicate_rows"] == 1
    assert [c["type"] for c in b["columns"]] == ["categorical", "numeric", "date"]
    temp = b["columns"][1]["numeric"]
    assert temp["mean"] == rel_approx((-3.5 + 19 - 3.5) / 3, rel=1e-15)
    assert b["preview"]["rows"][1] == ["Lima", "19", "2026-01-05"]
    assert {a["id"] for a in b["assumptions"]} >= {"descriptive_only", "duplicates"}
    assert all(c["passed"] is not False for c in b["checks"])
    assert b["metadata"]["experiment_saved"] is False


def test_sample_and_identical_upload_share_their_identity(client: TestClient) -> None:
    a = client.post(URL, json={"source": {"kind": "sample", "sample_id": "messy_survey"}}).json()
    b = client.post(URL, json=upload(sample_bytes("messy_survey"))).json()
    assert a["dataset"]["sha256"] == b["dataset"]["sha256"]
    assert a["metadata"]["input_hash"] == b["metadata"]["input_hash"]
    assert a["columns"] == b["columns"]


def test_every_setting_is_part_of_the_identity(client: TestClient) -> None:
    def key(data: bytes = CSV, **options: Any) -> str:
        r = client.post(URL, json=upload(data, options=options))
        assert r.status_code == 200, r.text
        return str(r.json()["metadata"]["input_hash"])

    base = key()
    changed = {
        key(CSV + b"Rome,12,2026-01-06\n"),  # one more row
        key(CSV.replace(b"Lima", b"Lime")),  # same size, one byte different
        key(delimiter="semicolon"),
        key(missing_markers=["NA"]),
        key(missing_markers=[]),
        key(column_types=[{"column": 1, "type": "categorical"}]),
        key(column_types=[{"column": 2, "type": "categorical"}]),
    }
    assert base not in changed
    assert len(changed) == 7
    # Settings that mean the same thing are represented the same way (canonical options).
    assert key(missing_markers=["null", " NA ", "None", "NaN", "N/A", "NA", ""]) == base
    swapped = [{"column": 2, "type": "date"}, {"column": 0, "type": "categorical"}]
    in_order = [{"column": 0, "type": "categorical"}, {"column": 2, "type": "date"}]
    assert key(column_types=swapped) == key(column_types=in_order)


def test_options_are_echoed_canonically(client: TestClient) -> None:
    b = client.post(URL, json=upload(CSV, options={"missing_markers": ["x", " x", "a"]})).json()
    assert b["options"]["missing_markers"] == ["a", "x"]


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        (b"", None),  # rejected by the schema (min_length)
        (b"\xef\xbb\xbf", "only whitespace"),
        (b"a,b\n", "no data rows"),
        (b"a,a\n1,2\n", "Column names must be unique"),
        (b"a,b\n1\n", "Every row must have 2 fields"),
        (b'a\n"open\n', "not well-formed CSV"),
        (b"a\n\xff\n", "not valid UTF-8"),
    ],
)
def test_bad_files_are_explained(client: TestClient, data: bytes, fragment: str | None) -> None:
    r = client.post(URL, json=upload(data))
    assert r.status_code == 422
    if fragment is not None:
        assert fragment in r.json()["detail"]


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ({"source": {"kind": "upload", "content_base64": "not base64!"}}, "not valid base64"),
        ({"source": {"kind": "upload", "content_base64": "YQ"}}, "not valid base64"),  # padding
        ({"source": {"kind": "sample", "sample_id": "../../etc/passwd"}}, None),
        ({"source": {"kind": "file", "path": "/etc/passwd"}}, None),
        ({"source": {"kind": "upload", "content_base64": "YQ==", "filename": "a.csv"}}, None),
        (upload(CSV, options={"column_types": [{"column": 3, "type": "numeric"}]}), "only 3"),
        (upload(CSV, options={"column_types": [{"column": 100, "type": "numeric"}]}), None),
        (upload(CSV, options={"column_types": [{"column": 1, "type": "integer"}]}), None),
        (
            upload(CSV, options={"column_types": [{"column": 1, "type": "numeric"}] * 2}),
            None,
        ),
        (upload(CSV, options={"missing_markers": ["m"] * 21}), None),
        (upload(CSV, options={"missing_markers": ["m" * 33]}), None),
        (upload(CSV, options={"delimiter": "|"}), None),
        (upload(CSV, unknown=True), None),
    ],
)
def test_bad_requests_are_rejected(
    client: TestClient, body: dict[str, Any], fragment: str | None
) -> None:
    r = client.post(URL, json=body)
    assert r.status_code == 422
    if fragment is not None:
        assert fragment in r.json()["detail"]


def test_numbers_and_dates_without_text_count_as_mixed(client: TestClient) -> None:
    b = client.post(URL, json=upload(b"when\n1\n2024-01-01\n")).json()
    assert "the rest are text" not in b["columns"][0]["inference_reason"]
    assert {c["id"]: c["value"] for c in b["checks"]}["mixed_columns"] == 1.0


def test_single_column_with_another_delimiter_gets_a_hint(client: TestClient) -> None:
    col = client.post(URL, json=upload(b"a;b\n1;2\n")).json()["columns"][0]
    assert col["name"] == "a;b"
    assert any("Is the delimiter really comma?" in n for n in col["notes"])


def test_one_column_file_warns_that_blank_lines_may_be_empty_values(client: TestClient) -> None:
    b = client.post(URL, json=upload(b"score\n4\n\n7\n")).json()
    assert (b["n_rows"], b["blank_lines_skipped"]) == (2, 1)
    assert any("may be an empty value" in n for n in b["columns"][0]["notes"])
    two = client.post(URL, json=upload(b"a,b\n4,1\n\n7,2\n")).json()
    assert not any("may be an empty value" in n for c in two["columns"] for n in c["notes"])


def test_numeric_sentinel_marker_is_missing_not_a_number(client: TestClient) -> None:
    # -999 is a common "no reading" code; as a marker it must not enter the statistics.
    data = b"temp\n10\n-999\n20\n"
    plain = client.post(URL, json=upload(data)).json()["columns"][0]
    assert plain["numeric"]["mean"] == rel_approx(-323.0, rel=1e-15)  # (10 - 999 + 20) / 3
    marked = client.post(URL, json=upload(data, options={"missing_markers": ["-999"]})).json()
    col = marked["columns"][0]
    assert (col["missing_count"], col["missing_markers_found"]) == (1, {"-999": 1})
    assert col["numeric"]["mean"] == 15.0


def test_override_that_fits_no_value_gives_no_statistics(client: TestClient) -> None:
    b = client.post(
        URL, json=upload(CSV, options={"column_types": [{"column": 0, "type": "date"}]})
    )
    city = b.json()["columns"][0]
    assert (city["type"], city["invalid_count"], city["valid_count"]) == ("date", 3, 0)
    assert (city["date"], city["numeric"], city["categorical"]) == (None, None, None)
    assert any("No valid values" in n for n in city["notes"])


def test_unrepresentable_statistic_is_null_in_json(client: TestClient) -> None:
    b = client.post(URL, json=upload(b"x\n-1.7e308\n1.7e308\n"))
    assert b.status_code == 200
    num = strict(b.text)["columns"][0]["numeric"]
    assert num["std"] is None
    assert num["mean"] == 0.0


def test_largest_allowed_file_fits_within_the_request_limit(client: TestClient) -> None:
    # Exactly 2 MiB of realistic 5-column rows (about 40,000 of them, under the row limit);
    # the last row is padded to hit the byte limit exactly.
    header = b"id,label,date,value,note\n"
    row = b"1234567,abcdefghij,2026-01-05,0.125,some free text\n"
    rows = (MAX_FILE_BYTES - len(header)) // len(row)
    data = header + row * (rows - 1)
    fixed = b"1,,2026-01-05,0.5,t\n"
    data += b"1," + b"x" * (MAX_FILE_BYTES - len(data) - len(fixed)) + fixed[2:]
    assert len(data) == MAX_FILE_BYTES
    body = json.dumps(upload(data, options={"missing_markers": ["m" * 32] * 20})).encode()
    assert len(base64.b64encode(data)) == MAX_BASE64_CHARS
    assert len(body) < MAX_REQUEST_BYTES
    start = time.perf_counter()
    r = client.post(URL, content=body, headers={"content-type": "application/json"})
    elapsed = time.perf_counter() - start
    assert r.status_code == 200, r.text[:300]
    assert r.json()["n_rows"] == rows
    assert elapsed < 30  # observed about 1 s; generous so slow CI machines do not flake


def test_one_byte_over_the_file_limit_is_rejected(client: TestClient) -> None:
    # MAX + 1 bytes still encodes to MAX_BASE64_CHARS (base64 pads to 3-byte groups), so
    # the schema accepts it; the parser's check on the decoded size must reject it.
    data = b"x\n" + b"1" * (MAX_FILE_BYTES - 2) + b"\n"
    assert len(data) == MAX_FILE_BYTES + 1
    assert len(base64.b64encode(data)) == MAX_BASE64_CHARS
    r = client.post(URL, json=upload(data))
    assert r.status_code == 422
    assert (
        r.json()["detail"] == "The file is 2,097,153 bytes; the limit is 2,097,152 bytes (2 MiB)."
    )


def test_validation_errors_do_not_echo_the_upload(client: TestClient) -> None:
    # One base64 group over the schema limit: rejected by validation, whose default error
    # body would quote the whole ~2.8 MB input back.
    content = base64.b64encode(b"x" * (MAX_FILE_BYTES + 3)).decode()
    assert len(content) > MAX_BASE64_CHARS
    r = client.post(URL, json={"source": {"kind": "upload", "content_base64": content}})
    assert r.status_code == 422
    assert len(r.content) < 2_000
    assert content[:200] not in r.text
    assert "omitted" in r.text


def test_small_upload_is_not_echoed_either(client: TestClient) -> None:
    # A short file rejected for another reason must not come back. An unknown source kind
    # makes validation echo the whole source object, file content included.
    content = base64.b64encode(b"name,secret\nAda,42\n").decode()
    body = {"source": {"kind": "uploadd", "content_base64": content}}
    r = client.post(URL, json=body)
    assert r.status_code == 422
    assert content not in r.text


def test_huge_unknown_field_name_is_not_echoed(client: TestClient) -> None:
    name = "k" * 100_000
    r = client.post(URL, json={"source": {"kind": "sample", "sample_id": "messy_survey"}, name: 1})
    assert r.status_code == 422
    assert len(r.content) < 2_000


def test_base64_longer_than_the_schema_allows_is_rejected(client: TestClient) -> None:
    data = b"x\n" + b"1\n" * ((MAX_FILE_BYTES + 2) // 2)
    assert len(base64.b64encode(data)) > MAX_BASE64_CHARS
    assert client.post(URL, json=upload(data)).status_code == 422


def test_body_limit_boundary_is_exact(client: TestClient) -> None:
    # Exactly at the limit the body reaches the app (and fails as JSON: 422); one byte more
    # is refused by the guard (413).
    at_limit = b'"' + b"x" * (MAX_REQUEST_BYTES - 2) + b'"'
    assert len(at_limit) == MAX_REQUEST_BYTES
    headers = {"content-type": "application/json"}
    assert client.post(URL, content=at_limit, headers=headers).status_code == 422
    over = b'"' + b"x" * (MAX_REQUEST_BYTES - 1) + b'"'
    assert client.post(URL, content=over, headers=headers).status_code == 413


def test_chunked_body_limit_boundary_is_exact(client: TestClient) -> None:
    headers = {"content-type": "application/json"}

    def chunks(total: int) -> Iterator[bytes]:
        body = b'"' + b"x" * (total - 2) + b'"'
        for i in range(0, total, 65_536):
            yield body[i : i + 65_536]

    assert client.post(URL, content=chunks(MAX_REQUEST_BYTES), headers=headers).status_code == 422
    over = client.post(URL, content=chunks(MAX_REQUEST_BYTES + 1), headers=headers)
    assert over.status_code == 413


def test_size_limit_response_carries_cors_headers(client: TestClient) -> None:
    # A browser on an allowed origin must be able to read the 413 message.
    r = client.post(
        URL,
        content=b" " * (MAX_REQUEST_BYTES + 1),
        headers={"content-type": "application/json", "origin": "http://localhost:3000"},
    )
    assert r.status_code == 413
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_body_over_the_limit_is_refused_before_parsing(client: TestClient) -> None:
    body = b'{"source": ' + b" " * MAX_REQUEST_BYTES + b"}"
    r = client.post(URL, content=body, headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert "larger than" in r.json()["detail"]


def test_chunked_body_over_the_limit_is_cut_off(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"source": '
        for _ in range(MAX_REQUEST_BYTES // 65_536 + 2):
            yield b" " * 65_536

    r = client.post(URL, content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_small_chunked_body_still_works(client: TestClient) -> None:
    payload = json.dumps(upload(CSV)).encode()
    r = client.post(
        URL,
        content=iter([payload[:10], payload[10:]]),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 200


def test_other_labs_are_unaffected_by_the_body_limit(client: TestClient) -> None:
    assert client.post("/api/v1/economy/solow/simulate", json={}).status_code == 200
    assert client.post("/api/v1/physics/projectile/simulate", json={}).status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def _all_rows(db: Path) -> str:
    with sqlite3.connect(db) as conn:
        return json.dumps(conn.execute("SELECT * FROM experiments").fetchall())


def test_nothing_is_logged_unless_asked(client: TestClient, tmp_path: Path) -> None:
    client.post(URL, json=upload(CSV))
    assert client.get("/api/v1/experiments").json() == []
    assert _all_rows(tmp_path / "test.sqlite3") == "[]"


def test_saved_run_stores_identity_and_counts_but_no_data(
    client: TestClient, tmp_path: Path
) -> None:
    r = client.post(
        URL,
        json=upload(
            CSV,
            options={"column_types": [{"column": 1, "type": "numeric"}]},
            save_experiment=True,
        ),
    )
    b = r.json()
    assert b["metadata"]["experiment_saved"] is True
    [record] = client.get("/api/v1/experiments").json()
    assert record["model_id"] == "quant.dataset_profile"
    assert record["inputs"] == {
        "dataset": {"sha256": hashlib.sha256(CSV).hexdigest(), "byte_size": len(CSV)},
        "options": {
            "delimiter": "comma",
            "missing_markers": ["N/A", "NA", "NaN", "None", "null"],
            "column_types": [{"column": 1, "type": "numeric"}],
        },
    }
    assert record["summary"]["rows"] == 3
    assert record["input_hash"] == b["metadata"]["input_hash"]
    stored = _all_rows(tmp_path / "test.sqlite3")
    for secret in ("city", "temp_c", "when", "Oslo", "Lima", "-3.5", "2026-01-05"):
        assert secret not in stored
    assert base64.b64encode(CSV).decode()[:20] not in stored
