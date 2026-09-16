"""`rag compare <run_a> <run_b> --metric <m>` — P2-01, paired significance testing.

Retrieval metrics are deterministic: same index, same query, same ranking. Running
a config three times and averaging measures nothing. What does carry information is
the *pairing*: every question was scored under both runs, so the per-question
differences are the sample, and the question is whether their mean is
distinguishable from zero.

Two resampling tests over the paired differences, both seeded and recorded:

- **paired bootstrap** — resample questions with replacement, recompute the mean
  difference; the 2.5th–97.5th percentiles are the 95% CI *on the difference*.
- **sign-flip permutation test** — under the null that A and B are exchangeable,
  each question's difference is equally likely to have had the other sign; the
  p-value is the share of random sign assignments whose |mean| reaches the observed
  one (with the +1 correction so it is never exactly zero).

For a binary metric the discordant pairs also give the exact McNemar p-value, which
needs no resampling and is reported as a cross-check.

Zero LLM calls; the per-question outcomes are read from `run_questions`. Hosted dense
query embeddings are not byte-deterministic (OQ-023), so a "deterministic" dense
run carries a ~0.005 floor that this test does not see; DEC-047 says how the two
rules combine. A run whose pipeline itself called an LLM (P2-03) is flagged here
when its generation cache did not back every call.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

from rag.runner.diff import compare_provenance
from rag.runner.store import ResultsStore

DEFAULT_METRIC = "strict_recall@5"
DEFAULT_SEED = 20260915
DEFAULT_RESAMPLES = 10_000
# Slices on which P2-01 asks for the test. Others in the P0-08 set are reported too;
# these are named so a caller can pick them out.
HEADLINE_SLICES = ("gold_docs:single", "gold_docs:multi")


def compare_runs(
    run_a: str,
    run_b: str,
    *,
    metric: str = DEFAULT_METRIC,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    store: ResultsStore | None = None,
    slices: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Paired test of `metric` between two runs, overall and per slice.

    `slices` maps slice name to question ids; when omitted they are rebuilt from the
    runs' split with `rag.eval.slices.build_slices`, exactly as the runner built
    them, restricted to the questions both runs scored.
    """
    owns = store is None
    store = store or ResultsStore()
    try:
        return _compare(store, run_a, run_b, metric, seed, resamples, slices)
    finally:
        if owns:
            store.close()


