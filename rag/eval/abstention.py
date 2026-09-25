"""Abstention threshold sweep — P2-14, Axis 7.

The deliverable P2-14 asks for is not an operating point, it is the **curve**: how the
false-answer rate on `unanswerable` trades against the false-refusal rate on `dev` as a
confidence threshold moves. A single operating point without the curve it came from is
a claim with its evidence removed.

The mechanism swept here is the cheapest one available: **abstain before generating when
the top retrieval score is below a threshold.** No LLM call, no extra latency, and — the
reason this is reconstructed rather than run — the decision is a pure function of numbers
already in the results store. Per-question retrieval scores and generated answers are
recorded on every Tier 2 row, so every threshold can be evaluated exactly from two
existing runs. Spending experiment slots to re-measure numbers already on disk would be
theatre, the same argument DEC-061 made for the top-k sweep.

Two definitions, and both matter:

- **false answer** — the system returned an answer to a question the corpus cannot
  answer. Counted over the whole `unanswerable` split.
- **false refusal** — the system declined a question it *could* have answered, so it is
  counted only over questions whose gold document actually reached the generator
  (`gold_in_context`). Refusing when retrieval failed is correct behaviour, not a false
  refusal; MIS-012 records why a generation metric must condition on what the generator
  was given.

The threshold composes with the generator's own refusals rather than replacing them: at
threshold T the system answers only when `top1 >= T` **and** the generator chose to
answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rag.eval.generation_metrics import REFUSAL_DETECTOR_VERSION, is_refusal


@dataclass(frozen=True)
class Point:
    """One threshold's operating characteristics."""

    threshold: float
    false_answer_rate: float      # on the unanswerable split
    false_refusal_rate: float     # on answerable dev questions
    dev_answered_rate: float      # share of dev questions that still get an answer
    n_unanswerable: int
    n_answerable: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "threshold": round(self.threshold, 4),
            "false_answer_rate": round(self.false_answer_rate, 4),
            "false_refusal_rate": round(self.false_refusal_rate, 4),
            "dev_answered_rate": round(self.dev_answered_rate, 4),
            "n_unanswerable": self.n_unanswerable,
            "n_answerable": self.n_answerable,
        }


def question_signals(rows: dict[str, Any]) -> list[dict[str, Any]]:
    """Per question: the confidence signal, whether the generator refused, and whether
    the gold document was in front of it. Recomputes the refusal with the CURRENT
    detector rather than trusting the stored flag — MIS-037 is exactly the cost of not
    doing that."""
    out = []
    for row in rows.values():
        scores = json.loads(row["scores"] or "[]")
        if not scores:
            continue
        metrics = json.loads(row["metrics_json"] or "{}")
        answer = row["generated_answer"] or ""
        out.append(
            {
                "top1": float(scores[0]),
                "refused": bool(answer and is_refusal(answer)),
                "gold_in_context": metrics.get("gold_in_context"),
            }
        )
    return out


def sweep(
    dev_rows: dict[str, Any],
    unanswerable_rows: dict[str, Any],
    thresholds: list[float],
) -> list[Point]:
    """The trade-off curve, one point per threshold."""
    dev = question_signals(dev_rows)
    unans = question_signals(unanswerable_rows)
    if not dev or not unans:
        raise ValueError("both splits need per-question scores; is this a Tier 2 run?")
    # Only questions whose gold reached the generator can be falsely refused (MIS-012).
    answerable = [r for r in dev if r["gold_in_context"]]
    if not answerable:
        raise ValueError("no dev question had its gold document in context")

    points = []
    for t in thresholds:
        false_answers = sum(1 for r in unans if r["top1"] >= t and not r["refused"])
        false_refusals = sum(1 for r in answerable if r["top1"] < t or r["refused"])
        answered = sum(1 for r in dev if r["top1"] >= t and not r["refused"])
        points.append(
            Point(
                threshold=float(t),
                false_answer_rate=false_answers / len(unans),
                false_refusal_rate=false_refusals / len(answerable),
                dev_answered_rate=answered / len(dev),
                n_unanswerable=len(unans),
                n_answerable=len(answerable),
            )
        )
    return points


def free_lunch(points: list[Point]) -> Point | None:
    """The highest threshold that costs **no** false refusals against threshold 0.

    Named plainly because it is the one thing in a trade-off curve that is not a trade:
    if a threshold cuts false answers while leaving the false-refusal rate exactly where
    it started, nothing was paid for it. Returns None when no such threshold exists,
    which is the ordinary case and must not be silently reported as zero.
    """
    if not points:
        return None
    base = min(points, key=lambda p: p.threshold)
    free = [
        p for p in points
        if p.false_refusal_rate <= base.false_refusal_rate
        and p.false_answer_rate < base.false_answer_rate
    ]
    return max(free, key=lambda p: p.threshold) if free else None


def format_curve(points: list[Point]) -> str:
    lines = [
        "",
        f"*** ABSTENTION TRADE-OFF (P2-14; detector {REFUSAL_DETECTOR_VERSION}) ***",
        f"    n = {points[0].n_unanswerable} unanswerable, "
        f"{points[0].n_answerable} answerable dev questions",
        "",
        f"    {'threshold':>9} {'false-answer':>13} {'false-refusal':>14} {'dev answered':>13}",
    ]
    for p in points:
        lines.append(
            f"    {p.threshold:>9.3f} {p.false_answer_rate:>13.4f} "
            f"{p.false_refusal_rate:>14.4f} {p.dev_answered_rate:>13.4f}"
        )
    lines.append("")
    return "\n".join(lines)
