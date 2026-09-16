"""P2-01 — paired significance testing over per-question outcomes; P2-02 — MDD
family matching. Zero LLM calls, runs in seconds."""

from __future__ import annotations

import json
import time

import pytest

from rag.eval.noise_floor import (
    FLOOR_FAMILIES,
    JUDGED_MATCH_KEYS,
    family_for_run,
    format_judged,
    mdd_verdict,
    retrieval_family_for_run,
)
from rag.runner.compare import compare_runs, format_compare, mcnemar_exact_p
from rag.runner.store import ResultsStore


def _row(run_id: str, **overrides) -> dict:
    row = {
        "run_id": run_id,
        "timestamp": f"2026-09-15T00:00:00+00:00",
        "name": run_id,
        "config_hash": "hash",
        "config_json": "{}",
        "corpus_hash": "sha256:corpus",
        "normalization_version": "norm-v1",
        "hf_revision": "abc",
        "dataset_config": "dev",
        "split": "dev",
        "split_hash": "sha256:split",
        "git_sha": "deadbeef",
        "git_dirty": 0,
        "eval_tier": "tier1",
        "doc_pooling": "max",
        "harness_smoke_test": 0,
        "retriever": "bm25",
    }
    row.update(overrides)
    return row


def _question(run_id: str, qid: str, metrics: dict) -> dict:
    return {
        "run_id": run_id,
        "question_id": qid,
        "retrieved_doc_ids": json.dumps(["d1"]),
        "retrieved_chunk_ids": json.dumps([]),
        "context_chunk_ids": json.dumps([]),
        "scores": json.dumps([]),
        "gold_doc_ids": json.dumps(["d1"]),
        "metrics_json": json.dumps(metrics),
        "generated_answer": None,
        "cited_doc_ids": json.dumps([]),
        "latency_ms": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": None,
    }


@pytest.fixture()
def store(tmp_path):
    """40 questions: B fixes 10 of A's misses and breaks 2 of A's hits (binary), and
    a graded metric that moves by +0.1 on half of them."""
    with ResultsStore(tmp_path / "runs.sqlite") as store:
        store.start_run(_row("run_a"))
        store.start_run(_row("run_b"))
        rows_a, rows_b = [], []
        for i in range(40):
            qid = f"q{i:02d}"
            a_hit = i < 20
            if i < 2:
                b_hit = False       # A-only
            elif 20 <= i < 30:
                b_hit = True        # B-only
            else:
                b_hit = a_hit       # concordant
            graded_a = 0.5
            graded_b = 0.6 if i % 2 else 0.5
            # one question where the metric is not applicable on one side
            m_a = {"hit": float(a_hit), "graded": graded_a, "partial": 1.0 if i else None}
            m_b = {"hit": float(b_hit), "graded": graded_b, "partial": 1.0}
            rows_a.append(_question("run_a", qid, m_a))
            rows_b.append(_question("run_b", qid, m_b))
        store.add_questions(rows_a)
        store.add_questions(rows_b)
        store.finish_run("run_a", status="VALID", metrics={"hit": 0.5}, n_questions=40)
        store.finish_run("run_b", status="VALID", metrics={"hit": 0.70}, n_questions=40)
        yield store


SLICES = {
    "all": [f"q{i:02d}" for i in range(40)],
    "gold_docs:single": [f"q{i:02d}" for i in range(30)],
    "gold_docs:multi": [f"q{i:02d}" for i in range(30, 40)],
}


def test_contingency_delta_ci_and_p_for_a_binary_metric(store):
    report = compare_runs("run_a", "run_b", metric="hit", store=store, slices=SLICES, resamples=4000)
    overall = report["overall"]
    assert report["binary"] is True
    assert overall["contingency"] == {"both_correct": 18, "both_wrong": 10, "a_only": 2, "b_only": 10}
    assert overall["mean_a"] == 0.5 and overall["mean_b"] == 0.70 and overall["delta"] == 0.20
    lo, hi = overall["ci95"]
    assert lo < 0.20 < hi and lo > 0, "CI is on the difference, and excludes zero here"
    assert overall["p_value"] < 0.05 and overall["significant_at_0_05"]
    assert overall["mcnemar_exact_p"] == round(mcnemar_exact_p(2, 10), 4) < 0.05


