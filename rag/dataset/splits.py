"""Evaluation splits — P0-03.

Four artifacts, each hashed and provenance-tracked:

    test.parquet        100 ExpertWritten + 100 Simulated. Held out. See P0-12.
    dev.parquet         the remaining 100 + 100. Iterate here.
    dev_large.parquet   all 6,221 synthetic questions. Retrieval sweeps only.
    unanswerable.parquet  hand-authored refusal set. See rag.dataset.unanswerable.

Split assignment is deterministic: rows are sorted by `question_id`, grouped into
strata by `n_gold_docs`, shuffled with a recorded seed, and then dealt
alternately into test and dev. Dealing rather than slicing is what makes each
stratum split evenly *and* the totals land on exactly 100/100.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from rag.corpus.freeze import HF_DATASET, HF_REVISION
from rag.corpus.loader import load_corpus
from rag.dataset.unanswerable import build_unanswerable_rows
from rag.dataset.wixqa import load_qa_config
from rag.hashing import hash_records
from rag.paths import SPLIT_PATHS, SPLITS_META, ensure_frozen_dir

SPLIT_SEED = 1729

HELD_OUT_SOURCES = ("expertwritten", "simulated")
N_TEST_PER_SOURCE = 100

ROW_FIELDS = [
    "question_id",
    "question",
    "answer",
    "gold_doc_ids",
    "source_config",
    "n_gold_docs",
    "article_types",
]

# dev_large is generated data: each synthetic question was written *from* the
# article it is grounded in, so question and gold document share vocabulary that a
# real support ticket would not. Lexical retrievers score optimistically on it.
DEV_LARGE_WARNING = (
    "LEAKAGE WARNING: wixqa_synthetic questions were LLM-generated from the article "
    "they are grounded in. Question-document lexical overlap is inflated and BM25 "
    "numbers are optimistic. Use dev_large for statistical power on retrieval-only "
    "sweeps. Never quote a dev_large number as a headline result."
)


# The unanswerable split carries two extra authored columns; they are part of its
# hash so an edit to the seed file shows up as a new split_hash.
EXTRA_FIELDS = {"unanswerable": ["reason", "seed_id"]}


def _fields_for(name: str) -> list[str]:
    return ROW_FIELDS + EXTRA_FIELDS.get(name, [])


def _hash_split(rows: list[dict[str, Any]], name: str = "") -> str:
    return hash_records(rows, sort_key="question_id", fields=_fields_for(name))


def _deal_stratified(
    rows: list[dict[str, Any]], *, seed_key: str, n_first: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deal rows alternately into two piles, stratum by stratum.

    Strata are `n_gold_docs` values in ascending order. Within a stratum the order
    is a seeded shuffle, so the choice of which specific question is held out does
    not track anything in the data.
    """
    ordered: list[dict[str, Any]] = []
    for n_gold in sorted({r["n_gold_docs"] for r in rows}):
        stratum = sorted(
            (r for r in rows if r["n_gold_docs"] == n_gold),
            key=lambda r: r["question_id"],
        )
        random.Random(f"{SPLIT_SEED}:{seed_key}:{n_gold}").shuffle(stratum)
        ordered.extend(stratum)

    first = [r for i, r in enumerate(ordered) if i % 2 == 0]
    second = [r for i, r in enumerate(ordered) if i % 2 == 1]
    if len(first) != n_first:  # pragma: no cover - guards a silent miscount
        raise AssertionError(f"expected {n_first} held-out rows, dealt {len(first)}")
    return first, second


def _join_article_types(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Attach each question's gold article types. Returns (rows, unknown_doc_ids)."""
    corpus = load_corpus()
    lookup = dict(zip(corpus.frame["id"], corpus.frame["article_type"], strict=True))
    unknown: set[str] = set()
    for row in rows:
        types = []
        for doc_id in row["gold_doc_ids"]:
            if doc_id in lookup:
                types.append(lookup[doc_id])
            else:
                unknown.add(doc_id)
        row["article_types"] = sorted(set(types))
    return rows, sorted(unknown)


def _write(name: str, rows: list[dict[str, Any]], *, force: bool) -> dict[str, Any]:
    path = SPLIT_PATHS[name]
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass force=True to rebuild")
    rows = sorted(rows, key=lambda r: r["question_id"])
    columns = _fields_for(name)
    pd.DataFrame.from_records(rows, columns=columns).to_parquet(path, index=False)
    return {
        "artifact": path.name,
        "n_questions": len(rows),
        "split_hash": _hash_split(rows, name),
        "n_gold_docs_counts": _counts(rows, "n_gold_docs"),
        "source_config_counts": _counts(rows, "source_config"),
    }


def _counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row[field])] = counts.get(str(row[field]), 0) + 1
    return dict(sorted(counts.items()))


def build_splits(*, force: bool = False) -> dict[str, Any]:
    """Build all four splits and write `splits.meta.json`."""
    ensure_frozen_dir()
    load_corpus()  # fail fast if the corpus is not frozen yet

    test_rows: list[dict[str, Any]] = []
    dev_rows: list[dict[str, Any]] = []
    for source in HELD_OUT_SOURCES:
        rows = load_qa_config(source)
        held_out, kept = _deal_stratified(
            rows, seed_key=source, n_first=N_TEST_PER_SOURCE
        )
        test_rows.extend(held_out)
        dev_rows.extend(kept)

    dev_large_rows = load_qa_config("synthetic")
    unanswerable_rows = build_unanswerable_rows()

    all_rows = test_rows + dev_rows + dev_large_rows + unanswerable_rows
    all_rows, unknown_doc_ids = _join_article_types(all_rows)

    meta = {
        "hf_dataset": HF_DATASET,
        "hf_revision": HF_REVISION,
        "corpus_hash": load_corpus().corpus_hash,
        "split_seed": SPLIT_SEED,
        "assignment": (
            "sort by question_id; stratify by n_gold_docs; seeded shuffle per "
            "stratum; deal alternately into test/dev"
        ),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gold_doc_ids_not_in_corpus": unknown_doc_ids,
        "splits": {
            "test": _write("test", test_rows, force=force),
            "dev": _write("dev", dev_rows, force=force),
            "dev_large": _write("dev_large", dev_large_rows, force=force),
            "unanswerable": _write("unanswerable", unanswerable_rows, force=force),
        },
    }
    from rag.dataset.unanswerable import verification_status

    meta["splits"]["unanswerable"]["provenance"] = verification_status()
    meta["splits"]["unanswerable"]["construction"] = (
        "authored questions added; NO articles removed from the index (P0-04)"
    )
    meta["splits"]["test"]["status"] = "HELD OUT — opening requires --open-test (P0-12)"
    meta["splits"]["dev_large"]["warning"] = DEV_LARGE_WARNING
    SPLITS_META.write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def load_split(name: str) -> pd.DataFrame:
    """Read a built split. Emits the leakage warning for dev_large."""
    import warnings

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
        "split_hash": _hash_split(rows, name),
        "n_gold_docs_counts": _counts(rows, "n_gold_docs"),
        "source_config_counts": _counts(rows, "source_config"),
    }
    if name == "dev_large":
        described["warning"] = DEV_LARGE_WARNING
    return described
