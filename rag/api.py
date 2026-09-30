"""The answer API and demo page — P3-13 (DEC-097).

`POST /ask {"question": ...}` →
`{answer, citations: [{article_title, url, chunk_text}], refused, meta: {config_hash, latency_ms, cost_usd}}`.

It answers through `rag.pipeline.Pipeline` — the same components, built from the same config
file, as the runner the CI gate scores — so the page shows what the gate measured. At startup
it checks that the config's retrieval is exactly `configs/promoted.yaml`'s (the story: "it
loads promoted.yaml"); a config that has drifted from the promoted retrieval is refused.

Environment:
- `RAG_API_CONFIG` — the Tier 2 config to serve (default the v2 control, DEC-080: promoted
  retrieval + generator + prompt `baseline_answer@v1`).
- `RAG_API_REPLAY=1` — answer through the ci-eval call cache (DEC-084): a question the gate
  has already answered replays that exact answer at $0. For the contract test and demos; off
  by default, so a real deployment always calls the model.
- `OPENROUTER_API_KEY` — from `.env`, never logged.

Run: `uvicorn rag.api:app` (or `docker compose up`).
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DEFAULT_CONFIG = "configs/baseline_dense_tier2_v2.yaml"
PROMOTED = "configs/promoted.yaml"
PAGE = Path(__file__).with_name("api_page.html")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


def check_promoted_retrieval(config: Any, promoted: Any) -> list[str]:
    """Fields that decide what is retrieved, where the served config differs from promoted."""
    skip = {"split", "eval_tier"}
    return [f for f in type(config).TIER1_FIELDS
            if f not in skip and getattr(config, f) != getattr(promoted, f)]


class State:
    pipeline: Any = None
    replay: bool = False


state = State()


def build(config_path: str | None = None) -> Any:
    from rag.pipeline import Pipeline
    from rag.runner.config import load_config_file

    pipeline = Pipeline.from_config_file(config_path or os.environ.get("RAG_API_CONFIG", DEFAULT_CONFIG))
    drift = check_promoted_retrieval(pipeline.config, load_config_file(PROMOTED))
    if drift:
        raise RuntimeError(f"the served config's retrieval differs from {PROMOTED} on {drift}")
    return pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    if state.pipeline is None:  # tests inject one
        state.pipeline = build()
    state.replay = os.environ.get("RAG_API_REPLAY") == "1"
    yield


app = FastAPI(title="WixQA RAG", version="p3-13", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    ready = state.pipeline is not None
    return {"ready": ready, "config_hash": state.pipeline.config.config_hash if ready else None,
            "replay": state.replay}


@app.post("/ask")
def ask(request: AskRequest) -> dict[str, Any]:
    from rag.call_cache import CallCache, call_cache
    from rag.pipeline import describe

    if state.pipeline is None:
        raise HTTPException(503, "pipeline not loaded")
    started = time.perf_counter()
    cache = CallCache() if state.replay else None
    try:
        with (call_cache(cache) if cache is not None else nullcontext()):
            result = state.pipeline.answer(request.question.strip())
    except Exception as exc:  # a provider outage is an error response, never a made-up answer
        raise HTTPException(502, f"answer failed: {type(exc).__name__}: {str(exc)[:200]}") from exc
    finally:
        if cache is not None:
            cache.close()
    return {
        **describe(result),
        "meta": {
            "config_hash": state.pipeline.config.config_hash,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "cost_usd": result.cost_usd,
            "timings_ms": result.timings_ms,
            "replayed": bool(result.answer.meta.get("cached")),
            "model": result.answer.model,
            "prompt": result.answer.prompt_ref,
        },
    }


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    return PAGE.read_text()
