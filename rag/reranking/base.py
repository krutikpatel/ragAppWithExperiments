"""Reranker interface — P0-11 (interface) and P2-10 (Axis 5, the implementations).

A reranker re-orders chunks a retriever already found. It cannot rescue a document
the retriever never returned, so it is a **precision** technique measured against a
fixed candidate set.

Phase 0 shipped the interface alone, and `tests/test_interfaces.py` still asserts
that no concrete subclass lives in *this module*: implementations belong in the
sibling modules that a story authorised (`openrouter.py`, `llm.py`, DEC-058), so a
reranker cannot appear here as a quiet default.

## k and n are documents, not chunks (P1-03, DEC-040)

`rerank_candidates` is a count of **distinct documents**, and `top_k` stays the
count of distinct documents that reach the generator. `candidate_prefix` walks the
ranked chunk list until the (n+1)-th document appears and hands the reranker
everything above that line — every ranked chunk of those n documents, not one per
document. Keeping the duplicates is deliberate: it is the only way a cross-encoder
*can* re-concentrate the context onto one article, which is the behaviour P2-10
asks to be measured (the collapse ratio is recomputed after reranking).

## What the reranked ranking looks like

`apply_rerank` returns prefix-then-tail: the reranked candidates carry the
reranker's own relevance scores, and the untouched tail is pushed strictly below
them with a monotone decreasing score that preserves its original order. The tail
is kept rather than dropped so deeper metrics (recall@20) still measure a real
ranking rather than a truncation. Ties inside the prefix break on `chunk_id`, as
everywhere else (MIS-003).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Sequence

from rag.retrieval.base import ScoredChunk

if TYPE_CHECKING:
    from rag.generation.cache import GenerationCache
    from rag.generation.pipeline_llm import PipelineLLM


@dataclass
class RerankUsage:
    """What the reranker spent, summed over every query in the run.

    `cost_usd` is provider-reported, never inferred from a price table: OpenRouter's
    model listings report `0` for every rerank model while the responses bill real
    money (MIS-025). `search_units` is Cohere's billing unit and `tokens` Fireworks',
    so a run records whichever its reranker reported and neither is invented.
    """

    calls: int = 0
    retries: int = 0
    rate_limited: int = 0
    candidates: int = 0
    search_units: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    latency_ms_total: int = 0
    providers_seen: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "retries": self.retries,
            "rate_limited": self.rate_limited,
            "candidates": self.candidates,
            "search_units": self.search_units,
            "tokens": self.tokens,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms_total": self.latency_ms_total,
            "latency_ms_mean": round(self.latency_ms_total / self.calls, 1) if self.calls else None,
            "providers_seen": list(self.providers_seen),
        }


class Reranker(ABC):
    """Re-orders retrieved chunks for a query. Must not add or drop chunks."""

    name: str
    # Set by rerankers that call an LLM (the LLM-as-reranker, P2-10). The runner
    # reads it exactly as it reads a retriever's, records the cache hit rate and
    # marks the run `pipeline_nondeterministic` (P2-03).
    pipeline_llm: PipelineLLM | None = None
    # OQ-054, DEC-102: a reranker whose scores are probabilities may set a floor. The
    # context then holds only reranked chunks scoring at least this, so fewer than
    # top_k documents can reach the generator. The RANKING is untouched — every
    # retrieval metric reads the same list with or without a floor.
    context_floor: float | None = None

    def __init__(
        self,
        chunk_text: dict[str, str],
        *,
        generation_cache: GenerationCache | None = None,
        vector_source: Any = None,
    ) -> None:
        # The text the reranker scores is the text the retriever indexed, so a
        # "retrieve small, expand" chunker (P2-07) is reranked on what was indexed.
        self.chunk_text = chunk_text
        self.generation_cache = generation_cache
        # The retriever, for rerankers that work in its vector space (MMR, P2-13).
        # On the base because the runner hands it to every reranker uniformly; those
        # that score text rather than vectors simply never read it.
        self.vector_source = vector_source
        self.usage = RerankUsage()

    @abstractmethod
    def rerank(self, query: str, chunks: list[ScoredChunk], *, question_id: str = "") -> list[ScoredChunk]:
        """Return the same chunks, re-scored and re-ordered, best first."""

    def provenance(self) -> dict[str, Any]:
        """What this reranker was, recorded on the run row."""
        return {"reranker": self.name, "usage": self.usage.as_dict()}

    def query_cost_usd(self) -> float:
        """Provider-reported spend on this run's rerank calls. Zero for in-process."""
        return self.usage.cost_usd

    @classmethod
    def estimate_params(cls, reranker_params: dict[str, Any]) -> dict[str, Any] | None:
        """What this reranker would bill per query, for the pre-run gate (P2-06), or
        None when it costs nothing. Keyed on the class rather than the name so the
        runner never reads a hosted reranker as free."""
        return None

    # --- shared bookkeeping ---------------------------------------------------

    def _timed(self, fn, *args, **kwargs):
        started = time.perf_counter()
        out = fn(*args, **kwargs)
        self.usage.latency_ms_total += int((time.perf_counter() - started) * 1000)
        return out


# --- document-level candidate selection and splicing --------------------------


def candidate_prefix(
    ranked: Sequence[tuple[str, float]],
    chunk_to_doc: dict[str, str],
    *,
    n_docs: int,
) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """Split a ranked chunk list at the point where the (n_docs+1)-th document appears.

    The head is what the reranker sees: every ranked chunk of the top `n_docs`
    distinct documents, in retriever order. The tail is everything below. This is
    what makes "50 -> 5" a document-level ratio (P1-03) rather than a chunk count
    that means something different for every chunker.
    """
    if n_docs < 1:
        raise ValueError("n_docs must be at least 1")
    seen: list[str] = []
    cut = len(ranked)
    for position, (chunk_id, _score) in enumerate(ranked):
        doc_id = chunk_to_doc[chunk_id]
        if doc_id not in seen:
            if len(seen) == n_docs:
                cut = position
                break
            seen.append(doc_id)
    return list(ranked[:cut]), list(ranked[cut:])


