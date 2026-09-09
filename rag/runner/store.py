"""SQLite results store — P0-10.

Two tables. `runs` holds one row per experiment with the provenance needed to
reproduce it and the aggregate metrics. `run_questions` holds one row per question
per run.

The per-question table is the point. Aggregates say a technique gained four points;
per-question rows say *which* questions flipped and what was retrieved instead, and
that is the entire content of a findings document. Anything the aggregate cannot
explain is answered here.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from rag.paths import REPO_ROOT

DEFAULT_DB = REPO_ROOT / "results" / "runs.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id                TEXT PRIMARY KEY,
    timestamp             TEXT NOT NULL,
    name                  TEXT,
    config_hash           TEXT NOT NULL,
    config_json           TEXT NOT NULL,
    corpus_hash           TEXT NOT NULL,
    normalization_version TEXT NOT NULL,
    hf_revision           TEXT NOT NULL,
    dataset_config        TEXT,
    split                 TEXT NOT NULL,
    split_hash            TEXT NOT NULL,
    git_sha               TEXT NOT NULL,
    git_dirty             INTEGER NOT NULL,
    eval_tier             TEXT NOT NULL,
    doc_pooling           TEXT NOT NULL,
    chunker_id            TEXT,
    retriever             TEXT,
    top_k                 INTEGER,
    seed                  INTEGER,
    generator_model       TEXT,
    judge_model           TEXT,
    prompt_versions       TEXT,
    harness_smoke_test    INTEGER NOT NULL DEFAULT 0,
    status                TEXT NOT NULL DEFAULT 'RUNNING',
    n_questions           INTEGER,
    metrics_json          TEXT,
    slices_json           TEXT,
    notes                 TEXT
);

CREATE TABLE IF NOT EXISTS run_questions (
    run_id             TEXT NOT NULL,
    question_id        TEXT NOT NULL,
    retrieved_doc_ids  TEXT,
    retrieved_chunk_ids TEXT,
    scores             TEXT,
    gold_doc_ids       TEXT,
    metrics_json       TEXT,
    generated_answer   TEXT,
    cited_doc_ids      TEXT,
    latency_ms         INTEGER,
    tokens_in          INTEGER,
    tokens_out         INTEGER,
    cost_usd           REAL,
    PRIMARY KEY (run_id, question_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_config ON runs(config_hash);
CREATE INDEX IF NOT EXISTS idx_run_questions_run ON run_questions(run_id);
"""


class ResultsStore:
    def __init__(self, path: Path = DEFAULT_DB) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> ResultsStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def start_run(self, row: dict[str, Any]) -> None:
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        self.conn.execute(
            f"INSERT INTO runs ({columns}) VALUES ({placeholders})", list(row.values())
        )
        self.conn.commit()

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        metrics: dict[str, Any] | None = None,
        slices: dict[str, Any] | None = None,
        n_questions: int | None = None,
        notes: str | None = None,
    ) -> None:
        self.conn.execute(
            """UPDATE runs SET status = ?, metrics_json = ?, slices_json = ?,
                   n_questions = ?, notes = ? WHERE run_id = ?""",
            (
                status,
                json.dumps(metrics) if metrics is not None else None,
                json.dumps(slices) if slices is not None else None,
                n_questions,
                notes,
                run_id,
            ),
        )
        self.conn.commit()

    def add_questions(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        columns = list(rows[0])
        placeholders = ", ".join("?" for _ in columns)
        self.conn.executemany(
            f"INSERT INTO run_questions ({', '.join(columns)}) VALUES ({placeholders})",
            [[row[c] for c in columns] for row in rows],
        )
        self.conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM runs ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_questions(self, run_id: str) -> dict[str, dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM run_questions WHERE run_id = ?", (run_id,)
        ).fetchall()
        return {row["question_id"]: dict(row) for row in rows}

    def test_openings(self) -> list[dict[str, Any]]:
        """Every run recorded against the held-out split. P0-09 / P0-12."""
        rows = self.conn.execute(
            "SELECT run_id, timestamp, config_hash, git_sha, eval_tier, notes "
            "FROM runs WHERE split = 'test' ORDER BY timestamp"
        ).fetchall()
        return [dict(row) for row in rows]
