"""P0-06 — retrieval metrics."""

from __future__ import annotations

import pytest
from ranx import Qrels, Run, evaluate

from rag.eval.retrieval_metrics import evaluate_retrieval, mrr_single_gold, refuse_full_set_mrr

QRELS = {"q1": {"dA": 1, "dB": 1}, "q2": {"dC": 1}, "q3": {"dD": 1}}
RUN = {
    "q1": {"dA": 1.0, "dX": 0.9, "dB": 0.8},   # both gold, within top 3
    "q2": {"dC": 1.0},                          # gold at rank 1
    "q3": {"dZ": 1.0, "dY": 0.9},               # gold not retrieved
}


def test_ranx_per_query_order_is_the_qrels_key_order():
    """Pins the assumption per-question attribution depends on.

    `ranx` sorts query ids internally, so per-query arrays are not in input order.
    If a future version changes this, every per-question metric would be attached
    to the wrong question — silently. This test is the tripwire.
    """
    qrels = Qrels({"zq": {"d1": 1}, "aq": {"d3": 1}})
    run = Run({"zq": {"d1": 0.9}, "aq": {"d9": 0.7}})
    scores = evaluate(qrels, run, "recall@5", return_mean=False)
    assert list(qrels.qrels.keys()) == ["aq", "zq"]
    assert list(scores) == [0.0, 1.0], "per-query order no longer matches qrels key order"


def test_strict_recall_requires_all_gold_documents():
    metrics = evaluate_retrieval(QRELS, RUN, k_values=(1, 3))
    # q1 needs dA and dB: dA alone at k=1 is not enough.
    assert metrics.per_question["q1"]["strict_recall@1"] == 0.0
    assert metrics.per_question["q1"]["strict_recall@3"] == 1.0
    assert metrics.aggregate["strict_recall@3"] == pytest.approx(2 / 3)


def test_loose_recall_needs_only_one():
    metrics = evaluate_retrieval(QRELS, RUN, k_values=(1,))
    assert metrics.per_question["q1"]["loose_recall@1"] == 1.0
    assert metrics.aggregate["loose_recall@1"] == pytest.approx(2 / 3)


def test_strict_is_never_above_loose():
    metrics = evaluate_retrieval(QRELS, RUN, k_values=(1, 3, 5))
    for k in (1, 3, 5):
        assert metrics.aggregate[f"strict_recall@{k}"] <= metrics.aggregate[f"loose_recall@{k}"]


def test_strict_recall_at_1_is_impossible_for_multi_gold_questions():
    """Not a bug: two documents cannot both be in a top-1 list."""
    metrics = evaluate_retrieval({"q1": {"dA": 1, "dB": 1}}, {"q1": {"dA": 1.0, "dB": 0.9}}, k_values=(1, 2))
    assert metrics.aggregate["strict_recall@1"] == 0.0
    assert metrics.aggregate["strict_recall@2"] == 1.0


def test_mrr_is_restricted_to_single_gold_questions():
    value, per_question, n = mrr_single_gold(QRELS, RUN)
    assert n == 2 and set(per_question) == {"q2", "q3"}
    assert value == pytest.approx((1.0 + 0.0) / 2)


def test_full_set_mrr_is_refused():
    with pytest.raises(ValueError, match="not meaningful"):
        refuse_full_set_mrr(QRELS)
    refuse_full_set_mrr({"q2": {"dC": 1}})  # single-gold only: allowed


def test_mrr_subset_size_is_reported():
    metrics = evaluate_retrieval(QRELS, RUN)
    assert metrics.aggregate["mrr_single_gold_n"] == 2.0


def test_missing_question_is_an_error_not_a_zero():
    with pytest.raises(ValueError, match="absent from the run"):
        evaluate_retrieval(QRELS, {"q1": RUN["q1"]})


def test_empty_qrels_rejected():
    with pytest.raises(ValueError, match="nothing to score"):
        evaluate_retrieval({}, {})
