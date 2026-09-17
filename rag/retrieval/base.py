"""Retriever interface — P0-05, P1-03.

Every retriever returns ranked chunks *and* the ranked document list produced by
the pooling rule. Returning only chunks would push pooling into the metrics code,
where a run could quietly use a different rule than the one it recorded.

Since P1-03 it also returns the generator's context as a `DocSelection`: `k`
distinct documents, found by walking the ranking, not the first `k` chunks. The
two are different things on this corpus — adjacent chunks of one long article
collapse into one document — and the difference is recorded per question as the
collapse ratio.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rag.retrieval.pooling import (
    DEFAULT_POOLING,
    DocSelection,
    pool_chunks_to_docs,
    select_distinct_docs,
)

if TYPE_CHECKING:
    from rag.chunking.index_map import ChunkIndex
    from rag.generation.cache import GenerationCache
    from rag.generation.pipeline_llm import PipelineLLM


@dataclass(frozen=True)
class ScoredChunk:
    chunk_id: str
    doc_id: str
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    """One query's retrieval output, at both granularities."""

    question_id: str
    chunks: list[ScoredChunk]
    docs: list[tuple[str, float]]
    doc_pooling: str = DEFAULT_POOLING
    meta: dict = field(default_factory=dict)
    # The generator's context: k distinct documents (P1-03). None only for callers
    # that asked for a ranking alone.
    context: DocSelection | None = None

    @property
    def doc_ids(self) -> list[str]:
        return [doc_id for doc_id, _ in self.docs]

    @property
    def chunk_ids(self) -> list[str]:
        return [c.chunk_id for c in self.chunks]

    @property
    def context_chunks(self) -> list[ScoredChunk]:
        """One `ScoredChunk` per selected document, in rank order."""
        if self.context is None:
            return []
        by_id = {c.chunk_id: c for c in self.chunks}
        return [by_id[cid] for cid, _ in self.context.chunks]


class Retriever(ABC):
    """Ranks chunks for a query, then pools them to documents."""

    name: str
    # Set by retrievers that call an LLM inside retrieval (query transforms,
    # LLM-as-reranker, agentic loops). The runner reads its stats, records the cache
    # hit rate and marks the run `pipeline_nondeterministic` (P2-03).
    pipeline_llm: PipelineLLM | None = None

    def __init__(
        self,
        chunk_to_doc: dict[str, str],
        *,
        doc_pooling: str = DEFAULT_POOLING,
        index: ChunkIndex | None = None,
        generation_cache: GenerationCache | None = None,
    ) -> None:
        self.chunk_to_doc = chunk_to_doc
        self.doc_pooling = doc_pooling
        # The index's provenance (corpus hash, normalization, chunker id). Retrievers
        # that build something expensive from the chunks key it on this.
        self.index = index
        # The runner hands every retriever the generation cache; only those that
        # call an LLM inside retrieval build a `PipelineLLM` on it (P2-03).
        self.generation_cache = generation_cache

    @abstractmethod
    def search(self, query: str, *, top_k: int) -> list[tuple[str, float]]:
        """Return ranked (chunk_id, score), best first."""

    @classmethod
    def embedding_params(cls, retriever_params: dict[str, Any]) -> dict[str, Any] | None:
        """The embedder settings this retriever would build from `retriever_params`,
        or None when it embeds nothing. The runner asks this *before* the retriever
        exists, to check the index on disk and estimate the build (P2-06) — keyed on
        the class rather than on the name "dense", so a retriever that wraps a dense
        one (hybrid, P2-09) is costed the same way and never read as free."""
        return None

    def provenance(self) -> dict[str, Any]:
        """What this retriever was built from, recorded on the run row. Empty when
        there is nothing beyond the chunk index itself (BM25 is rebuilt in-process)."""
        return {}

    def query_cost_usd(self) -> float:
        """Money spent answering queries so far, excluding any index build. Zero for
        anything in-process; a hosted embedder reports what the provider charged."""
        return 0.0

    def retrieve(
        self,
        question_id: str,
        query: str,
        *,
        top_k: int,
        k_docs: int | None = None,
        candidate_pool: int | None = None,
    ) -> RetrievalResult:
        """Rank `top_k` chunks for scoring; select `k_docs` distinct documents for context.

        `top_k` is the scoring depth (DEC-012). `k_docs` is the document-level k of
        P1-03; when given, the walk scans at most `candidate_pool` chunks of the
        ranking (default: all of it) and the selection is attached as `context`.
        """
        ranked = self.search(query, top_k=top_k)
        scored = [
            ScoredChunk(chunk_id=cid, doc_id=self.chunk_to_doc[cid], score=score)
            for cid, score in ranked
        ]
        docs = pool_chunks_to_docs(ranked, self.chunk_to_doc, rule=self.doc_pooling)
        context = None
        if k_docs is not None:
            context = select_distinct_docs(
                ranked, self.chunk_to_doc, k=k_docs, candidate_pool=candidate_pool or len(ranked) or k_docs
            )
        return RetrievalResult(
            question_id=question_id,
            chunks=scored,
            docs=docs,
            doc_pooling=self.doc_pooling,
            meta={"retriever": self.name, "top_k": top_k},
            context=context,
        )
