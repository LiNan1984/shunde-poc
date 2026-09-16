# -*- coding: utf-8 -*-
"""HTTP embedding client: Bearer + model, no hash fallback when URL is set."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

from poc.kb_mcp.embed import embed_texts, embedding_backend_name
from poc.kb_mcp.fixtures import TOKENS, write_native_text_pdf
from poc.kb_mcp.ingest import ingest_pdf
from poc.kb_mcp.retrieve import search_knowledge


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("POC_LOAD_SECRETS", "0")
    for key in (
        "POC_EMBEDDING_URL",
        "POC_EMBEDDING_API_KEY",
        "POC_EMBEDDING_MODEL",
        "POC_CHAT_MODEL",
        "POC_CHAT_URL",
        "ARK_API_KEY",
        "ARK_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_hash_backend_when_url_unset() -> None:
    assert embedding_backend_name() == "hash"
    vecs = embed_texts(["ALPHAKEY", "unrelated"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 64


def test_url_without_key_does_not_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POC_EMBEDDING_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("POC_EMBEDDING_MODEL", "doubao-embedding-vision")
    with pytest.raises(RuntimeError, match="API Key"):
        embed_texts(["hello"])


def test_http_embed_sends_bearer_and_model_then_ranks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)
            seen["auth"] = self.headers.get("Authorization")
            seen["path"] = self.path
            payload = json.loads(raw.decode("utf-8"))
            seen["model"] = payload.get("model")
            inputs = payload.get("input") or []
            data = []
            for i, text in enumerate(inputs):
                # one-hot on whether ALPHAKEY is present
                vec = [1.0, 0.0, 0.0, 0.0] if "ALPHAKEY" in str(text) else [0.0, 1.0, 0.0, 0.0]
                data.append({"index": i, "embedding": vec})
            body = json.dumps({"data": data, "model": payload.get("model")}).encode()
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
        monkeypatch.setenv("POC_EMBEDDING_URL", f"http://{host}:{port}")
        monkeypatch.setenv("POC_EMBEDDING_MODEL", "doubao-embedding-vision")
        monkeypatch.setenv("POC_EMBEDDING_API_KEY", "ark-test-key")
        pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
        ingested = ingest_pdf(str(pdf), doc_id="credit-policy")
        assert ingested["ok"] is True
        assert ingested["stores"]["embedding"] == "doubao-embedding-vision"
        assert seen.get("auth") == "Bearer ark-test-key"
        assert seen.get("model") == "doubao-embedding-vision"
        assert str(seen.get("path") or "").endswith("/embeddings")
        hits = search_knowledge(TOKENS["alpha"], doc_id="credit-policy", mode="text")
        assert hits["ok"] is True
        assert any(TOKENS["alpha"] in (h.get("text") or "") for h in hits["hits"])
    finally:
        server.shutdown()


def test_http_embed_parallel_batches_preserve_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent batch embedding must return vectors aligned with input order."""
    import time as _time

    seen_batches: list[list[str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            inputs = [str(t) for t in (payload.get("input") or [])]
            seen_batches.append(inputs)
            _time.sleep(0.05)  # widen the window so batches overlap
            data = [
                {"index": i, "embedding": [float(i + 1), 0.0]}
                for i, text in enumerate(inputs)
            ]
            body = json.dumps({"data": data}).encode()
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
        monkeypatch.setenv("POC_EMBEDDING_URL", f"http://{host}:{port}/embeddings")
        monkeypatch.setenv("POC_EMBEDDING_MODEL", "test-model")
        monkeypatch.setenv("POC_EMBEDDING_API_KEY", "k")
        from poc.kb_mcp import embed as embed_mod

        texts = [f"chunk-{i}" for i in range(12)]  # 3 batches of _BATCH=4
        vectors = embed_mod._http_embed(f"http://{host}:{port}/embeddings", texts)
        assert len(vectors) == len(texts)
        # chunk i lives at sub-index i % 4 of its batch → one-hot value i % 4 + 1
        for i, vec in enumerate(vectors):
            assert vec == [float(i % embed_mod._BATCH + 1), 0.0], f"order broken at {i}"
        assert len(seen_batches) == 3
    finally:
        server.shutdown()
