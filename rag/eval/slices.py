"""Slice reporting — P0-08.

Aggregates hide findings. A technique that gains four points overall may have
gained twelve on single-document questions and lost four on multi-hop ones, and
only the slice table shows that.

Slices overlap by design: a question with gold documents of two article types is a
member of both type slices. They are not a partition, and no code should sum slice
counts and expect the split size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

ARTICLE_TYPES = ("article", "feature_request", "known_issue")


@dataclass(frozen=True)
class SliceSet:
    """Question ids per slice, plus the boundaries needed to reproduce them."""

    members: dict[str, list[str]]
    meta: dict[str, Any]

    def names(self) -> list[str]:
        return sorted(self.members)


def question_length(question: str) -> int:
    """Length in whitespace tokens. The unit is recorded so terciles are reproducible."""
    return len(question.split())


def build_slices(frame: pd.DataFrame) -> SliceSet:
    """Build every P0-08 slice for one split.

    Tercile boundaries are computed on the split being evaluated and recorded in
    `meta`, because they are a property of that split's question distribution. Two
    splits therefore have different boundaries, and a length-slice number may not
    be carried across splits without saying so.
    """
    members: dict[str, list[str]] = {}

    def add(name: str, mask: pd.Series) -> None:
        members[name] = sorted(frame.loc[mask, "question_id"])

    add("all", pd.Series(True, index=frame.index))
    add("gold_docs:single", frame["n_gold_docs"] == 1)
    add("gold_docs:multi", frame["n_gold_docs"] > 1)

    for article_type in ARTICLE_TYPES:
        mask = frame["article_types"].apply(lambda types: article_type in list(types))
        add(f"article_type:{article_type}", mask)

    for source in sorted(frame["source_config"].unique()):
        add(f"source:{source}", frame["source_config"] == source)

    lengths = frame["question"].apply(question_length)
    low, high = lengths.quantile([1 / 3, 2 / 3]).tolist()
    add("q_len:short", lengths <= low)
    add("q_len:medium", (lengths > low) & (lengths <= high))
    add("q_len:long", lengths > high)

    return SliceSet(
        members=members,
        meta={
            "n_questions": len(frame),
            "length_unit": "whitespace tokens",
            "length_tercile_boundaries": [float(low), float(high)],
            "length_range": [int(lengths.min()), int(lengths.max())],
            "slices_overlap": True,
        },
    )


def aggregate_by_slice(
    per_question: dict[str, dict[str, float | None]],
    slices: SliceSet,
    *,
    min_n: int = 1,
) -> dict[str, dict[str, Any]]:
    """Mean each metric within each slice, carrying the count it was computed over.

    Questions whose value is `None` (metric not applicable, e.g. step coverage on an
    answer with no steps) are excluded from that metric's mean rather than counted
    as zero, and the surviving count travels with the number. A mean over three
    questions is not a finding, and `n` is what lets a reader see that.
    """
    report: dict[str, dict[str, Any]] = {}
    for slice_name, question_ids in slices.members.items():
        rows = [per_question[qid] for qid in question_ids if qid in per_question]
        if len(rows) < min_n:
            continue
        metrics: dict[str, Any] = {"n_questions": len(rows)}
        for metric in sorted({key for row in rows for key in row}):
            values = [row[metric] for row in rows if row.get(metric) is not None]
            if not values:
                continue
            metrics[metric] = sum(values) / len(values)
            if len(values) != len(rows):
                metrics[f"{metric}__n"] = len(values)
        report[slice_name] = metrics
    return report
