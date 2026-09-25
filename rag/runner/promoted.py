"""`configs/promoted.yaml` — the committed "current best" (P2-05) and the split
policy that decides when it moves (P2-04).

The pointer is a file, not a reconstruction from the results table. It advances
only through `rag promote`, which re-runs the comparison it is asked to trust,
checks it against the split policy, and appends a row to the promotion log in
DECISIONS.md. Every axis experiment is a diff against this file, and the runner
records that diff on the run row so "changed one dimension" is checked, not assumed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.paths import CONFIGS_DIR
from rag.runner.config import DEV_ONLY_AXES, RETRIEVAL_AXES, EvalTier, RunConfig, load_config_file
from rag.runner.decision_log import append_row, count_rows

PROMOTED_PATH = CONFIGS_DIR / "promoted.yaml"
PROMOTION_LOG_HEADING = "## Promotion log"
PROMOTION_EMPTY_ROW = (
    "| _(none)_ | — | — | — | — | — | `promoted.yaml` is the dense control (EXP-0005); no axis winner yet. |"
)

# Which config fields belong to which dimension. A one-axis experiment changes
# fields in exactly one of these groups; run settings (split, tier, seed, name…)
# are not dimensions.
DIMENSIONS = {
    "chunking": ("chunker", "chunker_params"),
    "retrieval": ("retriever", "retriever_params"),
    "reranking": ("reranker", "reranker_params", "rerank_candidates"),
    "query_transform": ("query_transform", "query_transform_params"),
    "assembly": ("top_k", "candidate_pool", "retrieval_depth", "doc_pooling", "context_max_tokens",
                 "context_order", "context_compressor", "context_compressor_params"),
    "generation": (
        "generator_model", "generator_prompt", "generator_max_tokens", "generator_reasoning_effort",
        # P2-14: the self-check replaces an answer with a refusal, so it is a change to
        # what the generation step returned.
        "grounding_check", "grounding_check_params",
    ),
}
RUN_SETTINGS = (
    "name", "axis", "split", "eval_tier", "seed", "eval_subsample_size", "eval_subsample_seed",
    "full_eval", "harness_smoke_test", "judge_model", "judge_temperature", "judge_max_tokens",
    "judge_provider_order", "judge_concurrency", "judge_embedding_model",
)


def load_promoted(path: Path = PROMOTED_PATH) -> RunConfig:
    return load_config_file(path)


def config_diff(candidate: RunConfig, promoted: RunConfig) -> dict[str, Any]:
    """Fields where the candidate differs from the promoted config, grouped by
    dimension, plus which dimensions moved."""
    a, b = promoted.as_dict(), candidate.as_dict()
    changed = {k: {"promoted": a[k], "candidate": b[k]} for k in a if a[k] != b[k] and k not in RUN_SETTINGS}
    dimensions = sorted({dim for dim, keys in DIMENSIONS.items() if any(k in changed for k in keys)})
    return {
        "promoted_config_hash": promoted.config_hash,
        "changed": changed,
        "dimensions": dimensions,
        "one_dimension": len(dimensions) <= 1,
    }


def check_split_policy(config: RunConfig, *, allow_leaky_split: bool) -> dict[str, Any]:
    """P2-04, enforced. Returns `{"leakage_affected": bool, "note": str | None}` or raises.

    - Axis 3 (retrieval method: dense / BM25 / hybrid / alpha) decides on `dev` only:
      synthetic questions were generated from their gold article, so `dev_large`
      flatters lexical matching and any alpha tuned there is tuned to an artefact.
    - Judged-metric decisions (Tier 2) are on the `dev` subsample only.
    Both are refused on `dev_large` unless `--allow-leaky-split`, and a run allowed
    through is marked `leakage_affected` in the results store.
    """
    if config.split != "dev_large":
        return {"leakage_affected": False, "note": None}
    reasons = []
    if config.axis == "retrieval_method":
        reasons.append(
            "Axis 3 (retrieval method) is decided on `dev` ONLY (P2-04): dev_large's synthetic "
            "questions inflate lexical overlap and would tune the hybrid weight to an artefact"
        )
    if config.eval_tier is EvalTier.TIER_2:
        reasons.append("judged-metric decisions are made on the `dev` subsample only (P2-04)")
    if not reasons:
        return {"leakage_affected": False, "note": None}
    note = "; ".join(reasons)
    if not allow_leaky_split:
        raise PermissionError(
            f"refusing to run on dev_large: {note}. Pass --allow-leaky-split to run anyway; the "
            "run will be annotated leakage-affected and cannot decide the axis."
        )
    return {"leakage_affected": True, "note": f"LEAKAGE-AFFECTED (--allow-leaky-split): {note}"}


def decision_splits(axis: str) -> dict[str, str]:
    """Which split decides an axis, and which one is the sanity check (DEC-055).

    `dev` decides every axis: it is the only split with multi-document questions
    (`dev_large` has none, MIS-021) and the only one with user-written phrasings
    (`dev_large` flattered bge-m3 by +0.005 while `dev` lost 0.160, EXP-0010). For
    retrieval axes `dev_large` is still run and must agree in direction on its
    single-document questions; it cannot promote on its own.
    """
    if axis in RETRIEVAL_AXES:
        return {"decide": "dev", "check": "dev_large"}
    if axis in DEV_ONLY_AXES or axis == "combination":
        return {"decide": "dev"}
    raise ValueError(f"axis {axis!r} has no promotion rule")


def _same_experiment(meta: dict[str, Any], config: RunConfig) -> bool:
    """Whether a run row is a run of `config`, by tier identity (see
    `RunConfig.identity_hash`); the split is the row's own."""
    from rag.runner.config import config_from_json

    try:
        stored = config_from_json(meta["config_json"])
    except (TypeError, ValueError, KeyError):
        return False
    return stored.identity_hash == config.with_(split=stored.split).identity_hash


