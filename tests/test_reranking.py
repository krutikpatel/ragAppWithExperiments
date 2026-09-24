"""P2-10, Axis 5 — reranking.

The properties that matter here are the ones a wrong reranker would quietly
violate: the candidate set is a count of *documents*, the reranker re-orders and
never adds or drops, everything downstream is recomputed from the reranked
ranking, and a hosted reranker's price and response are never taken on trust.
"""

from __future__ import annotations

import json

import pytest

from rag.reranking.base import (
    Reranker,
    apply_rerank,
    candidate_prefix,
    check_same_chunks,
    rerank_result,
)
from rag.retrieval.base import RetrievalResult, ScoredChunk

# doc A has three chunks, doc B two, then one each. Long articles collapsing into
# one document is the characteristic shape of this corpus (P1-03).
CHUNK_TO_DOC = {
    "a1": "A", "a2": "A", "a3": "A",
    "b1": "B", "b2": "B",
    "c1": "C", "d1": "D", "e1": "E", "f1": "F",
}
RANKED = [("a1", 9.0), ("b1", 8.0), ("a2", 7.0), ("c1", 6.0), ("b2", 5.0),
          ("d1", 4.0), ("a3", 3.0), ("e1", 2.0), ("f1", 1.0)]


def _chunks(ranked):
    return [ScoredChunk(chunk_id=c, doc_id=CHUNK_TO_DOC[c], score=s) for c, s in ranked]


def _result(question_id="q1"):
    from rag.retrieval.pooling import pool_chunks_to_docs, select_distinct_docs

    return RetrievalResult(
        question_id=question_id,
        chunks=_chunks(RANKED),
        docs=pool_chunks_to_docs(RANKED, CHUNK_TO_DOC, rule="max"),
        doc_pooling="max",
        meta={"retriever": "fake"},
        context=select_distinct_docs(RANKED, CHUNK_TO_DOC, k=2, candidate_pool=9),
    )


# --- candidates are documents, not chunks (P1-03, DEC-040) --------------------

def test_candidate_prefix_counts_documents_and_keeps_all_their_chunks():
    head, tail = candidate_prefix(RANKED, CHUNK_TO_DOC, n_docs=3)
    assert [c for c, _ in head] == ["a1", "b1", "a2", "c1", "b2"]
    assert {CHUNK_TO_DOC[c] for c, _ in head} == {"A", "B", "C"}
    # a2 and b2 are in: the reranker sees every ranked chunk of a candidate
    # document, which is the only way it *can* re-concentrate the context.
    assert [c for c, _ in tail] == ["d1", "a3", "e1", "f1"]


def test_candidate_prefix_of_one_document_is_that_documents_chunks():
    head, tail = candidate_prefix(RANKED, CHUNK_TO_DOC, n_docs=1)
    assert [c for c, _ in head] == ["a1"]
    assert len(tail) == len(RANKED) - 1


def test_candidate_prefix_wider_than_the_ranking_takes_all_of_it():
    head, tail = candidate_prefix(RANKED, CHUNK_TO_DOC, n_docs=99)
    assert len(head) == len(RANKED) and tail == []


def test_candidate_prefix_rejects_zero():
    with pytest.raises(ValueError, match="at least 1"):
        candidate_prefix(RANKED, CHUNK_TO_DOC, n_docs=0)


# --- splicing -----------------------------------------------------------------

def test_apply_rerank_keeps_every_chunk_and_the_tails_order():
    head, tail = candidate_prefix(RANKED, CHUNK_TO_DOC, n_docs=3)
    reranked = list(reversed(_chunks(head)))
    spliced = apply_rerank(reranked, tail, CHUNK_TO_DOC)
    assert [c for c, _ in spliced] == ["b2", "c1", "a2", "b1", "a1", "d1", "a3", "e1", "f1"]
    assert sorted(c for c, _ in spliced) == sorted(c for c, _ in RANKED)


def test_apply_rerank_puts_the_tail_strictly_below_every_reranked_chunk():
    head, tail = candidate_prefix(RANKED, CHUNK_TO_DOC, n_docs=3)
    spliced = apply_rerank(_chunks(head), tail, CHUNK_TO_DOC)
    scores = [s for _, s in spliced]
    assert scores == sorted(scores, reverse=True), "the spliced ranking must be totally ordered"
    assert min(scores[: len(head)]) > max(scores[len(head) :])


def test_apply_rerank_rejects_a_chunk_the_index_does_not_have():
    with pytest.raises(KeyError, match="not in the index"):
        apply_rerank([ScoredChunk("ghost", "Z", 1.0)], [], CHUNK_TO_DOC)


