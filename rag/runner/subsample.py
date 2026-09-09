"""Fixed Tier 2 subsample — P0-09.

Tier 2 costs real money per question: Ragas faithfulness decomposes an answer into
claims and verifies each one, so a single question is several LLM calls per metric.
Across dozens of experiments on 200 dev questions that compounds fast.

So Tier 2 scores a fixed subsample, and *fixed* is the load-bearing word: the same
questions every run, chosen by a recorded seed, so two Tier 2 runs differ by their
configuration and not by which questions they happened to score. The subsample id is
recorded on every run and is part of the comparability check.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pandas as pd

from rag.hashing import short_id


@dataclass(frozen=True)
class Subsample:
    question_ids: list[str]
    subsample_id: str
    size: int
    seed: int
    full: bool

    @property
    def label(self) -> str:
        return "full split" if self.full else f"{self.size} of {self.size}+ questions"


def build_subsample(
    frame: pd.DataFrame, *, size: int, seed: int, split_hash: str, full: bool = False
) -> Subsample:
    """Pick the fixed Tier 2 subsample, or the whole split when `full`.

    Selection is a seeded shuffle of question ids sorted first, so it does not depend
    on row order in the parquet file. The id covers the split hash as well as the
    seed and size: changing the split must change the subsample id, or a comparison
    across split versions would look valid.
    """
    all_ids = sorted(frame["question_id"])

    if full or size >= len(all_ids):
        return Subsample(
            question_ids=all_ids,
            subsample_id=f"full:{split_hash[:16]}",
            size=len(all_ids),
            seed=seed,
            full=True,
        )

    shuffled = list(all_ids)
    random.Random(f"{seed}:{split_hash}").shuffle(shuffled)
    chosen = sorted(shuffled[:size])
    return Subsample(
        question_ids=chosen,
        subsample_id=f"sub{size}:{short_id(split_hash, str(seed), *chosen, length=12)}",
        size=size,
        seed=seed,
        full=False,
    )
