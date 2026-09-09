"""`run(config) -> row in the results store` — P0-09 and P0-10.

The runner owns provenance, tiering and recording. It owns no technique: retrievers
arrive through the registry, and the generator and judge through config.
"""

from __future__ import annotations

import json
import subprocess
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rag.assembly import ConcatAssembler
from rag.chunking.base import FixedTokenChunker
from rag.chunking.index_map import ChunkIndex
from rag.corpus.loader import load_corpus
from rag.dataset.splits import load_split
from rag.eval.generation_metrics import deterministic_metrics, refusal_summary
from rag.eval.judge import CRITERIA, JudgeConfig, OpenRouterJudge, judge_all_criteria
from rag.eval.qrels import qrels_from_split, run_from_results
from rag.eval.retrieval_metrics import evaluate_retrieval
from rag.eval.slices import aggregate_by_slice, build_slices
from rag.generation.base import GeneratorConfig, OpenRouterGenerator
from rag.hashing import short_id
from rag.runner.config import EvalTier, RunConfig
from rag.runner.registry import build_retriever
from rag.runner.store import ResultsStore

HELD_OUT_SPLIT = "test"


@dataclass(frozen=True)
class GitState:
    sha: str
    dirty: bool


def git_state() -> GitState:
    def _run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False
        ).stdout.strip()

    return GitState(sha=_run("rev-parse", "HEAD") or "unknown", dirty=bool(_run("status", "--porcelain")))


def make_run_id(config: RunConfig) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"run_{stamp}_{short_id(config.config_hash, stamp, length=4)}"


def check_test_split_guard(config: RunConfig, *, open_test: bool, store: ResultsStore) -> None:
    """P0-09 / P0-12 — the held-out split does not open by accident.

    400 gold questions across dozens of experiments is few enough that iterating on
    them produces a system tuned to the test set. The flag is the friction; the
    printed history is the reminder of how much of the budget is already spent.
    """
    if config.split != HELD_OUT_SPLIT:
        return
    if not open_test:
        raise PermissionError(
            "refusing to run against the held-out `test` split. Pass --open-test, and "
            "append a row to the openings log in docs/DECISIONS.md with the date, "
            "config hash, git SHA and reason."
        )
    previous = store.test_openings()
    print(f"\n*** OPENING THE TEST SPLIT ***")
    print(f"    previous openings: {len(previous)}")
    if previous:
        print(f"    last opening:      {previous[-1]['timestamp']} ({previous[-1]['run_id']})")
    print("    log this in docs/DECISIONS.md — date, config hash, git SHA, reason.\n")


def build_index(config: RunConfig) -> tuple[ChunkIndex, dict[str, str]]:
    corpus = load_corpus()
    chunker = FixedTokenChunker(**config.chunker_params)
    chunks = chunker.split_corpus(list(zip(corpus.frame["id"], corpus.frame["indexed_text"])))
    index = ChunkIndex(
        chunks=chunks,
        chunker_id=chunker.chunker_id,
        chunker_params=chunker.params,
        corpus_hash=corpus.corpus_hash,
        normalization_version=corpus.normalization_version,
    )
    return index, {chunk.chunk_id: chunk.text for chunk in chunks}


