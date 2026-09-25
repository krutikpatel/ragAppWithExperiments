"""P2-12 — Axis 4: query transformation.

Four techniques with one shape: ask a model for new query strings, retrieve for each,
fuse by RRF. The tests are built around the three things that can silently ruin the
axis — a parser that drops what the model actually returned (MIS-016), a failed call
that voids a run (MIS-034), and a transform whose queries are not the ones the
technique is supposed to send.
"""

from __future__ import annotations

import pytest

from rag.generation.base import Completion
from rag.generation.cache import GenerationCache
from rag.generation.pipeline_llm import PipelineLLM
from rag.retrieval.base import Retriever
from rag.retrieval.query_transform import (
    QUERY_TRANSFORMS,
    Decompose,
    HyDE,
    MultiQuery,
    QueryTransform,
    StepBack,
    TransformingRetriever,
    build_transform,
    registered_transforms,
)
from rag.runner.config import QUERY_TRANSFORM_NAMES, RunConfig


def backend_returning(text: str):
    calls = []

    def backend(prompt_text: str) -> Completion:
        calls.append(prompt_text)
        return Completion(text=text, tokens_in=9, tokens_out=5, reasoning_tokens=0,
                          finish_reason="stop")

    return backend, calls


def make(cls_name: str, text: str, tmp_path, **params):
    backend, calls = backend_returning(text)
    cache = GenerationCache(tmp_path / f"{cls_name}.sqlite")
    llm = PipelineLLM("m/x", cache=cache, backend=backend)
    return build_transform(cls_name, llm, **params), calls, cache


# --- registry -------------------------------------------------------------------

def test_the_config_name_list_matches_the_registry():
    """`RunConfig` cannot import the transform module (cycle through the registry), so
    it carries the names literally. This is what stops that copy drifting."""
    assert tuple(registered_transforms()) == tuple(sorted(QUERY_TRANSFORM_NAMES))
    assert set(QUERY_TRANSFORMS) == set(QUERY_TRANSFORM_NAMES)


def test_unknown_transform_is_refused_by_config_and_builder(tmp_path):
    with pytest.raises(ValueError, match="unknown query_transform"):
        RunConfig(name="t", query_transform="rewrite_harder")
    with GenerationCache(tmp_path / "c.sqlite") as cache:
        with pytest.raises(KeyError, match="unknown query_transform"):
            build_transform("rewrite_harder", PipelineLLM("m/x", cache=cache, backend=lambda t: None))


def test_which_transforms_keep_the_original_question():
    """The table in the module docstring, asserted. `decompose` and `hyde` REPLACE the
    question: a decomposition that still retrieves for the whole question is not being
    tested, and HyDE's entire claim is that the fake answer is a better query."""
    assert Decompose.keeps_original is False
    assert HyDE.keeps_original is False
    assert MultiQuery.keeps_original is True
    assert StepBack.keeps_original is True


# --- parsing real-shaped model output --------------------------------------------

def test_decompose_splits_lines_and_honours_its_cap(tmp_path):
    out = "How do I connect a domain in Wix?\nHow do I set up Wix Payments?\nHow do I publish?"
    transform, _, cache = make("decompose", out, tmp_path, max_parts=2)
    with cache:
        expansion = transform.expand("How do I connect a domain and take payments?")
    assert expansion.queries == [
        "How do I connect a domain in Wix?", "How do I set up Wix Payments?",
    ]
    assert expansion.generated == 2 and not expansion.fell_back


def test_parser_strips_the_numbering_the_prompt_forbade(tmp_path):
    """MIS-016: parse what arrives, not the format the prompt asked for. Models
    number lists even when told not to, and a sub-query beginning '1.' would be
    embedded with the digit in it."""
    out = "1. How do I add a page?\n2) How do I rename a page?\n- How do I delete a page?"
    transform, _, cache = make("decompose", out, tmp_path, max_parts=5)
    with cache:
        expansion = transform.expand("pages")
    assert expansion.queries == [
        "How do I add a page?", "How do I rename a page?", "How do I delete a page?",
    ]


