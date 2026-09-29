"""P3-08 — `rag ci-eval`: comparison rules, baseline file, orchestration. No model calls."""

from __future__ import annotations

import copy
import json

import pytest

from rag.runner.ci_eval import (
    EXIT_FAIL,
    EXIT_NEEDS_APPROVAL,
    EXIT_PASS,
    CIError,
    compare,
    load_gate,
    summary_markdown,
    update_baseline,
)

GATE = load_gate("ci/gate.yaml")
FAMILY = GATE["noise_floor_family"]


def _result(dev_hits=None, golden_hits=None, judged=None, answers=None, family=FAMILY):
    dev_hits = dev_hits if dev_hits is not None else {f"d{i:03d}": 1.0 if i < 150 else 0.0 for i in range(200)}
    golden_hits = golden_hits if golden_hits is not None else {f"g{i:02d}": (1.0 if i < 40 else 0.0) if i < 80 else None
                                                               for i in range(95)}
    answers = answers if answers is not None else {
        f"g{i:02d}": {"faithfulness": 0.85, "unsupported": i % 3 == 0, "refused": i >= 90, "unanswerable": i >= 80,
                      "citation_integrity": True, "empty": False, "judge_failed": False,
                      "citation_valid": True, "unretrieved_real_citations": []} for i in range(95)}
    judged = judged or {"mean_faithfulness": 0.85, "unsupported_answer_rate": 0.62, "false_answer_rate": 0.33,
                        "refusal_rate": 0.08, "citation_integrity": 0.98, "citation_validity": 0.95,
                        "cites_unretrieved_article": 0, "judge_failures": 0, "n_judged": 85}
    return {"runs": {"dev": "rd", "golden": "rg", "faithfulness": "rf"}, "git_sha": "abcdef1", "git_dirty": 0,
            "provenance": {"corpus_hash": "c", "dev_split_hash": "ds", "golden_split_hash": "gs", "judge": "j",
                           "judge_prompt_version": "v", "noise_floor_family": family,
                           "dev_config_hash": "hd", "golden_config_hash": "hg"},
            "metrics": {"judged": judged, "retrieval": {}},
            "per_question": {"dev": dev_hits, "golden": golden_hits, "answers": answers},
            "cost_usd": {"total": 0.0}, "call_cache": {}}


BASELINE = {"result": _result()}


def _rule(verdict, section, metric, run=None):
    return next(r for r in verdict[section] if r["metric"] == metric and (run is None or r.get("run") == run))


def test_an_unchanged_run_passes_with_zero_deltas():
    v = compare(_result(), BASELINE, GATE)
    assert v["status"] == "PASS" and v["draft"] is False and v["hard_fails"] == []
    assert _rule(v, "retrieval", "strict_recall@5", "dev")["delta"] == 0.0
    assert all(r["verdict"] in ("pass", "report") for r in v["judged"])
    assert v["changed_answers"] == []


def test_a_significant_retrieval_drop_fails_and_lists_the_newly_failed_ids():
    hits = dict(BASELINE["result"]["per_question"]["dev"])
    for q in list(hits)[:6]:  # 6 losses, 0 gains: exact McNemar p = 0.031 < 0.05
        hits[q] = 0.0
    r = _rule(compare(_result(dev_hits=hits), BASELINE, GATE), "retrieval", "strict_recall@5", "dev")
    assert r["verdict"] == "FAIL" and r["delta"] == -0.03 and len(r["lost"]) == 6


def test_a_retrieval_drop_inside_the_floor_passes_but_still_lists_ids():
    hits = dict(BASELINE["result"]["per_question"]["dev"])
    for q in list(hits)[:5]:
        hits[q] = 0.0
    v = compare(_result(dev_hits=hits), BASELINE, GATE)
    r = _rule(v, "retrieval", "strict_recall@5", "dev")
    assert r["verdict"] == "pass" and len(r["lost"]) == 5
    assert "Newly failed" in summary_markdown(_result(dev_hits=hits), v)


