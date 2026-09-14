#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prove kb stores talk to live ES + MySQL; GALASYBASE stays honest local."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("POC_LOAD_SECRETS", "1")
os.environ.setdefault("POC_WORKSPACE", str(ROOT))

from poc.kb_mcp.embed import hash_embed, load_embedding_secrets  # noqa: E402
from poc.kb_mcp.stores import open_stores  # noqa: E402


def main() -> int:
    load_embedding_secrets()
    bundle = open_stores()
    names = dict(bundle.names)
    print(json.dumps({"stores": names}, ensure_ascii=False))

    cid = "middleware-smoke-chunk"
    vec = hash_embed("顺德农商行信贷政策 第一档")
    bundle.vector.upsert(cid, vec, {"kind": "text"})
    knn = bundle.vector.knn(vec, 3)
    bundle.relational.upsert_document(
        "middleware-smoke",
        {"path": "smoke", "n_pages": 1, "backend": "smoke"},
    )
    bundle.relational.upsert_chunk(
        {
            "chunk_id": cid,
            "doc_id": "middleware-smoke",
            "page": 1,
            "chapter": "smoke",
            "kind": "text",
            "text": "顺德农商行信贷政策",
            "table": {},
        }
    )
    rows = bundle.relational.list_chunks(doc_id="middleware-smoke")
    es_url = (os.environ.get("ELASTICSEARCH_URL") or "").rstrip("/")
    es_count = None
    if es_url:
        req = urllib.request.Request(f"{es_url}/poc_kb_chunks*/_count")
        with urllib.request.urlopen(req, timeout=10) as resp:
            es_count = json.loads(resp.read().decode("utf-8")).get("count")

    report = {
        "knn_hit": bool(knn and knn[0][0] == cid),
        "mysql_row": bool(rows),
        "es_doc_count": es_count,
        "vector": names.get("vector"),
        "relational": names.get("relational"),
        "graph": names.get("graph"),
        "graph_live": names.get("graph_live"),
    }
    print(json.dumps(report, ensure_ascii=False))
    if names.get("vector") != "elasticsearch":
        print("FAIL: vector backend is not elasticsearch", file=sys.stderr)
        return 1
    if names.get("relational") != "mysql":
        print("FAIL: relational backend is not mysql", file=sys.stderr)
        return 1
    if not report["knn_hit"] or not report["mysql_row"]:
        print("FAIL: live upsert/knn/list did not round-trip", file=sys.stderr)
        return 1
    if names.get("graph") != "local":
        print("FAIL: graph claimed live without Galaxybase protocol", file=sys.stderr)
        return 1
    if names.get("graph_live") is not False:
        print("FAIL: graph_live must be boolean False", file=sys.stderr)
        return 1
    if getattr(bundle.graph, "live", True) is not False:
        print("FAIL: graph.live must be False", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
