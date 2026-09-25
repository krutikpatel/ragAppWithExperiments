"""Query transformation — P2-12, Axis 4.

Four techniques that all have the same shape: send the question to a model, get one
or more *new* query strings back, retrieve for each, and fuse the rankings. What
differs is what the model is asked for and whether the original question is still
retrieved for.

| transform | queries sent to the retriever | original kept? |
|---|---|---|
| `decompose` | the sub-questions the question depends on | no — the parts replace it |
| `hyde` | one hypothetical help article answering it | no — it replaces the query |
| `multi_query` | N paraphrases | yes |
| `step_back` | one more general question | yes |

`decompose` and `hyde` replace the question because that is the technique: HyDE's
whole claim is that a fake answer sits closer to the real answer than the question
does, and a decomposition that still retrieves for the un-decomposed question is not
being tested. `multi_query` and `step_back` are expansions, so the original stays.
Each transform states this in `keeps_original`, and a test asserts the table above.

Fusion is Reciprocal Rank Fusion — the same `rrf_fuse` Axis 3 used (P2-09), because
sub-query rankings have the same incomparable-scores problem two retrievers do: a
cosine against a hypothetical document and a cosine against the question are not on
one scale. Ranks are comparable; scores are not.

Three things this module is careful about:

- **Every call goes through `PipelineLLM`** (DEC-049), so the run is cache-backed and
  repeatable, and the hit rate lands on the row.
- **`prewarm` generates every question's transform in one concurrent batch** before
  the retrieval loop starts. Sequentially, 200 questions at ~5 s/call is 15+ minutes
  per run; batched at 16 workers it is under a minute, and the loop then runs entirely
  from cache. MIS-036 is why this is here from the start rather than after a 16-hour
  surprise.
- **A failed or empty transform falls back to the original question**, counted, never
  raised (MIS-034 / preflight 43). One bad completion out of 200 must not void a run,
  and retrieving for the untransformed question is exactly the control's behaviour.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rag.hashing import hash_text
from rag.prompts import load_prompt
from rag.retrieval.base import Retriever
from rag.retrieval.hybrid import DEFAULT_RRF_K, rrf_fuse

if TYPE_CHECKING:
    from rag.generation.cache import GenerationCache
    from rag.generation.pipeline_llm import PipelineLLM

QUERY_TRANSFORMS: dict[str, type[QueryTransform]] = {}


def register_transform(name: str):
    def decorator(cls: type[QueryTransform]) -> type[QueryTransform]:
        if name in QUERY_TRANSFORMS:
            raise ValueError(f"query transform {name!r} is already registered")
        cls.name = name
        QUERY_TRANSFORMS[name] = cls
        return cls

    return decorator


def build_transform(name: str, llm: PipelineLLM, **params: Any) -> QueryTransform:
    if name not in QUERY_TRANSFORMS:
        raise KeyError(f"unknown query_transform {name!r}; registered: {sorted(QUERY_TRANSFORMS)}")
    return QUERY_TRANSFORMS[name](llm, **params)


def registered_transforms() -> list[str]:
    return sorted(QUERY_TRANSFORMS)


@dataclass
class Expansion:
    """What one question became."""

    queries: list[str]
    generated: int          # how many the model produced, before the original is added
    fell_back: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


class QueryTransform(ABC):
    name: str
    prompt_id: str
    prompt_version: str = "v1"
    # Whether the original question is retrieved for alongside whatever the model
    # produced. See the table in this module's docstring.
    keeps_original: bool = True

    def __init__(self, llm: PipelineLLM, **params: Any) -> None:
        self.llm = llm
        self.prompt = load_prompt(self.prompt_id, self.prompt_version)
        self.params = params
        self.stats = {
            "questions": 0,
            "generated_total": 0,
            "fell_back": 0,
            "llm_seconds": 0.0,
        }
        self.failures: list[dict[str, str]] = []
        self._cache: dict[str, Expansion] = {}

    # --- the prompt, and what comes back ------------------------------------------

    @abstractmethod
    def render(self, question: str) -> str:
        """The prompt for this question."""

    @abstractmethod
    def parse(self, output: str, question: str) -> list[str]:
        """The query strings in the model's output. May be empty, which is a fallback."""

    @staticmethod
    def _lines(output: str) -> list[str]:
        """Non-empty lines, stripped of the bullets and numbering the prompt forbade
        but models produce anyway (MIS-016: parse what arrives, not what was asked)."""
        out = []
        for raw in output.splitlines():
            line = raw.strip().lstrip("-*•").strip()
            while line[:1].isdigit():
                head, _, tail = line.partition(".")
                if head.isdigit() and tail:
                    line = tail.strip()
                    continue
                head, _, tail = line.partition(")")
                if head.isdigit() and tail:
                    line = tail.strip()
                    continue
                break
            if line:
                out.append(line)
        return out

    # --- cache key ------------------------------------------------------------------

    @staticmethod
    def cache_id(question: str) -> str:
        """Keyed on the question text, not the question id: identical questions share
        one completion, and the key survives a change of split or subsample."""
        return f"qt:{hash_text(question)[7:30]}"

    # --- the work ---------------------------------------------------------------------

    def prewarm(self, questions: list[str], *, workers: int = 16) -> None:
        """Generate every question's transform in one concurrent batch (MIS-036).

        After this, `expand` runs entirely from the generation cache, so the retrieval
        loop is not paying a round trip per question.
        """
        from rag.generation.pipeline_llm import Request

        unique = list(dict.fromkeys(questions))
        requests = [
            Request(
                question_id=self.cache_id(q),
                prompt_id=self.prompt_id,
                prompt_version=self.prompt_version,
                prompt_text=self.render(q),
            )
            for q in unique
        ]
        started = time.perf_counter()
        outcomes = self.llm.complete_many(requests, workers=workers)
        self.stats["llm_seconds"] = round(time.perf_counter() - started, 2)
        for question, outcome in zip(unique, outcomes):
            self._cache[question] = self._expansion_from(question, outcome)

    def _expansion_from(self, question: str, outcome: str | Exception) -> Expansion:
        if isinstance(outcome, Exception):
            self.failures.append(
                {"question": question[:120], "error": f"{type(outcome).__name__}: {str(outcome)[:160]}"}
            )
            return Expansion(queries=[question], generated=0, fell_back=True)
        produced = [q for q in self.parse(outcome, question) if q.strip()]
        if not produced:
            # The model returned nothing usable. Retrieving for the untransformed
            # question is exactly the control's behaviour, so that is the fallback.
            return Expansion(queries=[question], generated=0, fell_back=True)
        queries = ([question] + produced) if self.keeps_original else list(produced)
        return Expansion(queries=queries, generated=len(produced))

    def expand(self, question: str) -> Expansion:
        expansion = self._cache.get(question)
        if expansion is None:
            outcome: str | Exception
            try:
                outcome = self.llm.complete(
                    question_id=self.cache_id(question),
                    prompt_id=self.prompt_id,
                    prompt_version=self.prompt_version,
                    prompt_text=self.render(question),
                )
            except Exception as exc:  # noqa: BLE001 - counted, not swallowed
                outcome = exc
            expansion = self._expansion_from(question, outcome)
            self._cache[question] = expansion
        self.stats["questions"] += 1
        self.stats["generated_total"] += expansion.generated
        self.stats["fell_back"] += int(expansion.fell_back)
        return expansion

    def provenance(self) -> dict[str, Any]:
        n = self.stats["questions"]
        return {
            "query_transform": self.name,
            "prompt": f"{self.prompt_id}@{self.prompt_version}",
            "prompt_hash": self.prompt.content_hash,
            "keeps_original": self.keeps_original,
            "params": self.params,
            "mean_generated_per_question": round(self.stats["generated_total"] / n, 3) if n else None,
            "fallback_rate": round(self.stats["fell_back"] / n, 4) if n else None,
            "failures": self.failures[:20],
            "llm": self.llm.stats(),
            **self.stats,
        }


