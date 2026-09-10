"""Judged generation metrics, via Ragas — P0-07.

Ragas is used as a **metric library only**. Its `Dataset`, `experiment` and
result-logging abstractions are deliberately not adopted: Ragas has drifted from a
RAG-eval library toward a general LLM-app eval product with its own dataset
management and experiment tracking, and adopting those would fork the Phase 0
results store and break `rag diff`. We call metrics, take scores, and write them to
our own SQLite rows.

**This module is the only place Ragas may be imported.** `tests/test_eval_boundary.py`
asserts that. A Ragas major-version change or a swap to another judge library is then
a one-file change.

Provenance recorded on every score: judge model, judge family, temperature, the
pinned Ragas version, and a fingerprint of each metric's implementation package.
Ragas does not expose prompt objects on the collections API, so the fingerprint
hashes the metric package source — it changes when Ragas changes the metric, which
is the thing that would silently move scores across an upgrade.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

CRITERIA = ("faithfulness", "answer_correctness", "answer_relevance")

# Metrics that need no embedding model.
CRITERIA_WITHOUT_EMBEDDINGS = ("faithfulness", "answer_correctness")

# Ragas's AnswerRelevancy embeds generated questions to compare against the original,
# so it needs an embedding model. OpenRouter supplies one through its embeddings API
# (`POST /api/v1/embeddings`; models are listed at `/api/v1/embeddings/models`, a
# different endpoint from `/api/v1/models`). So this is a configuration question, not
# a capability gap: set `judge_embedding_model` and the criterion runs. See DEC-026,
# which corrects DEC-022.
EMBEDDING_REQUIRED = ("answer_relevance",)

OPENROUTER_EMBEDDINGS_MODELS_URL = "https://openrouter.ai/api/v1/embeddings/models"

# [factuality, semantic similarity]. Similarity is weighted to zero: it is the
# component P0-07 warns is noisy on long procedural answers, and zeroing it also
# removes the embeddings dependency from this metric. Recorded on every run.
ANSWER_CORRECTNESS_WEIGHTS = (1.0, 0.0)


def model_family(model_id: str) -> str:
    """The provider family of an OpenRouter model id: `openai/gpt-5-nano` -> `openai`.

    Used to enforce that the judge is not from the generator's family, which would
    make every judged score carry an unmeasured self-preference bias.
    """
    return model_id.split("/", 1)[0] if "/" in model_id else model_id


@dataclass(frozen=True)
class JudgeScore:
    criterion: str
    score: float
    judge_model: str
    judge_family: str
    judge_temperature: float
    ragas_version: str
    metric_fingerprint: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JudgeConfig:
    model: str
    temperature: float = 0.0
    embedding_model: str = ""
    answer_correctness_weights: tuple[float, float] = ANSWER_CORRECTNESS_WEIGHTS
    timeout_s: float = 120.0

    @property
    def family(self) -> str:
        return model_family(self.model)

    @property
    def criteria(self) -> tuple[str, ...]:
        """Which criteria this configuration can actually score."""
        if self.embedding_model:
            return CRITERIA
        return CRITERIA_WITHOUT_EMBEDDINGS

    @property
    def skipped_criteria(self) -> tuple[str, ...]:
        return tuple(c for c in CRITERIA if c not in self.criteria)


def ragas_version() -> str:
    import ragas

    return ragas.__version__


@lru_cache(maxsize=None)
def metric_fingerprint(package: str) -> str:
    """Hash of a Ragas metric package's source.

    Ragas manages metric prompts internally and revises them between releases. A
    prompt change on upgrade would silently move every historical score while
    `ragas_version` alone might still look "close enough" to a reader. Hashing the
    implementation package makes the change visible in the results store.
    """
    import importlib

    module = importlib.import_module(package)
    directory = Path(module.__file__).parent
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*.py")):
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()[:16]


class Judge(ABC):
    """Scores one (question, answer, contexts, reference) tuple."""

    name: str

    def __init__(self, config: JudgeConfig) -> None:
        if not config.model:
            raise ValueError(
                "no judge model configured. Model choice is not a default to be "
                "picked here — see CLAUDE.md section 10."
            )
        self.config = config

    @abstractmethod
    def score(
        self, *, question: str, answer: str, contexts: list[str], reference: str
    ) -> dict[str, JudgeScore]:
        """Return one JudgeScore per criterion this judge can compute."""


class RagasJudge(Judge):
    """Ragas metrics driven through an OpenRouter-backed instructor LLM."""

    name = "ragas"

    METRIC_PACKAGES = {
        "faithfulness": "ragas.metrics.collections.faithfulness",
        "answer_correctness": "ragas.metrics.collections.answer_correctness",
        "answer_relevance": "ragas.metrics.collections.answer_relevancy",
    }

    def __init__(self, config: JudgeConfig) -> None:
        super().__init__(config)
        self._metrics: dict[str, Any] | None = None

    def _openrouter_client(self) -> Any:
        from openai import OpenAI

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. It lives in .env at the repo root; "
                "load it into the environment before a Tier 2 run."
            )
        return OpenAI(
            api_key=api_key, base_url=OPENROUTER_BASE_URL, timeout=self.config.timeout_s
        )

    def _build_metrics(self) -> dict[str, Any]:
        from ragas.llms import llm_factory
        from ragas.metrics.collections import AnswerCorrectness, Faithfulness

        client = self._openrouter_client()
        llm = llm_factory(
            model=self.config.model,
            provider="openai",
            client=client,
            temperature=self.config.temperature,
        )

        metrics: dict[str, Any] = {
            "faithfulness": Faithfulness(llm=llm),
            "answer_correctness": AnswerCorrectness(
                llm=llm, weights=list(self.config.answer_correctness_weights)
            ),
        }
        if self.config.embedding_model:
            from ragas.metrics.collections import AnswerRelevancy

            metrics["answer_relevance"] = AnswerRelevancy(
                llm=llm, embeddings=self._embeddings()
            )
        return metrics

    def _embeddings(self) -> Any:
        """Ragas embeddings backed by OpenRouter's embeddings API.

        `ragas.embeddings.OpenAIEmbeddings` accepts any OpenAI-compatible client, and
        OpenRouter's embeddings endpoint is one, so no custom wrapper is needed — the
        model id is just an OpenRouter embedding model.
        """
        from ragas.embeddings import OpenAIEmbeddings

        return OpenAIEmbeddings(
            client=self._openrouter_client(), model=self.config.embedding_model
        )

    def score(
        self, *, question: str, answer: str, contexts: list[str], reference: str
    ) -> dict[str, JudgeScore]:
        if self._metrics is None:
            self._metrics = self._build_metrics()

        calls = {
            "faithfulness": lambda m: m.ascore(
                user_input=question, response=answer, retrieved_contexts=contexts
            ),
            "answer_correctness": lambda m: m.ascore(
                user_input=question, response=answer, reference=reference
            ),
            "answer_relevance": lambda m: m.ascore(user_input=question, response=answer),
        }

        scores: dict[str, JudgeScore] = {}
        for criterion, metric in self._metrics.items():
            result = asyncio.run(calls[criterion](metric))
            scores[criterion] = JudgeScore(
                criterion=criterion,
                score=float(result.value),
                judge_model=self.config.model,
                judge_family=self.config.family,
                judge_temperature=self.config.temperature,
                ragas_version=ragas_version(),
                metric_fingerprint=metric_fingerprint(self.METRIC_PACKAGES[criterion]),
                detail={"reason": getattr(result, "reason", None)},
            )
        return scores


def judge_provenance(config: JudgeConfig) -> dict[str, Any]:
    """The provenance a run row records for its judge, computed without calling one."""
    return {
        "judge_model": config.model,
        "judge_family": config.family,
        "judge_temperature": config.temperature,
        "ragas_version": ragas_version(),
        "answer_correctness_weights": list(config.answer_correctness_weights),
        "metric_prompt_versions": {
            criterion: metric_fingerprint(RagasJudge.METRIC_PACKAGES[criterion])
            for criterion in config.criteria
        },
        "skipped_criteria": list(config.skipped_criteria),
    }
