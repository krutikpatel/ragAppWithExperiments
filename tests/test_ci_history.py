"""DEC-100 — `rag ci-history`: the durable record of the gate's GitHub runs. No network here."""

from __future__ import annotations

import json

from rag.runner.ci_history import merge, read, summarize, write

RUN = {"databaseId": 1, "event": "pull_request", "headBranch": "b", "headSha": "abc", "createdAt": "2026-09-30T01:00:00Z",
       "displayTitle": "t"}
JOB = {"id": 10, "conclusion": "success", "started_at": "2026-09-30T01:00:00Z", "completed_at": "2026-09-30T01:01:30Z"}


def test_a_gate_artifact_becomes_one_row_with_cost_cache_and_headline_metrics(tmp_path):
    (tmp_path / "status").write_text("PASS\n")
    (tmp_path / "ci_eval.json").write_text(json.dumps({
        "result": {"gate": {"version": 5}, "mode": "gate", "git_sha": "abc", "runs": {"golden": "run_x"},
                   "cost_usd": {"total": 0.0}, "call_cache": {"embedding_hit_rate": 1.0, "completion_hit_rate": 1.0,
                                                             "judge_hit_rate": 1.0},
                   "metrics": {"retrieval": {"dev": {"strict_recall@5": 0.72}},
                               "judged": {"mean_faithfulness": 0.8739, "false_answer_rate": 0.2}}},
        "verdict": {"status": "PASS"}}))
    row = summarize(RUN, JOB, tmp_path)
    assert row["wall_minutes"] == 1.5 and row["verdict"] == "PASS" and row["gate_status"] == "PASS"
    assert row["cost_usd"] == {"total": 0.0} and row["cache_hit_rates"]["answers"] == 1.0
    assert row["strict_recall_at_5"] == {"dev": 0.72} and row["judged"]["mean_faithfulness"] == 0.8739
    assert row["store_runs"] == {"golden": "run_x"} and row["gate_version"] == 5


def test_no_artifact_and_a_job_cancelled_before_it_started():
    row = summarize(RUN, {**JOB, "completed_at": "2026-09-30T00:59:59Z", "conclusion": "cancelled"}, None)
    assert row["artifact"] is False and row["wall_minutes"] is None and row["verdict"] is None


def test_a_recorded_row_survives_its_artifact_expiring(tmp_path):
    kept = {**summarize(RUN, JOB, None), "cost_usd": {"total": 0.3216}}
    expired = summarize(RUN, JOB, None)  # the same job, re-fetched after GitHub deleted the artifact
    later = summarize({**RUN, "databaseId": 2, "createdAt": "2026-10-01T00:00:00Z"}, {**JOB, "id": 11}, None)
    rows = merge([kept], [expired, later])
    assert [r["job_id"] for r in rows] == [10, 11] and rows[0]["cost_usd"] == {"total": 0.3216}
    path = tmp_path / "h.jsonl"
    write(path, rows)
    assert read(path) == rows


def test_the_committed_history_mirrors_the_docs_total():
    rows = read(__import__("pathlib").Path("ci/history.jsonl"))
    assert len({r["job_id"] for r in rows}) == len(rows)
    first36 = [r for r in rows if r["created_at"] < "2026-09-30T05:30:00Z"]
    assert len(first36) == 36
    assert round(sum((r.get("cost_usd") or {}).get("total", 0) for r in first36), 4) == 2.0256
