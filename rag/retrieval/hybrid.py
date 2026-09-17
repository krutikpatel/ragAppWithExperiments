"""Hybrid retrieval — P2-09, Axis 3. Dense and BM25 rankings fused into one.

Two fusion rules, both over the top `top_k` chunks of each sub-retriever:

- `rrf` — Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, 2009): a chunk's
  fused score is the sum over lists of 1 / (rrf_k + rank), rank counted from 1.
  Scores are never read, only ranks, so the two retrievers' incomparable scales
  (cosine in [-1, 1], Okapi in [0, ∞)) never meet.
- `weighted` — convex combination of min-max-normalised scores: each list is
  rescaled to [0, 1] over the candidates it returned, a chunk missing from a list
  contributes 0 for that list, and the fused score is
  `alpha * dense + (1 - alpha) * bm25`. `alpha` is the weight on **dense**, so
  `alpha = 1` reproduces the dense ranking and `alpha = 0` reproduces BM25's — up
  to one artefact of min-max: a list's lowest-scored candidate normalises to 0 and
  so ties with every chunk the list did not return. At depth 100 that is rank 100,
  far below any k this project scores. A list whose candidates all share one score
  normalises to 1.

Ties in the fused score break on `chunk_id` (MIS-003). The dense sub-retriever owns
the vector index, so the hybrid's index key, build cost and query cost are its;
BM25 is rebuilt in-process and costs nothing. Nothing here calls an LLM.

Config shape (the runner passes `retriever_params` as keyword arguments):

    retriever: hybrid
    retriever_params:
      fusion: rrf          # or weighted
      rrf_k: 60            # rrf only
      alpha: 0.5           # weighted only; weight on dense
      dense: {embedding_backend, embedding_model, embedding_provider, ...}
      bm25: {k1, b}        # optional; Okapi defaults otherwise
"""

from __future__ import annotations

from typing import Any

from rag.retrieval.base import Retriever
from rag.retrieval.bm25 import BM25Retriever
from rag.retrieval.dense import DenseRetriever
from rag.runner.registry import register_retriever

FUSION_RULES = ("rrf", "weighted")
DEFAULT_RRF_K = 60


def rrf_fuse(
    rankings: list[list[tuple[str, float]]], *, k: int = DEFAULT_RRF_K
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion over any number of ranked lists. Ranks start at 1."""
    if k < 0:
        raise ValueError("rrf_k must be non-negative")
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, (chunk_id, _score) in enumerate(ranking, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))


def minmax_normalize(ranking: list[tuple[str, float]]) -> dict[str, float]:
    """Rescale a list's scores to [0, 1] over its own candidates. One candidate, or
    all candidates tied, normalises to 1.0 — present beats absent."""
    if not ranking:
        return {}
    scores = [score for _, score in ranking]
    lo, hi = min(scores), max(scores)
    if hi - lo <= 0.0:
        return {chunk_id: 1.0 for chunk_id, _ in ranking}
    return {chunk_id: (score - lo) / (hi - lo) for chunk_id, score in ranking}


def weighted_fuse(
    dense: list[tuple[str, float]], sparse: list[tuple[str, float]], *, alpha: float
) -> list[tuple[str, float]]:
    """`alpha * minmax(dense) + (1 - alpha) * minmax(sparse)`; missing = 0."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha}")
    d, s = minmax_normalize(dense), minmax_normalize(sparse)
    fused = {
        chunk_id: alpha * d.get(chunk_id, 0.0) + (1.0 - alpha) * s.get(chunk_id, 0.0)
        for chunk_id in set(d) | set(s)
    }
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))


