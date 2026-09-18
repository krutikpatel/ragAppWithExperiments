"""Structure-aware chunking — P2-07 (d), redefined for this corpus.

The story asked for "structure-aware splitting on headings". The frozen text has no
headings: 0 of 6,221 articles carry a markdown or HTML heading (measured 2026-09-18).
What it has is a line structure — a title line, prose lines, and "To do X:" header
lines each followed by a line of steps (17,516 of 45,722 lines end in ':'). So the
structure this chunker respects is the line:

- a line ending in ':' is bound to the line after it, and the binding chains: a
  steps line that itself ends in ':' (it carries the next header) pulls in the
  next line too, and lines that open with a DEC-039 step verb stay with the
  procedure they continue — so a procedure block stays whole, header included;
- consecutive units are packed into a chunk until the next one would take it past
  `max_words`;
- a single unit longer than `max_words` (65 lines in the corpus) is cut at
  `max_words`, since it has no inner structure to respect.

No overlap: the boundaries are the text's own. `max_words` defaults to the control's
600 so chunk *size* is held constant and only *where* the cuts fall changes.
"""

from __future__ import annotations

from typing import Any

from rag.chunking.base import Chunk, Chunker, register_chunker
from rag.corpus.profile import _STEP_ONLY


def _starts_with_step(line: str) -> bool:
    return _STEP_ONLY.match(line) is not None


def line_units(text: str) -> list[str]:
    """Lines, with a procedure kept in one unit: a line ending in ':' absorbs the
    line after it, and keeps absorbing while the unit still ends in ':' (a steps
    line often carries the *next* header at its end — "Tap Save. To enable X:") or
    the next line opens with a DEC-039 step verb (steps continued over blank lines)."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    units: list[str] = []
    i = 0
    while i < len(lines):
        unit = [lines[i]]
        i += 1
        in_procedure = unit[-1].endswith(":")
        while i < len(lines) and (unit[-1].endswith(":") or (in_procedure and _starts_with_step(lines[i]))):
            unit.append(lines[i])
            i += 1
            in_procedure = True
        units.append("\n".join(unit))
    return units


@register_chunker("structure")
class StructureChunker(Chunker):
    def __init__(self, max_words: int = 600) -> None:
        if max_words <= 0:
            raise ValueError("max_words must be positive")
        self.max_words = max_words

    @property
    def params(self) -> dict[str, Any]:
        return {"max_words": self.max_words, "unit": "line; ':'-line bound to next", "overlap": 0}

    def split(self, doc_id: str, text: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        current: list[str] = []
        current_words = 0

        def flush() -> None:
            nonlocal current, current_words
            if current:
                chunks.append(self.make_chunk(doc_id, len(chunks), "\n".join(current)))
                current, current_words = [], 0

        for unit in line_units(text):
            n = len(unit.split())
            if n > self.max_words:
                # No inner structure to respect: cut the long unit at max_words.
                flush()
                tokens = unit.split()
                for start in range(0, n, self.max_words):
                    chunks.append(self.make_chunk(doc_id, len(chunks), " ".join(tokens[start : start + self.max_words])))
                continue
            if current_words + n > self.max_words:
                flush()
            current.append(unit)
            current_words += n
        flush()
        return chunks
