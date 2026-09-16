"""Machine-appended tables in docs/DECISIONS.md.

Three things are logged by code rather than by hand, because their *count* is the
point and memory is not a record: test-split openings (P0-12), promotions of
`configs/promoted.yaml` (P2-05) and cost-gate approvals (P2-06). Each is a table
under its own `## ` heading; a row is appended, the placeholder row is replaced on
the first real entry, and nothing is ever removed.

A section ends at the next `## ` heading. The first version of the openings logger
did not bound it and would have counted every table row in the rest of the file —
DEC-046's MDD tables included — as an opening (MIS-018).
"""

from __future__ import annotations

import re

from rag.paths import DOCS_DIR

DECISIONS_PATH = DOCS_DIR / "DECISIONS.md"
_HEADING = re.compile(r"^## ", re.MULTILINE)


def count_rows(heading: str, path=None) -> int:
    """Rows already in the table under `heading` in DECISIONS.md."""
    return len(section_rows((path or DECISIONS_PATH).read_text(), heading))


def section_rows(text: str, heading: str) -> list[str]:
    """Data rows of the table under `heading` (header and separator excluded)."""
    _, body = _split_section(text, heading)
    return [
        line for line in body.split("\n")
        if line.startswith("| ") and not line.startswith("| #") and not line.startswith("|---")
        and "_(none)_" not in line
    ]


def append_row(heading: str, row: str, *, placeholder: str, path=None) -> int:
    """Append `row` to the table under `heading`; return the new row count."""
    path = path or DECISIONS_PATH  # resolved at call time so tests can redirect it
    text = path.read_text()
    head, body, tail = _split_section_3(text, heading)
    lines = body.rstrip("\n").split("\n")
    if placeholder in lines:
        lines[lines.index(placeholder)] = row
    else:
        lines.append(row)
    new_body = "\n".join(lines) + "\n"
    path.write_text(head + new_body + tail)
    return len(section_rows(head + new_body + tail, heading))


def _split_section(text: str, heading: str) -> tuple[str, str]:
    head, body, _ = _split_section_3(text, heading)
    return head, body


def _split_section_3(text: str, heading: str) -> tuple[str, str, str]:
    if heading not in text:
        raise RuntimeError(f"{DECISIONS_PATH} has no '{heading}' section")
    start = text.index(heading)
    after = start + len(heading)
    match = _HEADING.search(text, after)
    end = match.start() if match else len(text)
    # keep the blank line(s) before the next heading with the tail so the file's
    # spacing is untouched
    body = text[start:end]
    stripped = body.rstrip("\n")
    return text[:start], stripped + "\n", body[len(stripped) + 1:] + text[end:]
