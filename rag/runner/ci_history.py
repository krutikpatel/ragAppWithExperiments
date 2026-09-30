"""`rag ci-history` — a durable, machine-written record of every `ci-eval` job on GitHub (DEC-100).

The gate's own evidence is the `ci-eval` artifact of each GitHub Actions run (`ci_eval.json`,
`status`). GitHub deletes artifacts after 90 days, and after that every CI number in the docs
would point at nothing. This command extracts one JSON line per `ci-eval` job into
`ci/history.jsonl`, which is committed. The docs cite it the way they cite `results/`: the
markdown mirrors the file and never originates a number.

Re-running is safe: jobs already recorded are kept as they are (their artifact may have
expired since), and only jobs not yet in the file are added. Needs the `gh` CLI, logged in.
No model calls, no cost.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

WORKFLOW = "ci.yml"
JOB = "ci-eval"
HEADLINE = ("mean_faithfulness", "unsupported_answer_rate", "false_answer_rate", "citation_validity",
            "refusal_rate", "judge_failures", "n_judged")


def _minutes(started: str | None, completed: str | None) -> float | None:
    if not started or not completed:
        return None
    parse = lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))  # noqa: E731
    minutes = (parse(completed) - parse(started)).total_seconds() / 60
    return round(minutes, 2) if minutes >= 0 else None  # a job cancelled before it started


def summarize(run: dict[str, Any], job: dict[str, Any], artifact_dir: Path | None) -> dict[str, Any]:
    """One history row from a workflow run, its `ci-eval` job, and the job's downloaded artifact
    (None when there is none — a cancelled run, or one that ended before writing it)."""
    row: dict[str, Any] = {
        "github_run_id": run["databaseId"], "job_id": job["id"], "event": run["event"],
        "branch": run["headBranch"], "head_sha": run.get("headSha"), "created_at": run["createdAt"],
        "title": run.get("displayTitle"), "job_conclusion": job.get("conclusion"),
        "wall_minutes": _minutes(job.get("started_at"), job.get("completed_at")),
        "gate_status": None, "verdict": None, "artifact": False,
    }
    if artifact_dir is None:
        return row
    status = artifact_dir / "status"
    if status.exists():
        row["gate_status"] = status.read_text().strip().splitlines()[0] if status.read_text().strip() else None
        row["artifact"] = True
    result_file = artifact_dir / "ci_eval.json"
    if result_file.exists():
        doc = json.loads(result_file.read_text())
        result = doc.get("result") or {}
        cache = result.get("call_cache") or {}
        judged = (result.get("metrics") or {}).get("judged") or {}
        retrieval = (result.get("metrics") or {}).get("retrieval") or {}
        row.update(
            artifact=True,
            verdict=(doc.get("verdict") or {}).get("status_with_fallbacks") or (doc.get("verdict") or {}).get("status"),
            gate_version=(result.get("gate") or {}).get("version"), mode=result.get("mode"),
            git_sha=result.get("git_sha"), store_runs=result.get("runs"),
            cost_usd=result.get("cost_usd"),
            cache_hit_rates={"embeddings": cache.get("embedding_hit_rate"), "answers": cache.get("completion_hit_rate"),
                             "judge": cache.get("judge_hit_rate")},
            strict_recall_at_5={k: (v or {}).get("strict_recall@5") for k, v in retrieval.items()},
            judged={k: judged.get(k) for k in HEADLINE},
        )
    return row


def merge(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recorded rows win: an artifact that has since expired must not erase what it said."""
    seen = {r["job_id"] for r in existing}
    rows = existing + [r for r in new if r["job_id"] not in seen]
    return sorted(rows, key=lambda r: (r["created_at"], r["job_id"]))


def read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def collect(out: Path, *, limit: int = 500) -> tuple[int, int]:
    """Fetch every `ci-eval` job not yet in `out`; return (rows added, rows total)."""
    existing = read(out)
    known_runs = {r["github_run_id"] for r in existing}
    repo = _gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
    runs = json.loads(_gh("run", "list", "--workflow", WORKFLOW, "--limit", str(limit), "--json",
                          "databaseId,event,headBranch,headSha,createdAt,displayTitle,status"))
    new = []
    for run in runs:
        if run["databaseId"] in known_runs or run.get("status") != "completed":
            continue
        jobs = json.loads(_gh("api", f"repos/{repo}/actions/runs/{run['databaseId']}/jobs"))["jobs"]
        for job in (j for j in jobs if j["name"] == JOB):
            with tempfile.TemporaryDirectory() as tmp:
                got = subprocess.run(["gh", "run", "download", str(run["databaseId"]), "-n", JOB, "-D", tmp],
                                     capture_output=True, text=True).returncode == 0
                new.append(summarize(run, job, Path(tmp) if got else None))
    rows = merge(existing, new)
    write(out, rows)
    return len(rows) - len(existing), len(rows)
