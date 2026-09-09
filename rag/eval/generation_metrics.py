"""Generation metrics that cost nothing — part of P0-07.

Citation precision/recall, step coverage and refusal detection are computed from
the artifacts alone. No LLM call, no manual judgment. They are free because WixQA
ships `article_ids`, and they are the metrics least able to drift when a judge
model changes underneath us.

The judge-scored metrics — faithfulness, answer relevance, answer correctness —
live in `rag/eval/judge.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from rag.eval.steps import step_coverage

REFUSAL_DETECTOR_VERSION = "refusal-lexical-v1"

# Phrases a grounded system uses when it declines. Lexical on purpose: refusal rate
# has to be computable in Tier 1 cost terms and be auditable line by line. It is a
# proxy, and a weak one for creative refusals — tracked as OQ-008.
_REFUSAL_PATTERNS = [
    r"\bi (?:do not|don't) (?:have|know)\b",
    r"\b(?:cannot|can't|unable to) (?:answer|help|find|determine|verify)\b",
    r"\bnot (?:enough|sufficient) (?:information|context)\b",
    r"\bno (?:relevant )?(?:information|articles?|documents?) (?:was |were )?(?:found|available)\b",
    r"\b(?:is |are )?not (?:covered|available|documented|mentioned) in the (?:provided )?(?:context|articles?|documentation|knowledge base)\b",
    r"\bthe (?:provided )?(?:context|articles?) (?:does|do) not (?:contain|mention|cover)\b",
    r"\bcould you (?:please )?(?:clarify|specify|provide more)\b",
    r"\bout of scope\b",
]
_REFUSAL = re.compile("|".join(_REFUSAL_PATTERNS), re.IGNORECASE)


@dataclass(frozen=True)
class CitationScores:
    precision: float | None
    recall: float
    n_cited: int
    n_gold: int
    cited_nothing: bool


def citation_scores(cited_doc_ids: list[str], gold_doc_ids: list[str]) -> CitationScores:
    """Compare cited document ids against gold ids. Free — no judge involved.

    Precision is `None`, not zero, when the answer cites nothing: a system that
    declines to cite has not made a false citation, and scoring it as zero would
    reward citing one lucky document over citing none. `cited_nothing` carries that
    case so it can be counted separately.
    """
    cited, gold = set(cited_doc_ids), set(gold_doc_ids)
    hits = len(cited & gold)
    return CitationScores(
        precision=(hits / len(cited)) if cited else None,
        recall=(hits / len(gold)) if gold else 0.0,
        n_cited=len(cited),
        n_gold=len(gold),
        cited_nothing=not cited,
    )


def is_refusal(answer: str) -> bool:
    """Whether the answer declines to answer, by lexical pattern."""
    return bool(_REFUSAL.search(answer or ""))


def deterministic_metrics(
    *,
    generated_answer: str,
    reference_answer: str,
    cited_doc_ids: list[str],
    gold_doc_ids: list[str],
) -> dict[str, Any]:
    """Every P0-07 metric that needs no LLM call, for one question."""
    citations = citation_scores(cited_doc_ids, gold_doc_ids)
    steps = step_coverage(reference_answer, generated_answer)
    refused = is_refusal(generated_answer)
    answerable = bool(gold_doc_ids)

    return {
        "citation_precision": citations.precision,
        "citation_recall": citations.recall,
        "cited_nothing": float(citations.cited_nothing),
        "step_coverage": steps.coverage,
        "step_order_preserved": None if steps.order_preserved is None else float(steps.order_preserved),
        "n_reference_steps": steps.n_reference_steps,
        # Refusal on an unanswerable question is the goal; on an answerable one it
        # is a false refusal. Splitting them keeps a single "refusal rate" from
        # meaning two opposite things depending on the split.
        "refused": float(refused),
        "correct_refusal": float(refused) if not answerable else None,
        "false_refusal": float(refused) if answerable else None,
    }


def refusal_summary(per_question: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Refusal rate on unanswerable questions, false-refusal rate on answerable ones."""

    def _rate(metric: str) -> tuple[float | None, int]:
        values = [row[metric] for row in per_question.values() if row.get(metric) is not None]
        return (sum(values) / len(values) if values else None, len(values))

    refusal_rate, n_unanswerable = _rate("correct_refusal")
    false_rate, n_answerable = _rate("false_refusal")
    return {
        "refusal_rate": refusal_rate,
        "refusal_rate_n": n_unanswerable,
        "false_refusal_rate": false_rate,
        "false_refusal_rate_n": n_answerable,
        "refusal_detector": REFUSAL_DETECTOR_VERSION,
    }


def scores_as_dict(scores: CitationScores) -> dict[str, Any]:
    return asdict(scores)
