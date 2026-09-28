"""P3-02 — the startup check that every configured slug still resolves on OpenRouter.
No network: `fetch` is a stub standing in for GET /models/<id>/endpoints."""

from __future__ import annotations

import pytest

from rag.runner.config import historical_configs, load_config_file
from rag.runner.model_check import (
    ModelResolutionError,
    check_models,
    configured_models,
    verify_config_models,
)

SERVED = {
    "qwen/qwen3-embedding-8b": ["Nebius", "DeepInfra", "SiliconFlow"],
    "openai/gpt-5-nano": ["OpenAI", "Azure"],
    "deepseek/deepseek-v4.1-flash": ["Cerebras", "Groq", "DeepInfra"],
}
TIER2 = "configs/baseline_dense_tier2.yaml"
# The v1 control's gpt-oss judge is a refused pairing since DEC-073. The mechanism
# tests only need SOME cross-family judge; this is a stand-in, not a choice.
STAND_IN = {"judge_model": "deepseek/deepseek-v4.1-flash"}


def tier2():
    return load_config_file(TIER2, overrides=STAND_IN)


def fetch(served):
    calls = []

    def _fetch(model):
        calls.append(model)
        return served.get(model)

    _fetch.calls = calls
    return _fetch


def test_the_tier2_baseline_names_embedder_generator_judge_and_judge_embedder():
    refs = configured_models(tier2())
    assert [(r.role, r.model, r.providers) for r in refs] == [
        ("retriever embedder", "qwen/qwen3-embedding-8b", ("DeepInfra",)),
        ("generator", "openai/gpt-5-nano", ()),
        ("judge", "deepseek/deepseek-v4.1-flash", ("Cerebras", "Groq")),
        ("judge embedder", "qwen/qwen3-embedding-8b", ()),
    ]


def test_promoted_is_tier1_and_names_only_the_embedder():
    refs = configured_models(load_config_file("configs/promoted.yaml"))
    assert [r.model for r in refs] == ["qwen/qwen3-embedding-8b"]


def test_toy_configs_name_no_hosted_model():
    assert configured_models(load_config_file("configs/smoke_toy.yaml")) == []


def test_all_served_passes_and_each_slug_is_fetched_once():
    f = fetch(SERVED)
    results = verify_config_models(tier2(), fetch=f)
    assert all(r.ok for r in results)
    assert sorted(f.calls) == sorted(set(f.calls)), "a slug named twice is probed once"


def test_a_retired_slug_fails_fast_and_is_named():
    served = {k: v for k, v in SERVED.items() if k != "openai/gpt-5-nano"}
    with pytest.raises(ModelResolutionError, match=r"generator: 'openai/gpt-5-nano' does not resolve"):
        verify_config_models(tier2(), fetch=fetch(served))


def test_a_hard_pinned_provider_that_stopped_serving_fails():
    served = {**SERVED, "qwen/qwen3-embedding-8b": ["Nebius"]}
    with pytest.raises(ModelResolutionError, match=r"no longer served by \['DeepInfra'\]"):
        verify_config_models(load_config_file("configs/promoted.yaml"), fetch=fetch(served))


def test_the_judge_needs_only_one_provider_of_its_preference_order():
    served = {**SERVED, "deepseek/deepseek-v4.1-flash": ["Groq"]}
    config = tier2()
    results = check_models(configured_models(config), fetch=fetch(served))
    judge = next(r for r in results if r.ref.role == "judge")
    assert judge.ok and judge.missing_providers == ["Cerebras"]
    served["deepseek/deepseek-v4.1-flash"] = ["DeepInfra"]
    with pytest.raises(ModelResolutionError, match="judge"):
        verify_config_models(config, fetch=fetch(served))


CORPUS_READY = __import__("pathlib").Path("data/frozen/corpus.parquet").exists()


