"""Retriever interface — P0-05.

Every retriever returns ranked chunks *and* the ranked document list produced by
the pooling rule. Returning only chunks would push pooling into the metrics code,
where a run could quietly use a different rule than the one it recorded.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from rag.retrieval.pooling import DEFAULT_POOLING, pool_chunks_to_docs


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

    @property
    def doc_ids(self) -> list[str]:
        return [doc_id for doc_id, _ in self.docs]

    @property
    def chunk_ids(self) -> list[str]:
        return [c.chunk_id for c in self.chunks]


class Retriever(ABC):
    """Ranks chunks for a query, then pools them to documents."""

    name: str

    def __init__(self, chunk_to_doc: dict[str, str], *, doc_pooling: str = DEFAULT_POOLING) -> None:
        self.chunk_to_doc = chunk_to_doc
        self.doc_pooling = doc_pooling

    @abstractmethod
    def search(self, query: str, *, top_k: int) -> list[tuple[str, float]]:
        """Return ranked (chunk_id, score), best first."""

    def retrieve(self, question_id: str, query: str, *, top_k: int) -> RetrievalResult:
        ranked = self.search(query, top_k=top_k)
        scored = [
            ScoredChunk(chunk_id=cid, doc_id=self.chunk_to_doc[cid], score=score)
            for cid, score in ranked
        ]
        docs = pool_chunks_to_docs(ranked, self.chunk_to_doc, rule=self.doc_pooling)
        return RetrievalResult(
            question_id=question_id,
            chunks=scored,
            docs=docs,
            doc_pooling=self.doc_pooling,
            meta={"retriever": self.name, "top_k": top_k},
        )