@register_retriever("hybrid")
class HybridRetriever(Retriever):
    name = "hybrid"

    def __init__(
        self,
        chunk_to_doc: dict[str, str],
        chunk_text: dict[str, str],
        *,
        fusion: str = "rrf",
        rrf_k: int = DEFAULT_RRF_K,
        alpha: float | None = None,
        dense: dict[str, Any] | None = None,
        bm25: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunk_to_doc, **kwargs)
        if fusion not in FUSION_RULES:
            raise ValueError(f"unknown fusion {fusion!r}; known: {FUSION_RULES}")
        if fusion == "weighted":
            if alpha is None:
                raise ValueError("weighted fusion needs `alpha` (the weight on dense)")
            if not 0.0 <= alpha <= 1.0:
                raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        elif alpha is not None:
            raise ValueError("`alpha` only applies to weighted fusion; rrf reads ranks, not scores")
        self.fusion = fusion
        self.rrf_k = int(rrf_k)
        self.alpha = None if alpha is None else float(alpha)
        # Both sub-retrievers share the pooling rule, the chunk index and the cache
        # handle; the dense one keys its vector cache on the index's provenance.
        shared = {"doc_pooling": self.doc_pooling, "index": self.index, "generation_cache": self.generation_cache}
        self.dense = DenseRetriever(chunk_to_doc, chunk_text, **shared, **(dense or {}))
        self.bm25 = BM25Retriever(chunk_to_doc, chunk_text, **shared, **(bm25 or {}))
        # Per-run counters for the writeup: how much the two candidate sets overlap,
        # and which retriever found the documents that reached the context.
        self._queries = 0
        self._overlap_sum = 0.0
        self._context_source = {"both": 0, "dense_only": 0, "bm25_only": 0}

    @classmethod
    def embedding_params(cls, retriever_params: dict[str, Any]) -> dict[str, Any] | None:
        return dict(retriever_params.get("dense") or {})

    @property
    def params(self) -> dict[str, Any]:
        out: dict[str, Any] = {"fusion": self.fusion, "dense": self.dense.params, "bm25": self.bm25.params}
        if self.fusion == "rrf":
            out["rrf_k"] = self.rrf_k
        else:
            out["alpha"] = self.alpha
            out["normalization"] = "minmax over each list's own candidates; missing = 0"
        return out

    def query_cost_usd(self) -> float:
        return self.dense.query_cost_usd()

    def provenance(self) -> dict[str, Any]:
        """The dense index's provenance at top level — it *is* this retriever's index,
        and the cost bookkeeping reads `embedder` / `embedder_now` / `cache_hit` there —
        plus the fusion settings and the per-run fusion counters."""
        n = self._queries
        return {
            **self.dense.provenance(),
            "fusion": {k: v for k, v in self.params.items() if k != "dense"},
            "fusion_stats": {
                "queries": n,
                "mean_candidate_jaccard": round(self._overlap_sum / n, 4) if n else None,
                "context_docs_by_source": dict(self._context_source),
            },
        }

    def fuse(
        self, dense: list[tuple[str, float]], sparse: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        if self.fusion == "rrf":
            return rrf_fuse([dense, sparse], k=self.rrf_k)
        return weighted_fuse(dense, sparse, alpha=self.alpha)

    def search(self, query: str, *, top_k: int) -> list[tuple[str, float]]:
        dense = self.dense.search(query, top_k=top_k)
        sparse = self.bm25.search(query, top_k=top_k)
        self._last_sources = ({cid for cid, _ in dense}, {cid for cid, _ in sparse})
        return self.fuse(dense, sparse)[:top_k]

    def retrieve(self, question_id: str, query: str, *, top_k: int, **kw: Any):
        result = super().retrieve(question_id, query, top_k=top_k, **kw)
        dense_ids, sparse_ids = self._last_sources
        union = dense_ids | sparse_ids
        self._queries += 1
        self._overlap_sum += len(dense_ids & sparse_ids) / len(union) if union else 0.0
        if result.context is not None:
            for chunk_id, _ in result.context.chunks:
                source = (
                    "both" if chunk_id in dense_ids and chunk_id in sparse_ids
                    else "dense_only" if chunk_id in dense_ids
                    else "bm25_only"
                )
                self._context_source[source] += 1
        return result
