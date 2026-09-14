# -*- coding: utf-8 -*-
"""Offline unit tests for scripts/kb_eval.py (verdict logic + offline main flow).

No network: POC_LOAD_SECRETS=0 and every endpoint var is removed, so the KB
runs on hash vectors and local stores only.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
KB_EVAL = REPO_ROOT / "scripts" / "kb_eval.py"


def _load_kb_eval():
    spec = importlib.util.spec_from_file_location("kb_eval", KB_EVAL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kb_eval = _load_kb_eval()


@pytest.fixture()
def offline_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("POC_LOAD_SECRETS", "0")
    for key in kb_eval._OFFLINE_POP:
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_force_offline_pops_endpoints_and_disables_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POC_EMBEDDING_URL", "http://example.invalid/embeddings")
    monkeypatch.setenv("POC_CHAT_MODEL", "some-model")
    monkeypatch.setenv("ARK_API_KEY", "sk-test")
    monkeypatch.setenv("POC_LOAD_SECRETS", "1")
    popped = kb_eval.force_offline()
    assert "POC_EMBEDDING_URL" in popped
    assert "ARK_API_KEY" in popped
    assert os.environ.get("POC_EMBEDDING_URL") is None
    assert os.environ.get("POC_CHAT_MODEL") is None
    assert os.environ.get("ARK_API_KEY") is None
    assert os.environ.get("POC_LOAD_SECRETS") == "0"


def test_judge_hit_matches_text_image_table_and_page() -> None:
    hits = [
        {
            "kind": "text",
            "page": 1,
            "text": "本行对公信贷逾期90天认定标准适用于所有对公贷款产品",
            "image_description": "",
            "table": None,
        },
        {
            "kind": "image",
            "page": 1,
            "text": "embedded image 400x200",
            "image_description": "embedded image 400x200: RATECHART",
            "table": None,
        },
        {
            "kind": "table",
            "page": 2,
            "text": "",
            "image_description": "",
            "table": {"csv": "产品,利率\n经营贷款,4.20\n", "html": "<table>", "json": "[]"},
        },
    ]
    hit, where = kb_eval.judge_hit(["逾期90天"], None, hits, 8)
    assert hit and where.startswith("text")
    hit, where = kb_eval.judge_hit(["RATECHART"], None, hits, 8)
    assert hit and where.startswith("image")
    hit, where = kb_eval.judge_hit(["经营贷款", "4.20"], None, hits, 8)
    assert hit and where.startswith("table")
    # A partial keyword set must not count as a hit.
    hit, where = kb_eval.judge_hit(["经营贷款", "4.25"], None, hits, 8)
    assert not hit and where == "miss"
    # The expected_page fallback credits a page-level hit without keywords.
    hit, where = kb_eval.judge_hit(["绝不存在的词"], 2, hits, 8)
    assert hit and where == "page2"


def test_judge_hit_respects_topk_boundary() -> None:
    top = {"kind": "text", "page": 1, "text": "无关内容", "image_description": "", "table": None}
    below = {
        "kind": "text",
        "page": 9,
        "text": "经营贷款利率4.20",
        "image_description": "",
        "table": None,
    }
    hit, _ = kb_eval.judge_hit(["经营贷款"], None, [top, below], 1)
    assert not hit
    hit, where = kb_eval.judge_hit(["经营贷款"], None, [top, below], 2)
    assert hit and where.startswith("text")


def test_run_eval_offline_end_to_end(offline_env: Path) -> None:
    golden = [
        {
            "question": "对公信贷逾期90天的认定标准适用于哪些产品？",
            "doc_id": "credit-policy",
            "modality": "text",
            "expected_keywords": ["逾期90天", "对公贷款"],
            "expected_page": 1,
            "note": "",
        },
        {
            "question": "BranchA 网点四季度贷款余额是多少亿元？",
            "doc_id": "branch-balance",
            "modality": "image",
            "expected_keywords": ["1.23"],
            "expected_page": 1,
            "note": "",
        },
    ]
    report = kb_eval.run_eval(golden, offline_env / "ws", k=8, live=False)
    assert report["ingest"]["credit-policy"]["ok"] is True
    assert report["ingest"]["branch-balance"]["ok"] is True
    assert report["ingest"]["branch-balance"]["n_chunks"] > 0

    groups = report["groups"]
    assert groups["text"]["n"] == 1 and groups["text"]["hits"] == 1
    # 1.23 only exists as a bar height: offline retrieval must miss it on
    # keywords even though the expected_page fallback credits the hit.
    assert groups["image"]["n"] == 1
    assert groups["image"]["hits"] == 1
    assert groups["image"]["keyword_hits"] == 0
    assert report["items"][0]["answer_hit"] is True
    assert report["items"][0]["hit"] is True
    assert report["items"][1]["where"] == "page1"


def test_cli_offline_run_passes_gate_and_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = dict(os.environ)
    env["POC_LOAD_SECRETS"] = "0"
    for key in kb_eval._OFFLINE_POP:
        env.pop(key, None)
    proc = subprocess.run(
        [sys.executable, str(KB_EVAL), "--keep-workspace"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "gated" in proc.stdout and "PASS" in proc.stdout
    kept = next(
        line.split(":", 1)[1].strip()
        for line in proc.stdout.splitlines()
        if line.startswith("workspace kept:")
    )
    workspace = Path(kept)
    try:
        report_path = workspace / "kb_eval_report.json"
        assert report_path.is_file()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["gate"]["pass"] is True
        assert report["config"]["live"] is False
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