@pytest.mark.parametrize("value, verdict", [(0.83, "pass"), (0.82, "FAIL"), (0.90, "pass")])
def test_judged_metrics_fail_only_beyond_the_measured_mdd(value, verdict):
    judged = {**BASELINE["result"]["metrics"]["judged"], "mean_faithfulness": value}
    r = _rule(compare(_result(judged=judged), BASELINE, GATE), "judged", "mean_faithfulness")
    assert r["mdd"] == 0.026 and r["verdict"] == verdict


def test_a_changed_judge_cannot_be_gated_and_fails_closed():
    v = compare(_result(family=None), BASELINE, GATE)
    r = _rule(v, "judged", "mean_faithfulness")
    assert r["verdict"] == "FAIL" and "fail closed" in r["note"]
    assert v["status"] == "FAIL"


def test_report_only_metrics_never_fail():
    judged = {**BASELINE["result"]["metrics"]["judged"], "citation_integrity": 0.5}
    r = _rule(compare(_result(judged=judged), BASELINE, GATE), "judged", "citation_integrity")
    assert r["verdict"] == "report" and r["note"] == "worse beyond the MDD"


def test_hard_fails():
    answers = copy.deepcopy(BASELINE["result"]["per_question"]["answers"])
    answers["g00"]["empty"] = True
    answers["g01"]["judge_failed"] = True
    new = _result(answers=answers)
    new["provenance"]["judge"] = "another judge"
    del new["per_question"]["dev"]["d000"]
    v = compare(new, BASELINE, GATE)
    rules = {h["rule"] for h in v["hard_fails"]}
    assert rules == {"empty_answer", "provenance_changed", "question_set_changed",
                     "schema_invalid"}, "a missing dev question also breaks the declared counts"
    assert [e["rule"] for e in v["errors"]] == ["judge_failure"] and v["status"] == "ERROR", \
        "a judge that could not score is infrastructure, not quality (P3-10)"


def test_the_baseline_needs_an_existing_decision_and_a_clean_run(tmp_path):
    src = tmp_path / "ci_eval.json"
    src.write_text(json.dumps({"result": _result(), "verdict": None}))
    decisions = tmp_path / "DECISIONS.md"
    decisions.write_text("## DEC-900 — a decision\n")
    with pytest.raises(CIError, match="DEC id"):
        update_baseline(source=str(src), reason="because", baseline_path=str(tmp_path / "b.json"),
                        decisions_path=str(decisions))
    with pytest.raises(CIError, match="not an entry"):
        update_baseline(source=str(src), reason="DEC-901", baseline_path=str(tmp_path / "b.json"),
                        decisions_path=str(decisions))
    b = update_baseline(source=str(src), reason="DEC-900", baseline_path=str(tmp_path / "b.json"),
                        decisions_path=str(decisions))
    assert b["reason"] == "DEC-900" and json.loads((tmp_path / "b.json").read_text())["result"]["runs"]["dev"] == "rd"
    answers = copy.deepcopy(_result()["per_question"]["answers"]); answers["g00"]["empty"] = True
    src.write_text(json.dumps({"result": _result(answers=answers), "verdict": None}))
    with pytest.raises(CIError, match="cannot become the baseline"):
        update_baseline(source=str(src), reason="DEC-900", baseline_path=str(tmp_path / "b.json"),
                        decisions_path=str(decisions))


