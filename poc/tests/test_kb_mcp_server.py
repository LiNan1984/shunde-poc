# -*- coding: utf-8 -*-
"""FastMCP registry + call_tool tests for the knowledge-base server."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from openpyxl import Workbook

from poc.kb_mcp.fixtures import TOKENS, write_native_text_pdf
from poc.kb_mcp.server import main, mcp

EXPECTED_TOOLS = {
    "parse_document",
    "ingest_document",
    "ingest_spreadsheet",
    "search_knowledge",
    "answer_knowledge",
    "analyze_page",
}
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("POC_LOAD_SECRETS", "0")
    monkeypatch.delenv("MINERU_ENDPOINT", raising=False)
    monkeypatch.delenv("POC_EMBEDDING_URL", raising=False)
    monkeypatch.delenv("POC_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("POC_CHAT_MODEL", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ELASTICSEARCH_URL", raising=False)
    monkeypatch.delenv("MYSQL_URL", raising=False)
    monkeypatch.delenv("GALASYBASE_URL", raising=False)
    return tmp_path


def _list_tools() -> dict[str, Any]:
    tools = asyncio.run(mcp.list_tools())
    return {tool.name: tool for tool in tools}


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = asyncio.run(mcp.call_tool(name, arguments))
    if isinstance(result, dict):
        return result
    assert result, f"tool {name!r} returned no content blocks"
    text = getattr(result[0], "text", None)
    assert text is not None, f"tool {name!r} returned non-text block: {result[0]!r}"
    payload = json.loads(text)
    assert isinstance(payload, dict)
    return payload


def test_server_registers_exactly_six_tools() -> None:
    tools = _list_tools()
    assert set(tools) == EXPECTED_TOOLS
    assert len(tools) == 6


def test_server_name_is_kb_qa() -> None:
    assert mcp.name == "kb-qa"


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOLS))
def test_registered_tools_have_descriptions(tool_name: str) -> None:
    desc = _list_tools()[tool_name].description
    assert desc and desc.strip()


def test_mcp_ingest_then_search_returns_real_chunk_text(tmp_path: Path) -> None:
    pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
    ingested = _call_tool(
        "ingest_document",
        {"path": str(pdf), "doc_id": "credit-policy"},
    )
    assert ingested["ok"] is True
    assert ingested["n_chunks"] >= 1
    hits = _call_tool(
        "search_knowledge",
        {"query": TOKENS["alpha"], "doc_id": "credit-policy"},
    )
    assert hits["ok"] is True
    assert hits["hits"]
    assert any(TOKENS["alpha"] in (h.get("text") or "") for h in hits["hits"])
    assert hits["hits"][0]["page"]
    answered = _call_tool(
        "answer_knowledge",
        {"query": "概括这份信贷文档的总体要点", "doc_id": "credit-policy"},
    )
    assert answered["ok"] is True
    assert answered["kind"] == "overview"
    assert TOKENS["alpha"] in answered["answer"]


def test_mcp_parse_document_tool(tmp_path: Path) -> None:
    pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
    parsed = _call_tool("parse_document", {"path": str(pdf), "doc_id": "credit-policy"})
    assert parsed["ok"] is True
    assert parsed["chunks"]
    assert any(TOKENS["beta"] in (c.get("text") or "") for c in parsed["chunks"])


def test_main_is_callable_and_invokes_mcp_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple, dict]] = []

    def _fake_run(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(mcp, "run", _fake_run)
    main()
    assert calls == [((), {})]


def test_importing_server_module_does_not_start_stdio() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from poc.kb_mcp.server import mcp, main; "
            "assert mcp.name == 'kb-qa'; "
            "assert callable(main); "
            "print('imported-ok')",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    assert "imported-ok" in completed.stdout


def test_mcp_ingest_spreadsheet_then_search_identifies_file_not_distractor(
    tmp_path: Path,
) -> None:
    shunde = tmp_path / "shunde_ledger.xlsx"
    other = tmp_path / "jiaozhou_ledger.xlsx"
    wb_a = Workbook()
    ws_a = wb_a.active
    ws_a.title = "顺德收支台账"
    ws_a.append(["交易日期", "金额", "顺德网点ShundeMetaTokenX9"])
    ws_a.append(["20260601", 100, "顺德容桂支行"])
    for i in range(18):
        ws_a.append([f"202606{i+2:02d}", i, "padding"])
    ws_a.append(["20260620", 999, "DEEP_CELL_TOKEN_NEVER_INDEX_7f3a"])
    wb_a.save(shunde)
    wb_b = Workbook()
    ws_b = wb_b.active
    ws_b.title = "胶州收支台账"
    ws_b.append(["交易日期", "金额", "胶州网点JiaozhouMetaTokenY2"])
    ws_b.append(["20260601", 50, "胶州铺集支行"])
    wb_b.save(other)

    ingested_a = _call_tool(
        "ingest_spreadsheet",
        {"path": str(shunde), "doc_id": "shunde-ledger", "sample_rows": 5},
    )
    ingested_b = _call_tool(
        "ingest_spreadsheet",
        {"path": str(other), "doc_id": "jiaozhou-ledger", "sample_rows": 5},
    )
    assert ingested_a["ok"] is True
    assert ingested_b["ok"] is True

    hits = _call_tool(
        "search_knowledge",
        {"query": "ShundeMetaTokenX9", "k": 8},
    )
    assert hits["ok"] is True
    assert hits["hits"]
    top = hits["hits"][0]
    blob = " ".join(
        [
            str(top.get("doc_id") or ""),
            str(top.get("text") or ""),
            str(top.get("chapter") or ""),
        ]
    )
    assert "shunde-ledger" in blob or "顺德" in blob
    assert "jiaozhou-ledger" not in (top.get("doc_id") or "")
    indexed = " ".join(h.get("text") or "" for h in hits["hits"])
    assert "DEEP_CELL_TOKEN_NEVER_INDEX_7f3a" not in indexed


def test_stdio_entrypoint_exits_on_stdin_eof() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    completed = subprocess.run(
        [sys.executable, "-m", "poc.kb_mcp"],
        cwd=str(REPO_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