def test_check_same_chunks_catches_a_reranker_that_drops_candidates():
    before = _chunks(RANKED[:4])
    with pytest.raises(RuntimeError, match="only re-order"):
        check_same_chunks(before, before[:2])


# --- everything downstream is recomputed --------------------------------------

class _Concentrate(Reranker):
    """Puts every chunk of one document on top — the failure mode P2-10 asks to
    be measured: a cross-encoder undoing the retriever's document diversity."""

    name = "concentrate"

    def rerank(self, query, chunks, *, question_id=""):
        target = chunks[0].doc_id
        ordered = [c for c in chunks if c.doc_id == target] + [c for c in chunks if c.doc_id != target]
        return [ScoredChunk(c.chunk_id, c.doc_id, float(len(ordered) - i)) for i, c in enumerate(ordered)]


def test_rerank_result_recomputes_the_collapse_ratio():
    before = _result()
    assert before.context.collapse_ratio == 1.0  # a1 then b1: two chunks, two docs

    after, record = rerank_result(
        before, _Concentrate({}), query="q", chunk_to_doc=CHUNK_TO_DOC,
        n_docs=3, k_docs=2, candidate_pool=9, doc_pooling="max",
    )
    # A's two candidate chunks now lead, so the walk scans a1, a2, b1 — three
    # chunks for two documents, where before it took two. That rise IS the finding
    # P2-10 asks for, and it only exists because pooling is recomputed here.
    assert after.context.doc_ids == ["A", "B"]
    assert after.context.collapse_ratio == 1.5 > before.context.collapse_ratio
    assert record["rerank_candidate_docs"] == 3.0
    assert record["rerank_candidate_chunks"] == 5.0


def test_rerank_result_records_how_much_of_the_context_changed():
    class _Promote(Reranker):
        name = "promote"

        def rerank(self, query, chunks, *, question_id=""):
            ordered = sorted(chunks, key=lambda c: c.doc_id, reverse=True)
            return [ScoredChunk(c.chunk_id, c.doc_id, float(len(ordered) - i)) for i, c in enumerate(ordered)]

    before = _result()
    after, record = rerank_result(
        before, _Promote({}), query="q", chunk_to_doc=CHUNK_TO_DOC,
        n_docs=3, k_docs=2, candidate_pool=9, doc_pooling="max",
    )
    assert before.doc_ids[:2] == ["A", "B"] and after.doc_ids[:2] == ["C", "B"]
    assert record["rerank_topk_changed"] == 1.0


def test_rerank_result_leaves_the_ranking_alone_when_the_reranker_does():
    class _Identity(Reranker):
        name = "identity"

        def rerank(self, query, chunks, *, question_id=""):
            return list(chunks)

    before = _result()
    after, record = rerank_result(
        before, _Identity({}), query="q", chunk_to_doc=CHUNK_TO_DOC,
        n_docs=4, k_docs=2, candidate_pool=9, doc_pooling="max",
    )
    assert after.doc_ids == before.doc_ids
    assert after.context.doc_ids == before.context.doc_ids
    assert record["rerank_topk_changed"] == 0.0


# --- the config dimension ------------------------------------------------------

def test_adding_axis_5_did_not_move_the_ledgers_hashes(tmp_path):
    """MIS-019: a new field with a default moves every config_hash, including the
    controls'. Axis 5's fields are excluded while `reranker` is empty, so every run
    already in the ledger still matches its config."""
    from rag.runner.promoted import load_promoted

    promoted = load_promoted()
    assert promoted.config_hash == "7c99bc8e9a88e878"
    assert promoted.identity_hash == "70610a6119fb9223"


def test_a_reranker_changes_the_hash():
    from rag.runner.config import RunConfig

    plain = RunConfig(name="t")
    reranked = plain.with_(reranker="toy_reverse", reranker_params={"model": "x"})
    assert plain.config_hash != reranked.config_hash
    assert plain.identity_hash != reranked.identity_hash


def test_rerank_candidates_alone_does_nothing_without_a_reranker():
    """An absent dimension is absent: changing its knob with the switch off cannot
    change a number, so it must not change a hash either."""
    from rag.runner.config import RunConfig

    assert RunConfig(name="t").config_hash == RunConfig(name="t", rerank_candidates=17).config_hash


def test_reranking_is_one_dimension_against_promoted():
    from rag.runner.promoted import config_diff, load_promoted

    promoted = load_promoted()
    candidate = promoted.with_(
        axis="reranking", reranker="openrouter",
        reranker_params={"model": "cohere/rerank-v3.5", "provider": "Cohere"},
    )
    diff = config_diff(candidate, promoted)
    assert diff["dimensions"] == ["reranking"] and diff["one_dimension"]


