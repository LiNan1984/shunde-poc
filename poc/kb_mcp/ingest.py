# -*- coding: utf-8 -*-
"""Parse a PDF or spreadsheet metadata and write stores (vectors / graph / meta)."""

from __future__ import annotations

import base64
import logging
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from poc.excel_guard_mcp.guards import _resolve_allowed_path

from .embed import embedding_backend_name, embed_texts, image_embedding_backend_name, image_embedding_endpoint
from .errors import with_error_type
from .parse import _safe_doc_id, parse_pdf
from .spreadsheet import parse_spreadsheet_metadata
from .stores import StoreBundle, open_stores, store_root

logger = logging.getLogger("poc.kb")

_VL_BATCH = 2
_VL_WORKERS = 4


def _sandbox_denied(err: dict[str, Any]) -> dict[str, Any]:
    issue = err.get("issue") or "path_denied"
    if issue == "path_denied":
        message = "路径越界 / Path outside workspace"
    else:
        message = err.get("message") or "路径无效 / Invalid path"
    return {
        "ok": False,
        "issue": issue,
        "message": message,
        "n_chunks": 0,
        "stores": {},
    }


def _image_vectors_for_chunks(chunks: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Real image embeddings for ``kind=="image"`` chunks that have a usable image file.

    Reads the image (embedded image path first, page PNG as fallback), encodes it
    as a base64 data URL and calls ``vl_embed`` (image+text share one vector
    space). Returns ``{chunk_id: vector}``; raises on endpoint failure — the
    caller must not fall back to caption/text vectors.
    """
    items: list[tuple[str, str]] = []
    for chunk in chunks:
        if (chunk.get("kind") or "text") != "image":
            continue
        path_str = str(chunk.get("screenshot") or chunk.get("page_image") or "")
        if not path_str:
            continue
        path = Path(path_str)
        try:
            data = path.read_bytes()
        except OSError as exc:
            logger.warning("cannot read image %s for embedding: %s", path, exc)
            continue
        if not data:
            continue
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        data_url = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
        items.append((chunk["chunk_id"], data_url))

    out: dict[str, list[float]] = {}
    from . import embed as embed_mod

    batches = [items[start : start + _VL_BATCH] for start in range(0, len(items), _VL_BATCH)]
    if len(batches) == 1:
        batch_vectors = [embed_mod.vl_embed([{"image": url} for _cid, url in batches[0]])]
    else:
        with ThreadPoolExecutor(max_workers=_VL_WORKERS) as pool:
            batch_vectors = list(pool.map(
                lambda batch: embed_mod.vl_embed([{"image": url} for _cid, url in batch]),
                batches,
            ))
    for batch, vectors in zip(batches, batch_vectors):
        for (cid, _url), vec in zip(batch, vectors, strict=False):
            out[cid] = vec
    return out


def _commit_chunks(
    *,
    bundle: StoreBundle,
    used_id: str,
    resolved: Path | None,
    chunks: list[dict[str, Any]],
    n_pages: int,
    backend: str,
    message: str,
    store_page_images: bool,
) -> dict[str, Any]:
    bundle.names["embedding"] = embedding_backend_name()
    bundle.names["image_embedding"] = image_embedding_backend_name()
    # Text and image embeddings are independent; run them concurrently.
    text_future = None
    image_future = None
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        if chunks:
            text_future = pool.submit(embed_texts, [c.get("text") or "" for c in chunks])
        if image_embedding_endpoint() and chunks:
            image_future = pool.submit(_image_vectors_for_chunks, chunks)
        try:
            vectors = text_future.result() if text_future else []
        except Exception as exc:  # noqa: BLE001 — never hash-embed after a live failure
            return {
                "ok": False,
                "message": str(exc),
                "doc_id": used_id,
                "n_chunks": 0,
                "n_pages": n_pages,
                "stores": dict(bundle.names),
            }
        if image_future is not None:
            try:
                image_vectors = image_future.result()
            except Exception as exc:  # noqa: BLE001 — never fall back to caption vectors
                return with_error_type(
                    {
                        "ok": False,
                        "message": f"图像向量入库失败 / image embedding failed: {exc}",
                        "doc_id": used_id,
                        "n_chunks": 0,
                        "n_pages": n_pages,
                        "stores": dict(bundle.names),
                    }
                )
            by_id = {c["chunk_id"]: i for i, c in enumerate(chunks)}
            for cid, vec in image_vectors.items():
                idx = by_id.get(cid)
                if idx is not None:
                    vectors[idx] = vec
    finally:
        pool.shutdown(wait=False)

    try:
        for row in bundle.relational.list_chunks(doc_id=used_id):
            cid = row.get("chunk_id") or ""
            if cid:
                bundle.relational.delete_chunk(cid)
                bundle.vector.delete(cid)
        bundle.relational.upsert_document(
            used_id,
            {
                "path": str(resolved) if resolved is not None else "",
                "n_pages": n_pages,
                "backend": backend,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=False):
            page_image = chunk.get("page_image") or ""
            if store_page_images and page_image:
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
            "n_pages": n_pages,
            "stores": dict(bundle.names),
        }

    return {
        "ok": True,
        "doc_id": used_id,
        "n_pages": n_pages,
        "n_chunks": len(chunks),
        "backend": backend,
        "stores": dict(bundle.names),
        "message": message or f"ingested {len(chunks)} chunks",
    }


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
    return _commit_chunks(
        bundle=bundle,
        used_id=used_id,
        resolved=resolved,
        chunks=chunks,
        n_pages=int(parsed.get("n_pages") or 0),
        backend=str(parsed.get("backend") or "local"),
        message=str(parsed.get("message") or ""),
        store_page_images=True,
    )


def ingest_spreadsheet(
    path: str,
    *,
    doc_id: str = "",
    sample_rows: int = 5,
    stores: StoreBundle | None = None,
) -> dict[str, Any]:
    """Index spreadsheet metadata only (filename, sheets, headers, sample rows)."""
    resolved, err = _resolve_allowed_path(path)
    if err is not None:
        return _sandbox_denied(err)

    parsed = parse_spreadsheet_metadata(
        path, doc_id=doc_id, sample_rows=sample_rows
    )
    if not parsed.get("ok"):
        return {**parsed, "n_chunks": parsed.get("n_chunks") or 0, "stores": {}}

    bundle = stores or open_stores()
    used_id = _safe_doc_id(str(parsed.get("doc_id") or doc_id or "sheet"))
    chunks: list[dict[str, Any]] = [
        c for c in (parsed.get("chunks") or []) if isinstance(c, dict)
    ]
    for chunk in chunks:
        chunk["doc_id"] = used_id
        chunk["page_image"] = ""
    return _commit_chunks(
        bundle=bundle,
        used_id=used_id,
        resolved=resolved,
        chunks=chunks,
        n_pages=int(parsed.get("n_pages") or len(chunks)),
        backend=str(parsed.get("backend") or "spreadsheet-meta"),
        message=str(parsed.get("message") or ""),
        store_page_images=False,
    )


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
