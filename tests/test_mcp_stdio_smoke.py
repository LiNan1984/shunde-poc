# -*- coding: utf-8 -*-
"""Drive the shipped ``scripts/mcp_stdio_smoke.py`` on the real path.

Asserts four MCP modules (excel-guard / report-visualizer / ops-data / kb-qa)
are in the smoke contract and that running the script exits 0 with four ok
entries totaling 21 tools (5+7+3+6). kb-qa must also run initialize twice
and return real fixture hit text.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SMOKE = WORKSPACE / "scripts" / "mcp_stdio_smoke.py"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("mcp_stdio_smoke", SMOKE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Loading executes top-level FastMCP imports; keep cwd on repo root.
    sys.path.insert(0, str(WORKSPACE))
    spec.loader.exec_module(mod)
    return mod


def test_smoke_script_exists_and_expects_four_mcps() -> None:
    assert SMOKE.is_file(), f"missing smoke script at {SMOKE}"
    mod = _load_smoke_module()
    expected = mod.EXPECTED
    assert set(expected) == {
        "poc.excel_guard_mcp",
        "poc.report_mcp",
        "poc.ops_mcp",
        "poc.kb_mcp",
    }
    assert expected["poc.excel_guard_mcp"] == 5
    assert expected["poc.report_mcp"] == 7
    assert expected["poc.ops_mcp"] == 3
    assert expected["poc.kb_mcp"] == 6
    assert sum(expected.values()) == 21


def test_smoke_script_run_covers_four_servers() -> None:
    """Execute the real entry point; parse its JSON summary."""
    proc = subprocess.run(
        [sys.executable, str(SMOKE)],
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, (
        f"smoke failed rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    summary = json.loads(proc.stdout)
    assert isinstance(summary, list)
    assert len(summary) == 4, f"expected 4 server rows, got {summary}"
    by_module = {row["module"]: row for row in summary}
    assert set(by_module) == {
        "poc.excel_guard_mcp",
        "poc.report_mcp",
        "poc.ops_mcp",
        "poc.kb_mcp",
    }
    for row in summary:
        assert row["ok"] is True, row
        assert row["stdio_server_name"], row
        assert row["inproc_tool_count"] == row["expected"], row
    total = sum(row["inproc_tool_count"] for row in summary)
    assert total == 21
    kb = by_module["poc.kb_mcp"]
    assert kb["initialize_1"] is True
    assert kb["initialize_2"] is True
    fixture = kb["fixture_ingest_search"]
    assert fixture["ok"] is True
    assert fixture["n_chunks"] >= 1
    assert fixture["token_in_hits"] is True
    assert fixture["hit_preview"]