def test_decompose_returning_one_line_is_an_answer_not_a_fallback(tmp_path):
    """A question that needs no splitting comes back unchanged. That is the model
    doing as it was told, and must not be counted as a failure."""
    transform, _, cache = make("decompose", "How do I publish my site?", tmp_path)
    with cache:
        expansion = transform.expand("How do I publish my site?")
    assert expansion.queries == ["How do I publish my site?"]
    assert expansion.generated == 1 and expansion.fell_back is False
    assert transform.provenance()["fallback_rate"] == 0.0


def test_hyde_returns_one_query_and_truncates_on_words(tmp_path):
    passage = "To connect a domain:\n1. Open Settings.\n2. Click Domains. " + "extra " * 200
    transform, _, cache = make("hyde", passage, tmp_path, max_words=20)
    with cache:
        expansion = transform.expand("how do I connect a domain")
    assert len(expansion.queries) == 1, "HyDE sends one query: the hypothetical passage"
    assert len(expansion.queries[0].split()) == 20
    assert "how do I connect a domain" not in expansion.queries


def test_multi_query_keeps_the_original_and_drops_an_echo_of_it(tmp_path):
    """A rewrite identical to the original would double that ranking's RRF weight and
    quietly bias the fusion back towards the question."""
    question = "How do I change my domain?"
    out = f"{question}\nHow can I switch the web address of my Wix site?\nchange site url"
    transform, _, cache = make("multi_query", out, tmp_path, n=3)
    with cache:
        expansion = transform.expand(question)
    assert expansion.queries[0] == question
    assert expansion.queries.count(question) == 1
    assert expansion.generated == 2


def test_step_back_takes_exactly_one_general_question(tmp_path):
    out = "How does Wix Bookings handle payments?\nAnd another stray line."
    transform, _, cache = make("step_back", out, tmp_path)
    with cache:
        expansion = transform.expand("Why did my Wix Bookings payment fail with error 402?")
    assert expansion.queries == [
        "Why did my Wix Bookings payment fail with error 402?",
        "How does Wix Bookings handle payments?",
    ]


# --- failure is a per-question fact ------------------------------------------------

def test_a_failed_transform_call_falls_back_to_the_question(tmp_path):
    """MIS-034 / preflight 43. One bad completion out of 200 must not void a run, and
    retrieving for the untransformed question is exactly the control's behaviour."""
    def backend(prompt_text: str) -> Completion:
        raise RuntimeError("provider said no")

    with GenerationCache(tmp_path / "c.sqlite") as cache:
        transform = build_transform("decompose", PipelineLLM("m/x", cache=cache, backend=backend))
        expansion = transform.expand("How do I publish?")
    assert expansion.queries == ["How do I publish?"]
    assert expansion.fell_back and expansion.generated == 0
    prov = transform.provenance()
    assert prov["fallback_rate"] == 1.0
    assert "provider said no" in prov["failures"][0]["error"]


def test_an_empty_completion_falls_back_rather_than_retrieving_for_nothing(tmp_path):
    transform, _, cache = make("hyde", "   ", tmp_path)
    with cache:
        expansion = transform.expand("how do I connect a domain")
    assert expansion.queries == ["how do I connect a domain"]
    assert expansion.fell_back


# --- caching and prewarm -------------------------------------------------------------

def test_prewarm_makes_the_retrieval_loop_free(tmp_path):
    """MIS-036: 200 sequential round trips is 15+ minutes a run. Prewarm batches them,
    and every later `expand` must then hit the cache rather than the provider."""
    transform, calls, cache = make("step_back", "How does Wix Bookings work?", tmp_path)
    questions = [f"question {i}" for i in range(5)] + ["question 0"]
    with cache:
        transform.prewarm(questions, workers=4)
        assert len(calls) == 5, "the repeated question must be deduplicated before calling"
        for q in questions:
            transform.expand(q)
    assert len(calls) == 5, "expand after prewarm must not call the provider"
    assert transform.stats["questions"] == 6


