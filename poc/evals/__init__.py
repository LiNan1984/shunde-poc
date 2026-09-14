# -*- coding: utf-8 -*-
"""Excel QA golden set: deterministic workbooks + question pairs + scorer."""

from .qa_set import QA_SET_VERSION, build_qa_fixture, golden_answers
from .score import score_answers

__all__ = ["QA_SET_VERSION", "build_qa_fixture", "golden_answers", "score_answers"]
