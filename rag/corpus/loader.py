"""The one way to read the frozen corpus — P0-01.

Nothing else in the codebase may touch HuggingFace at runtime. If this raises,
the fix is to run `rag corpus freeze`, never to fall back to a network read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import pandas as pd

from rag.paths import CORPUS_META, CORPUS_PARQUET


# eq=False keeps the default identity hash: the dataclass holds a DataFrame, which
# is unhashable, and `_type_lookup` caches on `self`.
@dataclass(frozen=True, eq=False)
class FrozenCorpus:
    """The materialized corpus plus the provenance every run must record."""

    frame: pd.DataFrame
    meta: dict[str, Any]

    @property
    def corpus_hash(self) -> str:
        return self.meta["corpus_hash"]

    @property
    def normalization_version(self) -> str:
        return self.meta["normalization_version"]

    @property
    def hf_revision(self) -> str:
        return self.meta["hf_revision"]

    def __len__(self) -> int:
        return len(self.frame)

    def article_types(self, doc_ids: list[str]) -> list[str]:
        """Article types for the given ids, in id order. Unknown ids are skipped."""
        lookup = self._type_lookup()
        return [lookup[d] for d in doc_ids if d in lookup]

    @lru_cache(maxsize=1)
    def _type_lookup(self) -> dict[str, str]:
        return dict(zip(self.frame["id"], self.frame["article_type"], strict=True))


@lru_cache(maxsize=1)
def load_corpus() -> FrozenCorpus:
    if not CORPUS_PARQUET.exists() or not CORPUS_META.exists():
        raise FileNotFoundError(
            "frozen corpus not found. Run `rag corpus freeze` first — "
            "no code path may read the corpus from HuggingFace at runtime."
        )
    frame = pd.read_parquet(CORPUS_PARQUET)
    meta = json.loads(CORPUS_META.read_text())
    return FrozenCorpus(frame=frame, meta=meta)


def verify_corpus() -> dict[str, Any]:
    """Recompute the hash of the materialized artifact and compare to metadata."""
    from rag.corpus.freeze import compute_corpus_hash

    corpus = load_corpus()
    recomputed = compute_corpus_hash(corpus.frame.to_dict("records"))
    return {
        "recorded": corpus.corpus_hash,
        "recomputed": recomputed,
        "match": recomputed == corpus.corpus_hash,
        "n_documents": len(corpus),
    }
