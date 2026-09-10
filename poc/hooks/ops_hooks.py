# -*- coding: utf-8 -*-
"""Four-category POC telemetry hooks.

Hooks are QwenPaw ``HookBase`` subclasses (see
``QwenPaw/src/qwenpaw/runtime/hooks.py:145``) registered via
``api.register_runtime_hook(hook_instance)``. Each hook reads the
current ``HookContext`` and emits a JSONL record through
:mod:`poc.hooks.telemetry`. No hook ever mutates the agent state or
short-circuits — they only observe.

The four categories line up with 任务 C's 24-requirement checklist:

* **call_volume** (PRE_DISPATCH / POST_DISPATCH): one record per request
  (start + end). Captures session/agent IDs.
* **token_usage** (POST_RESPONSE): reports ``tokens_in`` / ``tokens_out``
  from the request envelope when available.
* **tool_outcome** (PRE_EXECUTE / ON_ERROR): one record per tool call
  with ``tool`` name and ``status``.
* **latency** (POST_DISPATCH): ``latency_ms`` between PRE_DISPATCH and
  POST_DISPATCH.
* **identity** (PRE_AGENT_BUILD): session/agent/root pair for the
  request — handy when call_volume isn't enough.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

# We do NOT import qwenpaw at module load — the host runtime is only
# available inside the QwenPaw venv and importing it pulls the whole
# AgentScope stack. We follow the Phase/HookBase protocol with strings
# and duck typing instead. Plugin-time registration goes through
# ``api.register_runtime_hook(hook)`` which does the type check on the
# QwenPaw side.
#
# Phase string values come straight from
# ``QwenPaw/src/qwenpaw/runtime/phases.py`` so they line up with the
# enum used by the host runtime.

from . import telemetry

if TYPE_CHECKING:
    from qwenpaw.runtime.hooks import HookBase, HookContext, HookResult  # type: ignore[import-not-found]


def _make_hook_base() -> Any:
    """Return the HookBase class without importing qwenpaw at module load.

    Falls back to a tiny stub when qwenpaw isn't installed (CI), so the
    hooks remain importable for unit tests.
    """
    try:
        from qwenpaw.runtime.hooks import HookBase  # type: ignore[import-not-found]
        return HookBase
    except ImportError:
        class _StubHookBase:
            phase: Any = None
            name: str = ""
            priority: int = 100

            async def run(self, ctx: Any) -> Any:  # pragma: no cover
                return None
        return _StubHookBase


HookBase = _make_hook_base()


class CallVolumeStartHook(HookBase):
    """PRE_DISPATCH: emit session identity + start timestamp."""

    phase = "PRE_DISPATCH"
    name = "poc_call_volume_start"
    priority = 90

    async def run(self, ctx: Any) -> Any:
        telemetry.write("call_volume", {
            "event": "start",
            "session_id": ctx.session_id,
            "agent_id": ctx.agent_id,
            "root_session_id": ctx.root_session_id,
            "root_agent_id": ctx.root_agent_id,
            "workspace_dir": str(ctx.workspace_dir) if ctx.workspace_dir else "",
        })
        # Stash a start time for the latency hook pair.
        ctx.extras["poc_dispatch_start"] = time.monotonic()
        return None


class CallVolumeEndHook(HookBase):
    """POST_DISPATCH: emit end + computed latency_ms."""

    phase = "POST_DISPATCH"
    name = "poc_call_volume_end"
    priority = 110

    async def run(self, ctx: Any) -> Any:
        start = ctx.extras.get("poc_dispatch_start")
        latency_ms = None
        if isinstance(start, (int, float)):
            latency_ms = round((time.monotonic() - start) * 1000.0, 2)
        payload: dict = {
            "event": "end",
            "session_id": ctx.session_id,
            "agent_id": ctx.agent_id,
            "root_session_id": ctx.root_session_id,
            "root_agent_id": ctx.root_agent_id,
            "workspace_dir": str(ctx.workspace_dir) if ctx.workspace_dir else "",
        }
        if latency_ms is not None:
            payload["latency_ms"] = latency_ms
            telemetry.write("latency", payload)
        telemetry.write("call_volume", payload)
        return None


class IdentityHook(HookBase):
    """PRE_AGENT_BUILD: capture identity, redundant with call_volume_start
    but guaranteed to fire even when PRE_DISPATCH is short-circuited."""

    phase = "PRE_AGENT_BUILD"
    name = "poc_identity"
    priority = 90

    async def run(self, ctx: Any) -> Any:
        telemetry.write("identity", {
            "session_id": ctx.session_id,
            "agent_id": ctx.agent_id,
            "root_session_id": ctx.root_session_id,
            "root_agent_id": ctx.root_agent_id,
            "workspace_dir": str(ctx.workspace_dir) if ctx.workspace_dir else "",
        })
        return None


class TokenUsageHook(HookBase):
    """POST_RESPONSE: emit tokens_in / tokens_out if exposed."""

    phase = "POST_RESPONSE"
    name = "poc_token_usage"
    priority = 90

    async def run(self, ctx: Any) -> Any:
        # AgentRequest may carry usage in extras; we read defensively so a
        # missing field never breaks telemetry.
        request = ctx.request
        tokens_in = getattr(request, "tokens_in", None) or 0
        tokens_out = getattr(request, "tokens_out", None) or 0
        if not tokens_in and not tokens_out:
            # Nothing useful to record; still emit so consumers can see the
            # request happened (helps when providers stop emitting usage).
            tokens_in = tokens_out = 0
        telemetry.write("token_usage", {
            "session_id": ctx.session_id,
            "agent_id": ctx.agent_id,
            "tokens_in": int(tokens_in or 0),
            "tokens_out": int(tokens_out or 0),
        })
        return None


class ToolOutcomeHook(HookBase):
    """PRE_EXECUTE: mark a tool call as starting. Status defaults to ``ok``."""

    phase = "PRE_EXECUTE"
    name = "poc_tool_outcome"
    priority = 90

    async def run(self, ctx: Any) -> Any:
        request = ctx.request
        tool = getattr(request, "tool_name", "") or "unknown"
        telemetry.write("tool_outcome", {
            "event": "start",
            "session_id": ctx.session_id,
            "agent_id": ctx.agent_id,
            "tool": tool,
            "status": "ok",
        })
        return None


class ToolErrorHook(HookBase):
    """ON_ERROR: tag the most recent tool call as failed when an exception
    escapes the executor."""

    phase = "ON_ERROR"
    name = "poc_tool_error"
    priority = 90

    async def run(self, ctx: Any) -> Any:
        request = ctx.request
        tool = getattr(request, "tool_name", "") or "unknown"
        err = ctx.error
        telemetry.write("tool_outcome", {
            "event": "end",
            "session_id": ctx.session_id,
            "agent_id": ctx.agent_id,
            "tool": tool,
            "status": "error",
            "error_type": type(err).__name__ if err else "unknown",
            "error_message": str(err) if err else "",
        })
        return None


ALL_HOOKS = [
    CallVolumeStartHook(),
    CallVolumeEndHook(),
    IdentityHook(),
    TokenUsageHook(),
    ToolOutcomeHook(),
    ToolErrorHook(),
]