def test_config_refuses_more_candidates_than_the_retriever_ranked():
    from rag.runner.config import RunConfig

    with pytest.raises(ValueError, match="never ranked"):
        RunConfig(name="t", reranker="toy_reverse", retrieval_depth=20, rerank_candidates=50,
                  candidate_pool=20)


def test_config_refuses_fewer_candidates_than_the_context_needs():
    from rag.runner.config import RunConfig

    with pytest.raises(ValueError, match="at least top_k"):
        RunConfig(name="t", reranker="toy_reverse", top_k=5, rerank_candidates=3)


# --- cost: measured, never listed (MIS-025) ------------------------------------

def test_rerank_cost_reproduces_what_exp_0024_was_actually_billed():
    """DEC-035: calibrate an estimator on a measured run. EXP-0024 billed **234**
    search units for 200 dev questions at 50 candidate documents, not the 200 the
    first estimate assumed — Cohere's unit tracks candidate length, not candidate
    count. Out-of-sample validation is still owed (OQ-036)."""
    from rag.runner.cost import RERANK_CALIBRATION_RUN_ID, PricingTable, estimate_rerank_cost

    pricing = PricingTable.load()
    estimate = estimate_rerank_cost(
        reranker="openrouter",
        estimate_params={"kind": "rerank_endpoint", "model": "cohere/rerank-v3.5", "provider": "Cohere"},
        n_questions=200, candidate_docs=50, candidate_words=348, pricing=pricing,
    )
    assert estimate["search_units"] == 234
    assert estimate["rerank_usd"] == pytest.approx(0.234)
    assert RERANK_CALIBRATION_RUN_ID in estimate["source"]
    assert "NOT yet validated out of sample" in estimate["source"]


def test_token_billed_rerank_charges_the_query_once_per_document():
    """MIS-032: a cross-encoder scores (query, document) PAIRS, so the query and the
    model's template are billed once per DOCUMENT, not once per call. Ignoring that
    made EXP-0026's estimate 32% low. Calibrated on run_20260924_033136_e51f, which
    billed 6,051,291 tokens / $1.2103."""
    from rag.runner.cost import PricingTable, estimate_rerank_cost

    pricing = PricingTable.load()
    estimate = estimate_rerank_cost(
        reranker="openrouter",
        estimate_params={"kind": "rerank_endpoint", "model": "qwen/qwen3-reranker-8b",
                         "provider": "Fireworks"},
        n_questions=200, candidate_docs=50, candidate_words=309, pricing=pricing,
    )
    assert estimate["rerank_usd"] == pytest.approx(1.2103, abs=0.01)
    assert estimate["tokens"] == pytest.approx(6_051_291, rel=0.01)
    # The per-pair overhead is the whole point: without it the estimate is a third low.
    assert estimate["tokens_per_pair"] > 400
    assert "PER DOCUMENT" in estimate["source"]


def test_rerank_cost_scales_with_the_split_not_the_corpus():
    """Preflight 34: a reranker charges again for every question, so the same config
    is cents on `dev` and dollars on `dev_large`."""
    from rag.runner.cost import PricingTable, estimate_rerank_cost

    pricing = PricingTable.load()
    params = {"kind": "rerank_endpoint", "model": "cohere/rerank-v3.5", "provider": "Cohere"}
    dev = estimate_rerank_cost(reranker="openrouter", estimate_params=params, n_questions=200,
                               candidate_docs=50, candidate_words=348, pricing=pricing)
    dev_large = estimate_rerank_cost(reranker="openrouter", estimate_params=params, n_questions=6221,
                                     candidate_docs=50, candidate_words=348, pricing=pricing)
    assert dev_large["rerank_usd"] / dev["rerank_usd"] == pytest.approx(6221 / 200, rel=0.01)


def test_an_unpriced_reranker_is_unknown_not_free():
    from rag.runner.cost import PricingTable, estimate_rerank_cost, estimate_run_cost

    pricing = PricingTable.load()
    estimate = estimate_rerank_cost(
        reranker="openrouter",
        estimate_params={"kind": "rerank_endpoint", "model": "nobody/rerank-x", "provider": "Nowhere"},
        n_questions=200, candidate_docs=50, candidate_words=329, pricing=pricing,
    )
    assert "rerank_usd" not in estimate
    assert "never free" in estimate["price_unavailable"]
    run = estimate_run_cost(tier2=None, index={"index_usd": 0.0, "query_usd": 0.0}, rerank=estimate)
    assert run["over_gate"], "an unknown rerank price must halt the run, not pass the gate"


