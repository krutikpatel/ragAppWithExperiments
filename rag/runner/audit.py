"""`rag audit provenance` — P3-01.

Before Phase 3 baselines anything on the Phase 2 closing numbers, it has to be shown
that the dev and test runs behind them were independent: that nothing the test run
reported was served from a cache the dev run filled, that the two splits share no
question, and that numbers which came back identical did so for a reason other than
a leak.

Reads the results store and the generation cache. Zero model calls, zero cost.

Three kinds of reuse are possible on this pipeline, and each is checked where it
would happen rather than inferred from the config:

- **Index.** Passage vectors are cached under `indexes/<key>/` and shared by every run
  of the same chunker and embedder. That is corpus-level and split-blind by design, so
  a hit is expected on both sides and is not a leak.
- **Query embeddings.** Not cached anywhere. Each run embeds its own questions; the
  run row records how many calls and tokens that took (`embedder_now.usage`).
- **Model outputs.** In-pipeline LLM calls go through `GenerationCache` (P2-03), keyed
  on question id. The answer generator does not use a cache at all. The judge is
  Ragas behind `Judge`, with no cache configured. The audit counts the cache rows that
  *could* have served the answer prompt, and the pipeline-LLM hits each row recorded.
"""

from __future__ import annotations

import json
import re
from typing import Any

from rag.eval.generation_metrics import REFUSAL_DETECTOR_VERSION, is_refusal
from rag.generation.cache import GenerationCache
from rag.runner.store import ResultsStore

# Per-question metrics compared between the two sides. `refused` is recounted from the
# stored answer under the current detector, because older rows carry older versions
# (MIS-038) and the ledger compares both sides under v3.
OUTCOME_METRICS = ("gold_in_context", "strict_recall@5", "refused")


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _outcomes(question: dict[str, Any]) -> dict[str, float | None]:
    metrics = json.loads(question["metrics_json"] or "{}")
    out = {m: metrics.get(m) for m in OUTCOME_METRICS if m != "refused"}
    answer = question.get("generated_answer")
    out["refused"] = None if answer is None else float(is_refusal(answer))
    return out


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 4) if present else None


def _run_summary(meta: dict[str, Any], questions: dict[str, dict[str, Any]],
                 cache: GenerationCache | None) -> dict[str, Any]:
    config = json.loads(meta["config_json"] or "{}")
    retriever_meta = json.loads(meta["retriever_meta"] or "{}")
    pipeline_llm = json.loads(meta["pipeline_llm_json"] or "null")
    prompts = json.loads(meta["prompt_versions"] or "{}")
    usage = (retriever_meta.get("embedder_now") or {}).get("usage") or {}
    metrics = json.loads(meta["metrics_json"] or "{}")
    answer_prompt = prompts.get("answer", "")
    prompt_id, _, prompt_version = answer_prompt.partition("@")
    tier2 = meta["eval_tier"] == "tier2"

    answer_cache_rows = None
    if cache is not None and tier2 and prompt_id:
        answer_cache_rows = int(cache.conn.execute(
            "SELECT COUNT(*) FROM generations WHERE prompt_id = ? AND prompt_version = ? AND model_id = ?",
            (prompt_id, prompt_version, meta["generator_model"] or ""),
        ).fetchone()[0])

    return {
        "run_id": meta["run_id"],
        "timestamp": meta["timestamp"],
        "split": meta["split"],
        "split_hash": meta["split_hash"],
        "eval_tier": meta["eval_tier"],
        "subsample": meta["eval_subsample_id"],
        "n_questions": len(questions),
        "git_sha": meta["git_sha"][:7],
        "git_dirty": meta["git_dirty"],
        "config_hash": meta["config_hash"],
        "retrieval": {
            "index_cache_hit": retriever_meta.get("cache_hit"),
            "index_key": retriever_meta.get("index_key"),
            "query_embedding_calls": usage.get("calls"),
            "query_embedding_tokens": usage.get("prompt_tokens"),
            "query_embedding_cache": "none — every run embeds its own questions",
        },
        "pipeline_llm": pipeline_llm or {"note": "no in-pipeline LLM call in this config"},
        "generation": None if not tier2 else {
            "generator_model": meta["generator_model"],
            "answer_prompt": answer_prompt,
            "answer_cache": "none — OpenRouterGenerator.generate calls the provider every run",
            "cache_rows_for_answer_prompt": answer_cache_rows,
            "answers_stored": sum(1 for q in questions.values() if q.get("generated_answer")),
        },
        "judge": None if not tier2 else {
            "skipped": bool(metrics.get("skip_judge")),
            "judge_model": meta["judge_model"],
            "provider_order": json.loads(meta["judge_provider_order"] or "[]"),
            "judge_cache": "none configured",
        },
        "config_skip_judge": config.get("skip_judge"),
    }


