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


@pytest.mark.skipif(not Path("data/frozen/dev.parquet").exists(), reason="frozen splits not built")
def test_the_golden_slice_is_a_split_with_stratum_in_its_identity_and_slices():
    """P3-07/DEC-082: `load_split("golden_v1")` is the committed slice in the runner's shape."""
    from rag.dataset.loader import describe_split, fields_for, load_split
    from rag.eval.slices import build_slices

    frame = load_split("golden_v1")
    assert len(frame) == 95 and "stratum" in fields_for("golden_v1")
    assert (frame.loc[frame["stratum"] == "unanswerable", "gold_doc_ids"].apply(len) == 0).all()
    assert describe_split("golden_v1")["split_hash"] == \
        "sha256:253982866b468ee6cc12752a7342be858e507c1cec4565cb12300ceededddd55"
    members = build_slices(frame).members
    assert {k: len(v) for k, v in members.items() if k.startswith("stratum:")} == {
        "stratum:answered_without_gold": 27, "stratum:multi_doc": 20,
        "stratum:single_doc": 33, "stratum:unanswerable": 15}


@pytest.mark.skipif(not Path("data/frozen/corpus.parquet").exists(), reason="frozen corpus not built")
def test_a_run_on_the_golden_split_scores_answerable_questions_only(tmp_path):
    """The first split mixing answerable and unanswerable questions: retrieval metrics
    average over the 80 with gold; the 15 without are not applicable, never zero (MIS-002)."""
    import json

    from rag.generation.cache import GenerationCache
    from rag.runner.config import load_config_file
    from rag.runner.run import run
    from rag.runner.store import ResultsStore

    config = load_config_file("configs/smoke_toy.yaml").with_(split="golden_v1")
    with ResultsStore(tmp_path / "r.sqlite") as store, GenerationCache(tmp_path / "g.sqlite") as cache:
        row = run(config, store=store, generation_cache=cache)
        questions = store.get_questions(row["run_id"])
    assert row["n_questions"] == 95
    per_q = [json.loads(q["metrics_json"]) for q in questions.values()]
    scored = [m["strict_recall@5"] for m in per_q if m.get("strict_recall@5") is not None]
    assert len(scored) == 80
    assert json.loads(row["metrics_json"])["strict_recall@5"] == pytest.approx(sum(scored) / 80)


def test_the_golden_generation_config_matches_the_v2_control_except_split_and_judge():
    from rag.runner.config import load_config_file

    gen = load_config_file("configs/golden_generate_v2.yaml")
    ctl = load_config_file("configs/baseline_dense_tier2_v2.yaml")
    assert gen.split == "golden_v1" and gen.full_eval and gen.skip_judge and not gen.judge_model
    for field in ("retriever", "retriever_params", "chunker", "chunker_params", "retrieval_depth",
                  "candidate_pool", "top_k", "doc_pooling", "generator_model", "generator_prompt",
                  "generator_max_tokens", "generator_reasoning_effort", "context_max_tokens"):
        assert getattr(gen, field) == getattr(ctl, field), field
