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
- `RAG_API_LOG` — where the per-request JSON log is appended (P3-14; default
  `results/api_requests.jsonl`, gitignored; empty = stdout only). Every line is also
  written to stdout, so `docker compose logs` shows it.
- `OPENROUTER_API_KEY` — from `.env`, never logged.

Per-request log (P3-14, DEC-098): one JSON object per request — request id, status,
per-stage latency (embed, retrieve, assemble, generate), tokens, cost, config hash,
refused, served model, attempts, and on failure the stage that failed. The question is
logged as a hash and a length, never as text: an operator log is not the place for what
users typed.

Run: `uvicorn rag.api:app` (or `docker compose up`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DEFAULT_CONFIG = "configs/baseline_dense_tier2_v2.yaml"
PROMOTED = "configs/promoted.yaml"
GATED = "ci/gate.yaml"
PAGE = Path(__file__).with_name("api_page.html")
DEFAULT_LOG = "results/api_requests.jsonl"
# What decides the answer once the context is chosen. The served config must match the
# gate's golden config on every one, so the API answers only with what `rag ci-eval`
# scored — including any fallback chain, which the gate tests model by model (P3-14).
GENERATION_FIELDS = ("generator_model", "generator_prompt", "generator_max_tokens",
                     "generator_reasoning_effort", "generator_fallback_models",
                     "context_max_tokens", "context_order")

log = logging.getLogger("rag.api.requests")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


def check_promoted_retrieval(config: Any, promoted: Any) -> list[str]:
    """Fields that decide what is retrieved, where the served config differs from promoted."""
    skip = {"split", "eval_tier"}
    return [f for f in type(config).TIER1_FIELDS
            if f not in skip and getattr(config, f) != getattr(promoted, f)]


def check_gated_generation(config: Any, gated: Any) -> list[str]:
    """Generation fields where the served config differs from the one the CI gate scores."""
    return [f for f in GENERATION_FIELDS if getattr(config, f) != getattr(gated, f)]


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
    import yaml

    gated_path = yaml.safe_load(Path(GATED).read_text())["configs"]["golden"]
    ungated = check_gated_generation(pipeline.config, load_config_file(gated_path))
    if ungated:
        raise RuntimeError(f"the served config's generation differs from the gated {gated_path} on "
                           f"{ungated}; an ungated generator (or fallback) would bypass `rag ci-eval`")
    return pipeline


def write_log(record: dict[str, Any]) -> None:
    """One JSON line to stdout and, unless RAG_API_LOG is empty, to the log file. A log
    that cannot be written never fails the request it describes."""
    line = json.dumps(record, separators=(",", ":"), default=str)
    print(line, file=sys.stdout, flush=True)
    path = os.environ.get("RAG_API_LOG", DEFAULT_LOG)
    if path:
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            log.warning("request log not written to %s: %s", path, exc)


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
    request_id = uuid.uuid4().hex[:16]
    question = request.question.strip()
    started = time.perf_counter()
    record: dict[str, Any] = {
        "event": "ask", "request_id": request_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_hash": state.pipeline.config.config_hash,
        "question_sha256": hashlib.sha256(question.encode()).hexdigest()[:16], "question_chars": len(question),
        "replay": state.replay,
    }
    cache = CallCache() if state.replay else None
    try:
        with (call_cache(cache) if cache is not None else nullcontext()):
            result = state.pipeline.answer(question)
    except Exception as exc:  # a provider outage is an error response, never a made-up answer
        record.update(status=502, latency_ms=int((time.perf_counter() - started) * 1000),
                      stage=getattr(exc, "stage", "unknown"),
                      error=f"{type(getattr(exc, 'cause', exc)).__name__}: {str(getattr(exc, 'cause', exc))[:200]}")
        write_log(record)
        raise HTTPException(502, f"answer failed (request {request_id}): {str(exc)[:200]}") from exc
    finally:
        if cache is not None:
            cache.close()
    latency_ms = int((time.perf_counter() - started) * 1000)
    record.update(status=200, latency_ms=latency_ms, stages_ms=result.timings_ms, cost_usd=result.cost_usd,
                  refused=result.refused, citations=len([c for c in result.citations if c.cited]),
                  **result.usage)
    write_log(record)
    return {
        **describe(result),
        "meta": {
            "request_id": request_id,
            "config_hash": state.pipeline.config.config_hash,
            "latency_ms": latency_ms,
            "cost_usd": result.cost_usd,
            "timings_ms": result.timings_ms,
            "replayed": bool(result.answer.meta.get("cached")),
            "model": result.answer.model,
            "served_model": result.usage.get("served_model", result.answer.model),
            "prompt": result.answer.prompt_ref,
        },
    }


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    return PAGE.read_text()
