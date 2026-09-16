"""Embedder interface — P0-11, P1-04.

Text -> vector, with the **input type stated at the call**. The e5 and bge families
are trained with asymmetric prefixes — a query is embedded as `"query: ..."` and a
passage as `"passage: ..."` — and omitting them produces no error, just worse
numbers that then get blamed on the architecture. So `embed_texts` takes
`input_type`, the prefix comes from a table keyed by model family, and a model this
table does not know is an error unless the config names its convention explicitly.
Silence is the failure mode this module is designed to make impossible.

Two backends: `openrouter` (hosted, pinned to one provider — the Phase 1 control
uses `qwen/qwen3-embedding-8b` on DeepInfra, DEC-041) and `sentence_transformers`
(local, pinned to an HF revision; built for the handover's local option and kept
for Phase 2). Both apply the same prefix table.
"""

from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    # openrouter only. One provider, no fallbacks: two providers serving the same
    # model return different vectors (measured 2026-09-12, DEC-041), so a fallback
    # mid-index would mix two embedding spaces. Part of the index key.
    provider: str = ""
    max_attempts: int = 4
    backoff_s: float = 2.0


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

    @property
    def pinned_identity(self) -> str:
        """What fixes the vectors beyond the model id: an HF revision for a local
        model, a provider for a hosted one. Part of the dense index key."""
        return self.config.revision

    def provenance(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "model_id": self.config.model,
            "revision": self.config.revision,
            "pinned_identity": self.pinned_identity,
            "prefix_convention": self.prefix.name,
            "query_prefix": self.prefix.query,
            "passage_prefix": self.prefix.passage,
        }


@dataclass
class EmbedUsage:
    """What the hosted backend spent, summed over every call this embedder made."""

    calls: int = 0
    retries: int = 0
    prompt_tokens: int = 0
    cost_usd: float = 0.0
    providers_seen: list[str] = field(default_factory=list)


class OpenRouterEmbedder(Embedder):
    name = "openrouter"

    # Transient by nature: retry with backoff, and count it. Anything else — auth,
    # bad request, wrong provider — is raised on the first occurrence (MIS-010).
    # Transport errors are caught as the httpx superclass: the first dense index
    # build died on an SSL "bad record mac" that a TimeoutException-only clause
    # let through (MIS-014).
    _RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

    def __init__(self, config: EmbedderConfig) -> None:
        super().__init__(config)
        if not config.provider:
            raise ValueError(
                f"hosted embedding model {config.model!r} needs a `provider` pin. Providers "
                "serving one model return different vectors; an unpinned index is not "
                "reproducible (DEC-041)."
            )
        self.usage = EmbedUsage()

    @property
    def pinned_identity(self) -> str:
        return f"provider:{self.config.provider}"

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.config.batch_size):
            batch = texts[start : start + self.config.batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        import httpx

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. It lives in .env at the repo root."
            )
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                response = httpx.post(
                    OPENROUTER_EMBEDDINGS_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self.config.model,
                        "input": batch,
                        "provider": {"order": [self.config.provider], "allow_fallbacks": False},
                    },
                    timeout=self.config.timeout_s,
                )
                response.raise_for_status()
                return self._parse(response.json(), len(batch), attempt)
            except httpx.TransportError as exc:
                # Timeouts, connection resets, TLS read errors: the network, not the
                # request. TransportError is the httpx superclass of all of them.
                last_error = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in self._RETRY_STATUS:
                    # Not transient: raise with the body, which is where OpenRouter
                    # explains itself (a 404 "No endpoints found" carries a
                    # routing_funnel saying which filter dropped the pinned provider —
                    # MIS-023 was a batch too large for the endpoint's context).
                    raise RuntimeError(
                        f"{self.config.model} via {self.config.provider}: HTTP "
                        f"{exc.response.status_code} on a batch of {len(batch)} inputs: "
                        f"{exc.response.text[:500]}"
                    ) from exc
                last_error = exc
            self.usage.retries += 1
            if attempt < self.config.max_attempts:
                time.sleep(self.config.backoff_s * (2 ** (attempt - 1)))
        raise RuntimeError(
            f"{self.config.model}: {self.config.max_attempts} attempts failed; "
            f"last error {type(last_error).__name__}: {last_error}"
        ) from last_error

    def _parse(self, payload: dict[str, Any], expected: int, attempt: int) -> list[list[float]]:
        # Assert the response holds what was asked for, at the point of the call
        # (MIS-006): the right count, from the pinned provider.
        data = sorted(payload.get("data", []), key=lambda d: d["index"])
        if len(data) != expected:
            raise RuntimeError(f"embeddings API returned {len(data)} vectors for {expected} inputs")
        served_by = payload.get("provider")
        if served_by and served_by != self.config.provider:
            raise RuntimeError(
                f"embeddings served by {served_by!r}, not the pinned {self.config.provider!r}"
            )
        self.usage.calls += 1
        usage = payload.get("usage", {})
        self.usage.prompt_tokens += int(usage.get("prompt_tokens", 0))
        self.usage.cost_usd += float(usage.get("cost", 0.0))
        if served_by and served_by not in self.usage.providers_seen:
            self.usage.providers_seen.append(served_by)
        return [d["embedding"] for d in data]

    def provenance(self) -> dict[str, Any]:
        meta = super().provenance()
        meta["provider"] = self.config.provider
        meta["usage"] = {
            "calls": self.usage.calls,
            "retries": self.usage.retries,
            "prompt_tokens": self.usage.prompt_tokens,
            "cost_usd": round(self.usage.cost_usd, 6),
            "providers_seen": list(self.usage.providers_seen),
        }
        return meta


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
