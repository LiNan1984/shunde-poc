# -*- coding: utf-8 -*-
"""Local PDF parser: native text, empty-page OCR, tables csv/html/json, image captions."""

from __future__ import annotations

import csv
import html
import io
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from poc.excel_guard_mcp.guards import (
    _open_contained,
    _resolve_allowed_path,
    _workspace_root,
)

from .chunk import chunk_id, chunks_from_page
from .errors import with_error_type
from .mineru import mineru_cli_path, mineru_endpoint, parse_with_mineru

logger = logging.getLogger("poc.kb")

CHAPTER_RE = re.compile(r"第[一二三四五六七八九十百零〇0-9]+章[^\n]{0,40}")
_MAX_FILE_BYTES = 200 * 1024 * 1024


def _safe_doc_id(raw: str) -> str:
    cleaned = "".join(c for c in raw if c.isalnum() or c in "-_")
    return cleaned or "doc"


def _ocr_lang() -> str:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        return ""
    try:
        proc = subprocess.run(
            [tesseract, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        langs = proc.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return "eng"
    if "chi_sim" in langs:
        return "chi_sim+eng"
    return "eng"


def _ocr_image(image: Any) -> str:
    lang = _ocr_lang()
    if not lang:
        return ""
    try:
        import pytesseract
    except ImportError:
        return ""
    try:
        return pytesseract.image_to_string(image, lang=lang) or ""
    except Exception as exc:  # noqa: BLE001 — OCR is best-effort
        logger.warning("OCR failed: %s", exc)
        return ""


def _render_page(pdfium_doc: Any, index: int, scale: float = 2.0) -> Any:
    page = pdfium_doc[index]
    return page.render(scale=scale).to_pil()


def _detect_chapter(text: str) -> str:
    match = CHAPTER_RE.search(text or "")
    return match.group(0).strip() if match else ""


def _table_formats(rows: list[list[str]]) -> dict[str, Any]:
    cleaned: list[list[str]] = [
        ["" if cell is None else str(cell) for cell in row] for row in rows
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(cleaned)
    csv_text = buf.getvalue()
    html_parts = ["<table>"]
    for i, row in enumerate(cleaned):
        tag = "th" if i == 0 else "td"
        cells = "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in row)
        html_parts.append(f"<tr>{cells}</tr>")
    html_parts.append("</table>")
    header, *rest = cleaned if cleaned else ([],)
    if header and rest and all(header):
        json_payload: Any = [dict(zip(header, row, strict=False)) for row in rest]
    else:
        json_payload = cleaned
    return {"csv": csv_text, "html": "".join(html_parts), "json": json_payload}


def _extract_tables_from_page(plumber_page: Any) -> list[dict[str, Any]]:
    if plumber_page is None:
        return []
    try:
        raw_tables = plumber_page.extract_tables() or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("table extract failed: %s", exc)
        return []
    return [_table_formats(t) for t in raw_tables if t]


def _extract_images(reader_page: Any, dest_dir: Path, page_no: int) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    try:
        embedded = list(reader_page.images or [])
    except Exception:  # noqa: BLE001
        embedded = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    for i, item in enumerate(embedded):
        data = getattr(item, "data", None)
        pil = getattr(item, "image", None)
        if data is None and pil is None:
            continue
        out = dest_dir / f"p{page_no}-img{i}.png"
        try:
            if pil is not None:
                pil.save(out)
                width, height = pil.size
                description = _describe_pil(pil, f"p{page_no}-img{i}")
            else:
                out.write_bytes(data)
                width = height = 0
                description = f"embedded image ({out.name})"
        except Exception as exc:  # noqa: BLE001
            logger.warning("image extract failed: %s", exc)
            continue
        images.append(
            {
                "path": str(out),
                "width": width,
                "height": height,
                "description": description,
            }
        )
    return images


def _describe_pil(pil: Any, fallback: str) -> str:
    width, height = pil.size
    ocr = _ocr_image(pil).strip()
    if ocr:
        compact = " ".join(ocr.split())
        return f"embedded image {width}x{height}: {compact[:120]}"
    return f"embedded image {width}x{height} ({fallback})"


def _default_output_dir(doc_id: str) -> Path | None:
    root, err = _workspace_root()
    if err or root is None:
        return None
    return root / "kb_store" / "objects" / doc_id


def _chunks_from_mineru_pages(pages: list[Any], doc_id: str) -> list[dict[str, Any]]:
    """Map a MinerU page list onto the local chunk schema (no fabricated text)."""
    chunks: list[dict[str, Any]] = []
    last_chapter = ""
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page") or 0)
        body = str(page.get("text") or "")
        chapter = str(page.get("chapter") or _detect_chapter(body) or last_chapter)
        if chapter:
            last_chapter = chapter
        tables = []
        for table in page.get("tables") or []:
            if isinstance(table, dict) and (table.get("csv") or table.get("html") or table.get("json")):
                tables.append(table)
            elif isinstance(table, list) and table:
                tables.append(_table_formats(table))
        images = []
        for i, image in enumerate(page.get("images") or []):
            if isinstance(image, dict):
                images.append(
                    {
                        "path": image.get("path") or "",
                        "description": image.get("description") or "",
                    }
                )
            elif isinstance(image, str) and image.strip():
                images.append({"path": "", "description": image.strip()})
        page_image = str(page.get("page_image") or "")
        if page_image:
            resolved_img, img_err = _resolve_allowed_path(page_image)
            page_image = (
                str(resolved_img) if resolved_img is not None and img_err is None else ""
            )
        chunks.extend(
            chunks_from_page(
                doc_id=doc_id,
                page=page_no,
                chapter=chapter,
                body=body,
                page_image=page_image,
                tables=tables,
                images=images,
            )
        )
    return chunks


def _contained_pdf_bytes(resolved: Path) -> tuple[bytes | None, dict | None]:
    fh, err = _open_contained(resolved)
    if err is not None or fh is None:
        return None, err
    try:
        return fh.read(), None
    except OSError as exc:
        return None, with_error_type(
            {
                "ok": False,
                "message": f"无法读取文件 / cannot read file: {exc}",
                "backend": "",
                "pages": [],
                "chunks": [],
            }
        )
    finally:
        fh.close()


def _finalize_mineru_result(
    result: dict[str, Any], used_id: str, max_pages: int = 0,
) -> dict[str, Any]:
    """Force sandbox-safe doc_id; drop non-dict chunks; ignore out-of-workspace paths."""
    if not result.get("ok"):
        result["doc_id"] = used_id
        result.setdefault("chunks", [])
        result.setdefault("pages", [])
        return with_error_type(result)
    result["doc_id"] = used_id
    pages = result.get("pages") or []
    if max_pages > 0 and isinstance(pages, list):
        result["pages"] = pages[:max_pages]
    raw_chunks = result.get("chunks") or []
    if not isinstance(raw_chunks, list):
        return with_error_type(
            {
                "ok": False,
                "backend": "mineru",
                "doc_id": used_id,
                "pages": [],
                "chunks": [],
                "message": "MinerU 切块格式无效 / MinerU chunks are not a list",
            }
        )
    if not raw_chunks:
        try:
            result["chunks"] = _chunks_from_mineru_pages(result.get("pages") or [], used_id)
        except (TypeError, ValueError, AttributeError) as exc:
            return with_error_type(
                {
                    "ok": False,
                    "backend": "mineru",
                    "doc_id": used_id,
                    "pages": [],
                    "chunks": [],
                    "message": f"MinerU 页映射失败 / MinerU page map failed: {exc}",
                }
            )
    else:
        cleaned: list[dict[str, Any]] = []
        for i, chunk in enumerate(raw_chunks):
            if not isinstance(chunk, dict):
                continue
            try:
                page_no = int(chunk.get("page") or 0)
            except (TypeError, ValueError):
                continue
            image_path = str(chunk.get("page_image") or chunk.get("screenshot") or "")
            if image_path:
                resolved_img, img_err = _resolve_allowed_path(image_path)
                image_path = str(resolved_img) if resolved_img is not None and img_err is None else ""
            cleaned.append(
                {
                    "chunk_id": chunk_id(used_id, page_no, str(chunk.get("kind") or "text"), i),
                    "doc_id": used_id,
                    "page": page_no,
                    "chapter": str(chunk.get("chapter") or ""),
                    "kind": str(chunk.get("kind") or "text"),
                    "text": str(chunk.get("text") or ""),
                    "table": chunk.get("table") if isinstance(chunk.get("table"), dict) else None,
                    "image_description": str(chunk.get("image_description") or ""),
                    "page_image": image_path,
                    "screenshot": image_path,
                    "prev_id": "",
                    "next_id": "",
                }
            )
        result["chunks"] = cleaned
    result["n_pages"] = len(result.get("pages") or [])
    result["n_chunks"] = len(result.get("chunks") or [])
    return result


def parse_pdf(
    path: str,
    *,
    output_dir: str | None = None,
    max_pages: int = 0,
    doc_id: str = "",
) -> dict[str, Any]:
    """Parse a workspace PDF into pages + chunks.

    If ``MINERU_ENDPOINT`` is set, the MinerU client is used and a failure
    is returned as-is (no locally fabricated chunks). Otherwise the local
    parser runs: native text, OCR on empty extract, tables, images, page PNG.
    """
    resolved, err = _resolve_allowed_path(path)
    if err is not None or resolved is None:
        return with_error_type(
            {
                **(err or {"ok": False, "message": "path denied"}),
                "backend": "",
                "pages": [],
                "chunks": [],
            }
        )
    if not resolved.is_file():
        return with_error_type(
            {
                "ok": False,
                "issue": "missing",
                "message": f"文件不存在 / file not found: {path}",
                "backend": "",
                "pages": [],
                "chunks": [],
            }
        )
    try:
        size = resolved.stat().st_size
    except OSError as exc:
        return with_error_type(
            {
                "ok": False,
                "message": f"无法读取文件 / cannot stat file: {exc}",
                "backend": "",
                "pages": [],
                "chunks": [],
            }
        )
    if size > _MAX_FILE_BYTES:
        return with_error_type(
            {
                "ok": False,
                "message": f"文件过大 / file too large: {size} bytes",
                "backend": "",
                "pages": [],
                "chunks": [],
            }
        )

    used_id = _safe_doc_id(doc_id or resolved.stem)
    pdf_bytes, read_err = _contained_pdf_bytes(resolved)
    if read_err is not None or pdf_bytes is None:
        return with_error_type(
            {
                **(read_err or {"ok": False, "message": "cannot read pdf"}),
                "backend": "",
                "pages": [],
                "chunks": [],
            }
        )
    if len(pdf_bytes) > _MAX_FILE_BYTES:
        return with_error_type(
            {
                "ok": False,
                "message": f"文件过大 / file too large: {len(pdf_bytes)} bytes",
                "backend": "",
                "pages": [],
                "chunks": [],
            }
        )
    endpoint = mineru_endpoint()
    if endpoint or mineru_cli_path():
        result = parse_with_mineru(
            resolved, endpoint, data=pdf_bytes, max_pages=max_pages,
        )
        return _finalize_mineru_result(result, used_id, max_pages=max_pages)

    dest = Path(output_dir) if output_dir else _default_output_dir(used_id)
    root, root_err = _workspace_root()
    if dest is None or root is None or root_err is not None:
        return with_error_type(
            {
                "ok": False,
                "message": (root_err or {}).get("message")
                or "沙箱不可用 / workspace unavailable",
                "backend": "local",
                "pages": [],
                "chunks": [],
            }
        )
    try:
        dest = dest.expanduser().resolve(strict=False)
    except (OSError, ValueError) as exc:
        return with_error_type(
            {
                "ok": False,
                "message": f"输出目录无法解析 / cannot resolve output_dir: {exc}",
                "backend": "local",
                "pages": [],
                "chunks": [],
            }
        )
    if not dest.is_relative_to(root):
        return with_error_type(
            {
                "ok": False,
                "issue": "path_denied",
                "message": f"路径越界 / Path outside workspace root ({root}): {dest}",
                "backend": "local",
                "pages": [],
                "chunks": [],
            }
        )
    dest.mkdir(parents=True, exist_ok=True)

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        n_pages = len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        return with_error_type(
            {
                "ok": False,
                "message": f"PDF 无法打开 / cannot open PDF: {exc}",
                "backend": "local",
                "pages": [],
                "chunks": [],
            }
        )

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        return with_error_type(
            {
                "ok": False,
                "message": f"缺少 pypdfium2 / pypdfium2 missing: {exc}",
                "backend": "local",
                "pages": [],
                "chunks": [],
            }
        )

    plumber_pages: list[Any] = []
    plumber_doc = None
    try:
        import pdfplumber

        plumber_doc = pdfplumber.open(io.BytesIO(pdf_bytes))
        plumber_pages = list(plumber_doc.pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber open failed: %s", exc)

    try:
        pdfium_doc = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        if plumber_doc is not None:
            plumber_doc.close()
        return with_error_type(
            {
                "ok": False,
                "message": f"PDF 渲染失败 / cannot render PDF: {exc}",
                "backend": "local",
                "pages": [],
                "chunks": [],
            }
        )

    limit = n_pages if max_pages <= 0 else min(n_pages, max_pages)
    pages: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    ocr_notes: list[str] = []
    last_chapter = ""
    try:
        for i in range(limit):
            page_no = i + 1
            native = (reader.pages[i].extract_text() or "").strip()
            pil = _render_page(pdfium_doc, i)
            page_png = dest / f"page-{page_no}.png"
            pil.save(page_png)
            ocr_text = ""
            if not native:
                ocr_text = _ocr_image(pil).strip()
                if not ocr_text and not _ocr_lang():
                    ocr_notes.append(f"page {page_no}: tesseract unavailable")
            body = native or ocr_text
            chapter = _detect_chapter(body) or last_chapter
            if chapter:
                last_chapter = chapter
            plumber_page = plumber_pages[i] if i < len(plumber_pages) else None
            tables = _extract_tables_from_page(plumber_page)
            images = _extract_images(reader.pages[i], dest, page_no)
            if plumber_page is not None:
                # Release pdfplumber's per-page object cache immediately; the
                # full list would otherwise retain every page until the end
                # (multi-GB RSS on image-heavy reports).
                close_page = getattr(plumber_page, "close", None)
                if callable(close_page):
                    close_page()
                plumber_pages[i] = None
            pil.close() if hasattr(pil, "close") else None
            page_rec = {
                "page": page_no,
                "native_text": native,
                "ocr_text": ocr_text,
                "chapter": chapter,
                "page_image": str(page_png),
            }
            pages.append(page_rec)
            chunks.extend(
                chunks_from_page(
                    doc_id=used_id,
                    page=page_no,
                    chapter=chapter,
                    body=body,
                    page_image=str(page_png),
                    tables=tables,
                    images=images,
                )
            )
    finally:
        close = getattr(pdfium_doc, "close", None)
        if callable(close):
            close()
        if plumber_doc is not None:
            plumber_doc.close()

    message = f"parsed {len(pages)} pages into {len(chunks)} chunks"
    if ocr_notes:
        message += "；OCR skipped: " + "; ".join(ocr_notes)
    return {
        "ok": True,
        "backend": "local",
        "doc_id": used_id,
        "n_pages": len(pages),
        "n_chunks": len(chunks),
        "pages": pages,
        "chunks": chunks,
        "message": message,
    }
