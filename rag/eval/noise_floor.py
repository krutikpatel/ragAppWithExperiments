"""Measured run-to-run noise — the minimum detectable difference per metric.

A difference smaller than the run-to-run spread is not a finding (CLAUDE.md
section 3). This module holds the measured floors so `rag diff` applies the rule
instead of a reader remembering it.

Floors are properties of a *configuration family*: judge, provider pin, Ragas
version, generator, prompt, retriever and subsample. Two families have been
measured, each from three identical full runs on the fixed 100-question subsample:

- `phase0-bm25-answer-v1` — EXP-0001's Tier 2 config (DEC-037, 2026-09-11).
- `dense-control-v1` — the Phase 1 dense control, `baseline_dense_tier2.yaml`
  (DEC-046, 2026-09-13). **Active**: it is what Phase 2 diffs against.

The MDD rule (DEC-046): **MDD = max(range, 2 × sample stdev) over the three runs**,
rounded up to three decimals. DEC-037 used the range alone; with three samples
2 × stdev is usually the larger and the two rarely differ by more than 0.001, so
taking the larger keeps DEC-037's conservatism and satisfies P1-11's "2× stdev"
example. A delta at or below the MDD is written as "no measurable difference".

Retrieval metrics carry floors too since the dense control: hosted query
embeddings are not byte-deterministic (OQ-023). BM25's floors are exactly zero.
"""

from __future__ import annotations

MDD_RULE = "max(range, 2 * stdev) over 3 identical runs, rounded up to 0.001"

FLOOR_FAMILIES: dict[str, dict] = {
    "phase0-bm25-answer-v1": {
        "measured_on": {
            "runs": [
                "run_20260911_053316_510b",
                "run_20260911_055914_a8b3",
                "run_20260911_061624_3792",
            ],
            "config": "configs/exp_0001_baseline_tier2.yaml",
            "judge": "openai/gpt-oss-120b",
            "provider_order": ["Cerebras", "Groq"],
            "ragas_version": "0.4.3",
            "generator": "openai/gpt-5-nano",
            "prompt": "answer@v1",
            "retriever": "bm25",
            "subsample": "sub100:b551f7f49c91",
            "date": "2026-09-11",
            "rule": "range over 3 runs (DEC-037)",
        },
        # Range across the three runs. See DEC-037 for the full table.
        "floors": {
            "faithfulness": 0.032,
            "answer_correctness": 0.011,
            "answer_relevance": 0.032,
            # citation floors re-measured under citation-v2 (DEC-043); v1 gave 0.007 / 0.005
            "citation_precision": 0.001,
            "citation_recall": 0.018,
            # re-measured under refusal-lexical-v2 (DEC-045); v1 gave 0.010
            "false_refusal_rate": 0.060,
            "step_coverage": 0.064,
        },
    },
    "dense-control-v1": {
        "measured_on": {
            "runs": [
                "run_20260913_054522_7d37",
                "run_20260913_202416_9156",
                "run_20260913_205058_dc03",
            ],
            "config": "configs/baseline_dense_tier2.yaml",
            "judge": "openai/gpt-oss-120b",
            "provider_order": ["Cerebras", "Groq"],
            "ragas_version": "0.4.3",
            "generator": "openai/gpt-5-nano",
            "prompt": "baseline_answer@v1",
            "retriever": "dense (qwen/qwen3-embedding-8b, DeepInfra)",
            "subsample": "sub100:b551f7f49c91",
            "date": "2026-09-13",
            "rule": MDD_RULE,
        },
        # Corpus-level floors. Per-slice floors are in DEC-046 / EXPERIMENTS.md and
        # are larger: multi-document faithfulness has an MDD of 0.112 at n=26.
        "floors": {
            # judged
            "faithfulness": 0.014,
            "answer_correctness": 0.020,
            "answer_relevance": 0.021,
            # generated (the generator is not deterministic: 1 of 100 answers
            # byte-identical between runs). Citation precision moved 0.071 between
            # two runs of nothing — a citation-precision delta under 0.08 is noise.
            "citation_precision": 0.080,
            "citation_recall": 0.040,
            "cited_nothing": 0.023,
            "step_coverage": 0.097,
            "step_order_preserved": 0.036,
            "false_refusal_rate": 0.031,
            "refused": 0.031,
            # retrieval — hosted query embeddings (OQ-023); one question on n=100
            "strict_recall@1": 0.012,
            "strict_recall@5": 0.012,
            "loose_recall@1": 0.012,
            "loose_recall@5": 0.012,
            "ndcg@10": 0.004,
            "mrr_single_gold": 0.008,
            "collapse_ratio_mean": 0.003,
            "gold_in_context": 0.012,
        },
    },
}

ACTIVE_FAMILY = "dense-control-v1"
MEASURED_ON = FLOOR_FAMILIES[ACTIVE_FAMILY]["measured_on"]
NOISE_FLOOR: dict[str, float] = FLOOR_FAMILIES[ACTIVE_FAMILY]["floors"]


def verdict(metric: str, delta: float) -> str:
    """'finding', 'within noise', or 'no floor measured' for a metric delta.

    Floors are the active family's. A metric without an entry (BM25 retrieval
    metrics: spread exactly zero; latency: not a quality metric) gets no verdict.
    """
    floor = NOISE_FLOOR.get(metric)
    if floor is None:
        return "no floor measured"
    return "finding" if abs(delta) > floor else "within noise"
