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

REFUSAL_DETECTOR_VERSION = "refusal-lexical-v2"

# Phrases a grounded system uses when it declines. Lexical on purpose: refusal rate
# has to be computable in Tier 1 cost terms and be auditable line by line. It is a
# proxy — tracked as OQ-008 — and v2 (DEC-045) is what OQ-008's first count showed
# was needed:
#   - apostrophes are normalised first: the model writes "don’t", v1 matched "don't";
#   - the phrase list covers the paraphrases seen ("is not covered by the …",
#     "they do not cover …", "I would need …");
#   - a match counts only in the OPENING of the answer (first `REFUSAL_WINDOW`
#     characters) and only if the answer has no numbered steps. A caveat after a
#     procedure ("… but the articles do not give a timeline") is a hedged answer,
#     not a refusal. Measured on 45 hand-labelled unanswerable answers: refusals put
#     the phrase at character 0–259 with zero steps; hedged answers put it at
#     617–2,127 after three or more steps.
_REFUSAL_PATTERNS = [
    r"\bi (?:do not|don't) (?:have|know)\b",
    r"\b(?:cannot|can't|unable to) (?:answer|help|find|determine|verify)\b",
    r"\bnot (?:enough|sufficient) (?:information|context)\b",
    r"\bno (?:relevant )?(?:information|articles?|documents?) (?:was |were )?(?:found|available)\b",
    r"\b(?:is |are )?not (?:covered|available|documented|mentioned) in the (?:provided )?(?:context|articles?|documentation|knowledge base)\b",
    r"\bthe (?:provided )?(?:context|articles?) (?:does|do) not (?:contain|mention|cover)\b",
    r"\bcould you (?:please )?(?:clarify|specify|provide more)\b",
    r"\bout of scope\b",
    # --- added in v2 ---
    r"\b(?:is|are|was|were) not (?:covered|addressed|described|mentioned|specified|documented|included|listed|provided) (?:by|in) (?:the |these |those |any )?(?:provided |available |given |retrieved )?(?:wix )?(?:help center )?(?:context|articles?|documentation|knowledge base|sources?|materials?|set)\b",
    r"\b(?:the |these |those )?(?:provided |available |given |retrieved |listed )?(?:articles?|context|documentation|sources?|they) (?:here |provided |above |you provided )?(?:do|does|don't|doesn't) not (?:contain|mention|cover|describe|specify|include|address|provide|explain|state|list|give)\b",
    r"\b(?:the |these |those )?(?:provided |available |given |retrieved )?(?:articles?|context|sources?) (?:you provided )?(?:don't|doesn't) (?:contain|mention|cover|describe|specify|include|address|provide|explain|state|list|give)\b",
    r"\b(?:i|we) would need\b",
    r"\b(?:i'm|i am) not seeing (?:any|an|a|information)\b",
    r"\b(?:there isn't|there is no|there's no|isn't|is no) (?:a |an |any )?(?:specific |direct |dedicated )?(?:article|information|content|guidance|steps?|instructions?|details?)\b[^.]{0,60}\b(?:in|from|that|about|for|on)\b",
    r"\bno (?:direct |specific |relevant )?(?:information|article|guidance|content) (?:in|from) the (?:provided |available )?(?:articles?|context)\b",
    r"\bnot possible to answer\b",
    r"\bnone of the (?:provided |listed |available |supplied )?(?:wix )?(?:help center )?(?:articles?|documents?|sources?|entries)\b",
    r"\b(?:i'm|i am) (?:unable|not able) to (?:find|answer|determine|locate)\b",
    r"\bpricing information is not covered\b",
]
_REFUSAL = re.compile("|".join(_REFUSAL_PATTERNS), re.IGNORECASE)
_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'"})
_NUMBERED_STEP = re.compile(r"^[ \t]*\d+[.)]\s+\S", re.MULTILINE)

# How far into the answer a refusal phrase may sit and still count as declining.
REFUSAL_WINDOW = 300


@dataclass(frozen=True)
class CitationScores:
    precision: float | None
    recall: float | None
    n_cited: int
    n_gold: int
    cited_nothing: bool


