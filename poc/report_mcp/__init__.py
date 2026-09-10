# -*- coding: utf-8 -*-
"""Report visualizer MCP package for Shunde POC (Phase 2).

Provides:
- Cross-tabulation helpers (pandas)
- Five chart renderers (matplotlib, Agg backend)
- DOCX report assembly (python-docx)
- FastMCP stdio server entry (poc.report_mcp.server)
"""

from .charts import (
    render_bar,
    render_heatmap,
    render_line,
    render_pie,
    render_scatter,
)
from .crosstab import pivot_table
from .docx_gen import render_docx_report

__all__ = [
    "pivot_table",
    "render_bar",
    "render_line",
    "render_pie",
    "render_scatter",
    "render_heatmap",
    "render_docx_report",
]
