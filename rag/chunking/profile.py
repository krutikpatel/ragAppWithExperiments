"""Chunking characterisation for any chunker — P2-07.

`rag corpus profile` (DEC-039) counts procedure blocks cut by *fixed* chunk spans,
because it works from token offsets. The chunkers in this axis do not have spans
(a semantic chunk is whatever the boundaries made it), so the same question —
"does one chunk hold the whole procedure, header included?" — is asked on text
instead: a block is cut when no chunk of its document contains the block's tokens
as a contiguous run. Tokens are whitespace tokens, so the check is insensitive to
how the chunker rejoined them. `FixedTokenChunker` at the control setting gives the
same count either way, which a test pins.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, median
from typing import Any

from rag.chunking.base import Chunk
from rag.corpus.profile import find_procedure_blocks, token_offsets


def _contains(haystack: list[str], needle: list[str]) -> bool:
    n = len(needle)
    if n == 0:
        return True
    first = needle[0]
    for i, tok in enumerate(haystack):
        if tok == first and haystack[i : i + n] == needle:
            return True
    return False


def profile_chunks(chunks: list[Chunk], docs: dict[str, str]) -> dict[str, Any]:
    """Counts over the indexed text: chunks, words per chunk, articles in one
    chunk, and DEC-039 procedure blocks that no single chunk contains."""
    by_doc: dict[str, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_doc[c.doc_id].append(c)
    words = [len(c.text.split()) for c in chunks]
    context_words = [len(c.context.split()) for c in chunks]
    one_chunk = sum(1 for d in docs if len(by_doc.get(d, [])) == 1)

    # Cut on the indexed text (what is scored) and on the context (what the
    # generator reads). They differ only for the "retrieve small, expand" chunkers,
    # where the indexed unit is a sentence and the context is the window round it.
    blocks_total = blocks_cut = docs_with_cut = context_cut = 0
    expands = any(c.context_text is not None for c in chunks)
    for doc_id, text in docs.items():
        blocks = find_procedure_blocks(text)
        if not blocks:
            continue
        offsets = token_offsets(text)
        tokens = [text[s:e] for s, e in offsets]
        doc_chunks = by_doc.get(doc_id, [])
        chunk_tokens = [c.text.split() for c in doc_chunks]
        context_tokens = [c.context.split() for c in doc_chunks] if expands else chunk_tokens
        cut_here = 0
        for b in blocks:
            needle = tokens[b.start_token : b.end_token]
            if not any(_contains(ct, needle) for ct in chunk_tokens):
                cut_here += 1
                if not any(_contains(ct, needle) for ct in context_tokens):
                    context_cut += 1
        blocks_total += len(blocks)
        blocks_cut += cut_here
        docs_with_cut += bool(cut_here)

    return {
        "n_chunks": len(chunks),
        "n_documents": len(docs),
        "chunks_per_doc_mean": round(len(chunks) / len(docs), 3) if docs else None,
        "words_per_chunk_mean": round(mean(words), 1) if words else None,
        "words_per_chunk_median": median(words) if words else None,
        "words_per_chunk_max": max(words) if words else None,
        "context_words_per_chunk_mean": round(mean(context_words), 1) if context_words else None,
        "docs_in_one_chunk": one_chunk,
        "docs_in_one_chunk_share": round(one_chunk / len(docs), 4) if docs else None,
        "procedure_blocks": blocks_total,
        "procedure_blocks_cut": blocks_cut,
        "procedure_blocks_cut_in_context": context_cut,
        "docs_with_cut_block": docs_with_cut,
    }
