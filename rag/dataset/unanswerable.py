"""The unanswerable set — P0-04.

WixQA contains no questions the system should refuse, so this set is authored by
hand and lives in `data/authored/unanswerable_seed.yaml` under version control.

The set is built by *adding questions*, never by removing articles from the index.
Removing articles would change `corpus_hash` and make every run built on this set
incomparable to every other run. If you ever find yourself deleting documents to
create a refusal case, stop: that is the failure this module exists to prevent.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import yaml

from rag.dataset.wixqa import question_id
from rag.paths import REPO_ROOT

SEED_PATH: Path = REPO_ROOT / "data" / "authored" / "unanswerable_seed.yaml"

SOURCE_CONFIG = "unanswerable"
REASON_BUCKETS = ("out-of-scope-platform", "post-snapshot", "underspecified")
MIN_QUESTIONS = 40
MAX_QUESTIONS = 50


def load_seed() -> dict[str, Any]:
    return yaml.safe_load(SEED_PATH.read_text())


def verification_status() -> dict[str, Any]:
    meta = load_seed()["meta"]
    return {
        "drafted_by": meta.get("drafted_by"),
        "drafted_on": meta.get("drafted_on"),
        "verified_by": meta.get("verified_by"),
        "verified_on": meta.get("verified_on"),
        "human_verified": bool(meta.get("verified_by")),
    }


def build_unanswerable_rows() -> list[dict[str, Any]]:
    """Validate the authored set and return it as split rows."""
    seed = load_seed()
    questions = seed["questions"]

    if not MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS:
        raise ValueError(
            f"unanswerable set has {len(questions)} questions; "
            f"P0-04 requires {MIN_QUESTIONS}-{MAX_QUESTIONS}"
        )

    counts: dict[str, int] = {bucket: 0 for bucket in REASON_BUCKETS}
    seen_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in questions:
        reason = item["reason"]
        if reason not in REASON_BUCKETS:
            raise ValueError(f"{item['id']}: unknown reason bucket {reason!r}")
        if item["id"] in seen_ids:
            raise ValueError(f"duplicate id {item['id']}")
        seen_ids.add(item["id"])
        counts[reason] += 1
        rows.append(
            {
                "question_id": question_id(SOURCE_CONFIG, item["question"], []),
                "question": item["question"],
                "answer": "",
                "gold_doc_ids": [],
                "source_config": SOURCE_CONFIG,
                "n_gold_docs": 0,
                "reason": reason,
                "seed_id": item["id"],
            }
        )

    # "Roughly balanced" — no bucket may be more than twice any other.
    if max(counts.values()) > 2 * min(counts.values()):
        raise ValueError(f"reason buckets are not roughly balanced: {counts}")

    if not verification_status()["human_verified"]:
        warnings.warn(
            "unanswerable set is LLM-drafted and NOT yet human-verified "
            f"({SEED_PATH.relative_to(REPO_ROOT)}: meta.verified_by is null). "
            "Refusal and false-refusal numbers computed from it are provisional.",
            stacklevel=2,
        )
    return rows
