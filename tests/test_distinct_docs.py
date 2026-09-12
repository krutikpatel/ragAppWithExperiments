"""P1-03 — k distinct documents, not k chunks; the collapse ratio; pool exhaustion."""

from __future__ import annotations

import pytest

from rag.retrieval.base import Retriever
from rag.retrieval.pooling import pool_chunks_to_docs, select_distinct_docs
from rag.runner.config import RunConfig

# Ten ranked chunks. The top five all belong to two documents (A and B) — the case
# the story names — and documents C, D, E appear only at ranks 6, 8 and 9.
CHUNK_TO_DOC = {
    "c1": "A", "c2": "A", "c3": "B", "c4": "A", "c5": "B",
    "c6": "C", "c7": "B", "c8": "D", "c9": "E", "c10": "A",
}
RANKED = [(f"c{i}", 10.0 - i) for i in range(1, 11)]


class _FixedRanking(Retriever):
    name = "fixed"

    def search(self, query, *, top_k):
        return RANKED[:top_k]


def test_top_five_chunks_from_two_docs_still_yield_five_distinct_docs():
    selection = select_distinct_docs(RANKED, CHUNK_TO_DOC, k=5, candidate_pool=50)
    assert selection.doc_ids == ["A", "B", "C", "D", "E"]
    assert len(set(selection.doc_ids)) == 5
    # It had to read nine chunks to find five documents.
    assert selection.chunks_scanned == 9
    assert selection.collapse_ratio == pytest.approx(9 / 5)
    assert selection.collapse_ratio >= 1.8
    assert not selection.exhausted


def test_collapse_ratio_is_at_least_2_5_when_five_chunks_hold_two_docs():
    """The story's number: top-5 chunks in 2 docs must record a ratio >= 2.5."""
    selection = select_distinct_docs(RANKED, CHUNK_TO_DOC, k=2, candidate_pool=5)
    assert selection.doc_ids == ["A", "B"]
    assert selection.chunks_scanned == 3  # A at c1, B at c3
    # With k=2 the walk stops early. The ratio the story describes is chunks
    # actually needed per doc over the top-5 window: 5 chunks / 2 docs.
    window = select_distinct_docs(RANKED[:5], CHUNK_TO_DOC, k=5, candidate_pool=5)
    assert window.doc_ids == ["A", "B"]
    assert window.collapse_ratio == pytest.approx(2.5)
    assert window.exhausted


def test_one_chunk_per_document_is_the_documents_best_chunk():
    selection = select_distinct_docs(RANKED, CHUNK_TO_DOC, k=5, candidate_pool=50)
    assert [cid for cid, _ in selection.chunks] == ["c1", "c3", "c6", "c8", "c9"]
    # Same document order as max pooling over the same prefix of the ranking.
    pooled = pool_chunks_to_docs(RANKED[:9], CHUNK_TO_DOC, rule="max")
    assert [d for d, _ in pooled][:5] == selection.doc_ids


def test_pool_exhaustion_is_recorded_not_hidden():
    selection = select_distinct_docs(RANKED, CHUNK_TO_DOC, k=5, candidate_pool=6)
    assert selection.doc_ids == ["A", "B", "C"]
    assert selection.chunks_scanned == 6
    assert selection.exhausted
    assert selection.collapse_ratio == pytest.approx(2.0)
    # A ranking shorter than the pool exhausts too.
    short = select_distinct_docs(RANKED[:2], CHUNK_TO_DOC, k=5, candidate_pool=50)
    assert short.doc_ids == ["A"] and short.exhausted
    empty = select_distinct_docs([], CHUNK_TO_DOC, k=5, candidate_pool=50)
    assert empty.doc_ids == [] and empty.exhausted and empty.collapse_ratio is None


def test_invalid_walk_parameters_are_rejected():
    with pytest.raises(ValueError):
        select_distinct_docs(RANKED, CHUNK_TO_DOC, k=0, candidate_pool=5)
    with pytest.raises(ValueError):
        select_distinct_docs(RANKED, CHUNK_TO_DOC, k=6, candidate_pool=5)


def test_retriever_attaches_the_selection_and_keeps_the_scoring_depth():
    retriever = _FixedRanking(CHUNK_TO_DOC)
    result = retriever.retrieve("q", "query", top_k=10, k_docs=5, candidate_pool=50)
    assert len(result.chunks) == 10  # scoring depth untouched
    assert result.context.doc_ids == ["A", "B", "C", "D", "E"]
    assert [c.chunk_id for c in result.context_chunks] == ["c1", "c3", "c6", "c8", "c9"]
    assert [c.doc_id for c in result.context_chunks] == ["A", "B", "C", "D", "E"]
    # Without k_docs the result is a ranking only.
    assert retriever.retrieve("q", "query", top_k=10).context is None


def test_run_config_orders_top_k_pool_and_depth():
    ok = RunConfig(name="t", top_k=5, candidate_pool=50, retrieval_depth=100)
    assert (ok.top_k, ok.candidate_pool, ok.retrieval_depth) == (5, 50, 100)
    with pytest.raises(ValueError, match="candidate_pool"):
        RunConfig(name="t", top_k=10, candidate_pool=5)
    with pytest.raises(ValueError, match="retrieval_depth"):
        RunConfig(name="t", candidate_pool=50, retrieval_depth=20)
