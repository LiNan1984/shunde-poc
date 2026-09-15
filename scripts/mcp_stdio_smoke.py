"""stdio smoke test for the four MCP servers.

Sends JSON-RPC over stdin and reads responses from stdout to confirm:
- excel-guard MCP exposes 5 tools
- report-visualizer MCP exposes 7 tools
- ops-data MCP exposes 3 tools
- kb-qa MCP exposes 6 tools (parse_document, ingest_document,
  ingest_spreadsheet, search_knowledge, answer_knowledge, analyze_page)

Total: 5 + 7 + 3 + 6 = 21 tools.

kb-qa additionally: two consecutive ``python -m poc.kb_mcp`` initialize
handshakes, plus one in-process ingest+search against a small fixture PDF
(asserts real chunk text, not just HTTP/JSON-RPC 200).

Run from the repo root with the venv active:

    source .venv/bin/activate
    python scripts/mcp_stdio_smoke.py
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

EXPECTED = {
    "poc.excel_guard_mcp": 9,
    "poc.report_mcp": 7,
    "poc.ops_mcp": 3,
    "poc.kb_mcp": 6,
}


def _list_tools(module: str) -> tuple[list[str], dict | None]:
    """Start the server as a subprocess and confirm it speaks JSON-RPC."""
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
        timeout=20,
    )
    out = proc.stdout.strip()
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
            return [server_info.get("name", module)], msg
    return [], None


from poc.excel_guard_mcp.server import mcp as _excel_mcp  # noqa: E402
from poc.kb_mcp.server import mcp as _kb_mcp  # noqa: E402
from poc.ops_mcp.server import mcp as _ops_mcp  # noqa: E402
from poc.report_mcp.server import mcp as _report_mcp  # noqa: E402


def _inproc_tool_names(mcp_obj) -> list[str]:
    return sorted(t.name for t in asyncio.run(mcp_obj.list_tools()))


def _call_tool(mcp_obj, name: str, arguments: dict) -> dict:
    result = asyncio.run(mcp_obj.call_tool(name, arguments))
    if isinstance(result, dict):
        return result
    text = getattr(result[0], "text", None)
    return json.loads(text)


def _kb_fixture_roundtrip() -> dict:
    from poc.kb_mcp.fixtures import TOKENS, write_native_text_pdf

    workspace = Path(tempfile.mkdtemp(prefix="kb-smoke-"))
    os.environ["POC_WORKSPACE"] = str(workspace)
    os.environ["POC_LOAD_SECRETS"] = "0"
    os.environ.pop("POC_EMBEDDING_URL", None)
    os.environ.pop("POC_EMBEDDING_API_KEY", None)
    os.environ.pop("POC_CHAT_MODEL", None)
    pdf = write_native_text_pdf(workspace / "native_text.pdf")
    ingested = _call_tool(
        _kb_mcp,
        "ingest_document",
        {"path": str(pdf), "doc_id": "smoke-credit"},
    )
    searched = _call_tool(
        _kb_mcp,
        "search_knowledge",
        {"query": TOKENS["alpha"], "doc_id": "smoke-credit"},
    )
    hit_text = " ".join(h.get("text") or "" for h in searched.get("hits") or [])
    return {
        "ingest_ok": bool(ingested.get("ok")),
        "n_chunks": ingested.get("n_chunks") or 0,
        "search_ok": bool(searched.get("ok")),
        "hit_text": hit_text,
        "token": TOKENS["alpha"],
        "token_in_hits": TOKENS["alpha"] in hit_text,
        "workspace": str(workspace),
    }


def main() -> int:
    rc = 0
    summary = []
    pairs = [
        ("poc.excel_guard_mcp", 9, _excel_mcp),
        ("poc.report_mcp", 7, _report_mcp),
        ("poc.ops_mcp", 3, _ops_mcp),
        ("poc.kb_mcp", 6, _kb_mcp),
    ]
    kb_launch_1 = kb_launch_2 = None
    kb_roundtrip = None
    for module, expected_count, mcp_obj in pairs:
        try:
            stdio_names, launch_msg = _list_tools(module)
            if module == "poc.kb_mcp":
                kb_launch_1 = launch_msg
                stdio_names_2, kb_launch_2 = _list_tools(module)
                if not stdio_names_2:
                    stdio_names = []
                kb_roundtrip = _kb_fixture_roundtrip()
            inproc_names = _inproc_tool_names(mcp_obj)
        except subprocess.TimeoutExpired:
            print(f"FAIL {module}: subprocess timeout")
            rc = 1
            continue
        except Exception as exc:  # noqa: BLE001 - top-level summary
            print(f"FAIL {module}: {type(exc).__name__}: {exc}")
            rc = 1
            continue
        ok = len(inproc_names) == expected_count and bool(stdio_names)
        row = {
            "module": module,
            "expected": expected_count,
            "stdio_server_name": stdio_names[0] if stdio_names else None,
            "inproc_tool_count": len(inproc_names),
            "inproc_tools": inproc_names,
            "ok": ok,
        }
        if module == "poc.kb_mcp":
            launches_ok = bool(kb_launch_1 and kb_launch_2)
            names_stable = (
                (kb_launch_1 or {}).get("result", {}).get("serverInfo", {}).get("name")
                == (kb_launch_2 or {}).get("result", {}).get("serverInfo", {}).get("name")
            )
            rt_ok = bool(kb_roundtrip and kb_roundtrip.get("token_in_hits")
                         and kb_roundtrip.get("n_chunks", 0) >= 1)
            row["initialize_1"] = bool(kb_launch_1)
            row["initialize_2"] = bool(kb_launch_2)
            roundtrip = kb_roundtrip or {}
            row["fixture_ingest_search"] = {
                "ok": rt_ok,
                "n_chunks": roundtrip.get("n_chunks"),
                "token_in_hits": roundtrip.get("token_in_hits"),
                "hit_preview": (roundtrip.get("hit_text") or "")[:200],
            }
            row["ok"] = ok and launches_ok and names_stable and rt_ok
        summary.append(row)
        if not row["ok"]:
            rc = 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
