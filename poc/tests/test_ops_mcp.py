"""Tests for the ops telemetry sink and the ops-data MCP tools.

We exercise:
- write() creates a JSONL under the sandbox with the expected fields
- write() tolerates a missing/misconfigured workspace (no crash)
- list_telemetry_files / summarize_calls / recent_events on a fixture
- summarize_calls groups by category, status, and tool correctly
- recent_events respects category filter and limit
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from poc.hooks import telemetry
from poc.ops_mcp.server import mcp
from poc.ops_mcp.server_lib import (
    list_telemetry_files,
    recent_events,
    summarize_calls,
)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    # Reset the cached "already created" set so each test gets a fresh dir.
    telemetry._WRITTEN_DIRS.clear()
    return tmp_path


def test_write_creates_jsonl(workspace: Path) -> None:
    telemetry.write("call_volume", {"session_id": "s1", "agent_id": "a1"})

    files = list((workspace / "telemetry").rglob("ops.jsonl"))
    assert files, "telemetry JSONL not written"
    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["category"] == "call_volume"
    assert rec["session_id"] == "s1"
    assert rec["ts"].endswith("Z")


def test_write_swallows_bad_workspace(monkeypatch, capsys) -> None:
    """Telemetry must never raise; an unusable sandbox skips and logs."""
    monkeypatch.setenv("POC_WORKSPACE", "/no/such/path/__no_such__")
    telemetry._WRITTEN_DIRS.clear()
    path = telemetry.write("call_volume", {"session_id": "s1"})
    assert path is None
    assert "telemetry skip" in capsys.readouterr().err


def test_list_when_no_data(workspace: Path) -> None:
    result = list_telemetry_files()
    assert result["ok"] is True
    assert result["count"] == 0
    assert result["files"] == []


def test_summarize_after_writes(workspace: Path) -> None:
    for cat, tool in [
        ("call_volume", "tool_a"),
        ("call_volume", "tool_a"),
        ("tool_outcome", "tool_b"),
        ("tool_outcome", None),  # missing tool field — covers by_tool guard
    ]:
        rec = {"session_id": "s", "agent_id": "a", "category": cat}
        if tool is not None:
            rec["tool"] = tool
        telemetry.write(cat, rec)

    # list should see the file now
    listing = list_telemetry_files()
    assert listing["ok"] is True
    assert listing["count"] == 1

    summary = summarize_calls()
    assert summary["ok"] is True
    counts = summary["counts"]
    assert counts["total"] == 4
    assert counts["by_category"]["call_volume"] == 2
    assert counts["by_category"]["tool_outcome"] == 2
    assert counts["by_tool"]["tool_a"] == 2
    assert counts["by_tool"]["tool_b"] == 1
    # 1 event had no tool field — by_tool should not crash and should
    # only contain keys for events that had one.
    assert sum(counts["by_tool"].values()) == 3


def test_recent_events_filter_and_limit(workspace: Path) -> None:
    for i in range(5):
        telemetry.write("call_volume", {"session_id": f"s{i}"})
    for i in range(3):
        telemetry.write("tool_outcome", {"session_id": f"t{i}", "tool": "x"})

    all_recent = recent_events()
    assert all_recent["ok"] is True
    assert all_recent["count"] == 8

    only_call = recent_events(category="call_volume")
    assert only_call["count"] == 5
    assert {e["category"] for e in only_call["events"]} == {"call_volume"}

    limited = recent_events(category="call_volume", limit=2)
    assert limited["count"] == 2


def test_recent_events_rejects_bad_limit(workspace: Path) -> None:
    telemetry.write("call_volume", {"session_id": "s"})
    result = recent_events(limit=0)
    assert result["ok"] is False
    result = recent_events(limit=10_000)
    assert result["ok"] is False


def test_mcp_tools_register() -> None:
    """Three tools, same shape as the existing MCP servers."""
    tools = asyncio.run(mcp.list_tools())
    names = sorted(t.name for t in tools)
    assert names == [
        "list_telemetry_files_tool",
        "recent_events_tool",
        "summarize_calls_tool",
    ]


def test_mcp_tool_call_roundtrip(workspace: Path) -> None:
    telemetry.write("call_volume", {"session_id": "abc", "agent_id": "x"})

    async def _invoke() -> dict:
        result = await mcp.call_tool("list_telemetry_files_tool", {})
        text = result[0].text
        return json.loads(text)

    body = asyncio.run(_invoke())
    assert body["ok"] is True
    assert body["count"] == 1


def test_list_tool_writes_jsonl_when_dir_was_empty(workspace: Path) -> None:
    """The user-facing path: ops-data MCP must produce JSONL on first list."""
    assert list((workspace / "telemetry").rglob("ops.jsonl")) == []

    async def _invoke() -> dict:
        result = await mcp.call_tool("list_telemetry_files_tool", {})
        return json.loads(result[0].text)

    body = asyncio.run(_invoke())
    assert body["ok"] is True
    assert body["count"] >= 1
    files = list((workspace / "telemetry").rglob("ops.jsonl"))
    assert files, "list_telemetry_files_tool must write ops.jsonl before listing"
    recs = [
        json.loads(line)
        for line in files[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tools = {rec.get("tool") for rec in recs}
    assert any(
        isinstance(t, str) and t.endswith("list_telemetry_files_tool") for t in tools
    )

    summary = asyncio.run(
        mcp.call_tool("summarize_calls_tool", {})
    )
    summary_body = json.loads(summary[0].text)
    assert summary_body["ok"] is True
    assert summary_body["counts"]["total"] >= 1


def test_mark_mcp_started_writes_under_workspace(workspace: Path) -> None:
    path = telemetry.mark_mcp_started("ops-data")
    assert path is not None
    assert path.is_file()
    rec = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["event"] == "mcp_started"