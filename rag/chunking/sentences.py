"""Sentence splitting for the P2-07 chunkers.

The frozen text glues a third of its sentence boundaries: "…your account.Before you
begin:We recommend…" (34,778 of 112,219 boundaries have no space after the period,
measured 2026-09-18 over all 6,221 articles). A splitter that only breaks on
"period, space, capital" would treat those as one sentence and hand the
sentence-window and semantic chunkers a third fewer units than the text has. So a
boundary here is:

- a newline (the text's own line structure — title, prose, "To do X:" headers), or
- `.`, `?` or `!` followed by whitespace, or followed directly by an upper-case
  letter (the glued case).

A colon at the end of a line stays with its line, so "To do X:" is one sentence and
the steps under it are the following sentences. No abbreviation list: "e.g.Next"
would split wrongly, and the count of such cases was not measured — this is a
heuristic, recorded as such, and the same one is used by every chunker that needs
sentences so their units agree.
"""

from __future__ import annotations

import re

_BOUNDARY = re.compile(r"(?<=[.?!])(?:\s+|(?=[A-Z]))|\n+")


def split_sentences(text: str) -> list[str]:
    """Sentences in order, whitespace-stripped, empty ones dropped."""
    return [s.strip() for s in _BOUNDARY.split(text) if s and s.strip()]
