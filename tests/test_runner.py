"""P0-09 / P0-10 — tiers, the runner, the results store, and `rag diff`."""

from __future__ import annotations

import json

import pytest

from rag.eval.qrels import run_from_results
from rag.retrieval.base import RetrievalResult, ScoredChunk
from rag.runner.config import EvalTier, RunConfig, load_config_file
from rag.runner.diff import compare_provenance, diff_runs
from rag.runner.registry import build_retriever, registered_retrievers
from rag.runner.store import ResultsStore


# --- P0-09: tiers -----------------------------------------------------------

def test_tier_1_is_the_default_and_uses_no_llm():
    config = RunConfig(name="t")
    assert config.eval_tier is EvalTier.TIER_1
    assert config.eval_tier.uses_llm is False


def test_tier_2_refuses_to_run_without_models_chosen():
    """Model choice is Krutik's decision, not a default this code may invent."""
    with pytest.raises(ValueError, match="generator_model and judge_model"):
        RunConfig(name="t", eval_tier=EvalTier.TIER_2)
    with pytest.raises(ValueError, match="judge_model"):
        RunConfig(name="t", eval_tier=EvalTier.TIER_2, generator_model="some/model")

    ok = RunConfig(
        name="t", eval_tier=EvalTier.TIER_2, generator_model="a/b", judge_model="c/d"
    )
    assert ok.eval_tier.uses_llm is True


# --- P0-10: config identity -------------------------------------------------

def test_config_hash_is_stable_and_ignores_the_name():
    a = RunConfig(name="one")
    b = RunConfig(name="two")
    assert a.config_hash == b.config_hash, "renaming a run must not change its identity"


def test_config_hash_changes_with_anything_that_moves_a_number():
    base = RunConfig(name="x")
    for field, value in (
        ("top_k", 10),
        ("doc_pooling", "sum"),
        ("split", "dev_large"),
        ("seed", 2),
        ("chunker_params", {"chunk_size": 256, "overlap": 0}),
    ):
        assert base.with_(**{field: value}).config_hash != base.config_hash, field


def test_retrieval_depth_must_cover_top_k():
    with pytest.raises(ValueError, match="retrieval_depth"):
        RunConfig(name="x", retrieval_depth=3, top_k=5)


