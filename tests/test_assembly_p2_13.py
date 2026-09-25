"""P2-13 — Axis 6: context assembly.

Three techniques, and the tests are shaped by what each one is allowed to move.

Ordering and compression act *after* the document walk, so no test here may show
them changing a retrieval number — and one test proves reordering cannot, by
asserting it returns a permutation of its input. Contextual retrieval is the
opposite: it changes the indexed text and nothing else, so its tests assert the
generator still sees the original chunk.
"""

from __future__ import annotations

import json

import pytest

from rag.assembly import (
    COMPRESSORS,
    CONTEXT_ORDERS,
    EMPTY_MARKER,
    ConcatAssembler,
    ContextCompressor,
    build_compressor,
    order_chunks,
    reorder_lost_in_middle,
)
from rag.generation.base import Completion
from rag.generation.cache import GenerationCache
from rag.generation.pipeline_llm import PipelineLLM
from rag.retrieval.base import ScoredChunk
from rag.runner.config import EvalTier, RunConfig


def chunks(n: int) -> list[ScoredChunk]:
    return [ScoredChunk(chunk_id=f"c{i}", doc_id=f"d{i}", score=1.0 - i / 100) for i in range(n)]


def fixed_backend(text: str):
    calls = []

    def backend(prompt_text: str) -> Completion:
        calls.append(prompt_text)
        return Completion(text=text, tokens_in=7, tokens_out=3, reasoning_tokens=0,
                          finish_reason="stop")

    return backend, calls


# --- lost-in-the-middle reordering ---------------------------------------------

def test_reordering_is_a_permutation_so_it_cannot_change_retrieval():
    """The reason P2-13 forbids reporting retrieval deltas for this technique. Same
    chunks, same documents, same count — only the position in the prompt moves."""
    for n in range(0, 12):
        original = chunks(n)
        reordered = reorder_lost_in_middle(original)
        assert sorted(c.chunk_id for c in reordered) == sorted(c.chunk_id for c in original)
        assert len(reordered) == n


def test_reordering_puts_the_best_at_both_ends_and_the_worst_in_the_middle():
    order = [c.chunk_id for c in reorder_lost_in_middle(chunks(5))]
    assert order == ["c0", "c2", "c4", "c3", "c1"]
    # Rank 0 opens, rank 1 closes, and the weakest candidate (c4) is interior.
    assert order[0] == "c0" and order[-1] == "c1"
    assert order.index("c4") not in (0, len(order) - 1)


def test_reordering_degenerate_lengths():
    assert reorder_lost_in_middle([]) == []
    assert [c.chunk_id for c in reorder_lost_in_middle(chunks(1))] == ["c0"]
    assert [c.chunk_id for c in reorder_lost_in_middle(chunks(2))] == ["c0", "c1"]


def test_rank_order_is_the_identity_and_unknown_orders_are_refused():
    original = chunks(4)
    assert [c.chunk_id for c in order_chunks(original, "rank")] == ["c0", "c1", "c2", "c3"]
    with pytest.raises(ValueError, match="unknown context_order"):
        order_chunks(original, "middle_out")


# --- assembly ------------------------------------------------------------------

def test_assembler_records_order_and_word_counts():
    text = {f"c{i}": " ".join(["word"] * 10) for i in range(3)}
    result = ConcatAssembler(max_tokens=100, order="lost_in_middle").assemble(chunks(3), text)
    assert result.meta["order"] == "lost_in_middle"
    assert result.meta["doc_order"] == ["d0", "d2", "d1"]
    assert result.meta["words_in"] == 30 and result.meta["words_out"] == 30
    assert result.n_chunks == 3 and not result.truncated


def test_assembler_truncates_in_the_reordered_sequence_not_the_ranked_one():
    """Ordering happens before the budget walk. Reordering and then truncating is
    the technique; truncating and then reordering the survivors is a different one,
    and the difference shows up exactly here."""
    text = {f"c{i}": " ".join([f"w{i}"] * 10) for i in range(4)}
    result = ConcatAssembler(max_tokens=20, order="lost_in_middle").assemble(chunks(4), text)
    assert result.truncated
    # lost_in_middle order is c0, c2, c3, c1 — so the budget keeps c0 and c2, and
    # the RANK-order walk would have kept c0 and c1 instead.
    assert result.doc_ids == ["d0", "d2"]
    assert result.meta["words_in"] == 40 and result.meta["words_out"] == 20


