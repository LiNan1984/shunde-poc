"""One-command demo: produce a 1-crosstab + 5-chart DOCX from sample data.

Usage:
    source .venv/bin/activate
    python scripts/report_demo.py

What it does:
    1. Loads poc/fixtures/report_demo/quarterly_business.json.
    2. Renders 5 PNG charts (bar/line/pie/scatter/heatmap) and 1 crosstab
       via the report-visualizer MCP tool functions.
    3. Assembles everything into a single DOCX with title + sections.

Outputs (relative to repo root, inside the POC workspace sandbox):
    poc/fixtures/report_demo/out/charts/<name>.png
    poc/fixtures/report_demo/out/report.docx

This script is the "按一个键就能演示" deliverable for 任务 A.
It does NOT require QwenPaw; the demo proves the underlying MCP tool
functions render correctly end-to-end.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make sure we import the in-repo package, not any system install.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Sandbox: the workspace root must be the repo (or a parent of output paths).
# POC_WORKSPACE defaults to repo root when unset, so default works.
os.environ.setdefault("POC_WORKSPACE", str(REPO_ROOT))

from poc.report_mcp import charts as charts_mod  # noqa: E402
from poc.report_mcp.crosstab import pivot_table  # noqa: E402
from poc.report_mcp.docx_gen import render_docx_report  # noqa: E402

FIXTURE = REPO_ROOT / "poc" / "fixtures" / "report_demo" / "quarterly_business.json"
OUT = REPO_ROOT / "poc" / "fixtures" / "report_demo" / "out"
CHARTS = OUT / "charts"


def _resolve_under_sandbox(p: Path) -> Path:
    """Sanity-check that the output is inside the sandbox root."""
    root = Path(os.environ["POC_WORKSPACE"]).resolve()
    resolved = p.resolve()
    if not resolved.is_relative_to(root):
        raise SystemExit(f"refusing to write outside workspace: {resolved}")
    return resolved


def main() -> int:
    CHARTS.mkdir(parents=True, exist_ok=True)
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]

    # 1. Bar: 各支行三类产品总金额 (grouped by branch × product)
    bar_path = _resolve_under_sandbox(CHARTS / "bar_branch_product.png")
    r = charts_mod.render_bar(records, x="branch", y="amount", series="product",
                              title="各支行三季度分产品金额 / Branch × Product",
                              output_path=str(bar_path))
    assert r["ok"], r

    # 2. Line: 各支行客户数走势 — 这里简化为按 quarter 单点
    line_path = _resolve_under_sandbox(CHARTS / "line_branch_customers.png")
    r = charts_mod.render_line(records, x="branch", y="customers", series="product",
                               title="各支行三季度客户数 / Customers by Branch",
                               output_path=str(line_path))
    assert r["ok"], r

    # 3. Pie: 区域产品金额构成
    pie_path = _resolve_under_sandbox(CHARTS / "pie_region_amount.png")
    r = charts_mod.render_pie(records, label="region", value="amount",
                             title="区域金额构成 / Regional Amount Mix",
                             output_path=str(pie_path))
    assert r["ok"], r

    # 4. Scatter: 客户数 vs 金额（按区域着色）
    scatter_path = _resolve_under_sandbox(CHARTS / "scatter_customers_amount.png")
    r = charts_mod.render_scatter(records, x="customers", y="amount", color="region",
                                  title="客户数 vs 金额 / Customers vs Amount",
                                  output_path=str(scatter_path))
    assert r["ok"], r

    # 5. Heatmap: 支行 × 产品的金额矩阵（long form）
    heatmap_path = _resolve_under_sandbox(CHARTS / "heatmap_branch_product.png")
    r = charts_mod.render_heatmap(data=records, row="branch", col="product", value="amount",
                                  title="支行×产品 金额热力 / Branch × Product Heatmap",
                                  output_path=str(heatmap_path))
    assert r["ok"], r

    # Crosstab: 区域 × 产品 的金额合计
    cross = pivot_table(records, rows=["region"], cols=["product"],
                        value="amount", aggfunc="sum")
    assert cross["ok"], cross
    cross_table = {
        "headers": ["region", *cross["cols"]],
        "rows": [[r.get("region", r.get("__row__", "")), *(r.get(c, 0) for c in cross["cols"])] for r in cross["table"]],
    }

    # DOCX
    docx_path = _resolve_under_sandbox(OUT / "report.docx")
    sections = [
        {
            "heading": "一、各支行分产品金额（柱状图）",
            "paragraphs": ["2025 年第三季度各支行三类零售产品的合计金额对比。"],
            "charts": [str(bar_path)],
        },
        {
            "heading": "二、各支行客户数走势（折线图）",
            "paragraphs": ["同期客户数量分布，可用于评估网点覆盖。"],
            "charts": [str(line_path)],
        },
        {
            "heading": "三、区域金额构成（饼图）",
            "paragraphs": ["三个区域在全辖金额中的占比。"],
            "charts": [str(pie_path)],
        },
        {
            "heading": "四、客户数 vs 金额（散点图）",
            "paragraphs": ["按区域着色，便于识别规模与价值的关系。"],
            "charts": [str(scatter_path)],
        },
        {
            "heading": "五、支行×产品金额（热力图）",
            "paragraphs": ["以颜色深浅表示金额量级。"],
            "charts": [str(heatmap_path)],
        },
        {
            "heading": "六、区域×产品 金额交叉表",
            "paragraphs": ["金额合计，单位：元。"],
            "table": cross_table,
        },
    ]
    r = render_docx_report(
        title="顺德分行 2025Q3 零售业务可视化报告",
        sections=sections,
        output_path=str(docx_path),
        header="顺德银行 POC 演示报告",
        footer="本页由 report-visualizer MCP 一键生成",
    )
    assert r["ok"], r

    print(json.dumps({
        "ok": True,
        "charts": [str(p) for p in [bar_path, line_path, pie_path, scatter_path, heatmap_path]],
        "docx": str(docx_path),
        "crosstab_rows": len(cross["rows"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())