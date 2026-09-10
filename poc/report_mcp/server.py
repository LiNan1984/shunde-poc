# -*- coding: utf-8 -*-
"""FastMCP stdio server exposing report visualization tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .charts import render_bar, render_heatmap, render_line, render_pie, render_scatter
from .crosstab import pivot_table
from .docx_gen import render_docx_report

mcp = FastMCP("report-visualizer")


@mcp.tool()
def pivot_table_tool(
    data: list[dict],
    rows: list[str],
    cols: list[str],
    value: str,
    aggfunc: str = "sum",
    max_categories: int = 50,
) -> dict:
    """Build a cross-tabulation / pivot table from tabular data."""
    return pivot_table(data, rows, cols, value, aggfunc, max_categories)


@mcp.tool()
def render_bar_tool(
    data: list[dict],
    x: str,
    y: str,
    series: str | None = None,
    title: str = "",
    output_path: str = "",
) -> dict:
    """Render a bar chart (single or grouped) to PNG."""
    return render_bar(data, x, y, series=series, title=title, output_path=output_path)


@mcp.tool()
def render_line_tool(
    data: list[dict],
    x: str,
    y: str,
    series: str | None = None,
    title: str = "",
    output_path: str = "",
) -> dict:
    """Render a line chart (single or multi-series) to PNG."""
    return render_line(data, x, y, series=series, title=title, output_path=output_path)


@mcp.tool()
def render_pie_tool(
    data: list[dict],
    label: str,
    value: str,
    title: str = "",
    output_path: str = "",
) -> dict:
    """Render a pie chart to PNG (values summed by label)."""
    return render_pie(data, label, value, title=title, output_path=output_path)


@mcp.tool()
def render_scatter_tool(
    data: list[dict],
    x: str,
    y: str,
    color: str | None = None,
    title: str = "",
    output_path: str = "",
) -> dict:
    """Render a scatter plot to PNG (optionally colored by a column)."""
    return render_scatter(data, x, y, color=color, title=title, output_path=output_path)


@mcp.tool()
def render_heatmap_tool(
    data: list[dict] | None = None,
    row: str | None = None,
    col: str | None = None,
    value: str | None = None,
    x_labels: list[str] | None = None,
    y_labels: list[str] | None = None,
    matrix: list[list[float]] | None = None,
    title: str = "",
    output_path: str = "",
) -> dict:
    """Render a heatmap to PNG from long-form data or a 2D matrix."""
    return render_heatmap(
        data=data,
        row=row,
        col=col,
        value=value,
        x_labels=x_labels,
        y_labels=y_labels,
        matrix=matrix,
        title=title,
        output_path=output_path,
    )


@mcp.tool()
def render_docx_report_tool(
    title: str,
    sections: list[dict],
    output_path: str,
    header: str = "",
    footer: str = "",
    style: str = "default",
) -> dict:
    """Build a DOCX report with title, sections, tables, and embedded chart PNGs."""
    return render_docx_report(
        title=title,
        sections=sections,
        output_path=output_path,
        header=header,
        footer=footer,
        style=style,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
