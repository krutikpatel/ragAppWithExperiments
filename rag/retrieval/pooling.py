"""chunk → document pooling — P0-05.

Retrieval happens over chunks; scoring happens over documents. The rule that
bridges them is a first-class config field (`doc_pooling`) recorded on every run,
because it changes the document ranking on its own, with no change to retrieval.

`max` is the default. Under `max`, a document whose best chunk ranks 3rd can never
pool to 1st — the document owning the top chunk always scores at least as high.
Under `sum`, it can, when the document is matched by several chunks. That is a
real ranking difference produced by nothing but the pooling rule, which is exactly
why it may not be left implicit. See tests/test_pooling.py.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

DEFAULT_POOLING = "max"

_RULES: dict[str, Callable[[Sequence[float]], float]] = {
    "max": max,
    "sum": sum,
}

POOLING_RULES = tuple(_RULES)


def resolve_pooling(rule: str) -> Callable[[Sequence[float]], float]:
    if rule not in _RULES:
        raise ValueError(f"unknown doc_pooling {rule!r}; known rules: {POOLING_RULES}")
    return _RULES[rule]


def pool_chunks_to_docs(
    ranked_chunks: Iterable[tuple[str, float]],
    chunk_to_doc: dict[str, str],
    *,
    rule: str = DEFAULT_POOLING,
) -> list[tuple[str, float]]:
    """Pool ranked (chunk_id, score) pairs into ranked (doc_id, score) pairs.

    Ties break on the rank of the document's best chunk, so the ordering is total
    and reproducible rather than dependent on dict iteration order.
    """
    pool = resolve_pooling(rule)

    scores: dict[str, list[float]] = {}
    best_rank: dict[str, int] = {}
    for rank, (chunk_id, score) in enumerate(ranked_chunks):
        try:
            doc_id = chunk_to_doc[chunk_id]
        except KeyError:
            raise KeyError(
                f"chunk {chunk_id!r} is not in the chunk→doc mapping; the index and "
                "its mapping are out of sync"
            ) from None
        scores.setdefault(doc_id, []).append(score)
        best_rank.setdefault(doc_id, rank)

    pooled = [(doc_id, pool(values)) for doc_id, values in scores.items()]
    pooled.sort(key=lambda item: (-item[1], best_rank[item[0]]))
    return pooled


# --- P1-03: k distinct documents, not k chunks -------------------------------


@dataclass(frozen=True)
class DocSelection:
    """The generator's context, chosen at document granularity.

    `chunks` holds one (chunk_id, score) per selected document — the document's
    best-ranked chunk, which under `max` pooling is the chunk that gave the document
    its score. `chunks_scanned` is how far down the ranked chunk list the walk went
    to find them; divided by the documents found it is the **collapse ratio**, the
    first-class measure of how many chunks fold into one article on this corpus.
    """

    chunks: list[tuple[str, float]]
    doc_ids: list[str]
    chunks_scanned: int
    candidate_pool: int
    k: int

    @property
    def exhausted(self) -> bool:
        """Fewer than `k` distinct documents were found within the candidate pool."""
        return len(self.doc_ids) < self.k

    @property
    def collapse_ratio(self) -> float | None:
        """chunks scanned ÷ distinct documents returned. None if nothing was found."""
        if not self.doc_ids:
            return None
        return self.chunks_scanned / len(self.doc_ids)


def select_distinct_docs(
    ranked_chunks: Sequence[tuple[str, float]],
    chunk_to_doc: dict[str, str],
    *,
    k: int,
    candidate_pool: int,
) -> DocSelection:
    """Walk the ranked chunk list until `k` distinct documents are collected.

    Gold is document-level and multi-document questions need two or three *distinct*
    articles, so a context of five chunks that fold into two articles cannot satisfy
    them regardless of how good the ranking is. The walk stops at `k` documents or
    after `candidate_pool` chunks, whichever comes first; stopping on the pool is
    recorded as exhaustion rather than silently returning fewer documents.

    The first chunk seen for a document is kept as its representative. Under `max`
    pooling that is the chunk that scored the document; the walk does not re-pool,
    so the document order here matches `pool_chunks_to_docs(rule="max")` over the
    same prefix of the ranking.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    if candidate_pool < k:
        raise ValueError(f"candidate_pool ({candidate_pool}) must be at least k ({k})")
    chosen: list[tuple[str, float]] = []
    doc_ids: list[str] = []
    seen: set[str] = set()
    scanned = 0
    for chunk_id, score in ranked_chunks[:candidate_pool]:
        scanned += 1
        doc_id = chunk_to_doc[chunk_id]
        if doc_id in seen:
            continue
        seen.add(doc_id)
        chosen.append((chunk_id, score))
        doc_ids.append(doc_id)
        if len(doc_ids) == k:
            break
    return DocSelection(
        chunks=chosen, doc_ids=doc_ids, chunks_scanned=scanned, candidate_pool=candidate_pool, k=k
    )
