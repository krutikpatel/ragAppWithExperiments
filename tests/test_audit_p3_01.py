"""P3-01 — the run provenance audit. Zero model calls, a temp store and a temp cache."""

from __future__ import annotations

import json

import pytest

from rag.generation.cache import CacheKey, GenerationCache
from rag.runner.audit import format_audit, provenance_audit
from rag.runner.store import ResultsStore


def _row(run_id: str, split: str, tier: str = "tier2", **overrides) -> dict:
    row = {
        "run_id": run_id,
        "timestamp": "2026-09-27T00:00:00+00:00",
        "name": run_id,
        "config_hash": "hash",
        "config_json": json.dumps({"skip_judge": split == "test"}),
        "corpus_hash": "sha256:corpus",
        "normalization_version": "norm-v1",
        "hf_revision": "abc",
        "dataset_config": split,
        "split": split,
        "split_hash": f"sha256:{split}",
        "git_sha": "deadbeefcafe",
        "git_dirty": 0,
        "eval_tier": tier,
        "doc_pooling": "max",
        "harness_smoke_test": 0,
        "retriever": "dense",
        "generator_model": "openai/gpt-5-nano" if tier == "tier2" else None,
        "prompt_versions": json.dumps({"answer": "baseline_answer@v1"} if tier == "tier2" else {}),
        "retriever_meta": json.dumps({"cache_hit": True, "index_key": "k",
                                      "embedder_now": {"usage": {"calls": 3, "prompt_tokens": 30}}}),
    }
    row.update(overrides)
    return row


def _question(run_id: str, qid: str, hit: float, answer: str | None) -> dict:
    return {
        "run_id": run_id, "question_id": qid,
        "retrieved_doc_ids": "[]", "retrieved_chunk_ids": "[]", "context_chunk_ids": "[]",
        "scores": "[]", "gold_doc_ids": "[]",
        "metrics_json": json.dumps({"gold_in_context": hit, "strict_recall@5": hit}),
        "generated_answer": answer, "cited_doc_ids": "[]",
        "latency_ms": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": None,
    }


def _add(store: ResultsStore, run_id: str, split: str, questions: list[tuple[str, float, str | None]],
         tier: str = "tier2", skip_judge: bool = False) -> None:
    store.start_run(_row(run_id, split, tier))
    store.add_questions([_question(run_id, q, h, a) for q, h, a in questions])
    store.finish_run(run_id, status="VALID", metrics={"skip_judge": skip_judge}, n_questions=len(questions))


@pytest.fixture()
def env(tmp_path):
    with ResultsStore(tmp_path / "runs.sqlite") as store, GenerationCache(tmp_path / "cache.sqlite") as cache:
        _add(store, "dev2", "dev", [
            ("d1", 1.0, "1. Click Settings. 2. Click Save. [doc:a]"),
            ("d2", 0.0, "I'm sorry, the provided articles do not cover this."),
            ("d3", 1.0, "1. Open the editor. 2. Publish. [doc:b]"),
        ])
        _add(store, "test2", "test", [
            ("t1", 1.0, "1. Go to Billing. 2. Cancel. [doc:c]"),
            ("t2", 1.0, "1. Open Domains. 2. Connect. [doc:d]"),
            ("t3", 0.0, "I'm sorry, the provided articles do not cover this question at all."),
        ], skip_judge=True)
        _add(store, "dev1", "dev", [("d1", 1.0, None), ("d2", 1.0, None), ("d3", 1.0, None), ("d4", 1.0, None)],
             tier="tier1")
        _add(store, "test1", "test", [("t1", 1.0, None), ("t2", 1.0, None), ("t3", 0.0, None)], tier="tier1")
        yield store, cache


def _audit(store, cache, dev="dev2", test="test2", **kw):
    return provenance_audit(dev, test, store=store, cache=cache, check_splits=False, **kw)


def test_independent_runs_report_no_leak_and_disjoint_ids(env):
    store, cache = env
    report = _audit(store, cache, dev_tier1="dev1", test_tier1="test1")
    assert report["leak_found"] is False
    assert report["agreement_on_shared_ids"]["n_shared"] == 0
    assert report["cross_run_reuse"]["test_judge_ran"] is False
    assert report["outcomes"]["dev"]["refused"] == {"mean": 0.3333, "hits": 1, "n": 3}
    assert report["outcomes"]["test"]["gold_in_context"]["hits"] == 2
    # Tier 1 recall restricted to the Tier 2 subsample: dev has a fourth question outside it.
    t1 = report["tier1_restricted_to_subsample"]["dev"]
    assert (t1["n_split"], t1["n_subsample"]) == (4, 3)
    assert "disjoint" in format_audit(report)


def test_a_shared_question_id_is_a_leak_with_paired_agreement(env):
    store, cache = env
    _add(store, "test_overlap", "test", [("d1", 1.0, "1. Something else. 2. Else. [doc:z]")], skip_judge=True)
    report = _audit(store, cache, test="test_overlap")
    assert report["leak_found"] is True
    assert report["question_sets"]["shared_ids_between_runs"] == ["d1"]
    assert report["agreement_on_shared_ids"]["gold_in_context"] == {"n": 1, "agree": 1}


def test_an_answer_copied_from_the_dev_run_is_flagged(env):
    store, cache = env
    _add(store, "test_copy", "test", [("t9", 1.0, "1. click settings.  2. Click Save. [doc:a]")], skip_judge=True)
    report = _audit(store, cache, test="test_copy")
    assert report["cross_run_reuse"]["test_answers_identical_to_a_dev_answer"] == ["t9"]
    assert report["leak_found"] is True


def test_a_cache_row_that_could_serve_the_answer_prompt_is_flagged(env):
    store, cache = env
    assert _audit(store, cache)["runs"]["test"]["generation"]["cache_rows_for_answer_prompt"] == 0
    cache.put(CacheKey("t1", "baseline_answer", "v1", "openai/gpt-5-nano", "h"), "cached answer")
    report = _audit(store, cache)
    assert report["runs"]["test"]["generation"]["cache_rows_for_answer_prompt"] == 1
    assert report["leak_found"] is True
