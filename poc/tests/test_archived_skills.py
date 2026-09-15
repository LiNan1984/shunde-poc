"""Assert extracted 归档 office skills have valid SKILL.md + zip assets."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"

ARCHIVED_SKILLS = (
    "Excel文件处理",
    "PPT文件处理",
    "Word文件处理",
    "WPS Office文件处理",
    "合并excel",
    "数据分析与可视化",
    "专业图表生成",
)

# Existing POC skills must remain on disk (criterion 1).
POC_SKILLS = (
    "excel-qa-bank",
    "kb-qa-bank",
    "ops-assistant",
    "report-visualizer",
)

OFFICECLI_SKILLS = (
    "officecli",
    "officecli-xlsx",
    "officecli-docx",
    "officecli-pptx",
    "officecli-word-form",
    "officecli-academic-paper",
    "officecli-data-dashboard",
    "officecli-financial-model",
    "officecli-pitch-deck",
    "morph-ppt",
    "morph-ppt-3d",
)

ASSET_CHECKS: dict[str, tuple[str, ...]] = {
    "Excel文件处理": ("scripts/recalc.py", "scripts/office/pack.py"),
    "PPT文件处理": ("scripts/add_slide.py", "scripts/clean.py"),
    "Word文件处理": ("scripts/accept_changes.py", "scripts/comment.py"),
    "WPS Office文件处理": ("requirements.txt", "main.py"),
    "数据分析与可视化": (
        "chart-selection.md",
        "decision-briefs.md",
        "metric-contracts.md",
        "pitfalls.md",
        "techniques.md",
    ),
    "专业图表生成": ("bridge.py", "capture.py"),
    "合并excel": (),
}


def _load_frontmatter(skill_name: str) -> tuple[dict, str, Path]:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        pytest.fail(f"{skill_name} SKILL.md missing YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        pytest.fail(f"{skill_name} SKILL.md frontmatter not closed")
    meta = yaml.safe_load(parts[1])
    if not isinstance(meta, dict):
        pytest.fail(f"{skill_name} frontmatter did not parse to a mapping")
    return meta, parts[2], path


@pytest.mark.parametrize("skill_name", ARCHIVED_SKILLS)
def test_archived_skill_md_exists(skill_name: str) -> None:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    assert path.is_file(), f"missing {path}"


@pytest.mark.parametrize("skill_name", ARCHIVED_SKILLS)
def test_archived_frontmatter_name_and_description(skill_name: str) -> None:
    meta, _body, _path = _load_frontmatter(skill_name)
    assert meta.get("name") == skill_name
    assert str(meta.get("description") or "").strip()


@pytest.mark.parametrize("skill_name", ARCHIVED_SKILLS)
def test_archived_zip_assets_landed(skill_name: str) -> None:
    root = SKILLS_DIR / skill_name
    for rel in ASSET_CHECKS[skill_name]:
        path = root / rel
        assert path.is_file(), f"{skill_name} missing zip asset {rel}"


@pytest.mark.parametrize("skill_name", POC_SKILLS)
def test_existing_poc_skills_still_present(skill_name: str) -> None:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    assert path.is_file(), f"POC skill disappeared: {path}"


@pytest.mark.parametrize("skill_name", OFFICECLI_SKILLS)
def test_officecli_skill_md_exists(skill_name: str) -> None:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    assert path.is_file(), f"missing {path}"


@pytest.mark.parametrize("skill_name", OFFICECLI_SKILLS)
def test_officecli_frontmatter_name_and_description(skill_name: str) -> None:
    meta, _body, _path = _load_frontmatter(skill_name)
    assert meta.get("name") == skill_name
    assert str(meta.get("description") or "").strip()
