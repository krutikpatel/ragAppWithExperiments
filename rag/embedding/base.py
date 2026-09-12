"""Embedder interface — P0-11, P1-04.

Text -> vector, with the **input type stated at the call**. The e5 and bge families
are trained with asymmetric prefixes — a query is embedded as `"query: ..."` and a
passage as `"passage: ..."` — and omitting them produces no error, just worse
numbers that then get blamed on the architecture. So `embed_texts` takes
`input_type`, the prefix comes from a table keyed by model family, and a model this
table does not know is an error unless the config names its convention explicitly.
Silence is the failure mode this module is designed to make impossible.

Two backends: `sentence_transformers` (local, the Phase 1 control — re-indexing
6,221 articles takes minutes and needs no network) and `openrouter` (hosted; what
Ragas `answer_relevance` uses via DEC-027). Both apply the same prefix table.
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

InputType = Literal["query", "passage"]


@dataclass(frozen=True)
class PrefixConvention:
    """What is prepended to a query and to a passage for one model family.

    Taken from each family's model card. The card is the only authority here; none
    of these have been measured on this corpus (that would be a Phase 2 question).
    """

    name: str
    query: str
    passage: str

    def apply(self, text: str, input_type: InputType) -> str:
        if input_type == "query":
            return self.query + text
        if input_type == "passage":
            return self.passage + text
        raise ValueError(f"input_type must be 'query' or 'passage', got {input_type!r}")


# Model-id pattern -> convention. First match wins; patterns are matched against the
# id with any provider prefix ("openrouter/", "BAAI/") kept, case-insensitively.
PREFIX_CONVENTIONS: dict[str, PrefixConvention] = {
    "none": PrefixConvention("none", "", ""),
    "e5": PrefixConvention("e5", "query: ", "passage: "),
    "bge-en": PrefixConvention(
        "bge-en", "Represent this sentence for searching relevant passages: ", ""
    ),
    "nomic": PrefixConvention("nomic", "search_query: ", "search_document: "),
    "qwen3": PrefixConvention(
        "qwen3",
        "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: ",
        "",
    ),
}

_FAMILY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)(multilingual-)?e5-", re.I), "e5"),
    (re.compile(r"(^|/)bge-(small|base|large)-en", re.I), "bge-en"),
    (re.compile(r"(^|/)bge-m3", re.I), "none"),
    (re.compile(r"(^|/)nomic-embed-text", re.I), "nomic"),
    (re.compile(r"(^|/)qwen3-embedding", re.I), "qwen3"),
    (re.compile(r"(^|/)gte-(base|large)-en", re.I), "none"),
    (re.compile(r"(^|/)text-embedding-3-", re.I), "none"),
    (re.compile(r"(^|/)all-minilm-", re.I), "none"),
]


def infer_prefix_convention(model_id: str) -> str | None:
    """The convention name for a model id, or None if the family is unknown."""
    for pattern, name in _FAMILY_PATTERNS:
        if pattern.search(model_id):
            return name
    return None


def resolve_prefix_convention(model_id: str, explicit: str | None = None) -> PrefixConvention:
    """Pick the convention: explicit config wins, else inferred, else an error.

    An unknown family with no explicit convention is refused. Defaulting to "no
    prefix" would be exactly the silent degradation P1-04 warns about.
    """
    name = explicit or infer_prefix_convention(model_id)
    if name is None:
        raise ValueError(
            f"no prefix convention known for embedding model {model_id!r}. e5/bge-style "
            "models need query/passage prefixes and omitting them degrades silently. Set "
            f"`prefix_convention` explicitly to one of {sorted(PREFIX_CONVENTIONS)} — "
            "'none' if the model card says no prefix is needed."
        )
    if name not in PREFIX_CONVENTIONS:
        raise ValueError(f"unknown prefix_convention {name!r}; known: {sorted(PREFIX_CONVENTIONS)}")
    return PREFIX_CONVENTIONS[name]


@dataclass(frozen=True)
class EmbedderConfig:
    model: str
    # Exact model revision (HF commit sha for local models). Pinned, never floating,
    # so a silently updated model cannot invalidate comparisons unseen (CLAUDE.md §10).
    revision: str = ""
    prefix_convention: str | None = None
    batch_size: int = 64
    timeout_s: float = 60.0
    # sentence-transformers only. Recorded in provenance; not part of the index key.
    device: str | None = None
    # sentence-transformers only. The model's own limit applies if None.
    max_seq_length: int | None = None


class Embedder(ABC):
    """Text -> vector. `embed_texts` is the batch primitive; `embed_text` wraps it."""

    name: str

    def __init__(self, config: EmbedderConfig) -> None:
        if not config.model:
            raise ValueError(
                "no embedding model configured. Model choice is Krutik's — see "
                "CLAUDE.md section 10 and DEC-027."
            )
        self.config = config
        self.prefix = resolve_prefix_convention(config.model, config.prefix_convention)

    @abstractmethod
    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Backend call on already-prefixed texts. One vector per input, in order."""

    def embed_texts(self, texts: list[str], *, input_type: InputType) -> list[list[float]]:
        """Embed with the family's prefix for `input_type` applied to every text."""
        prefixed = [self.prefix.apply(t, input_type) for t in texts]
        vectors = self._embed(prefixed)
        if len(vectors) != len(texts):
            raise RuntimeError(f"embedder returned {len(vectors)} vectors for {len(texts)} inputs")
        return vectors

    def embed_text(self, text: str, *, input_type: InputType) -> list[float]:
        return self.embed_texts([text], input_type=input_type)[0]

    @property
    def model_id(self) -> str:
        return self.config.model

    def provenance(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "model_id": self.config.model,
            "revision": self.config.revision,
            "prefix_convention": self.prefix.name,
            "query_prefix": self.prefix.query,
            "passage_prefix": self.prefix.passage,
        }


