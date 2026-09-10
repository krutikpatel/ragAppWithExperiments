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

_CITATION = re.compile(r"\[doc:([0-9a-f]{8,64})\]")


@dataclass(frozen=True)
class Completion:
    text: str
    tokens_in: int
    tokens_out: int
    reasoning_tokens: int
    finish_reason: str


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

    def generate(self, question: str, context: str) -> GeneratedAnswer:
        prompt = load_prompt(self.config.prompt_id, self.config.prompt_version)
        started = time.perf_counter()
        completion = self._complete(prompt.render(question=question, context=context))
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
            meta={"finish_reason": completion.finish_reason},
        )


def extract_citations(text: str) -> list[str]:
    """Document ids cited as `[doc:<id>]`, de-duplicated, first-mention order."""
    seen: dict[str, None] = {}
    for match in _CITATION.finditer(text or ""):
        seen.setdefault(match.group(1), None)
    return list(seen)


class OpenRouterGenerator(Generator):
    name = "openrouter"

    def _complete(self, prompt: str) -> Completion:
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
