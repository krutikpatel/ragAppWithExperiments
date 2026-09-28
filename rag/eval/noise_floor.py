"""Measured run-to-run noise — the minimum detectable difference per metric.

A difference smaller than the run-to-run spread is not a finding (CLAUDE.md
section 3). This module holds the measured floors so `rag diff` and `rag compare`
apply the rule instead of a reader remembering it.

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

P2-02 (DEC-048) adds the family *matching*: a run gets the floors of the family whose
judge, generator and prompt provenance it shares, found from the run row, so an old
result keeps its old MDD and a run under a changed judge gets **no** MDD until P1-11
is re-run for it. It is never silently given the active family's numbers.
"""

from __future__ import annotations

import json
from typing import Any

MDD_RULE = "max(range, 2 * stdev) over 3 identical runs, rounded up to 0.001"

# The judged criteria — their MDD is judge noise. Every other floored metric is
# generator noise (citations, steps, refusal) or embedding noise (retrieval).
JUDGED_METRICS = ("faithfulness", "answer_correctness", "answer_relevance")
RETRIEVAL_METRICS = (
    "strict_recall@1", "strict_recall@3", "strict_recall@5", "strict_recall@10", "strict_recall@20",
    "loose_recall@1", "loose_recall@3", "loose_recall@5", "loose_recall@10", "loose_recall@20",
    "ndcg@10", "mrr_single_gold", "collapse_ratio_mean", "gold_in_context",
)

# A judged delta above the MDD but not above this multiple of it is "marginal":
# significant by the rule, but close enough to the floor that P2-02 spends three
# replicates on it before anything is promoted. Above it, no replicates.
REPLICATE_ZONE_MULTIPLE = 1.5

# Run-row fields that must be equal for a family's judged/generated floors to apply.
# These are exactly P2-02's re-measurement triggers (judge model, judge prompt via
# the Ragas fingerprints and version) plus the generator and its prompt, which
# DEC-046 showed are the noisier instrument for citation metrics.
JUDGED_MATCH_KEYS = (
    "judge_model",
    "judge_provider_order",
    "judge_embedding_model",
    "ragas_version",
    "metric_prompt_versions",
    "generator_model",
    "prompt_versions",
)
# Fields the floors were measured under but which a Phase 2 axis run legitimately
# changes. A mismatch is reported as a caveat on the verdict, not as a refusal:
# the P2-02 rule keeps P1-11's MDD across axes unless the judge changes.
CONTEXT_KEYS = ("retriever", "eval_subsample_id")

_RAGAS_0_4_3_PROMPTS = {
    "faithfulness": "sha256:475517e1d53e61ad",
    "answer_correctness": "sha256:24e941af1230520b",
    "answer_relevance": "sha256:4417e7484c29c546",
}

