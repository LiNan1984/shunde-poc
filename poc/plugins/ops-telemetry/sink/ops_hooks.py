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

import sys
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
                return _continue()
        return _StubHookBase


def _make_hook_result() -> Any:
    """Host ``HookResult`` when QwenPaw is importable; duck-typed stub otherwise.

    2.2.2b1 ``HookRegistry.run`` reads ``result.action``. Returning ``None``
    raises ``AttributeError`` and aborts the phase.
    """
    try:
        from qwenpaw.runtime.hooks import HookResult  # type: ignore[import-not-found]
        return HookResult
    except ImportError:
        class _StubHookResult:
            def __init__(self, action: str = "continue", payload: Any = None) -> None:
                self.action = action
                self.payload = payload

        return _StubHookResult


HookBase = _make_hook_base()
HookResult = _make_hook_result()


def _continue() -> Any:
    return HookResult()


def _observe(run):
    """Run the hook body, always return HookResult so HookRegistry.run cannot crash."""

    async def wrapped(self, ctx: Any) -> Any:
        try:
            await run(self, ctx)
        except Exception as exc:
            print(
                f"telemetry hook {getattr(self, 'name', type(self).__name__)} failed: {exc}",
                file=sys.stderr,
            )
        return _continue()

    wrapped.__name__ = getattr(run, "__name__", "run")
    wrapped.__doc__ = run.__doc__
    return wrapped


def _emit(category: str, ctx: Any, extra: dict[str, Any] | None = None) -> None:
    """Write one event into the same sandbox root MCP will read."""
    payload = {
        "session_id": getattr(ctx, "session_id", ""),
        "agent_id": getattr(ctx, "agent_id", ""),
        "root_session_id": getattr(ctx, "root_session_id", ""),
        "root_agent_id": getattr(ctx, "root_agent_id", ""),
        "workspace_dir": str(ctx.workspace_dir) if getattr(ctx, "workspace_dir", None) else "",
    }
    if extra:
        payload.update(extra)
    telemetry.write(category, payload, workspace_dir=getattr(ctx, "workspace_dir", None))


def _phase(name: str) -> Any:
    """Resolve a phase *attribute name* to the host ``Phase`` enum member.

    ``HookRegistry.register`` requires an actual ``Phase`` instance
    (``QwenPaw/src/qwenpaw/runtime/hooks.py``) — plain strings, even
    correctly-spelled ones, are rejected with a ``TypeError`` and the
    plugin registration path swallows that error at debug level, so the
    hook would silently never fire. When qwenpaw isn't importable (CI
    unit tests) we fall back to the enum's lowercase string *value*.
    """
    try:
        from qwenpaw.runtime.phases import Phase  # type: ignore[import-not-found]
        return Phase[name]
    except ImportError:
        return name.lower()


class CallVolumeStartHook(HookBase):
    """PRE_DISPATCH: emit session identity + start timestamp."""

    phase = _phase("PRE_DISPATCH")
    name = "poc_call_volume_start"
    priority = 90

    @_observe
    async def run(self, ctx: Any) -> Any:
        _emit("call_volume", ctx, {"event": "start"})
        # Stash a start time for the latency hook pair.
        ctx.extras["poc_dispatch_start"] = time.monotonic()


class CallVolumeEndHook(HookBase):
    """POST_DISPATCH: emit end + computed latency_ms."""

    phase = _phase("POST_DISPATCH")
    name = "poc_call_volume_end"
    priority = 110

    @_observe
    async def run(self, ctx: Any) -> Any:
        start = ctx.extras.get("poc_dispatch_start")
        extra: dict[str, Any] = {"event": "end"}
        if isinstance(start, (int, float)):
            extra["latency_ms"] = round((time.monotonic() - start) * 1000.0, 2)
            _emit("latency", ctx, extra)
        _emit("call_volume", ctx, extra)


class IdentityHook(HookBase):
    """PRE_AGENT_BUILD: capture identity, redundant with call_volume_start
    but guaranteed to fire even when PRE_DISPATCH is short-circuited."""

    phase = _phase("PRE_AGENT_BUILD")
    name = "poc_identity"
    priority = 90

    @_observe
    async def run(self, ctx: Any) -> Any:
        _emit("identity", ctx)


class TokenUsageHook(HookBase):
    """POST_RESPONSE: emit tokens_in / tokens_out if exposed."""

    phase = _phase("POST_RESPONSE")
    name = "poc_token_usage"
    priority = 90

    @_observe
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
        _emit("token_usage", ctx, {
            "tokens_in": int(tokens_in or 0),
            "tokens_out": int(tokens_out or 0),
        })


class ToolOutcomeHook(HookBase):
    """PRE_EXECUTE: mark a tool call as starting. Status defaults to ``ok``."""

    phase = _phase("PRE_EXECUTE")
    name = "poc_tool_outcome"
    priority = 90

    @_observe
    async def run(self, ctx: Any) -> Any:
        request = ctx.request
        tool = getattr(request, "tool_name", "") or "unknown"
        _emit("tool_outcome", ctx, {
            "event": "start",
            "tool": tool,
            "status": "ok",
        })


class ToolErrorHook(HookBase):
    """ON_ERROR: tag the most recent tool call as failed when an exception
    escapes the executor."""

    phase = _phase("ON_ERROR")
    name = "poc_tool_error"
    priority = 90

    @_observe
    async def run(self, ctx: Any) -> Any:
        request = ctx.request
        tool = getattr(request, "tool_name", "") or "unknown"
        err = ctx.error
        _emit("tool_outcome", ctx, {
            "event": "end",
            "tool": tool,
            "status": "error",
            "error_type": type(err).__name__ if err else "unknown",
            "error_message": str(err) if err else "",
        })


ALL_HOOKS = [
    CallVolumeStartHook(),
    CallVolumeEndHook(),
    IdentityHook(),
    TokenUsageHook(),
    ToolOutcomeHook(),
    ToolErrorHook(),
]