def test_orchestration_budget_stop_and_missing_baseline(tmp_path, monkeypatch):
    """The whole command with fake model calls: over budget -> exit 3 before any spend;
    no baseline -> an error unless asked to record one."""
    import rag.runner.model_check as mc
    from rag.runner.ci_eval import ci_eval

    monkeypatch.setattr(mc, "verify_config_models", lambda config, **kw: [])
    calls = []

    def runner(config, store=None, estimate_only=False, reason=None):
        calls.append((config.split, estimate_only))
        return {"total_usd": 0.9}

    code, doc = ci_eval(gate_path="ci/gate.yaml", baseline_path=str(tmp_path / "none.json"),
                        out_dir=str(tmp_path / "out"), allow_no_baseline=True, runner=runner, store=object())
    assert code == EXIT_NEEDS_APPROVAL and doc["status"] == "NEEDS_APPROVAL"
    assert all(estimate for _, estimate in calls), "nothing was run for real"
    with pytest.raises(CIError, match="no baseline"):
        ci_eval(gate_path="ci/gate.yaml", baseline_path=str(tmp_path / "none.json"), out_dir=str(tmp_path / "o"),
                runner=runner, store=object())
    assert (EXIT_PASS, EXIT_FAIL) == (0, 1)


# --- the opt-in call cache (DEC-084) ---------------------------------------------------

def _fake_embedder():
    from rag.embedding.base import Embedder, EmbedderConfig

    class Fake(Embedder):
        name = "fake"

        def __init__(self, config):
            super().__init__(config)
            self.calls = []

        def _embed(self, texts):
            self.calls.append(list(texts))
            return [[float(len(t))] for t in texts]

    return Fake(EmbedderConfig(model="qwen/qwen3-embedding-8b"))


def test_query_embeddings_replay_only_inside_ci_eval_and_passages_never_cache(tmp_path):
    from rag.call_cache import CallCache, call_cache

    emb = _fake_embedder()
    emb.embed_texts(["q"], input_type="query")
    emb.embed_texts(["q"], input_type="query")
    assert len(emb.calls) == 2, "no cache outside ci-eval: experiments always call"
    cache = CallCache(tmp_path / "c.sqlite")
    with call_cache(cache):
        a = emb.embed_texts(["q", "r"], input_type="query")
        b = emb.embed_texts(["r", "q"], input_type="query")
        emb.embed_texts(["p"], input_type="passage")
        emb.embed_texts(["p"], input_type="passage")
    assert b == [a[1], a[0]]
    assert len(emb.calls) == 5, "one query batch for the two misses, then two uncached passage calls"
    snap = cache.snapshot()
    assert snap["embedding_hits"] == 2 and snap["embedding_misses"] == 2


def test_answers_replay_inside_ci_eval_and_a_changed_prompt_misses(tmp_path):
    from rag.call_cache import CallCache, call_cache
    from rag.generation.base import Completion, Generator, GeneratorConfig

    doc = "ab" * 32  # the citation parser accepts real 64-hex document ids only

    class Fake(Generator):
        name = "fake"
        n = 0

        def _complete(self, prompt):
            Fake.n += 1
            return Completion(text=f"answer {Fake.n} [doc:{doc}]", tokens_in=1, tokens_out=1, reasoning_tokens=0,
                              finish_reason="stop")

    gen = Fake(GeneratorConfig(model="openai/gpt-5-nano", prompt_id="baseline_answer", prompt_version="v1"))
    cache = CallCache(tmp_path / "c.sqlite")
    with call_cache(cache):
        first = gen.generate("q?", "ctx")
        again = gen.generate("q?", "ctx")
        other = gen.generate("q?", "different context")
    assert first.text == again.text == f"answer 1 [doc:{doc}]" and other.text == f"answer 2 [doc:{doc}]"
    assert again.cited_doc_ids == [doc]
    assert first.meta["cached"] is False and again.meta["cached"] is True, "a replay is marked, so it is not billed"
    snap = cache.snapshot()
    assert snap["completion_hits"] == 1 and snap["completion_misses"] == 2


# --- P3-09: the declared rules (DEC-087) -----------------------------------------------

def test_the_declared_gate_is_version_1_with_every_story_rule():
    assert GATE["status"] == "declared" and GATE["version"] == 2 and GATE["baseline_updates"] == "manual"
    gating = {r["metric"] for r in GATE["judged"] if r["gating"]}
    assert gating == {"mean_faithfulness", "unsupported_answer_rate", "false_answer_rate", "citation_validity"}
    assert {"cites_unretrieved_article", "schema_invalid"} <= set(GATE["hard_fails"])
    assert GATE["alpha"] == 0.05


