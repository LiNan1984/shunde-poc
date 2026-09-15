#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Golden-QA evaluation for the multimodal knowledge base (offline by default).

    python scripts/kb_eval.py [--live] [--k 8] [--min-hit-rate 0.8] [--keep-workspace]

Steps: force-offline env (unless --live) -> temp POC_WORKSPACE -> regenerate the
deterministic KB fixture PDFs -> ingest_pdf -> per golden item search_knowledge
+ answer_knowledge -> grouped hit@k report (JSON at POC_WORKSPACE/kb_eval_report.json).

The text+table groups are gated by --min-hit-rate (exit 1 below it). The image
group is reported as the known gap: offline retrieval cannot read pixels, only
--live can answer those via the analyze_page vision tool (skipped with a note
when analyze_page is not importable yet).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
GOLDEN_PATH = REPO_ROOT / "poc" / "fixtures" / "kb_golden_qa.json"

# Dropped in offline mode so embeddings / chat / rerank / vision can never touch
# the network, even when ~/.qwenpaw.secret leaked vars into the environment.
# embed.py also honors the QWEN_* aliases for the same endpoints, so they go too.
_OFFLINE_POP = (
    "POC_EMBEDDING_URL",
    "POC_IMAGE_EMBEDDING_URL",
    "POC_RERANKER_URL",
    "POC_CHAT_URL",
    "POC_CHAT_MODEL",
    "POC_VISION_MODEL",
    "ARK_API_KEY",
    "ARK_BASE_URL",
    "QWEN_EMBEDDING_URL",
    "QWEN3_EMBEDDING_URL",
)

# Only these modalities gate the exit code; image is the measured gap.
GATED_MODALITIES = ("text", "table")

GROUP_ORDER = ("text", "table", "image")


def force_offline() -> list[str]:
    """Set POC_LOAD_SECRETS=0 and pop network-capable endpoint vars.

    Must run BEFORE importing poc.kb_mcp. Returns the popped key names.
    """
    os.environ["POC_LOAD_SECRETS"] = "0"
    popped = []
    for key in _OFFLINE_POP:
        if key in os.environ:
            del os.environ[key]
            popped.append(key)
    return popped


def hit_texts(hit: dict[str, Any]) -> list[str]:
    """All searchable strings of one retrieval hit (text / image / table)."""
    texts = [str(hit.get("text") or ""), str(hit.get("image_description") or "")]
    table = hit.get("table")
    if isinstance(table, dict):
        texts.append(str(table.get("csv") or ""))
    return texts


def judge_hit(
    keywords: list[str],
    expected_page: int | None,
    hits: list[dict[str, Any]],
    k: int,
) -> tuple[bool, str]:
    """Golden-item verdict against the top-k hits.

    Hit when any top-k chunk's text / image_description / table_csv contains
    ALL keywords, or when the expected page appears in the top-k at all.
    Returns (hit, where) with a short human-readable ``where``.
    """
    top = hits[: max(1, k)]
    for hit in top:
        joined = " ".join(hit_texts(hit))
        if keywords and all(kw in joined for kw in keywords):
            return True, f"{hit.get('kind')}:p{hit.get('page')}"
    if expected_page:
        for hit in top:
            if int(hit.get("page") or 0) == int(expected_page):
                return True, f"page{expected_page}"
    return False, "miss"


def load_analyze_page() -> Callable[..., Any] | None:
    """Best-effort import of the parallel-track analyze_page vision tool.

    None means the tool is not importable yet — callers skip vision items
    with a note instead of fabricating a vision answer.
    """
    for module_name in ("poc.kb_mcp.vision", "poc.kb_mcp.server"):
        try:
            module = __import__(module_name, fromlist=["analyze_page"])
        except Exception:  # noqa: BLE001 — module may not exist on this branch
            continue
        fn = getattr(module, "analyze_page", None)
        if callable(fn):
            return fn
    return None


