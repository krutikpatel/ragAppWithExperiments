"""Maximal Marginal Relevance — P2-13, Axis 6.

MMR (Carbonell & Goldstein, 1998) re-orders candidates to trade relevance against
redundancy. Each step picks the candidate maximising

    lambda * rel(d) - (1 - lambda) * max_{s already selected} sim(d, s)

`lambda = 1` reproduces the retriever's ranking exactly; `lambda = 0` ignores
relevance after the first pick and chases novelty.

## Why this lives in the reranker slot

Mechanically it is a reranker: it re-orders a candidate set and adds nothing. So it
reuses the P2-10 machinery — document-level candidates, splicing, re-pooling, the
recomputed collapse ratio — rather than a parallel path. Its *axis* is `assembly`
(P2-13), because the question it answers is about what the context should contain,
not about scoring quality. A run therefore carries `axis: assembly` while its config
diff reports the `reranking` dimension; both are accurate and DEC-062 says so.

## Why it is free

Relevance comes from the retriever's own scores and similarity from the cached
vectors, so MMR makes no network call and builds no index.

## Why it refuses a retriever without vectors

The two terms must be on one scale. A dense retriever's score *is* the cosine
between the query and the chunk, and the index rows are L2-normalized, so
`rel(d)` and `sim(d, s)` are both cosines and `lambda` means what it says. BM25's
Okapi scores are unbounded and share no space with any vector, so mixing them would
make `lambda` a meaningless dial calibrated to whatever the score happened to be.
`Retriever.chunk_vectors` returns None there and this refuses to run.

## Document diversity comes out of chunk diversity

Two chunks of one article are near-duplicates in embedding space, so the redundancy
term penalises the second one heavily. That is the mechanism by which MMR is expected
to serve multi-document coverage, and the collapse ratio on every run is how that
expectation is checked rather than assumed.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from rag.reranking.base import Reranker, check_same_chunks
from rag.retrieval.base import ScoredChunk
from rag.runner.registry import register_reranker


def mmr_order(
    relevance: np.ndarray, similarity: np.ndarray, *, lambda_: float
) -> list[int]:
    """Indices of `relevance`, in MMR order. `similarity` is the candidate-by-candidate
    cosine matrix. Ties break on the earlier (more relevant) candidate, as everywhere
    else in this repo (MIS-003)."""
    if not 0.0 <= lambda_ <= 1.0:
        raise ValueError(f"lambda must be in [0, 1], got {lambda_}")
    n = len(relevance)
    if n == 0:
        return []
    remaining = list(range(n))
    # The first pick has nothing to be redundant with, so it is the most relevant.
    first = max(remaining, key=lambda i: (relevance[i], -i))
    order = [first]
    remaining.remove(first)
    # Running max similarity of each remaining candidate to anything selected.
    redundancy = similarity[:, first].copy()
    while remaining:
        best = max(
            remaining,
            key=lambda i: (lambda_ * relevance[i] - (1.0 - lambda_) * redundancy[i], -i),
        )
        order.append(best)
        remaining.remove(best)
        np.maximum(redundancy, similarity[:, best], out=redundancy)
    return order


@register_reranker("mmr")
class MMRReranker(Reranker):
    """Diversity-aware re-ordering over the retriever's own vector space."""

    name = "mmr"

    def __init__(
        self,
        chunk_text: dict[str, str],
        *,
        generation_cache: Any = None,
        vector_source: Any = None,
        lambda_: float = 0.5,
    ) -> None:
        super().__init__(chunk_text, generation_cache=generation_cache, vector_source=vector_source)
        if not 0.0 <= lambda_ <= 1.0:
            raise ValueError(f"lambda must be in [0, 1], got {lambda_}")
        self.lambda_ = lambda_
        self.redundancy_removed = 0.0

    @property
    def reranker_id(self) -> str:
        return f"mmr@lambda={self.lambda_}"

    def rerank(
        self, query: str, chunks: list[ScoredChunk], *, question_id: str = ""
    ) -> list[ScoredChunk]:
        if not chunks:
            return []
        vectors = (
            self.vector_source.chunk_vectors([c.chunk_id for c in chunks])
            if self.vector_source is not None
            else None
        )
        if vectors is None:
            raise RuntimeError(
                "MMR needs candidate embeddings and this retriever has none. Its "
                "relevance and redundancy terms must share one scale, and mixing "
                "Okapi scores with cosines would make `lambda` meaningless. Use MMR "
                "with a retriever that owns a vector index (dense, or hybrid's dense "
                "half)."
            )
        vectors = np.asarray(vectors, dtype=np.float32)
        # Rows are L2-normalized by the index, so the Gram matrix is cosine similarity.
        similarity = vectors @ vectors.T
        relevance = np.array([c.score for c in chunks], dtype=np.float32)
        order = mmr_order(relevance, similarity, lambda_=self.lambda_)

        # How much redundancy the ordering actually removed, averaged over the
        # questions: the mean similarity between each pick and its most similar
        # predecessor. Recorded so "MMR diversified the context" is measured, not
        # asserted — it is the thing lambda is supposed to buy.
        if len(order) > 1:
            picked = np.array(order)
            worst = [similarity[picked[i], picked[:i]].max() for i in range(1, len(picked))]
            self.redundancy_removed += float(np.mean(worst))
        self.usage.calls += 1
        self.usage.candidates += len(chunks)
        reranked = [
            ScoredChunk(chunk_id=chunks[i].chunk_id, doc_id=chunks[i].doc_id,
                        score=float(len(order) - rank))
            for rank, i in enumerate(order)
        ]
        check_same_chunks(chunks, reranked)
        return reranked

    def provenance(self) -> dict[str, Any]:
        meta = super().provenance()
        meta.update({
            "lambda": self.lambda_,
            "reranker_id": self.reranker_id,
            "vector_source": getattr(self.vector_source, "name", None),
            "mean_redundancy_of_picks": (
                round(self.redundancy_removed / self.usage.calls, 4) if self.usage.calls else None
            ),
        })
        return meta
