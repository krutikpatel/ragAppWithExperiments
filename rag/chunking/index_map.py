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

    def __len__(self) -> int:
        return len(self.chunks)

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        pd.DataFrame.from_records(
            chunks_to_records(self.chunks),
            columns=["chunk_id", "doc_id", "ordinal", "text"],
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