def test_assembler_default_order_is_the_control():
    text = {f"c{i}": "a b c" for i in range(3)}
    result = ConcatAssembler(max_tokens=100).assemble(chunks(3), text)
    assert result.meta["doc_order"] == ["d0", "d1", "d2"]


def test_assembler_refuses_an_unknown_order_at_construction():
    with pytest.raises(ValueError, match="unknown context_order"):
        ConcatAssembler(max_tokens=10, order="nope")


# --- contextual compression ----------------------------------------------------

def test_compressor_keeps_only_what_the_model_returned(tmp_path):
    passage = "Open Settings. Click Domains. Then click Save. Unrelated billing text here."
    backend, calls = fixed_backend("Click Domains. Then click Save.")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        llm = PipelineLLM("m/x", cache=cache, backend=backend)
        compressor = ContextCompressor(llm)
        out = compressor.compress(
            question_id="q1", question="How do I set a domain?",
            chunks=chunks(1), chunk_text={"c0": passage},
        )
    assert len(calls) == 1
    assert out.chunk_text["c0"] == "Click Domains. Then click Save."
    assert compressor.stats["words_in"] == 11 and compressor.stats["words_out"] == 5
    assert compressor.provenance()["word_reduction"] == pytest.approx(1 - 5 / 11, abs=1e-4)


def test_compressor_drops_a_chunk_the_model_emptied(tmp_path):
    backend, _ = fixed_backend(EMPTY_MARKER)
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        compressor = ContextCompressor(PipelineLLM("m/x", cache=cache, backend=backend))
        out = compressor.compress(
            question_id="q1", question="Q", chunks=chunks(2),
            chunk_text={"c0": "a b c", "c1": "d e f"},
        )
    assert out.chunks == [] and out.chunk_text == {}
    assert compressor.stats["chunks_dropped"] == 2
    assert out.stats == {"question_id": "q1", "chunks_in": 2, "chunks_out": 0}


def test_compressor_keeps_a_rewritten_chunk_uncompressed_and_counts_it(tmp_path):
    """The prompt forbids rewriting. A rewrite that slipped through must not reach
    the generator, because faithfulness would then be scored against text retrieval
    never returned — so the original is kept and the disobedience is counted."""
    passage = "Open Settings. Click Domains."
    backend, _ = fixed_backend("You should navigate to the domain settings page.")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        compressor = ContextCompressor(PipelineLLM("m/x", cache=cache, backend=backend))
        out = compressor.compress(
            question_id="q1", question="Q", chunks=chunks(1), chunk_text={"c0": passage},
        )
    assert out.chunk_text["c0"] == passage
    assert compressor.stats["chunks_kept_verbatim_check_failed"] == 1


def test_compressor_min_keep_ratio_restores_an_over_trimmed_chunk(tmp_path):
    passage = " ".join(["word"] * 20)
    backend, _ = fixed_backend("word word word")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        compressor = ContextCompressor(
            PipelineLLM("m/x", cache=cache, backend=backend), min_keep_ratio=0.5
        )
        out = compressor.compress(
            question_id="q1", question="Q", chunks=chunks(1), chunk_text={"c0": passage},
        )
    assert out.chunk_text["c0"] == passage


def test_compressor_caches_per_chunk_not_per_question(tmp_path):
    """Two chunks of one question must not share a cache entry, or every chunk after
    the first would replay the first one's compression. The second run of the same
    config is then free, which is what keeps the judged comparison valid (P2-03)."""
    text = {"c0": "alpha beta gamma", "c1": "delta epsilon zeta"}
    backend, calls = fixed_backend("alpha beta gamma")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        first = ContextCompressor(PipelineLLM("m/x", cache=cache, backend=backend))
        first.compress(question_id="q1", question="Q", chunks=chunks(2), chunk_text=text)
        assert len(calls) == 2, "two chunks must produce two distinct cache keys"

        second = ContextCompressor(PipelineLLM("m/x", cache=cache, backend=backend))
        second.compress(question_id="q1", question="Q", chunks=chunks(2), chunk_text=text)
    assert len(calls) == 2, "the repeat must replay from cache, not call again"
    assert second.llm.stats()["hit_rate"] == 1.0


