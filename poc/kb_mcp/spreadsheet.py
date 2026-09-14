# -*- coding: utf-8 -*-
"""Parse spreadsheet metadata (file/sheet names, headers, samples) into chunks.

Excel/CSV are NOT row-wise embedded — questions about tables are deterministic
data operations that code execution answers better than retrieval. What
retrieval IS good for is routing: "哪个文件/哪张表里有 XX 数据". So we build
one small metadata chunk per sheet; the caller commits them via
``ingest._commit_chunks`` and the agent later runs pandas on the located file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from poc.excel_guard_mcp.guards import _resolve_allowed_path
from poc.excel_guard_mcp.readers import describe_workbook

from .chunk import chunk_id
from .parse import _safe_doc_id

logger = logging.getLogger("poc.kb")

_HEADER_PREVIEW_ROWS = 3
_HEADER_MAX_COLS = 64


def _sheet_text(file_name: str, sheet: dict[str, Any]) -> str:
    header = [str(c) for c in (sheet.get("headers") or [])[:_HEADER_MAX_COLS]]
    md_lines = (sheet.get("markdown") or "").splitlines()
    # markdown table: header line, separator line, then data rows
    sample = "\n".join(md_lines[: 2 + _HEADER_PREVIEW_ROWS])
    cols = "、".join(c for c in header if c)
    merged = sheet.get("merged_ranges") or []
    parts = [
        f"文件: {file_name}",
        f"Sheet: {sheet.get('name')}",
        f"行数 {sheet.get('row_count') or 0}，列数 {sheet.get('column_count') or 0}",
    ]
    if cols:
        parts.append(f"列: {cols}")
    if merged:
        parts.append(f"合并单元格: {', '.join(merged[:10])}")
    parts.append(f"样例:\n{sample}")
    head = "；".join(parts[:4])
    tail = "\n".join(parts[4:])
    return f"{head}\n{tail}" if tail else head


def build_spreadsheet_chunks(
    resolved: Path, described: dict[str, Any], used_id: str
) -> list[dict[str, Any]]:
    """One sheet_meta chunk per sheet, chained with prev/next like page chunks."""
    file_name = resolved.name
    chunks: list[dict[str, Any]] = []
    for i, sheet in enumerate(described.get("sheets") or []):
        chunks.append(
            {
                "chunk_id": chunk_id(used_id, i + 1, "sheet_meta", 0),
                "doc_id": used_id,
                "page": i + 1,
                "chapter": str(sheet.get("name") or ""),
                "kind": "sheet_meta",
                "text": _sheet_text(file_name, sheet),
                "table": None,
                "image_description": None,
                "page_image": "",
                "screenshot": "",
            }
        )
    for i, chunk in enumerate(chunks):
        chunk["prev_id"] = chunks[i - 1]["chunk_id"] if i else ""
        chunk["next_id"] = chunks[i + 1]["chunk_id"] if i + 1 < len(chunks) else ""
    return chunks


def parse_spreadsheet_metadata(
    path: str,
    *,
    doc_id: str = "",
    sample_rows: int = _HEADER_PREVIEW_ROWS,
) -> dict[str, Any]:
    """Describe a workbook and return one sheet_meta chunk per sheet.

    Pure parse: no store writes, no embedding — ``ingest.ingest_spreadsheet``
    owns the commit. Mirrors ``parse_pdf``'s result shape.
    """
    resolved, err = _resolve_allowed_path(path)
    if err is not None or resolved is None:
        return {
            **(err or {"ok": False, "message": "path denied"}),
            "doc_id": "",
            "n_pages": 0,
            "chunks": [],
        }

    try:
        sample_rows = int(sample_rows)
    except (TypeError, ValueError):
        sample_rows = _HEADER_PREVIEW_ROWS
    sample_rows = max(1, min(sample_rows, 20))

    described = describe_workbook(str(resolved), preview_rows=sample_rows)
    if not described.get("ok"):
        return {
            "ok": False,
            "message": described.get("message") or "spreadsheet describe failed",
            "doc_id": _safe_doc_id(doc_id or resolved.stem),
            "n_pages": 0,
            "chunks": [],
        }

    used_id = _safe_doc_id(doc_id or resolved.stem)
    chunks = build_spreadsheet_chunks(resolved, described, used_id)
    sheet_names = [str(s.get("name") or "") for s in described.get("sheets") or []]
    return {
        "ok": True,
        "kind": described.get("kind") or "",
        "doc_id": used_id,
        "n_pages": len(chunks),
        "n_chunks": len(chunks),
        "chunks": chunks,
        "sheets": sheet_names,
        "backend": "spreadsheet-meta",
        "message": (
            f"已解析 {resolved.name} 的 {len(chunks)} 个工作表元数据"
            f"（文件名/表头/样例）：{', '.join(sheet_names)}。"
            "检索命中后请用 pandas 打开原文件做精确计算。"
        ),
    }
