"""stdio smoke test for the two MCP servers.

Sends JSON-RPC over stdin and reads responses from stdout to confirm:
- excel-guard MCP exposes 3 tools (detect_corrupt_workbook, detect_encoding,
  chunk_large_workbook).
- report-visualizer MCP exposes 7 tools (pivot_table_tool, render_bar_tool,
  render_line_tool, render_pie_tool, render_scatter_tool, render_heatmap_tool,
  render_docx_report_tool).

This is the closest automated verification short of opening the QwenPaw
Console GUI. Run from the repo root with the venv active:

    source .venv/bin/activate
    python scripts/mcp_stdio_smoke.py

The script exits 0 if every server initializes and reports the expected
number of tools; non-zero otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "poc.excel_guard_mcp": 3,
    "poc.report_mcp": 7,
}


def _list_tools(module: str) -> list[str]:
    """Start the server as a subprocess and confirm it speaks JSON-RPC.

    FastMCP uses stdio for both request and response channels; the server
    must receive ``initialize`` and reply before any other request. We send
    only the initialize handshake — that's enough to prove the module is
    importable, registers with FastMCP, and isn't crashing on startup.

    Tool enumeration is then verified separately by the in-process unit
    tests in ``poc/tests/test_mcp_server.py`` and
    ``poc/tests/test_report_mcp_server.py``, which are the
    authoritative registration checks (those tests can't lie about how
    many tools the server exposes).
    """
    payload = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05",
                               "capabilities": {},
                               "clientInfo": {"name": "smoke", "version": "0"}}})
        + "\n"
    )
    proc = subprocess.run(
        [sys.executable, "-m", module],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=15,
    )
    out = proc.stdout.strip()
    # Look for an initialize response containing our id=1.
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == 1 and "result" in msg:
            server_info = msg["result"].get("serverInfo", {})
            return [server_info.get("name", module)]
    return []


# In-process tool enumeration is the same code the unit tests use, so we
# reuse it here rather than re-implementing MCP stdio plumbing.
import asyncio  # noqa: E402

REPO_ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT_PATH))
from poc.excel_guard_mcp.server import mcp as _excel_mcp  # noqa: E402
from poc.report_mcp.server import mcp as _report_mcp  # noqa: E402


def _inproc_tool_names(mcp_obj) -> list[str]:
    return sorted(t.name for t in asyncio.run(mcp_obj.list_tools()))


def main() -> int:
    rc = 0
    summary = []
    pairs = [
        ("poc.excel_guard_mcp", 3, _excel_mcp, _list_tools),
        ("poc.report_mcp", 7, _report_mcp, _list_tools),
    ]
    for module, expected_count, mcp_obj, stdio_fn in pairs:
        try:
            stdio_names = stdio_fn(module)
            inproc_names = _inproc_tool_names(mcp_obj)
        except subprocess.TimeoutExpired:
            print(f"FAIL {module}: subprocess timeout")
            rc = 1
            continue
        except Exception as exc:  # noqa: BLE001 - top-level summary
            print(f"FAIL {module}: {type(exc).__name__}: {exc}")
            rc = 1
            continue
        ok = len(inproc_names) == expected_count
        summary.append({
            "module": module,
            "expected": expected_count,
            "stdio_server_name": stdio_names[0] if stdio_names else None,
            "inproc_tool_count": len(inproc_names),
            "inproc_tools": inproc_names,
            "ok": ok,
        })
        if not ok or not stdio_names:
            rc = 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())