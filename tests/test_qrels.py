"""P0-05 — document-level qrels in the format ranx / pytrec_eval accept."""

from __future__ import annotations

import pandas as pd

from rag.eval.qrels import check_run_against_qrels, qrels_from_split, run_from_results
from rag.retrieval.base import RetrievalResult, ScoredChunk

SPLIT = pd.DataFrame(
    [
        {"question_id": "q1", "gold_doc_ids": ["doc_A"]},
        {"question_id": "q2", "gold_doc_ids": ["doc_A", "doc_B"]},
        {"question_id": "q3", "gold_doc_ids": []},
    ]
)


def test_qrels_are_binary_and_document_level():
    qrels = qrels_from_split(SPLIT)
    assert qrels == {"q1": {"doc_A": 1}, "q2": {"doc_A": 1, "doc_B": 1}}
    assert all(v == 1 for judgments in qrels.values() for v in judgments.values())


def test_questions_without_gold_docs_are_excluded():
    assert "q3" not in qrels_from_split(SPLIT)


def test_run_is_built_from_pooled_documents():
    result = RetrievalResult(
        question_id="q1",
        chunks=[ScoredChunk("c1", "doc_A", 0.9)],
        docs=[("doc_A", 0.9), ("doc_B", 0.4)],
    )
    assert run_from_results([result]) == {"q1": {"doc_A": 0.9, "doc_B": 0.4}}


def test_alignment_check_reports_both_directions():
    qrels = qrels_from_split(SPLIT)
    run = {"q1": {"doc_A": 0.9}, "q9": {"doc_C": 0.1}}
    report = check_run_against_qrels(run, qrels)
    assert report["missing_from_run"] == ["q2"]
    assert report["unjudged_in_run"] == ["q9"]
    assert report["aligned"] is False