def test_graded_metric_reports_direction_counts_not_a_2x2(store):
    report = compare_runs("run_a", "run_b", metric="graded", store=store, slices=SLICES, resamples=4000)
    assert report["binary"] is False
    assert report["overall"]["contingency"] == {"b_higher": 20, "a_higher": 0, "tied": 20}
    assert report["overall"]["delta"] == 0.05
    assert report["overall"]["p_value"] < 0.01


def test_per_slice_tests_and_not_applicable_exclusion(store):
    report = compare_runs("run_a", "run_b", metric="hit", store=store, slices=SLICES, resamples=2000)
    assert set(report["slices"]) == {"gold_docs:single", "gold_docs:multi"}
    multi = report["slices"]["gold_docs:multi"]
    assert multi["n"] == 10 and multi["delta"] == 0.0 and multi["p_value"] == 1.0
    assert multi["ci95"] == [0.0, 0.0]

    partial = compare_runs("run_a", "run_b", metric="partial", store=store, slices=SLICES, resamples=500)
    assert partial["n_paired"] == 39 and partial["n_excluded_not_applicable"] == 1


def test_resampling_is_seeded_and_reproducible(store):
    one = compare_runs("run_a", "run_b", metric="hit", store=store, slices=SLICES, seed=3, resamples=3000)
    two = compare_runs("run_a", "run_b", metric="hit", store=store, slices=SLICES, seed=3, resamples=3000)
    assert one["overall"] == two["overall"] and one["slices"] == two["slices"]
    assert one["seed"] == 3 and one["resamples"] == 3000
    other = compare_runs("run_a", "run_b", metric="hit", store=store, slices=SLICES, seed=4, resamples=3000)
    assert other["overall"]["delta"] == one["overall"]["delta"]  # the estimate never depends on the seed


def test_runs_in_seconds_at_dev_large_scale():
    """P2-01: must run in seconds. 6,221 questions, 10,000 resamples."""
    import numpy as np

    from rag.runner.compare import _paired_test

    rng = np.random.default_rng(0)
    a = (rng.random(6221) < 0.4).astype(float)
    b = np.where(rng.random(6221) < 0.1, 1 - a, a)
    started = time.perf_counter()
    result = _paired_test(a, b, binary=True, rng=np.random.default_rng(1), resamples=10_000)
    assert time.perf_counter() - started < 20
    assert result["n"] == 6221 and "contingency" in result


def test_compare_flags_uncached_pipeline_llm_runs(store):
    """P2-03 ↔ P2-01: a run whose pipeline called an LLM without full cache backing
    is not a fixed outcome, and the test says so."""
    store.update_run("run_b", pipeline_nondeterministic=1,
                     pipeline_llm_json=json.dumps({"hit_rate": 0.4, "calls": 40}))
    report = compare_runs("run_a", "run_b", metric="hit", store=store, slices=SLICES, resamples=200)
    assert len(report["warnings"]) == 1 and "40%" in report["warnings"][0]
    store.update_run("run_b", pipeline_llm_json=json.dumps({"hit_rate": 1.0, "calls": 40}))
    assert compare_runs("run_a", "run_b", metric="hit", store=store, slices=SLICES, resamples=200)["warnings"] == []


def test_format_is_readable(store):
    report = compare_runs("run_a", "run_b", metric="hit", store=store, slices=SLICES, resamples=500)
    text = format_compare(report)
    assert "overall" in text and "A-only 2  B-only 10" in text and "gold_docs:multi" in text


def test_mcnemar_exact_values():
    assert mcnemar_exact_p(0, 0) == 1.0
    assert mcnemar_exact_p(5, 5) == 1.0
    assert abs(mcnemar_exact_p(0, 10) - 2 / 1024) < 1e-12
    assert mcnemar_exact_p(1, 6) == mcnemar_exact_p(6, 1)


# --- P2-02: judged deltas carry their MDD, from the family the run belongs to ------

