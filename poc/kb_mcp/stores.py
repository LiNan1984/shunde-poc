# -*- coding: utf-8 -*-
"""Storage ports: object store, MySQL/sqlite, ElasticSearch/local vectors, GALASYBASE/local graph."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from poc.excel_guard_mcp.guards import _workspace_root

logger = logging.getLogger("poc.kb")


class VectorStore(Protocol):
    def upsert(self, chunk_id: str, vector: list[float], meta: dict[str, Any]) -> None: ...
    def knn(self, vector: list[float], k: int) -> list[tuple[str, float]]: ...
    def delete(self, chunk_id: str) -> None: ...


class RelationalStore(Protocol):
    def upsert_document(self, doc_id: str, meta: dict[str, Any]) -> None: ...
    def upsert_chunk(self, chunk: dict[str, Any]) -> None: ...
    def list_chunks(self, **filters: Any) -> list[dict[str, Any]]: ...
    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None: ...
    def delete_chunk(self, chunk_id: str) -> None: ...


class GraphStore(Protocol):
    def upsert_relations(self, chunk: dict[str, Any]) -> None: ...
    def neighbors(self, chunk_id: str) -> list[str]: ...
    def delete_chunk(self, chunk_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Local fallbacks (always available)
# ---------------------------------------------------------------------------


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_page_image(self, doc_id: str, page: int, src: Path) -> str:
        from poc.excel_guard_mcp.guards import _open_contained, _resolve_allowed_path

        safe = "".join(c for c in (doc_id or "") if c.isalnum() or c in "-_") or "doc"
        dest_dir = (self.root / safe).resolve()
        if not dest_dir.is_relative_to(self.root):
            raise ValueError(f"doc_id escapes object store: {doc_id}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = (dest_dir / f"page-{int(page)}.png").resolve()
        if not dest.is_relative_to(self.root):
            raise ValueError("page image destination escapes object store")
        resolved_src, err = _resolve_allowed_path(str(src))
        if err is not None or resolved_src is None:
            return ""
        fh, open_err = _open_contained(resolved_src)
        if open_err is not None or fh is None:
            return ""
        try:
            data = fh.read()
        finally:
            fh.close()
        dest.write_bytes(data)
        return str(dest)


class LocalRelationalStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    path TEXT,
                    n_pages INTEGER,
                    backend TEXT
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT,
                    page INTEGER,
                    chapter TEXT,
                    kind TEXT,
                    text TEXT,
                    table_csv TEXT,
                    table_html TEXT,
                    table_json TEXT,
                    image_description TEXT,
                    page_image TEXT,
                    screenshot TEXT,
                    prev_id TEXT,
                    next_id TEXT
                );
                """
            )

    def upsert_document(self, doc_id: str, meta: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO documents(doc_id, path, n_pages, backend) "
                "VALUES (?, ?, ?, ?)",
                (doc_id, meta.get("path", ""), int(meta.get("n_pages") or 0),
                 meta.get("backend", "")),
            )

    def upsert_chunk(self, chunk: dict[str, Any]) -> None:
        table = chunk.get("table") or {}
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO chunks("
                "chunk_id, doc_id, page, chapter, kind, text, table_csv, table_html, "
                "table_json, image_description, page_image, screenshot, prev_id, next_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    chunk["chunk_id"],
                    chunk.get("doc_id", ""),
                    int(chunk.get("page") or 0),
                    chunk.get("chapter") or "",
                    chunk.get("kind") or "text",
                    chunk.get("text") or "",
                    table.get("csv") or "",
                    table.get("html") or "",
                    json.dumps(table.get("json"), ensure_ascii=False) if table.get("json") is not None else "",
                    chunk.get("image_description") or "",
                    chunk.get("page_image") or "",
                    chunk.get("screenshot") or "",
                    chunk.get("prev_id") or "",
                    chunk.get("next_id") or "",
                ),
            )

    def list_chunks(
        self,
        doc_id: str = "",
        chapter: str = "",
        page_from: int = 0,
        page_to: int = 0,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM chunks WHERE 1=1"
        params: list[Any] = []
        if doc_id:
            sql += " AND doc_id = ?"
            params.append(doc_id)
        if chapter:
            sql += " AND chapter LIKE ?"
            params.append(f"%{chapter}%")
        if page_from > 0:
            sql += " AND page >= ?"
            params.append(page_from)
        if page_to > 0:
            sql += " AND page <= ?"
            params.append(page_to)
        sql += " ORDER BY doc_id, page, chunk_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_chunk(self, chunk_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE chunk_id = ?", (chunk_id,))


class LocalVectorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self.path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def upsert(self, chunk_id: str, vector: list[float], meta: dict[str, Any]) -> None:
        data = self._load()
        data[chunk_id] = {"vector": vector, "kind": meta.get("kind", "text")}
        self._save(data)

    def knn(self, vector: list[float], k: int) -> list[tuple[str, float]]:
        from .embed import cosine

        data = self._load()
        scored = [
            (cid, cosine(vector, rec["vector"]))
            for cid, rec in data.items()
            if rec.get("vector")
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: max(1, k)]

    def knn_kind(self, vector: list[float], k: int, kind: str) -> list[tuple[str, float]]:
        from .embed import cosine

        data = self._load()
        scored = [
            (cid, cosine(vector, rec["vector"]))
            for cid, rec in data.items()
            if rec.get("vector") and rec.get("kind") == kind
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: max(1, k)]

    def delete(self, chunk_id: str) -> None:
        data = self._load()
        data.pop(chunk_id, None)
        self._save(data)


class LocalGraphStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self.path.write_text(json.dumps({"edges": []}), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8") or '{"edges":[]}')

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def upsert_relations(self, chunk: dict[str, Any]) -> None:
        data = self._load()
        edges: list[dict[str, str]] = data.setdefault("edges", [])
        doc_id = chunk.get("doc_id") or ""
        chapter = chunk.get("chapter") or ""
        page = int(chunk.get("page") or 0)
        cid = chunk["chunk_id"]
        wanted = [
            {"src": f"doc:{doc_id}", "dst": f"chapter:{doc_id}:{chapter}", "rel": "HAS_CHAPTER"},
            {"src": f"chapter:{doc_id}:{chapter}", "dst": f"page:{doc_id}:{page}", "rel": "HAS_PAGE"},
            {"src": f"page:{doc_id}:{page}", "dst": cid, "rel": "HAS_CHUNK"},
        ]
        if chunk.get("next_id"):
            wanted.append({"src": cid, "dst": chunk["next_id"], "rel": "NEXT"})
        existing = {(e["src"], e["dst"], e["rel"]) for e in edges}
        for edge in wanted:
            key = (edge["src"], edge["dst"], edge["rel"])
            if key not in existing:
                edges.append(edge)
                existing.add(key)
        self._save(data)

    def neighbors(self, chunk_id: str) -> list[str]:
        data = self._load()
        out: list[str] = []
        for edge in data.get("edges") or []:
            if edge.get("rel") != "NEXT":
                continue
            if edge.get("src") == chunk_id:
                out.append(edge["dst"])
            if edge.get("dst") == chunk_id:
                out.append(edge["src"])
        return out

    def delete_chunk(self, chunk_id: str) -> None:
        """Keep NEXT edges so neighbor expansion can still walk past a hole."""
        return None


# ---------------------------------------------------------------------------
# Live adapters (used only when the named service actually pings)
# ---------------------------------------------------------------------------


class ElasticsearchVectorStore:
    """REST adapter for the POC-required ElasticSearch vector backend."""

    def __init__(self, url: str, index: str = "poc_kb_chunks") -> None:
        self.url = url.rstrip("/")
        self.index = index

    def ping(self) -> bool:
        try:
            with urllib.request.urlopen(self.url + "/", timeout=2) as resp:
                return 200 <= getattr(resp, "status", 200) < 300
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def _ensure_index(self, dims: int) -> None:
        mapping = {
            "mappings": {
                "properties": {
                    "vector": {"type": "dense_vector", "dims": dims, "index": True, "similarity": "cosine"},
                    "kind": {"type": "keyword"},
                }
            }
        }
        req = urllib.request.Request(
            f"{self.url}/{self.index}",
            data=json.dumps(mapping).encode(),
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in {400, 409}:
                raise

    def upsert(self, chunk_id: str, vector: list[float], meta: dict[str, Any]) -> None:
        self._ensure_index(max(1, len(vector)))
        body = json.dumps({"vector": vector, "kind": meta.get("kind", "text")}).encode()
        encoded = urllib.parse.quote(chunk_id, safe="")
        req = urllib.request.Request(
            f"{self.url}/{self.index}/_doc/{encoded}",
            data=body,
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()

    def knn(self, vector: list[float], k: int) -> list[tuple[str, float]]:
        body = json.dumps({
            "knn": {
                "field": "vector",
                "query_vector": vector,
                "k": max(1, k),
                "num_candidates": max(10, k * 4),
            }
        }).encode()
        req = urllib.request.Request(
            f"{self.url}/{self.index}/_search",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        hits = payload.get("hits", {}).get("hits", [])
        return [(h["_id"], float(h.get("_score") or 0.0)) for h in hits]

    def delete(self, chunk_id: str) -> None:
        encoded = urllib.parse.quote(chunk_id, safe="")
        req = urllib.request.Request(
            f"{self.url}/{self.index}/_doc/{encoded}",
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise


class MySQLRelationalStore:
    """Adapter for the POC-required MySQL metadata backend (optional pymysql)."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._ready = False

    def _connect(self):
        import pymysql

        parsed = urllib.parse.urlparse(self.url)
        return pymysql.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            database=(parsed.path or "/poc").lstrip("/") or "poc",
            connect_timeout=2,
            charset="utf8mb4",
            autocommit=True,
        )

    def ping(self) -> bool:
        try:
            import pymysql  # noqa: F401
        except ImportError:
            logger.warning("MYSQL_URL set but pymysql is not installed; using sqlite fallback")
            return False
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS documents ("
                    "doc_id VARCHAR(191) PRIMARY KEY, path TEXT, n_pages INT, backend VARCHAR(64))"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS chunks ("
                    "chunk_id VARCHAR(191) PRIMARY KEY, doc_id VARCHAR(191), page INT, "
                    "chapter TEXT, kind VARCHAR(32), text MEDIUMTEXT, table_csv MEDIUMTEXT, "
                    "table_html MEDIUMTEXT, table_json MEDIUMTEXT, image_description TEXT, "
                    "page_image TEXT, screenshot TEXT, prev_id VARCHAR(191), next_id VARCHAR(191))"
                )
            conn.close()
            self._ready = True
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("MySQL ping failed: %s", exc)
            return False

    def upsert_document(self, doc_id: str, meta: dict[str, Any]) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "REPLACE INTO documents(doc_id, path, n_pages, backend) VALUES (%s,%s,%s,%s)",
                    (doc_id, meta.get("path", ""), int(meta.get("n_pages") or 0),
                     meta.get("backend", "")),
                )
        finally:
            conn.close()

    def upsert_chunk(self, chunk: dict[str, Any]) -> None:
        table = chunk.get("table") or {}
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "REPLACE INTO chunks(chunk_id, doc_id, page, chapter, kind, text, "
                    "table_csv, table_html, table_json, image_description, page_image, "
                    "screenshot, prev_id, next_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        chunk["chunk_id"],
                        chunk.get("doc_id", ""),
                        int(chunk.get("page") or 0),
                        chunk.get("chapter") or "",
                        chunk.get("kind") or "text",
                        chunk.get("text") or "",
                        table.get("csv") or "",
                        table.get("html") or "",
                        json.dumps(table.get("json"), ensure_ascii=False)
                        if table.get("json") is not None else "",
                        chunk.get("image_description") or "",
                        chunk.get("page_image") or "",
                        chunk.get("screenshot") or "",
                        chunk.get("prev_id") or "",
                        chunk.get("next_id") or "",
                    ),
                )
        finally:
            conn.close()

    def list_chunks(
        self,
        doc_id: str = "",
        chapter: str = "",
        page_from: int = 0,
        page_to: int = 0,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM chunks WHERE 1=1"
        params: list[Any] = []
        if doc_id:
            sql += " AND doc_id = %s"
            params.append(doc_id)
        if chapter:
            sql += " AND chapter LIKE %s"
            params.append(f"%{chapter}%")
        if page_from > 0:
            sql += " AND page >= %s"
            params.append(page_from)
        if page_to > 0:
            sql += " AND page <= %s"
            params.append(page_to)
        sql += " ORDER BY doc_id, page, chunk_id"
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM chunks WHERE chunk_id = %s", (chunk_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row, strict=False))
        finally:
            conn.close()

    def delete_chunk(self, chunk_id: str) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chunks WHERE chunk_id = %s", (chunk_id,))
        finally:
            conn.close()


class GalaxybaseGraphStore:
    """Config-only adapter for 创邻 GALASYBASE.

    The wire protocol is proprietary and not documented in this repo. When
    ``GALASYBASE_URL`` is set we still refuse to invent a fake live write;
    every mutation goes to the local graph fallback. Filter by
    doc_id / chapter / page continues to work through that fallback.
    """

    def __init__(self, url: str | None, local: LocalGraphStore) -> None:
        self.url = (url or "").strip()
        self.local = local
        self.live = False

    def ping(self) -> bool:
        if not self.url:
            return False
        try:
            with urllib.request.urlopen(self.url, timeout=2) as resp:
                return 200 <= getattr(resp, "status", 200) < 300
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def upsert_relations(self, chunk: dict[str, Any]) -> None:
        if self.url:
            logger.warning(
                "GALASYBASE_URL is set but the proprietary protocol is not "
                "implemented; using local graph fallback (not claiming live success)"
            )
        self.local.upsert_relations(chunk)

    def neighbors(self, chunk_id: str) -> list[str]:
        return self.local.neighbors(chunk_id)

    def delete_chunk(self, chunk_id: str) -> None:
        self.local.delete_chunk(chunk_id)


@dataclass
class StoreBundle:
    objects: LocalObjectStore
    relational: Any
    vector: Any
    graph: Any
    names: dict[str, str] = field(default_factory=dict)
    root: Path = field(default_factory=Path)


def store_root() -> tuple[Path | None, dict | None]:
    root, err = _workspace_root()
    if err or root is None:
        return None, err
    return root / "kb_store", None


def open_stores(root: Path | None = None) -> StoreBundle:
    """Pick live ES/MySQL/GALASYBASE when they ping; otherwise local fallbacks."""
    if root is None:
        resolved, err = store_root()
        if err or resolved is None:
            raise RuntimeError((err or {}).get("message") or "workspace unavailable")
        root = resolved
    root.mkdir(parents=True, exist_ok=True)

    objects = LocalObjectStore(root / "objects")
    relational: Any = LocalRelationalStore(root / "meta.sqlite")
    rel_name = "local"
    mysql_url = (os.environ.get("MYSQL_URL") or os.environ.get("POC_MYSQL_URL") or "").strip()
    if mysql_url:
        mysql = MySQLRelationalStore(mysql_url)
        if mysql.ping():
            relational = mysql
            rel_name = "mysql"

    vector: Any = LocalVectorStore(root / "vectors.json")
    vec_name = "local"
    es_url = (
        os.environ.get("ELASTICSEARCH_URL")
        or os.environ.get("POC_ES_URL")
        or ""
    ).strip()
    if es_url:
        es = ElasticsearchVectorStore(es_url)
        if es.ping():
            vector = es
            vec_name = "elasticsearch"

    local_graph = LocalGraphStore(root / "graph.json")
    gb_url = (os.environ.get("GALASYBASE_URL") or os.environ.get("POC_GALASYBASE_URL") or "").strip()
    graph: Any = GalaxybaseGraphStore(gb_url or None, local_graph)
    graph_name = "local"

    return StoreBundle(
        objects=objects,
        relational=relational,
        vector=vector,
        graph=graph,
        names={
            "object": "local",
            "relational": rel_name,
            "vector": vec_name,
            "graph": graph_name,
            "graph_adapter": "galasybase",
        },
        root=root,
    )