# The gap that separates reranked candidates from the untouched tail. Any positive
# constant works: only the order is read downstream (MIS-003), and pooling under
# `max` orders documents by their best chunk's rank either way.
_TAIL_GAP = 1.0
_TAIL_STEP = 1e-6


def apply_rerank(
    reranked: Sequence[ScoredChunk],
    tail: Sequence[tuple[str, float]],
    chunk_to_doc: dict[str, str],
) -> list[tuple[str, float]]:
    """Splice a reranked head back onto the untouched tail as one total ranking.

    Tail scores are rewritten to sit strictly below the lowest reranked score,
    decreasing by a fixed step so the tail keeps its original order exactly. The
    rewrite is why a rerank run's raw scores are not comparable to the retriever's
    — the ranking is, and the ranking is what every metric reads.
    """
    head = [(c.chunk_id, c.score) for c in reranked]
    floor = min((score for _, score in head), default=0.0) - _TAIL_GAP
    spliced = head + [
        (chunk_id, floor - index * _TAIL_STEP) for index, (chunk_id, _score) in enumerate(tail)
    ]
    for chunk_id, _ in spliced:
        if chunk_id not in chunk_to_doc:
            raise KeyError(f"reranker returned chunk {chunk_id!r}, which is not in the index")
    return spliced


def check_same_chunks(before: Sequence[ScoredChunk], after: Sequence[ScoredChunk]) -> None:
    """A reranker re-orders; it does not add or drop. Enforced at the call, because
    a dropped candidate would read as a retrieval failure in every metric."""
    a = sorted(c.chunk_id for c in before)
    b = sorted(c.chunk_id for c in after)
    if a != b:
        missing = sorted(set(a) - set(b))
        added = sorted(set(b) - set(a))
        raise RuntimeError(
            f"reranker changed the candidate set: dropped {missing[:5]} "
            f"({len(missing)}), added {added[:5]} ({len(added)}). A reranker may "
            "only re-order."
        )


def rerank_result(
    result: Any,
    reranker: Reranker,
    *,
    query: str,
    chunk_to_doc: dict[str, str],
    n_docs: int,
    k_docs: int,
    candidate_pool: int,
    doc_pooling: str,
) -> tuple[Any, dict[str, Any]]:
    """Re-order one question's retrieval result and rebuild everything downstream.

    Pooling and the distinct-document walk are recomputed from the reranked
    ranking, which is the point: the collapse ratio and pool exhaustion a run
    records are post-rerank facts, so a cross-encoder that re-concentrates the
    context onto one article shows up as a rising collapse ratio rather than
    disappearing into an unchanged number (P2-10).

    Returns the new `RetrievalResult` and a per-question record of what the rerank
    saw and how much of the context it replaced.
    """
    from rag.retrieval.base import RetrievalResult
    from rag.retrieval.pooling import pool_chunks_to_docs, select_distinct_docs

    ranked = [(c.chunk_id, c.score) for c in result.chunks]
    head, tail = candidate_prefix(ranked, chunk_to_doc, n_docs=n_docs)
    head_ids = {chunk_id for chunk_id, _ in head}
    head_chunks = [c for c in result.chunks if c.chunk_id in head_ids]
    before_docs = result.doc_ids[:k_docs]

    reranked = reranker.rerank(query, head_chunks, question_id=result.question_id)
    spliced = apply_rerank(reranked, tail, chunk_to_doc)
    scored = [ScoredChunk(chunk_id=cid, doc_id=chunk_to_doc[cid], score=score) for cid, score in spliced]
    docs = pool_chunks_to_docs(spliced, chunk_to_doc, rule=doc_pooling)
    context = select_distinct_docs(spliced, chunk_to_doc, k=k_docs, candidate_pool=candidate_pool)
    floor = reranker.context_floor
    floor_cut = 0
    if floor is not None:
        # Only reranked chunks have a score on the reranker's scale; the tail was never
        # judged, so it cannot pass a floor. `reranked` is sorted best first, so the
        # filter keeps a prefix and the walk order is unchanged.
        passing = [(c.chunk_id, c.score) for c in reranked if c.score >= floor]
        unfloored = context
        context = select_distinct_docs(passing, chunk_to_doc, k=k_docs, candidate_pool=candidate_pool)
        floor_cut = len(unfloored.doc_ids) - len(context.doc_ids)
    new = RetrievalResult(
        question_id=result.question_id,
        chunks=scored,
        docs=docs,
        doc_pooling=doc_pooling,
        meta={
            **result.meta,
            "reranker": reranker.name,
            "rerank_candidate_docs": n_docs,
            "rerank_candidate_chunks": len(head_chunks),
        },
        context=context,
    )
    after_docs = new.doc_ids[:k_docs]
    record = {
        "rerank_candidate_docs": float(len({chunk_to_doc[cid] for cid in head_ids})),
        "rerank_candidate_chunks": float(len(head_chunks)),
        # How much of the context the reranker replaced: documents in the new top-k
        # that were not in the old one. Zero means it changed nothing for this
        # question, which is a fact worth having per question and not just on average.
        "rerank_topk_changed": float(len(set(after_docs) - set(before_docs))),
    }
    if floor is not None:
        # Documents the floor kept out of the context. A floored question also reads
        # `pool_exhausted` = 1 (fewer than top_k documents); this says why.
        record["context_floor_cut"] = float(floor_cut)
    return new, record
