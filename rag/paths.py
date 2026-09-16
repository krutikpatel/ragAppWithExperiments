"""Filesystem locations. One place, so nothing hardcodes a path."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = REPO_ROOT / "data"
FROZEN_DIR = DATA_DIR / "frozen"
DOCS_DIR = REPO_ROOT / "docs"
PROMPTS_DIR = REPO_ROOT / "prompts"
CONFIGS_DIR = REPO_ROOT / "configs"
RESULTS_DIR = REPO_ROOT / "results"
# In-pipeline LLM completions, keyed by (question, prompt, model, input) — P2-03.
# Gitignored with the rest of results/; the hit rate on each run row says whether
# it was warm.
GENERATION_CACHE = RESULTS_DIR / "generation_cache.sqlite"
# Dense vector indexes, keyed by provenance tuple (P1-04). Gitignored, rebuildable.
INDEXES_DIR = REPO_ROOT / "indexes"

CORPUS_PARQUET = FROZEN_DIR / "corpus.parquet"
CORPUS_META = FROZEN_DIR / "corpus.meta.json"

TEST_PARQUET = FROZEN_DIR / "test.parquet"
DEV_PARQUET = FROZEN_DIR / "dev.parquet"
DEV_LARGE_PARQUET = FROZEN_DIR / "dev_large.parquet"
UNANSWERABLE_PARQUET = FROZEN_DIR / "unanswerable.parquet"
SPLITS_META = FROZEN_DIR / "splits.meta.json"

SPLIT_PATHS = {
    "test": TEST_PARQUET,
    "dev": DEV_PARQUET,
    "dev_large": DEV_LARGE_PARQUET,
    "unanswerable": UNANSWERABLE_PARQUET,
}


def ensure_frozen_dir() -> Path:
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    return FROZEN_DIR
