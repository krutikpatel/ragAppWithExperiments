"""P2-09 — hybrid retrieval: RRF and weighted score fusion over dense + BM25."""

from __future__ import annotations

import pytest

from rag.chunking.base import FixedTokenChunker
from rag.chunking.index_map import ChunkIndex
from rag.embedding.base import EmbedderConfig
from rag.retrieval.hybrid import HybridRetriever, minmax_normalize, rrf_fuse, weighted_fuse
from rag.runner.registry import build_retriever, registered_retrievers, retriever_class
from tests.test_embedding import DOCS, FakeEmbedder

CORPUS_HASH = "sha256:" + "b" * 64


# --- the fusion rules, on hand-built rankings ------------------------------------

def test_rrf_sums_reciprocal_ranks_and_breaks_ties_on_chunk_id():
    a = [("x", 9.0), ("y", 8.0), ("z", 1.0)]
    b = [("y", 0.9), ("w", 0.5), ("x", 0.1)]
    fused = rrf_fuse([a, b], k=60)
    scores = dict(fused)
    assert scores["x"] == pytest.approx(1 / 61 + 1 / 63)
    assert scores["y"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["z"] == pytest.approx(1 / 63)
    assert scores["w"] == pytest.approx(1 / 62)
    assert [cid for cid, _ in fused] == ["y", "x", "w", "z"]  # ranks 2+1 beat 1+3
    # Symmetric lists tie exactly; the tie breaks on chunk_id, not on list order.
    assert [cid for cid, _ in rrf_fuse([[("b", 1.0)], [("a", 1.0)]])] == ["a", "b"]
    assert [cid for cid, _ in rrf_fuse([[("a", 1.0)], [("b", 1.0)]])] == ["a", "b"]


def test_rrf_reads_ranks_not_scores():
    a = [("x", 1000.0), ("y", 0.001)]
    b = [("x", 0.5), ("y", 0.4)]
    assert rrf_fuse([a, b]) == rrf_fuse([[("x", 1.0), ("y", 0.9)], [("x", 1.0), ("y", 0.9)]])


def test_minmax_normalises_over_the_lists_own_candidates():
    assert minmax_normalize([("a", 10.0), ("b", 5.0), ("c", 0.0)]) == {"a": 1.0, "b": 0.5, "c": 0.0}
    assert minmax_normalize([("a", 3.0)]) == {"a": 1.0}
    assert minmax_normalize([("a", 2.0), ("b", 2.0)]) == {"a": 1.0, "b": 1.0}
    assert minmax_normalize([]) == {}


def test_weighted_endpoints_reproduce_each_list_and_missing_scores_zero():
    dense = [("x", 0.9), ("y", 0.8), ("z", 0.7)]
    sparse = [("y", 12.0), ("w", 6.0), ("z", 0.0)]
    # alpha = 1 is the dense ranking; dense's last candidate (z) normalises to 0 and
    # ties with the sparse-only w — the min-max artefact, broken on chunk_id.
    assert [cid for cid, _ in weighted_fuse(dense, sparse, alpha=1.0)] == ["x", "y", "w", "z"]
    # alpha = 0 is the BM25 ranking; z is BM25's minimum and ties with the dense-only x.
    assert [cid for cid, _ in weighted_fuse(dense, sparse, alpha=0.0)] == ["y", "w", "x", "z"]
    mid = dict(weighted_fuse(dense, sparse, alpha=0.5))
    assert mid["y"] == pytest.approx(0.5 * 0.5 + 0.5 * 1.0)
    assert mid["x"] == pytest.approx(0.5 * 1.0)
    assert mid["w"] == pytest.approx(0.5 * 0.5)
    assert mid["z"] == pytest.approx(0.0)
    with pytest.raises(ValueError, match="alpha"):
        weighted_fuse(dense, sparse, alpha=1.5)


# --- the retriever ---------------------------------------------------------------

def _index() -> tuple[ChunkIndex, dict[str, str]]:
    chunker = FixedTokenChunker(chunk_size=600, overlap=0)
    chunks = chunker.split_corpus(DOCS)
    index = ChunkIndex(
        chunks=chunks, chunker_id=chunker.chunker_id, chunker_params=chunker.params,
        corpus_hash=CORPUS_HASH, normalization_version="norm-v1",
    )
    return index, {c.chunk_id: c.text for c in chunks}


def _hybrid(tmp_path, **params) -> HybridRetriever:
    index, text = _index()
    dense = {
        "embedder": FakeEmbedder(EmbedderConfig(model="intfloat/e5-base-v2", revision="abc123")),
        "index_dir": tmp_path / "idx",
    }
    return build_retriever(
        "hybrid", chunk_to_doc=index.chunk_to_doc, chunk_text=text, index=index, dense=dense, **params
    )


def test_hybrid_is_registered_and_declares_what_it_embeds():
    assert "hybrid" in registered_retrievers()
    assert retriever_class("hybrid").embedding_params({"fusion": "rrf", "dense": {"embedding_model": "m"}}) == {
        "embedding_model": "m"
    }
    assert retriever_class("bm25").embedding_params({"k1": 1.2}) is None
    assert retriever_class("dense").embedding_params({"embedding_model": "m"}) == {"embedding_model": "m"}


def test_hybrid_refuses_a_bad_fusion_spec(tmp_path):
    with pytest.raises(ValueError, match="unknown fusion"):
        _hybrid(tmp_path, fusion="borda")
    with pytest.raises(ValueError, match="alpha"):
        _hybrid(tmp_path, fusion="weighted")
    with pytest.raises(ValueError, match="alpha"):
        _hybrid(tmp_path, fusion="rrf", alpha=0.5)


def test_rrf_hybrid_fuses_the_two_sub_rankings(tmp_path):
    retriever = _hybrid(tmp_path, fusion="rrf", rrf_k=60)
    query = "how do I request a refund for my plan"
    dense = retriever.dense.search(query, top_k=5)
    sparse = retriever.bm25.search(query, top_k=5)
    assert retriever.search(query, top_k=5) == rrf_fuse([dense, sparse], k=60)[:5]
    assert retriever.search(query, top_k=5) == retriever.search(query, top_k=5)
    assert retriever.search("   ", top_k=5) == []


def test_weighted_hybrid_endpoints_reproduce_the_sub_rankings(tmp_path):
    """Up to the list's own last candidate, which min-max sends to 0 (see module doc)."""
    query = "click the menu design"
    dense_only = _hybrid(tmp_path, fusion="weighted", alpha=1.0)
    expected = [cid for cid, _ in dense_only.dense.search(query, top_k=5)]
    assert [cid for cid, _ in dense_only.search(query, top_k=5)][: len(expected) - 1] == expected[:-1]
    sparse_only = _hybrid(tmp_path, fusion="weighted", alpha=0.0)
    expected = [cid for cid, _ in sparse_only.bm25.search(query, top_k=5)]
    assert len(expected) >= 2
    assert [cid for cid, _ in sparse_only.search(query, top_k=5)][: len(expected) - 1] == expected[:-1]


def test_hybrid_provenance_carries_the_dense_index_and_the_fusion_counters(tmp_path):
    retriever = _hybrid(tmp_path, fusion="weighted", alpha=0.4)
    result = retriever.retrieve("q1", "how do I request a refund", top_k=10, k_docs=2, candidate_pool=10)
    assert len(result.context.doc_ids) == len(set(result.context.doc_ids))
    prov = retriever.provenance()
    assert prov["index_key"] == retriever.dense.key
    assert prov["fusion"]["alpha"] == 0.4 and "normalization" in prov["fusion"]
    stats = prov["fusion_stats"]
    assert stats["queries"] == 1
    assert 0.0 <= stats["mean_candidate_jaccard"] <= 1.0
    assert sum(stats["context_docs_by_source"].values()) == len(result.context.doc_ids)
    assert retriever.query_cost_usd() == 0.0  # the fake embedder charges nothing
    assert retriever.pipeline_llm is None
