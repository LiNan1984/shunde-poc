# -*- coding: utf-8 -*-
"""Hash embeddings, plus optional OpenAI-compatible HTTP (Ark doubao-embedding-vision)."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("poc.kb")

EMBED_DIM = 64
_MAX_CHARS = 6000
_BATCH = 8
_HTTP_TIMEOUT = 30.0


def tokenize(text: str) -> list[str]:
    """Latin words + CJK unigrams/bigrams so 3–5 字 queries still match."""
    text = (text or "").lower()
    tokens: list[str] = []
    buf: list[str] = []
    cjk: list[str] = []

    def flush_buf() -> None:
        if buf:
            tokens.append("".join(buf))
            buf.clear()

    def flush_cjk() -> None:
        if not cjk:
            return
        tokens.extend(cjk)
        if len(cjk) >= 2:
            tokens.extend(cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1))
        cjk.clear()

    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            flush_buf()
            cjk.append(ch)
        elif ch.isalnum():
            flush_cjk()
            buf.append(ch)
        else:
            flush_buf()
            flush_cjk()
    flush_buf()
    flush_cjk()
    return tokens


def hash_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    vec = [0.0] * dim
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n))) or 1.0
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n))) or 1.0
    return dot / (na * nb)


def _secrets_enabled() -> bool:
    return os.environ.get("POC_LOAD_SECRETS", "1").strip().lower() not in {"0", "false", "no"}


def load_embedding_secrets() -> None:
    """Fill missing env vars from ``$QWENPAW_SECRET_DIR/embedding.env``. Never override."""
    if not _secrets_enabled():
        return
    raw_dir = os.environ.get("QWENPAW_SECRET_DIR") or str(
        Path.home() / ".qwenpaw.secret"
    )
    path = Path(raw_dir).expanduser() / "embedding.env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("cannot read embedding secret file: %s", exc)
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def embedding_endpoint() -> str:
    load_embedding_secrets()
    raw = (
        os.environ.get("POC_EMBEDDING_URL")
        or os.environ.get("ARK_BASE_URL")
        or os.environ.get("QWEN_EMBEDDING_URL")
        or os.environ.get("QWEN3_EMBEDDING_URL")
        or ""
    ).strip()
    if not raw:
        return ""
    base = raw.rstrip("/")
    if base.endswith("/embeddings"):
        return base
    return base + "/embeddings"


def embedding_model() -> str:
    load_embedding_secrets()
    return (
        os.environ.get("POC_EMBEDDING_MODEL")
        or os.environ.get("ARK_EMBEDDING_MODEL")
        or "doubao-embedding-vision"
    ).strip()


def embedding_api_key() -> str:
    load_embedding_secrets()
    return (
        os.environ.get("POC_EMBEDDING_API_KEY")
        or os.environ.get("ARK_API_KEY")
        or ""
    ).strip()


def embedding_backend_name() -> str:
    return embedding_model() if embedding_endpoint() else "hash"


def reranker_endpoint() -> str:
    load_embedding_secrets()
    return (
        os.environ.get("POC_RERANKER_URL")
        or os.environ.get("QWEN_RERANKER_URL")
        or os.environ.get("QWEN3_RERANKER_URL")
        or ""
    ).strip()


def chat_endpoint() -> str:
    load_embedding_secrets()
    raw = (os.environ.get("POC_CHAT_URL") or "").strip()
    if raw:
        base = raw.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"
    model = chat_model()
    embed_base = (
        os.environ.get("POC_EMBEDDING_URL")
        or os.environ.get("ARK_BASE_URL")
        or ""
    ).strip()
    if model and embed_base:
        base = embed_base.rstrip("/")
        if base.endswith("/embeddings"):
            base = base[: -len("/embeddings")]
        return base.rstrip("/") + "/chat/completions"
    return ""


def chat_model() -> str:
    load_embedding_secrets()
    return (os.environ.get("POC_CHAT_MODEL") or "").strip()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Use the configured HTTP embedding endpoint; else hash embed.

    A configured-but-failing endpoint raises — callers must not silently
    substitute vectors (that would fabricate a live embedding success).
    """
    url = embedding_endpoint()
    if url:
        return _http_embed(url, texts)
    return [hash_embed(t) for t in texts]


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = embedding_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _http_embed(url: str, texts: list[str]) -> list[list[float]]:
    if not embedding_api_key():
        raise RuntimeError(
            "已配置 Embedding URL 但缺少 API Key / embedding URL set but POC_EMBEDDING_API_KEY is empty"
        )
    model = embedding_model()
    cleaned = [(t or "")[:_MAX_CHARS] or " " for t in texts]
    out: list[list[float]] = []
    for start in range(0, len(cleaned), _BATCH):
        batch = cleaned[start : start + _BATCH]
        payload = json.dumps({"model": model, "input": batch, "encoding_format": "float"}).encode()
        req = urllib.request.Request(url, data=payload, method="POST", headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            data = body.get("data") or body.get("embeddings") if isinstance(body, dict) else None
            if not isinstance(data, list) or len(data) != len(batch):
                raise RuntimeError("Embedding 端点返回无法解析 / embedding response malformed")
            ordered = sorted(
                data,
                key=lambda item: int(item.get("index", 0)) if isinstance(item, dict) else 0,
            )
            for item in ordered:
                vec = item.get("embedding") if isinstance(item, dict) else item
                if not isinstance(vec, list) or not vec:
                    raise RuntimeError("Embedding 端点缺少向量 / embedding missing vector")
                out.append([float(x) for x in vec])
        except RuntimeError:
            raise
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(
                f"Embedding 端点失败 / embedding HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError,
                UnicodeDecodeError, TypeError, ValueError, AttributeError) as exc:
            raise RuntimeError(f"Embedding 端点失败 / embedding endpoint failed: {exc}") from exc
    if len(out) != len(texts):
        raise RuntimeError("Embedding 数量与输入不一致 / embedding count mismatch")
    return out


def synthesize_answer(query: str, snippets: list[str]) -> str:
    """Optional LLM rewrite. Empty string means caller should use extractive fallback."""
    url = chat_endpoint()
    model = chat_model()
    if not url or not model:
        return ""
    if not embedding_api_key():
        return ""
    context = "\n".join(snippets[:8])[:8000]
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 600,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是银行 POC 知识库助手。只根据给定检索片段作答，"
                    "必须写出页码（及章节，若片段里有）。不要编造片段中没有的数字或结论。"
                ),
            },
            {
                "role": "user",
                "content": f"问题：{query}\n\n检索片段：\n{context}\n\n请作答。",
            },
        ],
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST", headers=_headers()
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        choices = body.get("choices") if isinstance(body, dict) else None
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = (message.get("content") or "").strip()
        if content:
            return content
        return (message.get("reasoning_content") or "").strip()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError,
            UnicodeDecodeError, TypeError, ValueError, AttributeError, urllib.error.HTTPError) as exc:
        logger.warning("chat synthesis failed: %s", exc)
        return ""
