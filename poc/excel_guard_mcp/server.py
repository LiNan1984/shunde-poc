# -*- coding: utf-8 -*-
"""FastMCP stdio server exposing Excel guard tools."""

from __future__ import annotations

from poc.hooks.telemetry import mark_mcp_started, traced_fastmcp

from .guards import (
    chunk_large_workbook as _chunk_large_workbook,
    detect_corrupt_workbook as _detect_corrupt_workbook,
    detect_encoding as _detect_encoding,
)
from .officecli_bridge import (
    edit_workbook as _edit_workbook,
    inspect_workbook as _inspect_workbook,
    render_workbook as _render_workbook,
    validate_workbook as _validate_workbook_cli,
)
from .readers import (
    describe_workbook as _describe_workbook,
    sheet_to_markdown as _sheet_to_markdown,
)

mcp = traced_fastmcp("excel-guard")


@mcp.tool()
def detect_corrupt_workbook(path: str) -> dict:
    """检测损坏表：判断 Excel 是否损坏或无法打开。"""
    return _detect_corrupt_workbook(path)


@mcp.tool()
def detect_encoding(path: str) -> dict:
    """识别编码：检测 CSV/文本表编码，或说明 xlsx 内部编码。"""
    return _detect_encoding(path)


@mcp.tool()
def chunk_large_workbook(path: str, max_rows: int = 5000) -> dict:
    """超大表分块：行数超过阈值时给出分块区间，避免整表载入。"""
    return _chunk_large_workbook(path, max_rows=max_rows)


@mcp.tool()
def describe_workbook(path: str, preview_rows: int = 5) -> dict:
    """描述表结构：列出 sheet、行列数、表头投票结果和短预览。"""
    return _describe_workbook(path, preview_rows=preview_rows)


@mcp.tool()
def sheet_to_markdown(
    path: str, sheet: str = "", start_row: int = 1, end_row: int = 0
) -> dict:
    """表转 Markdown：导出表头加指定行区间，供小范围预览。"""
    return _sheet_to_markdown(
        path, sheet=sheet, start_row=start_row, end_row=end_row
    )


@mcp.tool()
def edit_workbook(path: str, commands: list[dict]) -> dict:
    """守卫写回：officecli 批量编辑（add/set/remove/move/swap），写前预检、写后 validate+公式审计。"""
    return _edit_workbook(path, commands)


@mcp.tool()
def inspect_workbook(path: str, node_path: str = "/", depth: int = 1) -> dict:
    """结构化读取：officecli get 读取单元格样式/格式细节，补充 describe_workbook 看不到的信息。"""
    return _inspect_workbook(path, node_path=node_path, depth=depth)


@mcp.tool()
def validate_workbook(path: str) -> dict:
    """OpenXML 校验：officecli validate 检查工作簿 schema 合法性。"""
    return _validate_workbook_cli(path)


@mcp.tool()
def render_workbook(path: str, out_path: str = "") -> dict:
    """渲染成图：officecli 截图为 PNG（默认写在工作簿旁），供 agent 目检成品。"""
    return _render_workbook(path, out_path=out_path)


def main() -> None:
    mark_mcp_started("excel-guard")
    mcp.run()


if __name__ == "__main__":
    main()
