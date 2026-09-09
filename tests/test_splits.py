"""P0-03 / P0-04 — split curation and the authored unanswerable set."""

from __future__ import annotations

import pytest

from rag.dataset.splits import SPLIT_SEED, _deal_stratified, describe_split
from rag.dataset.unanswerable import (
    MAX_QUESTIONS,
    MIN_QUESTIONS,
    REASON_BUCKETS,
    build_unanswerable_rows,
    verification_status,
)
from rag.paths import SPLIT_PATHS


def _rows(n_by_gold: dict[int, int]) -> list[dict]:
    rows = []
    i = 0
    for n_gold, count in n_by_gold.items():
        for _ in range(count):
            rows.append({"question_id": f"q{i:04d}", "n_gold_docs": n_gold})
            i += 1
    return rows


def test_deal_is_stratified_and_exact():
    rows = _rows({1: 148, 2: 46, 3: 6})
    held_out, kept = _deal_stratified(rows, seed_key="expertwritten", n_first=100)
    assert len(held_out) == 100 and len(kept) == 100
    for n_gold in (1, 2, 3):
        a = sum(1 for r in held_out if r["n_gold_docs"] == n_gold)
        b = sum(1 for r in kept if r["n_gold_docs"] == n_gold)
        assert abs(a - b) <= 1, f"stratum {n_gold} unbalanced: {a} vs {b}"


def test_deal_is_deterministic():
    rows = _rows({1: 148, 2: 46, 3: 6})
    first, _ = _deal_stratified(rows, seed_key="expertwritten", n_first=100)
    second, _ = _deal_stratified(rows, seed_key="expertwritten", n_first=100)
    assert [r["question_id"] for r in first] == [r["question_id"] for r in second]


def test_seed_is_recorded():
    assert isinstance(SPLIT_SEED, int)


def test_unanswerable_set_shape():
    rows = build_unanswerable_rows()
    assert MIN_QUESTIONS <= len(rows) <= MAX_QUESTIONS
    assert all(r["gold_doc_ids"] == [] for r in rows)
    assert all(r["n_gold_docs"] == 0 for r in rows)
    assert {r["reason"] for r in rows} == set(REASON_BUCKETS)


def test_unanswerable_buckets_roughly_balanced():
    rows = build_unanswerable_rows()
    counts = {b: sum(1 for r in rows if r["reason"] == b) for b in REASON_BUCKETS}
    assert max(counts.values()) <= 2 * min(counts.values())


def test_unanswerable_questions_are_unique():
    rows = build_unanswerable_rows()
    assert len({r["question"] for r in rows}) == len(rows)
    assert len({r["question_id"] for r in rows}) == len(rows)


def test_unanswerable_provenance_is_recorded():
    status = verification_status()
    assert status["drafted_by"]
    assert "human_verified" in status


# --- these require `rag data splits` to have been run ------------------------

built = pytest.mark.skipif(
    not SPLIT_PATHS["dev"].exists(), reason="splits not built; run `rag data splits`"
)


@built
def test_split_sizes():
    assert describe_split("test")["n_questions"] == 200
    assert describe_split("dev")["n_questions"] == 200
    assert describe_split("dev_large")["n_questions"] == 6221


@built
def test_test_and_dev_are_disjoint():
    from rag.dataset.splits import load_split

    test_ids = set(load_split("test")["question_id"])
    dev_ids = set(load_split("dev")["question_id"])
    assert test_ids & dev_ids == set()


@built
def test_each_source_contributes_equally_to_test_and_dev():
    for split in ("test", "dev"):
        counts = describe_split(split)["source_config_counts"]
        assert counts == {"expertwritten": 100, "simulated": 100}


@built
def test_dev_large_carries_the_leakage_warning():
    assert "LEAKAGE WARNING" in describe_split("dev_large")["warning"]


@built
def test_dev_large_load_warns():
    from rag.dataset.splits import load_split

    with pytest.warns(UserWarning, match="LEAKAGE WARNING"):
        load_split("dev_large")
