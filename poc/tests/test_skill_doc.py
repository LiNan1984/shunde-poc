"""Assert POC SKILL.md files meet Phase 1 / Phase 2 POC 验收字段."""

from __future__ import annotations

from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
EXPECTED_SECTIONS = ("触发词", "参数", "返回值", "边界")
EXPECTED_FRONTMATTER = {"name", "description"}

SKILLS = [
    ("excel-qa-bank", {"detect_corrupt_workbook", "chunk_large_workbook", "describe_workbook"}),
    ("report-visualizer", {"pivot_table_tool", "render_bar_tool", "render_docx_report_tool"}),
    ("ops-assistant", {"summarize_calls_tool", "recent_events_tool", "list_telemetry_files_tool"}),
    ("kb-qa-bank", {"ingest_document", "ingest_spreadsheet", "search_knowledge", "answer_knowledge"}),
]


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        pytest.fail("SKILL.md missing YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        pytest.fail("SKILL.md frontmatter not closed")
    raw, body = parts[1], parts[2]
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in EXPECTED_FRONTMATTER:
            meta[key] = value
    return meta, body


def _load(skill_name: str) -> tuple[dict[str, str], str]:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    assert path.is_file(), f"missing {path}"
    return _split_frontmatter(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("skill_name,_tools", SKILLS)
def test_skill_md_exists(skill_name: str, _tools: set[str]) -> None:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    assert path.is_file(), f"missing {path}"


@pytest.mark.parametrize("skill_name,_tools", SKILLS)
def test_frontmatter_name_and_description(skill_name: str, _tools: set[str]) -> None:
    meta, _ = _load(skill_name)
    assert meta.get("name") == skill_name
    assert (meta.get("description") or "").strip()


@pytest.mark.parametrize("skill_name,_tools", SKILLS)
def test_body_has_poc_acceptance_sections(skill_name: str, _tools: set[str]) -> None:
    _, body = _load(skill_name)
    for needle in EXPECTED_SECTIONS:
        assert needle in body, f"{skill_name} SKILL.md missing required section marker: {needle}"


def test_excel_skill_mentions_excel_guard_tools() -> None:
    _, body = _load("excel-qa-bank")
    assert "detect_corrupt_workbook" in body
    assert "chunk_large_workbook" in body
    assert "describe_workbook" in body
    assert "sheet_to_markdown" in body
    assert "pandas" in body.lower()


def test_report_skill_mentions_mcp_tools() -> None:
    _, body = _load("report-visualizer")
    for tool in ("pivot_table_tool", "render_bar_tool", "render_docx_report_tool"):
        assert tool in body, f"report-visualizer SKILL.md missing tool mention: {tool}"


def test_ops_skill_mentions_mcp_tools() -> None:
    _, body = _load("ops-assistant")
    for tool in (
        "summarize_calls_tool",
        "recent_events_tool",
        "list_telemetry_files_tool",
    ):
        assert tool in body, f"ops-assistant SKILL.md missing tool mention: {tool}"


def test_kb_skill_mentions_mcp_tools() -> None:
    _, body = _load("kb-qa-bank")
    for tool in (
        "parse_document",
        "ingest_document",
        "ingest_spreadsheet",
        "search_knowledge",
        "answer_knowledge",
        "analyze_page",
    ):
        assert tool in body, f"kb-qa-bank SKILL.md missing tool mention: {tool}"
    assert "定位" in body or "locate" in body.lower()
    assert "pandas" in body.lower() or "excel-qa-bank" in body