def test_pricing_refresh_would_not_overwrite_the_measured_rerank_block():
    """OpenRouter lists every rerank model at $0 while the calls bill real money, so
    `rag pricing refresh` copies this block through instead of re-fetching it."""
    import inspect

    from rag.runner import cost

    source = inspect.getsource(cost.refresh_pricing)
    assert "rerank=current.rerank" in source
    assert PricingHasMeasuredRates()


def PricingHasMeasuredRates() -> bool:
    from rag.runner.cost import PricingTable

    pricing = PricingTable.load()
    rule = pricing.rerank_price("cohere/rerank-v3.5", "Cohere")
    return rule is not None and rule["usd_per_unit"] == 0.001


# --- the hosted reranker guards its inputs and its responses -------------------

def test_hosted_reranker_refuses_an_unpinned_provider():
    from rag.reranking.openrouter import OpenRouterReranker

    with pytest.raises(ValueError, match="provider"):
        OpenRouterReranker({}, model="cohere/rerank-v3.5")


def test_hosted_reranker_refuses_a_missing_model():
    from rag.reranking.openrouter import OpenRouterReranker

    with pytest.raises(ValueError, match="Krutik"):
        OpenRouterReranker({}, provider="Cohere")


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"results": [{"index": 0, "relevance_score": 1.0}]}, "short result list"),
        ({"results": [{"index": 0, "relevance_score": 1.0}, {"index": 5, "relevance_score": 0.1}]}, "index 5"),
        ({"results": [{"index": 0, "relevance_score": 1.0}, {"index": 0, "relevance_score": 0.1}]}, "index 0"),
        ({"provider": "Somebody", "results": [{"index": i, "relevance_score": 0.5} for i in range(2)]},
         "not the pinned"),
        ({}, "no `results`"),
    ],
)
def test_hosted_reranker_asserts_the_response(payload, message):
    """MIS-006: a short or scrambled result list is a broken call, not a ranking."""
    from rag.reranking.openrouter import OpenRouterReranker

    reranker = OpenRouterReranker({}, model="cohere/rerank-v3.5", provider="Cohere")
    with pytest.raises(RuntimeError, match=message):
        reranker._parse(payload, 2)


def test_hosted_reranker_takes_cost_from_the_response_not_a_table():
    from rag.reranking.openrouter import OpenRouterReranker

    reranker = OpenRouterReranker({}, model="cohere/rerank-v3.5", provider="Cohere")
    reranker._parse(
        {"provider": "Cohere", "usage": {"search_units": 1, "cost": 0.001},
         "results": [{"index": 0, "relevance_score": 0.9}, {"index": 1, "relevance_score": 0.2}]},
        2,
    )
    assert reranker.query_cost_usd() == 0.001
    assert reranker.provenance()["usage"]["search_units"] == 1


def test_hosted_reranker_returns_scores_in_document_order():
    from rag.reranking.openrouter import OpenRouterReranker

    reranker = OpenRouterReranker({}, model="cohere/rerank-v3.5", provider="Cohere")
    scores = reranker._parse(
        {"results": [{"index": 2, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.5},
                     {"index": 1, "relevance_score": 0.1}]},
        3,
    )
    assert scores == [0.5, 0.1, 0.9]


# --- the LLM reranker ----------------------------------------------------------

def test_llm_reranker_refuses_to_run_outside_the_pipeline_cache():
    """DEC-049: every in-pipeline LLM call goes through PipelineLLM, or the run is
    not replayable and its retrieval metrics are not a fixed outcome."""
    from rag.reranking.llm import LLMReranker

    with pytest.raises(ValueError, match="PipelineLLM"):
        LLMReranker({}, model="openai/gpt-5-nano")


def test_llm_reranker_is_marked_nondeterministic_by_carrying_a_pipeline_llm(tmp_path):
    from rag.generation.cache import GenerationCache
    from rag.reranking.llm import LLMReranker

    with GenerationCache(tmp_path / "c.sqlite") as cache:
        reranker = LLMReranker({}, generation_cache=cache, model="openai/gpt-5-nano")
        assert reranker.pipeline_llm is not None
        assert reranker.pipeline_llm.stats()["temperature"] == 0.0


