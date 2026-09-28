"""P3-03 — the golden CI slice: seeded, stratified, exclusive, and re-derivable."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from rag.dataset.golden import golden_hash, load_golden, select_golden


def _frames():
    dev = pd.DataFrame([
        {"question_id": f"q{i:03d}", "question": f"Q{i}", "answer": f"A{i}",
         "gold_doc_ids": [f"d{i}"] + ([f"e{i}"] if i % 5 == 0 else []),
         "source_config": "expertwritten", "n_gold_docs": 2 if i % 5 == 0 else 1}
        for i in range(200)
    ])
    una = pd.DataFrame([
        {"question_id": f"u{i:02d}", "question": f"U{i}", "reason": ["a", "b", "c"][i % 3]}
        for i in range(45)
    ])
    return dev, una


def test_strata_sizes_are_exclusive_and_the_risk_group_is_taken_whole():
    dev, una = _frames()
    awg = ["q000", "q001", "q007"]
    rows = select_golden(dev, una, awg)
    counts = Counter(r["stratum"] for r in rows)
    assert counts == {"answered_without_gold": 3, "multi_doc": 20, "single_doc": 33, "unanswerable": 15}
    assert len({r["question_id"] for r in rows}) == len(rows), "a question in two strata"
    assert {r["question_id"] for r in rows if r["stratum"] == "answered_without_gold"} == set(awg)
    assert Counter(r["reason"] for r in rows if r["stratum"] == "unanswerable") == {"a": 5, "b": 5, "c": 5}
    assert all(r["n_gold_docs"] >= 2 for r in rows if r["stratum"] == "multi_doc")


def test_selection_is_seeded_and_the_seed_matters():
    dev, una = _frames()
    a, b = select_golden(dev, una, []), select_golden(dev, una, [])
    assert golden_hash(a) == golden_hash(b)
    assert golden_hash(select_golden(dev, una, [], seed=1)) != golden_hash(a)


@pytest.mark.skipif(not Path("data/frozen/dev.parquet").exists(), reason="frozen splits not built")
def test_the_committed_v1_slice_re_derives_exactly_and_touches_no_test_question():
    from rag.dataset.golden import build_golden
    from rag.dataset.loader import load_split

    committed = load_golden()
    assert committed == build_golden()
    assert golden_hash(committed) == "sha256:baa621b13c481e953b60b6ce07782bbbe4857c321b9f37db9661b8d23384639a"
    test_ids = set(load_split("test")["question_id"])
    assert not test_ids & {r["question_id"] for r in committed}
