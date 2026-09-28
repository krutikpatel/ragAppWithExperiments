"""Startup check: every model a config names still resolves on OpenRouter — P3-02.

The Phase 3 baseline is frozen on exact model slugs. A slug that OpenRouter retires,
or a pinned provider that stops serving it, should stop a run before it spends
anything, with the slug named — not surface forty calls in as a 404 inside a metric.

"Resolves" is probed on the endpoint that would serve it (MIS-005):
`GET /api/v1/models/<id>/endpoints` returns 200 with the serving providers for a live
chat, embedding or rerank model, and 404 for an unknown id. It needs no API key and
costs nothing. Where the config pins a provider, the provider must be in that list:
the embedder and reranker pin one with `allow_fallbacks: false`, so a missing
provider is a hard failure; so does a judge with `judge_allow_fallbacks: false`
(DEC-080). A judge sent with fallbacks needs at least one of its providers.

A network failure after retries is `ModelCheckUnavailable`, not `ModelResolutionError`:
"OpenRouter did not answer" and "your model is gone" are different facts (P3-10).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from rag.runner.config import EvalTier, RunConfig
from rag.runner.cost import OPENROUTER_ENDPOINTS_URL

RETRIES = 3


class ModelResolutionError(RuntimeError):
    """A configured slug, or its pinned provider, is not served by OpenRouter today."""


class ModelCheckUnavailable(RuntimeError):
    """OpenRouter could not be reached to check. Infrastructure, not configuration."""


@dataclass(frozen=True)
class ModelRef:
    role: str
    model: str
    providers: tuple[str, ...] = ()
    # True: every listed provider must serve it (a hard pin). False: at least one.
    pinned: bool = True


@dataclass
class ModelCheck:
    ref: ModelRef
    resolves: bool
    providers_served: list[str] = field(default_factory=list)
    missing_providers: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if not self.resolves:
            return False
        if not self.ref.providers:
            return True
        return not self.missing_providers if self.ref.pinned else len(self.missing_providers) < len(self.ref.providers)


def configured_models(config: RunConfig) -> list[ModelRef]:
    """Every hosted model this config would call, with its provider pin."""
    refs: list[ModelRef] = []

    def from_params(role: str, params: dict[str, Any]) -> None:
        if params.get("embedding_backend", "openrouter") == "openrouter" and params.get("embedding_model"):
            provider = params.get("embedding_provider")
            refs.append(ModelRef(f"{role} embedder", params["embedding_model"], (provider,) if provider else ()))
        if params.get("model"):
            provider = params.get("provider")
            refs.append(ModelRef(role, params["model"], (provider,) if provider else ()))
        for value in params.values():
            if isinstance(value, dict):
                from_params(role, value)

    from_params("retriever", config.retriever_params)
    from_params("chunker", config.chunker_params)
    if config.reranker:
        from_params("reranker", config.reranker_params)
    if config.query_transform:
        from_params("query transform", config.query_transform_params)
    if config.eval_tier is EvalTier.TIER_2:
        refs.append(ModelRef("generator", config.generator_model))
        if config.context_compressor:
            from_params("compressor", config.context_compressor_params)
        if config.grounding_check:
            from_params("grounding check", config.grounding_check_params)
        if not config.skip_judge:
            refs.append(ModelRef("judge", config.judge_model, tuple(config.judge_provider_order),
                                pinned=not config.judge_allow_fallbacks))
            if config.judge_embedding_model:
                refs.append(ModelRef("judge embedder", config.judge_embedding_model))
    return [r for r in refs if r.model]


def fetch_endpoints(model: str) -> list[str] | None:
    """Provider names serving `model`, or None when OpenRouter does not know the id."""
    import httpx

    for attempt in range(RETRIES):
        try:
            response = httpx.get(OPENROUTER_ENDPOINTS_URL.format(model=model), timeout=20.0)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return [e.get("provider_name", "") for e in response.json()["data"]["endpoints"]]
        except httpx.TransportError as exc:
            error: Exception = exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500 and exc.response.status_code != 429:
                raise ModelCheckUnavailable(f"{model}: HTTP {exc.response.status_code} from OpenRouter") from exc
            error = exc
        time.sleep(2 ** attempt)
    raise ModelCheckUnavailable(f"could not reach OpenRouter to check {model!r} after {RETRIES} tries: {error}")


def check_models(
    refs: list[ModelRef], *, fetch: Callable[[str], list[str] | None] = fetch_endpoints
) -> list[ModelCheck]:
    served: dict[str, list[str] | None] = {}
    results = []
    for ref in refs:
        if ref.model not in served:
            served[ref.model] = fetch(ref.model)
        providers = served[ref.model]
        results.append(ModelCheck(
            ref=ref,
            resolves=providers is not None,
            providers_served=sorted(set(providers or [])),
            missing_providers=[p for p in ref.providers if p not in (providers or [])],
        ))
    return results


def verify_config_models(
    config: RunConfig, *, fetch: Callable[[str], list[str] | None] = fetch_endpoints
) -> list[ModelCheck]:
    """Raise `ModelResolutionError` naming every configured slug that no longer resolves."""
    return verify_models(configured_models(config), fetch=fetch)


def verify_models(
    refs: list[ModelRef], *, fetch: Callable[[str], list[str] | None] = fetch_endpoints
) -> list[ModelCheck]:
    results = check_models(refs, fetch=fetch)
    failed = [r for r in results if not r.ok]
    if failed:
        lines = []
        for r in failed:
            if not r.resolves:
                lines.append(f"  {r.ref.role}: {r.ref.model!r} does not resolve on OpenRouter (404)")
            else:
                lines.append(f"  {r.ref.role}: {r.ref.model!r} is no longer served by "
                             f"{r.missing_providers} (served by {r.providers_served})")
        raise ModelResolutionError(
            "configured model check failed — nothing has been spent (P3-02):\n" + "\n".join(lines)
        )
    return results


def format_checks(results: list[ModelCheck]) -> str:
    today = date.today().isoformat()
    lines = [f"model check {today}:"]
    for r in results:
        pin = f" pinned {list(r.ref.providers)}" if r.ref.providers else ""
        lines.append(f"  {'ok  ' if r.ok else 'FAIL'} {r.ref.role:<16} {r.ref.model}{pin}")
    return "\n".join(lines)
