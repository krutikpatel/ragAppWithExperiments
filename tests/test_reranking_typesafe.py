"""DEC-101 — TypeSafe Jev as a reranker. No call reaches TypeSafe here."""

from __future__ import annotations

import httpx
import pytest

from rag.retrieval.base import ScoredChunk

MODEL = "jev-1.13.0"


def _jev(**kwargs):
    from rag.reranking.typesafe import TypeSafeJevReranker

    kwargs.setdefault("model", MODEL)
    return TypeSafeJevReranker(kwargs.pop("chunk_text", {}), **kwargs)


def _payload(noul=0.8, tokens=300, model=MODEL, **answer):
    return {
        "model": model,
        "answers": {"relevant": {"type": "noul", "noul": noul, **answer}},
        "usage": {"input_tokens": tokens, "output_tokens": 1},
    }


# --- construction ----------------------------------------------------------------

def test_refuses_a_missing_model():
    with pytest.raises(ValueError, match="Krutik"):
        _jev(model="")


@pytest.mark.parametrize("alias", ["jev-latest", "jev-preview"])
def test_refuses_a_floating_alias(alias):
    with pytest.raises(ValueError, match="alias"):
        _jev(model=alias)


def test_refuses_a_model_with_no_price():
    """The response carries no cost, so an unpriced model would record $0 (MIS-025)."""
    with pytest.raises(ValueError, match="no price"):
        _jev(model="jev-9.99.0")


def test_reads_the_published_price_from_the_table():
    assert _jev().usd_per_mtok == 0.042


def test_the_request_is_one_noul_question_about_one_query_and_one_passage():
    body = _jev()._body("How do I add a domain?", "Go to Domains. Click Add.")
    assert body["model"] == MODEL
    assert body["state"] == {"query": "How do I add a domain?", "passage": "Go to Domains. Click Add."}
    question = body["questions"]["relevant"]
    assert question["type"] == "noul"
    assert set(question["criteria"]) == {"true", "false"}
    assert "THIS question" in question["instructions"]


# --- the response is asserted at the point of the call (MIS-006) --------------------

def test_parse_reads_the_probability_tokens_and_cost():
    jev = _jev()
    assert jev._parse(_payload(noul=0.73, tokens=1_000_000)) == 0.73
    assert jev.usage.calls == 1
    assert jev.usage.tokens == 1_000_000
    assert jev.query_cost_usd() == pytest.approx(0.042)
    assert jev.usage.providers_seen == ["TypeSafe"]


@pytest.mark.parametrize(
    "payload, message",
    [
        (_payload(model="jev-1.14.0"), "not the pinned"),
        ({"model": MODEL, "answers": {}, "usage": {"input_tokens": 5}}, "no answer"),
        (_payload(type="choice"), "not noul"),
        (_payload(noul=1.2), "not a probability"),
        (_payload(noul=None), "not a probability"),
        (_payload(noul=True), "not a probability"),
        (_payload(tokens=0), "no input_tokens"),
    ],
)
def test_parse_refuses_a_broken_response(payload, message):
    with pytest.raises(RuntimeError, match=message):
        _jev()._parse(payload)


def test_a_response_without_a_model_field_is_accepted():
    """The API reference shows `model` on the response; if it is absent there is
    nothing to compare, and the request's pin stands."""
    payload = _payload()
    del payload["model"]
    assert _jev()._parse(payload) == 0.8


# --- reranking -------------------------------------------------------------------

def test_rerank_sorts_by_probability_and_keeps_every_chunk(monkeypatch):
    texts = {"c1": "alpha", "c2": "beta", "c3": "gamma"}
    probability = {"alpha": 0.1, "beta": 0.9, "gamma": 0.5}
    jev = _jev(chunk_text=texts, workers=3)
    monkeypatch.setattr(
        jev, "_call", lambda body: (_payload(noul=probability[body["state"]["passage"]]), 10, 1, 0)
    )
    chunks = [ScoredChunk(chunk_id=c, doc_id=f"d{c}", score=1.0) for c in ("c1", "c2", "c3")]
    out = jev.rerank("q", chunks)
    assert [c.chunk_id for c in out] == ["c2", "c3", "c1"]
    assert [c.score for c in out] == [0.9, 0.5, 0.1]
    assert jev.usage.calls == 3, "one call per chunk (DEC-101)"
    assert jev.usage.candidates == 3
    assert jev.usage.retries == 3
    assert jev.usage.latency_ms_total == 30


def test_rerank_breaks_ties_on_chunk_id(monkeypatch):
    jev = _jev(chunk_text={"b": "x", "a": "y"})
    monkeypatch.setattr(jev, "_call", lambda body: (_payload(noul=0.5), 1, 0, 0))
    chunks = [ScoredChunk(chunk_id=c, doc_id=c, score=1.0) for c in ("b", "a")]
    assert [c.chunk_id for c in jev.rerank("q", chunks)] == ["a", "b"]


# --- retries ---------------------------------------------------------------------

def _response(status: int, body: object = None) -> httpx.Response:
    return httpx.Response(status, json=body if body is not None else {},
                          request=httpx.Request("POST", "https://api.typesafe.ai/v1/systemone"))


