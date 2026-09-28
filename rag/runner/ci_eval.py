"""`rag ci-eval` — P3-08: the whole quality gate as one command, identical locally and in CI.

1. Tier 1 retrieval on all of `dev` (`configs/promoted.yaml`).
2. Tier 2 generation on the golden slice (`golden_v1`, 95 questions, unanswerables included).
3. `rag faithfulness` on those answers (P3-05) with the production judge.
4. Comparison to `ci/baseline.json` on identical question ids: the exact paired test at
   the gate's α for retrieval, the measured MDD (P3-07) for judged metrics.

Steps 1–3 run with the opt-in call cache on (DEC-084): an unchanged pipeline replays
query embeddings, answers and judgments, so it costs almost nothing and compares equal to
its baseline. The baseline carries per-question outcomes, so no results store is needed
to compare — a CI machine has none.

Exit codes: 0 pass · 1 gated quality failure · 2 error (infrastructure, configuration or
an invalid comparison — never reported as a quality failure, P3-10) · 3 needs approval
(the estimate exceeds the CI budget).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

EXIT_PASS, EXIT_FAIL, EXIT_ERROR, EXIT_NEEDS_APPROVAL = 0, 1, 2, 3
SCHEMA_VERSION = 1


class CIError(RuntimeError):
    """Not a quality failure: infra, configuration or an invalid comparison (exit 2)."""


def load_gate(path: str | Path) -> dict[str, Any]:
    gate = yaml.safe_load(Path(path).read_text())
    for key in ("configs", "alpha", "noise_floor_family", "retrieval", "judged", "hard_fails", "ci_budget_usd"):
        if key not in gate:
            raise CIError(f"{path}: missing `{key}`")
    return gate


# --- collecting a run's outcomes -----------------------------------------------------

def _per_question_recall(store: Any, run_id: str) -> dict[str, float | None]:
    return {q: json.loads(r["metrics_json"]).get("strict_recall@5") for q, r in store.get_questions(run_id).items()}


def collect(*, dev_row: dict[str, Any], golden_row: dict[str, Any], faith_row: dict[str, Any],
            store: Any, gate: dict[str, Any], cost: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    """Everything the comparison needs, from the results store, in a store-free document."""
    from rag.eval.noise_floor import family_for_run

    answers = {}
    for qid, r in store.get_questions(faith_row["run_id"]).items():
        m = json.loads(r["metrics_json"])
        answers[qid] = {
            "faithfulness": m["faithfulness"], "unsupported": m["unsupported"], "refused": m["refused"],
            "unanswerable": m["unanswerable"], "citation_integrity": m["citation_integrity"],
            "empty": not (r["generated_answer"] or "").strip(),
            "judge_failed": (not m["refused"]) and m["faithfulness"] is None,
            "citation_valid": m.get("citation_valid"),
            "unretrieved_real_citations": m.get("unretrieved_real_citations"),
        }
    faith_metrics = json.loads(faith_row["metrics_json"])["by_stratum"]
    family, _ = family_for_run(faith_row)
    faith_config = json.loads(faith_row["config_json"])
    return {
        "schema_version": SCHEMA_VERSION,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": golden_row["git_sha"], "git_dirty": golden_row["git_dirty"],
        "gate": {"status": gate["status"], "version": gate["version"]},
        "runs": {"dev": dev_row["run_id"], "golden": golden_row["run_id"], "faithfulness": faith_row["run_id"]},
        "provenance": {
            "corpus_hash": golden_row["corpus_hash"],
            "dev_split_hash": dev_row["split_hash"], "golden_split_hash": golden_row["split_hash"],
            "dev_config_hash": dev_row["config_hash"], "golden_config_hash": golden_row["config_hash"],
            "generator_model": golden_row["generator_model"], "prompt_versions": golden_row["prompt_versions"],
            "judge": faith_config["judge"], "judge_prompt_version": faith_config["judge_prompt_version"],
            "noise_floor_family": family,
        },
        "metrics": {
            "retrieval": {
                "dev": {"strict_recall@5": json.loads(dev_row["metrics_json"])["strict_recall@5"]},
                "golden": {"strict_recall@5": json.loads(golden_row["metrics_json"])["strict_recall@5"]},
            },
            "judged": {k: faith_metrics["all"].get(k) for k in
                       ("mean_faithfulness", "unsupported_answer_rate", "false_answer_rate", "refusal_rate",
                        "citation_integrity", "citation_validity", "cites_unretrieved_article",
                        "garbled_citation_answers", "malformed_citation_answers", "judge_failures", "n_judged")},
            "judged_by_stratum": faith_metrics,
        },
        "per_question": {
            "dev": _per_question_recall(store, dev_row["run_id"]),
            "golden": _per_question_recall(store, golden_row["run_id"]),
            "answers": answers,
        },
        "cost_usd": cost, "call_cache": cache,
    }


# --- the result's own shape (P3-09 "schema-invalid output") ---------------------------

ANSWER_KEYS = {"faithfulness": (float, int, type(None)), "unsupported": (bool, type(None)), "refused": (bool,),
               "unanswerable": (bool,), "citation_integrity": (bool,), "empty": (bool,), "judge_failed": (bool,),
               "citation_valid": (bool,), "unretrieved_real_citations": (list,)}


def validate_result(result: dict[str, Any], gate: dict[str, Any]) -> list[str]:
    """Everything the comparison relies on is present and well-typed, and the question
    counts are the gate's. A result that fails this cannot be compared (hard fail)."""
    errors = []
    for key in ("runs", "provenance", "metrics", "per_question"):
        if key not in result:
            errors.append(f"missing `{key}`")
    if errors:
        return errors
    expected = gate.get("expected_questions", {})
    for part, n in expected.items():
        got = len(result["per_question"].get(part, {}))
        if got != n:
            errors.append(f"per_question.{part}: {got} questions, gate expects {n}")
    for qid, a in result["per_question"].get("answers", {}).items():
        for key, types in ANSWER_KEYS.items():
            if key not in a or not isinstance(a[key], types):
                errors.append(f"answer {qid}: `{key}` missing or {type(a.get(key)).__name__}")
                break
        if a.get("faithfulness") is not None and not 0.0 <= a["faithfulness"] <= 1.0:
            errors.append(f"answer {qid}: faithfulness {a['faithfulness']} outside [0, 1]")
    return errors[:20]


