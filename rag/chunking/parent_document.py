"""Parent-document (small-to-big) chunking — P2-07 (b).

Each article is cut into parents of `parent_size` words, and each parent into
children of `child_size` words. The children are what the retriever indexes and
scores (`text`); the parent is what the generator sees (`context_text`). Neither
level overlaps: an overlapping parent would make a child belong to two parents,
and the whole point is that a child has exactly one context.

The control (600/100) gives the generator 600-word chunks. `parent_size` defaults
to 600 so the generator's context is the same size as the control's and only the
retrieval unit changes. Children of 150 words: four per full parent. One
configuration, per P2-07.
"""

from __future__ import annotations

from typing import Any

from rag.chunking.base import Chunk, Chunker, register_chunker


@register_chunker("parent_document")
class ParentDocumentChunker(Chunker):
    def __init__(self, parent_size: int = 600, child_size: int = 150) -> None:
        if parent_size <= 0 or child_size <= 0:
            raise ValueError("parent_size and child_size must be positive")
        if child_size > parent_size:
            raise ValueError("child_size must not exceed parent_size")
        self.parent_size = parent_size
        self.child_size = child_size

    @property
    def params(self) -> dict[str, Any]:
        return {"parent_size": self.parent_size, "child_size": self.child_size, "overlap": 0}

    def split(self, doc_id: str, text: str) -> list[Chunk]:
        tokens = text.split()
        chunks: list[Chunk] = []
        ordinal = 0
        for p_start in range(0, len(tokens), self.parent_size):
            parent = tokens[p_start : p_start + self.parent_size]
            parent_text = " ".join(parent)
            for c_start in range(0, len(parent), self.child_size):
                child = parent[c_start : c_start + self.child_size]
                chunks.append(self.make_chunk(doc_id, ordinal, " ".join(child), parent_text))
                ordinal += 1
        return chunks