def resolve_run_ref(ref: str, *, store: Any, like_run: str | None = None) -> str:
    """`promoted` → the newest VALID run of `configs/promoted.yaml`'s configuration,
    on the same split as `like_run` when given. Any other ref is a run id."""
    if ref != "promoted":
        return ref
    promoted = load_promoted()
    split = store.get_run(like_run)["split"] if like_run and store.get_run(like_run) else None
    row = store.latest_run_of(promoted, split=split)
    if row is None:
        raise KeyError(
            f"no VALID run of the promoted config ({promoted.config_hash})"
            + (f" on split {split!r}" if split else "") + " in the results store"
        )
    return row["run_id"]


def promote(
    candidate_path: str | Path,
    *,
    axis: str,
    dev: tuple[str, str],
    dev_large: tuple[str, str] | None,
    metric: str,
    reason: str,
    store: Any,
    git_sha: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Advance `promoted.yaml` to `candidate_path` if the comparison passes the policy.

    `dev` and `dev_large` are (baseline_run, candidate_run) pairs. **`dev` decides**
    (DEC-055): a retrieval metric must be significant by the paired test (p < 0.05,
    DEC-047), a judged or generated metric by its MDD label (DEC-048). For retrieval
    axes the `dev_large` pair is required as a check and must agree in direction; it
    never promotes on its own. Other axes take the `dev` pair alone.
    """
    from rag.eval.noise_floor import RETRIEVAL_METRICS, family_for_run, mdd_verdict
    from rag.runner.compare import compare_runs

    candidate = load_config_file(candidate_path)
    promoted = load_promoted()
    splits = decision_splits(axis)
    pairs = {"decide": dev}
    if "check" in splits:
        if dev_large is None:
            raise ValueError(f"axis {axis!r} is decided on dev and checked on dev_large: pass --dev-large")
        pairs["check"] = dev_large
    elif dev_large is not None:
        raise ValueError(f"axis {axis!r} is decided on dev only; --dev-large does not apply")

    verdicts: dict[str, Any] = {}
    problems: list[str] = []
    for role, (run_a, run_b) in pairs.items():
        meta_a, meta_b = store.get_run(run_a), store.get_run(run_b)
        for run_id, meta in ((run_a, meta_a), (run_b, meta_b)):
            if meta is None:
                raise KeyError(f"no run {run_id!r}")
        expected_split = splits[role]
        for run_id, meta in ((run_a, meta_a), (run_b, meta_b)):
            if meta["split"] != expected_split:
                problems.append(f"{role}: {run_id} is on {meta['split']!r}, policy says {expected_split!r}")
            if meta.get("leakage_affected"):
                problems.append(f"{role}: {run_id} is leakage-affected and cannot decide an axis")
        if not _same_experiment(meta_a, promoted):
            problems.append(f"{role}: baseline {run_a} is not a run of the current promoted config ({promoted.config_hash})")
        if not _same_experiment(meta_b, candidate):
            problems.append(f"{role}: candidate {run_b} is not a run of {candidate_path} ({candidate.config_hash})")

        report = compare_runs(run_a, run_b, metric=metric, store=store)
        if not report["comparable"]:
            problems.append(f"{role}: {report['comparability']['verdict']}")
        problems += [f"{role}: {w}" for w in report["warnings"]]
        overall = report["overall"]
        if metric in RETRIEVAL_METRICS:
            # Deterministic metric: the paired test is the verdict (DEC-047). The
            # deciding split must be significant; the check split only has to agree
            # in direction, which is tested below.
            verdicts[role] = {"rule": "paired test", "delta": overall["delta"], "ci95": overall["ci95"],
                              "p_value": overall["p_value"]}
            passed = overall["delta"] > 0 and (role == "check" or overall["p_value"] < 0.05)
        else:
            # Judged or generated metric: the MDD label is the verdict (DEC-048).
            family, _ = family_for_run(meta_b)
            agg_a = json.loads(meta_a.get("metrics_json") or "{}").get(metric)
            agg_b = json.loads(meta_b.get("metrics_json") or "{}").get(metric)
            if agg_a is None or agg_b is None:
                problems.append(f"{role}: {metric} is not an aggregate metric on both runs")
                agg_a, agg_b = 0.0, 0.0
            info = mdd_verdict(metric, agg_b - agg_a, family=family)
            verdicts[role] = {"rule": "MDD", "delta": info["delta"], "label": info["label"], "mdd": info["mdd"],
                              "replicates_advised": info["replicates_advised"], "p_value": overall["p_value"]}
            passed = info["delta"] > 0 and (role == "check" or info["label"] == "significant")
        verdicts[role]["passed"] = passed
        verdicts[role]["runs"] = [run_a, run_b]
        verdicts[role]["split"] = expected_split

    if "check" in verdicts:
        if (verdicts["decide"]["delta"] > 0) != (verdicts["check"]["delta"] > 0):
            problems.append(
                "dev and dev_large DISAGREE in direction "
                f"({verdicts['decide']['delta']:+.4f} vs {verdicts['check']['delta']:+.4f}); "
                "that is a finding — write it up (P2-04 / DEC-055), do not promote"
            )
    failed = [role for role, v in verdicts.items() if not v["passed"]]
    if failed:
        problems += [f"{role}: {verdicts[role]}" for role in failed]

    result = {
        "axis": axis,
        "metric": metric,
        "from": promoted.config_hash,
        "to": candidate.config_hash,
        "verdicts": verdicts,
        "problems": problems,
        "promoted": False,
    }
    if problems or dry_run:
        return result

    # Advance the pointer: the candidate file's content, with a header saying so.
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body = Path(candidate_path).read_text()
    header = (
        f"# PROMOTED on {date} from {Path(candidate_path).name} (axis {axis}, {metric};\n"
        f"# {promoted.config_hash} -> {candidate.config_hash}; git {git_sha[:7]}). See the\n"
        "# promotion log in docs/DECISIONS.md. Do not edit by hand: `rag promote` moves this file.\n"
    )
    PROMOTED_PATH.write_text(header + body)
    count = count_rows(PROMOTION_LOG_HEADING) + 1
    verdict_text = "; ".join(
        f"{role} ({v['split']}): {v['runs'][0]} → {v['runs'][1]}, Δ{v['delta']:+.4f}, "
        + (f"p={v['p_value']:.4f}" if v["rule"] == "paired test" else f"MDD ±{v['mdd']} → {v['label']}")
        for role, v in verdicts.items()
    )
    row = (
        f"| {count} | {date} | {axis} | `{promoted.config_hash}` → `{candidate.config_hash}` "
        f"({Path(candidate_path).name}) | {metric} | {verdict_text} | {reason.replace('|', '/')} (git `{git_sha[:7]}`) |"
    )
    append_row(PROMOTION_LOG_HEADING, row, placeholder=PROMOTION_EMPTY_ROW)
    result["promoted"] = True
    result["log_row"] = count
    return result
