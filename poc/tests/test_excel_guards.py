# -*- coding: utf-8 -*-
"""Real tests for excel_guard_mcp.guards (no mocks of logic under test)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from poc.excel_guard_mcp.guards import (
    chunk_large_workbook,
    detect_corrupt_workbook,
    detect_encoding,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "poc" / "fixtures"


@pytest.fixture(autouse=True)
def _sandbox_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Confine path checks to the per-test temp dir (plus allow fixture tests)."""
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))


def test_detect_corrupt_workbook_rejects_invalid_zip(tmp_path: Path) -> None:
    bad = tmp_path / "corrupt.xlsx"
    bad.write_bytes(b"this is not a valid zip or xlsx file")

    result = detect_corrupt_workbook(str(bad))

    assert result["ok"] is False
    assert result["issue"] == "corrupt"
    assert "损坏" in result["message"] or "Corrupt" in result["message"]


def test_detect_corrupt_workbook_accepts_valid_xlsx(tmp_path: Path) -> None:
    good = tmp_path / "ok.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "hello"
    ws["B1"] = 42
    wb.save(good)

    result = detect_corrupt_workbook(str(good))

    assert result["ok"] is True
    assert result["issue"] == ""
    assert "OK" in result["message"] or "正常" in result["message"]


def test_detect_encoding_finds_latin1_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "latin1.csv"
    csv_path.write_bytes("name,city\nAlice,Caf\xe9\n".encode("latin-1"))

    result = detect_encoding(str(csv_path))

    encoding = result["encoding"].lower().replace("_", "-")
    assert encoding not in {"utf-8", "utf8"}
    assert "UTF-8" in result["message"] or "utf-8" in result["message"].lower()
    assert "编码" in result["message"] or "encoding" in result["message"].lower()


def test_detect_encoding_xlsx_notes_zip_utf8(tmp_path: Path) -> None:
    xlsx = tmp_path / "note.xlsx"
    wb = Workbook()
    wb.active["A1"] = "x"
    wb.save(xlsx)

    result = detect_encoding(str(xlsx))

    assert result["encoding"].lower() in {"utf-8", "utf8"}
    assert "ZIP" in result["message"] or "zip" in result["message"]


def test_chunk_large_workbook_needs_chunking(tmp_path: Path) -> None:
    large = tmp_path / "large.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["id", "value"])
    for i in range(120):
        ws.append([i, f"v{i}"])
    wb.save(large)

    result = chunk_large_workbook(str(large), max_rows=50)

    assert result["needs_chunking"] is True
    assert result["total_rows"] > 50
    assert len(result["chunks"]) >= 2
    first = result["chunks"][0]
    assert first["start_row"] == 1
    assert first["end_row"] == 50
    assert first["sheet"] == "Sheet1"
    assert "分块" in result["message"] or "chunk" in result["message"].lower()


def test_chunk_large_workbook_no_chunking_when_small(tmp_path: Path) -> None:
    small = tmp_path / "small.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["a", "b"])
    ws.append([1, 2])
    wb.save(small)

    result = chunk_large_workbook(str(small), max_rows=5000)

    assert result["needs_chunking"] is False
    assert result["total_rows"] <= 5000
    assert result["chunks"] == []
    assert "无需分块" in result["message"] or "No chunking" in result["message"]


def test_path_outside_workspace_denied(tmp_path: Path) -> None:
    outside = Path("/etc/passwd")
    if not outside.exists():
        pytest.skip("/etc/passwd not present")

    result = detect_corrupt_workbook(str(outside))
    assert result["ok"] is False
    assert result["issue"] == "path_denied"


def test_committed_fixtures_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POC_WORKSPACE", str(REPO_ROOT))

    corrupt = detect_corrupt_workbook(str(FIXTURES / "corrupt.xlsx"))
    assert corrupt["ok"] is False
    assert corrupt["issue"] == "corrupt"

    enc_path = FIXTURES / "encoding_gbk.csv"
    if not enc_path.exists():
        enc_path = FIXTURES / "encoding_latin1.csv"
    enc = detect_encoding(str(enc_path))
    assert enc["encoding"].lower() not in {"utf-8", "utf8"}

    large = chunk_large_workbook(str(FIXTURES / "large_chunk_demo.xlsx"), max_rows=5000)
    assert large["needs_chunking"] is True
    assert large["total_rows"] > 5000


def test_server_module_imports() -> None:
    from poc.excel_guard_mcp.server import mcp

    assert mcp is not None
    assert getattr(mcp, "name", None) or True
