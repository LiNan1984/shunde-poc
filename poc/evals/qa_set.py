# -*- coding: utf-8 -*-
"""Deterministic Excel QA fixtures and golden question pairs.

Every workbook is written from the same in-memory lists that produce the
expected answers, so a golden answer can never drift from the data. The set
deliberately covers the real-world failure modes: clean detail sheets,
multi-level merged headers, uncached formula columns, and non-UTF-8 CSV.

This is the measurement layer the POC was missing: agent answers go to
``score_answers`` and come back as an accuracy number, so any capability
change can be judged instead of argued.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook

QA_SET_VERSION = "1.0"

# --- deterministic source data (single source of truth) -----------------------

_SALES_ROWS: list[tuple[str, str, str, float]] = []
for _i in range(10):
    _day = 5 + _i
    _SALES_ROWS.extend(
        [
            (f"2024-01-{_day:02d}", "顺德", "容桂支行", 12000 + _i * 137),
            (f"2024-01-{_day + 7:02d}", "广州", "天河支行", 9800 + _i * 211),
            (f"2024-01-{_day + 14:02d}", "佛山", "禅城支行", 15300 + _i * 89),
            (f"2024-02-{_day - 3:02d}", "顺德", "大良支行", 8600 + _i * 173),
        ]
    )
del _i, _day

_SUMMARY_ROWS: list[tuple[str, float, int, float, int]] = [
    # 地区, 2024销售额, 2024订单数, 2025销售额, 2025订单数
    ("顺德", 1_250_000.50, 3210, 1_480_200.75, 3688),
    ("广州", 2_130_400.25, 5902, 2_305_100.00, 6120),
    ("佛山", 890_150.00, 2105, 1_002_750.30, 2450),
    ("珠海", 460_980.80, 1188, 521_300.60, 1290),
]

_FORMULA_ROWS: list[tuple[str, int, float]] = [
    # 商品, 数量, 单价 — 收入 column is a live =B*C formula in the workbook
    ("定期存单", 120, 88.00),
    ("理财产品A", 45, 260.00),
    ("理财产品B", 30, 199.90),
    ("基金定投", 88, 65.50),
    ("贵金属", 12, 460.00),
    ("外汇宝", 25, 320.00),
    ("保险年金", 60, 150.00),
    ("债券组合", 15, 510.00),
    ("货币基金", 210, 12.30),
    ("指数增强", 8, 880.00),
]

_STAFF_ROWS: list[tuple[str, str, str]] = []
for _n in range(1, 21):
    _name = f"员工{_n:03d}"
    if _n <= 8:
        _STAFF_ROWS.append((_name, "零售部", "容桂支行"))
    elif _n <= 14:
        _STAFF_ROWS.append((_name, "公司部", "大良支行"))
    elif _n <= 18:
        _STAFF_ROWS.append((_name, "零售部", "禅城支行"))
    elif _n == 19:
        _STAFF_ROWS.append((_name, "风险部", "容桂支行"))
    else:
        _STAFF_ROWS.append((_name, "风险部", "天河支行"))
del _n, _name


# --- workbook writers ----------------------------------------------------------


def _write_sales_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "销售明细"
    ws.append(["日期", "地区", "网点", "销售额"])
    for row in _SALES_ROWS:
        ws.append(list(row))
    wb.save(path)


def _write_summary_workbook(path: Path) -> None:
    """Two-level header: merged year band over 销售额/订单数 sub-columns."""
    wb = Workbook()
    ws = wb.active
    ws.title = "分区域汇总"
    ws["A1"] = "2024-2025年分区域销售汇总"
    ws.merge_cells("A1:E1")
    ws["A2"] = "地区"
    ws.merge_cells("A2:A3")
    ws["B2"] = "2024年"
    ws.merge_cells("B2:C2")
    ws["D2"] = "2025年"
    ws.merge_cells("D2:E2")
    ws["B3"], ws["C3"] = "销售额", "订单数"
    ws["D3"], ws["E3"] = "销售额", "订单数"
    for row in _SUMMARY_ROWS:
        ws.append(list(row))
    wb.save(path)


def _write_formula_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "收入计算"
    ws.append(["商品", "数量", "单价", "收入"])
    for i, (product, qty, price) in enumerate(_FORMULA_ROWS, start=2):
        ws[f"A{i}"], ws[f"B{i}"], ws[f"C{i}"] = product, qty, price
        ws[f"D{i}"] = f"=B{i}*C{i}"
    wb.save(path)


def _write_staff_csv(path: Path) -> None:
    with open(path, "w", encoding="gbk", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["姓名", "部门", "网点"])
        writer.writerows(_STAFF_ROWS)


# --- golden answers (computed from the same lists, not hand-typed) -------------


def _compute_expected() -> dict[str, Any]:
    sales = _SALES_ROWS
    shunde = sum(r[3] for r in sales if r[1] == "顺德")
    guangzhou_jan = sum(r[3] for r in sales if r[1] == "广州" and r[0].startswith("2024-01"))
    top_row = max(sales, key=lambda r: r[3])
    region_totals: dict[str, float] = {}
    for r in sales:
        region_totals[r[1]] = region_totals.get(r[1], 0.0) + r[3]
    top_region = max(region_totals, key=region_totals.get)  # type: ignore[arg-type]
    revenues = [(p, q * p_price) for p, q, p_price in _FORMULA_ROWS]
    revenue_total = sum(v for _, v in revenues)
    high_revenue_count = sum(1 for _, v in revenues if v > 5000)
    retail_count = sum(1 for _, dept, _ in _STAFF_ROWS if dept == "零售部")

    def region_summary(name: str, col: int) -> Any:
        return next(row[col] for row in _SUMMARY_ROWS if row[0] == name)

    return {
        "q01_shunde_total": round(float(shunde), 2),
        "q02_row_count": len(sales),
        "q03_top_branch": top_row[2],
        "q04_top_region": top_region,
        "q05_gz_jan_total": round(float(guangzhou_jan), 2),
        "q06_sd_2024_sales": region_summary("顺德", 1),
        "q07_gz_2025_orders": region_summary("广州", 4),
        "q08_revenue_total": round(float(revenue_total), 2),
        "q09_revenue_over_5000": high_revenue_count,
        "q10_retail_headcount": retail_count,
    }


def golden_questions() -> list[dict[str, Any]]:
    """The golden QA pairs. ``expected`` values come from _compute_expected."""
    exp = _compute_expected()
    return [
        {
            "id": "q01_shunde_total",
            "file": "销售明细.xlsx",
            "sheet": "销售明细",
            "question": "顺德地区的销售额合计是多少？",
            "expected": exp["q01_shunde_total"],
            "check": "number",
        },
        {
            "id": "q02_row_count",
            "file": "销售明细.xlsx",
            "sheet": "销售明细",
            "question": "销售明细一共有多少条记录？",
            "expected": exp["q02_row_count"],
            "check": "number",
        },
        {
            "id": "q03_top_branch",
            "file": "销售明细.xlsx",
            "sheet": "销售明细",
            "question": "单笔销售额最高的一笔发生在哪个网点？",
            "expected": exp["q03_top_branch"],
            "check": "text",
        },
        {
            "id": "q04_top_region",
            "file": "销售明细.xlsx",
            "sheet": "销售明细",
            "question": "哪个地区的销售额合计最高？",
            "expected": exp["q04_top_region"],
            "check": "text",
        },
        {
            "id": "q05_gz_jan_total",
            "file": "销售明细.xlsx",
            "sheet": "销售明细",
            "question": "广州地区2024年1月的销售额合计是多少？",
            "expected": exp["q05_gz_jan_total"],
            "check": "number",
        },
        {
            "id": "q06_sd_2024_sales",
            "file": "分区域汇总.xlsx",
            "sheet": "分区域汇总",
            "question": "顺德2024年销售额是多少？（注意表头有两级且含合并单元格）",
            "expected": exp["q06_sd_2024_sales"],
            "check": "number",
        },
        {
            "id": "q07_gz_2025_orders",
            "file": "分区域汇总.xlsx",
            "sheet": "分区域汇总",
            "question": "广州2025年的订单数是多少？",
            "expected": exp["q07_gz_2025_orders"],
            "check": "number",
        },
        {
            "id": "q08_revenue_total",
            "file": "公式列.xlsx",
            "sheet": "收入计算",
            "question": "全部商品的收入合计是多少？（收入列为公式，文件未缓存计算值）",
            "expected": exp["q08_revenue_total"],
            "check": "number",
        },
        {
            "id": "q09_revenue_over_5000",
            "file": "公式列.xlsx",
            "sheet": "收入计算",
            "question": "收入超过5000的商品有几种？",
            "expected": exp["q09_revenue_over_5000"],
            "check": "number",
        },
        {
            "id": "q10_retail_headcount",
            "file": "网点名单.csv",
            "sheet": "",
            "question": "零售部一共有多少人？（CSV 为 GBK 编码）",
            "expected": exp["q10_retail_headcount"],
            "check": "number",
        },
    ]


def golden_answers() -> dict[str, Any]:
    """Answer dict {id: expected} — a perfect agent scores 1.0 against it."""
    return {q["id"]: q["expected"] for q in golden_questions()}


def build_qa_fixture(dest_dir: Path | None = None) -> dict[str, Any]:
    """Write the four fixture workbooks and the golden manifest.

    Returns {"dir", "files", "questions", "version"}; the manifest
    (qa_golden.json) bundles questions + expected answers for the scorer.
    """
    dest = Path(dest_dir) if dest_dir else Path(__file__).resolve().parent / "qa_fixtures"
    dest.mkdir(parents=True, exist_ok=True)
    _write_sales_workbook(dest / "销售明细.xlsx")
    _write_summary_workbook(dest / "分区域汇总.xlsx")
    _write_formula_workbook(dest / "公式列.xlsx")
    _write_staff_csv(dest / "网点名单.csv")
    questions = golden_questions()
    manifest = {
        "version": QA_SET_VERSION,
        "dir": str(dest),
        "questions": questions,
    }
    (dest / "qa_golden.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "dir": str(dest),
        "files": [
            "销售明细.xlsx",
            "分区域汇总.xlsx",
            "公式列.xlsx",
            "网点名单.csv",
        ],
        "questions": questions,
        "version": QA_SET_VERSION,
    }