def test_llm_reranker_uses_the_cache_and_never_calls_twice(tmp_path):
    from rag.generation.cache import GenerationCache
    from rag.generation.pipeline_llm import PipelineLLM
    from rag.reranking.llm import LLMReranker

    calls = []

    def backend(prompt_text):
        from rag.generation.base import Completion

        calls.append(prompt_text)
        return Completion(text="2, 1", tokens_in=10, tokens_out=3, reasoning_tokens=0,
                          finish_reason="stop")

    with GenerationCache(tmp_path / "c.sqlite") as cache:
        reranker = LLMReranker({"x": "alpha", "y": "beta"}, generation_cache=cache, model="m")
        reranker.pipeline_llm = PipelineLLM("m", cache=cache, backend=backend)
        chunks = [ScoredChunk("x", "X", 1.0), ScoredChunk("y", "Y", 0.5)]
        first = reranker.rerank("q", chunks, question_id="q1")
        second = reranker.rerank("q", chunks, question_id="q1")
    assert [c.chunk_id for c in first] == ["y", "x"]
    assert first == second
    assert len(calls) == 1, "the second call must be served from the generation cache"
    assert reranker.pipeline_llm.stats()["hit_rate"] == 0.5


# --- the output parser, on adversarial and on real output (preflight 21) --------

@pytest.mark.parametrize(
    "text, expected, stats",
    [
        ("3, 1, 2", [2, 0, 1], {"invented": 0, "repeated": 0, "omitted": 0}),
        ("1\n2\n3", [0, 1, 2], {"invented": 0, "repeated": 0, "omitted": 0}),
        ("Ranking: [3], [2], [1]", [2, 1, 0], {"invented": 0, "repeated": 0, "omitted": 0}),
        # A number outside 1..n is an invented candidate: dropped and counted.
        ("3, 9, 1", [2, 0, 1], {"invented": 1, "repeated": 0, "omitted": 1}),
        # A repeat keeps its first position and is counted.
        ("2, 2, 1", [1, 0, 2], {"invented": 0, "repeated": 1, "omitted": 1}),
        # A partial answer: the rest keep the retriever's order, below.
        ("2", [1, 0, 2], {"invented": 0, "repeated": 0, "omitted": 2}),
        # Prose with no usable numbers falls back to the retriever's order entirely.
        ("I cannot rank these.", [0, 1, 2], {"invented": 0, "repeated": 0, "omitted": 3}),
        ("", [0, 1, 2], {"invented": 0, "repeated": 0, "omitted": 3}),
    ],
)
def test_parse_ranking(text, expected, stats):
    from rag.reranking.llm import parse_ranking

    parsed = parse_ranking(text, 3)
    assert parsed["order"] == expected
    for key, value in stats.items():
        assert parsed[key] == value, key


def test_parse_ranking_always_returns_every_candidate_exactly_once():
    from rag.reranking.llm import parse_ranking

    for text in ("5, 5, 99, 1", "", "nonsense", "1,2,3,4,5", "[4] then [2]"):
        order = parse_ranking(text, 5)["order"]
        assert sorted(order) == [0, 1, 2, 3, 4], text


def test_parse_ranking_on_stored_model_output():
    """Preflight 21: a parser of model output is tested on *stored* model output,
    not on the format the prompt asked for. The LLM reranker's replies live in the
    generation cache under `rerank_llm`; this skips until that run exists."""
    from rag.generation.cache import GENERATION_CACHE
    from rag.reranking.llm import parse_ranking

    if not GENERATION_CACHE.exists():
        pytest.skip("no generation cache on this machine")
    import sqlite3

    conn = sqlite3.connect(GENERATION_CACHE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT output FROM generations WHERE prompt_id = 'rerank_llm'"
    ).fetchall()
    conn.close()
    if not rows:
        pytest.skip("no LLM-reranker run recorded yet (P2-10 run 3)")
    unusable = [r["output"][:120] for r in rows if parse_ranking(r["output"], 50)["ranked"] == 0]
    assert unusable == [], (
        f"{len(unusable)} of {len(rows)} stored rerank replies parsed to no ordering at all: "
        f"{unusable[:3]}"
    )


# --- the whole path, through the runner ----------------------------------------

def test_a_recorded_rerank_run_carries_its_reranker_and_post_rerank_collapse():
    """The smoke run (configs/smoke_p2_10_rerank.yaml) proves the wiring: the row
    names the reranker, and the collapse ratio is the post-rerank one."""
    from rag.runner.store import DEFAULT_DB, ResultsStore

    if not DEFAULT_DB.exists():
        pytest.skip("no results store on this machine")
    with ResultsStore() as store:
        rows = [r for r in store.list_runs(200) if r["reranker"]]
        if not rows:
            pytest.skip("no rerank run recorded yet")
        row = rows[-1]
        metrics = json.loads(row["metrics_json"] or "{}")
        assert metrics["reranker"] == row["reranker"]
        assert metrics["collapse_ratio_mean"] is not None
        assert json.loads(row["reranker_meta"])["usage"]["calls"] == row["n_questions"]
