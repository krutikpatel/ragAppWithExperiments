"""Test-split discipline — P0-12.

400 gold questions across dozens of experiments is few enough that iterating on
them produces a system tuned to the test set. The held-out split therefore opens
only with an explicit flag, and every opening is written into DECISIONS.md
automatically — date, config hash, git SHA, reason — so the count of openings is a
matter of record, not memory.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rag.runner.decision_log import append_row, count_rows

LOG_HEADING = "## Test-split openings log"
EMPTY_ROW = "| _(none)_ | — | — | — | The test split has never been opened. |"


def record_test_opening(*, config_hash: str, git_sha: str, reason: str, run_id: str) -> int:
    """Append one row to the openings log and return the new opening count.

    The placeholder row is removed on the first real opening; after that rows only
    accumulate — the file is append-only and the count is the point.
    """
    count = count_rows(LOG_HEADING) + 1
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reason = reason.replace("|", "/").strip() or "no reason given"
    row = f"| {count} | {date} | `{config_hash}` | `{git_sha[:7]}` | {reason} (run `{run_id}`) |"
    return append_row(LOG_HEADING, row, placeholder=EMPTY_ROW)
