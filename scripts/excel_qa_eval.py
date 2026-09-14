# -*- coding: utf-8 -*-
"""Excel QA eval runner: build the golden fixture set and score agent answers.

Usage (from repo root, with the project venv):

    # 1. build fixtures + print the question list for the agent
    .venv/bin/python scripts/excel_qa_eval.py --build

    # 2. agent answers the questions into answers.json, then score:
    .venv/bin/python scripts/excel_qa_eval.py --answers answers.json

    # sanity: golden answers must score 1.0
    .venv/bin/python scripts/excel_qa_eval.py --self-test

The fixture set lives under poc/fixtures/qa_fixtures/ by default; the
manifest (qa_golden.json) carries questions + expected answers so scoring
needs no code, only the JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from poc.evals.qa_set import (  # noqa: E402
    build_qa_fixture,
    build_write_golden,
    golden_answers,
)
from poc.evals.score import score_answers  # noqa: E402

DEFAULT_DIR = REPO_ROOT / "poc" / "fixtures" / "qa_fixtures"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build", action="store_true",
        help="write fixture workbooks + qa_golden.json into --dir",
    )
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument(
        "--answers", type=Path,
        help="score this answers JSON ({question_id: value}) against the manifest",
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="build, then verify golden answers score 1.0",
    )
    args = parser.parse_args(argv)

    if not (args.build or args.answers or args.self_test):
        parser.print_help()
        return 2

    built = build_qa_fixture(args.dir)
    print(f"fixtures -> {built['dir']} ({', '.join(built['files'])})")
    print(f"questions: {len(built['questions'])} (version {built['version']})")
    for q in built["questions"]:
        print(f"  [{q['check']:6}] {q['id']}: {q['question']}")

    if not (args.answers or args.self_test):
        return 0

    if args.self_test:
        # golden read answers + golden write outputs: a perfect run scores 1.0
        answers = golden_answers()
        answers.update(build_write_golden(args.dir / "golden_outputs"))
        report = score_answers(built["questions"], answers)
        source = "golden (self-test)"
    else:
        answers = json.loads(args.answers.read_text(encoding="utf-8"))
        report = score_answers(built["questions"], answers)
        source = str(args.answers)

    print(f"\nscore vs {source}: {report['correct']}/{report['n']}"
          f" = accuracy {report['accuracy']:.2%}")
    for f in report["failed"]:
        print(f"  FAIL {f['id']}: expected={f['expected']!r} got={f['got']!r}")
        print(f"       {f['question']}")
    return 0 if report["accuracy"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