def test_extractive_check_ignores_layout_but_not_content():
    passage = "Open  Settings.\nClick Domains."
    assert ContextCompressor._is_extractive("Open Settings.", passage)
    assert ContextCompressor._is_extractive("Open Settings. Click Domains.", passage)
    # Short fragments are skipped rather than judged; a model that returns "Save."
    # has not invented anything, it has over-trimmed, which min_keep_ratio handles.
    assert ContextCompressor._is_extractive("Save.", passage)
    assert not ContextCompressor._is_extractive("Navigate to the domain settings.", passage)


def test_build_compressor_refuses_an_unknown_name(tmp_path):
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        llm = PipelineLLM("m/x", cache=cache, backend=fixed_backend("x")[0])
        assert build_compressor("llm_extract", llm).name == "llm_extract"
        with pytest.raises(KeyError, match="unknown context_compressor"):
            build_compressor("magic", llm)
    assert COMPRESSORS == ("llm_extract",)


# --- config ---------------------------------------------------------------------

def test_axis_6_fields_are_refused_at_tier_1():
    """A Tier 1 run carrying either field would record a number identical to the
    control's under a different config name — the worst kind of false finding."""
    with pytest.raises(ValueError, match="only change what the GENERATOR sees"):
        RunConfig(name="t", context_order="lost_in_middle")
    with pytest.raises(ValueError, match="only change what the GENERATOR sees"):
        RunConfig(name="t", context_compressor="llm_extract")


def test_unknown_axis_6_values_are_refused():
    with pytest.raises(ValueError, match="unknown context_order"):
        RunConfig(name="t", context_order="sideways")
    tier2 = dict(
        eval_tier=EvalTier.TIER_2, generator_model="openai/gpt-5-nano",
        judge_model="openai/gpt-oss-120b",
    )
    with pytest.raises(ValueError, match="unknown context_compressor"):
        RunConfig(name="t", context_compressor="squeeze", **tier2)
    assert CONTEXT_ORDERS == ("rank", "lost_in_middle")


def test_the_three_new_fields_moved_no_historical_hash():
    """MIS-019: a new field with a default moves every config_hash in the ledger,
    including the controls'. An axis at its off value is an absent dimension."""
    from rag.runner.promoted import load_promoted

    assert load_promoted().config_hash == "7c99bc8e9a88e878"


def test_axis_6_fields_are_not_tier_1_identity():
    """The mechanical guarantee that assembly cannot change a retrieval number: the
    fields are absent from TIER1_FIELDS, so a Tier 1 run's identity cannot see them."""
    assert "context_order" not in RunConfig.TIER1_FIELDS
    assert "context_compressor" not in RunConfig.TIER1_FIELDS
    tier2 = dict(
        eval_tier=EvalTier.TIER_2, generator_model="openai/gpt-5-nano",
        judge_model="openai/gpt-oss-120b",
    )
    control = RunConfig(name="c", **tier2)
    reordered = RunConfig(name="r", context_order="lost_in_middle", **tier2)
    assert control.config_hash != reordered.config_hash
    assert control.identity_hash != reordered.identity_hash


def test_assembly_is_one_dimension_against_the_tier_2_control():
    """One dimension, measured against the control these runs actually compare to.

    `promoted.yaml` is a Tier 1 config with no generator and no judge, so *any* Tier 2
    experiment differs from it on the generation dimension as well as its own. Axis 6
    is the first Tier 2 axis, so it is the first to meet that; the runner's
    `one_dimension` warning against promoted.yaml is therefore expected on these runs
    and is about the tier, not about the change under test (OQ-042).
    """
    from rag.runner.config import load_config_file
    from rag.runner.promoted import config_diff

    control = load_config_file("configs/baseline_dense_tier2.yaml")
    config = control.with_(name="x", axis="assembly", context_order="lost_in_middle")
    diff = config_diff(config, control)
    assert diff["dimensions"] == ["assembly"], diff
    assert diff["one_dimension"]


