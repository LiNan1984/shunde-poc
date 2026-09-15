# -*- coding: utf-8 -*-
"""Shared L1/L2/L3 progressive-load contract for the four POC assistants.

The published Skill body and MCP config are the source of truth. This module
only names the chain and maps each assistant to its MCP server key / file
tools so tests can *read* those artifacts — it does not reimplement tools.
"""

from __future__ import annotations

from pathlib import Path

# Literal load order required in Skill bodies and the PPT.
PROGRESSIVE_CHAIN = (
    "skill列表摘要 → skill → mcp列表namespace前缀 → 详细mcp → 文件摘要 → 文件详情"
)

CHAIN_PHRASES = (
    "skill列表摘要",
    "skill",
    "mcp列表",
    "namespace前缀",
    "详细mcp",
    "文件摘要",
    "文件详情",
)

LEVELS = ("L1", "L2", "L3")

# Catalog description must stay short so L1 is a stable prompt prefix.
MAX_DESCRIPTION_CHARS = 280

POC_DIR = Path(__file__).resolve().parent
SKILLS_DIR = POC_DIR / "skills"
CONFIG_DIR = POC_DIR / "config"


def mcp_namespace(server_key: str) -> str:
    """Match QwenPaw ``_sanitize_tool_namespace`` for letter-led keys."""
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in server_key)
    return cleaned.replace("-", "_")


def namespaced_tool(server_key: str, tool_name: str) -> str:
    return f"{mcp_namespace(server_key)}__{tool_name}"


# File-summary vs file-detail tools as they appear on the live MCP servers.
ASSISTANTS: tuple[dict[str, object], ...] = (
    {
        "skill": "excel-qa-bank",
        "label": "Excel问答",
        "mcp_key": "excel-guard",
        "mcp_config": "mcp-excel-guard.json",
        "mcp_module": "poc.excel_guard_mcp.server",
        "file_summary_tools": ("describe_workbook",),
        "file_detail_tools": ("sheet_to_markdown", "inspect_workbook"),
    },
    {
        "skill": "kb-qa-bank",
        "label": "多模态文件",
        "mcp_key": "kb-qa",
        "mcp_config": "mcp-kb-qa.json",
        "mcp_module": "poc.kb_mcp.server",
        "file_summary_tools": ("parse_document", "search_knowledge"),
        "file_detail_tools": ("analyze_page",),
    },
    {
        "skill": "ops-assistant",
        "label": "运营",
        "mcp_key": "ops-data",
        "mcp_config": "mcp-ops-data.json",
        "mcp_module": "poc.ops_mcp.server",
        "file_summary_tools": ("list_telemetry_files_tool",),
        "file_detail_tools": ("recent_events_tool",),
    },
    {
        "skill": "report-visualizer",
        "label": "报告可视化",
        "mcp_key": "report-visualizer",
        "mcp_config": "mcp-report-visualizer.json",
        "mcp_module": "poc.report_mcp.server",
        "file_summary_tools": ("pivot_table_tool",),
        "file_detail_tools": ("render_docx_report_tool",),
    },
)


def skill_path(skill_name: str) -> Path:
    return SKILLS_DIR / skill_name / "SKILL.md"


def mcp_config_path(filename: str) -> Path:
    return CONFIG_DIR / filename
