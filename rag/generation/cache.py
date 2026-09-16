"""Generation cache for in-pipeline LLM calls — P2-03.

Query decomposition (Axis 4), LLM-as-reranker (Axis 5) and agentic retrieval
(Axis 8) put an LLM call *inside* retrieval. That makes retrieval outcomes
non-deterministic, which silently breaks the paired test's assumption (P2-01) that
a question's outcome is a fixed property of the config. The cache restores it: a
repeat of an identical config replays the stored completions, so the second run's
retrieval is identical to the first's — and it is free.

Keyed on `(question_id, prompt_id, prompt_version, model_id, input_hash)`. The
input hash covers the rendered prompt and the decoding settings, so a prompt edit
without a version bump still misses (and `tests/test_prompts.py` fails the suite
anyway). Lives under `results/` — gitignored, like the results store — because a
cold cache is a fact about a machine, not about an experiment; the hit rate is
recorded on the run row so that fact is visible.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rag.paths import GENERATION_CACHE

SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
    question_id    TEXT NOT NULL,
    prompt_id      TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model_id       TEXT NOT NULL,
    input_hash     TEXT NOT NULL,
    output         TEXT NOT NULL,
    tokens_in      INTEGER NOT NULL DEFAULT 0,
    tokens_out     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    PRIMARY KEY (question_id, prompt_id, prompt_version, model_id, input_hash)
);
"""


@dataclass(frozen=True)
class CacheKey:
    question_id: str
    prompt_id: str
    prompt_version: str
    model_id: str
    input_hash: str

    def as_tuple(self) -> tuple[str, str, str, str, str]:
        return (self.question_id, self.prompt_id, self.prompt_version, self.model_id, self.input_hash)


@dataclass(frozen=True)
class CachedGeneration:
    output: str
    tokens_in: int
    tokens_out: int
    created_at: str


class GenerationCache:
    def __init__(self, path: Path = GENERATION_CACHE) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def get(self, key: CacheKey) -> CachedGeneration | None:
        row = self.conn.execute(
            "SELECT output, tokens_in, tokens_out, created_at FROM generations WHERE "
            "question_id = ? AND prompt_id = ? AND prompt_version = ? AND model_id = ? AND input_hash = ?",
            key.as_tuple(),
        ).fetchone()
        return CachedGeneration(*row) if row else None

    def put(self, key: CacheKey, output: str, *, tokens_in: int = 0, tokens_out: int = 0) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO generations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*key.as_tuple(), output, tokens_in, tokens_out,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def __len__(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0])

    def __bool__(self) -> bool:
        # An empty cache is still a cache. Without this, `cache or default` would
        # silently swap a cold test cache for the shared one under results/.
        return True

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> GenerationCache:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