def test_a_tier_2_experiment_differs_from_promoted_on_the_tier_not_the_axis():
    """Pins the behaviour the test above describes, so that if the promotion rule is
    ever changed to know about tiers, this test is what fails and says so."""
    from rag.runner.promoted import config_diff, load_promoted

    promoted = load_promoted()
    config = promoted.with_(
        name="x", axis="assembly", eval_tier=EvalTier.TIER_2,
        generator_model="openai/gpt-5-nano", judge_model="openai/gpt-oss-120b",
        context_order="lost_in_middle",
    )
    diff = config_diff(config, promoted)
    assert diff["dimensions"] == ["assembly", "generation"], diff
    assert not diff["one_dimension"]


# --- contextual retrieval (the chunker) -----------------------------------------

def test_contextual_chunker_prefixes_the_index_and_not_the_generator(tmp_path):
    """The one-dimension property of this technique: `text` (indexed) carries the
    generated prefix, `context` (what the generator sees) is the original chunk."""
    from rag.chunking.contextual import ContextualChunker

    backend, calls = fixed_backend("This chunk is from an article about domains.")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        chunker = ContextualChunker(
            chunk_size=10, overlap=0,
            llm=PipelineLLM("m/x", cache=cache, backend=backend),
        )
        out = chunker.split("doc1", " ".join(f"w{i}" for i in range(25)))

    assert len(out) == 3 and len(calls) == 3
    for chunk in out:
        assert chunk.text.startswith("This chunk is from an article about domains.\n\n")
        assert chunk.context == chunk.text.split("\n\n", 1)[1]
        assert not chunk.context.startswith("This chunk")
    assert chunker.stats["prefixes_generated"] == 3
    assert chunker.provenance()["mean_prefix_words"] == 8.0


def test_contextual_chunker_keeps_the_controls_boundaries(tmp_path):
    """The comparison isolates the prefix. If this chunker also moved the chunk
    boundaries it would be two changes at once and not an Axis 6 experiment."""
    from rag.chunking.base import FixedTokenChunker
    from rag.chunking.contextual import ContextualChunker

    text = " ".join(f"w{i}" for i in range(1400))
    control = FixedTokenChunker(chunk_size=600, overlap=100).split("doc1", text)
    backend, _ = fixed_backend("ctx")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        chunker = ContextualChunker(llm=PipelineLLM("m/x", cache=cache, backend=backend))
        out = chunker.split("doc1", text)
    assert len(out) == len(control)
    assert [c.context for c in out] == [c.text for c in control]


def test_contextual_chunker_records_an_empty_prefix_rather_than_raising(tmp_path):
    from rag.chunking.contextual import ContextualChunker

    backend, _ = fixed_backend("   ")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        chunker = ContextualChunker(
            chunk_size=10, overlap=0, llm=PipelineLLM("m/x", cache=cache, backend=backend)
        )
        out = chunker.split("doc1", " ".join(f"w{i}" for i in range(15)))
    assert chunker.stats["prefixes_empty"] == 2
    assert chunker.provenance()["mean_prefix_words"] is None
    # The chunk still indexes as the control's chunk; nothing is lost.
    assert all(c.context_text is None for c in out)


def test_contextual_chunker_workload_is_counted_not_guessed(tmp_path):
    """The gate has to fire before the first call, so the estimate comes from a free
    split of the real corpus text: one call per chunk, each resending its document."""
    from rag.chunking.contextual import ContextualChunker

    backend, calls = fixed_backend("ctx")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        chunker = ContextualChunker(
            chunk_size=10, overlap=0, llm=PipelineLLM("m/x", cache=cache, backend=backend)
        )
        docs = {"d1": " ".join(["w"] * 25), "d2": " ".join(["w"] * 5)}
        workload = chunker.llm_workload(docs)
    assert calls == [], "estimating the workload must not call the model"
    assert workload["calls"] == 4  # 3 chunks + 1 chunk
    assert workload["model"] == "m/x" and workload["prompt_caching"] is False
    assert workload["indexed_words"] == 30 + 4 * chunker.context_max_words
    assert workload["tokens_in"] > 0 and workload["tokens_out"] > 0


