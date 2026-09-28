"""`rag faithfulness <run_id>` — P3-05, the offline faithfulness evaluation.

For every answer a Tier 2 run stored, which of its claims are supported by the context
the generator actually saw? Nothing is regenerated and nothing is retrieved: the context
is rebuilt from the run's stored `context_chunk_ids` through the same assembler, so the
judge reads exactly the prompt context the answer was written from.

The judge comes from a CONFIG (default `configs/baseline_dense_tier2_v2.yaml`, the
production judge of DEC-079), never from the run row: Phase 0–2 runs recorded a
same-lab judge that DEC-073 refused.

Metrics — declared in P3-05 and here, not tuned later:
- **mean faithfulness**: supported claims / claims, over answers that were judged.
- **unsupported-answer rate**: answers with ≥ 1 unsupported claim / answers judged.
  Strict by declaration (P3-05).
- **refusal rate**: refusals / answerable questions (`refusal-lexical-v3`).
- **false-answer rate**: unanswerable questions that got an answer / unanswerable questions.
- **citation integrity** (deterministic): the share of answers whose every cited
  `[doc:<id>]` is a document that was in the assembled context. This project cites
  documents, not chunks (P1-06); a chunk-level check would have nothing to check.

Not applicable is designed first (MIS-002): a refusal has no claims and is not judged;
a judge failure is `None`, counted, never zero (MIS-011); NaN is a failure (MIS-043).

**Claim attribution is a heuristic, labelled as one.** Ragas judges each claim against
the joined context and does not say which chunk supported it. `attribution-lexical-v1`
points each claim at the context chunk sharing the most of its content words. The
VERDICT is the judge's; the chunk pointer is ours.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.eval.generation_metrics import REFUSAL_DETECTOR_VERSION, is_refusal, malformed_citation_markers
from rag.paths import RESULTS_DIR

JUDGE_CACHE = RESULTS_DIR / "judge_cache.sqlite"
REPORTS_DIR = RESULTS_DIR / "reports"
DEFAULT_JUDGE_CONFIG = "configs/baseline_dense_tier2_v2.yaml"
ATTRIBUTION = "attribution-lexical-v1"
# Estimate basis: EXP-0054 (`run_20260928_052254_e257`), the same judge on 240 pairs of
# realistic-length answers: $0.586071 over 200,797 context words. Linear in context words.
CALIBRATION_RUN = "run_20260928_052254_e257"
USD_PER_CONTEXT_WORD = 0.586071 / 200_797

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an the and or of to in on for with at by from is are be your you it this that as can if".split())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


# --- the judge cache ---------------------------------------------------------------

class JudgeCache:
    """Keyed on (judge, judge prompt version, question, context hash, answer hash), as
    P3-05 specifies. `judge` includes the provider pin and fallback flag: a different
    host is a different judge (DEC-032). An unchanged answer is never re-judged."""

    SCHEMA = """CREATE TABLE IF NOT EXISTS judgments (
        judge TEXT NOT NULL, prompt_version TEXT NOT NULL, question_hash TEXT NOT NULL,
        context_hash TEXT NOT NULL, answer_hash TEXT NOT NULL, output TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (judge, prompt_version, question_hash, context_hash, answer_hash))"""

    def __init__(self, path: Path = JUDGE_CACHE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(self.SCHEMA)
        self.hits = self.misses = 0

    @staticmethod
    def key(judge: str, prompt_version: str, question: str, contexts: list[str], answer: str) -> tuple:
        return (judge, prompt_version, _sha(question), _sha("\n".join(contexts)), _sha(answer))

    def get(self, key: tuple) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT output FROM judgments WHERE judge=? AND prompt_version=? AND question_hash=? "
            "AND context_hash=? AND answer_hash=?", key).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: tuple, output: dict[str, Any]) -> None:
        self.conn.execute("INSERT OR REPLACE INTO judgments VALUES (?,?,?,?,?,?,?)",
                          (*key, json.dumps(output), datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


def judge_identity(config: Any) -> str:
    order = ",".join(config.provider_order)
    return f"{config.model}@{order}{'' if config.provider_allow_fallbacks else ':nofallback'}|t={config.temperature}"


def judge_prompt_version() -> str:
    from rag.eval.judge import RagasJudge, metric_fingerprint, ragas_version

    return f"ragas-{ragas_version()}:{metric_fingerprint(RagasJudge.METRIC_PACKAGES['faithfulness'])}"


# --- inputs ------------------------------------------------------------------------

@dataclass
class AnswerInput:
    question_id: str
    question: str
    answer: str
    gold_doc_ids: list[str]
    cited_doc_ids: list[str]
    context_chunk_ids: list[str]
    context_doc_ids: list[str]
    contexts: list[str]
    gold_in_context: float | None

    @property
    def unanswerable(self) -> bool:
        return not self.gold_doc_ids

    @property
    def refused(self) -> bool:
        return is_refusal(self.answer)

    @property
    def context_words(self) -> int:
        return sum(len(c.split()) for c in self.contexts)


def rebuild_contexts(chunk_ids: list[str], chunk_to_doc: dict[str, str], context_text: dict[str, str],
                     *, max_tokens: int, order: str) -> tuple[list[str], list[str], list[str]]:
    """The prompt context exactly as the assembler built it: one part per chunk that fit
    the budget, each headed by its document id, as the generator saw it. Asserted equal
    to the assembler's own text, so a change to assembly cannot drift silently."""
    from rag.assembly import ConcatAssembler, order_chunks
    from rag.retrieval.base import ScoredChunk

    chunks = [ScoredChunk(c, chunk_to_doc[c], 0.0) for c in chunk_ids]
    assembled = ConcatAssembler(max_tokens=max_tokens, order=order).assemble(chunks, context_text)
    kept = order_chunks(chunks, order)[: assembled.n_chunks]
    parts = [f"--- ARTICLE [doc:{c.doc_id}] ---\n{context_text[c.chunk_id]}" for c in kept]
    if "\n\n".join(parts) != assembled.text:
        raise AssertionError("rebuilt context differs from the assembler's output")
    return parts, [c.chunk_id for c in kept], assembled.doc_ids


