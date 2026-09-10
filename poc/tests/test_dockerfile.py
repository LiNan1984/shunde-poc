"""Static checks for poc/deploy/Dockerfile.poc.

We don't have docker in CI here, so we verify the Dockerfile by parsing it
line by line and asserting the structural invariants 任务 D requires:
- multi-stage (>=2 FROM)
- runtime uses python:slim (NOT full)
- no XFCE / Chromium / Coding Mode (bank demo doesn't need them)
- fonts-wqy-zenhei is present (otherwise charts render as boxes)
- exposes a port (so the health server is reachable)
- COPY references only paths that exist in the repo
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parents[1] / "deploy" / "Dockerfile.poc"
REPO_ROOT = DOCKERFILE.parents[2]  # poc/deploy/Dockerfile.poc → repo root


@pytest.fixture(scope="module")
def lines() -> list[str]:
    assert DOCKERFILE.exists(), f"Dockerfile missing: {DOCKERFILE}"
    return DOCKERFILE.read_text(encoding="utf-8").splitlines()


def _sections(lines: list[str]) -> list[list[str]]:
    """Split a Dockerfile into per-FROM sections."""
    sections: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if line.startswith("FROM "):
            if cur:
                sections.append(cur)
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        sections.append(cur)
    return sections


def test_uses_multi_stage(lines: list[str]) -> None:
    sections = _sections(lines)
    assert len(sections) >= 2, (
        f"expected >=2 FROM stages, got {len(sections)}"
    )


def test_runtime_stage_is_slim(lines: list[str]) -> None:
    sections = _sections(lines)
    # The last stage is the runtime.
    last = sections[-1]
    from_line = next(l for l in last if l.startswith("FROM "))
    assert "slim" in from_line.lower(), (
        f"runtime stage must use a slim image: {from_line!r}"
    )
    assert ":latest" not in from_line, "pin a specific tag instead of :latest"


def test_no_xfce_chromium_or_browser(lines: list[str]) -> None:
    """Bank demo does not need a browser/Coding Mode (see 任务 D notes)."""
    # Strip "#"-comments before scanning for install lines.
    code = "\n".join(l for l in lines if not l.lstrip().startswith("#")).lower()
    for forbidden in ("xfce", "chromium", "firefox", "webkit"):
        assert forbidden not in code, (
            f"Dockerfile installs {forbidden} (unwanted bloat)"
        )


def test_installs_cjk_font(lines: list[str]) -> None:
    joined = "\n".join(lines)
    assert "fonts-wqy-zenhei" in joined, (
        "charts will render as boxes without fonts-wqy-zenhei "
        "(see 交接清单 §5 中文字体)"
    )


def test_exposes_a_port(lines: list[str]) -> None:
    assert any(l.strip().startswith("EXPOSE ") for l in lines), (
        "Dockerfile must EXPOSE a port for the /health endpoint"
    )


def test_copy_paths_exist() -> None:
    """Every COPY source path (whitespace-split first arg) must exist."""
    for line in _lines_starting_with_copy():
        src = line.split()[1]
        if src.startswith("--") or "=" in src.split("=", 1)[0]:
            # flag-form like COPY --from=builder ...
            continue
        # Allow src to be "." (current build context) — repo root always exists.
        if src == ".":
            continue
        target = (REPO_ROOT / src).resolve()
        assert target.exists(), f"COPY source missing in repo: {src}"


def _lines_starting_with_copy() -> list[str]:
    text = DOCKERFILE.read_text(encoding="utf-8")
    out = []
    for raw in text.splitlines():
        stripped = raw.strip()
        # Handle line continuations only at top of statement.
        if not stripped.startswith("COPY "):
            continue
        # Strip trailing backslash continuations for parsing purposes.
        out.append(stripped.rstrip("\\").rstrip())
    return out


def test_no_absolute_secrets(lines: list[str]) -> None:
    """红线 1: nothing API-key-like in the Dockerfile."""
    joined = "\n".join(lines).lower()
    for needle in ("bearer ", "api_key=", "apikey=", "sk-", "providers.json"):
        assert needle not in joined, f"forbidden secret-like literal: {needle!r}"