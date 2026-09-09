"""LLM judge — the scored half of P0-07.

Three criteria, one prompt each, versioned. Every score carries the judge model id
and the prompt ref that produced it, because swapping either changes the numbers
and must be visible in the results store rather than inferred from a commit date.

No model is chosen here. `JudgeConfig.model` is supplied by the run config, and
choosing it is Krutik's decision (CLAUDE.md section 10) — running with the same
family as the generator risks self-preference bias, which needs a decision entry
rather than a default.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from rag.prompts import load_prompt

CRITERIA = ("faithfulness", "answer_relevance", "answer_correctness")

PROMPT_FOR_CRITERION = {
    "faithfulness": ("judge_faithfulness", "v1"),
    "answer_relevance": ("judge_answer_relevance", "v1"),
    "answer_correctness": ("judge_answer_correctness", "v1"),
}

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True)
class JudgeScore:
    criterion: str
    score: float
    reasoning: str
    judge_model: str
    prompt_ref: str
    detail: dict[str, Any] = field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass(frozen=True)
class JudgeConfig:
    model: str
    temperature: float = 0.0
    max_tokens: int = 600
    timeout_s: float = 60.0


class Judge(ABC):
    """Scores one answer on one criterion."""

    name: str

    def __init__(self, config: JudgeConfig) -> None:
        if not config.model:
            raise ValueError(
                "no judge model configured. Model choice is not a default to be "
                "picked here — see CLAUDE.md section 10."
            )
        self.config = config

    @abstractmethod
    def _complete(self, prompt: str) -> tuple[str, int, int]:
        """Return (text, tokens_in, tokens_out)."""

    def score(self, criterion: str, **fields: Any) -> JudgeScore:
        if criterion not in PROMPT_FOR_CRITERION:
            raise ValueError(f"unknown criterion {criterion!r}; known: {CRITERIA}")
        prompt_id, version = PROMPT_FOR_CRITERION[criterion]
        prompt = load_prompt(prompt_id, version)
        text, tokens_in, tokens_out = self._complete(prompt.render(**fields))
        parsed = _parse_json_object(text)

        score = float(parsed.get("score", 0.0))
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"judge returned out-of-range score {score} for {criterion}")

        return JudgeScore(
            criterion=criterion,
            score=score,
            reasoning=str(parsed.get("reasoning", ""))[:500],
            judge_model=self.config.model,
            prompt_ref=prompt.ref,
            detail={k: v for k, v in parsed.items() if k not in {"score", "reasoning"}},
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )


def _parse_json_object(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a completion, tolerating code fences.

    A judge that returns unparseable output raises. Defaulting a failed parse to
    0.0 would quietly turn an infrastructure failure into a quality finding.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1]
        stripped = stripped[4:] if stripped.startswith("json") else stripped
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"judge response contained no JSON object: {text[:200]!r}")
    return json.loads(stripped[start : end + 1])


class OpenRouterJudge(Judge):
    """Judge backed by OpenRouter. The key comes from `.env`; the model from config."""

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


def judge_all_criteria(
    judge: Judge,
    *,
    question: str,
    answer: str,
    context: str,
    reference_answer: str,
) -> dict[str, JudgeScore]:
    """Score one question on all three criteria."""
    fields = {
        "faithfulness": {"context": context, "answer": answer},
        "answer_relevance": {"question": question, "answer": answer},
        "answer_correctness": {
            "question": question,
            "reference_answer": reference_answer,
            "answer": answer,
        },
    }
    return {criterion: judge.score(criterion, **fields[criterion]) for criterion in CRITERIA}
