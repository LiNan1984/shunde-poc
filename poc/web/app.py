# -*- coding: utf-8 -*-
"""Minimal FastAPI app for shunde-poc.harness-agent.app."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

REPO = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
DATA = Path(os.environ.get("POC_WORKSPACE") or (REPO / "data"))

app = FastAPI(title="shunde-poc", version="1.0.0")
if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

ASSISTANTS = [
    {
        "id": "excel-agent",
        "name": "Excel问答助手",
        "skill": "excel-qa-bank",
        "mcp": "excel-guard",
        "ask": "损坏表.xlsx 是不是坏了",
    },
    {
        "id": "kb-agent",
        "name": "多模态文件助手",
        "skill": "kb-qa-bank",
        "mcp": "kb-qa",
        "ask": "逾期90天认定标准 / 再平衡思路 / AI 两类金融风险",
    },
    {
        "id": "ops-agent",
        "name": "运营助手",
        "skill": "ops-assistant",
        "mcp": "ops-data",
        "ask": "今天调用量怎么样 / 最近一次失败的工具",
    },
    {
        "id": "report-agent",
        "name": "报告可视化助手",
        "skill": "report-visualizer",
        "mcp": "report-visualizer",
        "ask": "用分行业务.json 出交叉表和五类图 docx",
    },
]


class AskBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    doc_id: str = ""


def _ensure_kb() -> None:
    os.environ.setdefault("POC_LOAD_SECRETS", "0")
    os.environ["POC_WORKSPACE"] = str(DATA)
    DATA.mkdir(parents=True, exist_ok=True)
    pdf = DATA / "信贷政策.pdf"
    if not pdf.is_file():
        from poc.kb_mcp.fixtures import write_native_text_pdf, write_table_image_pdf

        write_native_text_pdf(pdf)
        write_table_image_pdf(DATA / "产品定价.pdf")
    store = DATA / "kb_store" / "meta.sqlite"
    if not store.is_file():
        from poc.kb_mcp.ingest import ingest_pdf

        ingest_pdf(str(pdf), doc_id="credit-policy")
        table = DATA / "产品定价.pdf"
        if table.is_file():
            ingest_pdf(str(table), doc_id="pricing")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "shunde-poc", "version": "1.0.0"}


@app.get("/api/health")
def api_health() -> dict:
    return health()


@app.get("/api/assistants")
def assistants() -> dict:
    return {"ok": True, "assistants": ASSISTANTS}


@app.post("/api/kb/answer")
def kb_answer(body: AskBody) -> dict:
    try:
        _ensure_kb()
        from poc.kb_mcp.retrieve import answer_knowledge

        result = answer_knowledge(body.query, doc_id=body.doc_id)
        return result
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"ok": False, "message": f"检索失败: {exc}", "answer": ""},
            status_code=500,
        )


@app.get("/")
def index() -> HTMLResponse:
    index_file = STATIC / "index.html"
    if index_file.is_file():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>shunde-poc</h1>", status_code=200)


@app.get("/architecture.png")
def architecture() -> FileResponse:
    png = (
        REPO
        / "docs"
        / "演示材料"
        / "preview"
        / "poc-status-architecture.png"
    )
    if png.is_file():
        return FileResponse(png, media_type="image/png")
    fallback = STATIC / "poc-status-architecture.png"
    return FileResponse(fallback, media_type="image/png")