def _dense_control_row(**overrides) -> dict:
    row = {
        "run_id": "r",
        "judge_model": "openai/gpt-oss-120b",
        "judge_provider_order": json.dumps(["Cerebras", "Groq"]),
        "judge_embedding_model": "qwen/qwen3-embedding-8b",
        "ragas_version": "0.4.3",
        "metric_prompt_versions": json.dumps(FLOOR_FAMILIES["dense-control-v1"]["match"]["metric_prompt_versions"]),
        "generator_model": "openai/gpt-5-nano",
        "prompt_versions": json.dumps({"answer": "baseline_answer@v1"}),
        "retriever": "dense",
        "eval_subsample_id": "sub100:b551f7f49c91",
    }
    row.update(overrides)
    return row


def test_family_is_found_from_run_provenance():
    assert family_for_run(_dense_control_row()) == ("dense-control-v1", [])
    phase0 = _dense_control_row(prompt_versions=json.dumps({"answer": "answer@v1"}), retriever="bm25")
    assert family_for_run(phase0)[0] == "phase0-bm25-answer-v1"


@pytest.mark.parametrize("key", JUDGED_MATCH_KEYS)
def test_a_changed_judge_generator_or_prompt_gets_no_mdd(key):
    """P2-02: change the judge model, judge prompt (Ragas fingerprints / version) or
    the generator and the P1-11 measurement no longer applies — re-run it."""
    row = _dense_control_row(**{key: json.dumps({"x": "changed"}) if key.endswith("versions") or key.endswith("order") else "changed/model"})
    family, caveats = family_for_run(row)
    assert family is None
    assert "re-run P1-11" in caveats[0]


def test_retriever_or_subsample_change_is_a_caveat_not_a_refusal():
    family, caveats = family_for_run(_dense_control_row(retriever="hybrid_rrf"))
    assert family == "dense-control-v1"
    assert len(caveats) == 1 and "retriever differs" in caveats[0]


def test_tier_1_runs_need_no_judged_family():
    assert family_for_run({"run_id": "t", "judge_model": "", "retriever": "dense"}) == (None, [])
    assert retrieval_family_for_run({"retriever": "dense"}) == "dense-control-v1"
    assert retrieval_family_for_run({"retriever": "bm25"}) is None  # BM25's spread is exactly zero


def test_verdict_labels_and_the_replicate_zone():
    within = mdd_verdict("faithfulness", 0.010, family="dense-control-v1")
    assert within["label"] == "within judge noise" and within["replicates_advised"] is False
    marginal = mdd_verdict("faithfulness", 0.020, family="dense-control-v1")   # 1.43 × MDD
    assert marginal["label"] == "significant" and marginal["replicates_advised"] is True
    clear = mdd_verdict("faithfulness", 0.030, family="dense-control-v1")      # 2.1 × MDD
    assert clear["label"] == "significant" and clear["replicates_advised"] is False
    # MDDs are stated to 3 decimals; the delta is compared at that precision.
    edge = mdd_verdict("answer_correctness", -0.0503, family="dense-control-v1", slice_name="gold_docs:multi")
    assert edge["label"] == "within judge noise"
    assert mdd_verdict("faithfulness", 0.5, family=None)["label"] == "no MDD measured"


def test_slice_floors_are_larger_and_used():
    multi = mdd_verdict("faithfulness", 0.05, family="dense-control-v1", slice_name="gold_docs:multi")
    assert multi["mdd"] == 0.112 and multi["label"] == "within judge noise"
    corpus = mdd_verdict("faithfulness", 0.05, family="dense-control-v1")
    assert corpus["label"] == "significant"
    assert mdd_verdict("faithfulness", 0.05, family="dense-control-v1", slice_name="article_type:article")["mdd"] is None


def test_p2_02_line_format():
    info = mdd_verdict("faithfulness", 0.03, family="dense-control-v1")
    assert format_judged("faithfulness", 0.74, 0.71, info) == (
        "faithfulness 0.740 (baseline 0.710, Δ+0.030, MDD ±0.014 → significant)"
    )
    info = mdd_verdict("faithfulness", 0.01, family="dense-control-v1")
    assert format_judged("faithfulness", 0.72, 0.71, info).endswith("MDD ±0.014 → within judge noise)")
