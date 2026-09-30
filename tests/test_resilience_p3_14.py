"""P3-14 — request logging and resilience: the per-request JSON log, timeouts and bounded
retries on every OpenRouter call, and fallback models that are off by default and gated
model by model. No model call is ever made here."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

from rag.runner.config import RunConfig, load_config_file

GOLDEN = "configs/golden_generate_v2.yaml"


# --- timeouts and bounded retries on every OpenRouter call -----------------------------

# Every file that talks to OpenRouter directly, and the policy it carries. A new call site
# fails `test_every_openrouter_call_site_is_accounted_for` until it is added here WITH a
# timeout and a bounded retry — that is the point of the inventory.
CALL_SITES = {
    "rag/generation/base.py": "OpenRouterGenerator._complete: max_attempts + a 429 budget, backoff",
    "rag/embedding/base.py": "OpenRouterEmbedder: retries with backoff, a 429 budget",
    "rag/reranking/openrouter.py": "OpenRouterReranker: retries with backoff, a 429 budget",
    "rag/runner/model_check.py": "fetch_endpoints: RETRIES with backoff",
    "rag/http_retry.py": "get_json: bounded retries with backoff (cost estimator, pricing refresh)",
    "rag/eval/judge.py": "AsyncOpenAI(max_retries=JUDGE_HTTP_RETRIES) + FaithfulnessClaims' one retry",
}
RAW_CALL = re.compile(r"\b(httpx\.(get|post)|AsyncOpenAI|OpenAI)\(")


def _code_lines(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines() if not line.strip().startswith("#")]


def test_every_openrouter_call_site_is_accounted_for():
    found = {str(p) for p in Path("rag").rglob("*.py") if any(RAW_CALL.search(l) for l in _code_lines(p))}
    assert found == set(CALL_SITES), "a new direct HTTP call needs a timeout, a bounded retry and an entry here"


def test_every_call_carries_a_timeout():
    for path in CALL_SITES:
        lines = _code_lines(Path(path))
        for i, line in enumerate(lines):
            if RAW_CALL.search(line):
                call = "\n".join(lines[i:i + 10])
                assert "timeout=" in call, f"{path}: {line.strip()} has no timeout"


def test_the_judge_client_retry_is_explicit():
    src = Path("rag/eval/judge.py").read_text()
    assert "max_retries=JUDGE_HTTP_RETRIES" in src


def _response(status: int, body: object = None) -> httpx.Response:
    return httpx.Response(status, json=body if body is not None else {}, request=httpx.Request("GET", "https://x"))


def test_get_json_retries_transient_failures_with_backoff_then_succeeds(monkeypatch):
    import rag.http_retry as hr

    replies = [httpx.ConnectTimeout("slow"), _response(503), _response(200, {"data": [1]})]
    sleeps: list[float] = []
    monkeypatch.setattr(httpx, "get", lambda url, timeout: (r := replies.pop(0)) if not isinstance(
        replies[0], Exception) else (_ for _ in ()).throw(replies.pop(0)))
    monkeypatch.setattr(hr.time, "sleep", sleeps.append)
    assert hr.get_json("https://x", timeout=5) == {"data": [1]}
    assert sleeps == [2.0, 4.0]


def test_get_json_raises_a_permanent_error_at_once_and_gives_up_after_its_budget(monkeypatch):
    import rag.http_retry as hr

    monkeypatch.setattr(hr.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(httpx, "get", lambda url, timeout: calls.append(1) or _response(404))
    with pytest.raises(httpx.HTTPStatusError):
        hr.get_json("https://x")
    assert len(calls) == 1
    calls.clear()
    monkeypatch.setattr(httpx, "get", lambda url, timeout: calls.append(1) or _response(502))
    with pytest.raises(RuntimeError, match="4 attempts failed"):
        hr.get_json("https://x", attempts=4)
    assert len(calls) == 4


# --- fallback models: off by default, and a different config when on -------------------

def _generator(fallbacks=()):
    from rag.generation.base import GeneratorConfig, OpenRouterGenerator

    return OpenRouterGenerator(GeneratorConfig(model="openai/gpt-5-nano", prompt_id="baseline_answer",
                                               fallback_models=tuple(fallbacks)))


def _capture_post(monkeypatch, served="openai/gpt-5-nano"):
    sent = []

    def post(url, headers, json, timeout):
        sent.append(json)
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "model": served, "choices": [{"message": {"content": "1. Do it. [doc:abcdef12]"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(httpx, "post", post)
    return sent


def test_fallbacks_are_off_by_default_and_the_request_names_one_model(monkeypatch):
    sent = _capture_post(monkeypatch)
    completion = _generator()._complete("prompt")
    assert sent[0]["model"] == "openai/gpt-5-nano" and "models" not in sent[0]
    assert completion.served_model == "openai/gpt-5-nano"
    assert RunConfig.__dataclass_fields__["generator_fallback_models"].default == ()
    for path in Path("configs").glob("*.yaml"):
        assert "generator_fallback_models" not in path.read_text(), f"{path} enables a fallback"


def test_an_enabled_fallback_sends_the_ordered_chain_and_records_who_answered(monkeypatch):
    sent = _capture_post(monkeypatch, served="x/fallback")
    completion = _generator(["x/fallback"])._complete("prompt")
    assert "model" not in sent[0] and sent[0]["models"] == ["openai/gpt-5-nano", "x/fallback"]
    assert completion.served_model == "x/fallback"


def test_a_fallback_is_its_own_config_and_off_moves_no_existing_hash():
    base = load_config_file(GOLDEN)
    assert load_config_file(GOLDEN, overrides={"generator_fallback_models": []}).config_hash == base.config_hash
    on = load_config_file(GOLDEN, overrides={"generator_fallback_models": ["x/fallback"]})
    assert on.config_hash != base.config_hash and on.generator_fallback_models == ("x/fallback",)
    with pytest.raises(ValueError, match="no model twice"):
        load_config_file(GOLDEN, overrides={"generator_fallback_models": ["openai/gpt-5-nano"]})


def test_the_gate_evaluates_each_fallback_as_its_own_config():
    from rag.runner.ci_eval import fallback_variants, worst_status

    on = load_config_file(GOLDEN, overrides={"generator_fallback_models": ["x/a", "y/b"]})
    variants = fallback_variants(on)
    assert [v.generator_model for v in variants] == ["x/a", "y/b"]
    assert all(v.generator_fallback_models == () for v in variants)
    assert all(v.with_(generator_model="openai/gpt-5-nano") == load_config_file(GOLDEN) for v in variants)
    assert fallback_variants(load_config_file(GOLDEN)) == []
    assert worst_status(["PASS", "FAIL", "PASS"]) == "FAIL" and worst_status(["PASS", "ERROR", "FAIL"]) == "ERROR"


def test_ci_eval_runs_and_gates_the_fallback_and_fails_when_only_the_fallback_regresses(tmp_path, monkeypatch):
    import rag.runner.ci_eval as ce
    import rag.runner.model_check as mc

    cfg = tmp_path / "golden_fb.yaml"
    cfg.write_text(Path(GOLDEN).read_text() + "generator_fallback_models: [x/fallback]\n")
    gate = yaml.safe_load(Path("ci/gate.yaml").read_text())
    gate["configs"]["golden"] = str(cfg)
    gate_path = tmp_path / "gate.yaml"
    gate_path.write_text(yaml.safe_dump(gate))
    verified, estimated, ran = [], [], []
    monkeypatch.setattr(mc, "verify_config_models", lambda config, **kw: verified.append(config.generator_model) or [])

    def runner(config, store=None, estimate_only=False, reason=None):
        (estimated if estimate_only else ran).append(config.generator_model or "dev")
        return {"total_usd": 0.01} if estimate_only else {"run_id": f"r{len(ran)}", "model": config.generator_model}

    def faithfulness(run_id, **kw):
        return SimpleNamespace(run_id=run_id, usage={"cost_usd": 0.0}, cache_stats={"hits": 1, "misses": 0})

    # The comparison itself is P3-08's, tested there; here only what it is fed and how the
    # statuses combine: the primary passes, the fallback fails.
    monkeypatch.setattr(ce, "collect", lambda **kw: {"golden_run": kw["golden_row"]["run_id"]})
    monkeypatch.setattr(ce, "compare", lambda new, base, g: {"status": "PASS" if new["golden_run"] == "r2" else "FAIL"})
    monkeypatch.setattr(ce, "summary_markdown", lambda result, verdict: verdict["status"])
    monkeypatch.setattr(ce, "verify_baseline", lambda b, **kw: [])
    base = tmp_path / "b.json"
    base.write_text(json.dumps({"result": {}}))
    store = SimpleNamespace(get_run=lambda run_id: {"run_id": run_id})
    code, doc = ce.ci_eval(gate_path=str(gate_path), baseline_path=str(base), out_dir=str(tmp_path / "o"),
                           runner=runner, faithfulness=faithfulness, store=store)
    assert "x/fallback" in verified and "x/fallback" in estimated
    assert ran == ["dev", "openai/gpt-5-nano", "x/fallback"]
    assert doc["verdict"]["status"] == "PASS" and doc["fallbacks"][0]["verdict"]["status"] == "FAIL"
    assert code == ce.EXIT_FAIL
    assert "Fallback `x/fallback`" in (tmp_path / "o" / "ci_eval.md").read_text()


# --- the API: serves only gated generation, logs every request -------------------------

def test_the_api_serves_only_the_generation_the_gate_scored():
    pytest.importorskip("fastapi")  # the `api` extra; CI's unit tests do not install it
    import rag.api as api

    served = load_config_file(api.DEFAULT_CONFIG)
    assert api.check_gated_generation(served, load_config_file(GOLDEN)) == []
    ungated = served.with_(generator_fallback_models=("x/fallback",))
    assert api.check_gated_generation(ungated, load_config_file(GOLDEN)) == ["generator_fallback_models"]


class _Pipeline:
    """The P3-13 fake, with P3-14's usage and stage timings."""

    def __init__(self, fail_stage=None):
        self.config = load_config_file("configs/baseline_dense_tier2_v2.yaml")
        self.fail_stage = fail_stage

    def answer(self, question, question_id="ask"):
        from rag.citations import RenderedCitation
        from rag.generation.base import GeneratedAnswer
        from rag.pipeline import PipelineAnswer, StageError

        if self.fail_stage:
            raise StageError(self.fail_stage, TimeoutError("provider timed out after 4 attempts"))
        answer = GeneratedAnswer(text="1. Do it. [doc:aaaaaaaa]", cited_doc_ids=["aaaaaaaa"], model="openai/gpt-5-nano",
                                 prompt_ref="baseline_answer@v1", tokens_in=900, tokens_out=120, meta={"cached": False})
        cites = [RenderedCitation("aaaaaaaa", "Doing It", "https://support.wix.com/x", "c1", "The paragraph.", True, True)]
        return PipelineAnswer(question, answer, cites, ["aaaaaaaa"], 1.0, False,
                              {"embed": 180, "retrieve": 40, "assemble": 1, "generate": 2100, "total": 2321}, 0.0000921,
                              {"tokens_in": 900, "tokens_out": 120, "reasoning_tokens": 0, "embedding_tokens": 14,
                               "served_model": "openai/gpt-5-nano", "attempts": 1, "replayed": False})