def test_the_cache_key_is_the_question_text(tmp_path):
    """Keyed on the text, not the question id, so identical questions share one
    completion and the key survives a change of split or subsample."""
    a = QueryTransform.cache_id("How do I publish my site?")
    b = QueryTransform.cache_id("How do I publish my site?")
    c = QueryTransform.cache_id("How do I unpublish my site?")
    assert a == b != c and a.startswith("qt:")


# --- the retriever wrapper -----------------------------------------------------------

class FakeRetriever(Retriever):
    """Returns a ranking per query, from a fixed table."""

    name = "fake"

    def __init__(self, chunk_to_doc, rankings):
        super().__init__(chunk_to_doc)
        self.rankings = rankings
        self.seen: list[str] = []

    def search(self, query: str, *, top_k: int):
        self.seen.append(query)
        return self.rankings.get(query, [])[:top_k]


def test_transforming_retriever_fuses_every_sub_query(tmp_path):
    chunk_to_doc = {"c1": "d1", "c2": "d2", "c3": "d3"}
    rankings = {
        "sub one": [("c1", 0.9), ("c2", 0.5)],
        "sub two": [("c3", 0.8), ("c1", 0.4)],
    }
    transform, _, cache = make("decompose", "sub one\nsub two", tmp_path)
    with cache:
        base = FakeRetriever(chunk_to_doc, rankings)
        wrapped = TransformingRetriever(base, transform)
        fused = wrapped.search("original question", top_k=10)
    assert base.seen == ["sub one", "sub two"], "the original must NOT be searched for"
    # c1 appears in both lists, so RRF ranks it first.
    assert fused[0][0] == "c1"
    assert {cid for cid, _ in fused} == {"c1", "c2", "c3"}


def test_transforming_retriever_records_distinct_document_yield(tmp_path):
    """P2-12 asks for the distinct-document yield per sub-query: how many documents
    each query found that no earlier one had."""
    chunk_to_doc = {"c1": "d1", "c2": "d2", "c3": "d3"}
    rankings = {
        "sub one": [("c1", 0.9), ("c2", 0.5)],   # d1, d2 -> 2 new
        "sub two": [("c2", 0.8), ("c3", 0.4)],   # d2 seen, d3 new -> 1 new
    }
    transform, _, cache = make("decompose", "sub one\nsub two", tmp_path)
    with cache:
        wrapped = TransformingRetriever(FakeRetriever(chunk_to_doc, rankings), transform)
        wrapped.search("original question", top_k=10)
    record = wrapped.per_question["original question"]
    assert record["distinct_doc_yield_per_query"] == [2, 1]
    assert record["distinct_docs_total"] == 3
    assert record["mean_new_docs_after_first"] == 1.0
    assert record["n_queries"] == 2 and record["n_generated"] == 2


def test_the_wrapper_keeps_the_base_retrievers_pooling_and_walk(tmp_path):
    """The wrapper is a Retriever, so the document walk and the collapse ratio are the
    base class's and behave exactly as they do for the control."""
    chunk_to_doc = {"c1": "d1", "c2": "d1", "c3": "d2"}
    rankings = {"q": [("c1", 0.9), ("c2", 0.8), ("c3", 0.7)]}
    transform, _, cache = make("step_back", "", tmp_path)   # empty -> falls back to "q"
    with cache:
        wrapped = TransformingRetriever(FakeRetriever(chunk_to_doc, rankings), transform)
        result = wrapped.retrieve("q1", "q", top_k=10, k_docs=2, candidate_pool=10)
    assert result.context is not None
    assert result.context.doc_ids == ["d1", "d2"]
    assert result.context.collapse_ratio == pytest.approx(1.5)


def test_single_query_expansion_skips_fusion_entirely(tmp_path):
    """HyDE sends one query, so there is nothing to fuse and the base ranking must
    pass through unchanged — including its scores, which RRF would have discarded."""
    chunk_to_doc = {"c1": "d1", "c2": "d2"}
    transform, _, cache = make("hyde", "a hypothetical passage", tmp_path)
    with cache:
        base = FakeRetriever(chunk_to_doc, {"a hypothetical passage": [("c1", 0.9), ("c2", 0.5)]})
        fused = TransformingRetriever(base, transform).search("real question", top_k=10)
    assert fused == [("c1", 0.9), ("c2", 0.5)]


