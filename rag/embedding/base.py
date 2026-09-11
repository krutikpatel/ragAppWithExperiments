"""Embedder interface — P0-11.

Phase 0 needs the seam, not dense retrieval. The one implementation calls
OpenRouter's embeddings API with the model chosen in DEC-027. It is not used by any
Phase 0 experiment; it exists so Phase 1 dense retrieval plugs in without touching
the runner.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"


@dataclass(frozen=True)
class EmbedderConfig:
    model: str
    batch_size: int = 64
    timeout_s: float = 60.0


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

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """One vector per input, in order."""

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @property
    def model_id(self) -> str:
        return self.config.model


class OpenRouterEmbedder(Embedder):
    name = "openrouter"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
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
