"""Opt-in cache for query embeddings and generated answers — P3-08 / P3-10.

The CI gate must be cheap and deterministic when nothing changed: "an unchanged pipeline
means all cache hits and a near-zero-cost run" (P3-10). Experiments must NOT be: P1-11 and
P3-07 measure noise from fresh calls, and a replayed answer would hide it. So this cache
is off unless a caller switches it on with `call_cache(...)` — only `rag ci-eval` does —
and every run row records its hit and miss counts (DEC-084).

Keys cover everything that shapes the output:
- query embedding: model, pinned provider/revision, prefix convention, `dimensions`, and
  the exact prefixed text. Only `input_type == "query"`: passages live in the dense index.
- answer: model, prompt ref, temperature, max_tokens, reasoning_effort and the full
  rendered prompt (question + assembled context).

Lives under `results/` (gitignored); P3-10 restores it between CI runs.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from rag.paths import RESULTS_DIR

CALL_CACHE = RESULTS_DIR / "ci_call_cache.sqlite"


def _sha(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


class CallCache:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, vector TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS completions (key TEXT PRIMARY KEY, output TEXT NOT NULL, created_at TEXT NOT NULL);
    """

    def __init__(self, path: Path = CALL_CACHE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.executescript(self.SCHEMA)
        self.stats = {"embedding_hits": 0, "embedding_misses": 0, "completion_hits": 0, "completion_misses": 0}

    @staticmethod
    def embedding_key(identity: dict[str, Any], text: str) -> str:
        return _sha("embedding", identity, text)

    @staticmethod
    def completion_key(identity: dict[str, Any], prompt: str) -> str:
        return _sha("completion", identity, prompt)

    def get_embedding(self, key: str) -> list[float] | None:
        row = self.conn.execute("SELECT vector FROM embeddings WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_embedding(self, key: str, vector: list[float]) -> None:
        self.conn.execute("INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?)", (key, json.dumps(vector), _now()))
        self.conn.commit()

    def get_completion(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT output FROM completions WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_completion(self, key: str, output: dict[str, Any]) -> None:
        self.conn.execute("INSERT OR REPLACE INTO completions VALUES (?, ?, ?)", (key, json.dumps(output), _now()))
        self.conn.commit()

    def snapshot(self) -> dict[str, Any]:
        s = dict(self.stats)
        for kind in ("embedding", "completion"):
            total = s[f"{kind}_hits"] + s[f"{kind}_misses"]
            s[f"{kind}_hit_rate"] = round(s[f"{kind}_hits"] / total, 4) if total else None
        return s

    def close(self) -> None:
        self.conn.close()

    def __bool__(self) -> bool:  # an empty cache is still a cache (MIS-017)
        return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_ACTIVE: ContextVar[CallCache | None] = ContextVar("call_cache", default=None)


def active() -> CallCache | None:
    return _ACTIVE.get()


@contextmanager
def call_cache(cache: CallCache) -> Iterator[CallCache]:
    token = _ACTIVE.set(cache)
    try:
        yield cache
    finally:
        _ACTIVE.reset(token)
