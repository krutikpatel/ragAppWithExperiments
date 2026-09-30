"""P3-13 — the answer API: shape, errors, the promoted-retrieval check, no forked logic,
and the contract test against the gate's own answers. No model call is ever made here."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")  # the `api` extra; CI's unit tests may not install it
from fastapi.testclient import TestClient  # noqa: E402

import rag.api as api  # noqa: E402
from rag.citations import RenderedCitation  # noqa: E402
from rag.generation.base import GeneratedAnswer  # noqa: E402
from rag.pipeline import PipelineAnswer  # noqa: E402


class FakePipeline:
    def __init__(self, fail=False):
        from rag.runner.config import load_config_file

        self.config = load_config_file("configs/baseline_dense_tier2_v2.yaml")
        self.fail = fail

    def answer(self, question, question_id="ask"):
        if self.fail:
            raise ConnectionError("provider unreachable after retries")
        answer = GeneratedAnswer(text=f"1. Do it. [doc:{'a' * 64}]", cited_doc_ids=["a" * 64],
                                 model="openai/gpt-5-nano", prompt_ref="baseline_answer@v1",
                                 tokens_in=10, tokens_out=5, reasoning_tokens=0, latency_ms=3,
                                 meta={"cached": False})
        cites = [RenderedCitation("a" * 64, "Doing It", "https://support.wix.com/x", "c1", "The paragraph.", True, True),
                 RenderedCitation("b" * 64, "Unused", None, "c2", "Other.", True, False)]
        return PipelineAnswer(question, answer, cites, ["a" * 64, "b" * 64], 1.0, False,
                              {"retrieve": 1, "assemble": 0, "generate": 2, "total": 3}, 0.000012)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(api.state, "pipeline", FakePipeline())
    monkeypatch.setattr(api.state, "replay", False)
    monkeypatch.setenv("RAG_API_LOG", "")  # P3-14's request log: stdout only in tests
    with TestClient(api.app) as c:
        yield c


def test_ask_returns_the_story_shape_with_only_cited_sources(client):
    r = client.post("/ask", json={"question": "How do I do it?"})
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"answer", "citations", "refused", "meta"}
    assert d["citations"] == [{"article_title": "Doing It", "url": "https://support.wix.com/x",
                               "chunk_text": "The paragraph.", "doc_id": "a" * 64, "in_context": True}]
    assert d["refused"] is False
    assert {"config_hash", "latency_ms", "cost_usd"} <= set(d["meta"])
    assert d["meta"]["config_hash"] == FakePipeline().config.config_hash


def test_bad_input_is_rejected_and_a_provider_failure_is_a_502_not_an_answer(client, monkeypatch):
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={}).status_code == 422
    monkeypatch.setattr(api.state, "pipeline", FakePipeline(fail=True))
    r = client.post("/ask", json={"question": "anything"})
    assert r.status_code == 502 and "provider unreachable" in r.json()["detail"]


def test_health_and_page(client):
    assert client.get("/health").json()["ready"] is True
    page = client.get("/")
    assert page.status_code == 200 and "fetch(\"/ask\"" in page.text


def test_the_served_config_must_retrieve_exactly_like_promoted():
    from rag.runner.config import load_config_file

    promoted = load_config_file(api.PROMOTED)
    assert api.check_promoted_retrieval(load_config_file(api.DEFAULT_CONFIG), promoted) == []
    drifted = load_config_file(api.DEFAULT_CONFIG).with_(top_k=4)
    assert api.check_promoted_retrieval(drifted, promoted) == ["top_k"]


def test_the_pipeline_refuses_features_it_does_not_implement():
    from rag.pipeline import Pipeline
    from rag.runner.config import load_config_file

    config = load_config_file(api.DEFAULT_CONFIG, overrides={"judge_model": "", "judge_embedding_model": "",
                                                              "skip_judge": True, "context_order": "rank",
                                                              "grounding_check": "self_check",
                                                              "grounding_check_params": {"model": "x/y"}})
    with pytest.raises(ValueError, match="no forked logic"):
        Pipeline(config)


def test_no_forked_logic_ask_and_the_api_both_answer_through_pipeline():
    """`rag ask` and the API share `rag.pipeline.Pipeline`; neither wires its own retriever."""
    for module in ("rag/ask.py", "rag/api.py"):
        src = Path(module).read_text()
        assert "Pipeline" in src and "build_retriever" not in src and "OpenRouterGenerator(" not in src


# --- the contract test ----------------------------------------------------------------

STORE = Path("results/runs.sqlite")
CACHE = Path("results/ci_call_cache.sqlite")
READY = Path("data/frozen/corpus.parquet").exists() and STORE.exists() and CACHE.exists()


def _gate_golden_run() -> tuple[str, dict[str, str]] | None:
    """The newest local golden run the gate made under the call cache, and its answers."""
    with sqlite3.connect(STORE) as c:
        for run_id, metrics in c.execute(
                "SELECT run_id, metrics_json FROM runs WHERE split='golden_v1' AND eval_tier='tier2' "
                "AND status='VALID' ORDER BY timestamp DESC"):
            if "call_cache" in json.loads(metrics or "{}"):
                answers = dict(c.execute("SELECT question_id, generated_answer FROM run_questions WHERE run_id=?",
                                         (run_id,)).fetchall())
                return run_id, answers
    return None


@pytest.mark.skipif(not READY, reason="needs the frozen corpus, a results store and the ci-eval call cache")
def test_contract_the_api_returns_the_gates_own_answers_for_five_golden_questions(monkeypatch):
    """P3-13: 'for 5 golden questions, API output equals ci-eval pipeline output'. With every
    model call blocked, the only way to answer is to rebuild the exact prompt the gate built
    and replay its cached answer — so equal text proves the same pipeline, at $0."""
    from rag.dataset.golden import load_golden
    from rag.embedding.base import Embedder
    from rag.generation.base import OpenRouterGenerator

    found = _gate_golden_run()
    if found is None:
        pytest.skip("no golden run made under the call cache on this machine")
    run_id, gate_answers = found
    golden = [g for g in load_golden() if g["stratum"] != "unanswerable"][:5]

    def blocked(*a, **k):
        raise AssertionError("a model was called — the API did not rebuild the gate's prompt")

    monkeypatch.setattr(OpenRouterGenerator, "_complete", blocked)
    monkeypatch.setattr(Embedder, "_embed", blocked, raising=False)
    monkeypatch.setattr(api.state, "pipeline", None)
    monkeypatch.setenv("RAG_API_REPLAY", "1")
    monkeypatch.setenv("RAG_API_LOG", "")
    with TestClient(api.app) as client:
        for g in golden:
            d = client.post("/ask", json={"question": g["question"]}).json()
            assert d["answer"] == gate_answers[g["question_id"]], f"{g['question_id']} differs from {run_id}"
            assert d["meta"]["replayed"] is True and d["meta"]["cost_usd"] == 0.0


def test_the_image_contains_every_file_the_api_reads_at_startup():
    """MIS-051: P3-14 made the API read ci/gate.yaml and the image did not copy it; the
    container failed at startup while every unit test passed."""
    import re

    copied = re.findall(r"^COPY (?!--from)(\S+)", Path("Dockerfile").read_text(), re.M)
    needed = [api.GATED, api.PROMOTED, api.DEFAULT_CONFIG, "prompts", "eval"]
    for path in needed:
        assert any(path == c or path.startswith(c.rstrip("/") + "/") for c in copied), f"{path} is not in the image"
