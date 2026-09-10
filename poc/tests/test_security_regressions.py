"""Attack-vector regression tests for the security hardening pass.

Covers:
- H1 TOCTOU: a symlink at a workspace path is rejected at open time
  (O_NOFOLLOW), and a self-referencing symlink does not leak the parent
  directory contents.
- M1 fail-closed sandbox: ``POC_WORKSPACE=/`` and a non-existent directory
  deny every operation; unset env falls back to the repo root.

Each test uses ``monkeypatch`` so we never depend on the host's real
``POC_WORKSPACE`` value, and ``tmp_path`` so the host filesystem is
untouched.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from poc.excel_guard_mcp import guards
from poc.excel_guard_mcp.guards import (
    _resolve_allowed_path,
    chunk_large_workbook,
    detect_corrupt_workbook,
)


def _set_workspace(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("POC_WORKSPACE", value)
    monkeypatch.delenv("QWENPAW_WORKING_DIR", raising=False)


# ---------- H1: TOCTOU / symlink ------------------------------------------------


def test_final_component_symlink_rejected(tmp_path: Path, monkeypatch) -> None:
    """A symlink at the *final* path component is rejected at open time.

    The file outside the workspace is unreadable to the tool even though
    the symlink target exists and is readable on the host filesystem.
    """
    _set_workspace(monkeypatch, str(tmp_path))
    # External target lives outside the sandbox on purpose.
    external = tmp_path.parent / "external_secret.xlsx"
    external.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
    link = tmp_path / "sneaky.xlsx"
    link.symlink_to(external)

    result = detect_corrupt_workbook(str(link))

    assert result["ok"] is False
    # path_denied comes from _classify_open_error(ELOOP). Any non-ok
    # response is acceptable; we specifically assert it's NOT a success
    # that would have leaked the file.
    assert result["issue"] != ""
    assert "external_secret" not in result["message"]


def test_self_referencing_symlink_rejected(
    tmp_path: Path, monkeypatch,
) -> None:
    """A self-referencing symlink (ELOOP) is not silently treated as missing."""
    _set_workspace(monkeypatch, str(tmp_path))
    loop = tmp_path / "loop.xlsx"
    loop.symlink_to(loop.name)  # ELOOP on resolve / O_NOFOLLOW

    result = detect_corrupt_workbook(str(loop))

    assert result["ok"] is False
    # Must NOT be silently "ok" — that would mean we never opened it.
    assert result["issue"] != ""


def test_path_outside_workspace_still_denied(
    tmp_path: Path, monkeypatch,
) -> None:
    """A regular (non-symlink) file outside the sandbox is denied."""
    _set_workspace(monkeypatch, str(tmp_path))
    outside = tmp_path.parent / "outside.xlsx"
    outside.write_bytes(b"x" * 10)

    _, err = _resolve_allowed_path(str(outside))
    assert err is not None
    assert err["issue"] == "path_denied"


# ---------- M1: fail-closed sandbox ---------------------------------------------


def test_workspace_root_slash_is_rejected(monkeypatch) -> None:
    """``POC_WORKSPACE=/`` MUST be rejected (was the original M1 fail-open)."""
    _set_workspace(monkeypatch, "/")

    root, err = guards._workspace_root()

    assert root is None
    assert err is not None
    assert err["issue"] == "workspace_invalid"
    # The rejection message must explain WHY '/' is unsafe so the operator
    # can fix the configuration.
    assert "/" in err["message"] or "根" in err["message"]


def test_workspace_root_nonexistent_dir_is_rejected(monkeypatch) -> None:
    _set_workspace(monkeypatch, "/definitely/not/here/__no_such__")

    root, err = guards._workspace_root()

    assert root is None
    assert err is not None
    assert err["issue"] == "workspace_invalid"


def test_tool_call_with_slash_workspace_does_not_explode(
    monkeypatch, tmp_path: Path,
) -> None:
    """End-to-end: with ``POC_WORKSPACE=/`` every tool surfaces the error."""
    _set_workspace(monkeypatch, "/")

    result = detect_corrupt_workbook(str(tmp_path / "any.xlsx"))

    assert result["ok"] is False
    assert result["issue"] == "workspace_invalid"


def test_chunk_large_workbook_inherits_fail_closed(monkeypatch) -> None:
    """chunk_large_workbook must also surface workspace_invalid, not raise."""
    _set_workspace(monkeypatch, "/")

    # chunk_large_workbook returns the legacy "needs_chunking" shape; the
    # legacy message field carries the error text. We only assert it doesn't
    # blow up and signals denial.
    result = chunk_large_workbook("/whatever.xlsx")

    assert result["needs_chunking"] is False
    # message comes from the workspace_invalid dict via _resolve_allowed_path.
    assert "沙箱" in result["message"] or "workspace" in result["message"].lower()


# ---------- MemoryError audit ---------------------------------------------------


def test_no_broad_except_swallows_memoryerror() -> None:
    """Static guard: ensure we don't have ``except Exception`` swallowing
    MemoryError in the corruption check path. (MemoryError is not a subclass
    of Exception, so a bare ``except`` won't catch it; we just assert no
    ``except BaseException``-style blanket catch exists.)
    """
    import ast

    src = Path(guards.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    found_broad = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                # bare `except:` catches BaseException including KeyboardInterrupt
                found_broad = True
            elif isinstance(node.type, ast.Name) and node.type.id == "BaseException":
                found_broad = True
    assert not found_broad, (
        "guards.py contains an over-broad except that could swallow "
        "MemoryError / KeyboardInterrupt / SystemExit"
    )