# --- comparing to the baseline ---------------------------------------------------------

def _retrieval_rule(rule: dict[str, Any], new: dict[str, Any], base: dict[str, Any], alpha: float) -> dict[str, Any]:
    from rag.runner.compare import mcnemar_exact_p

    run = rule["run"]
    a_map, b_map = base["per_question"][run], new["per_question"][run]
    ids = sorted(q for q in a_map if a_map[q] is not None and b_map.get(q) is not None)
    a = np.array([a_map[q] for q in ids]); b = np.array([b_map[q] for q in ids])
    lost = [q for q in ids if a_map[q] == 1 and b_map[q] == 0]
    gained = [q for q in ids if a_map[q] == 0 and b_map[q] == 1]
    p = mcnemar_exact_p(len(lost), len(gained))
    delta = round(float(b.mean() - a.mean()), 4) if ids else 0.0
    failed = bool(rule["gating"] and delta < 0 and p < alpha)
    return {"metric": rule["metric"], "run": run, "gating": rule["gating"], "n": len(ids),
            "baseline": round(float(a.mean()), 4) if ids else None, "value": round(float(b.mean()), 4) if ids else None,
            "delta": delta, "mcnemar_exact_p": round(p, 4), "alpha": alpha,
            "lost": lost, "gained": gained,
            "verdict": "FAIL" if failed else ("pass" if rule["gating"] else "report")}


def _judged_rule(rule: dict[str, Any], new: dict[str, Any], base: dict[str, Any], floors: dict[str, float] | None) -> dict[str, Any]:
    metric = rule["metric"]
    b, v = base["metrics"]["judged"].get(metric), new["metrics"]["judged"].get(metric)
    out = {"metric": metric, "gating": rule["gating"], "better": rule["better"], "baseline": b, "value": v}
    if b is None or v is None:
        if rule["gating"] and b is None and v is not None:
            # Fail closed (DEC-087): a gating metric the baseline does not have cannot be
            # gated, and passing it silently would be a gate that looks on but is off.
            return {**out, "delta": None, "mdd": None, "verdict": "FAIL",
                    "note": "the baseline lacks this gating metric — re-baseline with a DEC entry"}
        return {**out, "delta": None, "mdd": None, "verdict": "n/a", "note": "not applicable on one side"}
    delta = round(v - b, 4)
    worse = -delta if rule["better"] == "higher" else delta
    mdd = (floors or {}).get(metric)
    if mdd is None:
        verdict = "FAIL" if rule["gating"] else "report"
        return {**out, "delta": delta, "mdd": None, "verdict": verdict,
                "note": "no MDD measured for this judge/generator/prompt — cannot be gated (fail closed)"}
    note = "within noise" if abs(delta) <= mdd else ("worse beyond the MDD" if worse > mdd else "better beyond the MDD")
    failed = rule["gating"] and worse > mdd
    return {**out, "delta": delta, "mdd": mdd, "note": note,
            "verdict": "FAIL" if failed else ("pass" if rule["gating"] else "report")}


