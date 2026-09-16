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


def _fake_word_dropping_backend(prompt_text: str):
    """A stand-in for a model that is not deterministic: it rewrites the query by
    dropping one content word chosen with an *unseeded* generator, so two cold calls
    on the same query can differ. Only the generation cache (P2-03) makes two runs
    of it agree — which is exactly what the determinism test checks."""
    import random

    from rag.generation.base import Completion

    query = prompt_text.split(":", 1)[1].strip() if ":" in prompt_text else prompt_text
    words = query.split()
    if len(words) > 3:
        words.pop(random.SystemRandom().randrange(len(words)))
    return Completion(text=" ".join(words), tokens_in=len(prompt_text.split()),
                      tokens_out=len(words), reasoning_tokens=0, finish_reason="stop")


_FAKE_BACKENDS = {"drop_random_word": _fake_word_dropping_backend}


@register_retriever("toy_llm_rewrite")
class ToyLLMRewriteRetriever(ToyOverlapRetriever):
    """`toy_overlap` behind a query rewrite made by an in-pipeline LLM call.

    Exists to exercise P2-03 end to end — the cache, the hit rate, the
    `pipeline_nondeterministic` flag — without paying for a model: `fake_backend`
    names a built-in stand-in. With `fake_backend` unset it would call the
    configured model through OpenRouter, which no config does. Smoke test only.
    """

    name = "toy_llm_rewrite"

    def __init__(
        self,
        chunk_to_doc: dict[str, str],
        chunk_text: dict[str, str],
        *,
        model: str = "fake/word-dropper",
        fake_backend: str = "",
        **kwargs,
    ) -> None:
        super().__init__(chunk_to_doc, chunk_text, **kwargs)
        from rag.generation.cache import GenerationCache
        from rag.generation.pipeline_llm import PipelineLLM

        self.pipeline_llm = PipelineLLM(
            model,
            cache=self.generation_cache if self.generation_cache is not None else GenerationCache(),
            backend=_FAKE_BACKENDS[fake_backend] if fake_backend else None,
        )

    def retrieve(self, question_id: str, query: str, **kwargs):
        rewritten = self.pipeline_llm.complete(
            question_id=question_id,
            prompt_id="toy_rewrite",
            prompt_version="v0",
            prompt_text=f"Rewrite the question: {query}",
        )
        return super().retrieve(question_id, rewritten, **kwargs)
