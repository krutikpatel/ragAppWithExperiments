"""Measured run-to-run noise of the judged metrics — OQ-017 / DEC-037.

A difference smaller than the run-to-run spread is not a finding (CLAUDE.md
section 3). For deterministic retrieval metrics the spread is zero and every
difference is real. For judged metrics it is not zero, and this module holds the
measured floor so `rag diff` can apply the rule instead of a reader remembering it.

The floors are the RANGE over three identical full runs of EXP-0001's Tier 2 config
on the fixed 100-question subsample — the widest gap seen between two runs that
differed in nothing. Range rather than standard deviation, because three samples is
too few to estimate a distribution and the range is the conservative choice.

These numbers are properties of THIS judge, provider, Ragas version and subsample.
A change to any of those needs the floors re-measured (three runs, ~$2.50).
"""

from __future__ import annotations

MEASURED_ON = {
    "runs": [
        "run_20260911_053316_510b",
        "run_20260911_055914_a8b3",
        "run_20260911_061624_3792",
    ],
    "judge": "openai/gpt-oss-120b",
    "provider_order": ["Cerebras", "Groq"],
    "ragas_version": "0.4.3",
    "subsample": "sub100:b551f7f49c91",
    "date": "2026-09-11",
}

# Range across the three runs. See DEC-037 for the full table.
JUDGED_NOISE_FLOOR: dict[str, float] = {
    "faithfulness": 0.032,
    "answer_correctness": 0.011,
    "answer_relevance": 0.032,
}

# Deterministic generation metrics also vary run to run, because the generator is
# not deterministic at temperature 0 (0 of 100 answers were byte-identical across
# the three runs). Their floors are small — except step coverage, whose floor is
# half its own value and which therefore cannot currently detect anything.
GENERATION_NOISE_FLOOR: dict[str, float] = {
    "citation_precision": 0.007,
    "citation_recall": 0.005,
    "false_refusal_rate": 0.010,
    "step_coverage": 0.064,
}

NOISE_FLOOR = {**JUDGED_NOISE_FLOOR, **GENERATION_NOISE_FLOOR}


def verdict(metric: str, delta: float) -> str:
    """'finding', 'within noise', or 'no floor measured' for a metric delta.

    Retrieval metrics have no entry: their spread is zero, so any delta is real and
    the caller should not ask.
    """
    floor = NOISE_FLOOR.get(metric)
    if floor is None:
        return "no floor measured"
    return "finding" if abs(delta) > floor else "within noise"
