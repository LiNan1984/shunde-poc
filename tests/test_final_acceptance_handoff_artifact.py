# -*- coding: utf-8 -*-
"""Structural checks for the bank-side final acceptance handoff markdown.

Drives the real ``docs/最终验收交接文档.md`` on disk (not a re-implementation)
and asserts the OBJECTIVE section set + must-have markers. Also locks the
division of labor with ``docs/HANDOFF.md`` (开发侧 vs 行方侧, 并存).
"""

from __future__ import annotations

import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
FINAL = WORKSPACE / "docs" / "最终验收交接文档.md"
HANDOFF = WORKSPACE / "docs" / "HANDOFF.md"

REQUIRED_HEADINGS = [
    "〇. 验收速览",
    "一、对应原需求",
    "二、交付物清单",
    "三、演示流程",
    "四、24 条业务验收速查",
    "五、红线对照",
    "六、阻塞项与对接窗口",
    "七、签字栏",
]

USE_CASE_IDS = [
    "1-1",
    "1-2",
    "1-3",
    "2-1",
    "2-2",
    "3-1",
    "3-2",
    "3-3",
    "4-1",
    "4-2",
    "4-3",
]

DEMO_SUBSECTIONS = [
    "3.1",
    "3.2",
    "3.3",
    "3.4",
    "3.5",
    "3.6",
    "3.7",
    "3.8",
]

# Paths that must exist on disk AND be cited (substring match) in the doc.
CITED_PATHS = [
    "poc/excel_guard_mcp",
    "poc/report_mcp",
    "poc/ops_mcp",
    "poc/plugins/health",
    "poc/plugins/ops-telemetry",
    "poc/deploy/Dockerfile.poc",
    "scripts/report_demo.py",
    "scripts/mcp_stdio_smoke.py",
    "scripts/append_proof_blocks.py",
    "docs/HANDOFF.md",
]

# Skill trees: doc may use brace form poc/skills/{a,b,c}/SKILL.md
SKILL_PATHS = [
    "poc/skills/excel-qa-bank/SKILL.md",
    "poc/skills/report-visualizer/SKILL.md",
    "poc/skills/ops-assistant/SKILL.md",
]


def _final_text() -> str:
    assert FINAL.is_file(), f"missing final acceptance doc at {FINAL}"
    return FINAL.read_text(encoding="utf-8")


def test_final_acceptance_artifact_exists() -> None:
    assert FINAL.is_file(), f"missing {FINAL}"
    assert HANDOFF.is_file(), f"missing {HANDOFF}"


def test_eight_named_sections_present() -> None:
    text = _final_text()
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"missing section heading: {heading}"


def test_overview_table_has_countable_claims() -> None:
    text = _final_text()
    overview = text.split("## 〇. 验收速览", 1)[1].split("## 一、", 1)[0]
    assert "三个 MCP" in overview or "三个MCP" in overview, "速览 missing 三个 MCP"
    assert "三个 Skill" in overview or "3 份 SKILL" in overview, (
        "速览 must label three Skills (not 两个 Skill for three paths)"
    )
    assert "两个 Skill" not in overview, "inconsistent: 两个 Skill label with three paths"
    assert "两个" in overview and "插件" in overview, "速览 missing 两个插件 claim"
    assert "0 行" in overview or "内核改动" in overview, "速览 missing 内核 0 行"
    assert "0" in overview and ("密钥" in overview or "Bearer" in overview), (
        "速览 missing 0 密钥泄露 claim"
    )


def test_eleven_requirement_use_cases_mapped() -> None:
    text = _final_text()
    section = text.split("## 一、对应原需求", 1)[1].split("## 二、", 1)[0]
    for case_id in USE_CASE_IDS:
        assert case_id in section, f"missing use-case row {case_id}"
    # commit hashes appear for completed rows (short hex)
    hashes = re.findall(r"`([0-9a-f]{7})`", section)
    assert len(hashes) >= 6, f"expected commit hashes in §一, found {hashes}"
    assert "证据位置" in section or "证据" in section


def test_deliverables_index_covers_code_docs_scripts() -> None:
    text = _final_text()
    section = text.split("## 二、交付物清单", 1)[1].split("## 三、", 1)[0]
    assert "poc/" in section
    assert "docs/" in section
    assert "scripts/" in section
    for path in (
        "excel_guard_mcp",
        "report_mcp",
        "ops_mcp",
        "excel-qa-bank",
        "report-visualizer",
        "ops-assistant",
        "scripts/report_demo.py",
        "scripts/mcp_stdio_smoke.py",
    ):
        assert path in section, f"交付物清单 missing {path}"