def _compare(
    store: ResultsStore,
    run_a: str,
    run_b: str,
    metric: str,
    seed: int,
    resamples: int,
    slices: dict[str, list[str]] | None,
) -> dict[str, Any]:
    meta_a, meta_b = store.get_run(run_a), store.get_run(run_b)
    for run_id, meta in ((run_a, meta_a), (run_b, meta_b)):
        if meta is None:
            raise KeyError(f"no run {run_id!r} in {store.path}")
    comparability = compare_provenance(meta_a, meta_b)
    warnings = _pipeline_warnings(meta_a, meta_b)

    questions_a, questions_b = store.get_questions(run_a), store.get_questions(run_b)
    shared = sorted(set(questions_a) & set(questions_b))
    values_a, values_b, excluded = {}, {}, 0
    for question_id in shared:
        va = json.loads(questions_a[question_id]["metrics_json"] or "{}").get(metric)
        vb = json.loads(questions_b[question_id]["metrics_json"] or "{}").get(metric)
        if va is None or vb is None:
            # Not applicable on one side (MIS-002): the pair is dropped, and counted.
            excluded += 1
            continue
        values_a[question_id], values_b[question_id] = float(va), float(vb)
    paired = sorted(values_a)
    if not paired:
        raise ValueError(f"no question has {metric!r} scored in both runs")

    binary = all(v in (0.0, 1.0) for v in values_a.values()) and all(
        v in (0.0, 1.0) for v in values_b.values()
    )

    if slices is None:
        slices = _slices_from_split(meta_b["split"], paired)

    overall = _paired_test(
        np.array([values_a[q] for q in paired]),
        np.array([values_b[q] for q in paired]),
        binary=binary,
        rng=np.random.default_rng(seed),
        resamples=resamples,
    )
    per_slice: dict[str, Any] = {}
    for index, name in enumerate(sorted(slices)):
        members = [q for q in slices[name] if q in values_a]
        if len(members) < 2 or name == "all":
            continue
        per_slice[name] = _paired_test(
            np.array([values_a[q] for q in members]),
            np.array([values_b[q] for q in members]),
            binary=binary,
            # One seed, one derived stream per slice, so the report is reproducible
            # regardless of which slices exist on a given split.
            rng=np.random.default_rng([seed, index + 1]),
            resamples=resamples,
        )

    # Judged aggregates are labelled against MDD here too (P2-02), so one command
    # gives both verdicts: the paired test for deterministic metrics, the noise
    # floor for judged ones.
    from rag.eval.noise_floor import judged_report

    return {
        "run_a": run_a,
        "run_b": run_b,
        "metric": metric,
        "binary": binary,
        "method": (
            "paired bootstrap 95% CI (percentile) and sign-flip permutation p-value on the "
            "per-question difference (B − A)" + ("; exact McNemar p on discordant pairs" if binary else "")
        ),
        "seed": seed,
        "resamples": resamples,
        "comparable": comparability["comparable"],
        "comparability": comparability,
        "warnings": warnings,
        "n_shared_questions": len(shared),
        "n_paired": len(paired),
        "n_excluded_not_applicable": excluded,
        "overall": overall,
        "slices": per_slice,
        "mdd": judged_report(meta_a, meta_b),
    }


