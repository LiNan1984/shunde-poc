# -*- coding: utf-8 -*-
"""Health-check FastAPI router for QwenPaw POC.

Exposes ``GET /api/poc/health`` returning ``{"status": "ok"}`` with
HTTP 200. Mounted via QwenPaw's plugin API
(``api.register_http_router(router, prefix="/poc")``) — no kernel
patching required (红线 2).

The router is importable on its own, which lets the test suite hit it
without a running QwenPaw instance.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health() -> JSONResponse:
    """Liveness probe. Always 200 unless the process is dead."""
    return JSONResponse({"status": "ok"})


@router.get("/health/version")
def health_version() -> JSONResponse:
    """Same as /health but echoes the POC package version if importable.

    Kept under /health so a single LB probe can be expanded without
    changing the upstream URL when operators want more signal later.
    """
    version = "unknown"
    try:
        from poc import __version__ as poc_version  # type: ignore[attr-defined]

        version = poc_version
    except (ImportError, AttributeError):
        pass
    return JSONResponse({"status": "ok", "poc_version": version})