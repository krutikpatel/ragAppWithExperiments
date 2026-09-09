"""`rag diff <run_a> <run_b>` — P0-10.

Aggregates say a technique gained four points. This says which questions flipped,
in both directions, with their gold documents and the ranks they actually got.
The regressions are usually the interesting half and are invisible in a mean.
"""

from __future__ import annotations

import json
from typing import Any

from rag.runner.store import ResultsStore

DEFAULT_METRIC = "strict_recall@5"


def diff_runs(
    run_a: str, run_b: str, *, metric: str = DEFAULT_METRIC, store: ResultsStore | None = None
) -> dict[str, Any]:
    """Questions whose `metric` outcome changed between two runs."""
    owns = store is None
    store = store or ResultsStore()
    try:
        return _diff(store, run_a, run_b, metric)
    finally:
        if owns:
            store.close()


def _diff(store: ResultsStore, run_a: str, run_b: str, metric: str) -> dict[str, Any]:
    meta_a, meta_b = store.get_run(run_a), store.get_run(run_b)
    for run_id, meta in ((run_a, meta_a), (run_b, meta_b)):
        if meta is None:
            raise KeyError(f"no run {run_id!r} in {store.path}")

    comparability = compare_provenance(meta_a, meta_b)

    questions_a, questions_b = store.get_questions(run_a), store.get_questions(run_b)
    shared = sorted(set(questions_a) & set(questions_b))

    gained, lost, unchanged = [], [], 0
    for question_id in shared:
        before = json.loads(questions_a[question_id]["metrics_json"]).get(metric)
        after = json.loads(questions_b[question_id]["metrics_json"]).get(metric)
        if before is None or after is None or before == after:
            unchanged += 1
            continue
        entry = {
            "question_id": question_id,
            metric: {"a": before, "b": after},
            "gold_doc_ids": json.loads(questions_a[question_id]["gold_doc_ids"]),
            "ranks_a": _gold_ranks(questions_a[question_id]),
            "ranks_b": _gold_ranks(questions_b[question_id]),
        }
        (gained if after > before else lost).append(entry)

    return {
        "run_a": run_a,
        "run_b": run_b,
        "metric": metric,
        "comparable": comparability["comparable"],
        "comparability": comparability,
        "n_shared_questions": len(shared),
        "n_gained": len(gained),
        "n_lost": len(lost),
        "n_unchanged": unchanged,
        "gained": gained,
        "lost": lost,
    }


def _gold_ranks(question_row: dict[str, Any]) -> dict[str, int | None]:
    """1-indexed rank of each gold document, or None if it was not retrieved."""
    retrieved = json.loads(question_row["retrieved_doc_ids"])
    gold = json.loads(question_row["gold_doc_ids"])
    return {
        doc_id: (retrieved.index(doc_id) + 1 if doc_id in retrieved else None) for doc_id in gold
    }


COMPARABILITY_KEYS = (
    "corpus_hash",
    "normalization_version",
    "split",
    "split_hash",
    "eval_subsample_id",
    "doc_pooling",
    "judge_model",
    "judge_temperature",
    # A Ragas upgrade can change a metric's internal prompts, which moves every
    # judged score without anything else in the config changing. MIS-004.
    "ragas_version",
    "metric_prompt_versions",
)


def compare_provenance(meta_a: dict[str, Any], meta_b: dict[str, Any]) -> dict[str, Any]:
    """Refuse to imply a comparison is valid when the inputs differ.

    This is the preflight rule from MIS-001 made mechanical: differing corpus hash,
    eval-set version, pooling rule or judge model means the delta means nothing.
    """
    differences = {
        key: {"a": meta_a.get(key), "b": meta_b.get(key)}
        for key in COMPARABILITY_KEYS
        if meta_a.get(key) != meta_b.get(key)
    }
    smoke = bool(meta_a.get("harness_smoke_test") or meta_b.get("harness_smoke_test"))
    return {
        "comparable": not differences and not smoke,
        "differences": differences,
        "involves_harness_smoke_test": smoke,
        "verdict": (
            "COMPARABLE"
            if not differences and not smoke
            else "NOT COMPARABLE — "
            + ("a harness smoke-test run is involved; " if smoke else "")
            + (f"these differ: {sorted(differences)}" if differences else "")
        ),
    }
