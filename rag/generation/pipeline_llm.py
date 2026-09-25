"""In-pipeline LLM calls — P2-03.

`PipelineLLM` is the only way a retriever, query transform or agentic loop may call
a model. It fixes the decoding at temperature 0, routes every call through the
generation cache, and counts hits and misses so the runner can record the hit rate
and mark the run `pipeline_nondeterministic`.

Prompts still come from `prompts/` by (id, version) — the caller renders and passes
the text along with the ids, which are part of the cache key.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from rag.generation.base import Completion, GeneratorConfig, OpenRouterGenerator
from rag.generation.cache import CacheKey, GenerationCache
from rag.hashing import canonical_json, hash_text

# Not configurable. A temperature above zero would make a "deterministic" retrieval
# metric a random variable with no cache able to fix it (P2-03).
TEMPERATURE = 0.0

Backend = Callable[[str], Completion]


@dataclass(frozen=True)
class Request:
    """One prompt to complete, for `complete_many`."""

    question_id: str
    prompt_id: str
    prompt_version: str
    prompt_text: str


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

    def complete_many(
        self, requests: Sequence[Request], *, workers: int = 1
    ) -> list[str | Exception]:
        """Complete many prompts, reusing the cache, with the network calls in parallel.

        Results are returned in the order of `requests`; a request whose call failed
        yields the exception instead of a string, so the caller decides per unit what
        to do with it (preflight 43) rather than losing the whole batch.

        Concurrency is deliberately confined to the HTTP calls. Cache reads, cache
        writes and the counters all happen on this thread, before and after the pool,
        because the cache is one SQLite connection and the counters are plain ints —
        sharing either across threads would corrupt the hit rate this class exists to
        report, and SQLite connections are not safe across threads by default.

        `workers=1` is the default so that no existing caller changes behaviour by
        upgrading; only a caller that asks for parallelism gets it. Sequential prefix
        generation for 8,218 chunks measured 8.3 s/call — 16 hours (P2-13).
        """
        if workers < 1:
            raise ValueError("workers must be at least 1")

        keys = [
            CacheKey(
                question_id=r.question_id,
                prompt_id=r.prompt_id,
                prompt_version=r.prompt_version,
                model_id=self.model,
                input_hash=self.input_hash(r.prompt_text),
            )
            for r in requests
        ]
        results: list[str | Exception | None] = [None] * len(requests)
        misses: list[int] = []
        for i, (request, key) in enumerate(zip(requests, keys)):
            self.calls += 1
            self.prompts_used.add(f"{request.prompt_id}@{request.prompt_version}")
            cached = self.cache.get(key)
            if cached is not None:
                self.hits += 1
                results[i] = cached.output
            else:
                self.misses += 1
                misses.append(i)

        if misses:
            # The backend is shared across workers, which is safe here and checked
            # rather than assumed: `_complete_once` calls `httpx.post`, which builds a
            # client per request, and the generator's only mutable state is the
            # `rate_limited` diagnostic counter. If a backend ever holds a shared
            # session or a non-atomic accumulator, it needs one instance per worker.
            def run(index: int) -> tuple[int, Any]:
                try:
                    return index, self._backend(requests[index].prompt_text)
                except Exception as exc:  # noqa: BLE001 - handed back, not swallowed
                    return index, exc

            if workers == 1:
                completed = [run(i) for i in misses]
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    completed = list(pool.map(run, misses))

            for index, outcome in completed:
                if isinstance(outcome, Exception):
                    results[index] = outcome
                    continue
                self.tokens_in += outcome.tokens_in
                self.tokens_out += outcome.tokens_out
                self.cache.put(
                    keys[index], outcome.text,
                    tokens_in=outcome.tokens_in, tokens_out=outcome.tokens_out,
                )
                results[index] = outcome.text

        return [r if r is not None else RuntimeError("no result") for r in results]

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