def test_eight_demo_command_blocks() -> None:
    text = _final_text()
    section = text.split("## 三、演示流程", 1)[1].split("## 四、", 1)[0]
    for sub in DEMO_SUBSECTIONS:
        assert sub in section, f"missing demo subsection {sub}"
    # eight fenced bash (or generic) command blocks
    fences = re.findall(r"```(?:bash)?\n[\s\S]*?```", section)
    assert len(fences) >= 7, (
        f"expected ≥7 copy-paste command blocks in §三, found {len(fences)}"
    )
    # §3.3 must claim three MCPs including ops-data with 13 tools total
    demo_stdio = section.split("3.3", 1)[1].split("3.4", 1)[0]
    assert "ops-data" in demo_stdio
    assert "13" in demo_stdio
    assert "mcp_stdio_smoke.py" in demo_stdio


def test_scripts_index_smoke_row_matches_three_mcps() -> None:
    text = _final_text()
    section = text.split("## 二、交付物清单", 1)[1].split("## 三、", 1)[0]
    assert "mcp_stdio_smoke.py" in section
    assert "三个 MCP" in section
    assert "13" in section
    # Forbid the stale "10 个工具" claim that only covered two MCPs
    assert "10 个工具" not in section


def test_six_scene_acceptance_table() -> None:
    text = _final_text()
    section = text.split("## 四、24 条业务验收速查", 1)[1].split("## 五、", 1)[0]
    assert "验收要点" in section
    assert "本仓库对位" in section
    # six scene rows ①…⑥
    for mark in ("①", "②", "③", "④", "⑤", "⑥"):
        assert mark in section, f"§四 missing scene row {mark}"


def test_seven_red_lines_checked() -> None:
    text = _final_text()
    section = text.split("## 五、红线对照", 1)[1].split("## 六、", 1)[0]
    numbered = re.findall(r"(?m)^\|\s*([1-7])\s*\|", section)
    assert numbered == ["1", "2", "3", "4", "5", "6", "7"], (
        f"expected red-line rows 1..7, got {numbered}"
    )
    assert section.count("✅") >= 7


def test_five_external_dependency_rows() -> None:
    text = _final_text()
    section = text.split("## 六、阻塞项与对接窗口", 1)[1].split("## 七、", 1)[0]
    # data rows in markdown table (skip header + separator)
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("|") and "---" not in line and "阻塞项" not in line
    ]
    assert len(rows) >= 5, f"expected ≥5 阻塞/依赖 rows, found {len(rows)}: {rows}"


def test_ascii_signoff_block() -> None:
    text = _final_text()
    section = text.split("## 七、签字栏", 1)[1]
    assert "交出方" in section
    assert "接收方" in section
    assert "┌" in section and "└" in section and "│" in section


def test_division_of_labor_with_handoff() -> None:
    final = _final_text()
    handoff = HANDOFF.read_text(encoding="utf-8")
    assert "并存" in final, "最终验收 must state 并存 with HANDOFF"
    assert "HANDOFF.md" in final
    assert "开发侧" in final or "接手 48" in final or "48 小时" in final
    assert "行方" in final
    # HANDOFF keeps 开发侧 role and points at 最终验收
    assert "48 小时" in handoff or "48小时" in handoff
    assert "密钥" in handoff
    assert "最终验收交接文档" in handoff
    assert "并存" in handoff or "行方侧" in handoff


def test_cited_deliverable_paths_exist_on_disk() -> None:
    """Spot-check that paths advertised in the doc actually exist."""
    text = _final_text()
    for rel in CITED_PATHS:
        assert rel in text, f"doc should cite {rel}"
        path = WORKSPACE / rel
        assert path.exists(), f"cited path missing on disk: {rel}"
    for rel in SKILL_PATHS:
        path = WORKSPACE / rel
        assert path.is_file(), f"skill path missing on disk: {rel}"
        # Accept full path or brace-expansion citation of the skill dir name
        skill_dir = Path(rel).parts[2]  # excel-qa-bank / report-visualizer / …
        assert skill_dir in text, f"doc should mention skill {skill_dir}"
    assert "poc/skills/" in text and "SKILL.md" in text
    # Explicitly forbid the wrong historical path for report_demo
    assert "poc/scripts/report_demo.py" not in text, (
        "stale path poc/scripts/report_demo.py — use scripts/report_demo.py"
    )
