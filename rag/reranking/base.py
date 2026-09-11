"""Reranker interface — P0-11. Interface only.

Phase 0 ships no reranker on purpose: the baseline must be the dumbest thing that
works, and a reranker is technique work. `tests/test_interfaces.py` asserts that no
concrete subclass exists in this package, so one cannot slip in without a story and a
decision entry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from rag.retrieval.base import ScoredChunk


class Reranker(ABC):
    """Re-orders retrieved chunks for a query. Must not add or drop chunks."""

    name: str

    @abstractmethod
    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        """Return the same chunks, re-scored and re-ordered, best first."""
