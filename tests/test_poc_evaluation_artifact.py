# -*- coding: utf-8 -*-
"""Structural verification of the POC modification evaluation deliverable.

Drives real filesystem/git entry points in this workspace:
- QwenPaw clone tag must be exactly v2.0.0
- Evaluation markdown must cover all six POC areas with concrete path citations
- MaaS wiring section must require env/gitignored secrets (no committed Bearer)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
QWENPAW = WORKSPACE / "QwenPaw"
EVAL = WORKSPACE / "docs" / "qwenpaw-poc-modification-evaluation.md"

REQUIRED_SECTION_HEADINGS = [
    "EXCEL 文件问答助手",
    "多模态文件问答助手",
    "运营助手",
    "报告可视化助手",
    "后端部署能力",
    "HARNESS 能力",
]

# At least one real path/mechanism citation per major area (from clone inspection).
REQUIRED_PATH_CITATIONS = [
    "src/qwenpaw/agents/skills/xlsx-zh/SKILL.md",
    "src/qwenpaw/app/mcp/schemas.py",
    "src/qwenpaw/agents/memory/reme_light_memory_manager.py",
    "src/qwenpaw/runtime/phases.py",
    "src/qwenpaw/plugins/api.py",
    "src/qwenpaw/agents/skills/docx-zh/SKILL.md",
    "deploy/Dockerfile",
    "src/qwenpaw/sandbox/config.py",
    "src/qwenpaw/agents/context/scroll",
]

MAAS_MARKERS = [
    "compatible-mode/v1",
    "QWENPAW_MAAS_API_KEY",
    "QWENPAW_SECRET_DIR",
    "禁止",
]

GAP_MARKERS = [
    "ElasticSearch",
    "MySQL",
    "GALASYBASE",
    "Qwen3.6",
    "qwen3.5-35b-a3b",
]

PRIORITY_PATTERN = re.compile(
    r"推荐改造优先级|优先改造顺序",
    re.MULTILINE,
)
NUMBERED_PRIORITY_PATTERN = re.compile(
    r"(?m)^\d+\.\s+\*\*.+\*\*",
)


def _git_describe(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "describe", "--tags", "--exact-match"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_qwenpaw_clone_is_v2_0_0() -> None:
    assert QWENPAW.is_dir(), f"missing clone at {QWENPAW}"
    assert (QWENPAW / "src" / "qwenpaw").is_dir()
    assert _git_describe(QWENPAW) == "v2.0.0"


def test_evaluation_artifact_exists_and_covers_six_areas() -> None:
    assert EVAL.is_file(), f"missing evaluation at {EVAL}"
    text = EVAL.read_text(encoding="utf-8")
    for heading in REQUIRED_SECTION_HEADINGS:
        assert heading in text, f"missing section for: {heading}"


def test_evaluation_cites_real_clone_paths() -> None:
    text = EVAL.read_text(encoding="utf-8")
    for path in REQUIRED_PATH_CITATIONS:
        assert path in text, f"evaluation missing citation: {path}"
        # Citation must correspond to something that exists in the clone.
        target = QWENPAW / path
        assert target.exists(), f"cited path missing in clone: {path}"


def test_evaluation_maas_wiring_forbids_committed_secrets() -> None:
    text = EVAL.read_text(encoding="utf-8")
    for marker in MAAS_MARKERS:
        assert marker in text, f"MaaS wiring missing marker: {marker}"
    # Must not embed live Bearer tokens in the tracked eval.
    assert re.search(r"Authorization:\s*Bearer\s+\S+", text) is None
    assert re.search(r"Bearer\s+sk-", text) is None
    assert re.search(r"sk-[A-Za-z0-9._\-]{20,}", text) is None

    gitignore = (WORKSPACE / ".gitignore").read_text(encoding="utf-8")
    for rule in (".env", "providers.json", "QwenPaw/"):
        assert rule in gitignore, f".gitignore missing rule: {rule}"

    env_example = (WORKSPACE / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"(?m)^QWENPAW_MAAS_API_KEY=\s*$", env_example), (
        ".env.example must leave QWENPAW_MAAS_API_KEY empty"
    )


def test_evaluation_has_gaps_and_ranked_modification_order() -> None:
    text = EVAL.read_text(encoding="utf-8")
    for marker in GAP_MARKERS:
        assert marker in text, f"gap list missing: {marker}"
    assert PRIORITY_PATTERN.search(text), "missing prioritized modification section"
    matches = NUMBERED_PRIORITY_PATTERN.findall(text)
    assert len(matches) >= 5, (
        f"expected numbered priority list (>=5), found {len(matches)}"
    )


def test_cited_extension_docs_exist() -> None:
    for rel in (
        "website/public/docs/mcp.zh.md",
        "website/public/docs/skills.zh.md",
        "website/public/docs/models.zh.md",
        "website/public/docs/memory.zh.md",
        "website/public/docs/context.zh.md",
        "website/public/docs/plugins.zh.md",
    ):
        assert (QWENPAW / rel).is_file(), rel
