# -*- coding: utf-8 -*-
"""FastMCP stdio server for ops data Q&A (telemetry)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .server_lib import list_telemetry_files, recent_events, summarize_calls

mcp = FastMCP("ops-data")


@mcp.tool()
def list_telemetry_files_tool() -> dict:
    """列出埋点文件：列出 POC_WORKSPACE/telemetry 下所有 JSONL。"""
    return list_telemetry_files()


@mcp.tool()
def summarize_calls_tool(path: str | None = None) -> dict:
    """汇总调用量：按类别/状态/工具统计 JSONL 次数。"""
    return summarize_calls(path)


@mcp.tool()
def recent_events_tool(
    category: str | None = None,
    limit: int = 50,
    path: str | None = None,
) -> dict:
    """最近事件：返回最近 N 条埋点，可按类别过滤。"""
    return recent_events(category=category, limit=limit, path=path)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()