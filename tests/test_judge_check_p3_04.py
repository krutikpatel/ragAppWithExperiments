"""P3-04 — the synthetic judge check's construction and arithmetic. No model calls."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from rag.eval.judge import JudgeConfig
from rag.eval.judge_check import (
    EXCLUDE_TOP,
    build_pairs,
    judge_config,
    strip_links,
    summarize,
    verdict_flag,
)

GOLDEN = [
    {"question_id": "q1", "stratum": "single_doc", "question": "Q1", "reference_answer": "A1", "article_ids": ["g1"]},
    {"question_id": "q2", "stratum": "multi_doc", "question": "Q2", "reference_answer": "A2", "article_ids": ["g2", "g3"]},
    {"question_id": "u1", "stratum": "unanswerable", "question": "U", "reference_answer": "", "article_ids": []},
]
CORPUS = [f"d{i:03d}" for i in range(300)] + ["g1", "g2", "g3"]
RANKED = {"q1": ["d000", "g1"] + [f"d{i:03d}" for i in range(1, 99)],
          "q2": ["g2", "d100", "g3", "d101"] + [f"d{i:03d}" for i in range(102, 198)]}


def test_one_pair_per_kind_per_answerable_question_with_matching_article_counts():
    pairs = build_pairs(GOLDEN, CORPUS, RANKED)
    assert Counter(p.kind for p in pairs) == {"supported": 2, "unsupported": 2, "hard_negative": 2}
    by = {(p.question_id, p.kind): p for p in pairs}
    assert by[("q2", "supported")].article_ids == ("g2", "g3")
    assert len(by[("q2", "unsupported")].article_ids) == 2
    assert by[("q2", "hard_negative")].article_ids == ("d100", "d101"), "top-ranked NON-gold, in rank order"
    assert all(p.question_id != "u1" for p in pairs), "unanswerables have no reference answer to check"


def test_unsupported_articles_are_neither_gold_nor_in_the_dense_top_50():
    for p in build_pairs(GOLDEN, CORPUS, RANKED):
        if p.kind == "unsupported":
            banned = set(RANKED[p.question_id][:EXCLUDE_TOP]) | {"g1", "g2", "g3"}
            assert not banned & set(p.article_ids)


def test_pairs_are_seeded():
    assert build_pairs(GOLDEN, CORPUS, RANKED) == build_pairs(GOLDEN, CORPUS, RANKED)
    assert build_pairs(GOLDEN, CORPUS, RANKED, seed=1) != build_pairs(GOLDEN, CORPUS, RANKED)


def test_the_flag_is_p3_05s_strict_definition_and_a_failure_is_not_a_verdict():
    assert verdict_flag(1.0) is False
    assert verdict_flag(0.99) is True
    assert verdict_flag(0.0) is True
    assert verdict_flag(None) is None


def test_confusion_matrix_and_rates():
    def r(kind, score):
        return {"kind": kind, "score": score, "flag": verdict_flag(score)}

    results = ([r("supported", 1.0)] * 7 + [r("supported", 0.5)] * 1 + [r("supported", None)] * 2
               + [r("unsupported", 0.0)] * 9 + [r("unsupported", 1.0)] * 1
               + [r("hard_negative", 0.2)] * 3 + [r("hard_negative", 1.0)] * 1)
    s = summarize(results)
    assert s["confusion"] == {"flagged_unsupported": {"unsupported": 9, "supported": 1},
                              "not_flagged": {"unsupported": 1, "supported": 7}}
    assert s["n_gating_scored"] == 18
    assert s["accuracy"] == round(16 / 18, 4)
    assert s["unsupported_flag_precision"] == 0.9 and s["unsupported_flag_recall"] == 0.9
    assert s["judge_failures"] == 2 and s["judge_failure_by_kind"]["supported"] == 2
    assert s["hard_negative"] == {"n": 4, "flagged_unsupported": 3, "flag_rate": 0.75}
    assert s["auroc"] is not None and 0.5 < s["auroc"] <= 1.0


def test_the_bake_off_judge_is_pinned_to_one_host_without_fallbacks_and_scores_faithfulness_only():
    config = judge_config("deepseek/deepseek-v4.1-flash", "DeepInfra")
    assert config.extra_body["provider"] == {"order": ["DeepInfra"], "allow_fallbacks": False}
    assert config.criteria == ("faithfulness",)
    assert JudgeConfig(model="x/y").criteria != ("faithfulness",), "the default is unchanged"


def test_strip_links_keeps_link_text_and_drops_targets():
    text = "Go to [CMS] (https://www.wix.com/a?x=1&actionUrl=https://b/{{id}}/db/) in your dashboard. See https://x.y/z."
    assert strip_links(text) == "Go to CMS in your dashboard. See "


@pytest.mark.skipif(not Path("data/frozen/dev.parquet").exists(), reason="frozen splits not built")
def test_no_url_survives_in_any_stored_reference_answer():
    """Preflight 49: validate a lexical rule on the FULL stored corpus it runs on.
    norm-v1's link regex left 40 of these 75 URLs in place."""
    from rag.dataset.golden import load_golden

    answers = [r["reference_answer"] for r in load_golden() if r["stratum"] != "unanswerable"]
    whole_url = re.compile(r"https?://\S+")
    any_url_marker = re.compile(r"https?://|www\.")
    assert sum(len(whole_url.findall(a)) for a in answers) == 75
    assert sum(len(any_url_marker.findall(strip_links(a))) for a in answers) == 0


def test_a_nan_score_is_a_failure_not_a_pass():
    """MIS-043: NaN < 1.0 is False, so a NaN read as a verdict means 'fully supported'."""
    nan = float("nan")
    assert verdict_flag(nan) is None
    s = summarize([{"kind": "unsupported", "score": nan, "flag": False},
                   {"kind": "unsupported", "score": 0.0, "flag": True}])
    assert s["unsupported_flag_recall"] == 1.0
    assert s["judge_failures"] == 1 and s["mean_faithfulness"]["unsupported"] == 0.0
