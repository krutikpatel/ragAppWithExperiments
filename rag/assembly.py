"""Context assembly — retrieved chunks into the generator's prompt.

The document id is printed in each article header because the generator is asked to
cite `[doc:<id>]`, and citation precision is scored against those ids with no LLM
call. If the id were not in the context, the citation metric could not exist.

P2-13 (Axis 6) adds two things that act *after* retrieval has ranked and the
document walk has selected, so neither can move a retrieval metric:

- **Ordering.** `rank` is the control: documents in the order retrieval returned
  them. `lost_in_middle` puts the strongest at the two ends of the prompt and the
  weakest in the middle, on the claim that a long-context model attends to its
  edges. It is a permutation of the same chunks — the set reaching the generator is
  identical, which is why the story forbids reporting retrieval deltas for it.
- **Compression.** A model trims each retrieved chunk to the sentences bearing on
  the question before the chunks are concatenated. This *can* drop a chunk entirely,
  so it changes what the generator sees; it still cannot change what was retrieved.
  Words in and words out are recorded per question so the tokens-per-query reduction
  is reported next to quality.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rag.prompts import load_prompt
from rag.retrieval.base import ScoredChunk

if TYPE_CHECKING:
    from rag.generation.pipeline_llm import PipelineLLM


# --- ordering (P2-13) ----------------------------------------------------------

CONTEXT_ORDERS = ("rank", "lost_in_middle")


def reorder_lost_in_middle(chunks: list[ScoredChunk]) -> list[ScoredChunk]:
    """Best at the front, second best at the back, working inwards.

    `[1,2,3,4,5]` becomes `[1,3,5,4,2]`: rank 1 opens the prompt, rank 2 closes it,
    and the weakest candidate lands in the middle. Liu et al. 2023 ("Lost in the
    Middle") measured that accuracy drops when the needed passage sits mid-prompt;
    whether that holds for *this* generator, prompt and context length is what the
    run measures.

    The return value is always a permutation of the input — same chunks, same
    documents, same count. A test asserts that, because it is the reason this
    technique cannot change recall.
    """
    front: list[ScoredChunk] = []
    back: list[ScoredChunk] = []
    for position, chunk in enumerate(chunks):
        (front if position % 2 == 0 else back).append(chunk)
    return front + back[::-1]


def order_chunks(chunks: list[ScoredChunk], order: str) -> list[ScoredChunk]:
    if order == "rank":
        return list(chunks)
    if order == "lost_in_middle":
        return reorder_lost_in_middle(chunks)
    raise ValueError(f"unknown context_order {order!r}; known: {CONTEXT_ORDERS}")


# --- assembly ------------------------------------------------------------------

@dataclass(frozen=True)
class AssembledContext:
    text: str
    doc_ids: list[str]
    n_chunks: int
    truncated: bool
    # What assembly did, recorded per question. `words_in` is the retrieved text as
    # the walk selected it; `words_out` is what actually reached the prompt. They
    # differ when a chunk was compressed away or the token budget truncated.
    meta: dict[str, Any] = field(default_factory=dict)


class ContextAssembler(ABC):
    name: str

    @abstractmethod
    def assemble(self, chunks: list[ScoredChunk], chunk_text: dict[str, str]) -> AssembledContext:
        ...


class ConcatAssembler(ContextAssembler):
    """Chunks in `order`, each headed by its document id, to a token budget."""

    name = "concat"

    def __init__(self, max_tokens: int = 6000, order: str = "rank") -> None:
        if order not in CONTEXT_ORDERS:
            raise ValueError(f"unknown context_order {order!r}; known: {CONTEXT_ORDERS}")
        self.max_tokens = max_tokens
        self.order = order

    def assemble(self, chunks: list[ScoredChunk], chunk_text: dict[str, str]) -> AssembledContext:
        # Ordering happens before the budget walk, so a reordered prompt keeps
        # whichever chunks fit *in the new order*. Truncating in rank order and then
        # reordering the survivors would be a different technique.
        ordered = order_chunks(chunks, self.order)
        parts: list[str] = []
        doc_ids: list[str] = []
        budget = self.max_tokens
        truncated = False

        for chunk in ordered:
            text = chunk_text[chunk.chunk_id]
            cost = len(text.split())
            if cost > budget:
                truncated = True
                break
            parts.append(f"--- ARTICLE [doc:{chunk.doc_id}] ---\n{text}")
            if chunk.doc_id not in doc_ids:
                doc_ids.append(chunk.doc_id)
            budget -= cost

        return AssembledContext(
            text="\n\n".join(parts),
            doc_ids=doc_ids,
            n_chunks=len(parts),
            truncated=truncated,
            meta={
                "order": self.order,
                "words_in": sum(len(chunk_text[c.chunk_id].split()) for c in ordered),
                "words_out": sum(len(chunk_text[c.chunk_id].split()) for c in ordered[: len(parts)]),
                "doc_order": [c.doc_id for c in ordered],
            },
        )


# --- compression (P2-13) -------------------------------------------------------

# What the model returns for a chunk with nothing relevant in it. A marker rather
# than an empty string because an empty completion is a broken call, not an answer
# (MIS-006) — the two have to stay distinguishable at the point of the call.
EMPTY_MARKER = "NOTHING_RELEVANT"

COMPRESSOR_PROMPT_ID = "compress_context"
COMPRESSOR_PROMPT_VERSION = "v1"

# Named in `config.context_compressor`. One entry today; it is a tuple rather than a
# bare string so an unknown name is refused by the config instead of being ignored.
COMPRESSORS = ("llm_extract",)


@dataclass
class CompressionResult:
    chunks: list[ScoredChunk]
    chunk_text: dict[str, str]
    stats: dict[str, Any]


class ContextCompressor:
    """Trims each retrieved chunk to the sentences bearing on the question.

    Every call goes through `PipelineLLM` (DEC-049): temperature 0, cached on
    (chunk, question, prompt, model), hit rate counted. A repeat of the same config
    therefore replays the same compressions and is free, which is what keeps a
    judged comparison against the control meaningful.

    A chunk the model empties is dropped from the context. A chunk whose "kept"
    text is not actually a subset of the original is kept **uncompressed** and
    counted: the prompt forbids rewriting, and a rewritten chunk would mean
    faithfulness was scored against text retrieval never returned. The count goes on
    the row rather than into an exception, because one disobedient chunk is a
    per-question fact, not a failure of the run (preflight 15).

    **A call that fails outright is the same kind of fact** (MIS-034). One chunk out of
    500 whose completion came back empty — a reasoning model spending its whole budget
    before emitting anything — must not VOID a 100-question run. The chunk is kept
    uncompressed, which is exactly the control's behaviour, and the failure is counted
    on the row. VOID is for failures of the *run*, and "the compressor could not
    shorten one passage" is not one.
    """

    name = "llm_extract"

    def __init__(self, llm: PipelineLLM, *, min_keep_ratio: float = 0.0) -> None:
        self.llm = llm
        self.min_keep_ratio = min_keep_ratio
        self.prompt = load_prompt(COMPRESSOR_PROMPT_ID, COMPRESSOR_PROMPT_VERSION)
        self.stats = {
            "chunks_seen": 0,
            "chunks_dropped": 0,
            "chunks_kept_verbatim_check_failed": 0,
            "chunks_call_failed": 0,
            "words_in": 0,
            "words_out": 0,
        }
        # Bounded: the first 20 distinct failures, so a systematic fault is legible on
        # the row without a 500-entry blob if every call fails.
        self.failures: list[dict[str, str]] = []

    @staticmethod
    def _is_extractive(kept: str, original: str) -> bool:
        """Every non-trivial line of `kept` appears in `original`.

        Whitespace is normalised on both sides because the model reflows lines; the
        check is on content, not on layout.
        """
        haystack = " ".join(original.split())
        for line in kept.splitlines():
            piece = " ".join(line.split())
            if len(piece.split()) < 3:
                continue
            if piece not in haystack:
                return False
        return True

    def compress(
        self, *, question_id: str, question: str, chunks: list[ScoredChunk], chunk_text: dict[str, str]
    ) -> CompressionResult:
        kept_chunks: list[ScoredChunk] = []
        kept_text: dict[str, str] = {}
        for chunk in chunks:
            original = chunk_text[chunk.chunk_id]
            self.stats["chunks_seen"] += 1
            self.stats["words_in"] += len(original.split())
            rendered = self.prompt.render(
                question=question, passage=original, empty_marker=EMPTY_MARKER
            )
            # The cache key's question_id has to separate the chunks of one question,
            # or every chunk after the first would replay the first one's compression.
            try:
                output = self.llm.complete(
                    question_id=f"{question_id}:{chunk.chunk_id}",
                    prompt_id=COMPRESSOR_PROMPT_ID,
                    prompt_version=COMPRESSOR_PROMPT_VERSION,
                    prompt_text=rendered,
                ).strip()
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                # Keep the retrieved text and say so. Counted per reason, because
                # "empty completion" and "provider refused" want different fixes.
                self.stats["chunks_call_failed"] += 1
                self.failures.append(
                    {"question_id": question_id, "chunk_id": chunk.chunk_id,
                     "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                )
                kept_chunks.append(chunk)
                kept_text[chunk.chunk_id] = original
                self.stats["words_out"] += len(original.split())
                continue

            if not output or EMPTY_MARKER in output:
                self.stats["chunks_dropped"] += 1
                continue
            text = output
            if not self._is_extractive(text, original):
                self.stats["chunks_kept_verbatim_check_failed"] += 1
                text = original
            elif len(text.split()) < self.min_keep_ratio * len(original.split()):
                # Over-trimmed past the floor the config set: keep the original
                # rather than hand the generator a fragment.
                text = original
            kept_chunks.append(chunk)
            kept_text[chunk.chunk_id] = text
            self.stats["words_out"] += len(text.split())

        return CompressionResult(
            chunks=kept_chunks,
            chunk_text=kept_text,
            stats={
                "question_id": question_id,
                "chunks_in": len(chunks),
                "chunks_out": len(kept_chunks),
            },
        )

    def provenance(self) -> dict[str, Any]:
        reduction = (
            1.0 - self.stats["words_out"] / self.stats["words_in"]
            if self.stats["words_in"]
            else None
        )
        return {
            "compressor": self.name,
            "prompt": f"{COMPRESSOR_PROMPT_ID}@{COMPRESSOR_PROMPT_VERSION}",
            "prompt_hash": self.prompt.content_hash,
            "min_keep_ratio": self.min_keep_ratio,
            "word_reduction": round(reduction, 4) if reduction is not None else None,
            # The runner reads this to mark the run `pipeline_nondeterministic` and
            # to price the compression calls (P2-03).
            "llm": self.llm.stats(),
            "call_failures": self.failures[:20],
            "call_failure_rate": (
                self.stats["chunks_call_failed"] / self.stats["chunks_seen"]
                if self.stats["chunks_seen"] else None
            ),
            **self.stats,
        }


def build_compressor(name: str, llm: PipelineLLM, **params: Any) -> ContextCompressor:
    if name not in COMPRESSORS:
        raise KeyError(f"unknown context_compressor {name!r}; known: {COMPRESSORS}")
    return ContextCompressor(llm, **params)
