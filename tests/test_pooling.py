"""P0-05 — chunk→doc pooling, including the required rank-3 case."""

from __future__ import annotations

import pytest

from rag.retrieval.base import Retriever
from rag.retrieval.pooling import pool_chunks_to_docs

# Synthetic ranking. doc_A is the correct document. Its best chunk ranks 3rd among
# chunks, behind two chunks of doc_B, but doc_A is matched three times over.
CHUNK_TO_DOC = {
    "c1": "doc_B",
    "c2": "doc_B",
    "c3": "doc_A",
    "c4": "doc_A",
    "c5": "doc_A",
    "c6": "doc_C",
}
RANKED_CHUNKS = [
    ("c1", 0.90),
    ("c2", 0.85),
    ("c3", 0.80),
    ("c4", 0.75),
    ("c5", 0.70),
    ("c6", 0.40),
]


def test_correct_doc_best_chunk_is_third():
    """Precondition for the cases below."""
    chunk_rank_of_doc_a = [
        i for i, (cid, _) in enumerate(RANKED_CHUNKS) if CHUNK_TO_DOC[cid] == "doc_A"
    ]
    assert chunk_rank_of_doc_a[0] == 2  # 0-indexed: third chunk


def test_sum_pooling_lifts_the_correct_doc_to_rank_one():
    """The document ranks 1st after pooling even though its best chunk ranked 3rd."""
    pooled = pool_chunks_to_docs(RANKED_CHUNKS, CHUNK_TO_DOC, rule="sum")
    assert [doc for doc, _ in pooled] == ["doc_A", "doc_B", "doc_C"]
    assert pooled[0][1] == pytest.approx(0.80 + 0.75 + 0.70)


def test_max_pooling_cannot_lift_it_past_the_top_chunks_owner():
    """Same retrieval, different pooling rule, different document ranking.

    This is the whole reason `doc_pooling` is recorded on every run: under `max`
    the document owning the top chunk can never be displaced, so a run's document
    metrics are not interpretable without knowing which rule produced them.
    """
    pooled = pool_chunks_to_docs(RANKED_CHUNKS, CHUNK_TO_DOC, rule="max")
    assert [doc for doc, _ in pooled] == ["doc_B", "doc_A", "doc_C"]
    assert pooled[0][1] == pytest.approx(0.90)


def test_default_rule_is_max():
    assert pool_chunks_to_docs(RANKED_CHUNKS, CHUNK_TO_DOC) == pool_chunks_to_docs(
        RANKED_CHUNKS, CHUNK_TO_DOC, rule="max"
    )


def test_ties_break_on_best_chunk_rank():
    chunk_to_doc = {"c1": "doc_X", "c2": "doc_Y"}
    pooled = pool_chunks_to_docs([("c1", 0.5), ("c2", 0.5)], chunk_to_doc)
    assert [doc for doc, _ in pooled] == ["doc_X", "doc_Y"]


def test_unknown_chunk_is_an_error_not_a_silent_drop():
    with pytest.raises(KeyError, match="out of sync"):
        pool_chunks_to_docs([("ghost", 1.0)], CHUNK_TO_DOC)


def test_unknown_pooling_rule_rejected():
    with pytest.raises(ValueError, match="unknown doc_pooling"):
        pool_chunks_to_docs(RANKED_CHUNKS, CHUNK_TO_DOC, rule="mean")


class _FixtureRetriever(Retriever):
    """Replays a fixed ranking, so the interface can be tested without an index."""

    name = "fixture"

    def search(self, query: str, *, top_k: int) -> list[tuple[str, float]]:
        return RANKED_CHUNKS[:top_k]


def test_retriever_returns_both_granularities():
    retriever = _FixtureRetriever(CHUNK_TO_DOC, doc_pooling="sum")
    result = retriever.retrieve("q1", "any query", top_k=6)

    assert result.chunk_ids == ["c1", "c2", "c3", "c4", "c5", "c6"]
    assert result.doc_ids == ["doc_A", "doc_B", "doc_C"]
    assert result.doc_pooling == "sum"
    assert all(c.doc_id == CHUNK_TO_DOC[c.chunk_id] for c in result.chunks)
