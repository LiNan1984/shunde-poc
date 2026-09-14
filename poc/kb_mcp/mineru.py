# -*- coding: utf-8 -*-
"""MinerU2.5-Pro client: official /file_parse + stub /parse + local CLI.

Never fabricates chunks on failure.
"""

from __future__ import annotations

import csv
import html as html_lib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

logger = logging.getLogger("poc.kb")


def mineru_endpoint() -> str:
    from .embed import load_embedding_secrets

    load_embedding_secrets()
    return (
        os.environ.get("MINERU_ENDPOINT")
        or os.environ.get("POC_MINERU_URL")
        or ""
    ).strip()


def mineru_backend() -> str:
    raw = (os.environ.get("MINERU_BACKEND") or os.environ.get("POC_MINERU_BACKEND") or "").strip()
    if raw:
        return raw
    # Apple Silicon / no NVIDIA: pipeline is the documented CPU-capable backend.
    return "pipeline"


def mineru_timeout() -> float:
    try:
        return float(os.environ.get("MINERU_TIMEOUT") or "300")
    except ValueError:
        return 300.0


def mineru_cli_path() -> str:
    """Only used when MINERU_CLI or MINERU_LOCAL=1 — tests must not auto-pick it."""
    explicit = (os.environ.get("MINERU_CLI") or "").strip()
    if explicit:
        return explicit
    local = (os.environ.get("MINERU_LOCAL") or "").strip().lower()
    if local not in {"1", "true", "yes", "on"}:
        return ""
    bundled = Path(__file__).resolve().parents[2] / "MinerU" / ".venv" / "bin" / "mineru"
    if bundled.is_file():
        return str(bundled)
    return shutil.which("mineru") or ""


def _mineru_fail(message: str, doc_id: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "backend": "mineru",
        "doc_id": doc_id,
        "pages": [],
        "chunks": [],
        "message": message,
    }


class _TableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"}:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None:
            text = html_lib.unescape("".join(self._cell)).strip()
            if self._row is not None:
                self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def table_formats_from_html(table_html: str) -> dict[str, Any]:
    parser = _TableHTMLParser()
    try:
        parser.feed(table_html or "")
    except Exception:  # noqa: BLE001
        parser.rows = []
    rows = parser.rows
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    header, *rest = rows if rows else ([],)
    if header and rest and all(header):
        json_payload: Any = [dict(zip(header, row, strict=False)) for row in rest]
    else:
        json_payload = rows
    return {
        "csv": buf.getvalue(),
        "html": table_html or "",
        "json": json_payload,
    }


