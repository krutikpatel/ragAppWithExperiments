"""One question through the configured pipeline — shared by `rag ask` and the API (P3-13).

The runner scores a split; this answers one question. Both are built from the same config
file with the same components — `build_index`, `build_retriever`, `ConcatAssembler`,
`OpenRouterGenerator` — so the API cannot fork the logic the eval gates (P3-13: "imports
the same pipeline code as the eval"). The contract test (`tests/test_api_p3_13.py`)
checks it the strict way: for golden questions the API builds the same prompt the gate's
run built, so it replays the gate's own cached answer, character for character.

Built once and reused: the index is 134 MB and loads in seconds, so a server keeps one.

A config feature this class does not implement is REFUSED, not skipped — a query
transform, a reranker, context compression or the grounding self-check would each change
what the runner does, and a silent difference is exactly the fork P3-13 forbids.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rag.assembly import ConcatAssembler
from rag.citations import RenderedCitation, render_citations
from rag.eval.generation_metrics import is_refusal
from rag.generation.base import GeneratedAnswer, GeneratorConfig, OpenRouterGenerator
from rag.runner.config import RunConfig, load_config_file

# The pipeline never judges; judge fields are cleared before the config is validated.
NO_JUDGE = {"judge_model": "", "judge_embedding_model": "", "skip_judge": True}
UNSUPPORTED = ("query_transform", "reranker", "context_compressor", "grounding_check")


@dataclass(frozen=True)
class PipelineAnswer:
    question: str
    answer: GeneratedAnswer
    citations: list[RenderedCitation]
    context_doc_ids: list[str]
    collapse_ratio: float | None
    refused: bool
    timings_ms: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0


class Pipeline:
    def __init__(self, config: RunConfig) -> None:
        from rag.corpus.loader import load_corpus
        from rag.runner.model_check import configured_models, verify_models
        from rag.runner.registry import build_retriever
        from rag.runner.run import build_index

        if not config.generator_model:
            raise ValueError("the pipeline needs a Tier 2 config with a generator_model")
        used = [f for f in UNSUPPORTED if getattr(config, f)]
        if used:
            raise ValueError(f"{used} are not implemented by the one-question pipeline; answering "
                             "without them would differ from the runner (P3-13: no forked logic)")
        self.config = config
        verify_models(configured_models(config))  # P3-02: fail fast on a retired slug
        self.corpus = load_corpus()
        self.index, chunk_text = build_index(config)
        self.retriever = build_retriever(
            config.retriever, chunk_to_doc=self.index.chunk_to_doc, chunk_text=chunk_text,
            doc_pooling=config.doc_pooling, index=self.index, **config.retriever_params,
        )
        self.assembler = ConcatAssembler(max_tokens=config.context_max_tokens, order=config.context_order)
        self.generator = OpenRouterGenerator(GeneratorConfig(
            model=config.generator_model, prompt_id=config.generator_prompt_id,
            prompt_version=config.generator_prompt_version, max_tokens=config.generator_max_tokens,
            reasoning_effort=config.generator_reasoning_effort,
        ))

    @classmethod
    def from_config_file(cls, path: str) -> Pipeline:
        return cls(load_config_file(path, overrides=NO_JUDGE))

    def _embedding_cost(self) -> float:
        embedder = getattr(self.retriever, "embedder", None)
        usage = (embedder.provenance().get("usage") or {}) if embedder is not None else {}
        return float(usage.get("cost_usd") or 0.0)

    def answer(self, question: str, *, question_id: str = "ask") -> PipelineAnswer:
        from rag.runner.cost import PricingTable

        spent_before = self._embedding_cost()
        t0 = time.perf_counter()
        result = self.retriever.retrieve(
            question_id, question, top_k=self.config.retrieval_depth, k_docs=self.config.top_k,
            candidate_pool=self.config.candidate_pool,
        )
        t1 = time.perf_counter()
        context_text = self.index.context_text
        context = self.assembler.assemble(result.context_chunks, context_text)
        t2 = time.perf_counter()
        answer = self.generator.generate(question, context.text)
        t3 = time.perf_counter()

        cost = self._embedding_cost() - spent_before
        if not answer.meta.get("cached"):  # a replayed answer was not bought on this request
            price = PricingTable.load().price("chat", self.config.generator_model) or {}
            if price:
                cost += answer.tokens_in / 1e6 * price["in"] + answer.tokens_out / 1e6 * price["out"]
        return PipelineAnswer(
            question=question, answer=answer,
            citations=render_citations(answer.cited_doc_ids, result.context_chunks, context_text, self.corpus),
            context_doc_ids=[c.doc_id for c in result.context_chunks],
            collapse_ratio=result.context.collapse_ratio if result.context else None,
            refused=is_refusal(answer.text),
            timings_ms={"retrieve": int((t1 - t0) * 1000), "assemble": int((t2 - t1) * 1000),
                        "generate": int((t3 - t2) * 1000), "total": int((t3 - t0) * 1000)},
            cost_usd=round(cost, 8),
        )


def describe(result: PipelineAnswer) -> dict[str, Any]:
    """The API's response shape (P3-13)."""
    return {
        "answer": result.answer.text,
        "citations": [
            {"article_title": c.title, "url": c.url, "chunk_text": c.chunk_text, "doc_id": c.doc_id,
             "in_context": c.in_context}
            for c in result.citations if c.cited
        ],
        "refused": result.refused,
    }