@pytest.fixture()
def api_client(monkeypatch, tmp_path):
    fastapi = pytest.importorskip("fastapi")  # noqa: F841 — the `api` extra
    from fastapi.testclient import TestClient

    import rag.api as api

    log = tmp_path / "requests.jsonl"
    monkeypatch.setenv("RAG_API_LOG", str(log))
    monkeypatch.setattr(api.state, "pipeline", _Pipeline())
    monkeypatch.setattr(api.state, "replay", False)
    with TestClient(api.app) as client:
        yield client, api, log


def test_every_request_writes_one_structured_log_line(api_client, capsys):
    client, api, log = api_client
    question = "How do I connect my own domain?"
    r = client.post("/ask", json={"question": question})
    record = json.loads(log.read_text().strip())
    assert record["request_id"] == r.json()["meta"]["request_id"]
    assert record["status"] == 200 and record["refused"] is False
    assert set(record["stages_ms"]) >= {"embed", "retrieve", "generate"}
    assert record["tokens_in"] == 900 and record["tokens_out"] == 120 and record["embedding_tokens"] == 14
    assert record["cost_usd"] == 0.0000921 and record["config_hash"] == api.state.pipeline.config.config_hash
    assert record["served_model"] == "openai/gpt-5-nano"
    assert question not in log.read_text() and record["question_chars"] == len(question)
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == record  # stdout too