def _outcome_profile(questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    per_q = {qid: _outcomes(q) for qid, q in questions.items()}
    return {
        metric: {
            "mean": _mean([o[metric] for o in per_q.values()]),
            "hits": sum(1 for o in per_q.values() if o[metric] == 1.0),
            "n": sum(1 for o in per_q.values() if o[metric] is not None),
        }
        for metric in OUTCOME_METRICS
    }


def _agreement(qa: dict[str, dict[str, Any]], qb: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Paired agreement on the question ids both runs answered. Empty when disjoint."""
    shared = sorted(set(qa) & set(qb))
    out: dict[str, Any] = {"n_shared": len(shared)}
    for metric in OUTCOME_METRICS:
        pairs = [(_outcomes(qa[q])[metric], _outcomes(qb[q])[metric]) for q in shared]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        out[metric] = {"n": len(pairs), "agree": sum(1 for a, b in pairs if a == b)}
    return out


def _restricted_recall(tier1: dict[str, dict[str, Any]], ids: set[str]) -> dict[str, Any]:
    """Tier 1 strict recall@5 over the whole split and over the Tier 2 subsample only."""
    def mean_over(keys: list[str]) -> float | None:
        return _mean([json.loads(tier1[k]["metrics_json"]).get("strict_recall@5") for k in keys])

    inside = sorted(set(tier1) & ids)
    return {
        "n_split": len(tier1),
        "strict_recall@5_split": mean_over(sorted(tier1)),
        "n_subsample": len(inside),
        "strict_recall@5_subsample": mean_over(inside),
    }


def _split_overlap(split_a: str, split_b: str) -> dict[str, Any]:
    from rag.dataset.loader import load_split

    a, b = load_split(split_a), load_split(split_b)
    ids = sorted(set(a["question_id"]) & set(b["question_id"]))
    texts_a = {_norm(t) for t in a["question"]}
    same_text = sorted(qid for qid, t in zip(b["question_id"], b["question"]) if _norm(t) in texts_a)
    return {
        "n_a": len(a), "n_b": len(b),
        "shared_question_ids": ids,
        "shared_question_texts": same_text,
    }


def provenance_audit(
    dev_run: str,
    test_run: str,
    *,
    dev_tier1: str | None = None,
    test_tier1: str | None = None,
    store: ResultsStore | None = None,
    cache: GenerationCache | None = None,
    check_splits: bool = True,
) -> dict[str, Any]:
    owns_store, owns_cache = store is None, cache is None
    store = store if store is not None else ResultsStore()
    cache = cache if cache is not None else GenerationCache()
    try:
        meta_a, meta_b = store.get_run(dev_run), store.get_run(test_run)
        for run_id, meta in ((dev_run, meta_a), (test_run, meta_b)):
            if meta is None:
                raise KeyError(f"no run {run_id!r} in {store.path}")
        qa, qb = store.get_questions(dev_run), store.get_questions(test_run)

        answers_a = {_norm(q["generated_answer"]) for q in qa.values() if q.get("generated_answer")}
        identical_answers = sorted(
            qid for qid, q in qb.items() if q.get("generated_answer") and _norm(q["generated_answer"]) in answers_a
        )
        pipeline_b = json.loads(meta_b["pipeline_llm_json"] or "null") or {}

        report: dict[str, Any] = {
            "refusal_detector": REFUSAL_DETECTOR_VERSION,
            "runs": {"dev": _run_summary(meta_a, qa, cache), "test": _run_summary(meta_b, qb, cache)},
            "question_sets": {
                "shared_ids_between_runs": sorted(set(qa) & set(qb)),
                "splits": _split_overlap(meta_a["split"], meta_b["split"]) if check_splits else None,
            },
            "cross_run_reuse": {
                "test_answers_identical_to_a_dev_answer": identical_answers,
                "test_pipeline_llm_cache_hits": pipeline_b.get("cache_hits", 0),
                "test_judge_ran": not json.loads(meta_b["metrics_json"] or "{}").get("skip_judge", False),
            },
            "outcomes": {"dev": _outcome_profile(qa), "test": _outcome_profile(qb)},
            "agreement_on_shared_ids": _agreement(qa, qb),
        }
        if dev_tier1 and test_tier1:
            report["tier1_restricted_to_subsample"] = {
                "dev": {"run_id": dev_tier1, **_restricted_recall(store.get_questions(dev_tier1), set(qa))},
                "test": {"run_id": test_tier1, **_restricted_recall(store.get_questions(test_tier1), set(qb))},
            }
        report["leak_found"] = bool(
            report["question_sets"]["shared_ids_between_runs"]
            or identical_answers
            or report["cross_run_reuse"]["test_pipeline_llm_cache_hits"]
            or (report["runs"]["test"]["generation"] or {}).get("cache_rows_for_answer_prompt")
            or (check_splits and (report["question_sets"]["splits"]["shared_question_ids"]
                                  or report["question_sets"]["splits"]["shared_question_texts"]))
        )
        return report
    finally:
        if owns_store:
            store.close()
        if owns_cache:
            cache.close()


def format_audit(report: dict[str, Any]) -> str:
    lines = []
    for side in ("dev", "test"):
        r = report["runs"][side]
        lines.append(f"{side}: {r['run_id']}  split={r['split']}  tier={r['eval_tier']}  "
                     f"subsample={r['subsample']}  n={r['n_questions']}  sha={r['git_sha']}")
        ret = r["retrieval"]
        lines.append(f"  retrieval: index cache hit={ret['index_cache_hit']} (key {ret['index_key']}); "
                     f"query embeddings {ret['query_embedding_calls']} calls, "
                     f"{ret['query_embedding_tokens']} tokens, uncached")
        lines.append(f"  pipeline LLM: {json.dumps(r['pipeline_llm'])}")
        if r["generation"]:
            g = r["generation"]
            lines.append(f"  generation: {g['generator_model']} {g['answer_prompt']}; answer cache rows "
                         f"{g['cache_rows_for_answer_prompt']} -> all {g['answers_stored']} answers were fresh calls")
            j = r["judge"]
            lines.append(f"  judge: {'SKIPPED' if j['skipped'] else j['judge_model']} "
                         f"{j['provider_order'] or ''}; cache: {j['judge_cache']}")
    qs = report["question_sets"]
    lines.append(f"shared question ids between the two runs: {len(qs['shared_ids_between_runs'])}")
    if qs["splits"]:
        s = qs["splits"]
        lines.append(f"full splits ({s['n_a']} vs {s['n_b']}): shared ids {len(s['shared_question_ids'])}, "
                     f"identical question text {len(s['shared_question_texts'])}")
    reuse = report["cross_run_reuse"]
    lines.append(f"test answers identical to any dev answer: {len(reuse['test_answers_identical_to_a_dev_answer'])}; "
                 f"test pipeline-LLM cache hits: {reuse['test_pipeline_llm_cache_hits']}; "
                 f"test judge ran: {reuse['test_judge_ran']}")
    lines.append(f"outcomes (refusals recounted under {report['refusal_detector']}):")
    for metric in OUTCOME_METRICS:
        d, t = report["outcomes"]["dev"][metric], report["outcomes"]["test"][metric]
        lines.append(f"  {metric:16s} dev {d['mean']} ({d['hits']}/{d['n']})   test {t['mean']} ({t['hits']}/{t['n']})")
    agree = report["agreement_on_shared_ids"]
    lines.append(f"per-question agreement: {agree['n_shared']} shared ids"
                 + (" — the question sets are disjoint, so identical aggregates come from different questions"
                    if agree["n_shared"] == 0 else ""))
    if "tier1_restricted_to_subsample" in report:
        for side in ("dev", "test"):
            t = report["tier1_restricted_to_subsample"][side]
            lines.append(f"tier1 {side} {t['run_id']}: strict recall@5 {t['strict_recall@5_split']} on {t['n_split']}, "
                         f"{t['strict_recall@5_subsample']} on the {t['n_subsample']} Tier 2 subsample questions")
    lines.append(f"LEAK FOUND: {report['leak_found']}")
    return "\n".join(lines)
