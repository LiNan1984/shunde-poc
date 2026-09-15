# -*- coding: utf-8 -*-
"""Parse-path tests for native text / OCR / tables / images / page PNGs."""

from __future__ import annotations

import json
import shutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

from poc.kb_mcp.fixtures import (
    TOKENS,
    write_chapter_carry_pdf,
    write_native_text_pdf,
    write_scan_pdf,
    write_table_image_pdf,
)
from poc.kb_mcp.parse import parse_pdf

TESSERACT = shutil.which("tesseract")


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("POC_LOAD_SECRETS", "0")
    monkeypatch.delenv("MINERU_ENDPOINT", raising=False)
    monkeypatch.delenv("POC_MINERU_URL", raising=False)
    monkeypatch.delenv("POC_EMBEDDING_URL", raising=False)
    monkeypatch.delenv("POC_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("POC_CHAT_MODEL", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ELASTICSEARCH_URL", raising=False)
    monkeypatch.delenv("MYSQL_URL", raising=False)
    monkeypatch.delenv("GALASYBASE_URL", raising=False)
    return tmp_path


def test_native_text_chunks_have_doc_id_page_and_chapter(tmp_path: Path) -> None:
    pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
    result = parse_pdf(str(pdf), doc_id="credit-policy")
    assert result["ok"] is True
    assert result["backend"] == "local"
    chunks = result["chunks"]
    assert chunks
    joined = " ".join(c["text"] for c in chunks)
    assert TOKENS["alpha"] in joined
    assert TOKENS["beta"] in joined
    assert TOKENS["gamma"] in joined
    page1 = [c for c in chunks if c["page"] == 1]
    assert page1
    assert page1[0]["doc_id"] == "credit-policy"
    assert "第一" in (page1[0].get("chapter") or "")
    page2 = [c for c in chunks if c["page"] == 2]
    assert page2
    assert "第二" in (page2[0].get("chapter") or "")
    pngs = [Path(c["page_image"]) for c in chunks]
    assert pngs
    assert pngs[0].is_file()
    assert pngs[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(not TESSERACT, reason="tesseract not installed; OCR branch skipped")
def test_scan_page_empty_extract_goes_through_ocr(tmp_path: Path) -> None:
    pdf = write_scan_pdf(tmp_path / "scan_page.pdf")
    result = parse_pdf(str(pdf), doc_id="scan-demo")
    assert result["ok"] is True
    pages = result["pages"]
    assert pages
    assert not (pages[0].get("native_text") or "").strip()
    ocr = (pages[0].get("ocr_text") or "").upper()
    joined = " ".join(c["text"] for c in result["chunks"]).upper()
    assert TOKENS["scan"] in ocr or TOKENS["scan"] in joined


def test_table_csv_html_json_and_image_description(tmp_path: Path) -> None:
    pdf = write_table_image_pdf(tmp_path / "table_image.pdf")
    result = parse_pdf(str(pdf), doc_id="pricing")
    assert result["ok"] is True
    tables = [c for c in result["chunks"] if c["kind"] == "table"]
    assert tables, "expected a table chunk from the fixture PDF"
    table = tables[0]["table"]
    assert table["csv"] and TOKENS["mortgage_rate"] in table["csv"]
    assert TOKENS["biz_rate"] in table["csv"]
    assert table["html"] and "<table" in table["html"].lower()
    assert TOKENS["mortgage_rate"] in table["html"]
    dumped = table["json"] if isinstance(table["json"], str) else json.dumps(table["json"], ensure_ascii=False)
    assert TOKENS["biz_rate"] in dumped
    assert tables[0]["page"] >= 1
    images = [c for c in result["chunks"] if c["kind"] == "image"]
    assert images, "expected an image chunk"
    desc = images[0]["image_description"] or ""
    assert desc.strip()
    assert images[0]["page"] >= 1
    if TESSERACT:
        # 无 tesseract 时（CI）解析器优雅降级为 "EMBEDDED IMAGE ..."，无 OCR 文本可断言
        assert TOKENS["chart"] in desc.upper() or TOKENS["chart"] in (images[0].get("text") or "").upper()
    shot = Path(images[0]["screenshot"] or images[0]["page_image"])
    assert shot.is_file()


def test_chapter_carries_forward_to_pages_without_heading(tmp_path: Path) -> None:
    pdf = write_chapter_carry_pdf(tmp_path / "carry.pdf")
    result = parse_pdf(str(pdf), doc_id="carry-doc")
    assert result["ok"] is True
    page2 = [c for c in result["chunks"] if c["page"] == 2]
    assert page2
    assert "第一" in (page2[0].get("chapter") or "")
    assert "CARRYTOKEN" in " ".join(c["text"] for c in page2)


def test_parse_rejects_path_outside_workspace(tmp_path: Path) -> None:
    result = parse_pdf("/etc/passwd")
    assert result["ok"] is False
    assert result.get("chunks") == []


def test_parse_rejects_output_dir_outside_workspace(tmp_path: Path) -> None:
    pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
    result = parse_pdf(str(pdf), output_dir="/tmp/kb-out-of-sandbox")
    assert result["ok"] is False
    assert result.get("chunks") == []


def test_mineru_failure_does_not_fabricate_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINERU_ENDPOINT", "http://127.0.0.1:1")
    pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
    result = parse_pdf(str(pdf))
    assert result["ok"] is False
    assert result["backend"] == "mineru"
    assert "MinerU" in result["message"]
    assert result.get("chunks") == []


def test_mineru_success_maps_pages_without_local_reparse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            body = json.dumps(
                {
                    "doc_id": "mineru-doc",
                    "pages": [{"page": 1, "text": "MINERU_BACKEND_TOKEN 第一章 解析"}],
                    "chunks": [
                        {
                            "chunk_id": "mineru-doc:p1:text:0",
                            "doc_id": "mineru-doc",
                            "page": 1,
                            "chapter": "第一章 解析",
                            "text": "MINERU_BACKEND_TOKEN",
                            "kind": "text",
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        monkeypatch.setenv("MINERU_ENDPOINT", f"http://{host}:{port}")
        pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
        result = parse_pdf(str(pdf))
        assert result["ok"] is True
        assert result["backend"] == "mineru"
        assert "MINERU_BACKEND_TOKEN" in json.dumps(result, ensure_ascii=False)
    finally:
        server.shutdown()


def test_mineru_malicious_doc_id_and_page_image_are_contained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            body = json.dumps(
                {
                    "doc_id": "../../../tmp/pwn",
                    "pages": [{"page": 1, "text": "SAFE_TOKEN 第一章", "page_image": "/etc/passwd"}],
                    "chunks": [
                        {
                            "chunk_id": "../../../evil",
                            "doc_id": "../../../tmp/pwn",
                            "page": 1,
                            "text": "SAFE_TOKEN",
                            "page_image": "/etc/passwd",
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        monkeypatch.setenv("MINERU_ENDPOINT", f"http://{host}:{port}")
        pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
        result = parse_pdf(str(pdf), doc_id="credit-policy")
        assert result["ok"] is True
        assert result["doc_id"] == "credit-policy"
        assert ".." not in result["doc_id"]
        assert result["chunks"]
        for chunk in result["chunks"]:
            assert chunk["doc_id"] == "credit-policy"
            assert ".." not in chunk["chunk_id"]
            assert "/etc/passwd" not in (chunk.get("page_image") or "")
            assert "SAFE_TOKEN" in (chunk.get("text") or "")
    finally:
        server.shutdown()


def test_mineru_pages_without_chunks_are_mapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            body = json.dumps(
                {
                    "doc_id": "mineru-pages",
                    "pages": [{"page": 1, "text": "第一章 映射 MINERU_PAGE_ONLY_TOKEN"}],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        monkeypatch.setenv("MINERU_ENDPOINT", f"http://{host}:{port}")
        pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
        result = parse_pdf(str(pdf))
        assert result["ok"] is True
        assert result["backend"] == "mineru"
        assert result["chunks"]
        assert any("MINERU_PAGE_ONLY_TOKEN" in (c.get("text") or "") for c in result["chunks"])
        assert result["chunks"][0]["page"] == 1
    finally:
        server.shutdown()
