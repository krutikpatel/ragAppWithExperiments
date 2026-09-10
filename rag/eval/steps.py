"""Step extraction and coverage — part of P0-07.

Wix support answers are often procedures. A system can retrieve exactly the right
article and still fail by dropping step 4 or reordering it, and a faithfulness
judge will not notice: every step it did emit was faithful. Step coverage is the
metric that catches that.

It applies to fewer answers than the handover assumes. Of 200 `dev` reference
answers, 54 contain a numbered list; the rest are prose. The metric is therefore
reported over the procedural subset only, with `n` attached, and returns `None`
elsewhere rather than a zero that would drag an average toward a number that means
nothing. See MIS-002.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# "1. text" or "1) text" at the start of a line. Bullet markers are deliberately not
# treated as steps: bullets in this corpus are unordered facts ("Payouts are held
# if: ..."), and scoring order over them would invent a constraint the answer never
# had.
_NUMBERED_STEP = re.compile(r"^[ \t]*(\d+)[.)]\s+(.*)$", re.MULTILINE)

_MD_LINK = re.compile(r"\[([^\]]*)\]\s*\(([^)]*)\)")
_NON_WORD = re.compile(r"[^a-z0-9]+")

MIN_STEPS = 2
MATCH_THRESHOLD = 0.5

# Function words carry no procedural content; keeping them would let two unrelated
# steps match on "the", "to", "your".
_STOPWORDS = frozenset(
    """a an and are as at be by can click for from go had has have in into is it its
    of on or select tab that the then this to under up using was were will with you
    your""".split()
)


@dataclass(frozen=True)
class StepCoverage:
    coverage: float | None
    order_preserved: bool | None
    n_reference_steps: int
    n_generated_steps: int
    matched: int
    applicable: bool


def extract_steps(markdown: str | None) -> list[str]:
    """Ordered step texts from a markdown answer. Empty if it is not a procedure.

    Tolerates None so a metric never crashes a whole run on one odd answer. A None
    answer is still a bug worth failing on, but that failure belongs at the point of
    generation (see `EmptyGenerationError`), not here.
    """
    if not markdown:
        return []
    return [
        match.group(2).strip()
        for match in _NUMBERED_STEP.finditer(markdown)
        if match.group(2).strip()
    ]


def _content_tokens(text: str) -> set[str]:
    text = _MD_LINK.sub(r"\1", text).lower()
    tokens = {token for token in _NON_WORD.split(text) if token}
    return tokens - _STOPWORDS


def _similarity(left: str, right: str) -> float:
    """Jaccard overlap of content tokens.

    A crude proxy for "the same step, reworded". It is deliberately not a judge
    call: step coverage has to stay free so it can run on every Tier 2 question
    without adding LLM cost, and a lexical threshold is auditable in a way a model
    score is not. Its bluntness is recorded as OQ-007.
    """
    a, b = _content_tokens(left), _content_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def step_coverage(
    reference_answer: str,
    generated_answer: str,
    *,
    threshold: float = MATCH_THRESHOLD,
    min_steps: int = MIN_STEPS,
) -> StepCoverage:
    """Fraction of reference steps present in the generated answer, and their order.

    Each reference step is matched to its best-scoring generated step above the
    threshold, greedily and without reuse, so two reference steps cannot both claim
    the same generated one. Order is preserved when the matched generated indices
    increase monotonically.
    """
    reference_steps = extract_steps(reference_answer)
    generated_steps = extract_steps(generated_answer)

    if len(reference_steps) < min_steps:
        return StepCoverage(
            coverage=None,
            order_preserved=None,
            n_reference_steps=len(reference_steps),
            n_generated_steps=len(generated_steps),
            matched=0,
            applicable=False,
        )

    used: set[int] = set()
    matched_indices: list[int] = []
    for step in reference_steps:
        best_index, best_score = None, threshold
        for index, candidate in enumerate(generated_steps):
            if index in used:
                continue
            score = _similarity(step, candidate)
            if score >= best_score:
                best_index, best_score = index, score
        if best_index is not None:
            used.add(best_index)
            matched_indices.append(best_index)

    matched = len(matched_indices)
    return StepCoverage(
        coverage=matched / len(reference_steps),
        order_preserved=matched_indices == sorted(matched_indices),
        n_reference_steps=len(reference_steps),
        n_generated_steps=len(generated_steps),
        matched=matched,
        applicable=True,
    )
