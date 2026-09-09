"""P0-09 — the fixed Tier 2 subsample."""

from __future__ import annotations

import pandas as pd

from rag.runner.subsample import build_subsample

FRAME = pd.DataFrame({"question_id": [f"q{i:03d}" for i in range(200)]})


def test_subsample_is_the_same_questions_every_time():
    """Fixed is the point: two Tier 2 runs must differ by config, not by questions."""
    a = build_subsample(FRAME, size=100, seed=7, split_hash="sha256:abc")
    b = build_subsample(FRAME, size=100, seed=7, split_hash="sha256:abc")
    assert a.question_ids == b.question_ids
    assert a.subsample_id == b.subsample_id
    assert len(a.question_ids) == 100


def test_subsample_id_changes_with_the_split():
    a = build_subsample(FRAME, size=100, seed=7, split_hash="sha256:abc")
    b = build_subsample(FRAME, size=100, seed=7, split_hash="sha256:def")
    assert a.subsample_id != b.subsample_id, "a new split must invalidate the subsample id"


def test_subsample_id_changes_with_the_seed_and_size():
    base = build_subsample(FRAME, size=100, seed=7, split_hash="sha256:abc")
    assert build_subsample(FRAME, size=100, seed=8, split_hash="sha256:abc").subsample_id != base.subsample_id
    assert build_subsample(FRAME, size=50, seed=7, split_hash="sha256:abc").subsample_id != base.subsample_id


def test_full_eval_takes_the_whole_split():
    full = build_subsample(FRAME, size=100, seed=7, split_hash="sha256:abc", full=True)
    assert full.full is True
    assert len(full.question_ids) == 200
    assert full.subsample_id.startswith("full:")


def test_size_larger_than_the_split_is_the_whole_split():
    result = build_subsample(FRAME, size=500, seed=7, split_hash="sha256:abc")
    assert result.full is True and len(result.question_ids) == 200


def test_selection_does_not_depend_on_row_order():
    shuffled = FRAME.sample(frac=1, random_state=99).reset_index(drop=True)
    assert (
        build_subsample(FRAME, size=100, seed=7, split_hash="sha256:abc").question_ids
        == build_subsample(shuffled, size=100, seed=7, split_hash="sha256:abc").question_ids
    )