def _changed_answers(new: dict[str, Any], base: dict[str, Any]) -> list[dict[str, Any]]:
    changed = []
    for qid, b in sorted(base["per_question"]["answers"].items()):
        n = new["per_question"]["answers"].get(qid)
        if n is None:
            continue
        flips = [k for k in ("refused", "unsupported", "citation_integrity", "citation_valid") if b.get(k) != n.get(k)]
        if flips or b.get("faithfulness") != n.get("faithfulness"):
            changed.append({"question_id": qid, "flipped": flips,
                            "faithfulness": [b.get("faithfulness"), n.get("faithfulness")]})
    return changed


def compare(new: dict[str, Any], baseline: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    from rag.eval.noise_floor import FLOOR_FAMILIES

    base = baseline["result"]
    hard = []
    if "schema_invalid" in gate["hard_fails"]:
        errors = validate_result(new, gate)
        if errors:
            hard.append({"rule": "schema_invalid", "errors": errors})
    if "cites_unretrieved_article" in gate["hard_fails"]:
        offenders = {q: a["unretrieved_real_citations"] for q, a in new["per_question"]["answers"].items()
                     if a.get("unretrieved_real_citations")}
        if offenders:
            hard.append({"rule": "cites_unretrieved_article", "question_ids": offenders})
    if "empty_answer" in gate["hard_fails"]:
        empty = [q for q, a in new["per_question"]["answers"].items() if a["empty"]]
        if empty:
            hard.append({"rule": "empty_answer", "question_ids": empty})
    # P3-10 (DEC-088): a judge that could not score an answer after its retries is an
    # infrastructure failure, never a quality one. It is an ERROR (exit 2, "not verified").
    errors = []
    if "judge_failure" in gate.get("errors", []):
        failed = [q for q, a in new["per_question"]["answers"].items() if a["judge_failed"]]
        if failed:
            errors.append({"rule": "judge_failure", "question_ids": failed})
    if "question_set_changed" in gate["hard_fails"]:
        for part in ("dev", "golden", "answers"):
            if set(new["per_question"][part]) != set(base["per_question"][part]):
                hard.append({"rule": "question_set_changed", "part": part})
    if "provenance_changed" in gate["hard_fails"]:
        keys = ("corpus_hash", "dev_split_hash", "golden_split_hash", "judge", "judge_prompt_version")
        diff = {k: [base["provenance"].get(k), new["provenance"].get(k)] for k in keys
                if base["provenance"].get(k) != new["provenance"].get(k)}
        if diff:
            hard.append({"rule": "provenance_changed", "fields": diff})

    family = gate["noise_floor_family"]
    floors = FLOOR_FAMILIES[family]["floors"] if new["provenance"]["noise_floor_family"] == family else None
    retrieval = [_retrieval_rule(r, new, base, gate["alpha"]) for r in gate["retrieval"]]
    judged = [_judged_rule(r, new, base, floors) for r in gate["judged"]]
    failed = bool(hard) or any(r["verdict"] == "FAIL" for r in retrieval + judged)
    status = "ERROR" if errors else ("FAIL" if failed else "PASS")
    return {"status": status, "draft": gate["status"] != "declared", "errors": errors,
            "baseline_runs": base["runs"], "hard_fails": hard, "retrieval": retrieval, "judged": judged,
            "noise_floor_family": family if floors else None,
            "changed_answers": _changed_answers(new, base)}


# --- the summary ------------------------------------------------------------------------

def summary_markdown(result: dict[str, Any], verdict: dict[str, Any] | None) -> str:
    lines = []
    if verdict is None:
        lines += ["## RAG quality gate — NO BASELINE", "",
                  "No `ci/baseline.json` to compare against. Metrics are recorded below; "
                  "create a baseline with `rag ci-baseline update --reason <DEC-id>`.", ""]
    else:
        badge = {"PASS": "✅ PASS", "FAIL": "❌ FAIL",
                 "ERROR": "⚠️ ERROR — infrastructure, not a quality result (not verified)"}[verdict["status"]]
        lines += [f"## RAG quality gate — {badge}" + (" (DRAFT rules, P3-09 pending)" if verdict["draft"] else ""), ""]
        for e in verdict.get("errors", []):
            lines.append(f"- **ERROR `{e['rule']}`** — {json.dumps({k: v for k, v in e.items() if k != 'rule'})[:300]}")
        for h in verdict["hard_fails"]:
            lines.append(f"- **HARD FAIL `{h['rule']}`** — {json.dumps({k: v for k, v in h.items() if k != 'rule'})[:300]}")
        lines += ["", "| Metric | Gating | Baseline | This run | Δ | Threshold | Verdict |", "|---|---|---|---|---|---|---|"]
        for r in verdict["retrieval"]:
            lines.append(f"| {r['metric']} ({r['run']}) | {'yes' if r['gating'] else 'report'} | {r['baseline']} | "
                         f"{r['value']} | {r['delta']:+.4f} | paired p={r['mcnemar_exact_p']} (α {r['alpha']}) | "
                         f"**{r['verdict']}** |")
        for r in verdict["judged"]:
            delta = "—" if r["delta"] is None else f"{r['delta']:+.4f}"
            lines.append(f"| {r['metric']} | {'yes' if r['gating'] else 'report'} | {r['baseline']} | {r['value']} | "
                         f"{delta} | MDD {r['mdd']} | **{r['verdict']}** {r.get('note', '')} |")
        dev = next((r for r in verdict["retrieval"] if r["run"] == "dev"), None)
        if dev:
            lines += ["", f"**Questions that changed outcome (recall@5, dev):** {len(dev['lost'])} lost, "
                          f"{len(dev['gained'])} gained."]
            if dev["lost"]:
                lines.append("Newly failed: " + ", ".join(f"`{q}`" for q in dev["lost"][:30]))
        lines.append(f"**Golden answers whose judged outcome changed:** {len(verdict['changed_answers'])}")
    c = result.get("call_cache", {})
    lines += ["", f"Runs: dev `{result['runs']['dev']}`, golden `{result['runs']['golden']}`, "
                  f"faithfulness `{result['runs']['faithfulness']}` · git `{result['git_sha'][:7]}`",
              f"Cost ${result['cost_usd'].get('total', 0):.4f} · cache hit rates: embeddings "
              f"{c.get('embedding_hit_rate')}, answers {c.get('completion_hit_rate')}, judge {c.get('judge_hit_rate')}"]
    return "\n".join(lines)


# --- orchestration ----------------------------------------------------------------------

def ci_eval(*, gate_path: str, baseline_path: str, out_dir: str, approve_cost: str = "",
            estimate_only: bool = False, allow_no_baseline: bool = False,
            runner: Callable[..., dict[str, Any]] | None = None,
            faithfulness: Callable[..., Any] | None = None, store: Any = None) -> tuple[int, dict[str, Any]]:
    from rag.call_cache import CallCache, call_cache
    from rag.eval.faithfulness import NeedsApproval, run_faithfulness
    from rag.runner.config import load_config_file
    from rag.runner.cost import CostGateError
    from rag.runner.model_check import ModelCheckUnavailable, ModelResolutionError, verify_config_models
    from rag.runner.run import run
    from rag.runner.store import ResultsStore

    runner = runner or run
    faithfulness = faithfulness or run_faithfulness
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    gate = load_gate(gate_path)
    baseline = json.loads(Path(baseline_path).read_text()) if Path(baseline_path).exists() else None
    if baseline is None and not allow_no_baseline and not estimate_only:
        raise CIError(f"no baseline at {baseline_path}; pass --allow-no-baseline to record one")
    dev_cfg, golden_cfg = load_config_file(gate["configs"]["dev_retrieval"]), load_config_file(gate["configs"]["golden"])
    budget = float(gate["ci_budget_usd"])
    approval = approve_cost.strip() or f"ci-eval: within ci_budget_usd {budget}"

    try:
        for cfg in (dev_cfg, golden_cfg, load_config_file(gate["configs"]["judge"])):
            verify_config_models(cfg)
    except (ModelResolutionError, ModelCheckUnavailable) as exc:
        raise CIError(f"model check: {exc}") from exc

    owns = store is None
    store = store if store is not None else ResultsStore()
    try:
        est = {k: runner(c, store=store, estimate_only=True)["total_usd"] for k, c in (("dev", dev_cfg), ("golden", golden_cfg))}
        if estimate_only:
            doc = {"estimate_only": True, "runs_usd": est,
                   "judge_usd_upper_bound": "set after generation, from the faithfulness estimator"}
            (out / "ci_eval_estimate.json").write_text(json.dumps(doc, indent=2))
            return EXIT_PASS, doc
        if sum(est.values()) > budget and not approve_cost.strip():
            return EXIT_NEEDS_APPROVAL, {"status": "NEEDS_APPROVAL", "estimate": est, "budget": budget}
        cache = CallCache()
        try:
            with call_cache(cache):
                dev_row = runner(dev_cfg, store=store, reason="rag ci-eval (P3-08)")
                golden_row = runner(golden_cfg, store=store, reason="rag ci-eval (P3-08)")
            spent = (dev_row.get("cost_actual_usd") or 0) + (golden_row.get("cost_actual_usd") or 0)
            try:
                faith = faithfulness(golden_row["run_id"], judge_config_path=gate["configs"]["judge"],
                                     approve_cost=approval, max_usd=None if approve_cost.strip() else budget - spent,
                                     store=store)
            except NeedsApproval as exc:
                return EXIT_NEEDS_APPROVAL, {"status": "NEEDS_APPROVAL", "reason": str(exc), "budget": budget}
        finally:
            cache.close()
        faith_row = store.get_run(faith.run_id)
        judge_total = faith.cache_stats.get("hits", 0) + faith.cache_stats.get("misses", 0)
        stats = {**cache.snapshot(), "judge_hit_rate": round(faith.cache_stats.get("hits", 0) / judge_total, 4)
                 if judge_total else None}
        cost = {"dev": dev_row.get("cost_actual_usd") or 0, "golden": golden_row.get("cost_actual_usd") or 0,
                "judge": faith.usage.get("cost_usd", 0)}
        cost["total"] = round(sum(cost.values()), 6)
        result = collect(dev_row=dev_row, golden_row=golden_row, faith_row=faith_row, store=store,
                         gate=gate, cost=cost, cache=stats)
    except (CostGateError,) as exc:
        return EXIT_NEEDS_APPROVAL, {"status": "NEEDS_APPROVAL", "reason": str(exc)}
    finally:
        if owns:
            store.close()

    verdict = compare(result, baseline, gate) if baseline else None
    doc = {"result": result, "verdict": verdict}
    (out / "ci_eval.json").write_text(json.dumps(doc, indent=2, default=str))
    (out / "ci_eval.md").write_text(summary_markdown(result, verdict))
    if verdict is None:
        return EXIT_PASS, doc
    return {"PASS": EXIT_PASS, "FAIL": EXIT_FAIL, "ERROR": EXIT_ERROR}[verdict["status"]], doc


# --- the baseline file -----------------------------------------------------------------

def update_baseline(*, source: str, reason: str, baseline_path: str, decisions_path: str) -> dict[str, Any]:
    """Write `ci/baseline.json` from a ci-eval result. Only with a DEC entry that exists
    (P3-11 adds the rest of the ratchet), and only from a run with no hard failure."""
    import re

    if not re.fullmatch(r"DEC-\d{3,}", reason):
        raise CIError("--reason must be a DEC id, e.g. DEC-085")
    if not re.search(rf"^## {re.escape(reason)}\b", Path(decisions_path).read_text(), re.MULTILINE):
        raise CIError(f"{reason} is not an entry in {decisions_path}: write the decision first")
    doc = json.loads(Path(source).read_text())
    result = doc["result"]
    if doc.get("verdict") and doc["verdict"]["hard_fails"]:
        raise CIError("the source run has hard failures; it cannot become the baseline")
    answers = result["per_question"]["answers"]
    if any(a["empty"] or a["judge_failed"] for a in answers.values()):
        raise CIError("the source run has empty answers or judge failures; it cannot become the baseline")
    baseline = {"schema_version": SCHEMA_VERSION, "reason": reason,
                "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "config_hashes": {"dev": result["provenance"]["dev_config_hash"],
                                  "golden": result["provenance"]["golden_config_hash"]},
                "result": result}
    Path(baseline_path).write_text(json.dumps(baseline, indent=2, default=str) + "\n")
    return baseline
