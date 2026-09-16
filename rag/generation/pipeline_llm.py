"""In-pipeline LLM calls — P2-03.

`PipelineLLM` is the only way a retriever, query transform or agentic loop may call
a model. It fixes the decoding at temperature 0, routes every call through the
generation cache, and counts hits and misses so the runner can record the hit rate
and mark the run `pipeline_nondeterministic`.

Prompts still come from `prompts/` by (id, version) — the caller renders and passes
the text along with the ids, which are part of the cache key.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rag.generation.base import Completion, GeneratorConfig, OpenRouterGenerator
from rag.generation.cache import CacheKey, GenerationCache
from rag.hashing import canonical_json, hash_text

# Not configurable. A temperature above zero would make a "deterministic" retrieval
# metric a random variable with no cache able to fix it (P2-03).
TEMPERATURE = 0.0

Backend = Callable[[str], Completion]


class PipelineLLM:
    def __init__(
        self,
        model: str,
        *,
        cache: GenerationCache,
        backend: Backend | None = None,
        max_tokens: int = 1000,
        reasoning_effort: str = "minimal",
    ) -> None:
        if not model:
            raise ValueError("PipelineLLM needs a model id; model choice is Krutik's (CLAUDE.md §10)")
        self.model = model
        self.cache = cache
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self._backend = backend or self._openrouter_backend()
        self.calls = 0
        self.hits = 0
        self.misses = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.prompts_used: set[str] = set()

    def _openrouter_backend(self) -> Backend:
        generator = OpenRouterGenerator(
            GeneratorConfig(
                model=self.model,
                temperature=TEMPERATURE,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
            )
        )
        return generator.complete_raw

    def input_hash(self, prompt_text: str) -> str:
        return hash_text(
            canonical_json(
                {
                    "prompt": prompt_text,
                    "temperature": TEMPERATURE,
                    "max_tokens": self.max_tokens,
                    "reasoning_effort": self.reasoning_effort,
                }
            )
        )[:23]

    def complete(
        self, *, question_id: str, prompt_id: str, prompt_version: str, prompt_text: str
    ) -> str:
        key = CacheKey(
            question_id=question_id,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_id=self.model,
            input_hash=self.input_hash(prompt_text),
        )
        self.calls += 1
        self.prompts_used.add(f"{prompt_id}@{prompt_version}")
        cached = self.cache.get(key)
        if cached is not None:
            self.hits += 1
            return cached.output
        self.misses += 1
        completion = self._backend(prompt_text)
        self.tokens_in += completion.tokens_in
        self.tokens_out += completion.tokens_out
        self.cache.put(key, completion.text, tokens_in=completion.tokens_in, tokens_out=completion.tokens_out)
        return completion.text

    def stats(self) -> dict[str, Any]:
        """Recorded on the run row as `pipeline_llm_json` (P2-03)."""
        return {
            "model": self.model,
            "temperature": TEMPERATURE,
            "max_tokens": self.max_tokens,
            "reasoning_effort": self.reasoning_effort,
            "calls": self.calls,
            "cache_hits": self.hits,
            "cache_misses": self.misses,
            "hit_rate": (self.hits / self.calls) if self.calls else None,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "prompts": sorted(self.prompts_used),
            "cache_path": str(self.cache.path),
        }