def _build_fixture_pdfs(golden: list[dict[str, Any]], workspace: Path) -> dict[str, Path]:
    from poc.fixtures.generate_fixtures import write_kb_pdf

    dest = workspace / "fixtures"
    dest.mkdir(parents=True, exist_ok=True)
    doc_ids = sorted({str(item["doc_id"]) for item in golden})
    return {doc_id: write_kb_pdf(doc_id, dest) for doc_id in doc_ids}


def run_eval(
    golden: list[dict[str, Any]],
    workspace: Path | str,
    *,
    k: int = 8,
    live: bool = False,
) -> dict[str, Any]:
    """Ingest the fixture PDFs and judge every golden item. Returns the report."""
    workspace = Path(workspace)
    # POC_WORKSPACE must be set before the sandbox helpers are used.
    os.environ["POC_WORKSPACE"] = str(workspace)
    from poc.kb_mcp.ingest import ingest_pdf
    from poc.kb_mcp.retrieve import answer_knowledge, search_knowledge

    fixtures = _build_fixture_pdfs(golden, workspace)

    ingest_report: dict[str, dict[str, Any]] = {}
    for doc_id, pdf_path in fixtures.items():
        result = ingest_pdf(str(pdf_path), doc_id=doc_id)
        ingest_report[doc_id] = {
            "ok": bool(result.get("ok")),
            "n_chunks": int(result.get("n_chunks") or 0),
            "message": str(result.get("message") or ""),
        }
        if not result.get("ok"):
            print(f"[warn] ingest failed for {doc_id}: {result.get('message')}", file=sys.stderr)

    analyze_page = load_analyze_page() if live else None

    items: list[dict[str, Any]] = []
    for index, entry in enumerate(golden):
        modality = str(entry.get("modality") or "text")
        keywords = [str(kw) for kw in (entry.get("expected_keywords") or [])]
        expected_page = entry.get("expected_page") or None
        question = str(entry["question"])
        doc_id = str(entry["doc_id"])
        record: dict[str, Any] = {
            "index": index,
            "question": question,
            "doc_id": doc_id,
            "modality": modality,
            "keywords": keywords,
        }
        if not ingest_report.get(doc_id, {}).get("ok"):
            record.update({"hit": False, "where": "ingest_failed", "answer_hit": False})
            items.append(record)
            continue

        search = search_knowledge(question, doc_id=doc_id, k=k)
        hits = list(search.get("hits") or []) if search.get("ok") else []
        hit, where = judge_hit(keywords, expected_page, hits, k)
        # "hit" includes the expected_page fallback; keyword_hit counts only
        # keyword matches inside chunk text — the honest offline-gap metric for
        # image items (page fallback is trivially true on 1-page docs).
        keyword_hit = hit and not where.startswith("page")
        answer_result = answer_knowledge(question, doc_id=doc_id, k=k)
        answer = str(answer_result.get("answer") or "")
        record.update(
            {
                "hit": hit,
                "where": where,
                "keyword_hit": keyword_hit,
                "answer_hit": bool(answer) and all(kw in answer for kw in keywords),
            }
        )
        if modality == "image":
            if not live:
                record["vision"] = "offline"
            elif analyze_page is None:
                record["vision"] = "skipped (analyze_page 不可用)"
            else:
                try:
                    vision = analyze_page(
                        doc_id=doc_id,
                        path=str(fixtures[doc_id]),
                        page=int(expected_page or 1),
                        query=question,
                    )
                    text = (
                        str(vision.get("answer") or vision.get("text") or "")
                        if isinstance(vision, dict)
                        else str(vision)
                    )
                    record["vision"] = (
                        "hit" if text and all(kw in text for kw in keywords) else "miss"
                    )
                except Exception as exc:  # noqa: BLE001 — tool signature may still move
                    record["vision"] = f"skipped ({type(exc).__name__}: {exc})"
        items.append(record)

    groups: dict[str, dict[str, Any]] = {}
    for modality in GROUP_ORDER:
        rows = [i for i in items if i["modality"] == modality]
        hits = sum(1 for i in rows if i["hit"])
        groups[modality] = {
            "n": len(rows),
            "hits": hits,
            "hit_at_k": round(hits / len(rows), 4) if rows else None,
            "keyword_hits": sum(1 for i in rows if i.get("keyword_hit")),
            "answer_hits": sum(1 for i in rows if i.get("answer_hit")),
        }
    gated_rows = [i for i in items if i["modality"] in GATED_MODALITIES]
    gated_hits = sum(1 for i in gated_rows if i["hit"])
    gated_rate = (gated_hits / len(gated_rows)) if gated_rows else 1.0
    gate = {
        "modalities": list(GATED_MODALITIES),
        "n": len(gated_rows),
        "hits": gated_hits,
        "hit_rate": round(gated_rate, 4),
        "pass": gated_rate >= 0.8,  # replaced by caller's threshold below
    }
    return {"ingest": ingest_report, "items": items, "groups": groups, "gate": gate}


