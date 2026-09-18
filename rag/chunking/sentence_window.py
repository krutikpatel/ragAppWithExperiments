"""Sentence-window chunking — P2-07 (a).

"Retrieve small, expand context." The indexed unit is one sentence, so the
retriever matches a query against the most specific text it can; the generator then
sees that sentence with `window` sentences on either side, so an answer is not
written from a fragment. `text` is the sentence, `context_text` is the window.

On this corpus an article has a median of 11 sentences and the index grows by
about the same factor over the 600/100 control (measured when the index is built and
recorded on the run row). The document-level walk (DEC-040) already takes one chunk
per article into the context, so several sentences of one article in the top of the
ranking collapse into a single window — that is the confound P2-07 asks the writeup
to address, and the collapse ratio is what measures it.
"""

from __future__ import annotations

from typing import Any

from rag.chunking.base import Chunk, Chunker, register_chunker
from rag.chunking.sentences import split_sentences


@register_chunker("sentence_window")
class SentenceWindowChunker(Chunker):
    def __init__(self, window: int = 3) -> None:
        if window < 0:
            raise ValueError("window must be >= 0")
        self.window = window

    @property
    def params(self) -> dict[str, Any]:
        return {"window": self.window, "unit": "sentence", "splitter": "sentences-v1"}

    def split(self, doc_id: str, text: str) -> list[Chunk]:
        sentences = split_sentences(text)
        chunks: list[Chunk] = []
        for i, sentence in enumerate(sentences):
            lo, hi = max(0, i - self.window), min(len(sentences), i + self.window + 1)
            chunks.append(self.make_chunk(doc_id, i, sentence, " ".join(sentences[lo:hi])))
        return chunks
