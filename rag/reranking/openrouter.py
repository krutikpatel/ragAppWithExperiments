"""Hosted cross-encoder reranking through OpenRouter's rerank endpoint — P2-10.

`POST /api/v1/rerank` takes a query and a list of documents and returns them
re-scored. Probed 2026-09-22: it exists and serves `cohere/rerank-v3.5`,
`cohere/rerank-4-fast` and `qwen/qwen3-reranker-8b` (Fireworks). `qwen3-reranker-4b`
and `baai/bge-reranker-v2-m3` are **not** served — 404 "No endpoints found" and 400
"does not exist" respectively, which is the probe preflight item 10 asks for rather
than an inference from a missing listing.

Two things this module refuses to take on trust:

- **Price.** `/models/<id>/endpoints` reports `prompt: "0", completion: "0"` for all
  three rerank models, and all three bill real money in the response's `usage.cost`
  (MIS-025). Cost here is always the provider-reported figure, never a table lookup.
- **The response.** The result count, the pinned provider and the returned indices
  are asserted at the point of the call (MIS-006). An index outside the request's
  range, or a short result list, is a broken call, not a bad ranking.

A cross-encoder scores each (query, document) pair independently, so splitting a
long candidate list over several calls returns scores on one comparable scale.
`batch_size` exists for that; the measured configurations send all 50 candidates in
one call (~40k tokens at 600 words each, inside every served endpoint's context).
"""

from __future__ import annotations

import os
import time
from typing import Any

from rag.reranking.base import Reranker, check_same_chunks
from rag.retrieval.base import ScoredChunk
from rag.runner.registry import register_reranker

OPENROUTER_RERANK_URL = "https://openrouter.ai/api/v1/rerank"

# Retryable by nature; anything else is raised on first occurrence with the body,
# which is where OpenRouter explains itself (MIS-010, MIS-023).
_RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


