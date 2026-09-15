# -*- coding: utf-8 -*-
"""FastMCP stdio server exposing Excel guard tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .guards import (
    chunk_large_workbook as _chunk_large_workbook,
    detect_corrupt_workbook as _detect_corrupt_workbook,
    detect_encoding as _detect_encoding,
)
from .readers import (
    describe_workbook as _describe_workbook,
    sheet_to_markdown as _sheet_to_markdown,
)

mcp = FastMCP("excel-guard")


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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
