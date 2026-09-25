"""Anthropic-style contextual retrieval — P2-13 (Axis 6).

The technique, from Anthropic's September 2024 post: before indexing a chunk, ask a
model to write a sentence or two situating that chunk inside its own document, and
index the **prefixed** text. A chunk that says "Click Save." becomes "This chunk is
from an article about changing a site's domain. It covers the final save step.
Click Save.", which a query about domains can now reach.

Three things about this implementation are load-bearing:

- **Only the indexed text changes.** `Chunk.text` carries the prefix, `context_text`
  carries the original chunk, so the generator sees exactly what the control's
  generator sees and only retrieval moves. Without that split this would be two
  changes at once and the run would not be a one-dimension diff (P2-05).
- **The split itself is the control's split.** Boundaries come from
  `FixedTokenChunker` at the promoted 600/100, so the comparison isolates the prefix
  rather than confounding it with a re-chunk. Every other Axis 1 chunker moved the
  boundaries; this one deliberately does not.
- **The spend is bounded, estimated and cached.** One LLM call per chunk across the
  whole corpus is the most expensive thing in Phase 2. `llm_workload` counts the
  calls from a *free* split of the corpus so the runner can gate the spend before a
  single call is made, and every call goes through `PipelineLLM` (DEC-049) so the
  same index rebuilds from cache for nothing.

On this corpus 79% of articles are one chunk (DEC-038), so for most chunks the
prefix summarises a document the chunk already contains in full. That bounds how
much the technique can do here and is part of the finding, not a caveat to bury.
"""

from __future__ import annotations

import time
from typing import Any

from rag.chunking.base import Chunk, Chunker, FixedTokenChunker, register_chunker
from rag.generation.pipeline_llm import PipelineLLM
from rag.prompts import load_prompt

PROMPT_ID = "contextual_chunk"
PROMPT_VERSION = "v1"

# 1.27 BPE tokens per whitespace word on this corpus (DEC-029). The estimate is in
# words because everything else in the chunking layer is.
WORDS_TO_TOKENS = 1.27
# Words of prompt scaffolding around the document and the chunk, measured from the
# rendered template rather than guessed.
_PROMPT_OVERHEAD_WORDS = len(
    load_prompt(PROMPT_ID, PROMPT_VERSION).render(document="", chunk="", max_words=0).split()
)


