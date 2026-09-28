"""Generator interface — the Tier 2 answer producer.

Phase 0 needs the seam, not a clever generator. The answer must carry the document
ids it cited, because citation precision and recall (P0-07) are computed from them
without an LLM call.
"""

from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from rag.prompts import load_prompt

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Recorded on every run. v1 matched `[doc:<id>]` exactly and dropped `[doc: <id>]`
# — 4 to 13 citations per 100 answers in the Phase 0 Tier 2 runs (MIS-016). v2
# tolerates whitespace inside the brackets and a capitalised "Doc" (DEC-043).
# v3 (P2-14) adds the span form `[doc:<id>|<quote>]` alongside the plain `[doc:<id>]`.
# Strictly additive: every string v2 parsed, v3 parses identically, which a test pins —
# a parser bump that moved a historical number would invalidate every citation
# comparison in the ledger at once.
CITATION_PARSER_VERSION = "citation-v3"
# The span separator is `|` or `#`; the span itself is anything up to the closing
# bracket. Without this, a span-form citation matched NOTHING and every citation metric
# on an Axis 7 span run would have silently read zero (MIS-016's lesson, caught before
# the run rather than after).
_CITATION = re.compile(
    r"\[\s*doc\s*:\s*([0-9a-f]{8,64})\s*(?:[|#]\s*([^\]]*?)\s*)?\]", re.IGNORECASE
)


@dataclass(frozen=True)
class Completion:
    text: str
    tokens_in: int
    tokens_out: int
    reasoning_tokens: int
    finish_reason: str
    attempts: int = 1


class EmptyGenerationError(RuntimeError):
    """The model returned no answer text.

    Raised rather than tolerated. An empty answer is not a refusal and not a bad
    answer — it is a broken call, and letting it through would score as a
    zero-citation, zero-step-coverage response and read as a system quality
    failure. See MIS-006.
    """


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    cited_doc_ids: list[str]
    model: str
    prompt_ref: str
    tokens_in: int = 0
    tokens_out: int = 0
    reasoning_tokens: int = 0
    latency_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratorConfig:
    model: str
    prompt_id: str = "answer"
    prompt_version: str = "v1"
    temperature: float = 0.0
    # Reasoning models spend completion tokens on reasoning before emitting any
    # content, and those tokens count against max_tokens. Measured on
    # openai/gpt-5-nano with an 812-word prompt: at max_tokens=800 all 768 completion
    # tokens went to reasoning and `content` came back None. See DEC-028 / MIS-006.
    max_tokens: int = 2000
    # "minimal" spends nothing on reasoning (measured: 0 reasoning tokens, complete
    # answer). "low" spent 256. The generator is a deliberately cheap constant
    # backdrop for retrieval comparisons, so it does not need to think.
    reasoning_effort: str = "minimal"
    timeout_s: float = 90.0
    # A Tier 2 run is 100 sequential calls. Without retries, one transient timeout
    # voids the whole run — which is exactly what happened to the first EXP-0001
    # Tier 2 attempt (MIS-010). Retries are bounded, backed off, and counted: the
    # attempt count travels on every answer so a run that needed them is visible.
    max_attempts: int = 4
    backoff_s: float = 2.0
    # 429 gets its own budget, on top of the ordinary attempts, and honours
    # `Retry-After`. MIS-024's prevention rule was applied to the embedder and not
    # here, because until P2-13 nothing sent this path concurrent traffic: a Tier 2
    # run is 100 sequential calls and never saw a rate limit. Contextual retrieval
    # sends 8,218 with a worker pool, where 2/4/8 s of backoff expires inside a
    # per-minute window exactly as it did for the two index builds MIS-024 killed.
    rate_limit_attempts: int = 8
    rate_limit_backoff_s: float = 15.0
    rate_limit_max_wait_s: float = 300.0


