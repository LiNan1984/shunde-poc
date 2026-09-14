# -*- coding: utf-8 -*-
"""Score agent answers against the Excel QA golden set.

Answers are {"<question_id>": value}. Numeric checks tolerate float noise
and string answers that merely wrap a number ("12,000 元" counts); text
checks are exact after strip. The scorer is deterministic and has no LLM
in the loop, so accuracy numbers are comparable across runs.
"""

from __future__ import annotations

import re
from typing import Any

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


_CHECKERS = {"number": _check_number, "text": _check_text}


def score_answers(
    questions: list[dict[str, Any]],
    answers: dict[str, Any],
) -> dict[str, Any]:
    """Grade ``answers`` against the golden questions.

    Returns {"n", "correct", "accuracy", "failed": [{id, question, expected,
    got}]}. Unanswered questions count as failures with got=None.
    """
    failed: list[dict[str, Any]] = []
    correct = 0
    for q in questions:
        qid = q["id"]
        got = answers.get(qid)
        checker = _CHECKERS.get(q.get("check") or "text", _check_text)
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
