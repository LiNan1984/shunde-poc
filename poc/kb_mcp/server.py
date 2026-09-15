# -*- coding: utf-8 -*-
"""FastMCP stdio server exposing knowledge-base ingest and retrieval tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .embed import load_embedding_secrets
from .ingest import ingest_pdf as _ingest_pdf
from .ingest import ingest_spreadsheet as _ingest_spreadsheet
from .parse import parse_pdf as _parse_pdf
from .retrieve import answer_knowledge as _answer_knowledge
from .retrieve import search_knowledge as _search_knowledge
from .vision import analyze_page as _analyze_page

mcp = FastMCP("kb-qa")


@mcp.tool()
def parse_document(path: str, doc_id: str = "", max_pages: int = 0) -> dict:
    """解析文档：把工作区 PDF 切成带页码/章节/表/图的块。"""
    return _parse_pdf(path, doc_id=doc_id, max_pages=max_pages)


@mcp.tool()
def ingest_document(path: str, doc_id: str = "", max_pages: int = 0) -> dict:
    """入库文档：解析 PDF 并写入页图、元数据、向量和图关系。"""
    return _ingest_pdf(path, doc_id=doc_id, max_pages=max_pages)


@mcp.tool()
def ingest_spreadsheet(path: str, doc_id: str = "", sample_rows: int = 5) -> dict:
    """索引表格元数据：只索引文件名/sheet/表头/样例行，用于定位文件。"""
    return _ingest_spreadsheet(path, doc_id=doc_id, sample_rows=sample_rows)


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
    """检索知识：BM25 + 文本向量 + 图像向量混合检索，命中带页码。"""
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
    """知识问答：按缺块/多模态/短句/概括作答，并引用页码章节。"""
    return _answer_knowledge(
        query,
        doc_id=doc_id,
        chapter=chapter,
        page_from=page_from,
        page_to=page_to,
        k=k,
    )


@mcp.tool()
def analyze_page(doc_id: str = "", path: str = "", page: int = 0, query: str = "") -> dict:
    """看图作答：把已入库文档的页面 PNG 喂给视觉模型，按图片内容回答精确数字/图表追问。

    用 doc_id + page 定位已入库页图，或直接给工作区内 PNG 路径。
    Answer from a stored page image via the vision model — use after
    search/answer hits kind=table/image chunks, to read exact numbers off the
    page. Never fabricates: unconfigured or failing vision endpoint returns
    ok=False with error_type (config/network/missing/empty_input/path_denied).
    """
    return _analyze_page(doc_id=doc_id, path=path, page=page, query=query)


def main() -> None:
    load_embedding_secrets()
    mcp.run()


if __name__ == "__main__":
    main()