def finalize_gate(report: dict[str, Any], min_hit_rate: float) -> dict[str, Any]:
    """Apply the CLI threshold to the text+table gate (min_hit_rate stored)."""
    gate = report["gate"]
    gate["min_hit_rate"] = min_hit_rate
    gate["pass"] = float(gate["hit_rate"]) >= min_hit_rate
    return gate


def _print_report(report: dict[str, Any], report_path: Path) -> None:
    print(f"KB golden QA eval — report: {report_path}")
    print(f"{'modality':<10}{'题数':>6}{'hit':>6}{'hit@k':>8}{'kw命中':>8}{'answer':>8}  备注")
    notes = {
        "image": "离线无法看图（kw命中仅靠 OCR 描述），仅 --live 可通过 analyze_page 作答",
    }
    for modality in GROUP_ORDER:
        group = report["groups"][modality]
        if group["n"] == 0:
            continue
        rate = "-" if group["hit_at_k"] is None else f"{group['hit_at_k']:.2f}"
        print(
            f"{modality:<10}{group['n']:>6}{group['hits']:>6}{rate:>8}"
            f"{group['keyword_hits']:>8}{group['answer_hits']:>8}  {notes.get(modality, '')}"
        )
    for item in report["items"]:
        if not item["hit"]:
            print(
                f"  MISS [{item['modality']}] {item['doc_id']}: {item['question']} "
                f"(keywords={item['keywords']}, where={item.get('vision', item['where'])})"
            )
    gate = report["gate"]
    verdict = "PASS" if gate["pass"] else "FAIL"
    print(
        f"gated ({'+'.join(gate['modalities'])}) hit_rate="
        f"{gate['hit_rate']:.2f} >= {gate['min_hit_rate']:.2f} -> {verdict}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Golden-QA evaluation for the multimodal knowledge base."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="load ~/.qwenpaw.secret endpoints and try analyze_page on image items",
    )
    parser.add_argument("--k", type=int, default=8, help="top-k hits judged per item")
    parser.add_argument(
        "--min-hit-rate",
        type=float,
        default=0.8,
        help="minimum hit rate for the text+table groups (exit 1 below it)",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="keep the temp POC_WORKSPACE (and the JSON report) and print its path",
    )
    args = parser.parse_args(argv)

    if not args.live:
        force_offline()

    import poc.kb_mcp  # noqa: F401  (after env hardening)

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    workspace = Path(tempfile.mkdtemp(prefix="kb-eval-"))
    report = run_eval(golden, workspace, k=args.k, live=args.live)
    report["config"] = {
        "live": args.live,
        "k": args.k,
        "min_hit_rate": args.min_hit_rate,
        "golden": str(GOLDEN_PATH),
        "workspace": str(workspace),
    }
    finalize_gate(report, args.min_hit_rate)

    report_path = workspace / "kb_eval_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _print_report(report, report_path)

    if args.keep_workspace:
        print(f"workspace kept: {workspace}")
    else:
        shutil.rmtree(workspace, ignore_errors=True)
    return 0 if report["gate"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
