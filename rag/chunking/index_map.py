"""The persisted chunk→document mapping — P0-05.

An index without its mapping cannot be scored, so the two are written and read
together. `ChunkIndex.save` is what every future index builder must call; nothing
should reconstruct the mapping by re-chunking, because that would silently depend
on the chunker settings still being identical.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from rag.chunking.base import Chunk, chunks_to_records

CHUNKS_FILE = "chunks.parquet"
MAP_META_FILE = "chunk_map.meta.json"


@dataclass(frozen=True, eq=False)
class ChunkIndex:
    """Chunks plus the provenance needed to score them against document qrels."""

    chunks: list[Chunk]
    chunker_id: str
    chunker_params: dict[str, Any]
    corpus_hash: str
    normalization_version: str

    @property
    def chunk_to_doc(self) -> dict[str, str]:
        return {c.chunk_id: c.doc_id for c in self.chunks}

    @property
    def doc_ids(self) -> set[str]:
        return {c.doc_id for c in self.chunks}

    @property
    def chunk_text(self) -> dict[str, str]:
        """What the retriever indexes."""
        return {c.chunk_id: c.text for c in self.chunks}

    @property
    def context_text(self) -> dict[str, str]:
        """What the generator sees per chunk (P2-07); equals `chunk_text` unless the
        chunker expands the context."""
        return {c.chunk_id: c.context for c in self.chunks}

    def profile(self, docs: dict[str, str]) -> dict[str, Any]:
        """The chunking characterisation P2-07 reports for every config: how many
        chunks, how long, how many articles fit in one, and how many procedure
        blocks (DEC-039) no single chunk contains. Computed on `text`, the indexed
        unit, against the document text in `docs`."""
        from rag.chunking.profile import profile_chunks

        return profile_chunks(self.chunks, docs)

    def __len__(self) -> int:
        return len(self.chunks)

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        pd.DataFrame.from_records(
            chunks_to_records(self.chunks),
            columns=["chunk_id", "doc_id", "ordinal", "text", "context_text"],
        ).to_parquet(directory / CHUNKS_FILE, index=False)
        meta = {
            "chunker_id": self.chunker_id,
            "chunker_params": self.chunker_params,
            "corpus_hash": self.corpus_hash,
            "normalization_version": self.normalization_version,
            "n_chunks": len(self.chunks),
            "n_documents": len(self.doc_ids),
        }
        (directory / MAP_META_FILE).write_text(json.dumps(meta, indent=2) + "\n")
        return directory

    @classmethod
    def load(cls, directory: Path) -> ChunkIndex:
        meta = json.loads((directory / MAP_META_FILE).read_text())
        frame = pd.read_parquet(directory / CHUNKS_FILE)
        chunks = [
            Chunk(
                chunk_id=row.chunk_id,
                doc_id=row.doc_id,
                ordinal=int(row.ordinal),
                text=row.text,
                # Parquet reads a missing string back as None or NaN; only a real
                # string is an expanded context.
                context_text=(ct if isinstance(ct := getattr(row, "context_text", None), str) else None),
            )
            for row in frame.itertuples()
        ]
        return cls(
            chunks=chunks,
            chunker_id=meta["chunker_id"],
            chunker_params=meta["chunker_params"],
            corpus_hash=meta["corpus_hash"],
            normalization_version=meta["normalization_version"],
        )