class Generator(ABC):
    name: str

    def __init__(self, config: GeneratorConfig) -> None:
        if not config.model:
            raise ValueError(
                "no generator model configured. Model choice is not a default to be "
                "picked here — see CLAUDE.md section 10."
            )
        self.config = config

    @abstractmethod
    def _complete(self, prompt: str) -> Completion:
        """Return the completion, or raise. Must never return empty content."""

    def complete_raw(self, prompt_text: str) -> Completion:
        """Complete an already-rendered prompt. For `PipelineLLM` (P2-03), which owns
        the prompt ids and the cache key; the answer path uses `generate`."""
        return self._complete(prompt_text)

    def generate(self, question: str, context: str) -> GeneratedAnswer:
        from rag.call_cache import CallCache, active

        prompt = load_prompt(self.config.prompt_id, self.config.prompt_version)
        rendered = prompt.render(question=question, context=context)
        started = time.perf_counter()
        cache = active()  # only inside `rag ci-eval` (DEC-084); experiments always call
        cached = False  # a replayed answer was not billed on this run (DEC-084)
        if cache is None:
            completion = self._complete(rendered)
        else:
            identity = {"model": self.config.model, "prompt": prompt.ref, "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens, "reasoning_effort": self.config.reasoning_effort}
            key = CallCache.completion_key(identity, rendered)
            hit = cache.get_completion(key)
            if hit is not None:
                cache.stats["completion_hits"] += 1
                completion = Completion(**hit)
                cached = True
            else:
                cache.stats["completion_misses"] += 1
                completion = self._complete(rendered)
                cache.put_completion(key, completion.__dict__)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return GeneratedAnswer(
            text=completion.text,
            cited_doc_ids=extract_citations(completion.text),
            model=self.config.model,
            prompt_ref=prompt.ref,
            tokens_in=completion.tokens_in,
            tokens_out=completion.tokens_out,
            reasoning_tokens=completion.reasoning_tokens,
            latency_ms=elapsed_ms,
            meta={"finish_reason": completion.finish_reason, "attempts": completion.attempts, "cached": cached},
        )


def extract_citations(text: str) -> list[str]:
    """Document ids cited as `[doc:<id>]` or `[doc:<id>|<quote>]`, de-duplicated,
    first-mention order."""
    seen: dict[str, None] = {}
    for match in _CITATION.finditer(text or ""):
        seen.setdefault(match.group(1), None)
    return list(seen)


def extract_span_citations(text: str) -> list[tuple[str, str]]:
    """`(doc_id, span)` for every citation that carried a quoted span (P2-14).

    Order of appearance, duplicates kept: the same span cited twice is two claims, and
    collapsing them would flatter the support rate. A plain `[doc:<id>]` contributes
    nothing here — it has no span to verify, which is the whole difference between
    chunk-level and span-level citation.
    """
    out: list[tuple[str, str]] = []
    for match in _CITATION.finditer(text or ""):
        span = (match.group(2) or "").strip().strip('"\u201c\u201d')
        if span:
            out.append((match.group(1), span))
    return out


class OpenRouterGenerator(Generator):
    name = "openrouter"

    # How many retries were 429s (MIS-024): counted so a slow pass is legible as
    # rate limiting rather than as a slow provider.
    rate_limited = 0

    # Transient by nature: retry. Anything else — auth, bad request, empty content —
    # is not, and is raised on the first occurrence.
    _RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

    def _complete(self, prompt: str) -> Completion:
        import httpx

        last_error: Exception | None = None
        attempt = 0
        rate_limited = 0
        while attempt < self.config.max_attempts + rate_limited:
            attempt += 1
            try:
                completion = self._complete_once(prompt)
                return Completion(**{**completion.__dict__, "attempts": attempt})
            except httpx.TransportError as exc:
                # Timeouts, connection resets, TLS read errors: the network, not the
                # request. TransportError is the httpx superclass of all of them.
                last_error = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in self._RETRY_STATUS:
                    raise
                last_error = exc
                if exc.response.status_code == 429 and rate_limited < self.config.rate_limit_attempts:
                    # Its own budget, not one of the ordinary attempts (MIS-024).
                    rate_limited += 1
                    self.rate_limited += 1
                    time.sleep(self._rate_limit_wait(exc.response.headers.get("Retry-After"), rate_limited))
                    continue
            if attempt < self.config.max_attempts + rate_limited:
                time.sleep(self.config.backoff_s * (2 ** (attempt - 1)))
        raise RuntimeError(
            f"{self.config.model}: {attempt} attempts failed ({rate_limited} rate-limited); "
            f"last error {type(last_error).__name__}: {last_error}"
        ) from last_error

    def _rate_limit_wait(self, retry_after: str | None, nth: int) -> float:
        """Seconds to wait after the nth consecutive 429: the provider's `Retry-After`
        when it is a number of seconds, else 15 s doubling, capped."""
        if retry_after:
            try:
                return min(float(retry_after), self.config.rate_limit_max_wait_s)
            except ValueError:
                pass  # an HTTP-date; fall through to the schedule
        return min(
            self.config.rate_limit_backoff_s * (2 ** (nth - 1)),
            self.config.rate_limit_max_wait_s,
        )

    def _complete_once(self, prompt: str) -> Completion:
        import httpx

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. It lives in .env at the repo root; "
                "load it into the environment before a Tier 2 run."
            )
        body: dict[str, Any] = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.config.reasoning_effort:
            body["reasoning"] = {"effort": self.config.reasoning_effort}

        response = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            timeout=self.config.timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
        choice = payload["choices"][0]
        usage = payload.get("usage", {})
        reasoning_tokens = int(
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
        )
        finish_reason = choice.get("finish_reason") or "unknown"
        text = choice["message"].get("content")

        if not text:
            raise EmptyGenerationError(
                f"{self.config.model} returned no content "
                f"(finish_reason={finish_reason!r}, "
                f"completion_tokens={usage.get('completion_tokens')}, "
                f"reasoning_tokens={reasoning_tokens}, "
                f"max_tokens={self.config.max_tokens}). "
                "For a reasoning model this usually means the token budget was spent "
                "on reasoning before any answer was emitted: raise max_tokens or lower "
                "reasoning_effort."
            )
        return Completion(
            text=text,
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            reasoning_tokens=reasoning_tokens,
            finish_reason=finish_reason,
        )
