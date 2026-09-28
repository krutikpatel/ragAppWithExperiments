"""`rag judge-check` — P3-04, the synthetic judge sanity check.

A judge cannot gate a build until it is shown to tell a supported answer from an
unsupported one on this corpus. There is no budget for human labels, so the check is
built from WixQA's own: each golden-slice reference answer (written by support experts
FROM its gold articles) is paired with

- **supported**: the full text of its gold articles — the correct verdict is supported;
- **unsupported**: the same number of random articles that share no gold id and are not
  in the dense retriever's top 50 for that question (the corpus has no product-area
  field, so "far away in retrieval" stands in for "different product area");
- **hard_negative**: the top-ranked NON-gold articles the dense control retrieved.
  Reported separately and never used for pass/fail: near-duplicate articles mean some
  of these may genuinely support the answer.

The verdict is the one P3-05 gates on: an answer is flagged **unsupported** when Ragas
faithfulness < 1.0 (at least one claim not supported). The production judge path is
used unchanged (`RagasJudge`, faithfulness only), so what is checked is what will gate.

Proves the judge is not broken on clear cases. It does NOT prove precision on borderline
answers, and no human agreement is measured.
"""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rag.eval.judge import JudgeConfig, RagasJudge
from rag.hashing import short_id

SEED = 20260928
# The promoted configuration's dev Tier 1 run: its ranking supplies the "not in the top
# 50" exclusion and the hard negatives.
DENSE_RUN = "run_20260912_225005_be04"
EXCLUDE_TOP = 50
KINDS = ("supported", "unsupported", "hard_negative")
GATING_KINDS = ("supported", "unsupported")

# The Phase 3 bake-off (DEC-075). One pinned host each, fallbacks off.
CANDIDATES: dict[str, tuple[str, str]] = {
    "deepseek": ("deepseek/deepseek-v4.1-flash", "DeepInfra"),
    "qwen": ("qwen/qwen3.8-flash", "Alibaba"),
    "gemini": ("google/gemini-3.8-flash", "Google AI Studio"),
}


# Reference answers carry markdown links to Wix URLs; the frozen corpus had link
# targets stripped (norm-v1) and the generator is told never to write URLs. Left in,
# every URL is a "claim" no article can support, and the strict flag would fire on a
# SUPPORTED pair over formatting. norm-v1's regex does not match these answers' looser
# link syntax (`[text] (url)`, URLs containing parentheses): measured, it removes 35 of
# 75. This rule keeps the link text and drops the target; any bare URL left is removed.
# Validated on all 80 answers: 75 URLs -> 0 (tests/test_judge_check_p3_04.py).
REFERENCE_LINK_RULE = "reference-links-v1"
_MD_LINK = re.compile(r"\[([^\]]*)\]\s*\(https?://\S+")
_BARE_URL = re.compile(r"https?://\S+")


def strip_links(text: str) -> str:
    return _BARE_URL.sub("", _MD_LINK.sub(r"\1", text))


@dataclass(frozen=True)
class Pair:
    pair_id: str
    question_id: str
    kind: str
    question: str
    answer: str
    article_ids: tuple[str, ...]

    @property
    def expected_unsupported(self) -> bool:
        return self.kind != "supported"


def build_pairs(golden: list[dict[str, Any]], corpus_ids: list[str],
                ranked_docs: dict[str, list[str]], *, seed: int = SEED) -> list[Pair]:
    """Every answerable golden question yields one pair of each kind, same article count."""
    pairs = []
    all_ids = sorted(corpus_ids)
    for row in golden:
        if row["stratum"] == "unanswerable":
            continue
        qid, gold = row["question_id"], list(row["article_ids"])
        ranked = ranked_docs[qid]
        # Per-question RNG: adding or removing one question never reshuffles another's.
        rng = random.Random(f"{seed}:{qid}")
        banned = set(gold) | set(ranked[:EXCLUDE_TOP])
        unrelated = []
        while len(unrelated) < len(gold):
            pick = rng.choice(all_ids)
            if pick not in banned and pick not in unrelated:
                unrelated.append(pick)
        hard = [d for d in ranked if d not in gold][: len(gold)]
        for kind, ids in (("supported", gold), ("unsupported", unrelated), ("hard_negative", hard)):
            pairs.append(Pair(f"{qid}:{kind}", qid, kind, row["question"], strip_links(row["reference_answer"]), tuple(ids)))
    return pairs