# --- the four techniques ---------------------------------------------------------

@register_transform("decompose")
class Decompose(QueryTransform):
    """Split a multi-hop question into the questions it depends on (run first, P2-12)."""

    prompt_id = "query_decompose"
    keeps_original = False

    def __init__(self, llm: PipelineLLM, *, max_parts: int = 4) -> None:
        if max_parts < 1:
            raise ValueError("max_parts must be at least 1")
        super().__init__(llm, max_parts=max_parts)
        self.max_parts = max_parts

    def render(self, question: str) -> str:
        return self.prompt.render(question=question, max_parts=self.max_parts)

    def parse(self, output: str, question: str) -> list[str]:
        # The prompt states the cap; the parser enforces it, because a model that
        # ignores it would otherwise multiply the run's embedding calls silently.
        return self._lines(output)[: self.max_parts]


@register_transform("hyde")
class HyDE(QueryTransform):
    """Embed a generated answer instead of the question (Gao et al. 2022)."""

    prompt_id = "query_hyde"
    keeps_original = False

    def __init__(self, llm: PipelineLLM, *, max_words: int = 120) -> None:
        if max_words < 1:
            raise ValueError("max_words must be at least 1")
        super().__init__(llm, max_words=max_words)
        self.max_words = max_words

    def render(self, question: str) -> str:
        return self.prompt.render(question=question, max_words=self.max_words)

    def parse(self, output: str, question: str) -> list[str]:
        """The whole passage is one query. Line structure is preserved because the
        embedder sees one string either way, and truncation is on words so a model
        that ignores the cap cannot inflate the query vector's input."""
        text = " ".join(output.split())
        if not text:
            return []
        return [" ".join(text.split()[: self.max_words])]