def citation_scores(cited_doc_ids: list[str], gold_doc_ids: list[str]) -> CitationScores:
    """Compare cited document ids against gold ids. Free — no judge involved.

    Precision is `None`, not zero, when the answer cites nothing: a system that
    declines to cite has not made a false citation, and scoring it as zero would
    reward citing one lucky document over citing none. `cited_nothing` carries that
    case so it can be counted separately. Recall is `None` when there is no gold
    document (the unanswerable split): nothing to recall is not zero recall (MIS-002).
    """
    cited, gold = set(cited_doc_ids), set(gold_doc_ids)
    hits = len(cited & gold)
    return CitationScores(
        precision=(hits / len(cited)) if cited else None,
        recall=(hits / len(gold)) if gold else None,
        n_cited=len(cited),
        n_gold=len(gold),
        cited_nothing=not cited,
    )


@dataclass(frozen=True)
class SpanSupport:
    """How many quoted spans actually appear in the document they were attributed to."""

    supported: int
    total: int
    unsupported_examples: list[str]

    @property
    def rate(self) -> float | None:
        """None, not zero, when the answer quoted nothing: an answer with no spans has
        made no unsupported claim, and scoring it zero would punish chunk-level
        citation for a metric that does not apply to it (MIS-002)."""
        return (self.supported / self.total) if self.total else None


def span_support(
    spans: list[tuple[str, str]], context_by_doc: dict[str, str]
) -> SpanSupport:
    """Check each `[doc:<id>|<quote>]` against the text of the document it names.

    This is what span-level citation buys over chunk-level and the reason P2-14 asks for
    the comparison: a quoted span can be **verified against the source with no LLM and no
    judge**. A document id alone can only be checked for being in the gold set; a span
    can be checked for being true of the thing it cites.

    Matching is on whitespace-normalised, case-folded text. It is deliberately exact
    beyond that: a model that paraphrases while claiming to quote has not supported its
    claim, and softening the match would hide precisely the failure being measured.
    A span attributed to a document that was never retrieved counts as unsupported —
    the model cannot have read it.
    """
    normalised = {
        doc_id: " ".join((text or "").split()).casefold()
        for doc_id, text in context_by_doc.items()
    }
    supported = 0
    unsupported: list[str] = []
    for doc_id, span in spans:
        needle = " ".join(span.split()).casefold()
        haystack = normalised.get(doc_id)
        if haystack and needle and needle in haystack:
            supported += 1
        elif len(unsupported) < 5:
            unsupported.append(f"[doc:{doc_id}] {span[:80]}")
    return SpanSupport(supported=supported, total=len(spans), unsupported_examples=unsupported)


def is_refusal(answer: str) -> bool:
    """Whether the answer declines to answer: a refusal phrase in its opening, and no
    numbered steps anywhere. See `REFUSAL_DETECTOR_VERSION`."""
    text = (answer or "").translate(_APOSTROPHES)
    if _NUMBERED_STEP.search(text):
        return False
    return bool(_REFUSAL.search(text[:REFUSAL_WINDOW]))


# P1-05: the generator must not write links — they are rendered from the doc store's
# `url` field, never generated, so a generated one can only be stale or invented.
# "URL-shaped" means a scheme or a www. host; a bare domain in prose ("connect
# example.com") is a name, not a link, and is deliberately not matched.
_URL_SHAPED = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def find_urls(answer: str) -> list[str]:
    """Every URL-shaped string in a generated answer. Empty is the requirement."""
    return _URL_SHAPED.findall(answer or "")


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
        # 1.0 if the raw model output contains a URL-shaped string (P1-05 forbids it).
        "has_url": float(bool(find_urls(generated_answer))),
    }


def refusal_summary(per_question: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Refusal rate on unanswerable questions, false-refusal rate on answerable ones."""

    def _rate(metric: str) -> tuple[float | None, int]:
        values = [row[metric] for row in per_question.values() if row.get(metric) is not None]
        return (sum(values) / len(values) if values else None, len(values))

    refusal_rate, n_unanswerable = _rate("correct_refusal")
    false_rate, n_answerable = _rate("false_refusal")
    urls = [row["has_url"] for row in per_question.values() if row.get("has_url") is not None]
    return {
        "refusal_rate": refusal_rate,
        "refusal_rate_n": n_unanswerable,
        "false_refusal_rate": false_rate,
        "false_refusal_rate_n": n_answerable,
        "refusal_detector": REFUSAL_DETECTOR_VERSION,
        "answers_with_url": int(sum(urls)),
    }


def scores_as_dict(scores: CitationScores) -> dict[str, Any]:
    return asdict(scores)
