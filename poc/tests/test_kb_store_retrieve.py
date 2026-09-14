# -*- coding: utf-8 -*-
"""Ingest three stores + BM25/vector/image/filter + four QA types + missing-chunk recall."""

from __future__ import annotations

from pathlib import Path

import pytest

from poc.kb_mcp.fixtures import (
    TOKENS,
    write_chapter_carry_pdf,
    write_native_text_pdf,
    write_overlap_pdf,
    write_scan_pdf,
    write_table_image_pdf,
)
from poc.kb_mcp.ingest import drop_chunk, ingest_pdf
from poc.kb_mcp.retrieve import answer_knowledge, classify_query, search_knowledge
from poc.kb_mcp.stores import (
    ElasticsearchVectorStore,
    GalaxybaseGraphStore,
    MySQLRelationalStore,
    open_stores,
)


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
    ):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def _ingest_native(tmp_path: Path) -> dict:
    pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
    return ingest_pdf(str(pdf), doc_id="credit-policy")


def test_ingest_writes_object_relational_vector_graph(tmp_path: Path) -> None:
    result = _ingest_native(tmp_path)
    assert result["ok"] is True
    assert result["n_chunks"] >= 1
    assert result["stores"]["vector"] in {"local", "elasticsearch"}
    assert result["stores"]["relational"] in {"local", "mysql"}
    assert result["stores"]["graph"] == "local"
    assert result["stores"]["graph_live"] is False
    assert result["stores"]["object"]
    assert result["stores"]["graph_adapter"] == "galasybase"
    root = tmp_path / "kb_store"
    assert (root / "meta.sqlite").is_file()
    assert (root / "vectors.json").is_file()
    assert (root / "graph.json").is_file()
    pngs = list((root / "objects").rglob("*.png"))
    assert pngs, "object store should hold page images"
    assert pngs[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    bundle = open_stores()
    rows = bundle.relational.list_chunks(doc_id="credit-policy")
    assert rows
    assert all(r["page"] >= 1 for r in rows)
    assert any("第一" in (r.get("chapter") or "") for r in rows)


def test_live_backend_adapters_exist_and_env_names_are_poc_required() -> None:
    src = Path(ElasticsearchVectorStore.__init__.__code__.co_filename).read_text(
        encoding="utf-8"
    )
    assert "ELASTICSEARCH_URL" in src
    assert "MYSQL_URL" in src
    assert "GALASYBASE_URL" in src
    assert ElasticsearchVectorStore.__name__ == "ElasticsearchVectorStore"
    assert MySQLRelationalStore.__name__ == "MySQLRelationalStore"
    assert GalaxybaseGraphStore.__name__ == "GalaxybaseGraphStore"
    es = ElasticsearchVectorStore("http://127.0.0.1:1")
    assert es.ping() is False
    mysql = MySQLRelationalStore("mysql://root@127.0.0.1:1/poc")
    assert mysql.ping() is False


def test_bm25_text_vector_image_vector_and_filters(tmp_path: Path) -> None:
    _ingest_native(tmp_path)
    table_pdf = write_table_image_pdf(tmp_path / "table_image.pdf")
    ingested = ingest_pdf(str(table_pdf), doc_id="pricing")
    assert ingested["ok"] is True

    bm25 = search_knowledge(TOKENS["alpha"], mode="bm25")
    assert bm25["ok"] is True
    assert any(TOKENS["alpha"] in (h["text"] or "") for h in bm25["hits"])
    assert all(h.get("page") for h in bm25["hits"] if TOKENS["alpha"] in (h["text"] or ""))

    text_vec = search_knowledge(TOKENS["beta"], mode="text")
    assert text_vec["ok"] is True
    assert any(TOKENS["beta"] in (h["text"] or "") for h in text_vec["hits"])

    image = search_knowledge(TOKENS["chart"], mode="image")
    assert image["ok"] is True
    blob = " ".join(
        (h.get("text") or "") + " " + (h.get("image_description") or "")
        for h in image["hits"]
    )
    assert TOKENS["chart"] in blob.upper()

    page2 = search_knowledge("风险管理", page_from=2, page_to=2, doc_id="credit-policy")
    assert page2["ok"] is True
    assert page2["hits"]
    assert all(h["page"] == 2 for h in page2["hits"])
    assert all(h["doc_id"] == "credit-policy" for h in page2["hits"])

    chapter = search_knowledge("信贷", chapter="第一章", doc_id="credit-policy")
    assert chapter["ok"] is True
    assert chapter["hits"]
    assert all("第一" in (h.get("chapter") or "") for h in chapter["hits"])


def test_reingest_replaces_old_chunks(tmp_path: Path) -> None:
    pdf = write_native_text_pdf(tmp_path / "native_text.pdf")
    first = ingest_pdf(str(pdf), doc_id="credit-policy")
    assert first["ok"] is True
    before = open_stores().relational.list_chunks(doc_id="credit-policy")
    assert any(r["page"] == 3 for r in before)
    second = ingest_pdf(str(pdf), doc_id="credit-policy", max_pages=1)
    assert second["ok"] is True
    after = open_stores().relational.list_chunks(doc_id="credit-policy")
    assert after
    assert all(r["page"] == 1 for r in after)


def test_chapter_filter_includes_carried_pages(tmp_path: Path) -> None:
    pdf = write_chapter_carry_pdf(tmp_path / "carry.pdf")
    assert ingest_pdf(str(pdf), doc_id="carry-doc")["ok"] is True
    hits = search_knowledge("CARRYTOKEN", chapter="第一章", doc_id="carry-doc")
    assert hits["ok"] is True
    assert any("CARRYTOKEN" in (h["text"] or "") for h in hits["hits"])
    assert all("第一" in (h.get("chapter") or "") for h in hits["hits"])


def test_missing_chunk_recalled_from_overlap_or_neighbor(tmp_path: Path) -> None:
    pdf = write_overlap_pdf(tmp_path / "overlap.pdf")
    result = ingest_pdf(str(pdf), doc_id="overlap-doc")
    assert result["ok"] is True
    bundle = open_stores()
    rows = bundle.relational.list_chunks(doc_id="overlap-doc")
    holders = [r for r in rows if TOKENS["missing"] in (r.get("text") or "")]
    assert len(holders) >= 2, "overlap chunking must place the token in more than one chunk"
    dropped = holders[0]["chunk_id"]
    drop = drop_chunk(dropped)
    assert drop["ok"] is True
    remaining = open_stores().relational.get_chunk(dropped)
    assert remaining is None
    found = search_knowledge(TOKENS["missing"], doc_id="overlap-doc")
    assert found["ok"] is True
    assert any(TOKENS["missing"] in (h["text"] or "") for h in found["hits"])


def test_four_qa_types_on_real_ingest_path(tmp_path: Path) -> None:
    _ingest_native(tmp_path)
    ingest_pdf(str(write_table_image_pdf(tmp_path / "table_image.pdf")), doc_id="pricing")
    ingest_pdf(str(write_overlap_pdf(tmp_path / "overlap.pdf")), doc_id="overlap-doc")

    holders = [
        r for r in open_stores().relational.list_chunks(doc_id="overlap-doc")
        if TOKENS["missing"] in (r.get("text") or "")
    ]
    drop_chunk(holders[0]["chunk_id"])
    missing = answer_knowledge(TOKENS["missing"], doc_id="overlap-doc")
    assert missing["ok"] is True
    assert TOKENS["missing"] in missing["answer"]
    assert missing["sources"]
    assert missing["sources"][0]["page"]

    multimodal = answer_knowledge("表格里的经营贷款利率", doc_id="pricing")
    assert multimodal["ok"] is True
    assert classify_query("表格里的经营贷款利率") == "multimodal"
    assert TOKENS["biz_rate"] in multimodal["answer"]
    assert multimodal["sources"]
    assert multimodal["sources"][0]["page"]
    assert "第" in multimodal["answer"] and "页" in multimodal["answer"]

    picture = answer_knowledge("图片 RATECHART 在哪一页", doc_id="pricing")
    assert picture["ok"] is True
    assert TOKENS["chart"] in picture["answer"].upper()
    assert picture["sources"][0]["page"]

    short_q = "信贷政策"
    assert classify_query(short_q) == "short"
    short = answer_knowledge(short_q, doc_id="credit-policy")
    assert short["ok"] is True
    assert short["kind"] == "short"
    assert short["sources"]
    assert short["sources"][0]["doc_id"] == "credit-policy"
    assert TOKENS["alpha"] in short["answer"] or "信贷" in short["answer"]

    overview_q = "概括这份信贷文档的总体要点"
    assert classify_query(overview_q) == "overview"
    overview = answer_knowledge(overview_q, doc_id="credit-policy")
    assert overview["ok"] is True
    assert overview["kind"] == "overview"
    pages = {s["page"] for s in overview["sources"]}
    assert len(pages) >= 2, f"overview must cite more than one page, got {overview['sources']}"
    body = overview["answer"]
    assert TOKENS["alpha"] in body
    assert TOKENS["beta"] in body or TOKENS["gamma"] in body


def test_galaxybase_adapter_fallback_still_filters(tmp_path: Path) -> None:
    _ingest_native(tmp_path)
    hits = search_knowledge("ALPHAKEY", chapter="第一章", doc_id="credit-policy")
    assert hits["ok"] is True
    assert hits["hits"]
    assert all("第一" in (h.get("chapter") or "") for h in hits["hits"])
    bundle = open_stores()
    assert isinstance(bundle.graph, GalaxybaseGraphStore)
    assert bundle.names["graph_adapter"] == "galasybase"
    assert bundle.names["graph"] == "local"
    assert bundle.names["graph_live"] is False
    assert bundle.graph.live is False
    assert bundle.graph.ping() is False
