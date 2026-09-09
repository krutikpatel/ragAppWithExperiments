"""P0-08 — slice reporting."""

from __future__ import annotations

import pandas as pd
import pytest

from rag.eval.slices import aggregate_by_slice, build_slices

FRAME = pd.DataFrame(
    [
        {"question_id": "q1", "question": "a b c", "n_gold_docs": 1,
         "article_types": ["article"], "source_config": "expertwritten"},
        {"question_id": "q2", "question": "a b c d e f g h", "n_gold_docs": 2,
         "article_types": ["article", "known_issue"], "source_config": "simulated"},
        {"question_id": "q3", "question": "a b c d e f g h i j k l", "n_gold_docs": 1,
         "article_types": ["feature_request"], "source_config": "simulated"},
    ]
)


def test_every_required_slice_axis_is_present():
    slices = build_slices(FRAME)
    names = slices.names()
    assert "gold_docs:single" in names and "gold_docs:multi" in names
    assert {"article_type:article", "article_type:feature_request", "article_type:known_issue"} <= set(names)
    assert "source:expertwritten" in names and "source:simulated" in names
    assert {"q_len:short", "q_len:medium", "q_len:long"} <= set(names)


def test_slices_overlap_on_article_type():
    """A question with two gold article types belongs to both slices."""
    slices = build_slices(FRAME)
    assert "q2" in slices.members["article_type:article"]
    assert "q2" in slices.members["article_type:known_issue"]
    assert slices.meta["slices_overlap"] is True


def test_tercile_boundaries_are_recorded():
    meta = build_slices(FRAME).meta
    assert len(meta["length_tercile_boundaries"]) == 2
    assert meta["length_unit"] == "whitespace tokens"


def test_gold_doc_slices_partition_the_split():
    slices = build_slices(FRAME)
    single = set(slices.members["gold_docs:single"])
    multi = set(slices.members["gold_docs:multi"])
    assert single | multi == set(FRAME["question_id"])
    assert single & multi == set()


def test_aggregate_carries_n_and_skips_none():
    per_question = {
        "q1": {"strict_recall@5": 1.0, "step_coverage": 0.5},
        "q2": {"strict_recall@5": 0.0, "step_coverage": None},
        "q3": {"strict_recall@5": 1.0, "step_coverage": None},
    }
    report = aggregate_by_slice(per_question, build_slices(FRAME))
    all_slice = report["all"]
    assert all_slice["n_questions"] == 3
    assert all_slice["strict_recall@5"] == pytest.approx(2 / 3)
    # None values are excluded from the mean, not counted as zero, and the count
    # the metric was actually computed over travels with it.
    assert all_slice["step_coverage"] == pytest.approx(0.5)
    assert all_slice["step_coverage__n"] == 1


def test_empty_slices_are_omitted():
    frame = FRAME[FRAME["source_config"] == "simulated"]
    report = aggregate_by_slice({"q2": {"m": 1.0}, "q3": {"m": 0.0}}, build_slices(frame))
    assert "source:expertwritten" not in report