def load_run(run_id: str, store: Any) -> tuple[dict[str, Any], list[AnswerInput]]:
    from rag.dataset.loader import load_split
    from rag.runner.config import config_from_json
    from rag.runner.run import build_index

    meta = store.get_run(run_id)
    if meta is None:
        raise KeyError(f"no run {run_id!r}")
    if meta["eval_tier"] != "tier2":
        raise ValueError(f"{run_id} is {meta['eval_tier']}; faithfulness needs a Tier 2 run with stored answers")
    config = config_from_json(meta["config_json"])
    index, _ = build_index(config)
    chunk_to_doc, context_text = index.chunk_to_doc, index.context_text
    questions = dict(zip(*[load_split(meta["split"])[c] for c in ("question_id", "question")]))
    inputs = []
    for qid, row in sorted(store.get_questions(run_id).items()):
        chunk_ids = json.loads(row["context_chunk_ids"] or "[]")
        contexts, kept, docs = rebuild_contexts(chunk_ids, chunk_to_doc, context_text,
                                                max_tokens=config.context_max_tokens, order=config.context_order)
        metrics = json.loads(row["metrics_json"] or "{}")
        inputs.append(AnswerInput(
            question_id=qid, question=str(questions[qid]), answer=row["generated_answer"] or "",
            gold_doc_ids=json.loads(row["gold_doc_ids"] or "[]"),
            cited_doc_ids=json.loads(row["cited_doc_ids"] or "[]"),
            context_chunk_ids=kept, context_doc_ids=docs, contexts=contexts,
            gold_in_context=metrics.get("gold_in_context"),
        ))
    return meta, inputs


# --- attribution and integrity ----------------------------------------------------

def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def attribute(statement: str, chunk_ids: list[str], contexts: list[str]) -> tuple[str | None, float]:
    """`attribution-lexical-v1`: the context chunk holding the largest share of the
    claim's content words. Returns (chunk id, share). A pointer, not a verdict."""
    words = _content_words(statement)
    if not words or not contexts:
        return None, 0.0
    shares = [len(words & _content_words(c)) / len(words) for c in contexts]
    best = max(range(len(shares)), key=lambda i: shares[i])
    return chunk_ids[best], round(shares[best], 3)