def test_a_failed_request_is_a_502_and_its_log_names_the_stage(api_client, monkeypatch):
    client, api, log = api_client
    monkeypatch.setattr(api.state, "pipeline", _Pipeline(fail_stage="generate"))
    r = client.post("/ask", json={"question": "anything"})
    assert r.status_code == 502
    record = json.loads(log.read_text().strip())
    assert record["status"] == 502 and record["stage"] == "generate"
    assert record["error"].startswith("TimeoutError") and record["request_id"] in r.json()["detail"]


def test_an_unwritable_log_never_fails_the_request(api_client, monkeypatch, tmp_path):
    client, api, log = api_client
    blocker = tmp_path / "file"
    blocker.write_text("")
    monkeypatch.setenv("RAG_API_LOG", str(blocker / "cannot" / "log.jsonl"))
    assert client.post("/ask", json={"question": "anything"}).status_code == 200


def test_the_pipeline_names_the_stage_that_failed():
    from rag.pipeline import Pipeline, StageError

    pipeline = object.__new__(Pipeline)

    class Broken:
        def retrieve(self, *a, **k):
            raise httpx.ReadTimeout("embedding timed out")

    pipeline.retriever = Broken()
    pipeline.config = load_config_file("configs/baseline_dense_tier2_v2.yaml")
    with pytest.raises(StageError) as err:
        pipeline.answer("q")
    assert err.value.stage == "retrieve" and isinstance(err.value.cause, httpx.ReadTimeout)


def test_query_embedding_is_timed_without_touching_rag_embedding():
    """The embed stage wraps the embedder instance; rag/embedding/ is CI's index-cache key (MIS-050)."""
    from rag.pipeline import Pipeline

    class Embedder:
        def embed_texts(self, texts, *, input_type):
            return [[0.0] for _ in texts]

        def embed_text(self, text, *, input_type):
            return self.embed_texts([text], input_type=input_type)[0]

    pipeline = object.__new__(Pipeline)
    pipeline.retriever = SimpleNamespace(embedder=Embedder())
    pipeline._time_query_embedding()
    pipeline.retriever.embedder.embed_text("q", input_type="query")
    assert pipeline.query_embed_ms > 0
    before = pipeline.query_embed_ms
    pipeline.retriever.embedder.embed_texts(["p"], input_type="passage")
    assert pipeline.query_embed_ms == before
    assert "query_ms" not in Path("rag/embedding/base.py").read_text()