def _paired_test(
    a: np.ndarray, b: np.ndarray, *, binary: bool, rng: np.random.Generator, resamples: int
) -> dict[str, Any]:
    diffs = b - a
    n = len(diffs)
    observed = float(diffs.mean())

    boot = np.empty(resamples)
    perm = np.empty(resamples)
    # Batched so a 6,221-question split at 10,000 resamples stays in a few tens of
    # MB rather than materialising a 62M-element index matrix.
    batch = max(1, min(resamples, 2_000_000 // max(n, 1)))
    for start in range(0, resamples, batch):
        size = min(batch, resamples - start)
        idx = rng.integers(0, n, size=(size, n))
        boot[start : start + size] = diffs[idx].mean(axis=1)
        signs = rng.integers(0, 2, size=(size, n)) * 2 - 1
        perm[start : start + size] = (diffs * signs).mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    # Tolerance: sign flips produce the observed mean exactly, and float sums of
    # the same values in a different order must still count as reaching it.
    p_perm = float((np.sum(np.abs(perm) >= abs(observed) - 1e-12) + 1) / (resamples + 1))

    result: dict[str, Any] = {
        "n": int(n),
        "mean_a": round(float(a.mean()), 4),
        "mean_b": round(float(b.mean()), 4),
        "delta": round(observed, 4),
        "ci95": [round(float(lo), 4), round(float(hi), 4)],
        "p_value": round(p_perm, 4),
        "significant_at_0_05": p_perm < 0.05,
    }
    if binary:
        both_correct = int(np.sum((a == 1) & (b == 1)))
        both_wrong = int(np.sum((a == 0) & (b == 0)))
        a_only = int(np.sum((a == 1) & (b == 0)))
        b_only = int(np.sum((a == 0) & (b == 1)))
        result["contingency"] = {
            "both_correct": both_correct,
            "both_wrong": both_wrong,
            "a_only": a_only,
            "b_only": b_only,
        }
        result["mcnemar_exact_p"] = round(mcnemar_exact_p(a_only, b_only), 4)
    else:
        result["contingency"] = {
            "b_higher": int(np.sum(diffs > 0)),
            "a_higher": int(np.sum(diffs < 0)),
            "tied": int(np.sum(diffs == 0)),
        }
    return result


def mcnemar_exact_p(a_only: int, b_only: int) -> float:
    """Two-sided exact McNemar test: discordant pairs under Binomial(n, 0.5)."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def _slices_from_split(split: str, question_ids: list[str]) -> dict[str, list[str]]:
    """The P0-08 slices, rebuilt on exactly the questions being compared — the
    same construction the runner used, so tercile boundaries match a Tier 2
    subsample rather than the whole split."""
    from rag.dataset.loader import load_split
    from rag.eval.slices import build_slices

    frame = load_split(split)
    frame = frame[frame["question_id"].isin(question_ids)].reset_index(drop=True)
    return build_slices(frame).members


def _pipeline_warnings(meta_a: dict[str, Any], meta_b: dict[str, Any]) -> list[str]:
    """P2-03: an in-pipeline LLM call makes retrieval outcomes non-deterministic unless
    the generation cache served every call. The paired test assumes fixed outcomes."""
    warnings = []
    for meta in (meta_a, meta_b):
        if not meta.get("pipeline_nondeterministic"):
            continue
        stats = json.loads(meta.get("pipeline_llm_json") or "{}")
        hit_rate = stats.get("hit_rate")
        if hit_rate is None or hit_rate < 1.0:
            warnings.append(
                f"{meta['run_id']}: the pipeline called an LLM and the generation cache "
                f"backed {'none' if hit_rate is None else f'{hit_rate:.0%}'} of those calls; "
                "its per-question outcomes are not reproducible, so the paired test's "
                "fixed-outcome assumption does not hold. Repeat it with a warm cache (P2-03)."
            )
    return warnings


def format_compare(report: dict[str, Any]) -> str:
    lines = [
        f"{report['run_a']}  →  {report['run_b']}   metric {report['metric']}"
        f"{' (binary)' if report['binary'] else ' (graded)'}",
        report["comparability"]["verdict"],
    ]
    lines += [f"WARNING: {w}" for w in report["warnings"]]
    lines.append(
        f"paired on {report['n_paired']} questions "
        f"({report['n_excluded_not_applicable']} excluded as not applicable); "
        f"seed {report['seed']}, {report['resamples']} resamples"
    )
    lines.append("")
    lines.append(_format_test("overall", report["overall"]))
    for name, result in report["slices"].items():
        lines.append(_format_test(name, result))
    mdd = report.get("mdd") or {}
    if mdd.get("metrics"):
        lines.append("")
        lines.append(
            f"MDD verdicts (family {mdd['family'] or 'none'}, retrieval family "
            f"{mdd['retrieval_family'] or 'none'}):"
        )
        for info in mdd["metrics"].values():
            if info["mdd"] is not None:
                lines.append(f"  {info['text']}")
        for entries in mdd.get("slices", {}).values():
            for info in entries.values():
                if info["mdd"] is not None:
                    lines.append(f"  {info['text']}")
        for note in mdd.get("notes", []):
            lines.append(f"  note: {note}")
    return "\n".join(lines)


def _format_test(name: str, r: dict[str, Any]) -> str:
    c = r["contingency"]
    if "both_correct" in c:
        cont = (
            f"both✓ {c['both_correct']}  both✗ {c['both_wrong']}  "
            f"A-only {c['a_only']}  B-only {c['b_only']}  McNemar p {r['mcnemar_exact_p']:.4f}"
        )
    else:
        cont = f"B higher {c['b_higher']}  A higher {c['a_higher']}  tied {c['tied']}"
    return (
        f"{name:<26} n={r['n']:<5} {r['mean_a']:.4f} → {r['mean_b']:.4f}  Δ{r['delta']:+.4f}  "
        f"CI95 [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}]  p={r['p_value']:.4f}"
        f"{' *' if r['significant_at_0_05'] else '  '}  {cont}"
    )
