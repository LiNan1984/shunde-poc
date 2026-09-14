# -*- coding: utf-8 -*-
"""analyze_page（看图作答）tests: all offline via monkeypatched HTTP + stores."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from poc.kb_mcp.server import mcp
from poc.kb_mcp import vision
from poc.kb_mcp.vision import analyze_page

FAKE_ANSWER = "图中表格显示 2026 年 6 月末余额为 1,234.56 元（原样引用）"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-payload" * 4


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("POC_LOAD_SECRETS", "0")
    for key in (
        "POC_CHAT_URL",
        "POC_CHAT_MODEL",
        "POC_ALIYUN_API_KEY",
        "POC_CHAT_API_KEY",
        "POC_VISION_MODEL",
        "POC_EMBEDDING_URL",
        "POC_EMBEDDING_API_KEY",
        "ARK_API_KEY",
        "ARK_BASE_URL",
        "QWENPAW_SECRET_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


class _FakeRelational:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks = chunks

    def list_chunks(self, **filters: Any) -> list[dict[str, Any]]:
        doc_id = str(filters.get("doc_id") or "")
        page_from = int(filters.get("page_from") or 0)
        page_to = int(filters.get("page_to") or 0)
        out = []
        for chunk in self._chunks:
            if doc_id and chunk.get("doc_id") != doc_id:
                continue
            page = int(chunk.get("page") or 0)
            if page_from > 0 and page < page_from:
                continue
            if page_to > 0 and page > page_to:
                continue
            out.append(chunk)
        return out


class _FakeBundle:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.relational = _FakeRelational(chunks)


def _write_png(tmp_path: Path, name: str = "page-3.png") -> Path:
    png = tmp_path / name
    png.write_bytes(PNG_BYTES)
    return png


def _configure(monkeypatch: pytest.MonkeyPatch, model: str = "qwen3-vl-test") -> None:
    monkeypatch.setenv("POC_CHAT_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("POC_ALIYUN_API_KEY", "test-key")
    monkeypatch.setenv("POC_VISION_MODEL", model)


def _patch_chat(
    monkeypatch: pytest.MonkeyPatch, answer: str = FAKE_ANSWER
) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def _fake_chat_completion(messages: list[dict[str, Any]], **kwargs: Any) -> str:
        seen["messages"] = messages
        seen["kwargs"] = kwargs
        return answer

    monkeypatch.setattr(vision, "chat_completion", _fake_chat_completion)
    return seen


def test_analyze_page_success_via_doc_id_and_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = _write_png(tmp_path)
    _configure(monkeypatch, model="qwen3-vl-test")
    seen = _patch_chat(monkeypatch)
    monkeypatch.setattr(
        vision,
        "open_stores",
        lambda: _FakeBundle([
            {"chunk_id": "c1", "doc_id": "pricing", "page": 3, "kind": "table",
             "page_image": str(png)},
        ]),
    )

    result = analyze_page(doc_id="pricing", page=3, query="6 月末余额是多少")

    assert result["ok"] is True
    assert result["answer"] == FAKE_ANSWER
    assert result["doc_id"] == "pricing"
    assert result["page"] == 3
    assert result["page_image"] == str(png)
    assert result["model"] == "qwen3-vl-test"
    assert result["query"] == "6 月末余额是多少"
    messages = seen["messages"]
    assert messages[0]["role"] == "system"
    assert "原样引用" in messages[0]["content"]
    user_content = messages[1]["content"]
    assert user_content[0]["type"] == "image_url"
    assert user_content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "6 月末余额是多少" in user_content[1]["text"]
    kwargs = seen["kwargs"]
    assert kwargs["model"] == "qwen3-vl-test"
    assert kwargs["temperature"] == 0.1
    assert kwargs["max_tokens"] == 800
    assert kwargs["timeout"] == 120.0


def test_analyze_page_success_via_workspace_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = _write_png(tmp_path, "manual-page.png")
    _configure(monkeypatch)
    _patch_chat(monkeypatch)

    result = analyze_page(path=str(png), query="图中第一行的金额")

    assert result["ok"] is True
    assert result["answer"] == FAKE_ANSWER
    assert result["page_image"] == str(png)
    assert result["doc_id"] == ""
    assert result["page"] == 0


def test_analyze_page_empty_query_is_rejected(tmp_path: Path) -> None:
    result = analyze_page(doc_id="pricing", page=3, query="   ")
    assert result["ok"] is False
    assert result["error_type"] == "empty_input"


def test_analyze_page_rejects_path_outside_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    result = analyze_page(path="/etc/hostname", query="图里有什么")
    assert result["ok"] is False
    assert result["error_type"] == "path_denied"


def test_analyze_page_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    result = analyze_page(path=str(tmp_path / "no-such-page.png"), query="图里有什么")
    assert result["ok"] is False
    assert result["error_type"] == "missing"


def test_analyze_page_no_page_image_in_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    _patch_chat(monkeypatch)
    monkeypatch.setattr(
        vision,
        "open_stores",
        lambda: _FakeBundle([
            {"chunk_id": "c1", "doc_id": "pricing", "page": 3, "kind": "table",
             "page_image": ""},
        ]),
    )

    result = analyze_page(doc_id="pricing", page=3, query="6 月末余额是多少")

    assert result["ok"] is False
    assert result["error_type"] == "missing"


def test_analyze_page_no_locator(tmp_path: Path) -> None:
    result = analyze_page(query="图里有什么")
    assert result["ok"] is False
    assert result["error_type"] == "empty_input"


def test_analyze_page_unconfigured_vision_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = _write_png(tmp_path)
    _patch_chat(monkeypatch)

    result = analyze_page(path=str(png), query="图中第一行的金额")

    assert result["ok"] is False
    assert result["error_type"] == "config"
    for needle in ("POC_CHAT_URL", "POC_ALIYUN_API_KEY", "POC_VISION_MODEL",
                   "middleware.env"):
        assert needle in result["message"]


def test_analyze_page_chat_failure_returns_network_not_fabricated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = _write_png(tmp_path)
    _configure(monkeypatch)
    _patch_chat(monkeypatch, answer="")

    result = analyze_page(path=str(png), query="图中第一行的金额")

    assert result["ok"] is False
    assert result["error_type"] == "network"
    assert not result.get("answer")


def _list_tools() -> dict[str, Any]:
    tools = asyncio.run(mcp.list_tools())
    return {tool.name: tool for tool in tools}


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = asyncio.run(mcp.call_tool(name, arguments))
    if isinstance(result, dict):
        return result
    assert result, f"tool {name!r} returned no content blocks"
    text = getattr(result[0], "text", None)
    assert text is not None
    payload = json.loads(text)
    assert isinstance(payload, dict)
    return payload


def test_server_registers_analyze_page_with_description() -> None:
    tools = _list_tools()
    assert "analyze_page" in tools
    desc = tools["analyze_page"].description
    assert desc and "看图" in desc


def test_server_analyze_page_tool_end_to_end_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = _write_png(tmp_path)
    _configure(monkeypatch)
    _patch_chat(monkeypatch)
    monkeypatch.setattr(
        vision,
        "open_stores",
        lambda: _FakeBundle([
            {"chunk_id": "c1", "doc_id": "pricing", "page": 3, "kind": "image",
             "page_image": str(png)},
        ]),
    )

    result = _call_tool(
        "analyze_page",
        {"doc_id": "pricing", "page": 3, "query": "图中饼图哪一块占比最大"},
    )

    assert result["ok"] is True
    assert result["answer"] == FAKE_ANSWER
    assert result["page"] == 3
    assert result["page_image"] == str(png)
