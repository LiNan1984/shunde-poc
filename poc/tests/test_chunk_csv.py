# -*- coding: utf-8 -*-
"""Tests for the CSV/text branch of ``chunk_large_workbook``.

The xlsx path is covered by ``test_mcp_server.py`` and ``test_excel_guards.py``;
this module pins the additive CSV/.txt behaviour:

* identical return shape to the xlsx branch (needs_chunking / total_rows /
  max_sheet_rows / chunks / message, chunks with start_row/end_row/sheet),
* constant-memory newline counting (CRLF counts once, no trailing LF still
  counts as one line),
* boundary cases: empty file, single line, just over max_rows.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from poc.excel_guard_mcp.guards import chunk_large_workbook


@pytest.fixture(autouse=True)
def _sandbox_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))


def _write(path: Path, raw: bytes) -> Path:
    path.write_bytes(raw)
    return path


def test_csv_large_file_plans_contiguous_chunks(tmp_path: Path) -> None:
    # Header + 120 data rows = 121 lines, matching the xlsx fixture size.
    csv_path = _write(
        tmp_path / "big.csv",
        b"id,region,amount\n" + b"".join(f"{i},N,{i*10}\n".encode() for i in range(120)),
    )

    res = chunk_large_workbook(str(csv_path), max_rows=50)

    assert res["needs_chunking"] is True
    assert res["total_rows"] == 121
    assert res["max_sheet_rows"] == 121
    chunks = res["chunks"]
    assert len(chunks) == 3
    assert [c["start_row"] for c in chunks] == [1, 51, 101]
    assert [c["end_row"] for c in chunks] == [50, 100, 121]
    for prev, curr in zip(chunks, chunks[1:]):
        assert curr["start_row"] == prev["end_row"] + 1
    assert chunks[-1]["end_row"] == res["total_rows"]
    assert all(c["sheet"] == "big" for c in chunks)
    assert "分块" in res["message"] or "chunk" in res["message"].lower()


def test_txt_suffix_uses_same_branch(tmp_path: Path) -> None:
    txt_path = _write(
        tmp_path / "dump.txt", b"".join(f"line {i}\n".encode() for i in range(12))
    )

    res = chunk_large_workbook(str(txt_path), max_rows=5)

    assert res["needs_chunking"] is True
    assert res["total_rows"] == 12
    assert [c["start_row"] for c in res["chunks"]] == [1, 6, 11]
    assert [c["end_row"] for c in res["chunks"]] == [5, 10, 12]
    assert all(c["sheet"] == "dump" for c in res["chunks"])


def test_csv_empty_file_reports_zero_rows(tmp_path: Path) -> None:
    empty = _write(tmp_path / "empty.csv", b"")

    res = chunk_large_workbook(str(empty), max_rows=10)

    assert res["needs_chunking"] is False
    assert res["total_rows"] == 0
    assert res["max_sheet_rows"] == 0
    assert res["chunks"] == []
    assert "无需分块" in res["message"] or "No chunking" in res["message"]


def test_csv_single_line_with_lf_boundary(tmp_path: Path) -> None:
    one = _write(tmp_path / "one.csv", b"a,b,c\n")

    res = chunk_large_workbook(str(one), max_rows=1)

    # Exactly at the limit (1 <= 1): no chunking.
    assert res["needs_chunking"] is False
    assert res["total_rows"] == 1
    assert res["chunks"] == []


def test_csv_single_line_without_trailing_lf_boundary(tmp_path: Path) -> None:
    one = _write(tmp_path / "one.csv", b"a,b,c")

    res = chunk_large_workbook(str(one))

    # A final fragment without LF is still one row.
    assert res["needs_chunking"] is False
    assert res["total_rows"] == 1
    assert res["chunks"] == []


def test_csv_two_rows_no_trailing_lf_exceeds_max(tmp_path: Path) -> None:
    two = _write(tmp_path / "two.csv", b"a,b\n1,2")

    res = chunk_large_workbook(str(two), max_rows=1)

    assert res["needs_chunking"] is True
    assert res["total_rows"] == 2
    assert res["chunks"] == [
        {"start_row": 1, "end_row": 1, "sheet": "two"},
        {"start_row": 2, "end_row": 2, "sheet": "two"},
    ]


def test_csv_crlf_counts_each_line_once(tmp_path: Path) -> None:
    crlf = _write(
        tmp_path / "crlf.csv",
        b"h1,h2\r\n1,a\r\n2,b\r\n3,c\r\n",
    )

    res = chunk_large_workbook(str(crlf), max_rows=2)

    assert res["needs_chunking"] is True
    assert res["total_rows"] == 4  # 4 lines, not 8, not 7
    assert [c["start_row"] for c in res["chunks"]] == [1, 3]
    assert [c["end_row"] for c in res["chunks"]] == [2, 4]


def test_csv_small_file_uses_default_max_rows(tmp_path: Path) -> None:
    small = _write(tmp_path / "small.csv", b"id\n" + b"".join(b"1\n" for _ in range(5)))

    res = chunk_large_workbook(str(small))

    assert res["needs_chunking"] is False
    assert res["total_rows"] == 6
    assert res["chunks"] == []
    # Message format must stay identical to the xlsx branch (downstream tests
    # and Skill docs rely on max_rows=5000 being shown).
    assert "无需分块" in res["message"] or "No chunking" in res["message"]
    assert "max_rows=5000" in res["message"]


def test_csv_rejects_max_rows_below_one(tmp_path: Path) -> None:
    csv_path = _write(tmp_path / "x.csv", b"a\n")

    res = chunk_large_workbook(str(csv_path), max_rows=0)

    assert res["needs_chunking"] is False
    assert res["chunks"] == []
    assert "max_rows" in res["message"]


def test_csv_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "absent.csv"

    res = chunk_large_workbook(str(missing), max_rows=10)

    assert res["needs_chunking"] is False
    assert res["total_rows"] == 0
    assert res["chunks"] == []
    assert "不存在" in res["message"] or "not found" in res["message"].lower()


def test_csv_outside_workspace_denied() -> None:
    fd, raw_path = tempfile.mkstemp(prefix="chunk-csv-outside-", suffix=".csv")
    try:
        os.write(fd, b"a\n")
    finally:
        os.close(fd)
    try:
        res = chunk_large_workbook(raw_path, max_rows=1)

        assert res["needs_chunking"] is False
        assert res["total_rows"] == 0
        assert res["chunks"] == []
        assert "路径越界" in res["message"]
    finally:
        Path(raw_path).unlink(missing_ok=True)


def test_csv_chunking_is_streaming_for_large_file(tmp_path: Path) -> None:
    """A file larger than one read buffer must still count correctly.

    3000 rows of ~600 bytes ≈ 1.8 MiB > the 1 MiB read buffer; if the branch
    ever regressed to a single read(), counts would silently truncate.
    """
    big = tmp_path / "multi_buffer.csv"
    line = ("x" * 590 + "\n").encode()
    with open(big, "wb") as fh:
        for _ in range(3000):
            fh.write(line)

    res = chunk_large_workbook(str(big), max_rows=1000)

    assert res["needs_chunking"] is True
    assert res["total_rows"] == 3000
    assert len(res["chunks"]) == 3
    assert res["chunks"][-1]["end_row"] == 3000
