"""Cost-gate approvals log — P2-06.

A run estimated above the gate halts. When it is approved and re-run with
`--approve-cost`, the approval, the estimate and what drove it are appended to
DECISIONS.md automatically, so "every run above $2 was flagged and approved
before execution" is checkable from the file, not from memory.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rag.runner.decision_log import append_row, count_rows

LOG_HEADING = "## Cost approvals log"
EMPTY_ROW = "| _(none)_ | — | — | — | — | No run has been estimated above the gate yet. |"


def record_cost_approval(
    *, run_id: str, config_hash: str, estimate_usd: float, driver: str, approval: str, git_sha: str
) -> int:
    count = count_rows(LOG_HEADING) + 1
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    approval = approval.replace("|", "/").strip()
    row = (
        f"| {count} | {date} | `{config_hash}` | ${estimate_usd:.4f} ({driver}) | "
        f"{approval} | run `{run_id}`, git `{git_sha[:7]}` |"
    )
    return append_row(LOG_HEADING, row, placeholder=EMPTY_ROW)
