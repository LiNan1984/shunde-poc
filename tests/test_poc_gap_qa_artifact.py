# -*- coding: utf-8 -*-
"""Structural checks for the Chinese POC completion-gap Q&A artifact.

Drives the real markdown deliverable on disk and cross-checks key claims
against the existing modification-evaluation doc (not a re-implementation).
"""

from __future__ import annotations

import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
QA = WORKSPACE / "docs" / "poc-completion-gap-qa.md"
EVAL = WORKSPACE / "docs" / "qwenpaw-poc-modification-evaluation.md"

SIX_AREAS = [
    "EXCEL",
    "多模态",
    "运营助手",
    "报告可视化",
    "后端部署",
    "HARNESS",
]

NON_TRACKING_GAPS = [
    "损坏",  # Excel MCP anomaly
    "ElasticSearch",
    "/health",
    "Qwen3.6",
]

ACCEPTANCE_MARKERS = [
    "12",
    "三种异常",
    "HOOK",
    "/health",
    "上下文压缩",
    "长期记忆",
    "沙箱",
]


def test_qa_artifact_exists() -> None:
    assert QA.is_file(), f"missing Q&A at {QA}"
    assert EVAL.is_file(), f"missing evaluation at {EVAL}"


def test_tracking_verdict_is_explicit_and_not_only_埋点() -> None:
    text = QA.read_text(encoding="utf-8")
    assert "主要不是" in text, "missing explicit 埋点 verdict"
    assert "Verdict" in text or "明确结论" in text
    # Must cite non-埋点 gaps
    for gap in NON_TRACKING_GAPS:
        assert gap in text, f"missing non-埋点 gap citation: {gap}"


def test_undeveloped_coverage_for_six_poc_areas() -> None:
    text = QA.read_text(encoding="utf-8")
    for area in SIX_AREAS:
        assert area in text, f"missing POC area coverage: {area}"
    # Each area section should list concrete remaining work (❌ 未开发 / 未完成)
    undeveloped = text.count("❌ 未开发") + text.count("❌ 未完成")
    assert undeveloped >= 12, (
        f"expected many concrete undeveloped items, found {undeveloped}"
    )
    q3 = text.split("## Q3.", 1)[1].split("## Q4.", 1)[0]
    assert "待定" not in q3, "undeveloped list must not use vague 待定 placeholders"


def test_schedule_has_numeric_estimates() -> None:
    text = QA.read_text(encoding="utf-8")
    assert "人·日" in text or "人天" in text
    # Total range like 34～52 or similar digits
    assert re.search(r"\d+\s*[～~\-]\s*\d+\s*人", text), "missing person-day range"
    assert re.search(r"\d+(\.\d+)?\s*[～~\-]\s*\d+(\.\d+)?\s*周", text), (
        "missing calendar week range"
    )


def test_acceptance_criteria_section_maps_to_poc_checks() -> None:
    text = QA.read_text(encoding="utf-8")
    assert "验收标准" in text
    for marker in ACCEPTANCE_MARKERS:
        assert marker in text, f"acceptance missing POC marker: {marker}"
    # Numbered items 1..N
    numbered = re.findall(r"(?m)^\d+\.\s+\S+", text)
    assert len(numbered) >= 15, f"expected rich acceptance list, got {len(numbered)}"


def test_qa_aligned_with_evaluation_on_major_gaps() -> None:
    qa = QA.read_text(encoding="utf-8")
    ev = EVAL.read_text(encoding="utf-8")
    for key in ("ElasticSearch", "GALASYBASE", "xlsx", "/health"):
        assert key in qa and key in ev, f"cross-doc gap mismatch on {key}"
