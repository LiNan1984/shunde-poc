# -*- coding: utf-8 -*-
"""Parse a PDF and write page images / metadata / vectors / graph relations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from poc.excel_guard_mcp.guards import _resolve_allowed_path

from .embed import embedding_backend_name, embed_texts
from .parse import _safe_doc_id, parse_pdf
from .stores import StoreBundle, open_stores, store_root

logger = logging.getLogger("poc.kb")


def ingest_pdf(
    path: str,
    *,
    doc_id: str = "",
    max_pages: int = 0,
    stores: StoreBundle | None = None,
) -> dict[str, Any]:
    """Parse then upsert into object / relational / vector / graph stores."""
    resolved, err = _resolve_allowed_path(path)
    if err is not None:
        return {**err, "n_chunks": 0, "stores": {}}

    parsed = parse_pdf(path, max_pages=max_pages, doc_id=doc_id)
    if not parsed.get("ok"):
        return {**parsed, "n_chunks": parsed.get("n_chunks") or 0, "stores": {}}

    bundle = stores or open_stores()
    bundle.names["embedding"] = embedding_backend_name()
    used_id = _safe_doc_id(str(parsed.get("doc_id") or doc_id or "doc"))
    chunks: list[dict[str, Any]] = [
        c for c in (parsed.get("chunks") or []) if isinstance(c, dict)
    ]
    for chunk in chunks:
        chunk["doc_id"] = used_id
        img = chunk.get("page_image") or ""
        if img:
            img_path, img_err = _resolve_allowed_path(str(img))
            chunk["page_image"] = str(img_path) if img_path is not None and img_err is None else ""
    try:
        texts = [c.get("text") or "" for c in chunks]
        vectors = embed_texts(texts) if chunks else []
    except Exception as exc:  # noqa: BLE001 — never hash-embed after a live failure
        return {
            "ok": False,
            "message": str(exc),
            "doc_id": used_id,
            "n_chunks": 0,
            "n_pages": parsed.get("n_pages") or 0,
            "stores": dict(bundle.names),
        }

    try:
        for row in bundle.relational.list_chunks(doc_id=used_id):
            cid = row.get("chunk_id") or ""
            if cid:
                bundle.relational.delete_chunk(cid)
                bundle.vector.delete(cid)
        bundle.relational.upsert_document(
            used_id,
            {
                "path": str(resolved),
                "n_pages": parsed.get("n_pages") or 0,
                "backend": parsed.get("backend") or "local",
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=False):
            page_image = chunk.get("page_image") or ""
            if page_image:
                stored = bundle.objects.put_page_image(
                    used_id, int(chunk.get("page") or 0), Path(page_image)
                )
                chunk["page_image"] = stored
            bundle.relational.upsert_chunk(chunk)
            bundle.vector.upsert(
                chunk["chunk_id"], vector, {"kind": chunk.get("kind") or "text"}
            )
            bundle.graph.upsert_relations(chunk)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "message": f"入库失败 / ingest failed: {exc}",
            "doc_id": used_id,
            "n_chunks": 0,
            "n_pages": parsed.get("n_pages") or 0,
            "stores": dict(bundle.names),
        }

    return {
        "ok": True,
        "doc_id": used_id,
        "n_pages": parsed.get("n_pages") or 0,
        "n_chunks": len(chunks),
        "backend": parsed.get("backend") or "local",
        "stores": dict(bundle.names),
        "message": parsed.get("message") or f"ingested {len(chunks)} chunks",
    }


def drop_chunk(chunk_id: str, stores: StoreBundle | None = None) -> dict[str, Any]:
    """Remove a chunk from the index (simulates 缺块/截断) while keeping graph NEXT."""
    if not chunk_id.strip():
        return {"ok": False, "message": "chunk_id 不能为空 / chunk_id required"}
    bundle = stores or open_stores()
    bundle.relational.delete_chunk(chunk_id)
    bundle.vector.delete(chunk_id)
    bundle.graph.delete_chunk(chunk_id)
    return {"ok": True, "chunk_id": chunk_id, "message": "dropped from index"}


def default_store_dir() -> Path | None:
    root, err = store_root()
    if err:
        return None
    return root
