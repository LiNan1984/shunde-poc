# -*- coding: utf-8 -*-
"""Hybrid retrieval: BM25 + text vectors + image vectors + filters + neighbor expansion."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from .embed import (
    embed_texts,
    image_embedding_endpoint,
    rerank_scores,
    reranker_endpoint,
    reranker_model,
    synthesize_answer,
    tokenize,
    vl_embed,
)
from .errors import with_error_type
from .stores import StoreBundle, open_stores

RERANK_TOP_N = 16


def classify_query(query: str) -> str:
    q = (query or "").strip()
    if any(key in q for key in ("总结", "概括", "总体", "综述", "全文")):
        return "overview"
    if any(key in q for key in ("表格", "图片", "截图", "图表", "表里", "图里")):
        return "multimodal"
    cjk = sum(1 for ch in q if "\u4e00" <= ch <= "\u9fff")
    if 3 <= cjk <= 5 and len(q) <= 8:
        return "short"
    if 3 <= len(q) <= 5:
        return "short"
    return "fact"


class _BM25:
    def __init__(self, docs: list[list[str]]) -> None:
        self.docs = docs
        self.n = len(docs)
        self.df: Counter[str] = Counter()
        self.doc_len = [len(d) for d in docs]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 1.0
        for doc in docs:
            for token in set(doc):
                self.df[token] += 1
        self.k1 = 1.5
        self.b = 0.75

    def scores(self, query_tokens: list[str]) -> list[float]:
        out: list[float] = []
        for i, doc in enumerate(self.docs):
            tf = Counter(doc)
            score = 0.0
            dl = self.doc_len[i] or 1
            for token in query_tokens:
                freq = tf.get(token, 0)
                if not freq:
                    continue
                n = self.df[token]
                idf = math.log(1.0 + (self.n - n + 0.5) / (n + 0.5))
                denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += idf * (freq * (self.k1 + 1)) / denom
            out.append(score)
        return out


def _rrf(rank_lists: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rank_lists:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _hit_from_chunk(chunk: dict[str, Any], score: float, source: str) -> dict[str, Any]:
    table = None
    raw_json = chunk.get("table_json") or ""
    if chunk.get("kind") == "table":
        table = {
            "csv": chunk.get("table_csv") or "",
            "html": chunk.get("table_html") or "",
            "json": raw_json,
        }
    return {
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk.get("doc_id") or "",
        "page": int(chunk.get("page") or 0),
        "chapter": chunk.get("chapter") or "",
        "kind": chunk.get("kind") or "text",
        "text": chunk.get("text") or "",
        "image_description": chunk.get("image_description") or "",
        "table": table,
        "score": score,
        "source": source,
    }


def search_knowledge(
    query: str,
    *,
    doc_id: str = "",
    chapter: str = "",
    page_from: int = 0,
    page_to: int = 0,
    mode: str = "hybrid",
    k: int = 8,
    stores: StoreBundle | None = None,
) -> dict[str, Any]:
    if not (query or "").strip():
        return {"ok": False, "hits": [], "message": "query 不能为空 / query required"}
    try:
        bundle = stores or open_stores()
    except RuntimeError as exc:
        return {"ok": False, "hits": [], "message": str(exc)}
    candidates = bundle.relational.list_chunks(
        doc_id=doc_id, chapter=chapter, page_from=page_from, page_to=page_to
    )
    if not candidates:
        return {"ok": True, "hits": [], "message": "无候选块 / no indexed chunks"}

    by_id = {c["chunk_id"]: c for c in candidates}
    q_tokens = tokenize(query)
    bm25 = _BM25([tokenize(c.get("text") or "") for c in candidates])
    bm25_scores = bm25.scores(q_tokens)
    bm25_ranked = [
        cid
        for cid, _score in sorted(
            zip([c["chunk_id"] for c in candidates], bm25_scores, strict=False),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    try:
        q_vec = embed_texts([query])[0]
    except RuntimeError as exc:
        return with_error_type({"ok": False, "hits": [], "message": str(exc)})

    knn_fn = getattr(bundle.vector, "knn", None)
    text_ranked: list[str] = []
    image_ranked: list[str] = []
    try:
        if callable(knn_fn):
            text_ranked = [cid for cid, _ in knn_fn(q_vec, max(k * 4, 16)) if cid in by_id]
            knn_kind = getattr(bundle.vector, "knn_kind", None)
            if callable(knn_kind):
                # Image retrieval uses a query vector in the same space as the
                # stored image vectors when the multimodal endpoint is set;
                # otherwise fall back to the text embedding + kind filter.
                image_qvec = q_vec
                if image_embedding_endpoint():
                    try:
                        image_qvec = vl_embed([{"text": query}])[0]
                    except Exception as exc:  # noqa: BLE001 — no silent substitution
                        return with_error_type(
                            {
                                "ok": False,
                                "hits": [],
                                "message": f"图像查询向量失败 / image query embedding failed: {exc}",
                            }
                        )
                image_ranked = [
                    cid for cid, _ in knn_kind(image_qvec, max(k * 4, 16), "image") if cid in by_id
                ]
            else:
                image_ranked = [
                    cid for cid in text_ranked if by_id[cid].get("kind") == "image"
                ]
    except Exception as exc:  # noqa: BLE001
        return with_error_type(
            {"ok": False, "hits": [], "message": f"向量检索失败 / vector search failed: {exc}"}
        )

    mode_norm = (mode or "hybrid").lower()
    if mode_norm == "bm25":
        fused = {cid: float(i + 1) for i, cid in enumerate(bm25_ranked)}
        source = "bm25"
        ordered = bm25_ranked
    elif mode_norm in {"text", "vector"}:
        fused = {cid: float(i + 1) for i, cid in enumerate(text_ranked)}
        source = "text_vec"
        ordered = text_ranked
    elif mode_norm == "image":
        fused = {cid: float(i + 1) for i, cid in enumerate(image_ranked)}
        source = "image_vec"
        ordered = image_ranked
    else:
        lists = [bm25_ranked, text_ranked]
        # Image vectors only join hybrid when the question is about 表/图;
        # otherwise page-header images drown out body text (RRF of a short
        # image list gives logos a free rank boost).
        if classify_query(query) == "multimodal":
            lists.append(image_ranked)
        fused = _rrf(lists)
        source = "hybrid"
        ordered = sorted(fused, key=lambda cid: fused[cid], reverse=True)

    rerank_note = ""
    reranked = False
    if source == "hybrid" and ordered and reranker_endpoint():
        top = ordered[:RERANK_TOP_N]
        rest = ordered[RERANK_TOP_N:]
        docs: list[str] = []
        idxs: list[int] = []
        for i, cid in enumerate(top):
            chunk = by_id.get(cid) or {}
            doc = chunk.get("text") or chunk.get("image_description") or chunk.get("table_csv") or ""
            if doc:
                docs.append(doc)
                idxs.append(i)
        try:
            scores = rerank_scores(query, docs) if docs else []
        except RuntimeError as exc:
            # Keep the RRF order on reranker failure, but say so — never claim
            # a rerank that did not happen.
            rerank_note = f"；重排序失败，保留 RRF 排序：{exc}"
        else:
            if scores and len(scores) == len(docs):
                ranked = sorted(zip(idxs, scores, strict=False), key=lambda p: p[1], reverse=True)
                reranked_ids = [top[i] for i, _score in ranked]
                skipped = [top[i] for i in range(len(top)) if i not in set(idxs)]
                ordered = reranked_ids + skipped + rest
                reranked = True
                rerank_note = (
                    f"；已用 {reranker_model()} 对前 {len(reranked_ids)}/{len(top)} 个候选重排序"
                )
            else:
                rerank_note = "；重排序未返回有效分数，保留 RRF 排序"

    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cid in ordered:
        if cid in seen or cid not in by_id:
            continue
        seen.add(cid)
        score = fused.get(cid, 0.0)
        hits.append(_hit_from_chunk(by_id[cid], score, source))
        for nb in bundle.graph.neighbors(cid):
            if nb in seen or nb not in by_id:
                continue
            seen.add(nb)
            hits.append(_hit_from_chunk(by_id[nb], score * 0.5, "neighbor"))
        if len(hits) >= max(k * 2, k):
            break

    result: dict[str, Any] = {
        "ok": True,
        "hits": hits[: max(1, k * 2)],
        "message": f"{len(hits)} hits via {source}" + rerank_note,
        "mode": mode_norm,
    }
    if reranked:
        result["reranked"] = True
    return result


def _diversify_by_page(hits: list[dict[str, Any]], per_page: int = 1) -> list[dict[str, Any]]:
    seen: dict[int, int] = {}
    out: list[dict[str, Any]] = []
    for hit in hits:
        page = int(hit.get("page") or 0)
        used = seen.get(page, 0)
        if used >= per_page:
            continue
        seen[page] = used + 1
        out.append(hit)
    return out


def answer_knowledge(
    query: str,
    *,
    doc_id: str = "",
    chapter: str = "",
    page_from: int = 0,
    page_to: int = 0,
    k: int = 8,
    stores: StoreBundle | None = None,
) -> dict[str, Any]:
    kind = classify_query(query)
    retrieved = search_knowledge(
        query,
        doc_id=doc_id,
        chapter=chapter,
        page_from=page_from,
        page_to=page_to,
        mode="hybrid",
        k=max(k, 12) if kind == "overview" else k,
        stores=stores,
    )
    if not retrieved.get("ok"):
        return {**retrieved, "kind": kind, "answer": "", "sources": []}
    hits = list(retrieved.get("hits") or [])
    if kind == "overview":
        textual = [h for h in hits if h.get("kind") in {"text", "table"}]
        hits = _diversify_by_page(textual or hits, per_page=1)
    elif kind == "multimodal":
        preferred = [h for h in hits if h.get("kind") in {"table", "image"}]
        if preferred:
            hits = preferred + [h for h in hits if h not in preferred]

    sources = []
    parts: list[str] = []
    for hit in hits[: max(3, 8 if kind == "overview" else 4)]:
        text = (hit.get("text") or hit.get("image_description") or "").strip()
        if not text:
            continue
        page = int(hit.get("page") or 0)
        chapter_name = hit.get("chapter") or ""
        cite = f"第{page}页"
        if chapter_name:
            cite += f" {chapter_name}"
        parts.append(f"{text}（来源：{cite}）")
        sources.append(
            {
                "chunk_id": hit.get("chunk_id"),
                "doc_id": hit.get("doc_id"),
                "page": page,
                "chapter": chapter_name,
                "kind": hit.get("kind"),
                "text": text,
            }
        )
    extractive = "\n".join(parts) if parts else "未检索到相关内容 / no hits"
    synthesized = synthesize_answer(query, parts) if parts else ""
    answer = synthesized or extractive
    return {
        "ok": True,
        "kind": kind,
        "answer": answer,
        "sources": sources,
        "hits": hits,
        "message": retrieved.get("message") or "",
    }