def verdict_flag(score: float | None) -> bool | None:
    """True = flagged unsupported. P3-05's strict definition: any unsupported claim."""
    return None if score is None else score < 1.0


def _auroc(pos: list[float], neg: list[float]) -> float | None:
    """P(score of a supported pair > score of an unsupported pair); ties count half.
    Threshold-free separation, reported beside the thresholded verdict."""
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Confusion matrix on the gating kinds; hard negatives separately."""
    scored = [r for r in results if r["score"] is not None]
    gating = [r for r in scored if r["kind"] in GATING_KINDS]
    tp = sum(1 for r in gating if r["kind"] == "unsupported" and r["flag"])
    fn = sum(1 for r in gating if r["kind"] == "unsupported" and not r["flag"])
    fp = sum(1 for r in gating if r["kind"] == "supported" and r["flag"])
    tn = sum(1 for r in gating if r["kind"] == "supported" and not r["flag"])
    n = tp + fn + fp + tn

    def rate(a: int, b: int) -> float | None:
        return round(a / b, 4) if b else None

    def mean(kind: str) -> float | None:
        values = [r["score"] for r in scored if r["kind"] == kind]
        return round(sum(values) / len(values), 4) if values else None

    hard = [r for r in scored if r["kind"] == "hard_negative"]
    return {
        "confusion": {"flagged_unsupported": {"unsupported": tp, "supported": fp},
                      "not_flagged": {"unsupported": fn, "supported": tn}},
        "n_gating_scored": n,
        "accuracy": rate(tp + tn, n),
        "unsupported_flag_precision": rate(tp, tp + fp),
        "unsupported_flag_recall": rate(tp, tp + fn),
        "supported_pass_rate": rate(tn, tn + fp),
        "auroc": _auroc([r["score"] for r in gating if r["kind"] == "supported"],
                        [r["score"] for r in gating if r["kind"] == "unsupported"]),
        "mean_faithfulness": {kind: mean(kind) for kind in KINDS},
        "hard_negative": {"n": len(hard), "flagged_unsupported": sum(1 for r in hard if r["flag"]),
                          "flag_rate": rate(sum(1 for r in hard if r["flag"]), len(hard))},
        "judge_failures": sum(1 for r in results if r["score"] is None),
        "judge_failure_by_kind": {k: sum(1 for r in results if r["score"] is None and r["kind"] == k) for k in KINDS},
    }


def judge_config(model: str, provider: str) -> JudgeConfig:
    return JudgeConfig(model=model, provider_order=(provider,), provider_allow_fallbacks=False,
                       only=("faithfulness",))


def run_pairs(pairs: list[Pair], texts: dict[str, str], config: JudgeConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    judge = RagasJudge(config)
    items = [{"question": p.question, "answer": p.answer, "contexts": [texts[a] for a in p.article_ids],
              "reference": ""} for p in pairs]
    started = time.monotonic()
    scores = judge.score_batch(items)
    elapsed = time.monotonic() - started
    results = []
    for pair, score in zip(pairs, scores, strict=True):
        s = score["faithfulness"]
        results.append({"pair_id": pair.pair_id, "question_id": pair.question_id, "kind": pair.kind,
                        "article_ids": list(pair.article_ids), "score": s.score, "flag": verdict_flag(s.score),
                        "error": s.error, "reason": (s.detail or {}).get("reason")})
    return results, {**judge.usage.as_dict(), "wall_seconds": round(elapsed, 1)}


def load_inputs() -> tuple[list[dict[str, Any]], dict[str, str], dict[str, list[str]], Any]:
    from rag.corpus.loader import load_corpus
    from rag.dataset.golden import load_golden
    from rag.runner.store import ResultsStore

    corpus = load_corpus()
    texts = dict(zip(corpus.frame["id"], corpus.frame["indexed_text"]))
    with ResultsStore() as store:
        ranked = {q: json.loads(r["retrieved_doc_ids"]) for q, r in store.get_questions(DENSE_RUN).items()}
    return load_golden(), texts, ranked, corpus


def record_run(*, name: str, model: str, provider: str, pairs: list[Pair], results: list[dict[str, Any]],
               usage: dict[str, Any], summary: dict[str, Any], corpus: Any, notes: str,
               cost_estimate: float | None, approval: str) -> str:
    """One row in `runs` (eval_tier `judge_check`) and one `run_questions` row per pair,
    so every number P3-04 reports is traceable to a run id (CLAUDE.md §2)."""
    from rag.dataset.golden import VERSION, golden_hash, load_golden
    from rag.runner.run import git_state
    from rag.runner.store import ResultsStore

    config = {"kind": "judge_check", "judge_model": model, "judge_provider": provider,
              "allow_fallbacks": False, "criterion": "faithfulness", "reference_links": REFERENCE_LINK_RULE, "verdict": "flag unsupported if faithfulness < 1.0",
              "pair_seed": SEED, "dense_run": DENSE_RUN, "exclude_top": EXCLUDE_TOP, "golden": VERSION,
              "pair_ids": [p.pair_id for p in pairs]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{stamp}_{short_id(json.dumps(config, sort_keys=True), stamp, length=4)}"
    git = git_state()
    from rag.eval.judge import judge_provenance

    prov = judge_provenance(judge_config(model, provider))
    with ResultsStore() as store:
        store.start_run({
            "run_id": run_id, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "name": name, "config_hash": short_id(json.dumps(config, sort_keys=True), length=16),
            "config_json": json.dumps(config), "corpus_hash": corpus.corpus_hash,
            "normalization_version": corpus.normalization_version, "hf_revision": corpus.hf_revision,
            "dataset_config": "golden", "split": VERSION, "split_hash": golden_hash(load_golden()),
            "git_sha": git.sha, "git_dirty": int(git.dirty), "eval_tier": "judge_check", "doc_pooling": "max",
            "judge_model": model, "judge_family": prov["judge_family"], "judge_temperature": prov["judge_temperature"],
            "ragas_version": prov["ragas_version"], "metric_prompt_versions": json.dumps(prov["metric_prompt_versions"]),
            "judge_provider_order": json.dumps([provider]), "harness_smoke_test": 0,
            "cost_estimate_usd": cost_estimate, "cost_actual_usd": usage["cost_usd"],
            "cost_actual_json": json.dumps(usage), "cost_approval": approval,
        })
        store.add_questions([{
            "run_id": run_id, "question_id": r["pair_id"], "retrieved_doc_ids": json.dumps(r["article_ids"]),
            "retrieved_chunk_ids": "[]", "scores": "[]", "gold_doc_ids": "[]",
            "metrics_json": json.dumps({"kind": r["kind"], "faithfulness": r["score"], "flag_unsupported": r["flag"],
                                        "error": r["error"]}),
            "generated_answer": r["reason"], "cited_doc_ids": "[]", "latency_ms": None,
            "tokens_in": None, "tokens_out": None, "cost_usd": None,
        } for r in results])
        store.finish_run(run_id, status="VALID", metrics={**summary, "usage": usage}, n_questions=len(results), notes=notes)
    return run_id


def estimate(pairs: list[Pair], texts: dict[str, str], probe: dict[str, Any]) -> dict[str, Any]:
    """Whole-run cost from a measured probe, scaled by context words. An estimate
    calibrated on a handful of pairs — say so when quoting it (MIS-040)."""
    words = sum(len(texts[a].split()) for p in pairs for a in p.article_ids)
    usd = probe["cost_usd"] / max(probe["context_words"], 1) * words
    return {"n_pairs": len(pairs), "context_words": words, "usd": round(usd, 4),
            "source": f"probe {probe['run_id']}: ${probe['cost_usd']:.5f} over {probe['context_words']} context words"}
