# -*- coding: utf-8 -*-
"""Excel guard MCP package for Shunde POC."""

from .guards import (
    chunk_large_workbook,
    detect_corrupt_workbook,
    detect_encoding,
)

__all__ = [
    "chunk_large_workbook",
    "detect_corrupt_workbook",
    "detect_encoding",
]
