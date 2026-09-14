# -*- coding: utf-8 -*-
"""Shared error classification for kb_mcp tool results.

Failure dicts across tools carry a machine-readable ``error_type`` so the
calling agent can branch (retry vs report vs ask for configuration) without
parsing human-readable messages.
"""

from __future__ import annotations

from typing import Any

# Ordered: first matching keyword wins.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("path_denied", ("路径越界", "path outside", "path denied", "沙箱不可用", "workspace unavailable")),
    ("missing", ("文件不存在", "file not found", "no indexed chunks", "无候选块", "not found")),
    ("too_large", ("文件过大", "file too large", "too big")),
    ("config", ("缺少", "not configured", "未配置", "cannot resolve output_dir")),
    ("network", ("超时", "timeout", "HTTP", "端点失败", "endpoint", "URLError", "connection")),
    ("parse", ("无法打开", "cannot open", "解析失败", "parse", "渲染失败", "cannot render", "格式无效")),
    ("empty_input", ("不能为空", "required", "不能为空 / query required")),
]


def classify_error(message: str) -> str:
    text = message or ""
    for error_type, keywords in _RULES:
        if any(k.lower() in text.lower() for k in keywords):
            return error_type
    return "backend"


def with_error_type(result: dict[str, Any]) -> dict[str, Any]:
    """Attach ``error_type`` to a failure result (ok False) in place and return it."""
    if isinstance(result, dict) and not result.get("ok") and "error_type" not in result:
        result["error_type"] = classify_error(str(result.get("message") or ""))
    return result