def citation_integrity(cited: list[str], context_docs: list[str]) -> tuple[bool, list[str]]:
    invented = [d for d in cited if d not in set(context_docs)]
    return not invented, invented


_CORPUS_IDS: set[str] | None = None


def corpus_ids() -> set[str]:
    global _CORPUS_IDS
    if _CORPUS_IDS is None:
        from rag.corpus.loader import load_corpus

        _CORPUS_IDS = set(load_corpus().frame["id"])
    return _CORPUS_IDS


def citation_checks(answer: str, cited: list[str], context_docs: list[str],
                    known_ids: set[str]) -> dict[str, Any]:
    """P3-09 (DEC-087). Three different errors, separated because they behave differently:
    - `cites_unretrieved_article`: a REAL corpus article the generator was not given —
      0 in 481 answers across six fresh runs; the gate's zero-tolerance hard fail;
    - `garbled_citations`: a well-formed id that matches no article (a mis-copied hash);
    - `malformed_citations`: a `[doc:` marker the parser rejects (wrong-length id, a title).
    `citation_valid` is none of the three."""
    _, outside = citation_integrity(cited, context_docs)
    real = [d for d in outside if d in known_ids]
    garbled = [d for d in outside if d not in known_ids]
    malformed = malformed_citation_markers(answer)
    return {"unretrieved_real_citations": real, "garbled_citations": garbled,
            "malformed_citations": malformed, "citation_valid": not (outside or malformed)}


# --- aggregation ---------------------------------------------------------------------

