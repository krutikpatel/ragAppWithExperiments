"""P0-13 — the baseline retriever."""

from __future__ import annotations

from rag.retrieval.bm25 import BM25Retriever, tokenize

DOCS = {
    "c1": "Add a blog to your site from the dashboard.",
    "c2": "Payment verification may place a payout on hold.",
    "c3": "Connect a custom domain in Settings.",
    "c4": "Edit your site colors and fonts.",
    "c5": "Blog post settings and categories.",
}
MAP = {c: c.replace("c", "d") for c in DOCS}


def test_tokenizer_is_lowercase_alphanumeric_only():
    assert tokenize("Add a Blog, to YOUR site!") == ["add", "a", "blog", "to", "your", "site"]


def test_ranks_the_matching_chunk_first():
    ranked = BM25Retriever(MAP, DOCS).search("how do I add a blog", top_k=3)
    assert ranked[0][0] == "c1"
    assert all(score > 0 for _, score in ranked)


def test_returns_nothing_for_an_empty_query():
    assert BM25Retriever(MAP, DOCS).search("!!!", top_k=3) == []


def test_ranking_is_deterministic_across_instances():
    a = BM25Retriever(MAP, DOCS).search("blog settings", top_k=5)
    b = BM25Retriever(MAP, DOCS).search("blog settings", top_k=5)
    assert a == b


def test_retrieve_pools_to_documents():
    result = BM25Retriever(MAP, DOCS).retrieve("q1", "blog", top_k=5)
    assert result.doc_ids[:1] in (["d1"], ["d5"])
    assert result.doc_pooling == "max"
    assert result.meta["retriever"] == "bm25"


def test_params_are_recorded():
    params = BM25Retriever(MAP, DOCS, k1=1.2, b=0.5).params
    assert params["k1"] == 1.2 and params["b"] == 0.5 and "tokenizer" in params