def run(
    config: RunConfig,
    *,
    open_test: bool = False,
    store: ResultsStore | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Execute one experiment and record it. Returns the finished `runs` row."""
    owns_store = store is None
    store = store or ResultsStore()
    try:
        return _run(config, open_test=open_test, store=store, reason=reason)
    finally:
        if owns_store:
            store.close()


def _run(
    config: RunConfig, *, open_test: bool, store: ResultsStore, reason: str | None
) -> dict[str, Any]:
    check_test_split_guard(config, open_test=open_test, store=store)

    git = git_state()
    if git.dirty:
        warnings.warn(
            "GIT WORKING TREE IS DIRTY. This run is recorded with git_dirty=1 and its "
            "git SHA does not describe the code that produced it. Commit before any "
            "run whose numbers you intend to keep.",
            stacklevel=3,
        )

    corpus = load_corpus()
    frame = load_split(config.split)
    slices = build_slices(frame)
    index, chunk_text = build_index(config)

    run_id = make_run_id(config)
    store.start_run(
        {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "name": config.name,
            "config_hash": config.config_hash,
            "config_json": json.dumps(config.as_dict()),
            "corpus_hash": corpus.corpus_hash,
            "normalization_version": corpus.normalization_version,
            "hf_revision": corpus.hf_revision,
            "dataset_config": config.split,
            "split": config.split,
            "split_hash": _split_hash(config.split),
            "git_sha": git.sha,
            "git_dirty": int(git.dirty),
            "eval_tier": config.eval_tier.value,
            "doc_pooling": config.doc_pooling,
            "chunker_id": index.chunker_id,
            "retriever": config.retriever,
            "top_k": config.top_k,
            "seed": config.seed,
            "generator_model": config.generator_model,
            "judge_model": config.judge_model,
            "prompt_versions": json.dumps(_prompt_versions(config)),
            "harness_smoke_test": int(config.harness_smoke_test),
            "status": "RUNNING",
        }
    )

    try:
        row = _execute(config, run_id, frame, index, chunk_text, slices, store, reason)
    except Exception as exc:
        # An abandoned run is recorded as VOID rather than left out. Silent gaps in
        # the ledger are what make a results document untrustworthy.
        store.finish_run(run_id, status="VOID", notes=f"{type(exc).__name__}: {exc}")
        raise
    return row


def _split_hash(split: str) -> str:
    from rag.dataset.splits import describe_split

    return describe_split(split)["split_hash"]


def _prompt_versions(config: RunConfig) -> dict[str, str]:
    if config.eval_tier is not EvalTier.TIER_2:
        return {}
    from rag.eval.judge import PROMPT_FOR_CRITERION

    versions = {"answer": config.generator_prompt}
    for criterion, (prompt_id, version) in PROMPT_FOR_CRITERION.items():
        versions[criterion] = f"{prompt_id}@{version}"
    return versions


def _execute(
    config: RunConfig,
    run_id: str,
    frame,
    index: ChunkIndex,
    chunk_text: dict[str, str],
    slices,
    store: ResultsStore,
    reason: str | None,
) -> dict[str, Any]:
    retriever = build_retriever(
        config.retriever,
        chunk_to_doc=index.chunk_to_doc,
        chunk_text=chunk_text,
        doc_pooling=config.doc_pooling,
        **config.retriever_params,
    )

    rows = frame.to_dict("records")
    results = [
        retriever.retrieve(row["question_id"], row["question"], top_k=config.retrieval_depth)
        for row in rows
    ]
    results_by_question = {result.question_id: result for result in results}

    qrels = qrels_from_split(frame)
    run_dict = run_from_results(results)

    per_question: dict[str, dict[str, Any]] = {row["question_id"]: {} for row in rows}
    aggregate: dict[str, Any] = {}

    # Tier 1 — retrieval only. Questions with no gold document are not scorable
    # here and are excluded from qrels (DEC-009); the unanswerable split therefore
    # produces no retrieval metrics at all, only Tier 2 refusal numbers.
    if qrels:
        retrieval = evaluate_retrieval(qrels, {q: run_dict[q] for q in qrels}, k_values=(1, 3, 5, 10, 20))
        aggregate.update(retrieval.aggregate)
        for question_id, metrics in retrieval.per_question.items():
            per_question[question_id].update(metrics)
        notes = dict(retrieval.notes)
        # A k larger than the deepest document list scores as if the tail were
        # missing, which reads as a ceiling in the metric rather than in the run.
        deepest = max((len(result.docs) for result in results), default=0)
        notes["max_docs_returned"] = deepest
        notes["k_values_capped_by_depth"] = [k for k in (1, 3, 5, 10, 20) if k > deepest]
        aggregate["retrieval_notes"] = notes

    generated: dict[str, Any] = {}
    if config.eval_tier is EvalTier.TIER_2:
        generated = _tier2(config, rows, results_by_question, chunk_text, per_question)
        aggregate.update(refusal_summary(per_question))
        for criterion in CRITERIA:
            values = [
                row[criterion] for row in per_question.values() if row.get(criterion) is not None
            ]
            if values:
                aggregate[criterion] = sum(values) / len(values)

    slice_report = aggregate_by_slice(per_question, slices)
    aggregate["slice_meta"] = slices.meta

    store.add_questions(
        [
            {
                "run_id": run_id,
                "question_id": row["question_id"],
                "retrieved_doc_ids": json.dumps(results_by_question[row["question_id"]].doc_ids),
                "retrieved_chunk_ids": json.dumps(results_by_question[row["question_id"]].chunk_ids),
                "scores": json.dumps([c.score for c in results_by_question[row["question_id"]].chunks]),
                "gold_doc_ids": json.dumps(list(row["gold_doc_ids"])),
                "metrics_json": json.dumps(per_question[row["question_id"]]),
                "generated_answer": generated.get(row["question_id"], {}).get("text"),
                "cited_doc_ids": json.dumps(generated.get(row["question_id"], {}).get("cited", [])),
                "latency_ms": generated.get(row["question_id"], {}).get("latency_ms", 0),
                "tokens_in": generated.get(row["question_id"], {}).get("tokens_in", 0),
                "tokens_out": generated.get(row["question_id"], {}).get("tokens_out", 0),
                "cost_usd": None,
            }
            for row in rows
        ]
    )

    store.finish_run(
        run_id,
        status="VALID",
        metrics=aggregate,
        slices=slice_report,
        n_questions=len(rows),
        notes=reason,
    )
    return store.get_run(run_id)


def _tier2(
    config: RunConfig,
    rows: list[dict[str, Any]],
    results_by_question: dict[str, Any],
    chunk_text: dict[str, str],
    per_question: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Generate answers and judge them. The only part of a run that costs money."""
    assembler = ConcatAssembler(max_tokens=config.context_max_tokens)
    generator = OpenRouterGenerator(GeneratorConfig(model=config.generator_model))
    judge = OpenRouterJudge(JudgeConfig(model=config.judge_model))

    generated: dict[str, Any] = {}
    for row in rows:
        question_id = row["question_id"]
        # Scoring saw `retrieval_depth` chunks; the generator sees `top_k` of them.
        context = assembler.assemble(
            results_by_question[question_id].chunks[: config.top_k], chunk_text
        )
        answer = generator.generate(row["question"], context.text)

        per_question[question_id].update(
            deterministic_metrics(
                generated_answer=answer.text,
                reference_answer=row["answer"],
                cited_doc_ids=answer.cited_doc_ids,
                gold_doc_ids=list(row["gold_doc_ids"]),
            )
        )
        scores = judge_all_criteria(
            judge,
            question=row["question"],
            answer=answer.text,
            context=context.text,
            reference_answer=row["answer"],
        )
        for criterion, score in scores.items():
            per_question[question_id][criterion] = score.score

        generated[question_id] = {
            "text": answer.text,
            "cited": answer.cited_doc_ids,
            "latency_ms": answer.latency_ms,
            "tokens_in": answer.tokens_in + sum(s.tokens_in for s in scores.values()),
            "tokens_out": answer.tokens_out + sum(s.tokens_out for s in scores.values()),
        }
    return generated
