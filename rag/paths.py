"""Filesystem locations. One place, so nothing hardcodes a path."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = REPO_ROOT / "data"
FROZEN_DIR = DATA_DIR / "frozen"
DOCS_DIR = REPO_ROOT / "docs"
PROMPTS_DIR = REPO_ROOT / "prompts"
CONFIGS_DIR = REPO_ROOT / "configs"

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
