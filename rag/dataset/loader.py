"""Reading frozen evaluation splits — the runner's only dataset dependency.

Deliberately free of any benchmark import. `rag.dataset.splits` builds the splits
and knows about WixQA; this module only reads what was built. P0-11 requires that
the runner import nothing benchmark-specific, and `tests/test_interfaces.py` checks
the import graph.
"""

from __future__ import annotations

import warnings
from typing import Any

import pandas as pd

from rag.hashing import hash_records
from rag.paths import SPLIT_PATHS

ROW_FIELDS = [
    "question_id",
    "question",
    "answer",
    "gold_doc_ids",
    "source_config",
    "n_gold_docs",
    "article_types",
]
EXTRA_FIELDS = {"unanswerable": ["reason", "seed_id"]}
# P3-03/P3-07: a golden CI slice is a split too. Its stratum is part of its identity.
GOLDEN_PREFIX = "golden_"
GOLDEN_EXTRA_FIELDS = ["stratum", "reason"]

DEV_LARGE_WARNING = (
    "LEAKAGE WARNING: wixqa_synthetic questions were LLM-generated from the article "
    "they are grounded in. Question-document lexical overlap is inflated and BM25 "
    "numbers are optimistic. Use dev_large for statistical power on retrieval-only "
    "sweeps. Never quote a dev_large number as a headline result."
)


def fields_for(name: str) -> list[str]:
    if name.startswith(GOLDEN_PREFIX):
        return ROW_FIELDS + GOLDEN_EXTRA_FIELDS
    return ROW_FIELDS + EXTRA_FIELDS.get(name, [])


def hash_split(rows: list[dict[str, Any]], name: str = "") -> str:
    return hash_records(rows, sort_key="question_id", fields=fields_for(name))


def counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[str(row[field])] = out.get(str(row[field]), 0) + 1
    return dict(sorted(out.items()))


def load_split(name: str) -> pd.DataFrame:
    """Read a built split. Emits the leakage warning for dev_large. `golden_vN` is the
    committed CI slice (P3-03), read through `rag.dataset.golden` — its only read path."""
    if name.startswith(GOLDEN_PREFIX):
        return _golden_frame(name)
    path = SPLIT_PATHS[name]
    if not path.exists():
        raise FileNotFoundError(f"split {name!r} not built. Run `rag data splits`.")
    if name == "dev_large":
        warnings.warn(DEV_LARGE_WARNING, stacklevel=2)
    return pd.read_parquet(path)


def describe_split(name: str) -> dict[str, Any]:
    frame = load_split(name)
    rows = frame.to_dict("records")
    for row in rows:
        row["gold_doc_ids"] = list(row["gold_doc_ids"])
        row["article_types"] = list(row["article_types"])
    described = {
        "split": name,
        "n_questions": len(rows),
        "split_hash": hash_split(rows, name),
        "n_gold_docs_counts": counts(rows, "n_gold_docs"),
        "source_config_counts": counts(rows, "source_config"),
    }
    if name == "dev_large":
        described["warning"] = DEV_LARGE_WARNING
    return described


def _golden_frame(name: str) -> pd.DataFrame:
    """The golden slice in the runner's split shape. Article types come from `dev` (the
    slice stores ids, not types); unanswerable questions have none."""
    from rag.dataset.golden import load_golden

    dev = load_split("dev").set_index("question_id")
    rows = []
    for g in load_golden(name):
        qid = g["question_id"]
        rows.append({
            "question_id": qid, "question": g["question"], "answer": g["reference_answer"],
            "gold_doc_ids": list(g["article_ids"]), "source_config": g["source_config"],
            "n_gold_docs": int(g["n_gold_docs"]),
            "article_types": list(dev.loc[qid, "article_types"]) if qid in dev.index else [],
            "stratum": g["stratum"], "reason": g["reason"],
        })
    return pd.DataFrame(rows)