class OpenRouterEmbedder(Embedder):
    name = "openrouter"

    def _embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. It lives in .env at the repo root."
            )
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.config.batch_size):
            batch = texts[start : start + self.config.batch_size]
            response = httpx.post(
                OPENROUTER_EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": self.config.model, "input": batch},
                timeout=self.config.timeout_s,
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda d: d["index"])
            if len(data) != len(batch):
                raise RuntimeError(
                    f"embeddings API returned {len(data)} vectors for {len(batch)} inputs"
                )
            vectors.extend(d["embedding"] for d in data)
        return vectors


class SentenceTransformersEmbedder(Embedder):
    """Local model via `sentence-transformers`. Loaded lazily, at a pinned revision."""

    name = "sentence_transformers"

    def __init__(self, config: EmbedderConfig) -> None:
        super().__init__(config)
        if not config.revision:
            raise ValueError(
                f"embedding model {config.model!r} needs an exact `revision` (HF commit sha). "
                "A floating alias can change underneath a comparison family."
            )
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.config.model, revision=self.config.revision, device=self.config.device
            )
            if self.config.max_seq_length is not None:
                self._model.max_seq_length = self.config.max_seq_length
        return self._model

    @property
    def max_seq_length(self) -> int:
        return int(self._load().max_seq_length)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(
            texts,
            batch_size=self.config.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [row.tolist() for row in vectors]

    def provenance(self) -> dict[str, Any]:
        meta = super().provenance()
        model = self._load()
        meta["device"] = str(model.device)
        meta["max_seq_length"] = int(model.max_seq_length)
        meta["embedding_dim"] = int(model.get_sentence_embedding_dimension())
        return meta


BACKENDS: dict[str, type[Embedder]] = {
    OpenRouterEmbedder.name: OpenRouterEmbedder,
    SentenceTransformersEmbedder.name: SentenceTransformersEmbedder,
}


def build_embedder(backend: str, config: EmbedderConfig) -> Embedder:
    if backend not in BACKENDS:
        raise KeyError(f"unknown embedding backend {backend!r}; known: {sorted(BACKENDS)}")
    return BACKENDS[backend](config)
