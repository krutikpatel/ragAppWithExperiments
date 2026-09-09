"""Context assembly — retrieved chunks into the generator's prompt.

The document id is printed in each article header because the generator is asked to
cite `[doc:<id>]`, and citation precision is scored against those ids with no LLM
call. If the id were not in the context, the citation metric could not exist.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from rag.retrieval.base import ScoredChunk


@dataclass(frozen=True)
class AssembledContext:
    text: str
    doc_ids: list[str]
    n_chunks: int
    truncated: bool


class ContextAssembler(ABC):
    name: str

    @abstractmethod
    def assemble(self, chunks: list[ScoredChunk], chunk_text: dict[str, str]) -> AssembledContext:
        ...


class ConcatAssembler(ContextAssembler):
    """Chunks in rank order, each headed by its document id, to a token budget."""

    name = "concat"

    def __init__(self, max_tokens: int = 6000) -> None:
        self.max_tokens = max_tokens

    def assemble(self, chunks: list[ScoredChunk], chunk_text: dict[str, str]) -> AssembledContext:
        parts: list[str] = []
        doc_ids: list[str] = []
        budget = self.max_tokens
        truncated = False

        for chunk in chunks:
            text = chunk_text[chunk.chunk_id]
            cost = len(text.split())
            if cost > budget:
                truncated = True
                break
            parts.append(f"--- ARTICLE [doc:{chunk.doc_id}] ---\n{text}")
            if chunk.doc_id not in doc_ids:
                doc_ids.append(chunk.doc_id)
            budget -= cost

        return AssembledContext(
            text="\n\n".join(parts),
            doc_ids=doc_ids,
            n_chunks=len(parts),
            truncated=truncated,
        )
