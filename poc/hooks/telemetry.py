# -*- coding: utf-8 -*-
"""Telemetry sink for the POC ops hooks.

Writes one JSON object per line (JSONL) to
``POC_WORKSPACE/telemetry/ops-<date>.jsonl``. The schema is intentionally
flat so downstream consumers (jq / pandas) can load it without an extra
parser.

The sink is intentionally lock-free and best-effort: if a write fails
(permission, full disk, etc.) the failure is logged to stderr and
swallowed. Telemetry must NEVER crash a real request — that would be
worse than missing one event (红线: telemetry 不能影响主流程).

Fields per event:
    ts: ISO-8601 UTC timestamp
    category: "call_volume" | "token_usage" | "tool_outcome" |
              "identity" | "latency"
    session_id, agent_id, root_session_id, root_agent_id: identity
    tool: tool name (for tool_outcome / call_volume)
    status: "ok" | "error" | "skip"  (tool_outcome)
    tokens_in, tokens_out: int (token_usage)
    latency_ms: float (latency)
    workspace_dir: str (absolute path under sandbox)
    extras: free-form dict
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("poc.ops.telemetry")

_LOCK = threading.Lock()
_WRITTEN_DIRS: set[str] = set()


def _telemetry_dir() -> Path | None:
    """Resolve the per-day telemetry directory under the sandbox.

    Returns None when the sandbox root is unusable so callers can
    short-circuit safely.
    """
    workspace = os.environ.get("POC_WORKSPACE") or os.environ.get(
        "QWENPAW_WORKING_DIR"
    )
    if not workspace:
        return None
    try:
        root = Path(workspace).expanduser().resolve(strict=False)
    except (OSError, ValueError):
        return None
    if not root.is_dir():
        return None
    day = time.strftime("%Y-%m-%d", time.gmtime())
    d = root / "telemetry" / day
    return d


def write(category: str, payload: dict[str, Any]) -> None:
    """Append one event. Never raises."""
    base = _telemetry_dir()
    if base is None:
        return
    try:
        with _LOCK:
            if str(base) not in _WRITTEN_DIRS:
                base.mkdir(parents=True, exist_ok=True)
                _WRITTEN_DIRS.add(str(base))
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            record = {"ts": ts, "category": category, **payload}
            line = json.dumps(record, ensure_ascii=False, sort_keys=True)
            with (base / "ops.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError as exc:
        # stderr only — stdout is the MCP JSON-RPC channel for the
        # bundled MCP servers (红线 4). Plugin hooks don't have that
        # constraint, but staying on stderr keeps the convention.
        print(f"telemetry write failed: {exc}", file=sys.stderr)