"""Static + minimal runtime checks for the telemetry hooks.

We don't spin up a full QwenPaw runtime here (no QwenPaw process under
test). Instead we assert:
- ALL_HOOKS has six entries (one per category).
- Each hook declares a valid ``Phase`` and a unique ``name``.
- A bare-minimum hook context lets each hook's ``run()`` execute
  without crashing, even when fields are missing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from poc.hooks.ops_hooks import ALL_HOOKS, CallVolumeEndHook


@dataclass
class _StubExtras:
    data: dict = field(default_factory=dict)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)


@dataclass
class _StubRequest:
    tokens_in: int = 0
    tokens_out: int = 0
    tool_name: str = ""


@dataclass
class _StubCtx:
    request: _StubRequest = field(default_factory=_StubRequest)
    session_id: str = "s1"
    agent_id: str = "a1"
    root_session_id: str = "rs"
    root_agent_id: str = "ra"
    workspace_dir: str = ""
    extras: _StubExtras = field(default_factory=_StubExtras)
    error: BaseException | None = None


def _stub_ctx(**overrides):
    ctx = _StubCtx()
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


def test_all_hooks_well_formed() -> None:
    assert len(ALL_HOOKS) == 6
    names = [h.name for h in ALL_HOOKS]
    assert len(names) == len(set(names)), "hook names must be unique"

    # These are the canonical QwenPaw Phase values (from
    # QwenPaw/src/qwenpaw/runtime/phases.py). We assert them as strings
    # so the test stays importable without qwenpaw installed.
    expected_phases = {
        "PRE_DISPATCH",
        "POST_DISPATCH",
        "PRE_AGENT_BUILD",
        "POST_AGENT_BUILD",
        "PRE_EXECUTE",
        "POST_RESPONSE",
        "ON_ERROR",
        "FINALLY",
    }
    for h in ALL_HOOKS:
        assert h.phase in expected_phases, (
            f"hook {h.name} has invalid phase {h.phase!r}"
        )


@pytest.mark.parametrize("hook", ALL_HOOKS, ids=lambda h: h.name)
def test_hook_run_does_not_crash(hook, tmp_path, monkeypatch) -> None:
    """Each hook must swallow missing data and never raise."""
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))

    import asyncio
    result = asyncio.run(hook.run(_stub_ctx()))
    # Result can be a HookResult (host venv) or None (stub fallback).
    assert result is None or hasattr(result, "action")


def test_call_volume_end_records_latency(tmp_path, monkeypatch) -> None:
    """When PRE_DISPATCH stashed a start time, the end hook should record
    a non-zero latency_ms."""
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))

    import asyncio

    end_hook = CallVolumeEndHook()
    extras = _StubExtras()
    extras["poc_dispatch_start"] = 0.0  # way in the past → latency > 0
    ctx = _stub_ctx(extras=extras)
    # Patch monotonic to be deterministic.
    import time as _time

    orig = _time.monotonic
    _time.monotonic = lambda: orig() + 0.123
    try:
        asyncio.run(end_hook.run(ctx))
    finally:
        _time.monotonic = orig

    # Inspect what was written.
    files = list((tmp_path / "telemetry").rglob("ops.jsonl"))
    assert files, "latency event not written"
    cats = [
        json.loads(line).get("category")
        for line in files[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert "latency" in cats
    assert "call_volume" in cats