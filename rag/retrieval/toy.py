"""A deliberately bad retriever, for exercising the harness.

`toy_overlap` ranks chunks by raw content-word overlap with the query. It is not a
technique, it is not a baseline, and its numbers must never reach
`docs/EXPERIMENTS.md`. It exists so the runner, the results store and `rag diff` can
be tested end to end without standing up BM25, which belongs to P0-13 and whose
first run is the recorded baseline.

Any run using it must set `harness_smoke_test=True`, which marks the row in the
results store.
"""

from __future__ import annotations

import re

from rag.retrieval.base import Retriever
from rag.runner.registry import register_retriever

_NON_WORD = re.compile(r"[^a-z0-9]+")


@register_retriever("toy_overlap")
class ToyOverlapRetriever(Retriever):
    name = "toy_overlap"

    def __init__(self, chunk_to_doc: dict[str, str], chunk_text: dict[str, str], **kwargs) -> None:
        super().__init__(chunk_to_doc, **kwargs)
        self.chunk_tokens = {cid: self._tokens(text) for cid, text in chunk_text.items()}

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token for token in _NON_WORD.split(text.lower()) if len(token) > 2}

    def search(self, query: str, *, top_k: int) -> list[tuple[str, float]]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []
        scored = [
            (chunk_id, len(query_tokens & tokens) / len(query_tokens))
            for chunk_id, tokens in self.chunk_tokens.items()
        ]
        # Ties break on chunk_id so the ranking is reproducible run to run.
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [(cid, score) for cid, score in scored[:top_k] if score > 0]
