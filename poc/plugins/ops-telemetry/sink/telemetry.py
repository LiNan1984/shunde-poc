# -*- coding: utf-8 -*-
"""Telemetry sink for the POC ops hooks.

Writes one JSON object per line (JSONL) to
``<workspace>/telemetry/<UTC-date>/ops.jsonl``. The reader (ops-data MCP)
uses ``POC_WORKSPACE`` (typically ``/root/shunde-poc``). The writer fans
out to every usable root so a host process whose env points at
``~/.qwenpaw`` still produces a file the MCP can list.

The sink is lock-free and best-effort: write failures go to stderr and are
swallowed. Telemetry must NEVER crash a real request.

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
"""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("poc.ops.telemetry")

_LOCK = threading.Lock()
_WRITTEN_DIRS: set[str] = set()

# Deploy-host MCP sandbox from poc/config/mcp-ops-data.json. Exists only on
# the QwenPaw box; on a laptop this is a no-op because the path is absent.
KNOWN_MCP_SANDBOXES: tuple[Path, ...] = (Path("/root/shunde-poc"),)


def _as_existing_dir(raw: Any) -> Path | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        root = Path(text).expanduser().resolve(strict=False)
    except (OSError, ValueError):
        return None
    if str(root) == os.sep:
        return None
    try:
        is_dir = root.is_dir()
    except OSError:  # unreadable parent (e.g. /root on Linux CI) — treat as absent
        return None
    if not is_dir:
        return None
    return root


def _looks_like_qwenpaw_home(root: Path) -> bool:
    return ".qwenpaw" in root.parts


def pin_host_sandbox(candidates: list[Any]) -> Path | None:
    """Set ``POC_WORKSPACE`` to the MCP sandbox when the host has none, or
    when the current value is ``~/.qwenpaw`` (agent home, not MCP).

    ``QWENPAW_WORKING_DIR`` is ignored here on purpose.
    """
    existing = _as_existing_dir(os.environ.get("POC_WORKSPACE"))
    known = None
    for raw in (*candidates, *KNOWN_MCP_SANDBOXES):
        root = _as_existing_dir(raw)
        if root is None or _looks_like_qwenpaw_home(root):
            continue
        known = root
        break
    if known is not None and (existing is None or _looks_like_qwenpaw_home(existing)):
        os.environ["POC_WORKSPACE"] = str(known)
        return known
    return existing if existing is not None else known


def iter_write_roots(workspace_dir: Any = None) -> list[Path]:
    """Every directory that should receive a copy of the event."""
    seen: set[str] = set()
    roots: list[Path] = []
    for raw in (
        os.environ.get("POC_WORKSPACE"),
        *KNOWN_MCP_SANDBOXES,
        workspace_dir,
        os.environ.get("QWENPAW_WORKING_DIR"),
    ):
        root = _as_existing_dir(raw)
        if root is None:
            continue
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        roots.append(root)
    return roots


def resolve_workspace_root(workspace_dir: Any = None) -> Path | None:
    """Primary root the ops-data MCP lists.

    Order: POC_WORKSPACE → known MCP sandbox → ctx.workspace_dir →
    QWENPAW_WORKING_DIR. ``~/.qwenpaw`` is skipped when a real MCP
    sandbox is available.
    """
    poc = _as_existing_dir(os.environ.get("POC_WORKSPACE"))
    if poc is not None and not (
        _looks_like_qwenpaw_home(poc) and any(
            _as_existing_dir(k) is not None for k in KNOWN_MCP_SANDBOXES
        )
    ):
        return poc
    for known in KNOWN_MCP_SANDBOXES:
        root = _as_existing_dir(known)
        if root is not None:
            return root
    ctx = _as_existing_dir(workspace_dir)
    if ctx is not None:
        return ctx
    qwen = _as_existing_dir(os.environ.get("QWENPAW_WORKING_DIR"))
    if qwen is not None:
        return qwen
    return poc


def _append_line(root: Path, category: str, payload: dict[str, Any]) -> Path | None:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    base = root / "telemetry" / day
    try:
        with _LOCK:
            if str(base) not in _WRITTEN_DIRS:
                base.mkdir(parents=True, exist_ok=True)
                _WRITTEN_DIRS.add(str(base))
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            record = {**payload, "ts": ts, "category": category}
            line = json.dumps(record, ensure_ascii=False, sort_keys=True)
            path = base / "ops.jsonl"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            return path
    except Exception as exc:
        print(f"telemetry write failed ({root}): {exc}", file=sys.stderr)
        return None


def write(
    category: str,
    payload: dict[str, Any],
    *,
    workspace_dir: Any = None,
) -> Path | None:
    """Append one event to every usable root. Never raises."""
    if workspace_dir is None:
        workspace_dir = payload.get("workspace_dir")
    roots = iter_write_roots(workspace_dir)
    if not roots:
        print(
            "telemetry skip: no usable workspace "
            "(tried POC_WORKSPACE, known MCP sandbox, "
            "ctx.workspace_dir, QWENPAW_WORKING_DIR)",
            file=sys.stderr,
        )
        return None
    last: Path | None = None
    for root in roots:
        written = _append_line(root, category, payload)
        if written is not None:
            last = written
    return last


def write_plugin_loaded(hook_names: list[str]) -> Path | None:
    """Emit a bootstrap line as soon as the plugin registers (no user turn)."""
    return write(
        "identity",
        {
            "event": "plugin_register",
            "plugin_id": "poc-ops-telemetry",
            "hooks": ",".join(hook_names),
            "session_id": "plugin_register",
            "agent_id": "",
        },
    )


def record_mcp_call(tool: str, *, server: str, status: str = "ok") -> Path | None:
    """Record one MCP tool invocation. Used by the FastMCP servers themselves.

    Runtime hooks never fired on the host; ops-data MCP *does* run when the
    user asks 「哪个工具用得最多」. Writing here is the path that actually
    executes, and it uses the same ``POC_WORKSPACE`` the reader has.
    """
    return write(
        "tool_outcome",
        {
            "tool": tool,
            "status": status,
            "event": "mcp",
            "server": server,
            "session_id": "mcp",
            "agent_id": "",
        },
    )


def mark_mcp_started(server: str) -> Path | None:
    return write(
        "identity",
        {
            "event": "mcp_started",
            "server": server,
            "tool": f"{server.replace('-', '_')}__server",
            "session_id": "mcp_start",
            "agent_id": "",
        },
    )


def mcp_traced(server: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Write a tool_outcome line *before* the tool body (so list sees it)."""
    ns = server.replace("-", "_")

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        qualified = f"{ns}__{getattr(fn, '__name__', 'tool')}"

        @functools.wraps(fn)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            record_mcp_call(qualified, server=server, status="ok")
            try:
                return fn(*args, **kwargs)
            except Exception:
                record_mcp_call(qualified, server=server, status="error")
                raise

        return wrapped

    return decorator


def traced_fastmcp(server: str) -> Any:
    """FastMCP whose ``@mcp.tool()`` functions emit JSONL on every call."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(server)
    original_tool = mcp.tool

    def tool(*dargs: Any, **dkwargs: Any) -> Callable[[Callable[..., Any]], Any]:
        register = original_tool(*dargs, **dkwargs)

        def deco(fn: Callable[..., Any]) -> Any:
            return register(mcp_traced(server)(fn))

        return deco

    mcp.tool = tool  # type: ignore[method-assign]
    return mcp
