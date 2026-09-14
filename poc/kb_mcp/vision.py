# -*- coding: utf-8 -*-
"""看图作答：把已入库文档的页面 PNG 喂给视觉模型，按图片内容回答追问。

``analyze_page`` locates a stored page PNG either directly by workspace path
or via ``doc_id`` + ``page`` in the relational store, encodes it as a base64
data URL, and asks the configured vision model (POC_VISION_MODEL) to answer
the user query strictly from the image. Answers never get fabricated: an
unconfigured or failing vision endpoint returns ``ok=False`` with an
``error_type`` instead of text.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from poc.excel_guard_mcp.guards import _resolve_allowed_path

from .embed import chat_completion, chat_endpoint, provider_api_key, vision_model
from .errors import with_error_type
from .stores import open_stores

_SYSTEM_PROMPT = (
    "你是银行文档看图助手。只依据图片内容作答："
    "图中出现的数字必须原样引用，不得换算、估算或改写；"
    "图片里没有的信息要如实回答图中没有，禁止编造。"
)

_USER_PROMPT_SUFFIX = (
    "\n\n（请只依据图片内容回答：图中数字原样引用；图中没有的信息请明确说明图中没有。）"
)


def _fail(message: str) -> dict[str, Any]:
    return with_error_type({"ok": False, "message": message})


def _config_error() -> dict[str, Any]:
    return with_error_type({
        "ok": False,
        "message": (
            "未配置视觉模型 / vision model not configured："
            "需要在 ~/.qwenpaw.secret/middleware.env 配置 "
            "POC_CHAT_URL、POC_ALIYUN_API_KEY、POC_VISION_MODEL"
        ),
    })


def _locate_page_image(doc_id: str, path: str, page: int) -> tuple[str, str, int, dict[str, Any] | None]:
    """Resolve the page PNG. Returns (page_image, doc_id, page, error_dict)."""
    path = (path or "").strip()
    doc_id = (doc_id or "").strip()
    if path:
        resolved, err = _resolve_allowed_path(path)
        if err is not None or resolved is None:
            message = str((err or {}).get("message") or "路径越界 / path denied")
            return "", "", 0, _fail(message)
        if not resolved.is_file():
            return "", "", 0, _fail(f"文件不存在 / file not found: {path}")
        return str(resolved), doc_id, 0, None
    if doc_id and page > 0:
        try:
            bundle = open_stores()
        except RuntimeError as exc:
            return "", "", 0, _fail(str(exc))
        chunks = bundle.relational.list_chunks(doc_id=doc_id, page_from=page, page_to=page)
        for chunk in chunks:
            page_image = (chunk.get("page_image") or "").strip()
            if page_image:
                return page_image, doc_id, int(page), None
        return "", "", 0, _fail(
            f"页面图不存在 / page image not found for doc_id={doc_id}, page={page}"
        )
    return "", "", 0, _fail("页面定位参数缺失 / path or doc_id+page required")


def analyze_page(doc_id: str = "", path: str = "", page: int = 0, query: str = "") -> dict[str, Any]:
    """Answer a question from a stored page PNG via the vision model.

    Locate the page image by workspace ``path``, or by ``doc_id`` + ``page``
    from the indexed chunks. Returns ok=True with the vision answer plus
    provenance (doc_id / page / page_image / model), or ok=False with an
    ``error_type`` (empty_input / path_denied / missing / config / network /
    parse) — never a fabricated answer.
    """
    query = (query or "").strip()
    if not query:
        return _fail("query 不能为空 / query required")

    page_image, resolved_doc_id, page_no, err = _locate_page_image(doc_id, path, page)
    if err is not None:
        return err

    model = vision_model()
    if not model or not chat_endpoint() or not provider_api_key():
        return _config_error()

    try:
        data = Path(page_image).read_bytes()
    except OSError as exc:
        return _fail(f"无法读取页面图 / cannot open page image: {exc}")
    data_url = "data:image/png;base64," + base64.b64encode(data).decode("ascii")

    answer = chat_completion(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": f"问题：{query}{_USER_PROMPT_SUFFIX}"},
                ],
            },
        ],
        model=model,
        temperature=0.1,
        max_tokens=800,
        timeout=120.0,
    )
    if not answer:
        return _fail("视觉端点失败，未返回答案 / vision endpoint failed: empty response")

    return {
        "ok": True,
        "answer": answer,
        "doc_id": resolved_doc_id,
        "page": page_no,
        "page_image": page_image,
        "model": model,
        "query": query,
        "message": "已按页面图作答 / answered from page image",
    }
