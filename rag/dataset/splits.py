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
from rag.dataset.loader import (
    DEV_LARGE_WARNING,
    ROW_FIELDS,
    counts as _counts,
    fields_for as _fields_for,
    hash_split as _hash_split,
)
from rag.paths import SPLIT_PATHS, SPLITS_META, ensure_frozen_dir

SPLIT_SEED = 1729

HELD_OUT_SOURCES = ("expertwritten", "simulated")
N_TEST_PER_SOURCE = 100

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


# Reading built splits lives in `rag.dataset.loader`, which has no benchmark import,
# so the runner can depend on it without depending on WixQA (P0-11).
from rag.dataset.loader import describe_split, load_split  # noqa: E402,F401
