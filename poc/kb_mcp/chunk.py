# -*- coding: utf-8 -*-
"""Split parsed pages into overlapping chunks tagged with doc_id/page/chapter."""

from __future__ import annotations

from typing import Any

DEFAULT_MAX_CHARS = 400
DEFAULT_OVERLAP = 80


def split_with_overlap(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if max_chars <= 0:
        return [text]
    overlap = max(0, min(overlap, max_chars - 1))
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = end - overlap
    return chunks


def chunk_id(doc_id: str, page: int, kind: str, index: int) -> str:
    return f"{doc_id}:p{page}:{kind}:{index}"


def chunks_from_page(
    *,
    doc_id: str,
    page: int,
    chapter: str,
    body: str,
    page_image: str,
    tables: list[dict[str, Any]],
    images: list[dict[str, Any]],
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict[str, Any]]:
    """Build text / table / image chunks for one page."""
    out: list[dict[str, Any]] = []
    text_parts = split_with_overlap(body, max_chars=max_chars, overlap=overlap)
    for i, part in enumerate(text_parts):
        out.append(
            {
                "chunk_id": chunk_id(doc_id, page, "text", i),
                "doc_id": doc_id,
                "page": page,
                "chapter": chapter,
                "kind": "text",
                "text": part,
                "table": None,
                "image_description": None,
                "page_image": page_image,
                "screenshot": page_image,
            }
        )
    for i, table in enumerate(tables):
        out.append(
            {
                "chunk_id": chunk_id(doc_id, page, "table", i),
                "doc_id": doc_id,
                "page": page,
                "chapter": chapter,
                "kind": "table",
                "text": table.get("csv") or "",
                "table": table,
                "image_description": None,
                "page_image": page_image,
                "screenshot": page_image,
            }
        )
    for i, image in enumerate(images):
        desc = image.get("description") or ""
        out.append(
            {
                "chunk_id": chunk_id(doc_id, page, "image", i),
                "doc_id": doc_id,
                "page": page,
                "chapter": chapter,
                "kind": "image",
                "text": desc,
                "table": None,
                "image_description": desc,
                "page_image": page_image,
                "screenshot": image.get("path") or page_image,
            }
        )
    for i, item in enumerate(out):
        item["prev_id"] = out[i - 1]["chunk_id"] if i else ""
        item["next_id"] = out[i + 1]["chunk_id"] if i + 1 < len(out) else ""
    return out