def test_contextual_chunker_rebuild_is_free(tmp_path):
    """One LLM call per chunk is only affordable because it is cached (DEC-049).
    A second build of the same chunks must not call the model at all."""
    from rag.chunking.contextual import ContextualChunker

    backend, calls = fixed_backend("ctx")
    text = " ".join(f"w{i}" for i in range(25))
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        first = ContextualChunker(
            chunk_size=10, overlap=0, llm=PipelineLLM("m/x", cache=cache, backend=backend)
        )
        a = first.split("doc1", text)
        assert len(calls) == 3

        second = ContextualChunker(
            chunk_size=10, overlap=0, llm=PipelineLLM("m/x", cache=cache, backend=backend)
        )
        b = second.split("doc1", text)
    assert len(calls) == 3, "the rebuild must replay from cache"
    assert [c.text for c in a] == [c.text for c in b]
    assert second.llm.stats()["hit_rate"] == 1.0


def test_contextual_chunker_refuses_to_build_without_a_cache_or_a_model():
    from rag.chunking.contextual import ContextualChunker

    with pytest.raises(ValueError, match="needs the generation cache"):
        ContextualChunker(context_model="m/x")
    with pytest.raises(ValueError, match="model choice is Krutik"):
        ContextualChunker(generation_cache=object())


def test_only_chunkers_that_asked_for_it_get_the_generation_cache(tmp_path):
    from rag.chunking.base import build_chunker, chunker_class

    assert chunker_class("contextual").needs_generation_cache is True
    assert chunker_class("fixed_token").needs_generation_cache is False
    # The control chunker's signature knows nothing about a cache and must not have
    # to: passing one anyway is not an error, it is simply not forwarded.
    assert build_chunker("fixed_token", generation_cache=object(), chunk_size=600, overlap=100)
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        built = build_chunker("contextual", generation_cache=cache, context_model="m/x")
    assert built.llm.model == "m/x"


def test_contextual_chunker_identity_covers_the_prompt_and_the_model(tmp_path):
    """The index on disk was built by a specific prompt and a specific model. If
    either were outside `chunker_id`, a prompt bump would silently reuse the old
    index — the most expensive version-skew available in this project."""
    from rag.chunking.contextual import ContextualChunker

    with GenerationCache(tmp_path / "c.sqlite") as cache:
        a = ContextualChunker(llm=PipelineLLM("m/x", cache=cache, backend=fixed_backend("c")[0]))
        b = ContextualChunker(llm=PipelineLLM("m/y", cache=cache, backend=fixed_backend("c")[0]))
    assert a.chunker_id != b.chunker_id
    assert a.params["prefix"] == "contextual_chunk@v1"
    assert a.params["prefix_hash"].startswith("sha256:")
    assert a.params["context_model"] == "m/x"


# --- cost -------------------------------------------------------------------------

def test_chunker_llm_estimate_prices_both_directions():
    from rag.runner.cost import PricingTable, estimate_chunker_llm_cost

    pricing = PricingTable.load()
    assert estimate_chunker_llm_cost(None, pricing=pricing) == {}
    estimate = estimate_chunker_llm_cost(
        {"calls": 100, "tokens_in": 1_000_000, "tokens_out": 100_000,
         "model": "openai/gpt-5-nano", "prompt_caching": False},
        pricing=pricing,
    )
    # $0.05/Mtok in, $0.40/Mtok out (configs/pricing.yaml).
    assert estimate["chunker_llm_usd"] == pytest.approx(0.05 + 0.04, abs=1e-6)
    assert "counted from a free split" in estimate["source"]


def test_chunker_llm_estimate_never_reads_an_absent_price_as_free():
    from rag.runner.cost import PricingTable, estimate_chunker_llm_cost

    estimate = estimate_chunker_llm_cost(
        {"calls": 1, "tokens_in": 1, "tokens_out": 1, "model": "nobody/nothing"},
        pricing=PricingTable.load(),
    )
    assert "chunker_llm_usd" not in estimate
    assert "no chat price" in estimate["price_unavailable"]


