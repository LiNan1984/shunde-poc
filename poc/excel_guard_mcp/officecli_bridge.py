# -*- coding: utf-8 -*-
"""Guarded officecli bridge: subprocess wrapper + sandboxed write/verify tools.

officecli (https://github.com/iOfficeAI/OfficeCLI) supplements the openpyxl
write path with capabilities openpyxl handles poorly (pivot tables, charts,
conditional formatting, formula auto-evaluation on write) and adds an OpenXML
schema validator plus a rendered-screenshot loop. Every call from this module
is wrapped in the same guard pipeline as the read tools:

* workspace containment via :func:`_resolve_allowed_path` (both the workbook
  and any output file must live inside ``POC_WORKSPACE``),
* corrupt/oversize preflight before any mutation,
* verb allowlist on batch items (no ``raw-set``/``import``/``create`` — the
  CLI is never handed an arbitrary verb),
* ``OFFICECLI_RESIDENT_FLUSH=each`` so openpyxl-side post-checks always see
  flushed bytes (H1-style TOCTOU: we never hold a resident across readers).

The CLI itself is executed as a subprocess with ``--json`` (envelope:
``{"success": bool, "data": ..., "error": {"error", "code"}}``) and never
receives shell interpolation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .guards import _check_file_size, _resolve_allowed_path, detect_corrupt_workbook
from .readers import audit_workbook

logger = logging.getLogger(__name__)

# Verbs safe to forward through `batch`. Deliberately excludes create/import/
# dump/raw-set/move-part style verbs: the bridge exposes document edits only,
# never arbitrary part surgery or filesystem-side imports.
_EDIT_VERBS = frozenset({"add", "set", "remove", "move", "swap"})
# Read-only verbs forwarded to a dedicated inspection tool.
_READ_VERBS = frozenset({"get", "query"})

_DEFAULT_TIMEOUT_S = 120.0


def _timeout() -> float:
    raw = os.environ.get("POC_OFFICECLI_TIMEOUT")
    try:
        value = float(raw) if raw else _DEFAULT_TIMEOUT_S
    except ValueError:
        value = _DEFAULT_TIMEOUT_S
    return max(value, 5.0)


def _binary() -> str | None:
    """Locate the officecli binary (OFFICECLI_BIN overrides PATH lookup)."""
    override = os.environ.get("OFFICECLI_BIN")
    if override and Path(override).is_file():
        return override
    return shutil.which("officecli")


def _run_officecli(args: list[str], *, stdin_data: str | None = None) -> dict:
    """Run ``officecli ... --json`` and normalize the envelope to our dict shape.

    Returns ``{"ok": True, "data": <parsed data>}`` on success or
    ``{"ok": False, "issue": ..., "code": ..., "message": ...}`` on failure.
    """
    binary = _binary()
    if not binary:
        return {
            "ok": False,
            "issue": "officecli_missing",
            "message": (
                "officecli 未安装 / officecli binary not found on PATH"
                "（可设 OFFICECLI_BIN 指定路径）。"
            ),
        }
    cmd = [binary, *args, "--json"]
    # RESIDENT_FLUSH=each: every mutation is flushed to disk before the
    # command returns, so the openpyxl-side audit that follows always reads
    # the post-edit bytes. SKIP_UPDATE: no background updater inside a
    # guard-controlled tool call.
    env = {
        **os.environ,
        "OFFICECLI_RESIDENT_FLUSH": "each",
        "OFFICECLI_SKIP_UPDATE": "1",
    }
    try:
        proc = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=_timeout(),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("officecli timed out after %.0fs: %s", _timeout(), args[0])
        return {
            "ok": False,
            "issue": "officecli_timeout",
            "message": f"officecli 超时 / timed out after {_timeout():.0f}s",
        }
    except OSError as exc:
        logger.warning("officecli spawn failed: %s", exc)
        return {
            "ok": False,
            "issue": "officecli_unavailable",
            "message": f"officecli 无法启动 / cannot spawn: {exc}",
        }

    payload: Any = None
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = None
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "issue": "officecli_bad_output",
            "message": (
                "officecli 输出无法解析 / unparseable output: "
                f"exit={proc.returncode} stderr={proc.stderr.strip()[:200]}"
            ),
        }
    if not payload.get("success"):
        err = payload.get("error") or {}
        code = err.get("code") if isinstance(err, dict) else None
        message = (
            err.get("error")
            or payload.get("message")
            or proc.stderr.strip()[:200]
            or "officecli reported failure"
        )
        failed = {
            "ok": False,
            "issue": "officecli_error",
            "code": code,
            "message": f"officecli 失败 / officecli failed: {message}",
        }
        # Batch runs report partial failures with data intact (per-item
        # results + summary, e.g. atomicRolledBack) — keep it for callers.
        if payload.get("data") is not None:
            failed["data"] = payload["data"]
        return failed
    return {"ok": True, "data": payload.get("data")}


def _preflight_gate(file_path: Path) -> dict | None:
    """Reject corrupt or oversize workbooks before handing them to the CLI."""
    if not file_path.is_file():
        return {
            "ok": False,
            "issue": "missing",
            "message": f"文件不存在 / File not found: {file_path.name}",
        }
    size_err = _check_file_size(file_path)
    if size_err is not None:
        return size_err
    corrupt = detect_corrupt_workbook(str(file_path))
    if not corrupt.get("ok"):
        return {
            "ok": False,
            "issue": corrupt.get("issue", "corrupt"),
            "message": corrupt.get("message", "文件损坏，拒绝编辑。"),
        }
    return None


def _validate_batch_commands(commands: Any) -> dict | None:
    """Shape- and verb-check batch items before they reach the CLI."""
    if not isinstance(commands, list) or not commands:
        return {
            "ok": False,
            "issue": "invalid_commands",
            "message": "commands 必须为非空数组 / commands must be a non-empty array",
        }
    for i, item in enumerate(commands):
        if not isinstance(item, dict):
            return {
                "ok": False,
                "issue": "invalid_commands",
                "message": f"commands[{i}] 必须为对象 / must be an object",
            }
        verb = item.get("command") or item.get("op")
        if verb not in _EDIT_VERBS:
            return {
                "ok": False,
                "issue": "verb_not_allowed",
                "message": (
                    f"commands[{i}] 动词不被允许 / verb not allowed: {verb!r}。"
                    f"白名单 / allowlist: {sorted(_EDIT_VERBS)}"
                ),
            }
        if not (item.get("path") or item.get("parent") or item.get("selector")):
            return {
                "ok": False,
                "issue": "invalid_commands",
                "message": (
                    f"commands[{i}] 缺少 path/parent/selector 寻址字段 / "
                    "missing addressing field"
                ),
            }
    return None


def edit_workbook(path: str, commands: list[dict]) -> dict:
    """Guarded batch edit of an xlsx inside the workspace via officecli.

    Pipeline: containment + corrupt/oversize preflight -> verb allowlist ->
    single atomic ``officecli batch`` (any failing item rolls the whole batch
    back) -> post-write ``officecli validate`` + openpyxl formula audit.
    Commands follow officecli batch item schema, e.g.
    ``{"command":"set","path":"/Sheet1/B2","props":{"value":"=SUM(A1:A5)"}}``.
    """
    file_path, err = _resolve_allowed_path(path)
    if err is not None or file_path is None:
        return err
    gate = _preflight_gate(file_path)
    if gate is not None:
        return gate
    verb_err = _validate_batch_commands(commands)
    if verb_err is not None:
        return verb_err

    batch = _run_officecli(
        ["batch", str(file_path)], stdin_data=json.dumps(commands, ensure_ascii=False)
    )
    if not batch.get("ok"):
        summary = (batch.get("data") or {}).get("summary") or {}
        return {**batch, "summary": summary} if summary else batch
    summary = (batch.get("data") or {}).get("summary") or {}

    validate = _run_officecli(["validate", str(file_path)])
    audit = audit_workbook(str(file_path))
    return {
        "ok": True,
        "file": str(file_path),
        "summary": summary,
        "validate": (
            validate.get("data") if validate.get("ok") else validate.get("message")
        ),
        "audit": audit,
        "message": (
            f"编辑完成 / edit done: "
            f"{summary.get('succeeded', 0)}/{summary.get('total', 0)} 项成功，"
            f"validate={'通过' if validate.get('ok') else '未通过'}，"
            f"公式审计 must_fix={len((audit.get('must_fix') or []))}"
        ),
    }


def inspect_workbook(path: str, node_path: str = "/", depth: int = 1) -> dict:
    """Read-only structured inspection of a workspace xlsx via officecli get.

    Complements describe_workbook when you need styles/merge/annotation detail
    the openpyxl readers do not surface (e.g. ``/Sheet1/B2`` cell format).
    """
    file_path, err = _resolve_allowed_path(path)
    if err is not None or file_path is None:
        return err
    if not isinstance(node_path, str) or not node_path.strip():
        node_path = "/"
    depth = max(0, min(int(depth), 6))
    args = ["get", str(file_path), node_path]
    if depth > 0:
        args += ["--depth", str(depth)]
    result = _run_officecli(args)
    if not result.get("ok"):
        return result
    return {"ok": True, "file": str(file_path), "node": result.get("data")}


def validate_workbook(path: str) -> dict:
    """Validate a workspace xlsx against the OpenXML schema via officecli."""
    file_path, err = _resolve_allowed_path(path)
    if err is not None or file_path is None:
        return err
    if not file_path.is_file():
        return {
            "ok": False,
            "issue": "missing",
            "message": f"文件不存在 / File not found: {file_path.name}",
        }
    result = _run_officecli(["validate", str(file_path)])
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "file": str(file_path),
        "message": "OpenXML 校验通过 / OpenXML validation passed.",
    }


def render_workbook(path: str, out_path: str = "") -> dict:
    """Render a workspace xlsx sheet to PNG so the agent can see the result.

    The output file is forced inside the workspace: empty out_path writes
    next to the workbook as ``<stem>_render.png``; anything outside
    ``POC_WORKSPACE`` is rejected.
    """
    file_path, err = _resolve_allowed_path(path)
    if err is not None or file_path is None:
        return err
    if not file_path.is_file():
        return {
            "ok": False,
            "issue": "missing",
            "message": f"文件不存在 / File not found: {file_path.name}",
        }
    if out_path.strip():
        out_resolved, out_err = _resolve_allowed_path(out_path)
        if out_err is not None or out_resolved is None:
            return out_err
    else:
        out_resolved = file_path.with_name(f"{file_path.stem}_render.png")
    result = _run_officecli(
        ["view", str(file_path), "screenshot", "-o", str(out_resolved)]
    )
    if not result.get("ok"):
        return result
    produced = result.get("data")
    return {
        "ok": True,
        "file": str(file_path),
        "screenshot": str(produced or out_resolved),
        "message": f"渲染完成 / rendered: {produced or out_resolved}",
    }
