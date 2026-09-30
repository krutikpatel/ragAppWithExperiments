"""TypeSafe Jev as a reranker, called on TypeSafe's own API — DEC-101.

Jev is a "System One" decision model: it does not write text, it answers a typed
question about a `state` with a probability. `POST /v1/systemone` with one `noul`
(yes/no) question per (query, chunk) pair returns P(relevant), and the chunks are
sorted by it. The question's wording is a versioned prompt (`rerank_jev.yaml`).

**One call per chunk** (Krutik, DEC-101). Each chunk is judged alone, like a
cross-encoder pair, so a chunk's score cannot depend on which other chunks share its
request. Calls for one query run on `workers` threads — the HTTP only; every counter
is updated on the calling thread (the MIS-036 pattern).

Three things this module refuses to take on trust:

- **The model.** Pinned to an exact version (`jev-1.13.0`), never the `jev-latest`
  alias, and the response's `model` field is asserted against the pin when present.
- **The response.** Every answer must be a `noul` in [0, 1] under the question key
  that was sent (MIS-006). A missing answer is a broken call, not a score of zero.
- **The price, as far as that is possible.** The response reports `usage.input_tokens`
  and no cost, so unlike every OpenRouter reranker (MIS-025) cost here is reported
  tokens x the PUBLISHED rate in `configs/pricing.yaml`. The row records that basis;
  DEC-101 requires reconciling it with TypeSafe's billing page after the first run.

Jev is not on OpenRouter under this id, so `rag models verify` cannot check it
(`verified_by_model_check = False`). The version pin and the response assertion are
the check instead.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import yaml

from rag.prompts import load_prompt
from rag.reranking.base import Reranker, check_same_chunks
from rag.retrieval.base import ScoredChunk
from rag.runner.registry import register_reranker

TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
TYPESAFE_PROVIDER = "TypeSafe"
KEY_ENV = "TYPESAFE_JEV_KEY"
QUESTION_KEY = "relevant"
# 529 is TypeSafe's "overloaded" (API reference); the rest are transient by nature.
# 401/403/422 are raised on first occurrence: a retried auth error is a hidden bug (MIS-014).
_RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})


@register_reranker("typesafe_jev")
class TypeSafeJevReranker(Reranker):
    """P(relevant) from Jev's `noul` question, one call per chunk."""

    name = "typesafe_jev"
    verified_by_model_check = False

    def __init__(
        self,
        chunk_text: dict[str, str],
        *,
        generation_cache: Any = None,
        vector_source: Any = None,
        model: str = "",
        prompt_version: str = "v1",
        workers: int = 8,
        timeout_s: float = 60.0,
        max_attempts: int = 4,
        backoff_s: float = 2.0,
        rate_limit_attempts: int = 8,
        rate_limit_backoff_s: float = 5.0,
        rate_limit_max_wait_s: float = 120.0,
        usd_per_mtok: float | None = None,
    ) -> None:
        super().__init__(chunk_text, generation_cache=generation_cache, vector_source=vector_source)
        if not model:
            raise ValueError(
                "no Jev model configured. Model choice is Krutik's — see CLAUDE.md section 10 "
                "and DEC-101."
            )
        if model.endswith("latest") or model.endswith("preview"):
            raise ValueError(
                f"{model!r} is a floating alias. Pin an exact version such as jev-1.13.0: an "
                "alias can move under a run and nothing in the artifacts would show it."
            )
        self.model = model
        self.prompt = load_prompt("rerank_jev", prompt_version)
        self.question = self._question(self.prompt)
        self.workers = max(1, workers)
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.rate_limit_attempts = rate_limit_attempts
        self.rate_limit_backoff_s = rate_limit_backoff_s
        self.rate_limit_max_wait_s = rate_limit_max_wait_s
        if usd_per_mtok is None:
            from rag.runner.cost import PricingTable

            rule = PricingTable.load().rerank_price(model, TYPESAFE_PROVIDER)
            if not rule or "usd_per_mtok" not in rule:
                raise ValueError(
                    f"{model} ({TYPESAFE_PROVIDER}) has no price in configs/pricing.yaml. The "
                    "response carries no cost, so an unpriced Jev run would record $0 (MIS-025)."
                )
            usd_per_mtok = float(rule["usd_per_mtok"])
        self.usd_per_mtok = usd_per_mtok

    @staticmethod
    def _question(prompt) -> dict[str, Any]:
        spec = yaml.safe_load(prompt.render())
        return {
            "type": "noul",
            "instructions": spec["instructions"].strip(),
            "criteria": {"true": spec["criteria"]["true"].strip(), "false": spec["criteria"]["false"].strip()},
        }

    @property
    def reranker_id(self) -> str:
        return f"{self.model}@{TYPESAFE_PROVIDER}"

    def rerank(
        self, query: str, chunks: list[ScoredChunk], *, question_id: str = ""
    ) -> list[ScoredChunk]:
        if not chunks:
            return []
        bodies = [self._body(query, self.chunk_text[c.chunk_id]) for c in chunks]
        with ThreadPoolExecutor(max_workers=min(self.workers, len(bodies))) as pool:
            outcomes = list(pool.map(self._call, bodies))
        scored: list[ScoredChunk] = []
        for chunk, (payload, latency_ms, retries, rate_limited) in zip(chunks, outcomes):
            self.usage.retries += retries
            self.usage.rate_limited += rate_limited
            self.usage.latency_ms_total += latency_ms
            scored.append(ScoredChunk(chunk_id=chunk.chunk_id, doc_id=chunk.doc_id, score=self._parse(payload)))
        self.usage.candidates += len(chunks)
        # Ties break on chunk_id, as everywhere else in this repo (MIS-003).
        scored.sort(key=lambda c: (-c.score, c.chunk_id))
        check_same_chunks(chunks, scored)
        return scored

    def _body(self, query: str, passage: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "state": {"query": query, "passage": passage},
            "questions": {QUESTION_KEY: self.question},
        }

    def _call(self, body: dict[str, Any]) -> tuple[dict[str, Any], int, int, int]:
        """One request with bounded, backed-off retries. Runs on a worker thread, so
        it returns its counts instead of touching `self.usage`."""
        import httpx

        api_key = os.environ.get(KEY_ENV)
        if not api_key:
            raise RuntimeError(f"{KEY_ENV} is not set. It lives in .env at the repo root.")
        last_error: Exception | None = None
        retries = rate_limited = attempt = 0
        while attempt < self.max_attempts + rate_limited:
            attempt += 1
            started = time.perf_counter()
            try:
                response = httpx.post(
                    TYPESAFE_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=body,
                    timeout=self.timeout_s,
                )
                response.raise_for_status()
                latency_ms = int((time.perf_counter() - started) * 1000)
                return response.json(), latency_ms, retries, rate_limited
            except httpx.TransportError as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in _RETRY_STATUS:
                    raise RuntimeError(
                        f"{self.model}: HTTP {status} from TypeSafe: {exc.response.text[:500]}"
                    ) from exc
                last_error = exc
                if status == 429 and rate_limited < self.rate_limit_attempts:
                    rate_limited += 1
                    retries += 1
                    time.sleep(self._rate_limit_wait(exc.response.headers.get("Retry-After"), rate_limited))
                    continue
            retries += 1
            if attempt < self.max_attempts + rate_limited:
                time.sleep(self.backoff_s * (2 ** (min(attempt, 6) - 1)))
        raise RuntimeError(
            f"{self.model}: {attempt} Jev attempts failed ({rate_limited} rate-limited); "
            f"last error {type(last_error).__name__}: {last_error}"
        ) from last_error

    def _rate_limit_wait(self, retry_after: str | None, nth: int) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.rate_limit_max_wait_s)
            except ValueError:
                pass  # an HTTP-date; fall through to the schedule
        return min(self.rate_limit_backoff_s * (2 ** (nth - 1)), self.rate_limit_max_wait_s)

    def _parse(self, payload: dict[str, Any]) -> float:
        """P(relevant) from one response, asserted at the point of the call (MIS-006)."""
        served = payload.get("model")
        if served and served != self.model:
            raise RuntimeError(f"answered by {served!r}, not the pinned {self.model!r}")
        answer = (payload.get("answers") or {}).get(QUESTION_KEY)
        if not isinstance(answer, dict):
            raise RuntimeError(f"Jev response has no answer for {QUESTION_KEY!r}: {str(payload)[:300]}")
        if answer.get("type") not in (None, "noul"):
            raise RuntimeError(f"Jev answered a {answer.get('type')!r} question, not noul")
        value = answer.get("noul")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 1.0:
            raise RuntimeError(f"Jev noul {value!r} is not a probability")
        tokens = int((payload.get("usage") or {}).get("input_tokens", 0))
        if tokens <= 0:
            # No token count means no cost at all for this call — never a silent $0.
            raise RuntimeError(f"Jev response reports no input_tokens: {str(payload)[:300]}")
        self.usage.calls += 1
        self.usage.tokens += tokens
        self.usage.cost_usd += tokens / 1e6 * self.usd_per_mtok
        if TYPESAFE_PROVIDER not in self.usage.providers_seen:
            self.usage.providers_seen.append(TYPESAFE_PROVIDER)
        return float(value)

    def provenance(self) -> dict[str, Any]:
        meta = super().provenance()
        meta.update({
            "model": self.model,
            "provider": TYPESAFE_PROVIDER,
            "reranker_id": self.reranker_id,
            "prompt_ref": self.prompt.ref,
            "prompt_hash": self.prompt.content_hash,
            "calls_per_chunk": 1,
            "workers": self.workers,
            "endpoint": TYPESAFE_URL,
            "cost_basis": (
                f"reported input_tokens x published ${self.usd_per_mtok}/Mtok; the response "
                "carries no cost (DEC-101)"
            ),
        })
        return meta

    @classmethod
    def estimate_params(cls, reranker_params: dict[str, Any]) -> dict[str, Any] | None:
        return {
            "kind": "per_chunk_tokens",
            "model": reranker_params.get("model", ""),
            "provider": TYPESAFE_PROVIDER,
        }