FLOOR_FAMILIES: dict[str, dict] = {
    "phase0-bm25-answer-v1": {
        "effective_date": "2026-09-11",
        "decision": "DEC-037",
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
        # Run-row provenance, as stored, that a run must share to use these floors.
        "match": {
            "judge_model": "openai/gpt-oss-120b",
            "judge_provider_order": ["Cerebras", "Groq"],
            "judge_embedding_model": "qwen/qwen3-embedding-8b",
            "ragas_version": "0.4.3",
            "metric_prompt_versions": _RAGAS_0_4_3_PROMPTS,
            "generator_model": "openai/gpt-5-nano",
            "prompt_versions": {"answer": "answer@v1"},
        },
        "context": {"retriever": "bm25", "eval_subsample_id": "sub100:b551f7f49c91"},
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
        "slice_floors": {},
    },
    "dense-control-v1": {
        "effective_date": "2026-09-13",
        "decision": "DEC-046",
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
        "match": {
            "judge_model": "openai/gpt-oss-120b",
            "judge_provider_order": ["Cerebras", "Groq"],
            "judge_embedding_model": "qwen/qwen3-embedding-8b",
            "ragas_version": "0.4.3",
            "metric_prompt_versions": _RAGAS_0_4_3_PROMPTS,
            "generator_model": "openai/gpt-5-nano",
            "prompt_versions": {"answer": "baseline_answer@v1"},
        },
        "context": {"retriever": "dense", "eval_subsample_id": "sub100:b551f7f49c91"},
        # Corpus-level floors. Per-slice floors are below and are larger:
        # multi-document faithfulness has an MDD of 0.112 at n=26.
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
        # DEC-046, per-slice judged MDDs (n in parentheses in the decision entry).
        "slice_floors": {
            "all": {"faithfulness": 0.014, "answer_correctness": 0.020, "answer_relevance": 0.021},
            "gold_docs:single": {"faithfulness": 0.042, "answer_correctness": 0.028, "answer_relevance": 0.005},
            "gold_docs:multi": {"faithfulness": 0.112, "answer_correctness": 0.050, "answer_relevance": 0.074},
            "source:expertwritten": {"faithfulness": 0.039, "answer_correctness": 0.030, "answer_relevance": 0.021},
            "source:simulated": {"faithfulness": 0.025, "answer_correctness": 0.024, "answer_relevance": 0.043},
            "q_len:short": {"faithfulness": 0.041, "answer_correctness": 0.053, "answer_relevance": 0.019},
            "q_len:medium": {"faithfulness": 0.007, "answer_correctness": 0.033, "answer_relevance": 0.023},
            "q_len:long": {"faithfulness": 0.047, "answer_correctness": 0.050, "answer_relevance": 0.067},
        },
    },
    # P3-07 (DEC-083): the production judge on the golden CI slice, as `rag faithfulness`
    # rows record it. Three FULL runs (fresh generation + fresh judging, --no-cache),
    # 79 / 76 / 76 answers judged. `judge_only_floors` are two extra re-judges of run 1's
    # answers: the judge alone, generator held fixed. Matches faithfulness rows only (their
    # metric_prompt_versions name faithfulness alone and no judge embedder).
    "golden-v1-deepseek": {
        "effective_date": "2026-09-28",
        "decision": "DEC-083",
        "measured_on": {
            "generation_runs": [
                "run_20260928_194258_4916", "run_20260928_201450_6074", "run_20260928_203058_bc14",
            ],
            "runs": [
                "run_20260928_200150_ffb0", "run_20260928_203053_9597", "run_20260928_204237_e726",
            ],
            "judge_only_runs": [
                "run_20260928_200150_ffb0", "run_20260928_200828_9a46", "run_20260928_201447_9e59",
            ],
            "config": "configs/golden_generate_v2.yaml + rag faithfulness (configs/baseline_dense_tier2_v2.yaml judge)",
            "judge": "deepseek/deepseek-v4.1-flash",
            "provider_order": ["DeepInfra"],
            "ragas_version": "0.4.3",
            "generator": "openai/gpt-5-nano",
            "prompt": "baseline_answer@v1",
            "retriever": "dense (qwen/qwen3-embedding-8b, DeepInfra)",
            "subsample": "golden_v1 (95 questions, full)",
            "date": "2026-09-28",
            "rule": MDD_RULE,
        },
        "match": {
            "judge_model": "deepseek/deepseek-v4.1-flash",
            "judge_provider_order": ["DeepInfra"],
            "judge_embedding_model": None,  # faithfulness rows record NULL, not ""
            "ragas_version": "0.4.3",
            "metric_prompt_versions": {"faithfulness": _RAGAS_0_4_3_PROMPTS["faithfulness"]},
            "generator_model": "openai/gpt-5-nano",
            "prompt_versions": {"answer": "baseline_answer@v1"},
        },
        "context": {"retriever": None, "eval_subsample_id": "full:sha256:253982866"},
        # Corpus level ("all": 95 questions). Names are `rag faithfulness` metrics.
        "floors": {
            "mean_faithfulness": 0.026,
            "unsupported_answer_rate": 0.064,
            "refusal_rate": 0.073,
            "false_answer_rate": 0.077,
            "citation_integrity": 0.016,
        },
        "judge_only_floors": {
            "mean_faithfulness": 0.023,
            "unsupported_answer_rate": 0.057,
            "refusal_rate": 0.0,
            "false_answer_rate": 0.0,
            "citation_integrity": 0.0,
        },
        "slice_floors": {
            "answerable": {"mean_faithfulness": 0.031, "unsupported_answer_rate": 0.051,
                           "refusal_rate": 0.073, "citation_integrity": 0.017},
            "unanswerable": {"mean_faithfulness": 0.092, "unsupported_answer_rate": 0.306,
                             "false_answer_rate": 0.077, "citation_integrity": 0.0},
            "stratum:single_doc": {"mean_faithfulness": 0.041, "unsupported_answer_rate": 0.016,
                                   "refusal_rate": 0.161, "citation_integrity": 0.039},
            "stratum:multi_doc": {"mean_faithfulness": 0.028, "unsupported_answer_rate": 0.095,
                                  "refusal_rate": 0.058, "citation_integrity": 0.065},
            "stratum:answered_without_gold": {"mean_faithfulness": 0.067, "unsupported_answer_rate": 0.079,
                                              "refusal_rate": 0.043, "citation_integrity": 0.049},
        },
    },
}

