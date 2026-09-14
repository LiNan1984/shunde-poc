# -*- coding: utf-8 -*-
"""Live ES/MySQL selection + honest GALASYBASE fallback (no fake protocol)."""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

from poc.kb_mcp.embed import load_embedding_secrets
from poc.kb_mcp.stores import (
    GalaxybaseGraphStore,
    LocalGraphStore,
    MySQLRelationalStore,
    open_stores,
)


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("POC_LOAD_SECRETS", "0")
    for key in (
        "ELASTICSEARCH_URL",
        "MYSQL_URL",
        "GALASYBASE_URL",
        "POC_ES_URL",
        "POC_MYSQL_URL",
        "POC_GALASYBASE_URL",
        "QWENPAW_SECRET_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def test_middleware_env_file_fills_store_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "middleware.env").write_text(
        "ELASTICSEARCH_URL=http://127.0.0.1:19200\n"
        "MYSQL_URL=mysql://poc:secret@127.0.0.1:13306/poc_kb\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POC_LOAD_SECRETS", "1")
    monkeypatch.setenv("QWENPAW_SECRET_DIR", str(secret))
    load_embedding_secrets()
    assert os.environ["ELASTICSEARCH_URL"] == "http://127.0.0.1:19200"
    assert os.environ["MYSQL_URL"] == "mysql://poc:secret@127.0.0.1:13306/poc_kb"


def test_middleware_env_does_not_override_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "middleware.env").write_text(
        "ELASTICSEARCH_URL=http://from-file:9200\n"
        "MYSQL_URL=mysql://poc:from-file@127.0.0.1:13306/poc_kb\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POC_LOAD_SECRETS", "1")
    monkeypatch.setenv("QWENPAW_SECRET_DIR", str(secret))
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://already-set:9200")
    monkeypatch.setenv("MYSQL_URL", "mysql://poc:from-env@127.0.0.1:13306/poc")
    load_embedding_secrets()
    assert os.environ["ELASTICSEARCH_URL"] == "http://already-set:9200"
    assert os.environ["MYSQL_URL"] == "mysql://poc:from-env@127.0.0.1:13306/poc"


def test_open_stores_uses_elasticsearch_when_cluster_pings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"version":{"number":"8.17.0"}}')

        def log_message(self, *_args: object) -> None:
            return

    server, url = _serve(Handler)
    try:
        monkeypatch.setenv("ELASTICSEARCH_URL", url)
        bundle = open_stores()
        assert bundle.names["vector"] == "elasticsearch"
        assert bundle.names["relational"] == "local"
    finally:
        server.shutdown()


def test_open_stores_reads_middleware_env_for_es_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"version":{"number":"8.17.0"}}')

        def log_message(self, *_args: object) -> None:
            return

    server, url = _serve(Handler)
    try:
        secret = tmp_path / "secret"
        secret.mkdir()
        (secret / "middleware.env").write_text(
            f"ELASTICSEARCH_URL={url}\n", encoding="utf-8"
        )
        monkeypatch.setenv("POC_LOAD_SECRETS", "1")
        monkeypatch.setenv("QWENPAW_SECRET_DIR", str(secret))
        bundle = open_stores()
        assert bundle.names["vector"] == "elasticsearch"
    finally:
        server.shutdown()


def test_es_upsert_uses_dimension_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_PUT(self) -> None:  # noqa: N802
            seen["path"] = self.path
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"result":"created"}')

        def log_message(self, *_args: object) -> None:
            return

    from poc.kb_mcp.stores import ElasticsearchVectorStore

    server, url = _serve(Handler)
    try:
        store = ElasticsearchVectorStore(url)
        store.upsert("c1", [0.1, 0.2, 0.3], {"kind": "text"})
        assert "_d3/" in seen["path"]
        assert "refresh=true" in seen["path"]
    finally:
        server.shutdown()


def test_open_stores_stays_local_when_es_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://127.0.0.1:1")
    bundle = open_stores()
    assert bundle.names["vector"] == "local"


def test_galaxybase_http_200_still_not_live(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args: object) -> None:
            return

    server, url = _serve(Handler)
    try:
        local = LocalGraphStore(tmp_path / "graph.json")
        store = GalaxybaseGraphStore(url, local)
        assert store.ping() is False
        assert store.live is False
        store.upsert_relations(
            {
                "chunk_id": "c1",
                "doc_id": "credit-policy",
                "page": 1,
                "chapter": "第一章",
                "next_id": "c2",
            }
        )
        assert store.neighbors("c1") == ["c2"]
        payload = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
        assert any(edge.get("rel") == "NEXT" for edge in payload["edges"])
    finally:
        server.shutdown()


def test_open_stores_graph_stays_local_when_galasybase_http_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args: object) -> None:
            return

    server, url = _serve(Handler)
    try:
        monkeypatch.setenv("GALASYBASE_URL", url)
        bundle = open_stores()
        assert bundle.names["graph"] == "local"
        assert bundle.names["graph_adapter"] == "galasybase"
        assert bundle.names["graph_live"] is False
        assert bundle.graph.live is False
        assert bundle.graph.ping() is False
    finally:
        server.shutdown()


def test_mysql_ping_does_not_log_password(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="poc.kb"):
        mysql = MySQLRelationalStore("mysql://poc:super-secret@127.0.0.1:1/poc")
        assert mysql.ping() is False
    blob = "\n".join(record.getMessage() for record in caplog.records)
    assert "super-secret" not in blob
    assert "mysql://poc" not in blob