@register_transform("multi_query")
class MultiQuery(QueryTransform):
    """Retrieve for N paraphrases alongside the original and fuse."""

    prompt_id = "query_multi"
    keeps_original = True

    def __init__(self, llm: PipelineLLM, *, n: int = 3) -> None:
        if n < 1:
            raise ValueError("n must be at least 1")
        super().__init__(llm, n=n)
        self.n = n

    def render(self, question: str) -> str:
        return self.prompt.render(question=question, n=self.n)

    def parse(self, output: str, question: str) -> list[str]:
        flat = " ".join(question.split()).lower()
        # Drop a rewrite that is just the original back again: it would double that
        # ranking's RRF weight and quietly make the fusion favour the original.
        return [q for q in self._lines(output) if " ".join(q.split()).lower() != flat][: self.n]


@register_transform("step_back")
class StepBack(QueryTransform):
    """Retrieve for one more general question alongside the original (Zheng et al. 2023)."""

    prompt_id = "query_step_back"
    keeps_original = True

    def render(self, question: str) -> str:
        return self.prompt.render(question=question)

    def parse(self, output: str, question: str) -> list[str]:
        lines = self._lines(output)
        return lines[:1]


# --- the retriever wrapper ---------------------------------------------------------

class TransformingRetriever(Retriever):
    """Wraps a retriever, expands the query, searches each, fuses by RRF.

    It is a `Retriever`, so pooling, the document walk and the collapse ratio are the
    base class's and behave exactly as they do for the control. Only `search` changes.
    """

    name = "query_transform"

    def __init__(self, base: Retriever, transform: QueryTransform, *, rrf_k: int = DEFAULT_RRF_K) -> None:
        super().__init__(
            base.chunk_to_doc,
            doc_pooling=base.doc_pooling,
            index=base.index,
            generation_cache=base.generation_cache,
        )
        self.base = base
        self.transform = transform
        self.rrf_k = int(rrf_k)
        # The runner reads this to mark the run `pipeline_nondeterministic` (P2-03).
        self.pipeline_llm = transform.llm
        self.per_question: dict[str, dict[str, Any]] = {}
        self._search_seconds = 0.0

    def search(self, query: str, *, top_k: int) -> list[tuple[str, float]]:
        started = time.perf_counter()
        expansion = self.transform.expand(query)
        rankings = [self.base.search(q, top_k=top_k) for q in expansion.queries]
        fused = rrf_fuse(rankings, k=self.rrf_k)[:top_k] if len(rankings) > 1 else rankings[0][:top_k]
        self._search_seconds += time.perf_counter() - started

        # P2-12 asks for the distinct-document yield per sub-query: how many documents
        # each query contributed that no earlier query had already found.
        seen: set[str] = set()
        yields = []
        for ranking in rankings:
            docs = {self.chunk_to_doc[cid] for cid, _ in ranking}
            yields.append(len(docs - seen))
            seen |= docs
        self.per_question[query] = {
            "n_queries": len(expansion.queries),
            "n_generated": expansion.generated,
            "fell_back": float(expansion.fell_back),
            "distinct_docs_total": len(seen),
            "distinct_doc_yield_per_query": yields,
            "mean_new_docs_after_first": (
                round(sum(yields[1:]) / len(yields[1:]), 3) if len(yields) > 1 else None
            ),
        }
        return fused

    # --- everything else delegates ------------------------------------------------

    def chunk_vectors(self, chunk_ids: list[str]) -> Any | None:
        return self.base.chunk_vectors(chunk_ids)

    def query_cost_usd(self) -> float:
        return self.base.query_cost_usd()

    @classmethod
    def embedding_params(cls, retriever_params: dict[str, Any]) -> dict[str, Any] | None:
        """Never reached: the runner costs the *base* retriever, which it builds from
        `config.retriever`. A transform adds LLM calls and extra query embeddings, both
        estimated separately (P2-06)."""
        return None

    def provenance(self) -> dict[str, Any]:
        base = dict(self.base.provenance())
        base["query_transform"] = self.transform.provenance()
        base["rrf_k"] = self.rrf_k
        base["transform_search_seconds"] = round(self._search_seconds, 2)
        return base
