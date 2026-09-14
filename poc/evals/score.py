# -*- coding: utf-8 -*-
"""Score agent answers against the Excel QA golden set.

Answers are {"<question_id>": value}. Numeric checks tolerate float noise
and string answers that merely wrap a number ("12,000 元" counts); text
checks are exact after strip; write checks take the path of the file the
agent produced and verify its content deterministically. The scorer has no
LLM in the loop, so accuracy numbers are comparable across runs.
"""

from __future__ import annotations

import re
from typing import Any

from .qa_set import WRITE_VERIFIERS

_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _NUM_RE.search(value.replace("¥", "").replace("￥", ""))
        if match:
            try:
                return float(match.group(0).replace(",", ""))
            except ValueError:
                return None
    return None


def _check_number(expected: Any, got: Any) -> bool:
    exp_num = _coerce_number(expected)
    got_num = _coerce_number(got)
    if exp_num is None or got_num is None:
        return False
    return abs(got_num - exp_num) <= max(0.01, abs(exp_num) * 1e-6)


def _check_text(expected: Any, got: Any) -> bool:
    return str(got).strip() == str(expected).strip()


def _check_write(q: dict[str, Any], got: Any) -> tuple[bool, str]:
    """Run the question's registered verifier against the produced file path."""
    verifier = WRITE_VERIFIERS.get(q["id"])
    if verifier is None:
        return False, "no verifier registered"
    if not isinstance(got, str) or not got.strip():
        return False, "answer is not a file path"
    try:
        return verifier(got)
    except Exception as exc:  # noqa: BLE001 — verifier crashes are failures
        return False, f"verifier error: {type(exc).__name__}: {exc}"


_CHECKERS = {"number": _check_number, "text": _check_text}


def score_answers(
    questions: list[dict[str, Any]],
    answers: dict[str, Any],
) -> dict[str, Any]:
    """Grade ``answers`` against the golden questions.

    Returns {"n", "correct", "accuracy", "failed": [{id, question, expected,
    got}]}. Unanswered questions count as failures with got=None. For write
    questions the answer is the output file path; ``got`` in a failed entry
    carries the verifier detail (or None when unanswered).
    """
    failed: list[dict[str, Any]] = []
    correct = 0
    for q in questions:
        qid = q["id"]
        got = answers.get(qid)
        check = q.get("check") or "text"
        if check == "write":
            ok, detail = _check_write(q, got)
            if ok:
                correct += 1
            else:
                failed.append(
                    {
                        "id": qid,
                        "question": q["question"],
                        "expected": q["expected"],
                        "got": detail if got is not None else None,
                    }
                )
            continue
        checker = _CHECKERS.get(check, _check_text)
        if got is not None and checker(q["expected"], got):
            correct += 1
        else:
            failed.append(
                {
                    "id": qid,
                    "question": q["question"],
                    "expected": q["expected"],
                    "got": got,
                }
            )
    n = len(questions)
    return {
        "n": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "failed": failed,
    }