@register_chunker("contextual")
class ContextualChunker(Chunker):
    """Fixed-width chunks whose *indexed* text is prefixed with generated context."""

    name = "contextual"
    needs_generation_cache = True

    def __init__(
        self,
        *,
        chunk_size: int = 600,
        overlap: int = 100,
        context_model: str = "",
        context_max_words: int = 60,
        max_tokens: int = 200,
        generation_cache: Any | None = None,
        llm: PipelineLLM | None = None,
    ) -> None:
        if context_max_words <= 0:
            raise ValueError("context_max_words must be positive")
        self.splitter = FixedTokenChunker(chunk_size=chunk_size, overlap=overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.context_model = context_model
        self.context_max_words = context_max_words
        self.max_tokens = max_tokens
        self.prompt = load_prompt(PROMPT_ID, PROMPT_VERSION)
        if llm is not None:
            self.llm = llm
        else:
            if generation_cache is None:
                raise ValueError(
                    "ContextualChunker needs the generation cache: one LLM call per chunk "
                    "is only affordable because it is cached (DEC-049)"
                )
            if not context_model:
                raise ValueError(
                    "contextual chunking needs context_model; model choice is Krutik's "
                    "(CLAUDE.md section 10)"
                )
            self.llm = PipelineLLM(context_model, cache=generation_cache, max_tokens=max_tokens)
        # The runner reads this to mark the run `pipeline_nondeterministic` and record
        # the cache hit rate (P2-03), the same way it does for a retriever.
        self.pipeline_llm = self.llm
        self.stats = {
            "docs": 0,
            "chunks": 0,
            "prefixes_generated": 0,
            "prefixes_empty": 0,
            "prefix_calls_failed": 0,
            "prefix_words_total": 0,
            "llm_seconds": 0.0,
        }
        self.failures: list[dict[str, str]] = []

    @property
    def params(self) -> dict[str, Any]:
        return {
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
            "split": "fixed_token (the control's boundaries)",
            "prefix": f"{PROMPT_ID}@{PROMPT_VERSION}",
            "prefix_hash": self.prompt.content_hash,
            "context_model": self.llm.model,
            "context_max_words": self.context_max_words,
        }

    # --- the pre-spend the runner gates (P2-06) ----------------------------------

    def llm_workload(self, docs: dict[str, str]) -> dict[str, Any]:
        """Calls and tokens this chunker would spend, from a free split of the corpus.

        Counted, not guessed: the split costs nothing, so the estimate is over the
        exact chunks that will be prefixed and the exact documents each call resends.
        Assumes no prompt caching, which is the upper bound — and close to the truth
        here, since a single-chunk article has nothing to cache across.
        """
        calls = 0
        words_in = 0
        chunk_words = 0
        for doc_id, text in docs.items():
            chunks = self.splitter.split(doc_id, text)
            doc_words = len(text.split())
            for chunk in chunks:
                calls += 1
                this_chunk = len(chunk.text.split())
                chunk_words += this_chunk
                words_in += doc_words + this_chunk + _PROMPT_OVERHEAD_WORDS
        return {
            "calls": calls,
            "tokens_in": int(words_in * WORDS_TO_TOKENS),
            "tokens_out": int(calls * self.context_max_words * WORDS_TO_TOKENS),
            "model": self.llm.model,
            "prompt_caching": False,
            # What the dense index will embed afterwards: the chunks plus every prefix.
            "indexed_words": chunk_words + calls * self.context_max_words,
        }

    # --- chunking -----------------------------------------------------------------

    def _prefix_for(self, doc_id: str, document: str, chunk: Chunk) -> str:
        """The prefix for one chunk, or "" when the call failed.

        A failed call returns empty rather than raising (MIS-034). One bad completion
        out of 8,218 must not abandon an index build that has already been paid for:
        the chunk falls back to indexing as the control's chunk, the failure is
        counted, and the 8,217 prefixes already bought stay in the cache. A reasoning
        model can spend its whole budget before emitting anything, and on this model
        that happens unpredictably — measured, MIS-034.
        """
        rendered = self.prompt.render(
            document=document, chunk=chunk.text, max_words=self.context_max_words
        )
        started = time.perf_counter()
        try:
            output = self.llm.complete(
                # The cache key is per chunk, and `chunk_id` already covers the
                # chunker's identity, the document and the ordinal.
                question_id=f"chunk:{chunk.chunk_id}",
                prompt_id=PROMPT_ID,
                prompt_version=PROMPT_VERSION,
                prompt_text=rendered,
            ).strip()
        except Exception as exc:  # noqa: BLE001 - counted and reported, not swallowed
            self.stats["prefix_calls_failed"] += 1
            if len(self.failures) < 20:
                self.failures.append(
                    {"chunk_id": chunk.chunk_id, "doc_id": doc_id,
                     "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                )
            output = ""
        self.stats["llm_seconds"] = round(self.stats["llm_seconds"] + time.perf_counter() - started, 2)
        return " ".join(output.split())

    def split(self, doc_id: str, text: str) -> list[Chunk]:
        base = self.splitter.split(doc_id, text)
        if not base:
            return []
        self.stats["docs"] += 1
        out: list[Chunk] = []
        for ordinal, chunk in enumerate(base):
            prefix = self._prefix_for(doc_id, text, chunk)
            if prefix:
                self.stats["prefixes_generated"] += 1
                self.stats["prefix_words_total"] += len(prefix.split())
                indexed = f"{prefix}\n\n{chunk.text}"
            else:
                # An empty prefix is recorded, not retried and not raised: the chunk
                # still indexes as the control's chunk, and the count says how often
                # the technique contributed nothing.
                self.stats["prefixes_empty"] += 1
                indexed = chunk.text
            self.stats["chunks"] += 1
            out.append(
                self.make_chunk(doc_id, ordinal, indexed, context_text=chunk.text)
            )
        return out

    def provenance(self) -> dict[str, Any]:
        generated = self.stats["prefixes_generated"]
        return {
            "prefix_prompt": f"{PROMPT_ID}@{PROMPT_VERSION}",
            "mean_prefix_words": (
                round(self.stats["prefix_words_total"] / generated, 2) if generated else None
            ),
            "llm": self.llm.stats(),
            "prefix_call_failures": self.failures,
            "prefix_call_failure_rate": (
                self.stats["prefix_calls_failed"] / self.stats["chunks"]
                if self.stats["chunks"] else None
            ),
            **self.stats,
        }
