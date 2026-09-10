# -*- coding: utf-8 -*-
"""FastMCP stdio server exposing Excel guard tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .guards import (
    chunk_large_workbook as _chunk_large_workbook,
    detect_corrupt_workbook as _detect_corrupt_workbook,
    detect_encoding as _detect_encoding,
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