def test_compression_estimate_scales_with_the_split_and_top_k():
    from rag.runner.cost import PricingTable, estimate_compression_cost

    pricing = PricingTable.load()
    assert estimate_compression_cost(
        compressor="", compressor_params={}, n_questions=100,
        chunks_per_question=5, chunk_words=348, pricing=pricing,
    ) == {}
    small = estimate_compression_cost(
        compressor="llm_extract", compressor_params={"model": "openai/gpt-5-nano"},
        n_questions=100, chunks_per_question=5, chunk_words=348, pricing=pricing,
    )
    big = estimate_compression_cost(
        compressor="llm_extract", compressor_params={"model": "openai/gpt-5-nano"},
        n_questions=200, chunks_per_question=5, chunk_words=348, pricing=pricing,
    )
    assert small["calls"] == 500 and big["calls"] == 1000
    # Rounded to 4dp on the way out, so the doubling is exact only to that precision.
    assert big["compression_usd"] == pytest.approx(2 * small["compression_usd"], abs=1e-4)
    assert "upper bound" in small["output_basis"]


def test_compression_estimate_without_a_model_is_unavailable_not_free():
    from rag.runner.cost import PricingTable, estimate_compression_cost

    estimate = estimate_compression_cost(
        compressor="llm_extract", compressor_params={}, n_questions=10,
        chunks_per_question=5, chunk_words=100, pricing=PricingTable.load(),
    )
    assert "compression_usd" not in estimate
    assert "no model" in estimate["price_unavailable"]


def test_run_estimate_surfaces_the_new_parts_and_gates_on_them():
    from rag.runner.cost import COST_GATE_USD, estimate_run_cost

    estimate = estimate_run_cost(
        tier2=None,
        index={"index_usd": 0.0, "query_usd": 0.0001},
        chunker_llm={"chunker_llm_usd": 0.69},
        compression={"compression_usd": 0.10},
    )
    assert estimate["parts_usd"]["chunker_llm"] == 0.69
    assert estimate["parts_usd"]["compression"] == 0.10
    assert estimate["driver"] == "chunker_llm"
    assert estimate["total_usd"] == pytest.approx(0.7901, abs=1e-4)
    assert not estimate["over_gate"] and estimate["total_usd"] < COST_GATE_USD

    blocked = estimate_run_cost(
        tier2=None, index={"index_usd": 0.0, "query_usd": 0.0},
        chunker_llm={"price_unavailable": "no chat price for nobody/nothing"},
    )
    assert blocked["over_gate"] and blocked["unavailable"]


def test_two_pipeline_llms_are_priced_with_their_own_models():
    """Summing tokens across models first would charge one model's rate for the
    other's tokens. A run can hold two call sites since P2-13."""
    from rag.runner.cost import PricingTable, actual_run_cost

    pricing = PricingTable.load()
    one = actual_run_cost(
        retriever_meta={}, generator_tokens_in=0, generator_tokens_out=0,
        generator_model="openai/gpt-5-nano", judge_estimate_usd=None,
        pipeline_llm_stats={"model": "openai/gpt-5-nano", "tokens_in": 1_000_000, "tokens_out": 0},
        pricing=pricing,
    )
    two = actual_run_cost(
        retriever_meta={}, generator_tokens_in=0, generator_tokens_out=0,
        generator_model="openai/gpt-5-nano", judge_estimate_usd=None,
        pipeline_llm_stats=[
            {"model": "openai/gpt-5-nano", "tokens_in": 1_000_000, "tokens_out": 0},
            {"model": "openai/gpt-5-nano", "tokens_in": 1_000_000, "tokens_out": 0},
        ],
        pricing=pricing,
    )
    assert one["parts_usd"]["pipeline_llm"] == pytest.approx(0.05, abs=1e-6)
    assert two["parts_usd"]["pipeline_llm"] == pytest.approx(0.10, abs=1e-6)


def test_merged_pipeline_stats_keep_both_models_visible():
    from rag.runner.run import _merge_pipeline_stats

    a = {"model": "m/a", "temperature": 0.0, "calls": 4, "cache_hits": 4, "cache_misses": 0,
         "tokens_in": 10, "tokens_out": 2, "prompts": ["p@v1"]}
    b = {**a, "model": "m/b", "calls": 6, "cache_hits": 3, "cache_misses": 3,
         "prompts": ["q@v1"]}
    assert _merge_pipeline_stats([a]) is a
    merged = _merge_pipeline_stats([a, b])
    assert merged["model"] == ["m/a", "m/b"]
    assert merged["calls"] == 10 and merged["cache_hits"] == 7
    assert merged["hit_rate"] == pytest.approx(0.7)
    assert merged["prompts"] == ["p@v1", "q@v1"] and merged["sources"] == 2


# --- the parser, on stored model output (preflight 21) --------------------------

def test_extractive_check_on_real_compression_output():
    """Preflight 21: test every parser of model output on stored model output, not
    on the format the prompt asked for. Skips until a compression run exists."""
    from rag.paths import GENERATION_CACHE

    if not GENERATION_CACHE.exists():
        pytest.skip("no generation cache on this machine")
    import sqlite3

    conn = sqlite3.connect(GENERATION_CACHE)
    rows = conn.execute(
        "SELECT output FROM generations WHERE prompt_id = 'compress_context'"
    ).fetchall()
    conn.close()
    if not rows:
        pytest.skip("no compress_context completions recorded yet")
    # What we can assert without the passages: the marker is never embedded in an
    # otherwise substantive answer, which would make a dropped chunk ambiguous.
    for (output,) in rows:
        if EMPTY_MARKER in output:
            assert len(output.split()) < 5, f"marker buried in prose: {output[:120]!r}"


# --- DEC-063: Tier 2 without the judge -----------------------------------------

def test_skip_judge_needs_a_generator_but_not_a_judge():
    config = RunConfig(
        name="t", eval_tier=EvalTier.TIER_2, generator_model="openai/gpt-5-nano",
        skip_judge=True,
    )
    assert config.skip_judge and config.judge_model == ""
    # The generator is still required: no generator means no answers, and the
    # deterministic generation metrics are computed from answers.
    with pytest.raises(ValueError, match="generator_model"):
        RunConfig(name="t", eval_tier=EvalTier.TIER_2, skip_judge=True)


def test_an_omitted_judge_is_still_an_error_without_the_flag():
    """The flag exists so that a typo cannot silently turn a $0.91 run into a $0.03
    one that looks judged in the ledger."""
    with pytest.raises(ValueError, match="judge_model"):
        RunConfig(name="t", eval_tier=EvalTier.TIER_2, generator_model="openai/gpt-5-nano")


def test_skip_judge_and_a_judge_model_together_are_refused():
    with pytest.raises(ValueError, match="skip_judge is set but judge_model"):
        RunConfig(
            name="t", eval_tier=EvalTier.TIER_2, generator_model="openai/gpt-5-nano",
            judge_model="openai/gpt-oss-120b", skip_judge=True,
        )


def test_skip_judge_does_not_move_a_hash_when_it_is_off():
    from rag.runner.promoted import load_promoted

    assert load_promoted().config_hash == "7c99bc8e9a88e878"
    assert "skip_judge" not in RunConfig.TIER1_FIELDS


def test_skip_judge_zeroes_the_judge_half_of_the_estimate():
    import pandas as pd

    from rag.runner.cost import PricingTable
    from rag.runner.run import _cost_estimate

    pricing = PricingTable.load()
    frame = pd.DataFrame({"answer": ["a reference answer"] * 100})
    judged = _cost_estimate(
        RunConfig(name="t", eval_tier=EvalTier.TIER_2, generator_model="openai/gpt-5-nano",
                  judge_model="openai/gpt-oss-120b"),
        frame, pricing,
    )
    unjudged = _cost_estimate(
        RunConfig(name="t", eval_tier=EvalTier.TIER_2, generator_model="openai/gpt-5-nano",
                  skip_judge=True),
        frame, pricing,
    )
    assert judged["n_judged"] == 100 and unjudged["n_judged"] == 0
    assert judged["judge_usd"] > 0.5
    assert unjudged["judge_usd"] == 0.0
    # The generator is unchanged: the same answers are still generated and still
    # scored by the deterministic metrics.
    assert unjudged["generator_usd"] == judged["generator_usd"]
