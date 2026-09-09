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