ACTIVE_FAMILY = "dense-control-v1"
MEASURED_ON = FLOOR_FAMILIES[ACTIVE_FAMILY]["measured_on"]
NOISE_FLOOR: dict[str, float] = FLOOR_FAMILIES[ACTIVE_FAMILY]["floors"]

NO_MDD = "no MDD measured"


def _loads(value: Any) -> Any:
    """Run rows store JSON in TEXT columns; family tables hold the parsed value."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def family_for_run(meta: dict[str, Any] | None) -> tuple[str | None, list[str]]:
    """The floor family whose judge/generator/prompt provenance this run row shares.

    Returns `(family_name, caveats)`. No family — the run's judge, generator or
    prompt differ from every measured family — returns `(None, [reason])`, and the
    caller reports "no MDD measured" rather than borrowing a floor (P2-02: a changed
    judge means P1-11 is re-run, and old results keep their old MDD). Newest family
    first, so a run matching two gets the later measurement.
    """
    if not meta:
        return None, ["no run row to match a floor family against"]
    if not meta.get("judge_model"):
        # Tier 1: nothing judged or generated, so no judged family is needed.
        return None, []
    ordered = sorted(FLOOR_FAMILIES.items(), key=lambda item: item[1]["effective_date"], reverse=True)
    for name, family in ordered:
        if all(_loads(meta.get(key)) == family["match"][key] for key in JUDGED_MATCH_KEYS):
            caveats = [
                f"{key} differs from the family's ({meta.get(key)!r} vs {family['context'][key]!r}); "
                f"the floors were measured under the family's — DEC-046's revisit trigger"
                for key in CONTEXT_KEYS
                if meta.get(key) != family["context"][key]
            ]
            return name, caveats
    return None, [
        "no floor family matches this run's judge/generator/prompt provenance "
        f"({', '.join(JUDGED_MATCH_KEYS)}); re-run P1-11 (three identical runs) before "
        "reporting any judged delta for it (P2-02)"
    ]


def retrieval_family_for_run(meta: dict[str, Any] | None) -> str | None:
    """Retrieval floors depend on the retriever alone (hosted embedding noise,
    OQ-023), so a Tier 1 dense run gets the dense control's retrieval floors even
    though it has no judge to match."""
    if not meta:
        return None
    for name, family in sorted(
        FLOOR_FAMILIES.items(), key=lambda item: item[1]["effective_date"], reverse=True
    ):
        if meta.get("retriever") == family["context"]["retriever"] and any(
            metric in family["floors"] for metric in RETRIEVAL_METRICS
        ):
            return name
    return None


def floor_for(metric: str, family: str | None, slice_name: str | None = None) -> float | None:
    if family is None:
        return None
    table = FLOOR_FAMILIES[family]
    if slice_name and slice_name != "all":
        return table["slice_floors"].get(slice_name, {}).get(metric)
    return table["floors"].get(metric)


def mdd_verdict(
    metric: str,
    delta: float,
    *,
    family: str | None = ACTIVE_FAMILY,
    slice_name: str | None = None,
) -> dict[str, Any]:
    """Label a delta against its MDD. The label is the tool's, not the prose's (P2-02).

    label: 'significant' | 'within judge noise' | 'within noise' | 'no MDD measured'.
    `replicates_advised` marks the marginal zone MDD < |Δ| ≤ 1.5 × MDD, where
    P2-02 spends three replicates before promoting.
    """
    mdd = floor_for(metric, family, slice_name)
    judged = metric in JUDGED_METRICS
    if mdd is None:
        return {
            "metric": metric, "delta": round(delta, 4), "mdd": None, "family": family,
            "slice": slice_name or "all", "label": NO_MDD, "ratio": None,
            "replicates_advised": False,
        }
    # MDDs are stated to three decimals (DEC-046 rounds up to 0.001), so the delta
    # is compared at that precision — a fourth decimal would be false precision.
    magnitude = round(abs(delta), 3)
    ratio = magnitude / mdd if mdd > 0 else (float("inf") if magnitude else 0.0)
    if magnitude > mdd:
        label = "significant"
    else:
        label = "within judge noise" if judged else "within noise"
    return {
        "metric": metric,
        "delta": round(delta, 4),
        "mdd": mdd,
        "family": family,
        "slice": slice_name or "all",
        "label": label,
        "ratio": round(ratio, 2) if ratio != float("inf") else None,
        "replicates_advised": label == "significant" and ratio <= REPLICATE_ZONE_MULTIPLE,
    }


def verdict(metric: str, delta: float) -> str:
    """Corpus-level label under the active family. See `mdd_verdict` for the full form."""
    return mdd_verdict(metric, delta, family=ACTIVE_FAMILY)["label"]


def format_judged(metric: str, value: float, baseline: float, info: dict[str, Any]) -> str:
    """The P2-02 line: `faithfulness 0.740 (baseline 0.710, Δ+0.030, MDD ±0.014 → significant)`."""
    delta = value - baseline
    if info["mdd"] is None:
        return f"{metric} {value:.3f} (baseline {baseline:.3f}, Δ{delta:+.3f}, {NO_MDD})"
    tail = " — marginal, resolve with 3 replicates" if info["replicates_advised"] else ""
    return (
        f"{metric} {value:.3f} (baseline {baseline:.3f}, Δ{delta:+.3f}, "
        f"MDD ±{info['mdd']:.3f} → {info['label']}{tail})"
    )


def judged_report(
    meta_a: dict[str, Any], meta_b: dict[str, Any], *, with_slices: bool = True
) -> dict[str, Any]:
    """Every floored aggregate metric both runs report, labelled against the MDD of
    the family run B (the candidate) belongs to. A is the baseline.

    Judged and generated metrics need a judged-family match; retrieval metrics need
    only the retriever to match. Runs in different families get no verdicts.
    """
    fam_a, _ = family_for_run(meta_a)
    fam_b, caveats = family_for_run(meta_b)
    ret_a, ret_b = retrieval_family_for_run(meta_a), retrieval_family_for_run(meta_b)
    notes: list[str] = list(caveats)
    judged_runs = bool(meta_a.get("judge_model") or meta_b.get("judge_model"))
    if judged_runs and fam_a != fam_b:
        notes.append(
            f"runs belong to different floor families ({fam_a!r} vs {fam_b!r}); "
            "judged deltas get no verdict"
        )
    if ret_a != ret_b:
        notes.append(
            f"retrievers differ ({meta_a.get('retriever')!r} vs {meta_b.get('retriever')!r}), so "
            "no single retrieval floor applies; the paired test (rag compare) is the verdict "
            "on retrieval deltas"
        )

    agg_a, agg_b = _loads(meta_a.get("metrics_json")) or {}, _loads(meta_b.get("metrics_json")) or {}
    metrics: dict[str, Any] = {}
    for key in sorted(set(agg_a) & set(agg_b)):
        va, vb = agg_a[key], agg_b[key]
        if not _is_number(va) or not _is_number(vb):
            continue
        if key in RETRIEVAL_METRICS:
            family = ret_b if ret_a == ret_b else None
        else:
            family = fam_b if fam_a == fam_b else None
        info = mdd_verdict(key, vb - va, family=family)
        info["a"], info["b"] = va, vb
        info["text"] = format_judged(key, vb, va, info)
        metrics[key] = info

    slices: dict[str, Any] = {}
    if with_slices and fam_a == fam_b and fam_b is not None:
        sl_a, sl_b = _loads(meta_a.get("slices_json")) or {}, _loads(meta_b.get("slices_json")) or {}
        for slice_name in sorted(set(sl_a) & set(sl_b)):
            if slice_name == "all":
                continue  # the corpus-level block above already carries it
            for key in JUDGED_METRICS:
                va, vb = sl_a[slice_name].get(key), sl_b[slice_name].get(key)
                if not _is_number(va) or not _is_number(vb):
                    continue
                info = mdd_verdict(key, vb - va, family=fam_b, slice_name=slice_name)
                info["a"], info["b"] = va, vb
                info["n"] = sl_b[slice_name].get("n_questions")
                info["text"] = format_judged(f"{slice_name} {key}", vb, va, info)
                slices.setdefault(slice_name, {})[key] = info

    return {
        "family": fam_b if fam_a == fam_b else None,
        "retrieval_family": ret_b if ret_a == ret_b else None,
        "effective_date": FLOOR_FAMILIES[fam_b]["effective_date"] if fam_b else None,
        "notes": notes,
        "metrics": metrics,
        "slices": slices,
    }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
