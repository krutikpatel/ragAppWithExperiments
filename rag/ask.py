"""`rag ask` — one question through the pipeline, rendered for a reader (P1-06).

Uses the same index, retriever, assembler and generator the runner uses, built from
the same config file, so what it prints is what a Tier 2 run of that config would
have produced for the question. It writes nothing to the results store: this is a
way to look at the system, not a way to score it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag.citations import RenderedCitation, format_report
from rag.generation.base import GeneratedAnswer
from rag.runner.config import RunConfig
from rag.eval.generation_metrics import deterministic_metrics, find_urls



@dataclass(frozen=True)
class AskResult:
    question: str
    answer: GeneratedAnswer
    citations: list[RenderedCitation]
    context_doc_ids: list[str]
    collapse_ratio: float | None
    gold_doc_ids: list[str] | None
    reference_answer: str | None
    metrics: dict[str, Any] | None  # deterministic only, when gold is known
    config: RunConfig


def answer_question(
    config_path: str,
    *,
    question: str | None = None,
    question_id: str | None = None,
    split: str = "dev",
) -> AskResult:
    """One question through the shared `Pipeline` (P3-13) — the same code the API serves."""
    from rag.pipeline import Pipeline

    gold: list[str] | None = None
    reference: str | None = None
    if question_id:
        from rag.dataset.loader import load_split

        frame = load_split(split)
        rows = frame[frame["question_id"] == question_id]
        if rows.empty:
            raise KeyError(f"no question {question_id!r} in split {split!r}")
        row = rows.iloc[0]
        question = str(row["question"])
        gold = list(row["gold_doc_ids"])
        reference = str(row["answer"])
    assert question is not None

    pipeline = Pipeline.from_config_file(config_path)
    result = pipeline.answer(question, question_id=question_id or "ask")
    answer = result.answer
    metrics = None
    if gold is not None and reference is not None:
        metrics = deterministic_metrics(
            generated_answer=answer.text,
            reference_answer=reference,
            cited_doc_ids=answer.cited_doc_ids,
            gold_doc_ids=gold,
        )
    return AskResult(
        question=question,
        answer=answer,
        citations=result.citations,
        context_doc_ids=result.context_doc_ids,
        collapse_ratio=result.collapse_ratio,
        gold_doc_ids=gold,
        reference_answer=reference,
        metrics=metrics,
        config=pipeline.config,
    )


def format_ask(result: AskResult, *, max_chunk_chars: int | None = None) -> str:
    out = [format_report(result.question, result.answer.text, result.citations, max_chunk_chars=max_chunk_chars)]
    out.append("")
    out.append(
        f"model {result.answer.model}  prompt {result.answer.prompt_ref}  "
        f"tokens {result.answer.tokens_in} in / {result.answer.tokens_out} out  "
        f"{result.answer.latency_ms} ms  attempts {result.answer.meta.get('attempts', 1)}"
    )
    urls = find_urls(result.answer.text)
    out.append(f"URL-shaped strings in raw output: {len(urls)}" + (f"  {urls}" if urls else ""))
    if result.gold_doc_ids is not None and result.metrics is not None:
        m = result.metrics
        in_ctx = [g for g in result.gold_doc_ids if g in result.context_doc_ids]
        out.append("")
        out.append("SCORED AGAINST GOLD (deterministic, no LLM call)")
        out.append(f"  gold docs: {len(result.gold_doc_ids)}, in context: {len(in_ctx)}")
        prec = "n/a (cited nothing)" if m["citation_precision"] is None else f"{m['citation_precision']:.2f}"
        out.append(f"  citation precision {prec}   citation recall {m['citation_recall']:.2f}")
        cov = "n/a (reference is not a procedure)" if m["step_coverage"] is None else f"{m['step_coverage']:.2f}"
        out.append(f"  step coverage {cov}   refused {bool(m['refused'])}")
    return "\n".join(out)
