# -*- coding: utf-8 -*-
"""Offline tests: true rerank (cross-encoder), real image vectors, local dim guard.

All cases run with POC_LOAD_SECRETS=0; live behaviour is exercised by
monkeypatching the base-module functions (``poc.kb_mcp.embed.vl_embed``) or
the consumer-module references (``poc.kb_mcp.retrieve.rerank_scores``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import poc.kb_mcp.embed as embed_mod
import poc.kb_mcp.retrieve as retrieve_mod
from poc.kb_mcp.fixtures import write_native_text_pdf, write_table_image_pdf
from poc.kb_mcp.ingest import ingest_pdf
from poc.kb_mcp.retrieve import search_knowledge
from poc.kb_mcp.stores import LocalVectorStore, open_stores

_VL_DIM = 2560


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("POC_LOAD_SECRETS", "0")
    for key in (
        "MINERU_ENDPOINT",
        "POC_EMBEDDING_URL",
        "POC_EMBEDDING_API_KEY",
        "POC_CHAT_MODEL",
        "POC_CHAT_URL",
        "ARK_API_KEY",
        "ARK_BASE_URL",
        "ELASTICSEARCH_URL",
        "MYSQL_URL",
        "GALASYBASE_URL",
        "POC_ES_URL",
        "POC_MYSQL_URL",
        "POC_GALASYBASE_URL",
        "POC_RERANKER_URL",
        "POC_RERANKER_MODEL",
        "POC_IMAGE_EMBEDDING_URL",
        "POC_IMAGE_EMBEDDING_MODEL",
        "POC_IMAGE_EMBEDDING_API_KEY",
        "POC_ALIYUN_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def _ingest_native(tmp_path: Path, doc_id: str = "credit-policy") -> dict:
    pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
    return ingest_pdf(str(pdf), doc_id=doc_id)


# ---------------------------------------------------------------------------
# True rerank on the hybrid path
# ---------------------------------------------------------------------------


def test_rerank_reorders_hybrid_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _ingest_native(tmp_path)["ok"] is True
    base = search_knowledge("信贷政策 ALPHAKEY")
    assert base["ok"] is True
    assert "reranked" not in base
    assert len(base["hits"]) >= 2

    monkeypatch.setenv("POC_RERANKER_URL", "http://127.0.0.1:1/rerank")
    seen: dict[str, object] = {}

    def fake_scores(query: str, docs: list[str]) -> list[float]:
        seen["query"] = query
        seen["docs"] = list(docs)
        # Invert the RRF order: last candidate scores highest.
        return [float(i) for i in range(len(docs))]

    monkeypatch.setattr(retrieve_mod, "rerank_scores", fake_scores)

    reranked = search_knowledge("信贷政策 ALPHAKEY")
    assert reranked["ok"] is True
    assert reranked["reranked"] is True
    assert reranked["hits"][0]["chunk_id"] != base["hits"][0]["chunk_id"]
    assert {h["chunk_id"] for h in reranked["hits"]} == {h["chunk_id"] for h in base["hits"]}
    assert "qwen3.7-text-rerank" in reranked["message"]
    assert seen["query"] == "信贷政策 ALPHAKEY"
    assert seen["docs"] and all(isinstance(d, str) and d for d in seen["docs"])  # type: ignore[union-attr]


def test_rerank_not_applied_to_single_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _ingest_native(tmp_path)["ok"] is True
    monkeypatch.setenv("POC_RERANKER_URL", "http://127.0.0.1:1/rerank")
    monkeypatch.setattr(
        retrieve_mod, "rerank_scores", lambda q, docs: [0.0 for _ in docs]
    )
    bm25 = search_knowledge("ALPHAKEY", mode="bm25")
    assert bm25["ok"] is True
    assert "reranked" not in bm25


def test_rerank_failure_keeps_rrf_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _ingest_native(tmp_path)["ok"] is True
    base = search_knowledge("信贷政策 ALPHAKEY")
    assert base["ok"] is True

    monkeypatch.setenv("POC_RERANKER_URL", "http://127.0.0.1:1/rerank")

    def boom(query: str, docs: list[str]) -> list[float]:
        raise RuntimeError("Reranker 端点失败 / rerank HTTP error: 500")

    monkeypatch.setattr(retrieve_mod, "rerank_scores", boom)

    result = search_knowledge("信贷政策 ALPHAKEY")
    assert result["ok"] is True
    assert "reranked" not in result
    assert [h["chunk_id"] for h in result["hits"]] == [h["chunk_id"] for h in base["hits"]]
    assert "重排序失败" in result["message"]
    assert "HTTP error: 500" in result["message"]


def test_rerank_not_configured_leaves_no_trace(tmp_path: Path) -> None:
    assert _ingest_native(tmp_path)["ok"] is True
    result = search_knowledge("信贷政策 ALPHAKEY")
    assert result["ok"] is True
    assert "reranked" not in result
    assert "重排序" not in result["message"]
    assert "qwen3.7-text-rerank" not in result["message"]


# ---------------------------------------------------------------------------
# Image retrieval uses the shared image+text query vector
# ---------------------------------------------------------------------------


def test_image_query_vector_used_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POC_IMAGE_EMBEDDING_URL", "http://127.0.0.1:1/vl")
    ing_seen: list[list[dict]] = []

    def fake_ingest_vl(contents: list[dict]) -> list[list[float]]:
        ing_seen.append(list(contents))
        return [[0.5] * _VL_DIM for _ in contents]

    monkeypatch.setattr(embed_mod, "vl_embed", fake_ingest_vl)
    pdf = write_table_image_pdf(tmp_path / "table_image.pdf")
    ingested = ingest_pdf(str(pdf), doc_id="pricing")
    assert ingested["ok"] is True
    assert ingested["stores"]["image_embedding"] == "qwen3-vl-embedding"
    assert any("image" in c for batch in ing_seen for c in batch)

    q_seen: list[list[dict]] = []

    def fake_query_vl(contents: list[dict]) -> list[list[float]]:
        q_seen.append(list(contents))
        return [[0.9] * _VL_DIM for _ in contents]

    monkeypatch.setattr(retrieve_mod, "vl_embed", fake_query_vl)

    result = search_knowledge("图片 RATECHART 在哪一页", doc_id="pricing")
    assert result["ok"] is True
    assert q_seen and q_seen[-1] == [{"text": "图片 RATECHART 在哪一页"}]
    assert any(h["kind"] == "image" for h in result["hits"])


def test_image_query_vector_failure_fails_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert ingest_pdf(
        str(write_table_image_pdf(tmp_path / "table_image.pdf")), doc_id="pricing"
    )["ok"] is True

    monkeypatch.setenv("POC_IMAGE_EMBEDDING_URL", "http://127.0.0.1:1/vl")

    def boom(contents: list[dict]) -> list[list[float]]:
        raise RuntimeError("图像向量端点失败 / image embedding HTTP error: 500")

    monkeypatch.setattr(retrieve_mod, "vl_embed", boom)

    result = search_knowledge("图片 RATECHART 在哪一页", doc_id="pricing")
    assert result["ok"] is False
    assert result.get("error_type") == "network"
    assert "图像查询向量失败" in result["message"]


# ---------------------------------------------------------------------------
# Ingest: real image vectors for image chunks
# ---------------------------------------------------------------------------


def test_ingest_uses_image_vectors_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POC_IMAGE_EMBEDDING_URL", "http://127.0.0.1:1/vl")
    seen: list[list[dict]] = []

    def fake_vl(contents: list[dict]) -> list[list[float]]:
        seen.append(list(contents))
        return [[0.25] * _VL_DIM for _ in contents]

    monkeypatch.setattr(embed_mod, "vl_embed", fake_vl)

    pdf = write_table_image_pdf(tmp_path / "table_image.pdf")
    result = ingest_pdf(str(pdf), doc_id="pricing")
    assert result["ok"] is True
    assert result["stores"]["image_embedding"] == "qwen3-vl-embedding"
    assert seen, "vl_embed must be called for image chunks"
    for batch in seen:
        for item in batch:
            assert set(item) == {"image"}
            assert item["image"].startswith("data:image/png;base64,")

    rows = open_stores().relational.list_chunks(doc_id="pricing")
    image_rows = [r for r in rows if r["kind"] == "image"]
    assert image_rows, "fixture must produce image chunks"
    data = json.loads((tmp_path / "kb_store" / "vectors.json").read_text(encoding="utf-8"))
    for row in image_rows:
        assert data[row["chunk_id"]]["dim"] == _VL_DIM
    text_rows = [r for r in rows if r["kind"] == "text"]
    assert text_rows
    for row in text_rows:
        assert data[row["chunk_id"]]["dim"] == 64, "text chunks keep the caption/text vector"


def test_ingest_image_embedding_failure_is_not_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POC_IMAGE_EMBEDDING_URL", "http://127.0.0.1:1/vl")

    def boom(contents: list[dict]) -> list[list[float]]:
        raise RuntimeError("图像向量端点失败 / image embedding HTTP error: 500")

    monkeypatch.setattr(embed_mod, "vl_embed", boom)

    pdf = write_table_image_pdf(tmp_path / "table_image.pdf")
    result = ingest_pdf(str(pdf), doc_id="pricing")
    assert result["ok"] is False
    assert result.get("error_type") == "network"
    assert "图像向量" in result["message"]
    assert "HTTP error: 500" in result["message"]
    # Nothing committed behind the failure — no silent text-vector substitute.
    assert open_stores().relational.list_chunks(doc_id="pricing") == []


def test_ingest_without_image_endpoint_keeps_caption_vectors(tmp_path: Path) -> None:
    pdf = write_table_image_pdf(tmp_path / "table_image.pdf")
    result = ingest_pdf(str(pdf), doc_id="pricing")
    assert result["ok"] is True
    assert result["stores"]["image_embedding"] == "text_caption"

    rows = open_stores().relational.list_chunks(doc_id="pricing")
    data = json.loads((tmp_path / "kb_store" / "vectors.json").read_text(encoding="utf-8"))
    image_rows = [r for r in rows if r["kind"] == "image"]
    assert image_rows
    for row in image_rows:
        assert data[row["chunk_id"]]["dim"] == 64


# ---------------------------------------------------------------------------
# LocalVectorStore dimension guard
# ---------------------------------------------------------------------------


def test_local_vector_store_skips_dim_mismatch(tmp_path: Path) -> None:
    store = LocalVectorStore(tmp_path / "vectors.json")
    store.upsert("a3", [1.0, 0.0, 0.0], {"kind": "text"})
    store.upsert("b4", [0.0, 1.0, 0.0, 0.0], {"kind": "text"})
    store.upsert("i4", [0.0, 0.0, 1.0, 0.0], {"kind": "image"})

    assert [cid for cid, _ in store.knn([0.0, 1.0, 0.0, 0.0], 10)] == ["b4", "i4"]
    assert [cid for cid, _ in store.knn([1.0, 0.0, 0.0], 10)] == ["a3"]
    assert [cid for cid, _ in store.knn_kind([0.0, 0.0, 1.0, 0.0], 10, "image")] == ["i4"]
    assert store.knn_kind([1.0, 0.0, 0.0], 10, "image") == []


def test_local_vector_store_infers_dim_for_legacy_records(tmp_path: Path) -> None:
    path = tmp_path / "vectors.json"
    LocalVectorStore(path)  # creates the file
    legacy = {
        "old4": {"vector": [1.0, 0.0, 0.0, 0.0], "kind": "text"},
        "old3": {"vector": [0.0, 1.0, 0.0], "kind": "text"},
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")
    store = LocalVectorStore(path)
    assert [cid for cid, _ in store.knn([1.0, 0.0, 0.0, 0.0], 10)] == ["old4"]
    assert [cid for cid, _ in store.knn([0.0, 1.0, 0.0], 10)] == ["old3"]
