"""LLM-as-reranker — P2-10, Axis 5.

A different mechanism from a cross-encoder, which is why the story contrasts them:
a cross-encoder scores each (query, passage) pair in isolation, while this shows the
model every candidate at once and asks for an ordering, so candidates are ranked
against each other. Whether that helps on this corpus is the experiment.

Every call goes through `PipelineLLM` (P2-03, DEC-049): temperature 0, cached on
(question_id, prompt_id, prompt_version, model_id, input_hash), hit rate counted.
The runner reads `pipeline_llm` off the reranker exactly as it reads it off a
retriever and marks the run `pipeline_nondeterministic`.

## Parsing

The model is asked for bare numbers and does not always send bare numbers (MIS-016,
preflight 21). `parse_ranking` takes the integers in the order they appear and then:

- drops a number outside `1..n` — an invented candidate — and counts it;
- drops a repeat of a number already placed, and counts it;
- appends every candidate the model omitted, in the retriever's order, below the
  ones it ranked.

Nothing is silently discarded: the counts land in `usage` and on the run row, so a
reranker that answered with prose is visible as "ranked 0 of 50" rather than as a
result that happens to equal the baseline.
"""

from __future__ import annotations

import re
from typing import Any

from rag.prompts import load_prompt
from rag.reranking.base import Reranker, check_same_chunks
from rag.retrieval.base import ScoredChunk
from rag.runner.registry import register_reranker

_INT = re.compile(r"\d+")


def parse_ranking(text: str, n: int) -> dict[str, Any]:
    """`{"order": [0-based positions], "invented": int, "repeated": int, "omitted": int}`."""
    order: list[int] = []
    placed: set[int] = set()
    invented = repeated = 0
    for token in _INT.findall(text or ""):
        value = int(token)
        if not 1 <= value <= n:
            invented += 1
            continue
        if value - 1 in placed:
            repeated += 1
            continue
        placed.add(value - 1)
        order.append(value - 1)
    omitted = [i for i in range(n) if i not in placed]
    return {
        "order": order + omitted,
        "ranked": len(order),
        "invented": invented,
        "repeated": repeated,
        "omitted": len(omitted),
    }


@register_reranker("llm")
class LLMReranker(Reranker):
    """Ranks the whole candidate list in one cached, temperature-0 LLM call."""

    name = "llm"

    def __init__(
        self,
        chunk_text: dict[str, str],
        *,
        generation_cache: Any = None,
        model: str = "",
        prompt: str = "rerank_llm@v1",
        max_tokens: int = 1000,
        reasoning_effort: str = "minimal",
        candidate_words: int = 0,
    ) -> None:
        super().__init__(chunk_text, generation_cache=generation_cache)
        if generation_cache is None:
            raise ValueError(
                "the LLM reranker needs the generation cache: every in-pipeline LLM call "
                "goes through PipelineLLM so the run is replayable (P2-03, DEC-049)."
            )
        if "@" not in prompt:
            raise ValueError(f"prompt must be '<id>@<version>', got {prompt!r}")
        from rag.generation.pipeline_llm import PipelineLLM

        self.prompt_id, self.prompt_version = prompt.split("@", 1)
        self.prompt = load_prompt(self.prompt_id, self.prompt_version)
        # 0 = send the whole indexed chunk, so the LLM sees what the cross-encoders
        # see and the axis compares mechanisms rather than context budgets.
        self.candidate_words = candidate_words
        self.pipeline_llm = PipelineLLM(
            model,
            cache=generation_cache,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )
        self.parse_stats = {"ranked": 0, "invented": 0, "repeated": 0, "omitted": 0, "empty": 0}

    @property
    def reranker_id(self) -> str:
        return f"{self.pipeline_llm.model}@{self.prompt.ref}"

    def _candidate_block(self, chunks: list[ScoredChunk]) -> str:
        lines = []
        for position, chunk in enumerate(chunks, start=1):
            text = self.chunk_text[chunk.chunk_id]
            if self.candidate_words:
                text = " ".join(text.split()[: self.candidate_words])
            lines.append(f"[{position}] {text}")
        return "\n\n".join(lines)

    def rerank(
        self, query: str, chunks: list[ScoredChunk], *, question_id: str = ""
    ) -> list[ScoredChunk]:
        if not chunks:
            return []
        prompt_text = self.prompt.render(
            question=query, candidates=self._candidate_block(chunks), n=len(chunks)
        )
        output = self._timed(
            self.pipeline_llm.complete,
            question_id=question_id,
            prompt_id=self.prompt_id,
            prompt_version=self.prompt_version,
            prompt_text=prompt_text,
        )
        parsed = parse_ranking(output, len(chunks))
        for key in ("ranked", "invented", "repeated", "omitted"):
            self.parse_stats[key] += parsed[key]
        if parsed["ranked"] == 0:
            # The model returned no usable ordering. Recorded, not hidden: the
            # ranking falls back to the retriever's and the count says how often.
            self.parse_stats["empty"] += 1
        self.usage.calls += 1
        self.usage.candidates += len(chunks)
        # Scores descend with position; only the order is read downstream (MIS-003).
        reranked = [
            ScoredChunk(chunk_id=chunks[i].chunk_id, doc_id=chunks[i].doc_id, score=float(len(chunks) - rank))
            for rank, i in enumerate(parsed["order"])
        ]
        check_same_chunks(chunks, reranked)
        return reranked

    def query_cost_usd(self) -> float:
        """Zero here on purpose: the runner prices in-pipeline LLM calls from
        `pipeline_llm.stats()` at the table price, and counting them twice would
        double the run's recorded cost."""
        return 0.0

    def provenance(self) -> dict[str, Any]:
        meta = super().provenance()
        meta.update({
            "model": self.pipeline_llm.model,
            "prompt": self.prompt.ref,
            "prompt_content_hash": self.prompt.content_hash,
            "reranker_id": self.reranker_id,
            "candidate_words": self.candidate_words or None,
            "parse": dict(self.parse_stats),
            "pipeline_llm": self.pipeline_llm.stats(),
        })
        return meta

    @classmethod
    def estimate_params(cls, reranker_params: dict[str, Any]) -> dict[str, Any] | None:
        return {
            "kind": "chat",
            "model": reranker_params.get("model", ""),
            "candidate_words": reranker_params.get("candidate_words", 0),
        }
