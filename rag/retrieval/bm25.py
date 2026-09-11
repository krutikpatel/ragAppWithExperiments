"""BM25 — the P0-13 baseline retriever.

The dumbest thing that works, on purpose. Every later technique is measured against
this. Tokenization is lowercase alphanumeric word splitting and nothing more — no
stemming, no stopwords — so that what BM25 sees is the indexed text and not a
preprocessing choice hiding inside the retriever. Parameters are Okapi defaults.
"""

from __future__ import annotations

import re
from typing import Any

from rag.retrieval.base import Retriever
from rag.runner.registry import register_retriever

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@register_retriever("bm25")
class BM25Retriever(Retriever):
    name = "bm25"

    def __init__(
        self,
        chunk_to_doc: dict[str, str],
        chunk_text: dict[str, str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunk_to_doc, **kwargs)
        from rank_bm25 import BM25Okapi

        # Stable order so scores line up with ids and the index is reproducible.
        self.chunk_ids = sorted(chunk_text)
        self.k1, self.b = k1, b
        self.index = BM25Okapi([tokenize(chunk_text[cid]) for cid in self.chunk_ids], k1=k1, b=b)

    @property
    def params(self) -> dict[str, Any]:
        return {"k1": self.k1, "b": self.b, "tokenizer": "lowercase [a-z0-9]+"}

    def search(self, query: str, *, top_k: int) -> list[tuple[str, float]]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.index.get_scores(tokens)
        # Ties break on chunk_id so the ranking is reproducible run to run.
        ranked = sorted(
            zip(self.chunk_ids, scores, strict=True), key=lambda item: (-item[1], item[0])
        )
        return [(cid, float(score)) for cid, score in ranked[:top_k] if score > 0]
