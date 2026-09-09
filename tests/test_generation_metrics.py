"""P0-07 — the generation metrics that need no LLM call."""

from __future__ import annotations

import pytest

from rag.eval.generation_metrics import citation_scores, deterministic_metrics, is_refusal, refusal_summary
from rag.eval.steps import extract_steps, step_coverage
from rag.generation.base import extract_citations

REFERENCE = """To add a member area:
1. Go to your site dashboard.
2. Click Add Apps in the left menu.
3. Search for Members Area and click Add.
4. Publish your site.
"""


def test_citation_precision_and_recall():
    scores = citation_scores(["dA", "dB"], ["dA", "dC"])
    assert scores.precision == pytest.approx(0.5)
    assert scores.recall == pytest.approx(0.5)


def test_citing_nothing_gives_no_precision_rather_than_zero():
    """Declining to cite is not the same as citing wrongly."""
    scores = citation_scores([], ["dA"])
    assert scores.precision is None
    assert scores.recall == 0.0
    assert scores.cited_nothing is True


def test_duplicate_citations_do_not_inflate_the_denominator():
    assert citation_scores(["dA", "dA"], ["dA"]).precision == pytest.approx(1.0)


def test_citations_are_extracted_in_first_mention_order():
    assert extract_citations("x [doc:aabbccdd] y [doc:11223344] z [doc:aabbccdd]") == [
        "aabbccdd",
        "11223344",
    ]


def test_step_extraction_reads_numbered_lists_only():
    steps = extract_steps(REFERENCE)
    assert len(steps) == 4
    assert steps[0].startswith("Go to your site dashboard")
    # Bullets are unordered facts in this corpus, not steps.
    assert extract_steps("- first thing\n- second thing") == []


def test_step_coverage_counts_present_steps():
    generated = """1. Go to your site dashboard.
2. Click Add Apps in the left menu.
3. Publish your site.
"""
    result = step_coverage(REFERENCE, generated)
    assert result.applicable is True
    assert result.n_reference_steps == 4
    assert result.coverage == pytest.approx(0.75)
    assert result.order_preserved is True


def test_step_coverage_detects_reordering():
    reordered = """1. Publish your site.
2. Go to your site dashboard.
3. Click Add Apps in the left menu.
4. Search for Members Area and click Add.
"""
    result = step_coverage(REFERENCE, reordered)
    assert result.coverage == pytest.approx(1.0)
    assert result.order_preserved is False


def test_step_coverage_is_none_for_prose_answers():
    """Most WixQA answers are prose. Scoring them zero would poison the mean."""
    result = step_coverage("Payouts are held when verification is incomplete.", "Anything.")
    assert result.applicable is False
    assert result.coverage is None and result.order_preserved is None


def test_refusal_detection():
    assert is_refusal("The provided context does not contain this information.")
    assert is_refusal("I don't have enough information to answer that.")
    assert is_refusal("Could you clarify which site you mean?")
    assert not is_refusal("Go to Settings and click Save.")


def test_refusal_and_false_refusal_are_separate_metrics():
    unanswerable = deterministic_metrics(
        generated_answer="The articles do not cover this.",
        reference_answer="",
        cited_doc_ids=[],
        gold_doc_ids=[],
    )
    assert unanswerable["correct_refusal"] == 1.0
    assert unanswerable["false_refusal"] is None

    answerable = deterministic_metrics(
        generated_answer="The articles do not cover this.",
        reference_answer=REFERENCE,
        cited_doc_ids=[],
        gold_doc_ids=["dA"],
    )
    assert answerable["false_refusal"] == 1.0
    assert answerable["correct_refusal"] is None


def test_refusal_summary_reports_both_rates_with_counts():
    per_question = {
        "u1": {"correct_refusal": 1.0, "false_refusal": None},
        "u2": {"correct_refusal": 0.0, "false_refusal": None},
        "a1": {"correct_refusal": None, "false_refusal": 0.0},
    }
    summary = refusal_summary(per_question)
    assert summary["refusal_rate"] == pytest.approx(0.5)
    assert summary["refusal_rate_n"] == 2
    assert summary["false_refusal_rate"] == 0.0
    assert summary["false_refusal_rate_n"] == 1
    assert summary["refusal_detector"]
