"""Chunking — the `chunk_id → doc_id` half of P0-05.

Ground truth in WixQA is document-level; retrieval is chunk-level. Every chunk a
`Chunker` emits therefore carries the document it came from, and that mapping is
persisted with the index rather than re-derived. `chunk_id` is an opaque hash on
purpose: no code should recover a `doc_id` by parsing a chunk id.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from rag.hashing import canonical_json, short_id


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    ordinal: int
    # What the retriever indexes and scores.
    text: str
    # What the generator sees when this chunk is selected (P2-07). None means the
    # same as `text` — true for every chunker before the "retrieve small, expand
    # context" family (sentence-window, parent-document), which is the whole point
    # of those techniques and so is a field, not a lookup done elsewhere.
    context_text: str | None = None

    @property
    def context(self) -> str:
        return self.text if self.context_text is None else self.context_text


class Chunker(ABC):
    """Splits a document's indexed text into chunks."""

    name: str
    # Set by chunkers that call an LLM to build the index (contextual retrieval,
    # P2-13). `build_chunker` hands those the generation cache, so the calls are
    # cached and a rebuild is free (DEC-049).
    needs_generation_cache = False

    @property
    @abstractmethod
    def params(self) -> dict[str, Any]:
        """Config-visible parameters. Part of the chunker's identity."""

    @property
    def chunker_id(self) -> str:
        """Stable identity for this chunker and its settings."""
        return f"{self.name}-{short_id(self.name, canonical_json(self.params), length=8)}"

    @abstractmethod
    def split(self, doc_id: str, text: str) -> list[Chunk]:
        """Split one document. Implementations must produce contiguous ordinals."""

    @classmethod
    def embedding_params(cls, chunker_params: dict[str, Any]) -> dict[str, Any] | None:
        """Embedder settings this chunker would spend on *before* any chunk exists
        (the semantic chunker embeds every sentence to find boundaries), or None.
        The runner estimates and gates that spend from this (P2-06, P2-07)."""
        return None

    def llm_workload(self, docs: dict[str, str]) -> dict[str, Any] | None:
        """Calls and tokens this chunker would spend on an LLM *before* any chunk
        exists, or None when it calls no model. Contextual retrieval (P2-13) makes one
        call per chunk across the corpus; the runner estimates and gates that from
        here, so the money is approved before the first call rather than after
        (P2-06). Counted from a free split of `docs`, never guessed.
        """
        return None

    def provenance(self) -> dict[str, Any]:
        """What the chunker did, recorded on the run row under `chunker_meta`."""
        return {}

    def make_chunk(
        self, doc_id: str, ordinal: int, text: str, context_text: str | None = None
    ) -> Chunk:
        return Chunk(
            chunk_id=short_id(self.chunker_id, doc_id, str(ordinal)),
            doc_id=doc_id,
            ordinal=ordinal,
            text=text,
            context_text=None if context_text is None or context_text == text else context_text,
        )

    def split_corpus(self, docs: list[tuple[str, str]]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for doc_id, text in docs:
            chunks.extend(self.split(doc_id, text))
        return chunks


# --- registry (P2-07) ----------------------------------------------------------
# The runner names a chunker in `config.chunker`; it does not import one. Same seam
# as the retriever registry: a technique is registered here, not wired into run.py.

_CHUNKERS: dict[str, type[Chunker]] = {}
_BUILTINS_LOADED = False


def register_chunker(name: str):
    def decorator(cls: type[Chunker]) -> type[Chunker]:
        if name in _CHUNKERS:
            raise ValueError(f"chunker {name!r} is already registered")
        cls.name = name
        _CHUNKERS[name] = cls
        return cls

    return decorator


def _ensure_builtins() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    _BUILTINS_LOADED = True
    import rag.chunking.contextual  # noqa: F401
    import rag.chunking.parent_document  # noqa: F401
    import rag.chunking.semantic  # noqa: F401
    import rag.chunking.sentence_window  # noqa: F401
    import rag.chunking.structure  # noqa: F401


def build_chunker(name: str, *, generation_cache: Any | None = None, **params: Any) -> Chunker:
    """Build a chunker by name. The generation cache is injected only into chunkers
    that declared they call a model, so no other chunker's signature has to know
    about it."""
    _ensure_builtins()
    if name not in _CHUNKERS:
        raise KeyError(f"unknown chunker {name!r}; registered: {sorted(_CHUNKERS)}")
    cls = _CHUNKERS[name]
    if cls.needs_generation_cache:
        return cls(generation_cache=generation_cache, **params)
    return cls(**params)


def chunker_class(name: str) -> type[Chunker]:
    _ensure_builtins()
    if name not in _CHUNKERS:
        raise KeyError(f"unknown chunker {name!r}; registered: {sorted(_CHUNKERS)}")
    return _CHUNKERS[name]


def registered_chunkers() -> list[str]:
    _ensure_builtins()
    return sorted(_CHUNKERS)


@register_chunker("fixed_token")
class FixedTokenChunker(Chunker):
    """Fixed-width chunks over whitespace tokens.

    The unit is a whitespace-delimited token, not a model tokenizer token. That is
    a deliberate Phase 0 choice: it keeps chunking independent of which embedding
    model is in play, so a model swap cannot silently reshape the index. It also
    means a chunk is longer in model tokens than its size suggests: 1.27 BPE tokens
    per word on this corpus, so `chunk_size=600` is ~760 tokens. See
    docs/DECISIONS.md DEC-005 and DEC-029.
    """

    name = "fixed_token"

    def __init__(self, chunk_size: int = 512, overlap: int = 0) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= overlap < chunk_size:
            raise ValueError("overlap must be >= 0 and < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    @property
    def params(self) -> dict[str, Any]:
        return {"chunk_size": self.chunk_size, "overlap": self.overlap}

    def split(self, doc_id: str, text: str) -> list[Chunk]:
        tokens = text.split()
        if not tokens:
            return []
        stride = self.chunk_size - self.overlap
        chunks: list[Chunk] = []
        for ordinal, start in enumerate(range(0, len(tokens), stride)):
            window = tokens[start : start + self.chunk_size]
            if not window:
                break
            chunks.append(self.make_chunk(doc_id, ordinal, " ".join(window)))
            if start + self.chunk_size >= len(tokens):
                break
        return chunks


def chunks_to_records(chunks: list[Chunk]) -> list[dict[str, Any]]:
    return [asdict(c) for c in chunks]