def _join_captions(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def map_content_list(content_list: Any, *, md_fallback: str = "") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Turn MinerU content_list into our pages[] + chunks[] (no fabricated text)."""
    if isinstance(content_list, str):
        try:
            content_list = json.loads(content_list)
        except json.JSONDecodeError:
            content_list = []
    if not isinstance(content_list, list):
        content_list = []

    by_page: dict[int, dict[str, Any]] = {}
    chunks: list[dict[str, Any]] = []

    def page_rec(page_no: int) -> dict[str, Any]:
        rec = by_page.get(page_no)
        if rec is None:
            rec = {
                "page": page_no,
                "native_text": "",
                "ocr_text": "",
                "chapter": "",
                "page_image": "",
            }
            by_page[page_no] = rec
        return rec

    for item in content_list:
        if not isinstance(item, dict):
            continue
        try:
            if item.get("page_idx") is not None:
                page_no = int(item["page_idx"]) + 1
            elif item.get("page") is not None:
                page_no = int(item["page"])
            else:
                page_no = 1
        except (TypeError, ValueError):
            page_no = 1
        kind = str(item.get("type") or "text")
        rec = page_rec(page_no)
        chapter = rec["chapter"]
        if kind == "text":
            text = str(item.get("text") or item.get("content") or "").strip()
            if not text:
                continue
            if int(item.get("text_level") or 0) >= 1 and re.search(r"第.+章", text):
                rec["chapter"] = text
                chapter = text
            rec["native_text"] = (rec["native_text"] + "\n" + text).strip()
            chunks.append(
                {
                    "chunk_id": "",
                    "page": page_no,
                    "chapter": chapter,
                    "kind": "text",
                    "text": text,
                    "table": None,
                    "image_description": None,
                }
            )
        elif kind in {"table", "chart"}:
            table_html = str(item.get("table_body") or item.get("html") or "")
            caption = _join_captions(item.get("table_caption") or item.get("image_caption") or "")
            table = table_formats_from_html(table_html) if table_html else {
                "csv": caption, "html": table_html, "json": [],
            }
            rec["native_text"] = (rec["native_text"] + "\n" + (caption or table["csv"])).strip()
            chunks.append(
                {
                    "chunk_id": "",
                    "page": page_no,
                    "chapter": chapter,
                    "kind": "table",
                    "text": table["csv"] or caption,
                    "table": table,
                    "image_description": caption or None,
                }
            )
        elif kind in {"image"}:
            caption = _join_captions(item.get("image_caption") or item.get("img_caption") or "")
            desc = caption or str(item.get("img_path") or "embedded image")
            chunks.append(
                {
                    "chunk_id": "",
                    "page": page_no,
                    "chapter": chapter,
                    "kind": "image",
                    "text": desc,
                    "table": None,
                    "image_description": desc,
                }
            )
        else:
            text = str(item.get("text") or item.get("content") or "").strip()
            if text:
                rec["native_text"] = (rec["native_text"] + "\n" + text).strip()
                chunks.append(
                    {
                        "chunk_id": "",
                        "page": page_no,
                        "chapter": chapter,
                        "kind": "text",
                        "text": text,
                        "table": None,
                        "image_description": None,
                    }
                )

    pages = [by_page[k] for k in sorted(by_page)]
    if not pages and md_fallback.strip():
        pages = [{
            "page": 1,
            "native_text": md_fallback.strip(),
            "ocr_text": "",
            "chapter": "",
            "page_image": "",
        }]
        chunks.append(
            {
                "chunk_id": "",
                "page": 1,
                "chapter": "",
                "kind": "text",
                "text": md_fallback.strip(),
                "table": None,
                "image_description": None,
            }
        )
    return pages, chunks


def _multipart(fields: dict[str, str], file_bytes: bytes, filename: str = "upload.pdf") -> tuple[bytes, str]:
    boundary = f"----PocMinerUBoundary{os.urandom(8).hex()}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("utf-8")
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def _http_json(url: str, body: bytes, content_type: str, timeout: float) -> tuple[int, Any]:
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": content_type}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return getattr(resp, "status", 200), json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        try:
            return exc.code, json.loads(detail)
        except json.JSONDecodeError:
            raise RuntimeError(f"MinerU HTTP {exc.code}: {detail}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"MinerU 返回非 JSON / MinerU response is not JSON: {exc}") from exc


def _from_file_parse_payload(payload: dict[str, Any], doc_id: str) -> dict[str, Any]:
    results = payload.get("results")
    if not isinstance(results, dict) or not results:
        return _mineru_fail("MinerU /file_parse 返回空 results", doc_id)
    first = next(iter(results.values()))
    if not isinstance(first, dict):
        return _mineru_fail("MinerU results 格式无效", doc_id)
    pages, chunks = map_content_list(
        first.get("content_list"),
        md_fallback=str(first.get("md_content") or ""),
    )
    if not pages:
        return _mineru_fail("MinerU 返回空页 / MinerU returned no pages", doc_id)
    return {
        "ok": True,
        "backend": "mineru",
        "doc_id": doc_id,
        "pages": pages,
        "chunks": chunks,
        "message": f"parsed via MinerU {payload.get('backend') or ''} {payload.get('version') or ''}".strip(),
        "mineru_version": payload.get("version") or "",
        "mineru_engine": payload.get("backend") or "",
    }


def parse_with_mineru(
    path: Path,
    endpoint: str = "",
    timeout: float | None = None,
    data: bytes | None = None,
    max_pages: int = 0,
) -> dict[str, Any]:
    """Call official MinerU HTTP, then the POC stub, then local CLI."""
    timeout = mineru_timeout() if timeout is None else timeout
    if data is None:
        try:
            data = path.read_bytes()
        except OSError as exc:
            return _mineru_fail(f"MinerU 无法读取文件 / cannot read file: {exc}", path.stem)

    base = (endpoint or mineru_endpoint()).rstrip("/")
    if base:
        urls: list[str] = []
        if base.endswith("/file_parse") or base.endswith("/parse"):
            urls.append(base)
        else:
            urls.extend([base + "/file_parse", base + "/parse"])
        last_err = ""
        for url in urls:
            try:
                if url.endswith("/file_parse"):
                    fields = {
                        "return_md": "true",
                        "return_content_list": "true",
                        "return_images": "false",
                        "table_enable": "true",
                        "formula_enable": "true",
                        "backend": mineru_backend(),
                        "parse_method": "auto",
                        "lang_list": "ch",
                        "start_page_id": "0",
                    }
                    if max_pages > 0:
                        fields["end_page_id"] = str(max_pages - 1)
                    body, boundary = _multipart(fields, data, filename="upload.pdf")
                    status, payload = _http_json(
                        url, body, f"multipart/form-data; boundary={boundary}", timeout
                    )
                    if status >= 400:
                        last_err = f"HTTP {status}"
                        continue
                    if isinstance(payload, dict) and "results" in payload:
                        return _from_file_parse_payload(payload, path.stem)
                    last_err = "unexpected file_parse payload"
                    continue
                # POC stub: POST /parse with a single file field
                body, boundary = _multipart({}, data, filename="upload.pdf")
                # stub used name="file" previously
                stub_body, stub_boundary = _stub_file_body(data)
                status, payload = _http_json(
                    url, stub_body, f"multipart/form-data; boundary={stub_boundary}", timeout
                )
                if isinstance(payload, dict) and isinstance(payload.get("pages"), list):
                    pages = payload.get("pages") or []
                    chunks = payload.get("chunks") or []
                    if not pages:
                        return _mineru_fail("MinerU 返回空页 / MinerU returned no pages", path.stem)
                    if chunks and not isinstance(chunks, list):
                        return _mineru_fail("MinerU 切块格式无效 / MinerU chunks are not a list", path.stem)
                    if isinstance(chunks, list) and chunks and not all(isinstance(c, dict) for c in chunks):
                        return _mineru_fail("MinerU 切块格式无效 / MinerU chunks are not objects", path.stem)
                    return {
                        "ok": True,
                        "backend": "mineru",
                        "doc_id": path.stem,
                        "pages": pages,
                        "chunks": chunks if isinstance(chunks, list) else [],
                        "message": "parsed via MinerU",
                    }
                last_err = f"HTTP {status}"
            except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, UnicodeDecodeError) as exc:
                last_err = str(exc)
                logger.warning("MinerU request failed %s: %s", url, exc)
                continue
        if not mineru_cli_path():
            return _mineru_fail(f"MinerU 请求失败 / MinerU request failed: {last_err}", path.stem)

    cli = mineru_cli_path()
    if cli:
        return parse_with_mineru_cli(path, data=data, max_pages=max_pages, timeout=timeout)
    return _mineru_fail("未配置 MINERU_ENDPOINT 且未找到 mineru CLI", path.stem)


def _stub_file_body(data: bytes) -> tuple[bytes, str]:
    boundary = f"----PocMinerUBoundary{os.urandom(8).hex()}"
    header = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="upload.pdf"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return header + data + footer, boundary


def parse_with_mineru_cli(
    path: Path,
    *,
    data: bytes | None = None,
    max_pages: int = 0,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run bundled/local ``mineru`` CLI and map *_content_list.json."""
    cli = mineru_cli_path()
    if not cli:
        return _mineru_fail("mineru CLI 不存在", path.stem)
    timeout = mineru_timeout() if timeout is None else timeout
    with tempfile.TemporaryDirectory(prefix="poc-mineru-") as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "upload.pdf"
        src.write_bytes(data if data is not None else path.read_bytes())
        out = tmp_path / "out"
        out.mkdir()
        cmd = [
            cli,
            "-p",
            str(src),
            "-o",
            str(out),
            "-b",
            mineru_backend(),
            "-m",
            "auto",
            "-l",
            "ch",
            "-t",
            "true",
            "-s",
            "0",
        ]
        if max_pages > 0:
            cmd.extend(["-e", str(max_pages - 1)])
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _mineru_fail(f"mineru CLI 失败 / CLI failed: {exc}", path.stem)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "")[-400:]
            return _mineru_fail(f"mineru CLI exit {proc.returncode}: {err}", path.stem)
        lists = list(out.rglob("*_content_list.json"))
        md_files = list(out.rglob("*.md"))
        content: Any = []
        md_text = ""
        if lists:
            try:
                content = json.loads(lists[0].read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return _mineru_fail(f"content_list 无法解析: {exc}", path.stem)
        if md_files:
            md_text = md_files[0].read_text(encoding="utf-8")
        pages, chunks = map_content_list(content, md_fallback=md_text)
        if not pages:
            return _mineru_fail("mineru CLI 未产出页面", path.stem)
        return {
            "ok": True,
            "backend": "mineru",
            "doc_id": path.stem,
            "pages": pages,
            "chunks": chunks,
            "message": f"parsed via mineru CLI ({mineru_backend()})",
            "mineru_engine": mineru_backend(),
        }