def test_unknown_config_key_is_an_error(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("name: x\ntop_kk: 5\n")
    with pytest.raises(ValueError, match="unknown config keys"):
        load_config_file(path)


def test_smoke_config_loads_and_is_marked():
    config = load_config_file("configs/smoke_toy.yaml")
    assert config.harness_smoke_test is True
    assert config.retriever in registered_retrievers()


# --- P0-10: the rank-score regression --------------------------------------

def test_run_scores_follow_the_pooled_ranking_not_raw_scores():
    """Regression for MIS-003.

    Pooled scores tie constantly. Handing the raw ties to an IR library lets it
    re-break them by its own rule, so the metric scores a different ordering than
    the one recorded in run_questions — a gold document at stored rank 4 could score
    zero recall@5.
    """
    result = RetrievalResult(
        question_id="q1",
        chunks=[ScoredChunk("c1", "dA", 0.5)],
        docs=[("dA", 0.5), ("dB", 0.5), ("dC", 0.5)],
    )
    run = run_from_results([result])["q1"]
    assert run["dA"] > run["dB"] > run["dC"], "tied scores must become a strict order"
    assert list(run) == ["dA", "dB", "dC"]

    raw = run_from_results([result], rank_scores=False)["q1"]
    assert raw["dA"] == raw["dB"] == 0.5


# --- P0-10: store and diff --------------------------------------------------

def _row(run_id: str, **overrides) -> dict:
    row = {
        "run_id": run_id,
        "timestamp": f"2026-09-09T00:00:0{run_id[-1]}+00:00",
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
    }
    row.update(overrides)
    return row


def _question(run_id: str, question_id: str, strict: float, retrieved: list[str], gold: list[str]) -> dict:
    return {
        "run_id": run_id,
        "question_id": question_id,
        "retrieved_doc_ids": json.dumps(retrieved),
        "retrieved_chunk_ids": json.dumps([]),
        "scores": json.dumps([]),
        "gold_doc_ids": json.dumps(gold),
        "metrics_json": json.dumps({"strict_recall@5": strict}),
        "generated_answer": None,
        "cited_doc_ids": json.dumps([]),
        "latency_ms": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": None,
    }


@pytest.fixture()
def store(tmp_path):
    with ResultsStore(tmp_path / "runs.sqlite") as store:
        store.start_run(_row("run_a"))
        store.start_run(_row("run_b"))
        store.finish_run("run_a", status="VALID", metrics={"strict_recall@5": 0.5}, n_questions=2)
        store.finish_run("run_b", status="VALID", metrics={"strict_recall@5": 0.5}, n_questions=2)
        store.add_questions([
            _question("run_a", "q1", 1.0, ["dA"], ["dA"]),
            _question("run_a", "q2", 0.0, ["dZ"], ["dB"]),
        ])
        store.add_questions([
            _question("run_b", "q1", 0.0, ["dZ"], ["dA"]),
            _question("run_b", "q2", 1.0, ["dB"], ["dB"]),
        ])
        yield store


def test_store_round_trips_a_run(store):
    row = store.get_run("run_a")
    assert row["status"] == "VALID"
    assert json.loads(row["metrics_json"])["strict_recall@5"] == 0.5
    assert len(store.get_questions("run_a")) == 2


def test_diff_lists_flips_in_both_directions(store):
    report = diff_runs("run_a", "run_b", store=store)
    assert report["n_gained"] == 1 and report["n_lost"] == 1
    assert report["gained"][0]["question_id"] == "q2"
    assert report["lost"][0]["question_id"] == "q1"


def test_diff_reports_gold_ranks_for_flipped_questions(store):
    report = diff_runs("run_a", "run_b", store=store)
    lost = report["lost"][0]
    assert lost["ranks_a"] == {"dA": 1}
    assert lost["ranks_b"] == {"dA": None}, "an unretrieved gold document has no rank"


def test_diff_refuses_to_imply_an_invalid_comparison():
    verdict = compare_provenance(
        {"corpus_hash": "sha256:one", "split": "dev"},
        {"corpus_hash": "sha256:two", "split": "dev"},
    )
    assert verdict["comparable"] is False
    assert "corpus_hash" in verdict["differences"]


def test_smoke_test_runs_are_never_comparable():
    verdict = compare_provenance({"harness_smoke_test": 1}, {"harness_smoke_test": 0})
    assert verdict["comparable"] is False
    assert verdict["involves_harness_smoke_test"] is True


def test_missing_run_is_an_error(store):
    with pytest.raises(KeyError, match="no run"):
        diff_runs("run_a", "nope", store=store)


def test_test_split_openings_are_queryable(store):
    assert store.test_openings() == []
    store.start_run(_row("run_t", split="test"))
    assert [row["run_id"] for row in store.test_openings()] == ["run_t"]


# --- P0-09: the held-out split guard ---------------------------------------

def test_test_split_requires_the_explicit_flag(store):
    from rag.runner.run import check_test_split_guard

    config = RunConfig(name="x", split="test")
    with pytest.raises(PermissionError, match="--open-test"):
        check_test_split_guard(config, open_test=False, store=store)

    # P0-12: the flag alone is not enough — the reason goes into the openings log.
    with pytest.raises(PermissionError, match="--reason"):
        check_test_split_guard(config, open_test=True, store=store, reason="")

    check_test_split_guard(config, open_test=True, store=store, reason="phase boundary")


def test_dev_split_needs_no_flag(store):
    from rag.runner.run import check_test_split_guard

    check_test_split_guard(RunConfig(name="x", split="dev"), open_test=False, store=store)


def test_judge_must_not_share_the_generators_family():
    """P0-07: same-family judging carries unmeasured self-preference bias."""
    with pytest.raises(ValueError, match="self-preference"):
        RunConfig(
            name="x",
            eval_tier=EvalTier.TIER_2,
            generator_model="openai/gpt-5-nano",
            judge_model="openai/gpt-5.1",
        )

    ok = RunConfig(
        name="x",
        eval_tier=EvalTier.TIER_2,
        generator_model="openai/gpt-5-nano",
        judge_model="anthropic/claude-sonnet-5",
    )
    assert ok.generator_family == "openai" and ok.judge_family == "anthropic"


def test_subsample_settings_are_part_of_run_identity():
    base = RunConfig(name="x")
    assert base.with_(eval_subsample_size=50).config_hash != base.config_hash
    assert base.with_(full_eval=True).config_hash != base.config_hash


def test_store_migrates_instead_of_requiring_deletion(tmp_path):
    """MIS-007: a schema change must never be a reason to delete the results store."""
    import sqlite3

    path = tmp_path / "runs.sqlite"
    with ResultsStore(path) as store:
        store.start_run(_row("run_old"))

    # Simulate an older database that predates a column.
    conn = sqlite3.connect(path)
    conn.execute("ALTER TABLE runs DROP COLUMN judge_provider_order")
    conn.commit()
    conn.close()

    with ResultsStore(path) as store:  # reopening must migrate, not fail
        columns = {r["name"] for r in store.conn.execute("PRAGMA table_info(runs)")}
        assert "judge_provider_order" in columns
        assert store.get_run("run_old") is not None, "existing rows must survive"


def test_judge_concurrency_is_part_of_config_but_not_of_results():
    """Concurrency changes speed, not scores — but it is recorded for reproducibility."""
    base = RunConfig(name="x")
    assert base.judge_concurrency > 1
    assert base.with_(judge_concurrency=1).config_hash != base.config_hash
