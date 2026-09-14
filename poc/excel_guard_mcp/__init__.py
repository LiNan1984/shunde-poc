# -*- coding: utf-8 -*-
"""Excel guard MCP package for Shunde POC."""

from .guards import (
    chunk_large_workbook,
    detect_corrupt_workbook,
    detect_encoding,
)
from .readers import describe_workbook, sheet_to_markdown

__all__ = [
    "chunk_large_workbook",
    "describe_workbook",
    "detect_corrupt_workbook",
    "detect_encoding",
    "sheet_to_markdown",
]