def test_citing_a_real_article_that_was_not_retrieved_is_a_hard_fail():
    answers = copy.deepcopy(BASELINE["result"]["per_question"]["answers"])
    answers["g05"]["unretrieved_real_citations"] = ["a" * 64]
    v = compare(_result(answers=answers), BASELINE, GATE)
    hard = {h["rule"]: h for h in v["hard_fails"]}
    assert v["status"] == "FAIL" and hard["cites_unretrieved_article"]["question_ids"] == {"g05": ["a" * 64]}


@pytest.mark.parametrize("value, verdict", [(0.92, "pass"), (0.90, "FAIL")])
def test_citation_validity_is_gated_against_its_four_run_mdd(value, verdict):
    judged = {**BASELINE["result"]["metrics"]["judged"], "citation_validity": value}
    r = _rule(compare(_result(judged=judged), BASELINE, GATE), "judged", "citation_validity")
    assert r["mdd"] == 0.041 and r["verdict"] == verdict


def test_a_mistyped_or_out_of_range_result_is_schema_invalid():
    from rag.runner.ci_eval import validate_result

    answers = copy.deepcopy(BASELINE["result"]["per_question"]["answers"])
    answers["g00"]["faithfulness"] = 1.7
    answers["g01"]["refused"] = "no"
    errors = validate_result(_result(answers=answers), GATE)
    assert any("outside [0, 1]" in e for e in errors) and any("g01" in e for e in errors)
    assert validate_result(_result(), GATE) == []


def test_a_gating_metric_missing_from_the_baseline_fails_closed():
    base = copy.deepcopy(BASELINE)
    del base["result"]["metrics"]["judged"]["citation_validity"]
    r = _rule(compare(_result(), base, GATE), "judged", "citation_validity")
    assert r["verdict"] == "FAIL" and "re-baseline" in r["note"]


def test_a_provider_outage_exits_as_error_never_as_a_quality_failure(monkeypatch):
    """P3-10: infrastructure failure is distinct from quality failure."""
    import httpx
    from typer.testing import CliRunner

    import rag.runner.ci_eval as ce
    from rag.cli import app

    def outage(**kw):
        raise httpx.ConnectError("provider unreachable after retries")

    monkeypatch.setattr(ce, "ci_eval", outage)
    result = CliRunner().invoke(app, ["ci-eval"])
    assert result.exit_code == ce.EXIT_ERROR == 2
    assert "not a quality failure" in result.output


def test_the_gate_script_skips_docs_only_changes_and_blocks_without_a_key(tmp_path):
    """ci/run_gate.sh: no pipeline change -> SKIPPED (0); a pipeline change without the key
    -> NOT VERIFIED (1). Run against HEAD so no model is called."""
    import os
    import subprocess

    import sys
    from pathlib import Path

    env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
    env["GITHUB_STEP_SUMMARY"] = str(tmp_path / "summary.md")
    env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"  # `rag`, as CI installs it
    skipped = subprocess.run(["ci/run_gate.sh", "HEAD"], env=env, capture_output=True, text=True)
    assert skipped.returncode == 0 and "eval skipped: no pipeline change" in skipped.stdout
    blocked = subprocess.run(["ci/run_gate.sh", "HEAD"], env={**env, "FORCE_EVAL": "1"}, capture_output=True, text=True)
    assert blocked.returncode == 1 and "NOT VERIFIED" in blocked.stdout
    assert "NOT VERIFIED" in (tmp_path / "summary.md").read_text()


# --- P3-11: integrity, ratchet, drift (DEC-090) --------------------------------------

def _stamped(result, reason="DEC-900"):
    from rag.runner.ci_eval import result_digest

    return {"reason": reason, "result": result, "result_sha256": result_digest(result)}


def _decisions(tmp_path):
    p = tmp_path / "DECISIONS.md"
    p.write_text("## DEC-900 — a decision\n")
    return str(p)


