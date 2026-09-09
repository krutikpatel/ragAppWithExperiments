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
class GeneratedAnswer:
    text: str
    cited_doc_ids: list[str]
    model: str
    prompt_ref: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratorConfig:
    model: str
    prompt_id: str = "answer"
    prompt_version: str = "v1"
    temperature: float = 0.0
    max_tokens: int = 800
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
    def _complete(self, prompt: str) -> tuple[str, int, int]:
        """Return (text, tokens_in, tokens_out)."""

    def generate(self, question: str, context: str) -> GeneratedAnswer:
        prompt = load_prompt(self.config.prompt_id, self.config.prompt_version)
        started = time.perf_counter()
        text, tokens_in, tokens_out = self._complete(
            prompt.render(question=question, context=context)
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return GeneratedAnswer(
            text=text,
            cited_doc_ids=extract_citations(text),
            model=self.config.model,
            prompt_ref=prompt.ref,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=elapsed_ms,
        )


def extract_citations(text: str) -> list[str]:
    """Document ids cited as `[doc:<id>]`, de-duplicated, first-mention order."""
    seen: dict[str, None] = {}
    for match in _CITATION.finditer(text or ""):
        seen.setdefault(match.group(1), None)
    return list(seen)


class OpenRouterGenerator(Generator):
    name = "openrouter"

    def _complete(self, prompt: str) -> tuple[str, int, int]:
        import httpx

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. It lives in .env at the repo root; "
                "load it into the environment before a Tier 2 run."
            )
        response = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.config.timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage", {})
        return (
            payload["choices"][0]["message"]["content"],
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )
