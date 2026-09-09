"""Chunking — the `chunk_id → doc_id` half of P0-05.

Ground truth in WixQA is document-level; retrieval is chunk-level. Every chunk a
`Chunker` emits therefore carries the document it came from, and that mapping is
persisted with the index rather than re-derived. `chunk_id` is an opaque hash on
purpose: no code should recover a `doc_id` by parsing a chunk id.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from rag.hashing import canonical_json, short_id


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    ordinal: int
    text: str


class Chunker(ABC):
    """Splits a document's indexed text into chunks."""

    name: str

    @property
    @abstractmethod
    def params(self) -> dict[str, Any]:
        """Config-visible parameters. Part of the chunker's identity."""

    @property
    def chunker_id(self) -> str:
        """Stable identity for this chunker and its settings."""
        return f"{self.name}-{short_id(self.name, canonical_json(self.params), length=8)}"

    @abstractmethod
    def split(self, doc_id: str, text: str) -> list[Chunk]:
        """Split one document. Implementations must produce contiguous ordinals."""

    def make_chunk(self, doc_id: str, ordinal: int, text: str) -> Chunk:
        return Chunk(
            chunk_id=short_id(self.chunker_id, doc_id, str(ordinal)),
            doc_id=doc_id,
            ordinal=ordinal,
            text=text,
        )

    def split_corpus(self, docs: list[tuple[str, str]]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for doc_id, text in docs:
            chunks.extend(self.split(doc_id, text))
        return chunks


class FixedTokenChunker(Chunker):
    """Fixed-width chunks over whitespace tokens.

    The unit is a whitespace-delimited token, not a model tokenizer token. That is
    a deliberate Phase 0 choice: it keeps chunking independent of which embedding
    model is in play, so a model swap cannot silently reshape the index. It also
    means `chunk_size=512` is roughly 380-400 BPE tokens, not 512. See
    docs/DECISIONS.md DEC-005.
    """

    name = "fixed_token"

    def __init__(self, chunk_size: int = 512, overlap: int = 0) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= overlap < chunk_size:
            raise ValueError("overlap must be >= 0 and < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    @property
    def params(self) -> dict[str, Any]:
        return {"chunk_size": self.chunk_size, "overlap": self.overlap}

    def split(self, doc_id: str, text: str) -> list[Chunk]:
        tokens = text.split()
        if not tokens:
            return []
        stride = self.chunk_size - self.overlap
        chunks: list[Chunk] = []
        for ordinal, start in enumerate(range(0, len(tokens), stride)):
            window = tokens[start : start + self.chunk_size]
            if not window:
                break
            chunks.append(self.make_chunk(doc_id, ordinal, " ".join(window)))
            if start + self.chunk_size >= len(tokens):
                break
        return chunks


def chunks_to_records(chunks: list[Chunk]) -> list[dict[str, Any]]:
    return [asdict(c) for c in chunks]
