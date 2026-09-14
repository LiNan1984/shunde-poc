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
    """Detect whether an Excel workbook is corrupt or unreadable."""
    return _detect_corrupt_workbook(path)


@mcp.tool()
def detect_encoding(path: str) -> dict:
    """Detect CSV/text encoding, or describe xlsx ZIP/UTF-8 internals."""
    return _detect_encoding(path)


@mcp.tool()
def chunk_large_workbook(path: str, max_rows: int = 5000) -> dict:
    """Plan row-range chunks when a workbook exceeds max_rows."""
    return _chunk_large_workbook(path, max_rows=max_rows)


@mcp.tool()
def describe_workbook(path: str, preview_rows: int = 5) -> dict:
    """List sheets, row/column counts, headers, and a short preview of a workbook."""
    return _describe_workbook(path, preview_rows=preview_rows)


@mcp.tool()
def sheet_to_markdown(
    path: str, sheet: str = "", start_row: int = 1, end_row: int = 0
) -> dict:
    """Export the header plus an inclusive row range as a markdown table."""
    return _sheet_to_markdown(
        path, sheet=sheet, start_row=start_row, end_row=end_row
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
