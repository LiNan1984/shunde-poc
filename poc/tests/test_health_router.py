"""Tests for the POC /health plugin router.

The router is mountable under any FastAPI app; we don't need QwenPaw
running. Coverage goals: 200 path, content shape, prefix expectations,
and version probe non-fatal fallback when poc.__version__ is absent.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from poc.plugins.health.router import router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/poc")
    return TestClient(app)


def test_health_ok(client: TestClient) -> None:
    r = client.get("/poc/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_health_version_shape(client: TestClient) -> None:
    r = client.get("/poc/health/version")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "poc_version" in body
    # Either a real string or the sentinel — never raises.
    assert isinstance(body["poc_version"], str)


def test_404_on_unrelated_path(client: TestClient) -> None:
    r = client.get("/poc/no-such-thing")
    assert r.status_code == 404


def test_router_only_exposes_get() -> None:
    methods = sorted(
        {m for r in router.routes for m in getattr(r, "methods", set())}
    )
    assert methods == ["GET"]
    # Both routes are GET (no POST/PUT/DELETE).
    assert len([r for r in router.routes if "GET" in getattr(r, "methods", set())]) == 2


def test_json_content_type(client: TestClient) -> None:
    r = client.get("/poc/health")
    assert r.headers["content-type"].startswith("application/json")