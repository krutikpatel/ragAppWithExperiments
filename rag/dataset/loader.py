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

DEV_LARGE_WARNING = (
    "LEAKAGE WARNING: wixqa_synthetic questions were LLM-generated from the article "
    "they are grounded in. Question-document lexical overlap is inflated and BM25 "
    "numbers are optimistic. Use dev_large for statistical power on retrieval-only "
    "sweeps. Never quote a dev_large number as a headline result."
)


def fields_for(name: str) -> list[str]:
    return ROW_FIELDS + EXTRA_FIELDS.get(name, [])


def hash_split(rows: list[dict[str, Any]], name: str = "") -> str:
    return hash_records(rows, sort_key="question_id", fields=fields_for(name))


def counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[str(row[field])] = out.get(str(row[field]), 0) + 1
    return dict(sorted(out.items()))


def load_split(name: str) -> pd.DataFrame:
    """Read a built split. Emits the leakage warning for dev_large."""
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
