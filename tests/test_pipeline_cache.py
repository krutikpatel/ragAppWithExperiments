"""P2-03 — determinism control for in-pipeline LLM calls.

The cache is keyed on (question_id, prompt_id, prompt_version, model_id, input_hash);
every in-pipeline call runs at temperature 0; the hit rate is recorded on the run;
a run whose pipeline called an LLM is marked `pipeline_nondeterministic`; and a
repeat of an identical config with a warm cache produces identical retrieval metrics.
"""

from __future__ import annotations

import json

import pytest

from rag.generation.base import Completion
from rag.generation.cache import CacheKey, GenerationCache
from rag.generation.pipeline_llm import TEMPERATURE, PipelineLLM
from rag.paths import CORPUS_PARQUET, DEV_PARQUET


def _counting_backend():
    calls = []

    def backend(prompt_text: str) -> Completion:
        calls.append(prompt_text)
        return Completion(text=f"out-{len(calls)}", tokens_in=3, tokens_out=1,
                          reasoning_tokens=0, finish_reason="stop")

    return backend, calls


def test_cache_key_round_trip(tmp_path):
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        key = CacheKey("q1", "decompose", "v1", "m/x", "sha256:abc")
        assert cache.get(key) is None
        cache.put(key, "sub-q1\nsub-q2", tokens_in=10, tokens_out=5)
        assert cache.get(key).output == "sub-q1\nsub-q2"
        assert cache.get(CacheKey("q1", "decompose", "v2", "m/x", "sha256:abc")) is None, "version is in the key"
        assert len(cache) == 1


def test_pipeline_llm_is_temperature_zero_and_counts_hits(tmp_path):
    backend, calls = _counting_backend()
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        llm = PipelineLLM("m/x", cache=cache, backend=backend)
        first = llm.complete(question_id="q1", prompt_id="p", prompt_version="v1", prompt_text="hello")
        again = llm.complete(question_id="q1", prompt_id="p", prompt_version="v1", prompt_text="hello")
        other = llm.complete(question_id="q1", prompt_id="p", prompt_version="v1", prompt_text="hello!")
        assert first == again == "out-1" and other == "out-2"
        assert len(calls) == 2
        stats = llm.stats()
        assert stats["temperature"] == 0.0 == TEMPERATURE
        assert (stats["calls"], stats["cache_hits"], stats["cache_misses"]) == (3, 1, 2)
        assert stats["hit_rate"] == pytest.approx(1 / 3)
        assert stats["prompts"] == ["p@v1"]

        # A second PipelineLLM on the same cache — a new run — replays everything.
        warm = PipelineLLM("m/x", cache=cache, backend=backend)
        warm.complete(question_id="q1", prompt_id="p", prompt_version="v1", prompt_text="hello")
        assert warm.stats()["hit_rate"] == 1.0 and len(calls) == 2


def test_input_hash_covers_decoding_settings(tmp_path):
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        a = PipelineLLM("m/x", cache=cache, backend=_counting_backend()[0], max_tokens=100)
        b = PipelineLLM("m/x", cache=cache, backend=_counting_backend()[0], max_tokens=200)
        assert a.input_hash("same") != b.input_hash("same")


def test_pipeline_llm_refuses_an_unchosen_model(tmp_path):
    with GenerationCache(tmp_path / "c.sqlite") as cache, pytest.raises(ValueError, match="Krutik"):
        PipelineLLM("", cache=cache, backend=_counting_backend()[0])


frozen = pytest.mark.skipif(
    not (CORPUS_PARQUET.exists() and DEV_PARQUET.exists()),
    reason="frozen corpus and dev split not built on this machine",
)


@frozen
def test_repeat_run_with_warm_cache_is_identical_and_flags_a_cold_repeat(tmp_path):
    """P2-03's acceptance test: an LLM-in-the-loop config run twice. With a warm
    cache the retrieval metrics and every retrieved document list are identical and
    the hit rate is 100%. A third run on a fresh cache is a repeat with hit rate 0
    and is flagged."""
    from rag.runner.config import load_config_file
    from rag.runner.run import run
    from rag.runner.store import ResultsStore

    config = load_config_file("configs/smoke_p2_03_llm_rewrite.yaml")
    assert config.harness_smoke_test

    with ResultsStore(tmp_path / "runs.sqlite") as store, GenerationCache(tmp_path / "gen.sqlite") as cache:
        cold = run(config, store=store, generation_cache=cache)
        warm = run(config, store=store, generation_cache=cache)
        with GenerationCache(tmp_path / "other.sqlite") as fresh, pytest.warns(UserWarning, match="hit rate of 0%"):
            cold_again = run(config, store=store, generation_cache=fresh)

        for row in (cold, warm, cold_again):
            assert row["pipeline_nondeterministic"] == 1
            stats = json.loads(row["pipeline_llm_json"])
            assert stats["temperature"] == 0.0 and stats["calls"] == 200
        assert json.loads(cold["pipeline_llm_json"])["hit_rate"] == 0.0
        assert json.loads(warm["pipeline_llm_json"])["hit_rate"] == 1.0
        assert json.loads(cold_again["pipeline_llm_json"])["hit_rate"] == 0.0

        m_cold, m_warm = json.loads(cold["metrics_json"]), json.loads(warm["metrics_json"])
        for key in ("strict_recall@5", "loose_recall@5", "ndcg@10", "collapse_ratio_mean"):
            assert m_cold[key] == m_warm[key], key
        assert "pipeline_cache_flag" not in m_cold
        assert "pipeline_cache_flag" not in m_warm, "a warm repeat is what the cache is for"
        assert "repeat of config" in json.loads(cold_again["metrics_json"])["pipeline_cache_flag"]

        q_cold, q_warm = store.get_questions(cold["run_id"]), store.get_questions(warm["run_id"])
        assert all(q_cold[q]["retrieved_doc_ids"] == q_warm[q]["retrieved_doc_ids"] for q in q_cold)


@frozen
def test_runs_without_pipeline_llm_are_marked_deterministic(tmp_path):
    from rag.runner.config import load_config_file
    from rag.runner.run import run
    from rag.runner.store import ResultsStore

    config = load_config_file("configs/smoke_toy.yaml")
    with ResultsStore(tmp_path / "runs.sqlite") as store, GenerationCache(tmp_path / "gen.sqlite") as cache:
        row = run(config, store=store, generation_cache=cache)
    assert row["pipeline_nondeterministic"] == 0
    assert json.loads(row["metrics_json"])["pipeline_nondeterministic"] is False
