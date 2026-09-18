"""Semantic chunking — P2-07 (c).

Cut where the topic changes, not every N words. Each article's sentences are
embedded, the cosine distance between each consecutive pair is taken, and a chunk
boundary is placed after every sentence whose distance to the next one is above
the article's own `threshold_percentile` of those distances (the breakpoint rule
popularised by LangChain's SemanticChunker; 95 by default). A group that ends up
longer than `max_words` is cut at `max_words` so no chunk exceeds the control's
size. No overlap.

What this costs and what it depends on:

- **Every sentence in the corpus is embedded once** to find the boundaries (about
  118k sentences, the same ~3M tokens as one index build). That happens *before*
  the chunks exist, so the runner estimates and gates it as a pre-spend
  (`embedding_params`), the way it does the dense index.
- **The boundaries depend on the embedding model and provider**, so both are part
  of this chunker's identity (`params` → `chunker_id`). Hosted query vectors are not
  byte-deterministic (OQ-023); a cold recomputation could move a boundary. The
  consecutive-sentence distances are therefore cached on disk per article text
  (`indexes/sentence_distances/<embedder key>.json`), keyed on nothing but the
  embedder identity and the text, so once measured the chunks are reproducible
  from the cache. The cache hit rate and the embedding spend are recorded in
  `provenance()`.
- The sentence splitter is `rag.chunking.sentences` (the glued-boundary aware one).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from rag.chunking.base import Chunk, Chunker, register_chunker
from rag.chunking.sentences import split_sentences
from rag.embedding.base import EmbedderConfig, build_embedder
from rag.hashing import short_id
from rag.paths import INDEXES_DIR

DISTANCES_DIR_NAME = "sentence_distances"


def breakpoints(distances: list[float], percentile: float) -> list[int]:
    """Indices i such that a boundary falls after sentence i. Empty when there are
    fewer than two distances — a one- or two-sentence article is one chunk."""
    if len(distances) < 2:
        return []
    cut = float(np.percentile(np.asarray(distances, dtype=np.float64), percentile))
    return [i for i, d in enumerate(distances) if d > cut]


def group_sentences(sentences: list[str], cuts: list[int]) -> list[list[str]]:
    groups: list[list[str]] = []
    start = 0
    for i in cuts:
        groups.append(sentences[start : i + 1])
        start = i + 1
    groups.append(sentences[start:])
    return [g for g in groups if g]


@register_chunker("semantic")
class SemanticChunker(Chunker):
    def __init__(
        self,
        *,
        threshold_percentile: float = 95.0,
        max_words: int = 600,
        embedding_backend: str = "openrouter",
        embedding_model: str = "",
        embedding_provider: str = "",
        embedding_revision: str = "",
        prefix_convention: str | None = None,
        batch_size: int = 256,
        embedder: Any | None = None,
        cache_dir: Path | str | None = None,
    ) -> None:
        if not 0 < threshold_percentile <= 100:
            raise ValueError("threshold_percentile must be in (0, 100]")
        if max_words <= 0:
            raise ValueError("max_words must be positive")
        self.threshold_percentile = float(threshold_percentile)
        self.max_words = max_words
        self.embedder = embedder or build_embedder(
            embedding_backend,
            EmbedderConfig(
                model=embedding_model,
                revision=embedding_revision,
                provider=embedding_provider,
                prefix_convention=prefix_convention,
                batch_size=batch_size,
            ),
        )
        self.embedder_key = short_id(
            self.embedder.model_id, self.embedder.pinned_identity, self.embedder.prefix.name, length=16
        )
        self.cache_dir = Path(cache_dir) if cache_dir else INDEXES_DIR / DISTANCES_DIR_NAME
        self.cache_path = self.cache_dir / f"{self.embedder_key}.json"
        self._cache: dict[str, list[float]] = self._load_cache()
        self._dirty = False
        self.stats = {"docs": 0, "cache_hits": 0, "sentences_embedded": 0, "embed_seconds": 0.0}
        self._spent_before = self._usage_cost()

    @classmethod
    def embedding_params(cls, chunker_params: dict[str, Any]) -> dict[str, Any] | None:
        """What this chunker embeds before any chunk exists (the runner gates it)."""
        return {k: v for k, v in chunker_params.items() if k.startswith("embedding_") or k == "prefix_convention"}

    @property
    def params(self) -> dict[str, Any]:
        return {
            "threshold_percentile": self.threshold_percentile,
            "max_words": self.max_words,
            "unit": "sentence",
            "splitter": "sentences-v1",
            "distance": "1 - cosine, consecutive sentences",
            "embedding_model": self.embedder.model_id,
            "pinned_identity": self.embedder.pinned_identity,
            "prefix_convention": self.embedder.prefix.name,
        }

    # --- cache ---------------------------------------------------------------------

    def _load_cache(self) -> dict[str, list[float]]:
        if self.cache_path.exists():
            return json.loads(self.cache_path.read_text())
        return {}

    def save_cache(self) -> None:
        if self._dirty:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache))
            self._dirty = False

    def _usage_cost(self) -> float:
        usage = getattr(self.embedder, "usage", None)
        return float(usage.cost_usd) if usage is not None else 0.0

    def provenance(self) -> dict[str, Any]:
        return {
            "sentence_distance_cache": str(self.cache_path),
            "embedder": self.embedder.provenance(),
            "embedding_cost_usd": round(self._usage_cost() - self._spent_before, 6),
            **self.stats,
        }

    # --- distances -------------------------------------------------------------------

    @staticmethod
    def _text_key(text: str) -> str:
        return short_id(text, length=24)

    # Sentences embedded per provider round-trip group; bounds memory (118k × 4096
    # float32 at once would be 1.9 GB) and lets the cache be saved as it fills, so a
    # failed build keeps what it paid for.
    GROUP_SENTENCES = 4096

    def _distances_for(self, docs: list[tuple[str, str, list[str]]]) -> dict[str, list[float]]:
        """Consecutive-sentence distances per doc key, embedding only what the cache
        lacks, in bounded groups."""
        out: dict[str, list[float]] = {}
        missing: list[tuple[str, list[str]]] = []
        for _doc_id, key, sentences in docs:
            if key in self._cache:
                out[key] = self._cache[key]
                self.stats["cache_hits"] += 1
            elif len(sentences) < 3:
                # Fewer than two distances: `breakpoints` can never cut, so there
                # is nothing to embed.
                out[key] = []
            else:
                missing.append((key, sentences))
        group: list[tuple[str, list[str]]] = []
        pending = 0
        for item in missing:
            group.append(item)
            pending += len(item[1])
            if pending >= self.GROUP_SENTENCES:
                out.update(self._embed_group(group))
                group, pending = [], 0
        if group:
            out.update(self._embed_group(group))
        return out

    def _embed_group(self, group: list[tuple[str, list[str]]]) -> dict[str, list[float]]:
        flat = [s for _, sents in group for s in sents]
        started = time.perf_counter()
        vectors = np.asarray(self.embedder.embed_texts(flat, input_type="passage"), dtype=np.float32)
        self.stats["embed_seconds"] = round(self.stats["embed_seconds"] + time.perf_counter() - started, 2)
        self.stats["sentences_embedded"] += len(flat)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vectors = vectors / norms
        out: dict[str, list[float]] = {}
        pos = 0
        for key, sents in group:
            v = vectors[pos : pos + len(sents)]
            pos += len(sents)
            sims = np.sum(v[:-1] * v[1:], axis=1)
            dists = [round(float(1.0 - s), 6) for s in sims]
            self._cache[key] = dists
            out[key] = dists
        self._dirty = True
        self.save_cache()
        return out

    # --- chunking --------------------------------------------------------------------

    def _chunks_from_groups(self, doc_id: str, groups: list[list[str]]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for group in groups:
            tokens = " ".join(group).split()
            for start in range(0, len(tokens), self.max_words):
                chunks.append(self.make_chunk(doc_id, len(chunks), " ".join(tokens[start : start + self.max_words])))
        return chunks

    def split(self, doc_id: str, text: str) -> list[Chunk]:
        return self.split_corpus([(doc_id, text)])

    def split_corpus(self, docs: list[tuple[str, str]]) -> list[Chunk]:
        prepared = [(doc_id, self._text_key(text), split_sentences(text)) for doc_id, text in docs]
        distances = self._distances_for(prepared)
        self.save_cache()
        chunks: list[Chunk] = []
        for doc_id, key, sentences in prepared:
            if not sentences:
                continue
            self.stats["docs"] += 1
            cuts = breakpoints(distances[key], self.threshold_percentile)
            chunks.extend(self._chunks_from_groups(doc_id, group_sentences(sentences, cuts)))
        return chunks