def test_the_wrapper_exposes_its_llm_so_the_run_is_marked_nondeterministic(tmp_path):
    transform, _, cache = make("hyde", "passage", tmp_path)
    with cache:
        wrapped = TransformingRetriever(FakeRetriever({}, {}), transform)
        assert wrapped.pipeline_llm is transform.llm
        prov = wrapped.provenance()
    assert prov["query_transform"]["query_transform"] == "hyde"
    assert prov["query_transform"]["prompt"] == "query_hyde@v1"


# --- config and cost -------------------------------------------------------------------

def test_query_transform_is_tier_1_identity_unlike_the_axis_6_fields():
    """A query transform changes what is RETRIEVED, so it must move a Tier 1 identity.
    Axis 6's assembly fields must not. This is the line between the two axes."""
    assert "query_transform" in RunConfig.TIER1_FIELDS
    assert "context_order" not in RunConfig.TIER1_FIELDS
    control = RunConfig(name="c")
    transformed = RunConfig(name="t", query_transform="decompose",
                            query_transform_params={"model": "m/x"})
    assert control.identity_hash != transformed.identity_hash


def test_absent_transform_moved_no_historical_hash():
    from rag.runner.promoted import load_promoted

    assert load_promoted().config_hash == "7c99bc8e9a88e878"


def test_query_transform_is_one_dimension_against_promoted():
    from rag.runner.promoted import config_diff, load_promoted

    promoted = load_promoted()
    config = promoted.with_(name="x", axis="query_transform", query_transform="decompose",
                            query_transform_params={"model": "openai/gpt-oss-20b"})
    diff = config_diff(config, promoted)
    assert diff["dimensions"] == ["query_transform"], diff
    assert diff["one_dimension"]


def test_transform_cost_scales_with_the_split_not_the_corpus():
    """Billed per query like reranking (MIS-028's lesson, applied before the fact):
    the same config is cents on dev and dollars on dev_large."""
    from rag.runner.cost import PricingTable, estimate_query_transform_cost

    pricing = PricingTable.load()
    kwargs = dict(
        query_transform="decompose", transform_params={"model": "openai/gpt-oss-20b"},
        prompt_overhead_words=120, question_words=20, output_words=60,
        queries_per_question=2.5, pricing=pricing,
    )
    dev = estimate_query_transform_cost(n_questions=200, **kwargs)
    dev_large = estimate_query_transform_cost(n_questions=6221, **kwargs)
    assert dev["calls"] == 200 and dev_large["calls"] == 6221
    assert dev_large["query_transform_usd"] > 30 * dev["query_transform_usd"]
    # 1.5 extra queries per question, each an extra embedding call.
    assert dev["extra_query_embeddings"] == 300


def test_transform_cost_without_a_model_is_unavailable_not_free():
    from rag.runner.cost import PricingTable, estimate_query_transform_cost

    estimate = estimate_query_transform_cost(
        query_transform="hyde", transform_params={}, n_questions=10,
        prompt_overhead_words=10, question_words=10, output_words=10,
        queries_per_question=1.0, pricing=PricingTable.load(),
    )
    assert "query_transform_usd" not in estimate
    assert "no model" in estimate["price_unavailable"]


def test_run_estimate_gates_on_the_transform():
    from rag.runner.cost import estimate_run_cost

    blocked = estimate_run_cost(
        tier2=None, index={"index_usd": 0.0, "query_usd": 0.0},
        query_transform={"price_unavailable": "query_transform 'hyde' has no model"},
    )
    assert blocked["over_gate"] and blocked["unavailable"]
    priced = estimate_run_cost(
        tier2=None, index={"index_usd": 0.0, "query_usd": 0.0001},
        query_transform={"query_transform_usd": 0.01},
    )
    assert priced["parts_usd"]["query_transform"] == 0.01
