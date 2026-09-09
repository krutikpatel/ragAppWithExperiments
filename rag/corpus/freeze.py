"""Freeze the WixQA knowledge-base corpus — P0-01.

The corpus is materialized once from a pinned HuggingFace revision and never read
from the network again. Every other code path goes through `rag.corpus.loader`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from rag.corpus.normalize import NORMALIZATION_VERSION, normalize_for_index
from rag.hashing import hash_records
from rag.paths import CORPUS_META, CORPUS_PARQUET, ensure_frozen_dir

HF_DATASET = "Wix/WixQA"
HF_REVISION = "d662dc42479c14e202eccd832f8c4b66a035c4cc"
CORPUS_CONFIG = "wix_kb_corpus"
KB_SNAPSHOT_DATE = "2024-12-02"

# Fields taken verbatim from the source, in the order the hash sees them.
# `html_content` is deliberately excluded: it is a second rendering of the same
# article, it more than doubles the artifact size, and nothing in the pipeline
# reads it. See docs/DECISIONS.md DEC-003.
SOURCE_FIELDS = ["id", "url", "title", "contents", "article_type"]

# Derived columns are stored but excluded from corpus_hash, so that changing the
# normalization rule bumps `normalization_version` without pretending the corpus
# itself changed.
DERIVED_FIELDS = ["indexed_text"]


def compute_corpus_hash(records: list[dict[str, Any]]) -> str:
    return hash_records(records, sort_key="id", fields=SOURCE_FIELDS)


def freeze_corpus(*, force: bool = False) -> dict[str, Any]:
    """Materialize the corpus to parquet and return its metadata."""
    if CORPUS_PARQUET.exists() and not force:
        raise FileExistsError(
            f"{CORPUS_PARQUET} already exists; pass force=True to re-materialize"
        )

    from datasets import load_dataset

    dataset = load_dataset(HF_DATASET, CORPUS_CONFIG, revision=HF_REVISION, split="train")

    records: list[dict[str, Any]] = []
    for row in dataset:
        record = {field: row[field] for field in SOURCE_FIELDS}
        record["indexed_text"] = normalize_for_index(record["contents"])
        records.append(record)

    records.sort(key=lambda r: r["id"])
    corpus_hash = compute_corpus_hash(records)

    ensure_frozen_dir()
    frame = pd.DataFrame.from_records(records, columns=SOURCE_FIELDS + DERIVED_FIELDS)
    frame.to_parquet(CORPUS_PARQUET, index=False)

    meta = {
        "artifact": CORPUS_PARQUET.name,
        "hf_dataset": HF_DATASET,
        "hf_revision": HF_REVISION,
        "dataset_config": CORPUS_CONFIG,
        "kb_snapshot_date": KB_SNAPSHOT_DATE,
        "n_documents": len(records),
        "source_fields": SOURCE_FIELDS,
        "derived_fields": DERIVED_FIELDS,
        "corpus_hash": corpus_hash,
        "normalization_version": NORMALIZATION_VERSION,
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "license": "MIT",
        "citation": "Wix.com AI Research — WixQA (arXiv:2505.08643)",
    }
    CORPUS_META.write_text(json.dumps(meta, indent=2) + "\n")
    return meta
