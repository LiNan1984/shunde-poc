# -*- coding: utf-8 -*-
"""Read published Skill + MCP surfaces and assert the L1/L2/L3 load contract.

Does not reimplement MCP tools. Imports the live FastMCP servers and the
on-disk SKILL.md / mcp-*.json that Console actually mounts.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest

from poc.progressive_load import (
    ASSISTANTS,
    CHAIN_PHRASES,
    LEVELS,
    MAX_DESCRIPTION_CHARS,
    PROGRESSIVE_CHAIN,
    mcp_config_path,
    mcp_namespace,
    namespaced_tool,
    skill_path,
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
        if key in {"name", "description"} and key not in meta:
            meta[key] = value
    return meta, body


def _live_tool_names(module_path: str) -> set[str]:
    module = importlib.import_module(module_path)
    tools = asyncio.run(module.mcp.list_tools())
    return {tool.name for tool in tools}


@pytest.mark.parametrize("spec", ASSISTANTS, ids=lambda s: str(s["skill"]))
def test_skill_catalog_description_is_short_l1(spec: dict) -> None:
    text = skill_path(str(spec["skill"])).read_text(encoding="utf-8")
    meta, body = _split_frontmatter(text)
    desc = (meta.get("description") or "").strip()
    assert desc, f"{spec['skill']} missing description"
    assert desc not in {"|", ">"}, f"{spec['skill']} description must be a one-line catalog"
    assert len(desc) <= MAX_DESCRIPTION_CHARS, (
        f"{spec['skill']} L1 skill列表摘要 too long: {len(desc)} > {MAX_DESCRIPTION_CHARS}"
    )
    assert "properties" not in desc.lower()
    assert "input_schema" not in desc.lower()
    assert "渐进加载合同" in body


@pytest.mark.parametrize("spec", ASSISTANTS, ids=lambda s: str(s["skill"]))
def test_skill_body_has_l1_l2_l3_and_literal_chain(spec: dict) -> None:
    body = _split_frontmatter(skill_path(str(spec["skill"])).read_text(encoding="utf-8"))[1]
    for level in LEVELS:
        assert level in body, f"{spec['skill']} missing {level}"
    assert PROGRESSIVE_CHAIN in body, f"{spec['skill']} missing progressive chain"
    positions = [body.find(phrase) for phrase in CHAIN_PHRASES]
    assert all(p >= 0 for p in positions), (
        f"{spec['skill']} missing phrases: "
        + ", ".join(p for p, i in zip(CHAIN_PHRASES, positions) if i < 0)
    )


@pytest.mark.parametrize("spec", ASSISTANTS, ids=lambda s: str(s["skill"]))
def test_mcp_config_declares_namespace_prefix(spec: dict) -> None:
    cfg_path = mcp_config_path(str(spec["mcp_config"]))
    assert cfg_path.is_file(), cfg_path
    payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    servers = payload["mcpServers"]
    key = str(spec["mcp_key"])
    assert key in servers, f"{cfg_path} missing server {key}"
    declared = servers[key].get("namespace")
    expected = mcp_namespace(key)
    assert declared == expected, f"{key} namespace {declared!r} != {expected!r}"


@pytest.mark.parametrize("spec", ASSISTANTS, ids=lambda s: str(s["skill"]))
def test_skill_lists_namespace_prefix_before_file_details(spec: dict) -> None:
    body = _split_frontmatter(skill_path(str(spec["skill"])).read_text(encoding="utf-8"))[1]
    ns = mcp_namespace(str(spec["mcp_key"]))
    assert "mcp列表" in body
    assert "namespace前缀" in body
    assert f"{ns}__" in body, f"{spec['skill']} missing {ns}__ prefix list"
    live = _live_tool_names(str(spec["mcp_module"]))
    for tool in spec["file_summary_tools"]:
        assert tool in live, f"{tool} not registered on {spec['mcp_module']}"
        assert namespaced_tool(str(spec["mcp_key"]), str(tool)) in body
    for tool in spec["file_detail_tools"]:
        assert tool in live, f"{tool} not registered on {spec['mcp_module']}"
        assert namespaced_tool(str(spec["mcp_key"]), str(tool)) in body
        assert body.find("文件摘要") < body.find("文件详情")
        summary_pos = min(
            body.find(namespaced_tool(str(spec["mcp_key"]), str(t)))
            for t in spec["file_summary_tools"]
        )
        detail_pos = body.find(namespaced_tool(str(spec["mcp_key"]), str(tool)))
        assert summary_pos >= 0 and detail_pos >= 0
        assert summary_pos < detail_pos, (
            f"{spec['skill']}: file summary must appear before file detail {tool}"
        )


def test_four_assistants_are_excel_kb_ops_report() -> None:
    labels = [str(s["label"]) for s in ASSISTANTS]
    assert labels == ["Excel问答", "多模态文件", "运营", "报告可视化"]
    skills = [str(s["skill"]) for s in ASSISTANTS]
    for name in skills:
        assert skill_path(name).is_file()