@register_reranker("openrouter")
class OpenRouterReranker(Reranker):
    """A hosted rerank model, pinned to one provider (DEC-032)."""

    name = "openrouter"

    def __init__(
        self,
        chunk_text: dict[str, str],
        *,
        generation_cache: Any = None,
        vector_source: Any = None,
        model: str = "",
        provider: str = "",
        batch_size: int = 0,
        timeout_s: float = 300.0,
        max_attempts: int = 4,
        backoff_s: float = 2.0,
        rate_limit_attempts: int = 8,
        rate_limit_backoff_s: float = 15.0,
        rate_limit_max_wait_s: float = 300.0,
    ) -> None:
        super().__init__(chunk_text, generation_cache=generation_cache, vector_source=vector_source)
        if not model:
            raise ValueError(
                "no rerank model configured. Model choice is Krutik's — see CLAUDE.md "
                "section 10 and DEC-058."
            )
        if not provider:
            raise ValueError(
                f"hosted rerank model {model!r} needs a `provider` pin. One model is served "
                "by many providers whose outputs and prices differ; an unpinned reranker is "
                "not reproducible and not costable (DEC-032, MIS-008)."
            )
        self.model = model
        self.provider = provider
        self.batch_size = batch_size
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.rate_limit_attempts = rate_limit_attempts
        self.rate_limit_backoff_s = rate_limit_backoff_s
        self.rate_limit_max_wait_s = rate_limit_max_wait_s

    @property
    def reranker_id(self) -> str:
        return f"{self.model}@{self.provider}"

    def rerank(
        self, query: str, chunks: list[ScoredChunk], *, question_id: str = ""
    ) -> list[ScoredChunk]:
        if not chunks:
            return []
        size = self.batch_size or len(chunks)
        scored: list[ScoredChunk] = []
        for start in range(0, len(chunks), size):
            batch = chunks[start : start + size]
            scores = self._score_batch(query, [self.chunk_text[c.chunk_id] for c in batch])
            scored += [
                ScoredChunk(chunk_id=c.chunk_id, doc_id=c.doc_id, score=score)
                for c, score in zip(batch, scores)
            ]
        self.usage.candidates += len(chunks)
        # Ties break on chunk_id, as everywhere else in this repo (MIS-003).
        scored.sort(key=lambda c: (-c.score, c.chunk_id))
        check_same_chunks(chunks, scored)
        return scored

    def _score_batch(self, query: str, documents: list[str]) -> list[float]:
        """One relevance score per document, in the order the documents were sent."""
        import httpx

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set. It lives in .env at the repo root.")
        body = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
            "return_documents": False,
            "provider": {"order": [self.provider], "allow_fallbacks": False},
        }
        last_error: Exception | None = None
        rate_limited = 0
        attempt = 0
        while attempt < self.max_attempts + rate_limited:
            attempt += 1
            started = time.perf_counter()
            try:
                response = httpx.post(
                    OPENROUTER_RERANK_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=body,
                    timeout=self.timeout_s,
                )
                response.raise_for_status()
                self.usage.latency_ms_total += int((time.perf_counter() - started) * 1000)
                return self._parse(response.json(), len(documents))
            except httpx.TransportError as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in _RETRY_STATUS:
                    raise RuntimeError(
                        f"{self.model} via {self.provider}: HTTP {exc.response.status_code} on "
                        f"{len(documents)} documents: {exc.response.text[:500]}"
                    ) from exc
                last_error = exc
                if exc.response.status_code == 429 and rate_limited < self.rate_limit_attempts:
                    # A rate limit outlasts an ordinary backoff schedule (MIS-024).
                    rate_limited += 1
                    self.usage.retries += 1
                    self.usage.rate_limited += 1
                    time.sleep(self._rate_limit_wait(exc.response.headers.get("Retry-After"), rate_limited))
                    continue
            self.usage.retries += 1
            if attempt < self.max_attempts + rate_limited:
                time.sleep(self.backoff_s * (2 ** (min(attempt, 6) - 1)))
        raise RuntimeError(
            f"{self.model}: {attempt} rerank attempts failed ({rate_limited} rate-limited); "
            f"last error {type(last_error).__name__}: {last_error}"
        ) from last_error

    def _rate_limit_wait(self, retry_after: str | None, nth: int) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.rate_limit_max_wait_s)
            except ValueError:
                pass  # an HTTP-date; fall through to the schedule
        return min(self.rate_limit_backoff_s * (2 ** (nth - 1)), self.rate_limit_max_wait_s)

    def _parse(self, payload: dict[str, Any], expected: int) -> list[float]:
        results = payload.get("results")
        if results is None:
            raise RuntimeError(f"rerank response has no `results`: {str(payload)[:300]}")
        if len(results) != expected:
            raise RuntimeError(
                f"rerank returned {len(results)} scores for {expected} documents; a short "
                "result list is a broken call, not a ranking (MIS-006)"
            )
        served_by = payload.get("provider")
        if served_by and served_by != self.provider:
            raise RuntimeError(f"reranked by {served_by!r}, not the pinned {self.provider!r}")
        scores = [0.0] * expected
        seen = set()
        for item in results:
            index = int(item["index"])
            if not 0 <= index < expected or index in seen:
                raise RuntimeError(f"rerank returned index {index} for {expected} documents")
            seen.add(index)
            scores[index] = float(item["relevance_score"])
        usage = payload.get("usage", {}) or {}
        self.usage.calls += 1
        self.usage.search_units += int(usage.get("search_units", 0))
        self.usage.tokens += int(usage.get("total_tokens", 0))
        # Provider-reported, because the price table lies about rerank models (MIS-025).
        self.usage.cost_usd += float(usage.get("cost", 0.0))
        if served_by and served_by not in self.usage.providers_seen:
            self.usage.providers_seen.append(served_by)
        return scores

    def provenance(self) -> dict[str, Any]:
        meta = super().provenance()
        meta.update({
            "model": self.model,
            "provider": self.provider,
            "reranker_id": self.reranker_id,
            "batch_size": self.batch_size or None,
            "endpoint": OPENROUTER_RERANK_URL,
        })
        return meta

    @classmethod
    def estimate_params(cls, reranker_params: dict[str, Any]) -> dict[str, Any] | None:
        return {
            "kind": "rerank_endpoint",
            "model": reranker_params.get("model", ""),
            "provider": reranker_params.get("provider", ""),
        }
