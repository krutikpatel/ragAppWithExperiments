"""Citation rendering — P1-06. The traceable source paragraph.

Citations travel through the pipeline as `[doc:<id>]` and nothing else. At render
time each cited id is resolved against the doc store for its title and URL, and
against the retrieved context for the **exact chunk the generator was shown**.
The generator never writes a link (P1-05); every URL a reader sees comes from the
frozen corpus's `url` field.

A cited id that was not in the context is rendered too, flagged — it is a
hallucinated citation, and hiding it would hide the failure.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag.corpus.loader import FrozenCorpus
from rag.retrieval.base import ScoredChunk


@dataclass(frozen=True)
class RenderedCitation:
    doc_id: str
    title: str | None
    url: str | None
    chunk_id: str | None
    chunk_text: str | None
    in_context: bool  # False: the generator cited an id it was not given
    cited: bool  # False: retrieved and shown, but not cited


def render_citations(
    cited_doc_ids: list[str],
    context_chunks: list[ScoredChunk],
    chunk_text: dict[str, str],
    corpus: FrozenCorpus,
) -> list[RenderedCitation]:
    """Cited documents first, in citation order; then retrieved-but-uncited ones."""
    lookup = corpus.frame.set_index("id")
    by_doc = {c.doc_id: c for c in context_chunks}

    def _one(doc_id: str, cited: bool) -> RenderedCitation:
        chunk = by_doc.get(doc_id)
        known = doc_id in lookup.index
        return RenderedCitation(
            doc_id=doc_id,
            title=str(lookup.loc[doc_id, "title"]) if known else None,
            url=str(lookup.loc[doc_id, "url"]) if known else None,
            chunk_id=chunk.chunk_id if chunk else None,
            chunk_text=chunk_text[chunk.chunk_id] if chunk else None,
            in_context=chunk is not None,
            cited=cited,
        )

    rendered = [_one(doc_id, True) for doc_id in cited_doc_ids]
    rendered += [_one(c.doc_id, False) for c in context_chunks if c.doc_id not in set(cited_doc_ids)]
    return rendered


def format_report(
    question: str,
    answer: str,
    citations: list[RenderedCitation],
    *,
    max_chunk_chars: int | None = None,
) -> str:
    """question → answer → citation block, as `rag ask` prints it."""
    lines = ["QUESTION", question, "", "ANSWER", answer, "", "SOURCES"]
    cited = [c for c in citations if c.cited]
    uncited = [c for c in citations if not c.cited]
    if not cited:
        lines.append("(the answer cites nothing)")
    for i, c in enumerate(cited, 1):
        lines.append("")
        head = f"[{i}] {c.title or '(unknown document)'}  —  doc:{c.doc_id[:12]}"
        if not c.in_context:
            head += "  ** CITED BUT NOT RETRIEVED — the generator invented this id **"
        lines.append(head)
        lines.append(f"    {c.url or '(no url on record)'}")
        if c.chunk_text is not None:
            text = c.chunk_text
            if max_chunk_chars and len(text) > max_chunk_chars:
                text = text[:max_chunk_chars] + " …"
            lines.append("    retrieved chunk (exact text the generator was shown):")
            lines.extend("    | " + line for line in text.splitlines() or [""])
    if uncited:
        lines.append("")
        lines.append("Retrieved but not cited:")
        for c in uncited:
            lines.append(f"  - {c.title}  —  doc:{c.doc_id[:12]}  {c.url}")
    return "\n".join(lines)