def strata_of(item: AnswerInput) -> list[str]:
    if item.unanswerable:
        return ["all", "unanswerable"]
    tags = ["all", "answerable", "gold_docs:multi" if len(item.gold_doc_ids) > 1 else "gold_docs:single"]
    if item.gold_in_context is not None:
        tags.append("gold_in_context" if item.gold_in_context else "gold_not_in_context")
    return tags


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Every declared metric, per stratum. `None` where a metric has nothing to count."""
    def rate(num: int, den: int) -> float | None:
        return round(num / den, 4) if den else None

    by: dict[str, dict[str, Any]] = {}
    names = sorted({t for r in rows for t in r["strata"]})
    for name in names:
        group = [r for r in rows if name in r["strata"]]
        answerable = [r for r in group if not r["unanswerable"]]
        unanswerable = [r for r in group if r["unanswerable"]]
        answered = [r for r in group if not r["refused"]]
        judged = [r for r in answered if r["faithfulness"] is not None]
        by[name] = {
            "n": len(group),
            "n_answered": len(answered),
            "n_judged": len(judged),
            "judge_failures": sum(1 for r in answered if r["faithfulness"] is None),
            "mean_faithfulness": round(sum(r["faithfulness"] for r in judged) / len(judged), 4) if judged else None,
            "unsupported_answer_rate": rate(sum(1 for r in judged if r["unsupported"]), len(judged)),
            "refusal_rate": rate(sum(1 for r in answerable if r["refused"]), len(answerable)),
            "false_answer_rate": rate(sum(1 for r in unanswerable if not r["refused"]), len(unanswerable)),
            "citation_integrity": rate(sum(1 for r in answered if r["citation_integrity"]), len(answered)),
            "invented_citations": sum(len(r["invented_citations"]) for r in answered),
            "citation_validity": rate(sum(1 for r in answered if r.get("citation_valid", r["citation_integrity"])), len(answered)),
            "cites_unretrieved_article": sum(1 for r in answered if r.get("unretrieved_real_citations")),
            "garbled_citation_answers": sum(1 for r in answered if r.get("garbled_citations")),
            "malformed_citation_answers": sum(1 for r in answered if r.get("malformed_citations")),
            "claims": sum(r["n_claims"] for r in judged),
            "unsupported_claims": sum(r["n_unsupported"] for r in judged),
        }
    return by


def estimate(inputs: list[AnswerInput], cached: set[str]) -> dict[str, Any]:
    todo = [i for i in inputs if not i.refused and i.question_id not in cached]
    words = sum(i.context_words for i in todo)
    return {"n_to_judge": len(todo), "n_cached": len(cached), "n_refused": sum(1 for i in inputs if i.refused),
            "context_words": words, "usd": round(words * USD_PER_CONTEXT_WORD, 4),
            "source": f"${USD_PER_CONTEXT_WORD * 1000:.5f} per 1,000 context words, calibrated on {CALIBRATION_RUN}"}


# --- the run -----------------------------------------------------------------------

def evaluate(inputs: list[AnswerInput], judge: Any, cache: JudgeCache | None, *, identity: str,
             prompt_version: str, score_fn: Any = None, known_ids: set[str] | None = None) -> list[dict[str, Any]]:
    """Judge every answered question (cache first), then score integrity and strata.
    `score_fn(items) -> list[ClaimJudgment]` is injectable so tests need no model."""
    from rag.eval.judge import ClaimJudgment, ClaimVerdict, FaithfulnessClaims

    score_fn = score_fn or FaithfulnessClaims(judge).score_batch
    judgments: dict[str, ClaimJudgment] = {}
    todo = []
    for item in inputs:
        if item.refused:
            continue
        key = JudgeCache.key(identity, prompt_version, item.question, item.contexts, item.answer)
        hit = cache.get(key) if cache else None
        if hit is not None:
            cache.hits += 1
            judgments[item.question_id] = ClaimJudgment(
                score=hit["score"], claims=tuple(ClaimVerdict(**c) for c in hit["claims"]), error=hit["error"])
        else:
            todo.append((item, key))
    fresh = score_fn([{"question": i.question, "answer": i.answer, "contexts": i.contexts} for i, _ in todo]) if todo else []
    for (item, key), judgment in zip(todo, fresh, strict=True):
        judgments[item.question_id] = judgment
        if cache is not None:
            cache.misses += 1
            if judgment.score is not None:  # a failure is retried next time, never cached
                cache.put(key, {"score": judgment.score, "error": judgment.error,
                                "claims": [c.__dict__ for c in judgment.claims]})

    known_ids = known_ids if known_ids is not None else corpus_ids()
    rows = []
    for item in inputs:
        j = judgments.get(item.question_id)
        ok, invented = citation_integrity(item.cited_doc_ids, item.context_doc_ids)
        claims = []
        for c in (j.claims if j else ()):
            chunk, share = attribute(c.statement, item.context_chunk_ids, item.contexts)
            claims.append({"statement": c.statement, "supported": c.supported, "reason": c.reason,
                           "chunk_id": chunk, "attribution_share": share})
        n_unsupported = sum(1 for c in claims if not c["supported"])
        checks = citation_checks(item.answer, item.cited_doc_ids, item.context_doc_ids, known_ids)
        rows.append({
            "question_id": item.question_id, "question": item.question, "answer": item.answer,
            "strata": strata_of(item), "unanswerable": item.unanswerable, "refused": item.refused,
            "faithfulness": j.score if j else None, "error": j.error if j else None,
            "n_claims": len(claims), "n_unsupported": n_unsupported,
            "unsupported": (n_unsupported > 0) if (j and j.score is not None) else None,
            "claims": claims, "cited_doc_ids": item.cited_doc_ids, "context_doc_ids": item.context_doc_ids,
            "citation_integrity": ok, "invented_citations": invented, **checks,
        })
    return rows


def report_markdown(source_run: str, run_id: str, rows: list[dict[str, Any]], metrics: dict[str, Any],
                    n: int = 10) -> str:
    judged = sorted((r for r in rows if r["faithfulness"] is not None), key=lambda r: (r["faithfulness"], r["question_id"]))
    lines = [f"# Faithfulness report — `{run_id}`", "",
             f"Source run `{source_run}`. Refusals detected by `{REFUSAL_DETECTOR_VERSION}`. Claim → chunk "
             f"pointers are `{ATTRIBUTION}`, a heuristic; verdicts are the judge's.", "",
             "| Stratum | n | answered | judged | mean faithfulness | unsupported-answer rate | refusal rate | false-answer rate | citation integrity |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, m in metrics.items():
        lines.append(f"| {name} | {m['n']} | {m['n_answered']} | {m['n_judged']} | {m['mean_faithfulness']} | "
                     f"{m['unsupported_answer_rate']} | {m['refusal_rate']} | {m['false_answer_rate']} | {m['citation_integrity']} |")
    lines += ["", f"## The {n} lowest-faithfulness answers", ""]
    for r in judged[:n]:
        lines += [f"### `{r['question_id']}` — faithfulness {r['faithfulness']:.3f}", "",
                  f"**Q:** {r['question']}", "", f"**Cited:** {', '.join(r['cited_doc_ids']) or '—'}", "",
                  "| Verdict | Claim | Chunk (heuristic) | Judge's reason |", "|---|---|---|---|"]
        for c in r["claims"]:
            cell = lambda t: str(t).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {'supported' if c['supported'] else '**UNSUPPORTED**'} | {cell(c['statement'])} | "
                         f"`{c['chunk_id']}` ({c['attribution_share']}) | {cell(c['reason'])} |")
        lines.append("")
    return "\n".join(lines)


def record(*, source_meta: dict[str, Any], judge_cfg: Any, judge_config_path: str, rows: list[dict[str, Any]],
           metrics: dict[str, Any], usage: dict[str, Any], cache_stats: dict[str, int], est: dict[str, Any],
           approval: str, store: Any) -> str:
    """One `runs` row (eval_tier `faithfulness`) linked to its source run, one
    `run_questions` row per answer with its claims — the store is the source of truth."""
    from rag.eval.judge import judge_provenance
    from rag.hashing import short_id
    from rag.runner.run import git_state

    config = {"kind": "faithfulness", "source_run": source_meta["run_id"], "judge_config": judge_config_path,
              "judge": judge_identity(judge_cfg), "judge_prompt_version": judge_prompt_version(),
              "attribution": ATTRIBUTION, "refusal_detector": REFUSAL_DETECTOR_VERSION,
              "unsupported_answer": "at least one unsupported claim (P3-05, strict)"}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{stamp}_{short_id(json.dumps(config, sort_keys=True), stamp, length=4)}"
    prov = judge_provenance(judge_cfg)
    git = git_state()
    store.start_run({
        "run_id": run_id, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": f"P3-05 faithfulness of {source_meta['run_id']}", "config_hash": short_id(json.dumps(config, sort_keys=True), length=16),
        "config_json": json.dumps(config), "corpus_hash": source_meta["corpus_hash"],
        "normalization_version": source_meta["normalization_version"], "hf_revision": source_meta["hf_revision"],
        "dataset_config": source_meta["dataset_config"], "split": source_meta["split"], "split_hash": source_meta["split_hash"],
        "eval_subsample_id": source_meta["eval_subsample_id"], "git_sha": git.sha, "git_dirty": int(git.dirty),
        "eval_tier": "faithfulness", "doc_pooling": source_meta["doc_pooling"], "generator_model": source_meta["generator_model"],
        "judge_model": judge_cfg.model, "judge_family": prov["judge_family"], "judge_temperature": judge_cfg.temperature,
        "ragas_version": prov["ragas_version"], "metric_prompt_versions": json.dumps(prov["metric_prompt_versions"]),
        "judge_provider_order": json.dumps(list(judge_cfg.provider_order)), "harness_smoke_test": 0,
        "prompt_versions": source_meta["prompt_versions"], "cost_estimate_usd": est["usd"],
        "cost_actual_usd": usage.get("cost_usd", 0.0), "cost_actual_json": json.dumps({**usage, "cache": cache_stats}),
        "cost_approval": approval,
    })
    store.add_questions([{
        "run_id": run_id, "question_id": r["question_id"], "retrieved_doc_ids": json.dumps(r["context_doc_ids"]),
        "retrieved_chunk_ids": "[]", "scores": "[]", "gold_doc_ids": "[]",
        "metrics_json": json.dumps({k: r[k] for k in ("strata", "unanswerable", "refused", "faithfulness", "error",
                                                         "n_claims", "n_unsupported", "unsupported", "claims",
                                                         "citation_integrity", "invented_citations",
                                                         "citation_valid", "unretrieved_real_citations",
                                                         "garbled_citations", "malformed_citations")}),
        "generated_answer": r["answer"], "cited_doc_ids": json.dumps(r["cited_doc_ids"]),
        "latency_ms": None, "tokens_in": None, "tokens_out": None, "cost_usd": None,
    } for r in rows])
    store.finish_run(run_id, status="VALID", metrics={"by_stratum": metrics, "usage": usage, "cache": cache_stats},
                     n_questions=len(rows), notes=f"P3-05 on {source_meta['run_id']}")
    return run_id


class NeedsApproval(RuntimeError):
    """Uncached spend without an approval reference (DEC-053), or above a budget."""


@dataclass
class FaithfulnessResult:
    run_id: str | None
    rows: list[dict[str, Any]]
    metrics: dict[str, Any]
    usage: dict[str, Any]
    cache_stats: dict[str, Any]
    estimate: dict[str, Any]
    report_path: Path | None


def run_faithfulness(run_id: str, *, judge_config_path: str = DEFAULT_JUDGE_CONFIG, approve_cost: str = "",
                     no_cache: bool = False, limit: int = 0, estimate_only: bool = False,
                     max_usd: float | None = None, store: Any = None) -> FaithfulnessResult:
    """The whole P3-05 pipeline as one call: load, estimate, gate the spend, judge,
    aggregate, record, report. The CLI and `rag ci-eval` both use this."""
    from dataclasses import replace

    from rag.eval.judge import RagasJudge
    from rag.runner.config import load_config_file
    from rag.runner.cost import COST_GATE_USD
    from rag.runner.model_check import configured_models, verify_models
    from rag.runner.run import _judge_config
    from rag.runner.store import ResultsStore

    jconf = load_config_file(judge_config_path)
    judge_cfg = replace(_judge_config(jconf), only=("faithfulness",))
    identity, version = judge_identity(judge_cfg), judge_prompt_version()
    owns = store is None
    store = store if store is not None else ResultsStore()
    cache = None if no_cache else JudgeCache()
    try:
        meta, inputs = load_run(run_id, store)
        if limit:
            inputs = inputs[:limit]
        cached = {i.question_id for i in inputs if cache is not None and not i.refused
                  and cache.get(JudgeCache.key(identity, version, i.question, i.contexts, i.answer))}
        est = estimate(inputs, cached)
        if estimate_only:
            return FaithfulnessResult(None, [], {}, {}, {}, est, None)
        if max_usd is not None and est["usd"] > max_usd:
            raise NeedsApproval(f"faithfulness estimate ${est['usd']:.4f} is above the ${max_usd:.2f} budget")
        if est["usd"] > 0 and not approve_cost.strip():
            raise NeedsApproval("an approval reference is required for any uncached spend (DEC-053)")
        if est["usd"] > COST_GATE_USD and "DEC-" not in approve_cost:
            raise NeedsApproval(f"estimate above the ${COST_GATE_USD:.2f} gate: cite the DEC")
        judge = RagasJudge(judge_cfg)
        if est["n_to_judge"]:
            verify_models([r for r in configured_models(jconf) if r.role == "judge"])
        rows = evaluate(inputs, judge, cache, identity=identity, prompt_version=version)
        metrics = aggregate(rows)
        stats = {"hits": cache.hits if cache else 0,
                 "misses": cache.misses if cache else est["n_to_judge"], "bypassed": no_cache}
        new_id = record(source_meta=meta, judge_cfg=judge_cfg, judge_config_path=judge_config_path, rows=rows,
                        metrics=metrics, usage=judge.usage.as_dict(), cache_stats=stats, est=est,
                        approval=approve_cost, store=store)
    finally:
        if cache is not None:
            cache.close()
        if owns:
            store.close()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"faithfulness_{new_id}.md"
    path.write_text(report_markdown(run_id, new_id, rows, metrics))
    return FaithfulnessResult(new_id, rows, metrics, judge.usage.as_dict(), stats, est, path)
