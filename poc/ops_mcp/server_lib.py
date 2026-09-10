# -*- coding: utf-8 -*-
"""Read ops telemetry JSONL files for question-answering.

This is a tiny read-only surface — the heavy lifting (real ops DB)
lives behind 任务 G. For now we expose three tools that operate on the
JSONL files written by :mod:`poc.hooks.telemetry`:

* :func:`list_telemetry_files` — which JSONL files exist today
* :func:`summarize_calls` — counts per category / status / tool
* :func:`recent_events` — last N events, filterable by category

All paths go through the sandbox via :func:`_resolve_path`; the same
``POC_WORKSPACE`` rules as :mod:`poc.excel_guard_mcp.guards` apply.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Inherit sandbox logic from excel-guard so we don't reinvent
# workspace_root / path resolution. M1 fail-closed behavior is reused
# by reference.
from poc.excel_guard_mcp.guards import (  # noqa: F401  (re-exports semantics)
    _classify_open_error,
    _resolve_allowed_path,
    _workspace_root,
)


def _resolve_path(path: str) -> tuple[Path | None, dict | None]:
    return _resolve_allowed_path(path)


def _telemetry_root() -> tuple[Path | None, dict | None]:
    root, root_err = _workspace_root()
    if root_err is not None or root is None:
        return None, root_err
    return root / "telemetry", None


# ---------------------------------------------------------------------------
# Tool 1: list_telemetry_files
# ---------------------------------------------------------------------------


def list_telemetry_files() -> dict:
    """Return the JSONL files present under ``POC_WORKSPACE/telemetry``.

    Returns:
        {"ok": bool, "files": list[str], "count": int, "message": str}
    """
    base, err = _telemetry_root()
    if err is not None or base is None:
        return {
            "ok": False,
            "files": [],
            "count": 0,
            "message": (err or {"message": "沙箱不可用"})["message"],
        }
    if not base.is_dir():
        return {
            "ok": True,
            "files": [],
            "count": 0,
            "message": f"暂无埋点文件 / No telemetry yet under {base}.",
        }
    files = sorted(str(p) for p in base.glob("**/ops.jsonl"))
    return {
        "ok": True,
        "files": files,
        "count": len(files),
        "message": f"发现 {len(files)} 个埋点文件 / Found {len(files)} telemetry files.",
    }


# ---------------------------------------------------------------------------
# Tool 2: summarize_calls
# ---------------------------------------------------------------------------


def summarize_calls(path: str | None = None) -> dict:
    """Aggregate counts by category, status, and tool.

    Args:
        path: explicit JSONL file path (must be in sandbox). If None,
            the most recent file under ``POC_WORKSPACE/telemetry`` is used.
    """
    target, err = _pick_file(path)
    if err is not None:
        return {"ok": False, "counts": {}, "message": err["message"]}
    assert target is not None

    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_tool: dict[str, int] = {}
    total = 0
    try:
        with target.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total += 1
                cat = rec.get("category", "unknown")
                by_category[cat] = by_category.get(cat, 0) + 1
                status = rec.get("status")
                if status:
                    by_status[status] = by_status.get(status, 0) + 1
                tool = rec.get("tool")
                if tool:
                    by_tool[tool] = by_tool.get(tool, 0) + 1
    except OSError as exc:
        return _classify_open_error(exc, target) | {"counts": {}, "message": exc.strerror}

    return {
        "ok": True,
        "counts": {
            "total": total,
            "by_category": by_category,
            "by_status": by_status,
            "by_tool": by_tool,
        },
        "message": f"已汇总 {total} 条事件 / Aggregated {total} events from {target.name}.",
    }


# ---------------------------------------------------------------------------
# Tool 3: recent_events
# ---------------------------------------------------------------------------


def recent_events(
    category: str | None = None,
    limit: int = 50,
    path: str | None = None,
) -> dict:
    """Return up to ``limit`` most recent events, optionally filtered by
    category. Newest first.
    """
    if limit <= 0 or limit > 1000:
        return {
            "ok": False,
            "events": [],
            "message": "limit 必须在 1..1000 之间 / limit must be 1..1000.",
        }
    target, err = _pick_file(path)
    if err is not None:
        return {"ok": False, "events": [], "message": err["message"]}
    assert target is not None
    events: list[dict[str, Any]] = []
    try:
        with target.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if category and rec.get("category") != category:
                    continue
                events.append(rec)
    except OSError as exc:
        return _classify_open_error(exc, target) | {"events": []}
    events.reverse()  # newest first
    events = events[:limit]
    return {
        "ok": True,
        "events": events,
        "count": len(events),
        "message": f"返回最近 {len(events)} 条事件 / Returned {len(events)} recent events.",
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _pick_file(path: str | None) -> tuple[Path | None, dict | None]:
    """Resolve the JSONL target — either explicit or most recent."""
    if path:
        p, err = _resolve_path(path)
        if err is not None:
            return None, err
        if p is None:
            return None, {"ok": False, "issue": "missing", "message": "路径无效"}
        if not p.is_file():
            return None, {
                "ok": False,
                "issue": "missing",
                "message": f"文件不存在 / File not found: {p}",
            }
        return p, None

    base, err = _telemetry_root()
    if err is not None or base is None:
        return None, err or {
            "ok": False,
            "issue": "workspace_invalid",
            "message": "沙箱不可用",
        }
    if not base.is_dir():
        return None, {
            "ok": False,
            "issue": "missing",
            "message": f"暂无埋点文件 / No telemetry yet under {base}.",
        }
    files = sorted(base.glob("**/ops.jsonl"), reverse=True)
    if not files:
        return None, {
            "ok": False,
            "issue": "missing",
            "message": f"暂无埋点文件 / No telemetry yet under {base}.",
        }
    return files[0], None