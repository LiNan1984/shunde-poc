# -*- coding: utf-8 -*-
"""The PPT generator must describe today's host and live MCP counts.

Reads the shipped generation entry `docs/演示材料/presentation.js`.
Does not re-implement slides.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "docs" / "演示材料" / "presentation.js"


def _src() -> str:
    assert JS.is_file(), JS
    return JS.read_text(encoding="utf-8")


def test_current_host_is_222b1_not_v200() -> None:
    src = _src()
    assert "QwenPaw 2.2.2b1" in src
    # Old tag may appear only as the compared version, never as current host value.
    assert 'v: "QwenPaw v2.0.0"' not in src
    assert 'v: "QwenPaw 2.0.0"' not in src
    assert "宿主 QwenPaw v2.0.0" not in src


def test_excel_guard_nine_tools_and_twenty_five_total() -> None:
    src = _src()
    assert "excel-guard ×9" in src or "excel-guard（9）" in src
    assert "excel-guard ×5" not in src
    assert "Excel 5 + KB 6" not in src
    assert "5+6+3+7=21" not in src
    assert "9+6+3+7=25" in src or "Excel 9 + KB 6 + 运营 3 + 报告 7" in src
    assert "守卫写回" in src and "edit_workbook" in src
    assert "结构化读取" in src and "inspect_workbook" in src
    assert "OpenXML 校验" in src and "validate_workbook" in src
    assert "渲染成图" in src and "render_workbook" in src
