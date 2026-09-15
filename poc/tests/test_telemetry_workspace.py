# -*- coding: utf-8 -*-
"""Write-side / read-side telemetry path on the published hooks and MCP.

Drives ``poc.hooks.telemetry.write`` and ``hook.run``; does not reimplement
the sink. Proves empty env no longer silent-skips when ctx.workspace_dir is
set, and that ops-data reads the same ``telemetry/**/ops.jsonl`` the hook wrote.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from poc.hooks import telemetry
from poc.hooks.ops_hooks import ALL_HOOKS, CallVolumeStartHook, ToolOutcomeHook
from poc.ops_mcp import server_lib
from poc.ops_mcp.server_lib import list_telemetry_files, summarize_calls

REPO = Path(__file__).resolve().parents[2]
QWENPAW_PY = REPO / "QwenPaw" / ".venv" / "bin" / "python"


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
    tool_name: str = "excel_guard__describe_workbook"


@dataclass
class _StubCtx:
    request: _StubRequest = field(default_factory=_StubRequest)
    session_id: str = "s1"
    agent_id: str = "a1"
    root_session_id: str = "rs"
    root_agent_id: str = "ra"
    workspace_dir: Path | str | None = None
    extras: _StubExtras = field(default_factory=_StubExtras)
    error: BaseException | None = None


@pytest.fixture(autouse=True)
def _reset_sink(monkeypatch) -> None:
    telemetry._WRITTEN_DIRS.clear()
    monkeypatch.delenv("POC_WORKSPACE", raising=False)
    monkeypatch.delenv("QWENPAW_WORKING_DIR", raising=False)


def test_hook_writes_jsonl_from_ctx_workspace_without_env(tmp_path: Path) -> None:
    """(a) No POC_WORKSPACE; ctx.workspace_dir is enough to produce ops.jsonl."""
    ctx = _StubCtx(workspace_dir=tmp_path)
    asyncio.run(CallVolumeStartHook().run(ctx))
    files = list((tmp_path / "telemetry").rglob("ops.jsonl"))
    assert files, "hook must write ops.jsonl using ctx.workspace_dir"
    rec = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert rec["category"] == "call_volume"
    assert rec["session_id"] == "s1"


def test_mcp_reads_same_root_the_hook_just_wrote(tmp_path: Path, monkeypatch) -> None:
    """(b) Hook writes via ctx; MCP sandbox env points at that same root."""
    ctx = _StubCtx(workspace_dir=tmp_path)
    asyncio.run(ToolOutcomeHook().run(ctx))
    written = list((tmp_path / "telemetry").rglob("ops.jsonl"))
    assert written, "write side produced no JSONL"
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    listing = list_telemetry_files()
    assert listing["ok"] is True
    assert listing["count"] >= 1
    assert any(str(written[0]) == p or Path(p) == written[0] for p in listing["files"])
    summary = summarize_calls()
    assert summary["ok"] is True
    assert summary["counts"]["total"] >= 1
    assert "excel_guard__describe_workbook" in summary["counts"]["by_tool"]


def test_skip_is_observable_when_no_workspace(capsys) -> None:
    path = telemetry.write("call_volume", {"session_id": "s1"})
    assert path is None
    err = capsys.readouterr().err
    assert "telemetry skip" in err
    assert "POC_WORKSPACE" in err


def test_invalid_env_does_not_block_ctx_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POC_WORKSPACE", "/no/such/path/__no_such__")
    asyncio.run(CallVolumeStartHook().run(_StubCtx(workspace_dir=tmp_path)))
    assert list((tmp_path / "telemetry").rglob("ops.jsonl"))


def test_write_prefers_mcp_env_over_agent_workspace(
    tmp_path: Path, monkeypatch
) -> None:
    """When MCP sandbox env and ctx.workspace_dir diverge, write the MCP root."""
    mcp_root = tmp_path / "mcp"
    agent_root = tmp_path / "agent"
    mcp_root.mkdir()
    agent_root.mkdir()
    monkeypatch.setenv("POC_WORKSPACE", str(mcp_root))
    ctx = _StubCtx(workspace_dir=agent_root)
    result = asyncio.run(CallVolumeStartHook().run(ctx))
    assert result is not None
    assert hasattr(result, "action")
    written = list((mcp_root / "telemetry").rglob("ops.jsonl"))
    assert written, "JSONL must land under POC_WORKSPACE so MCP can list it"
    listing = list_telemetry_files()
    assert listing["ok"] is True
    assert listing["count"] >= 1
    assert any(Path(p) == written[0] for p in listing["files"])
    summary = summarize_calls()
    assert summary["ok"] is True
    assert summary["counts"]["total"] >= 1


def test_server_lib_telemetry_root_calls_shared_resolver() -> None:
    import inspect

    src = inspect.getsource(server_lib._telemetry_root)
    assert "resolve_workspace_root" in src


def test_list_without_sandbox_env_is_unavailable() -> None:
    listing = list_telemetry_files()
    assert listing["ok"] is False
    assert listing["count"] == 0


def test_pin_host_sandbox_sets_env_when_unset(
    tmp_path: Path, monkeypatch
) -> None:
    root = telemetry.pin_host_sandbox([tmp_path / "missing", tmp_path])
    assert root == tmp_path.resolve()
    assert Path(os.environ["POC_WORKSPACE"]) == tmp_path.resolve()
    monkeypatch.setenv("POC_WORKSPACE", os.environ["POC_WORKSPACE"])
    ctx = _StubCtx(workspace_dir=tmp_path / "agent")
    (tmp_path / "agent").mkdir()
    asyncio.run(CallVolumeStartHook().run(ctx))
    assert list((tmp_path / "telemetry").rglob("ops.jsonl"))
    listing = list_telemetry_files()
    assert listing["ok"] is True
    assert listing["count"] >= 1


def test_plugin_bootstrap_calls_pin_host_sandbox() -> None:
    src = (REPO / "poc" / "plugins" / "ops-telemetry" / "plugin.py").read_text(
        encoding="utf-8"
    )
    assert "pin_host_sandbox" in src
    assert "from sink.ops_hooks import ALL_HOOKS" in src
    assert "write_plugin_loaded" in src


def test_plugin_ships_identical_sink() -> None:
    plugin = REPO / "poc" / "plugins" / "ops-telemetry" / "sink"
    assert (plugin / "telemetry.py").read_bytes() == (
        REPO / "poc" / "hooks" / "telemetry.py"
    ).read_bytes()
    assert (plugin / "ops_hooks.py").read_bytes() == (
        REPO / "poc" / "hooks" / "ops_hooks.py"
    ).read_bytes()


def test_write_fans_out_to_known_mcp_sandbox(
    tmp_path: Path, monkeypatch
) -> None:
    """Agent POC_WORKSPACE must not hide the MCP sandbox from the writer."""
    mcp_root = tmp_path / "mcp"
    agent_root = tmp_path / "agent"
    mcp_root.mkdir()
    agent_root.mkdir()
    monkeypatch.setattr(telemetry, "KNOWN_MCP_SANDBOXES", (mcp_root,))
    monkeypatch.setenv("POC_WORKSPACE", str(agent_root))
    telemetry.write("call_volume", {"session_id": "s1"})
    assert list((mcp_root / "telemetry").rglob("ops.jsonl"))
    assert list((agent_root / "telemetry").rglob("ops.jsonl"))
    monkeypatch.setenv("POC_WORKSPACE", str(mcp_root))
    listing = list_telemetry_files()
    assert listing["ok"] is True
    assert listing["count"] >= 1
    summary = summarize_calls()
    assert summary["ok"] is True
    assert summary["counts"]["total"] >= 1


def test_pin_overrides_qwenpaw_home_poc_workspace(
    tmp_path: Path, monkeypatch
) -> None:
    mcp_root = tmp_path / "mcp"
    qwen_home = tmp_path / ".qwenpaw"
    mcp_root.mkdir()
    qwen_home.mkdir()
    monkeypatch.setenv("POC_WORKSPACE", str(qwen_home))
    root = telemetry.pin_host_sandbox([mcp_root])
    assert root == mcp_root.resolve()
    monkeypatch.setenv("POC_WORKSPACE", os.environ["POC_WORKSPACE"])
    assert Path(os.environ["POC_WORKSPACE"]) == mcp_root.resolve()


def test_resolve_skips_qwenpaw_home_when_known_sandbox_exists(
    tmp_path: Path, monkeypatch
) -> None:
    mcp_root = tmp_path / "mcp"
    qwen_home = tmp_path / ".qwenpaw"
    mcp_root.mkdir()
    qwen_home.mkdir()
    monkeypatch.setattr(telemetry, "KNOWN_MCP_SANDBOXES", (mcp_root,))
    monkeypatch.setenv("POC_WORKSPACE", str(qwen_home))
    assert telemetry.resolve_workspace_root() == mcp_root.resolve()


def test_plugin_loaded_event_is_visible_to_mcp(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    path = telemetry.write_plugin_loaded(["poc_identity", "poc_tool_outcome"])
    assert path is not None
    rec = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["event"] == "plugin_register"
    listing = list_telemetry_files()
    assert listing["ok"] is True
    assert listing["count"] >= 1


def test_pin_host_sandbox_does_not_override_existing_env(
    tmp_path: Path, monkeypatch
) -> None:
    mcp_root = tmp_path / "mcp"
    other = tmp_path / "other"
    mcp_root.mkdir()
    other.mkdir()
    monkeypatch.setenv("POC_WORKSPACE", str(mcp_root))
    root = telemetry.pin_host_sandbox([other])
    assert root == mcp_root.resolve()
    assert Path(os.environ["POC_WORKSPACE"]) == mcp_root.resolve()


def test_pin_sets_poc_workspace_even_when_qwenpaw_working_dir_is_set(
    tmp_path: Path, monkeypatch
) -> None:
    """Host QwenPaw exports QWENPAW_WORKING_DIR=~/.qwenpaw; that is not MCP."""
    mcp_root = tmp_path / "mcp"
    qwen_root = tmp_path / "qwenpaw"
    agent_root = tmp_path / "agent"
    mcp_root.mkdir()
    qwen_root.mkdir()
    agent_root.mkdir()
    monkeypatch.setenv("QWENPAW_WORKING_DIR", str(qwen_root))
    root = telemetry.pin_host_sandbox([mcp_root])
    assert root == mcp_root.resolve()
    monkeypatch.setenv("POC_WORKSPACE", os.environ["POC_WORKSPACE"])
    asyncio.run(CallVolumeStartHook().run(_StubCtx(workspace_dir=agent_root)))
    assert list((mcp_root / "telemetry").rglob("ops.jsonl"))
    listing = list_telemetry_files()
    assert listing["ok"] is True
    assert listing["count"] >= 1


def test_filesystem_root_sandbox_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("POC_WORKSPACE", "/")
    assert telemetry.resolve_workspace_root() is None
    path = telemetry.write("call_volume", {"session_id": "s1"})
    assert path is None
    listing = list_telemetry_files()
    assert listing["ok"] is False


def test_write_swallows_unserializable_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    path = telemetry.write("call_volume", {"session_id": "s1", "bad": object()})
    assert path is None


def test_hook_run_returns_result_when_extras_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    ctx = _StubCtx(workspace_dir=tmp_path)
    ctx.extras = None  # type: ignore[assignment]
    result = asyncio.run(CallVolumeStartHook().run(ctx))
    assert result is not None
    assert hasattr(result, "action")


def test_all_six_hooks_share_the_same_jsonl(tmp_path: Path) -> None:
    ctx = _StubCtx(workspace_dir=tmp_path)
    ctx.extras["poc_dispatch_start"] = 0.0
    for hook in ALL_HOOKS:
        asyncio.run(hook.run(ctx))
    files = list((tmp_path / "telemetry").rglob("ops.jsonl"))
    assert len(files) == 1
    cats = {
        json.loads(line)["category"]
        for line in files[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert "call_volume" in cats
    assert "identity" in cats
    assert "token_usage" in cats
    assert "tool_outcome" in cats


@pytest.mark.skipif(not QWENPAW_PY.is_file(), reason="QwenPaw venv missing")
def test_phase_is_enum_and_registers_on_qwenpaw_222() -> None:
    """On the host 2.2.2b1 interpreter, phase must be Phase, not str."""
    script = (
        "import sys; sys.path.insert(0, %r); "
        "from poc.hooks.ops_hooks import ALL_HOOKS; "
        "from qwenpaw.runtime.phases import Phase; "
        "from qwenpaw.runtime.hooks import HookBase, HookRegistry; "
        "assert all(isinstance(h, HookBase) for h in ALL_HOOKS); "
        "assert all(isinstance(h.phase, Phase) for h in ALL_HOOKS), "
        "[(h.name, type(h.phase), h.phase) for h in ALL_HOOKS]; "
        "reg = HookRegistry(); "
        "[reg.register(h) for h in ALL_HOOKS]; "
        "n = sum(len(reg.hooks_for(p)) for p in Phase); "
        "assert n == 6, n; "
        "print('registered', n)"
    ) % str(REPO)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(
        [str(QWENPAW_PY), "-c", script],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "registered 6" in proc.stdout


@pytest.mark.skipif(not QWENPAW_PY.is_file(), reason="QwenPaw venv missing")
def test_hook_registry_run_writes_jsonl(tmp_path: Path) -> None:
    """2.2.2b1 HookRegistry.run does result.action; None would AttributeError."""
    mcp_root = tmp_path / "mcp"
    agent_root = tmp_path / "agent"
    mcp_root.mkdir()
    agent_root.mkdir()
    script = (
        "import asyncio, os, sys\n"
        "from pathlib import Path\n"
        "from types import SimpleNamespace\n"
        "sys.path.insert(0, os.environ['REPO'])\n"
        "from qwenpaw.runtime.hooks import HookRegistry\n"
        "from qwenpaw.runtime.phases import Phase\n"
        "from poc.hooks.ops_hooks import ALL_HOOKS\n"
        "mcp_root = Path(os.environ['MCP_ROOT'])\n"
        "agent_root = Path(os.environ['AGENT_ROOT'])\n"
        "\n"
        "class Ctx:\n"
        "    request = SimpleNamespace(tokens_in=0, tokens_out=0, tool_name='t')\n"
        "    session_id = 's1'\n"
        "    agent_id = 'a1'\n"
        "    root_session_id = 'rs'\n"
        "    root_agent_id = 'ra'\n"
        "    workspace_dir = agent_root\n"
        "    extras = {}\n"
        "    error = None\n"
        "\n"
        "async def main():\n"
        "    reg = HookRegistry()\n"
        "    for h in ALL_HOOKS:\n"
        "        reg.register(h)\n"
        "    ctx = Ctx()\n"
        "    for phase in Phase:\n"
        "        result = await reg.run(phase, ctx)\n"
        "        assert result is not None\n"
        "        assert result.action is not None\n"
        "    files = list((mcp_root / 'telemetry').rglob('ops.jsonl'))\n"
        "    assert files, 'JSONL must land on MCP sandbox'\n"
        "    print('registry_run_ok')\n"
        "\n"
        "asyncio.run(main())\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["REPO"] = str(REPO)
    env["POC_WORKSPACE"] = str(mcp_root)
    env["MCP_ROOT"] = str(mcp_root)
    env["AGENT_ROOT"] = str(agent_root)
    env.pop("QWENPAW_WORKING_DIR", None)
    proc = subprocess.run(
        [str(QWENPAW_PY), "-c", script],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "registry_run_ok" in proc.stdout
