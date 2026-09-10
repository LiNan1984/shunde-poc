"""Assert excel-qa-bank SKILL.md meets Phase 1 POC 验收字段."""

from __future__ import annotations

from pathlib import Path

import pytest

SKILL_PATH = (
    Path(__file__).resolve().parents[1] / "skills" / "excel-qa-bank" / "SKILL.md"
)


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
        if key in ("name", "description"):
            meta[key] = value
    return meta, body


def test_skill_md_exists():
    assert SKILL_PATH.is_file(), f"missing {SKILL_PATH}"


def test_frontmatter_name_and_description():
    meta, _ = _split_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    assert meta.get("name") == "excel-qa-bank"
    description = meta.get("description", "")
    assert description.strip()


def test_body_has_poc_acceptance_sections():
    _, body = _split_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    for needle in ("触发词", "参数", "返回值", "边界"):
        assert needle in body, f"body missing required section marker: {needle}"


def test_body_mentions_excel_guard_tools():
    _, body = _split_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    assert "detect_corrupt_workbook" in body
    assert "chunk_large_workbook" in body