def test_a_hand_edited_or_unstamped_baseline_is_rejected(tmp_path):
    from rag.runner.ci_eval import verify_baseline

    d = _decisions(tmp_path)
    good = _stamped(_result())
    assert verify_baseline(good, decisions_path=d) == []
    edited = copy.deepcopy(good)
    edited["result"]["metrics"]["judged"]["mean_faithfulness"] = 0.50  # lowering the bar by hand
    assert any("edited outside" in p for p in verify_baseline(edited, decisions_path=d))
    assert any("missing `result_sha256`" in p
               for p in verify_baseline({"reason": "DEC-900", "result": {}}, decisions_path=d))
    assert any("not an entry" in p for p in verify_baseline(_stamped(_result(), "DEC-901"), decisions_path=d))


def test_the_committed_baseline_is_stamped_and_verifies():
    from rag.runner.ci_eval import verify_baseline

    assert verify_baseline(json.loads(open("ci/baseline.json").read())) == []


def test_the_ratchet_rejects_new_results_together_with_a_pipeline_change(tmp_path):
    from rag.runner.ci_eval import ratchet_check

    d = _decisions(tmp_path)
    base = _stamped(_result())
    moved = _stamped(_result(judged={**_result()["metrics"]["judged"], "mean_faithfulness": 0.70}))
    same_results = {**_stamped(_result()), "updated": "later"}

    ok, why = ratchet_check(["rag/cli.py"], base, base, decisions_path=d)
    assert ok and why == "baseline unchanged"
    ok, why = ratchet_check(["ci/baseline.json", "prompts/baseline_answer.yaml"], moved, base, decisions_path=d)
    assert not ok and "ratchet" in why and "prompts/baseline_answer.yaml" in why
    ok, why = ratchet_check(["ci/baseline.json", "rag/cli.py"], same_results, base, decisions_path=d)
    assert ok and "results did not" in why, "a metadata-only change moves no bar"
    ok, why = ratchet_check(["ci/baseline.json", "docs/DECISIONS.md"], moved, base, decisions_path=d)
    assert ok and "baseline-only" in why
    ok, why = ratchet_check(["ci/baseline.json"], {**moved, "result_sha256": "sha256:0"}, base, decisions_path=d)
    assert not ok and "cannot be trusted" in why
    ok, _ = ratchet_check(["ci/baseline.json"], None, base, decisions_path=d)
    assert not ok


def test_drift_mode_bypasses_every_cache(tmp_path, monkeypatch):
    """`--no-cache`: no call cache around the runs; the gate itself still uses it."""
    import rag.call_cache as cc
    import rag.runner.model_check as mc
    from rag.runner.ci_eval import ci_eval

    monkeypatch.setattr(mc, "verify_config_models", lambda config, **kw: [])
    seen = []

    def runner(config, store=None, estimate_only=False, reason=None):
        if estimate_only:
            return {"total_usd": 0.01}
        seen.append(cc.active() is not None)
        raise RuntimeError("stop after recording")

    base = tmp_path / "b.json"
    base.write_text(json.dumps(_stamped(_result())))
    for no_cache in (True, False):
        with pytest.raises(RuntimeError):
            ci_eval(gate_path="ci/gate.yaml", baseline_path=str(base), out_dir=str(tmp_path / "o"),
                    no_cache=no_cache, decisions_path=_decisions(tmp_path), runner=runner, store=object())
    assert seen == [False, True]


def test_a_broken_ratchet_check_is_an_error_not_a_rejection(tmp_path):
    """If `rag` itself cannot run, the gate must not report a policy REJECTED."""
    import os
    import subprocess

    env = {"PATH": "/usr/bin:/bin", "GITHUB_STEP_SUMMARY": str(tmp_path / "s.md"), "FORCE_EVAL": "1"}
    r = subprocess.run(["ci/run_gate.sh", "HEAD"], env=env, capture_output=True, text=True)
    assert r.returncode == 2 and "ERROR" in r.stdout and "REJECTED" not in r.stdout
