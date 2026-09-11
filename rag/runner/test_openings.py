"""Test-split discipline — P0-12.

400 gold questions across dozens of experiments is few enough that iterating on
them produces a system tuned to the test set. The held-out split therefore opens
only with an explicit flag, and every opening is written into DECISIONS.md
automatically — date, config hash, git SHA, reason — so the count of openings is a
matter of record, not memory.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rag.paths import DOCS_DIR

DECISIONS_PATH = DOCS_DIR / "DECISIONS.md"
LOG_HEADING = "## Test-split openings log"
EMPTY_ROW = "| _(none)_ | — | — | — | The test split has never been opened. |"


def record_test_opening(*, config_hash: str, git_sha: str, reason: str, run_id: str) -> int:
    """Append one row to the openings log and return the new opening count.

    The log is a table at the end of DECISIONS.md. The placeholder row is removed on
    the first real opening; after that rows only accumulate — the file is append-only
    and the count is the point.
    """
    text = DECISIONS_PATH.read_text()
    if LOG_HEADING not in text:
        raise RuntimeError(f"{DECISIONS_PATH} has no '{LOG_HEADING}' section")

    head, log = text.split(LOG_HEADING, 1)
    lines = log.rstrip("\n").split("\n")
    existing = [line for line in lines if line.startswith("| ") and "| —" not in line and "| #" not in line and "_(none)_" not in line]
    count = len(existing) + 1
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reason = reason.replace("|", "/").strip() or "no reason given"
    row = f"| {count} | {date} | `{config_hash}` | `{git_sha[:7]}` | {reason} (run `{run_id}`) |"

    if EMPTY_ROW in lines:
        lines[lines.index(EMPTY_ROW)] = row
    else:
        lines.append(row)

    DECISIONS_PATH.write_text(head + LOG_HEADING + "\n".join(lines) + "\n")
    return count
