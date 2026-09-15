# -*- coding: utf-8 -*-
"""FastMCP stdio server exposing report visualization tools."""

from __future__ import annotations

from poc.hooks.telemetry import mark_mcp_started, traced_fastmcp

from .charts import render_bar, render_heatmap, render_line, render_pie, render_scatter
from .crosstab import pivot_table
from .docx_gen import render_docx_report

mcp = traced_fastmcp("report-visualizer")


@mcp.tool()
def pivot_table_tool(
    data: list[dict],
    rows: list[str],
    cols: list[str],
    value: str,
    aggfunc: str = "sum",
    max_categories: int = 50,
) -> dict:
    """交叉表：按行/列维度对数值做透视，超限则拒绝。"""
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
    """柱状图：渲染单系列或分组柱状图为 PNG。"""
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
    """折线图：渲染单系列或多系列折线图为 PNG。"""
    return render_line(data, x, y, series=series, title=title, output_path=output_path)


@mcp.tool()
def render_pie_tool(
    data: list[dict],
    label: str,
    value: str,
    title: str = "",
    output_path: str = "",
) -> dict:
    """饼图：按标签汇总后渲染饼图为 PNG。"""
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
    """散点图：渲染散点图为 PNG，可按列着色。"""
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
    """热力图：由长表或二维矩阵渲染热力图 PNG。"""
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
    """生成 docx 报告：组装标题、章节、交叉表和嵌入的图表 PNG。"""
    return render_docx_report(
        title=title,
        sections=sections,
        output_path=output_path,
        header=header,
        footer=footer,
        style=style,
    )


def main() -> None:
    mark_mcp_started("report-visualizer")
    mcp.run()


if __name__ == "__main__":
    main()
