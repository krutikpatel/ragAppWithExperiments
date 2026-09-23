"""A deliberately trivial reranker, for exercising the harness — P2-10.

`toy_reverse` reverses the candidate order. It is not a technique and its numbers
must never reach `docs/EXPERIMENTS.md`; it exists so the rerank path — document-level
candidate selection, splicing, re-pooling, the recomputed collapse ratio, the run row
— can be tested end to end without spending money or depending on a provider.

Any run using it must set `harness_smoke_test=True`.
"""

from __future__ import annotations

from rag.reranking.base import Reranker, check_same_chunks
from rag.retrieval.base import ScoredChunk
from rag.runner.registry import register_reranker


@register_reranker("toy_reverse")
class ToyReverseReranker(Reranker):
    name = "toy_reverse"

    def rerank(
        self, query: str, chunks: list[ScoredChunk], *, question_id: str = ""
    ) -> list[ScoredChunk]:
        reversed_chunks = [
            ScoredChunk(chunk_id=c.chunk_id, doc_id=c.doc_id, score=float(rank))
            for rank, c in enumerate(reversed(chunks))
        ]
        self.usage.calls += 1
        self.usage.candidates += len(chunks)
        check_same_chunks(chunks, reversed_chunks)
        return reversed_chunks