@pytest.mark.skipif(not CORPUS_READY, reason="frozen corpus not built")
def test_the_runner_stops_before_the_index_or_any_row(tmp_path, monkeypatch):
    from rag.runner import run as run_mod
    from rag.runner.store import ResultsStore

    def fail(config):
        raise ModelResolutionError("retired")

    monkeypatch.setattr(run_mod, "verify_config_models", fail)
    # The check sits after the free estimate and the cost gate, and before the first
    # thing that can spend: the retriever (query embeddings, a dense index build).
    monkeypatch.setattr(run_mod, "build_retriever", lambda *a, **k: pytest.fail("retriever built before the check"))
    with ResultsStore(tmp_path / "runs.sqlite") as store:
        with pytest.raises(ModelResolutionError):
            run_mod.run(load_config_file("configs/smoke_toy.yaml"), store=store)
        assert store.list_runs() == []


def test_the_phase3_baseline_record_matches_the_files_it_froze():
    """ci/phase3_baseline.yaml is a record of the latest baseline tag (v2, DEC-080). If
    promoted.yaml, the Tier 2 control, the prompt or the golden slice moves, this fails
    until a DEC entry and a new version of the record say so."""
    import hashlib
    from pathlib import Path

    import yaml

    from rag.dataset.golden import golden_hash, load_golden
    from rag.prompts import load_prompt

    record = yaml.safe_load(Path("ci/phase3_baseline.yaml").read_text())
    assert record["version"] == 2 and record["tag"] == "phase3-baseline-v2"
    for key in ("promoted", "tier2_control"):
        entry = record[key]
        assert hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest() == entry["file_sha256"], key
        assert load_config_file(entry["path"]).config_hash == entry["config_hash"], key
    assert load_config_file(record["promoted"]["path"]).identity_hash == record["promoted"]["identity_hash"]

    tier2 = load_config_file(record["tier2_control"]["path"])
    prompt_id, version = record["prompt"]["ref"].split("@")
    assert tier2.generator_prompt == record["prompt"]["ref"]
    assert load_prompt(prompt_id, version).content_hash == record["prompt"]["content_hash"]
    assert golden_hash(load_golden(record["data"]["golden"]["version"])) == record["data"]["golden"]["hash"]

    models = record["models"]
    assert tier2.retriever_params["embedding_model"] == models["embedder"]["slug"]
    assert tier2.retriever_params["embedding_provider"] == models["embedder"]["provider"]
    assert tier2.generator_model == models["generator"]["slug"]
    assert tier2.judge_model == models["judge"]["slug"]
    assert list(tier2.judge_provider_order) == models["judge"]["provider_order"]
    assert tier2.judge_allow_fallbacks is models["judge"]["allow_fallbacks"] is False
    assert tier2.judge_embedding_model == models["judge_embedder"]["slug"]
    assert all(m["verified_on_openrouter"] for m in models.values())


def test_the_v1_control_is_refused_but_still_readable_as_history():
    """The v1 Tier 2 control is kept byte-identical for the `phase3-baseline` tag."""
    import hashlib
    from pathlib import Path

    path = "configs/baseline_dense_tier2.yaml"
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == \
        "4054bc08063d36797018385fb24dd20d67beb201845718afc15685b89f1fa04a"
    with pytest.raises(ValueError, match="'openai' family"):
        load_config_file(path)
    with historical_configs():
        assert load_config_file(path).config_hash == "86cd401cbdac80c7"


def test_a_judge_pinned_without_fallbacks_is_a_hard_pin_in_the_model_check():
    config = load_config_file("configs/baseline_dense_tier2_v2.yaml")
    judge = next(r for r in configured_models(config) if r.role == "judge")
    assert judge.pinned and judge.providers == ("DeepInfra",)
    served = {**SERVED, "deepseek/deepseek-v4.1-flash": ["Groq"]}
    with pytest.raises(ModelResolutionError, match="no longer served by \\['DeepInfra'\\]"):
        verify_config_models(config, fetch=fetch(served))


def test_allow_fallbacks_true_is_absent_from_every_hash():
    """MIS-019: the new field at its Phase 0-2 value moves no existing config_hash."""
    from rag.runner.config import RunConfig

    assert load_config_file("configs/promoted.yaml").config_hash == "7c99bc8e9a88e878"
    base = RunConfig(name="x")
    assert base.with_(judge_allow_fallbacks=True).config_hash == base.config_hash
