# -*- coding: utf-8 -*-
"""FastMCP stdio server exposing knowledge-base ingest and retrieval tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .embed import load_embedding_secrets
from .ingest import ingest_pdf as _ingest_pdf
from .parse import parse_pdf as _parse_pdf
from .retrieve import answer_knowledge as _answer_knowledge
from .retrieve import search_knowledge as _search_knowledge

mcp = FastMCP("kb-qa")


@mcp.tool()
def parse_document(path: str, doc_id: str = "", max_pages: int = 0) -> dict:
    """Parse a workspace PDF into chunks with page/chapter, tables, images, and page PNGs."""
    return _parse_pdf(path, doc_id=doc_id, max_pages=max_pages)


@mcp.tool()
def ingest_document(path: str, doc_id: str = "", max_pages: int = 0) -> dict:
    """Parse a workspace PDF and write page images, metadata, vectors, and graph relations."""
    return _ingest_pdf(path, doc_id=doc_id, max_pages=max_pages)


@mcp.tool()
def search_knowledge(
    query: str,
    doc_id: str = "",
    chapter: str = "",
    page_from: int = 0,
    page_to: int = 0,
    mode: str = "hybrid",
    k: int = 8,
) -> dict:
    """Hybrid search (BM25 + text vector + image vector) with doc/chapter/page filters."""
    return _search_knowledge(
        query,
        doc_id=doc_id,
        chapter=chapter,
        page_from=page_from,
        page_to=page_to,
        mode=mode,
        k=k,
    )


@mcp.tool()
def answer_knowledge(
    query: str,
    doc_id: str = "",
    chapter: str = "",
    page_from: int = 0,
    page_to: int = 0,
    k: int = 8,
) -> dict:
    """Answer 缺块/多模态/短句/概括 queries from indexed chunks, citing page and chapter."""
    return _answer_knowledge(
        query,
        doc_id=doc_id,
        chapter=chapter,
        page_from=page_from,
        page_to=page_to,
        k=k,
    )


def main() -> None:
    load_embedding_secrets()
    mcp.run()


if __name__ == "__main__":
    main()