def test_call_retries_overload_and_rate_limits_then_succeeds(monkeypatch):
    import rag.reranking.typesafe as ts

    monkeypatch.setenv("TYPESAFE_JEV_KEY", "test-key")
    replies = [_response(529), _response(429), _response(200, _payload())]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(ts.time, "sleep", lambda s: None)
    payload, _latency, retries, rate_limited = _jev()._call({})
    assert payload["answers"]["relevant"]["noul"] == 0.8
    assert (retries, rate_limited) == (2, 1)


def test_call_retries_cloudflare_errors(monkeypatch):
    """MIS-052: an HTTP 520 from Cloudflare ended EXP-0065's first attempt."""
    import rag.reranking.typesafe as ts

    monkeypatch.setenv("TYPESAFE_JEV_KEY", "test-key")
    replies = [_response(520), _response(524), _response(200, _payload())]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(ts.time, "sleep", lambda s: None)
    assert _jev()._call({})[2] == 2


def test_a_failed_call_still_counts_the_billed_calls_beside_it(monkeypatch):
    """MIS-052: the chunks that were scored were paid for, even if one call failed."""
    jev = _jev(chunk_text={"a": "ok", "b": "boom", "c": "ok"}, workers=3)

    def call(body):
        if body["state"]["passage"] == "boom":
            raise RuntimeError("HTTP 520")
        return _payload(tokens=100), 5, 0, 0

    monkeypatch.setattr(jev, "_call", call)
    chunks = [ScoredChunk(chunk_id=c, doc_id=c, score=1.0) for c in ("a", "b", "c")]
    with pytest.raises(RuntimeError, match="520"):
        jev.rerank("q", chunks)
    assert jev.usage.calls == 2
    assert jev.usage.tokens == 200


@pytest.mark.parametrize("status", [401, 403, 422])
def test_call_raises_a_permanent_error_at_once(monkeypatch, status):
    """A retried auth or validation error is a hidden bug (MIS-014)."""
    monkeypatch.setenv("TYPESAFE_JEV_KEY", "test-key")
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(1) or _response(status))
    with pytest.raises(RuntimeError, match=f"HTTP {status}"):
        _jev()._call({})
    assert len(calls) == 1


def test_call_gives_up_after_its_budget(monkeypatch):
    import rag.reranking.typesafe as ts

    monkeypatch.setenv("TYPESAFE_JEV_KEY", "test-key")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response(503))
    monkeypatch.setattr(ts.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="4 Jev attempts failed"):
        _jev()._call({})


def test_call_needs_the_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_JEV_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TYPESAFE_JEV_KEY"):
        _jev()._call({})


# --- cost estimate and model check -------------------------------------------------

def test_estimate_is_one_call_per_candidate_chunk_at_the_published_rate():
    from rag.reranking.typesafe import TypeSafeJevReranker
    from rag.runner.cost import PricingTable, estimate_rerank_cost

    estimate = estimate_rerank_cost(
        reranker="typesafe_jev",
        estimate_params=TypeSafeJevReranker.estimate_params({"model": MODEL}),
        n_questions=200, candidate_docs=50, candidate_words=309, pricing=PricingTable.load(),
    )
    assert estimate["calls"] == round(200 * 58.4)
    assert estimate["rerank_usd"] == pytest.approx(estimate["tokens"] / 1e6 * 0.042, abs=1e-4)
    assert "calibrated on probe jev_20260930" in estimate["source"]


def test_the_estimate_reproduces_the_probes_measured_tokens_per_call():
    """The probe billed a mean 816.0 input tokens per call at 339.4 passage words."""
    from rag.runner.cost import JEV_TOKENS_PER_CALL_OVERHEAD, WORDS_TO_TOKENS

    assert 339.4 * WORDS_TO_TOKENS + JEV_TOKENS_PER_CALL_OVERHEAD == pytest.approx(816.0, abs=1)


# --- stored Jev output (CLAUDE.md: test every parser of model output on stored output) --

def test_the_parser_accepts_every_stored_jev_response():
    import json
    from pathlib import Path

    rows = [json.loads(line) for line in Path("tests/fixtures/jev_1_13_0_responses.jsonl").read_text().splitlines()]
    assert len(rows) == 270
    jev = _jev()
    scores = [jev._parse(row["response"]) for row in rows]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert jev.usage.tokens == 220_328
    assert jev.query_cost_usd() == pytest.approx(220_328 / 1e6 * 0.042)


def test_an_unpriced_jev_model_is_unknown_not_free():
    from rag.runner.cost import PricingTable, estimate_rerank_cost

    estimate = estimate_rerank_cost(
        reranker="typesafe_jev",
        estimate_params={"kind": "per_chunk_tokens", "model": "jev-9.99.0", "provider": "TypeSafe"},
        n_questions=200, candidate_docs=50, candidate_words=309, pricing=PricingTable.load(),
    )
    assert "price_unavailable" in estimate
    assert "rerank_usd" not in estimate


def test_model_check_does_not_look_for_jev_on_openrouter():
    from rag.runner.config import load_config_file
    from rag.runner.model_check import configured_models

    config = load_config_file("configs/exp_0065_rerank_jev_dev.yaml")
    roles = {ref.role for ref in configured_models(config)}
    assert "reranker" not in roles
    assert "retriever embedder" in roles
