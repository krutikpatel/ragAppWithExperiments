"""Dense retrieval — P1-04. One embedding model, cosine over normalized vectors.

The index is a numpy matrix, one row per chunk, in sorted `chunk_id` order. It is
built once per **provenance tuple** — `(corpus_hash, normalization_version,
chunker_id, model_id, pinned_identity, prefix_convention)` — where the pinned identity
is an HF revision for a local model or the provider for a hosted one — and cached under `indexes/`
by a key derived from nothing but that tuple. Anything that changes a vector is in
the tuple; anything that does not (device, batch size) is recorded in the index's
metadata but does not change the key. Build time and size are logged and land on
the run row through `provenance()`.

No FAISS: 8,218 chunks is a matrix-vector product, and a brute-force search has no
approximation to record.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from rag.embedding.base import EmbedderConfig, build_embedder
from rag.hashing import short_id
from rag.paths import INDEXES_DIR
from rag.retrieval.base import Retriever
from rag.runner.registry import register_retriever

VECTORS_FILE = "vectors.npy"
INDEX_META_FILE = "index.meta.json"


def index_key(
    *,
    corpus_hash: str,
    normalization_version: str,
    chunker_id: str,
    model_id: str,
    revision: str,
    prefix_convention: str,
    dimensions: int | None = None,
) -> str:
    """The identity of a dense index. Deterministic in the P1-04 tuple and nothing else.

    `dimensions` (P2-08 run 5) joins the tuple only when set, so every key built
    before it existed is unchanged.
    """
    parts = [corpus_hash, normalization_version, chunker_id, model_id, revision, prefix_convention]
    if dimensions:
        parts.append(f"dim:{dimensions}")
    return short_id(*parts, length=16)


@register_retriever("dense")
class DenseRetriever(Retriever):
    name = "dense"

    def __init__(
        self,
        chunk_to_doc: dict[str, str],
        chunk_text: dict[str, str],
        *,
        embedding_backend: str = "openrouter",
        embedding_model: str = "",
        embedding_revision: str = "",
        embedding_provider: str = "",
        prefix_convention: str | None = None,
        batch_size: int = 64,
        device: str | None = None,
        max_seq_length: int | None = None,
        dimensions: int | None = None,
        index_dir: Path | str | None = None,
        embedder: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunk_to_doc, **kwargs)
        if self.index is None:
            raise ValueError(
                "DenseRetriever needs the ChunkIndex (`index=`) for its provenance: the "
                "vector cache is keyed on corpus hash, normalization and chunker id."
            )
        self.embedder = embedder or build_embedder(
            embedding_backend,
            EmbedderConfig(
                model=embedding_model,
                revision=embedding_revision,
                provider=embedding_provider,
                prefix_convention=prefix_convention,
                batch_size=batch_size,
                device=device,
                max_seq_length=max_seq_length,
                dimensions=dimensions,
            ),
        )
        self.chunk_ids = sorted(chunk_text)
        self.key = index_key(
            corpus_hash=self.index.corpus_hash,
            normalization_version=self.index.normalization_version,
            chunker_id=self.index.chunker_id,
            model_id=self.embedder.model_id,
            revision=self.embedder.pinned_identity,
            prefix_convention=self.embedder.prefix.name,
            dimensions=self.embedder.config.dimensions,
        )
        self.index_dir = Path(index_dir) if index_dir else INDEXES_DIR / self.key
        self.vectors, self.index_meta = self._load_or_build(chunk_text)
        # Whatever the embedder had spent once the index existed is the build's;
        # everything after is queries.
        self._build_cost_usd = self._usage_cost()

    def _usage_cost(self) -> float:
        usage = getattr(self.embedder, "usage", None)
        return float(usage.cost_usd) if usage is not None else 0.0

    def query_cost_usd(self) -> float:
        return self._usage_cost() - self._build_cost_usd

    # --- index -----------------------------------------------------------------

    def _load_or_build(self, chunk_text: dict[str, str]) -> tuple[np.ndarray, dict[str, Any]]:
        vectors_path = self.index_dir / VECTORS_FILE
        meta_path = self.index_dir / INDEX_META_FILE
        if vectors_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("key") == self.key and meta.get("chunk_ids_hash") == self._chunk_ids_hash():
                vectors = np.load(vectors_path)
                if vectors.shape[0] == len(self.chunk_ids):
                    meta["cache_hit"] = True
                    return vectors, meta
        return self._build(chunk_text)

    def _chunk_ids_hash(self) -> str:
        return short_id(*self.chunk_ids, length=16)

    def _build(self, chunk_text: dict[str, str]) -> tuple[np.ndarray, dict[str, Any]]:
        started = time.perf_counter()
        texts = [chunk_text[cid] for cid in self.chunk_ids]
        rows = self.embedder.embed_texts(texts, input_type="passage")
        vectors = np.asarray(rows, dtype=np.float32)
        vectors = _normalize(vectors)
        build_seconds = time.perf_counter() - started

        self.index_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.index_dir / VECTORS_FILE, vectors)
        meta = {
            "key": self.key,
            "corpus_hash": self.index.corpus_hash,
            "normalization_version": self.index.normalization_version,
            "chunker_id": self.index.chunker_id,
            "chunker_params": self.index.chunker_params,
            "chunk_ids_hash": self._chunk_ids_hash(),
            "n_vectors": int(vectors.shape[0]),
            "embedding_dim": int(vectors.shape[1]),
            "dtype": str(vectors.dtype),
            "size_bytes": int(vectors.nbytes),
            "build_seconds": round(build_seconds, 2),
            "embedder": self.embedder.provenance(),
            "cache_hit": False,
        }
        (self.index_dir / INDEX_META_FILE).write_text(json.dumps(meta, indent=2) + "\n")
        return vectors, meta

    # --- retrieval -------------------------------------------------------------

    @property
    def params(self) -> dict[str, Any]:
        return {
            "embedding_backend": self.embedder.name,
            "embedding_model": self.embedder.model_id,
            "pinned_identity": self.embedder.pinned_identity,
            "prefix_convention": self.embedder.prefix.name,
            "similarity": "cosine",
        }

    def provenance(self) -> dict[str, Any]:
        """Recorded on the run row: the P1-04 tuple, build time and size."""
        return {
            "index_key": self.key,
            "index_dir": str(self.index_dir),
            "corpus_hash": self.index.corpus_hash,
            "normalization_version": self.index.normalization_version,
            "chunker_id": self.index.chunker_id,
            "chunker_params": self.index.chunker_params,
            "n_vectors": self.index_meta["n_vectors"],
            "embedding_dim": self.index_meta["embedding_dim"],
            "size_bytes": self.index_meta["size_bytes"],
            "build_seconds": self.index_meta["build_seconds"],
            "cache_hit": self.index_meta.get("cache_hit", False),
            "embedder": self.index_meta["embedder"],
            "embedder_now": self.embedder.provenance(),
            "similarity": "cosine",
        }

    def search(self, query: str, *, top_k: int) -> list[tuple[str, float]]:
        if not query.strip() or not self.chunk_ids:
            return []
        q = np.asarray(self.embedder.embed_text(query, input_type="query"), dtype=np.float32)
        q = _normalize(q[None, :])[0]
        scores = self.vectors @ q
        k = min(top_k, len(self.chunk_ids))
        # argpartition for the candidate set, then a full sort with chunk_id as the
        # tie-breaker so the ranking is reproducible (MIS-003).
        candidates = np.argpartition(-scores, k - 1)[:k] if k < len(scores) else np.arange(len(scores))
        ranked = sorted(
            ((self.chunk_ids[i], float(scores[i])) for i in candidates), key=lambda item: (-item[1], item[0])
        )
        return ranked[:k]


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms
