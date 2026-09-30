"""`run(config) -> row in the results store` — P0-09 and P0-10.

The runner owns provenance, tiering and recording. It owns no technique: retrievers
arrive through the registry, and the generator and judge through config.
"""

from __future__ import annotations

import json
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from rag.assembly import ConcatAssembler, build_compressor
from rag.chunking.base import Chunker, build_chunker, chunker_class
from rag.chunking.index_map import ChunkIndex
from rag.corpus.loader import load_corpus
from rag.dataset.loader import load_split
from rag.eval.generation_metrics import deterministic_metrics, refusal_summary
from rag.eval.judge import CRITERIA, JudgeConfig, RagasJudge, judge_provenance
from rag.eval.qrels import qrels_from_split, run_from_results
from rag.eval.retrieval_metrics import evaluate_retrieval
from rag.eval.slices import aggregate_by_slice, build_slices
from rag.eval.generation_metrics import span_support
from rag.generation.base import (
    CITATION_PARSER_VERSION,
    GeneratorConfig,
    OpenRouterGenerator,
    extract_citations,
    extract_span_citations,
)
from rag.generation.grounding import GroundednessCheck
from rag.generation.cache import GenerationCache
from rag.generation.pipeline_llm import PipelineLLM
from rag.hashing import short_id
from rag.prompts import load_prompt
from rag.runner.config import EvalTier, RunConfig
from rag.runner.cost import (
    estimate_grounding_cost,
    estimate_query_transform_cost,
    estimate_chunker_llm_cost,
    estimate_compression_cost,
    COST_GATE_USD,
    CostGateError,
    PricingTable,
    actual_run_cost,
    estimate_index_cost,
    estimate_rerank_cost,
    estimate_run_cost,
    estimate_tier2_cost,
    format_estimate,
    format_run_estimate,
)
from rag.runner.model_check import format_checks, verify_config_models
from rag.runner.promoted import check_split_policy, config_diff, load_promoted
from rag.retrieval.query_transform import TransformingRetriever, build_transform
from rag.runner.registry import build_reranker, build_retriever, reranker_class, retriever_class
from rag.runner.store import ResultsStore
from rag.runner.subsample import build_subsample

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


def check_test_split_guard(
    config: RunConfig, *, open_test: bool, store: ResultsStore, reason: str | None = None
) -> None:
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
    if not (reason or "").strip():
        raise PermissionError(
            "opening the test split requires --reason. It is written into the "
            "openings log in docs/DECISIONS.md, and 'no reason' is not a reason."
        )
    previous = store.test_openings()
    print("\n*** OPENING THE TEST SPLIT ***")
    print(f"    previous openings: {len(previous)}")
    if previous:
        print(f"    last opening:      {previous[-1]['timestamp']} ({previous[-1]['run_id']})")
    print("    this opening will be appended to docs/DECISIONS.md.\n")


def build_index(
    config: RunConfig,
    chunker: Chunker | None = None,
    *,
    generation_cache: GenerationCache | None = None,
) -> tuple[ChunkIndex, dict[str, str]]:
    """Chunk the frozen corpus with the configured chunker (P2-07: named in
    `config.chunker`, built through the chunker registry). Returns the index and
    the text the retriever indexes; the generator's per-chunk context is
    `index.context_text`."""
    corpus = load_corpus()
    chunker = chunker or build_chunker(
        config.chunker, generation_cache=generation_cache, **config.chunker_params
    )
    chunks = chunker.split_corpus(list(zip(corpus.frame["id"], corpus.frame["indexed_text"])))
    index = ChunkIndex(
        chunks=chunks,
        chunker_id=chunker.chunker_id,
        chunker_params=chunker.params,
        corpus_hash=corpus.corpus_hash,
        normalization_version=corpus.normalization_version,
    )
    return index, index.chunk_text


def run(
    config: RunConfig,
    *,
    open_test: bool = False,
    store: ResultsStore | None = None,
    reason: str | None = None,
    generation_cache: GenerationCache | None = None,
    allow_leaky_split: bool = False,
    approve_cost: str = "",
    pricing: PricingTable | None = None,
    estimate_only: bool = False,
) -> dict[str, Any]:
    """Execute one experiment and record it. Returns the finished `runs` row.

    `generation_cache` backs any in-pipeline LLM call (P2-03); the default is the
    shared cache under results/. It is not part of the config — a cold cache
    changes cost and reproducibility, never the configuration being tested.
    `allow_leaky_split` overrides the P2-04 split policy (the run is then marked
    leakage-affected); `approve_cost` is the recorded approval that lets a run
    estimated above the $2 gate proceed (P2-06).
    """
    owns_store = store is None
    store = store or ResultsStore()
    owns_cache = generation_cache is None
    generation_cache = generation_cache or GenerationCache()
    try:
        return _run(
            config, open_test=open_test, store=store, reason=reason, generation_cache=generation_cache,
            allow_leaky_split=allow_leaky_split, approve_cost=approve_cost,
            pricing=pricing or PricingTable.load(), estimate_only=estimate_only,
        )
    finally:
        if owns_store:
            store.close()
        if owns_cache:
            generation_cache.close()


def _run(
    config: RunConfig,
    *,
    open_test: bool,
    store: ResultsStore,
    reason: str | None,
    generation_cache: GenerationCache,
    allow_leaky_split: bool,
    approve_cost: str,
    pricing: PricingTable,
    estimate_only: bool = False,
) -> dict[str, Any]:
    check_test_split_guard(config, open_test=open_test, store=store, reason=reason)
    policy = check_split_policy(config, allow_leaky_split=allow_leaky_split)
    if policy["note"]:
        warnings.warn(policy["note"], stacklevel=3)

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
    split_hash = _split_hash(config.split)

    # Tier 1 is free and always scores the whole split. Tier 2 scores a fixed
    # subsample unless full_eval is set (P0-09).
    if config.eval_tier is EvalTier.TIER_2:
        subsample = build_subsample(
            frame,
            size=config.eval_subsample_size,
            seed=config.eval_subsample_seed,
            split_hash=split_hash,
            full=config.full_eval,
        )
        frame = frame[frame["question_id"].isin(subsample.question_ids)].reset_index(drop=True)
        cost_estimate = _cost_estimate(config, frame, pricing)
        print(format_estimate(cost_estimate))
    else:
        cost_estimate = {}
        subsample = build_subsample(
            frame, size=len(frame), seed=config.eval_subsample_seed,
            split_hash=split_hash, full=True,
        )

    slices = build_slices(frame)
    judge_meta = (
        judge_provenance(_judge_config(config))
        if config.eval_tier is EvalTier.TIER_2 and not config.skip_judge
        else {}
    )

    # P2-06 — the whole-run estimate, printed with what drives it, gated at $2.
    # Full-corpus embedding for an uncached index is the dominant cost in this
    # project, so the index build is estimated before anything is spent.
    #
    # P2-07: a chunker may itself embed the corpus before any chunk exists (the
    # semantic chunker embeds every sentence to find its boundaries). That is a
    # pre-spend, so it is estimated from the corpus text and gated *before* the
    # chunker runs — otherwise the gate would fire after the money was spent.
    # Chunkers that embed nothing are chunked first and the index estimate uses
    # the exact indexed word count, as before.
    #
    # P2-13: a chunker may instead spend on an **LLM** before any chunk exists
    # (contextual retrieval makes one call per chunk across the corpus). Same shape
    # of problem, same answer: the workload is counted from a free split, estimated,
    # and gated before the first call. Getting this wrong would mean the gate fires
    # after the most expensive spend in the phase had already happened.
    chunker = build_chunker(
        config.chunker, generation_cache=generation_cache, **config.chunker_params
    )
    chunker_embeds = chunker_class(config.chunker).embedding_params(config.chunker_params)
    corpus_docs = dict(zip(load_corpus().frame["id"], load_corpus().frame["indexed_text"]))
    corpus_words = sum(len(t.split()) for t in corpus_docs.values())
    chunker_workload = chunker.llm_workload(corpus_docs)
    chunker_llm_estimate = estimate_chunker_llm_cost(chunker_workload, pricing=pricing)
    chunker_estimate: dict[str, Any] = {}
    if chunker_embeds is not None:
        chunker_estimate = estimate_index_cost(
            retriever=config.chunker,
            retriever_params=chunker_embeds,
            corpus_words=corpus_words,
            index_exists=_chunker_cache_exists(chunker),
            n_questions=0,
            pricing=pricing,
        )
    if chunker_embeds is None and chunker_workload is None:
        index, chunk_text = build_index(config, chunker)
        indexed_words = sum(len(text.split()) for text in chunk_text.values())
    else:
        index, chunk_text = None, None
        # Every chunker in this axis that embeds has no overlap, so its indexed
        # words equal the corpus words; that is the estimate's basis. A chunker that
        # spends on an LLM counts its own indexed words instead, because contextual
        # retrieval indexes the chunks *plus* every generated prefix.
        indexed_words = (chunker_workload or {}).get("indexed_words") or corpus_words
    index_estimate = estimate_index_cost(
        retriever=config.retriever,
        retriever_params=retriever_class(config.retriever).embedding_params(config.retriever_params),
        corpus_words=indexed_words,
        index_exists=_dense_index_exists(config, chunker_id=chunker.chunker_id),
        n_questions=len(frame),
        pricing=pricing,
    )
    if chunker_estimate.get("index_usd"):
        index_estimate["chunker_embedding_usd"] = chunker_estimate["index_usd"]
        index_estimate["chunker_source"] = f"{config.chunker}: {chunker_estimate['source']}"
        index_estimate["index_usd"] = round(index_estimate.get("index_usd", 0.0) + chunker_estimate["index_usd"], 4)
    # P2-10: reranking is billed **per query**, so unlike an index build it scales
    # with the split — the same config is cents on `dev` and dollars on `dev_large`.
    # It is estimated here, before the gate, from measured provider rates (MIS-025).
    rerank_estimate = estimate_rerank_cost(
        reranker=config.reranker,
        estimate_params=(
            reranker_class(config.reranker).estimate_params(config.reranker_params)
            if config.reranker else None
        ),
        n_questions=len(frame),
        candidate_docs=config.rerank_candidates,
        candidate_words=_mean_candidate_words(config, chunk_text),
        pricing=pricing,
    )
    # P2-13: contextual compression bills one call per retrieved chunk per question,
    # so like reranking it scales with the split rather than with the corpus.
    compression_estimate = (
        estimate_compression_cost(
            compressor=config.context_compressor,
            compressor_params=config.context_compressor_params,
            n_questions=len(frame),
            chunks_per_question=config.top_k,
            chunk_words=_mean_candidate_words(config, chunk_text),
            prompt_overhead_words=_COMPRESSOR_PROMPT_WORDS,
            pricing=pricing,
        )
        if config.eval_tier is EvalTier.TIER_2
        else {}
    )
    # P2-12: one LLM call per question, billed per query like reranking, so it scales
    # with the split. `queries_per_question` is what the transform will send to the
    # retriever, which drives the extra query embeddings.
    transform_estimate = _query_transform_estimate(config, frame, pricing)
    # P2-14: the self-check is a second LLM call per ANSWERED question, billed per query.
    grounding_estimate = estimate_grounding_cost(
        grounding_check=config.grounding_check,
        grounding_params=config.grounding_check_params,
        n_questions=len(frame),
        pricing=pricing,
    ) if config.eval_tier is EvalTier.TIER_2 else {}
    run_estimate = estimate_run_cost(
        tier2=cost_estimate or None,
        index=index_estimate,
        rerank=rerank_estimate,
        chunker_llm=chunker_llm_estimate,
        compression=compression_estimate,
        query_transform=transform_estimate,
        grounding=grounding_estimate,
    )
    run_estimate["index"] = index_estimate
    if config.reranker:
        run_estimate["rerank"] = rerank_estimate
    if chunker_llm_estimate:
        run_estimate["chunker_llm"] = chunker_llm_estimate
    if compression_estimate:
        run_estimate["compression"] = compression_estimate
    if transform_estimate:
        run_estimate["query_transform"] = transform_estimate
    if grounding_estimate:
        run_estimate["grounding"] = grounding_estimate
    print(format_run_estimate(run_estimate, pricing_version=pricing.pricing_version))
    _print_running_totals(store)
    if estimate_only:
        return {"estimate_only": True, "config_hash": config.config_hash, **run_estimate}
    if run_estimate["over_gate"] and not approve_cost.strip():
        raise CostGateError(
            f"estimated ${run_estimate['total_usd']:.4f} is above the ${COST_GATE_USD:.2f} gate"
            + (f" (or a price is unavailable: {run_estimate['unavailable']})" if run_estimate["unavailable"] else "")
            + ". The run has not started and nothing was recorded. Get approval, record it in "
            "docs/DECISIONS.md, and re-run with --approve-cost '<DEC-NNN or reason>' (P2-06)."
        )
    # P3-02: a retired slug or a provider that stopped serving it fails here, before the
    # first paid call, rather than as a 404 halfway through the questions.
    model_checks = verify_config_models(config)
    if model_checks:
        print(format_checks(model_checks))
    if index is None:
        index, chunk_text = build_index(config, chunker, generation_cache=generation_cache)
    chunking_profile = index.profile(corpus_docs)
    if config.axis and not config.harness_smoke_test:
        n_axis = len(store.axis_experiments(config.axis))
        if n_axis >= 5 and config.config_hash not in store.axis_experiments(config.axis):
            warnings.warn(
                f"axis {config.axis!r} already has {n_axis} recorded experiments; the cap is 5 "
                "(P2-06 / Phase 2 rule 1). Note further variants in HYPOTHESES.md instead.",
                stacklevel=3,
            )

    # P2-05 — every axis experiment is a diff against configs/promoted.yaml; the
    # diff is recorded so "one dimension" is a fact on the row, not a claim.
    vs_promoted: dict[str, Any] = {}
    if config.axis:
        vs_promoted = config_diff(config, load_promoted())
        if not vs_promoted["one_dimension"] and config.axis != "combination":
            warnings.warn(
                f"config changes {vs_promoted['dimensions']} vs promoted.yaml; a {config.axis!r} "
                "experiment changes one dimension (P2-05). Only `combination` runs may change several.",
                stacklevel=3,
            )

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
            "split_hash": split_hash,
            "git_sha": git.sha,
            "git_dirty": int(git.dirty),
            "eval_tier": config.eval_tier.value,
            "eval_subsample_id": subsample.subsample_id,
            "doc_pooling": config.doc_pooling,
            "chunker_id": index.chunker_id,
            "chunker_meta": json.dumps({"chunker": config.chunker, "params": index.chunker_params,
                                        "profile": chunking_profile, **chunker.provenance()}, default=str),
            "retriever": config.retriever,
            "reranker": config.reranker or None,
            "top_k": config.top_k,
            "seed": config.seed,
            "generator_model": config.generator_model,
            "judge_model": config.judge_model,
            "judge_family": judge_meta.get("judge_family"),
            "judge_temperature": judge_meta.get("judge_temperature"),
            "judge_embedding_model": judge_meta.get("judge_embedding_model"),
            "judge_provider_order": json.dumps(judge_meta.get("judge_provider_order", [])),
            "ragas_version": judge_meta.get("ragas_version"),
            "prompt_versions": json.dumps(_prompt_versions(config)),
            "metric_prompt_versions": json.dumps(judge_meta.get("metric_prompt_versions", {})),
            "harness_smoke_test": int(config.harness_smoke_test),
            "status": "RUNNING",
            "axis": config.axis or None,
            "leakage_affected": int(policy["leakage_affected"]),
            "promoted_config_hash": vs_promoted.get("promoted_config_hash"),
            "vs_promoted_json": json.dumps(vs_promoted) if vs_promoted else None,
            "pricing_version": pricing.pricing_version,
            "cost_estimate_usd": run_estimate["total_usd"],
            "cost_estimate_json": json.dumps(run_estimate, default=str),
            "cost_approval": approve_cost.strip() or None,
        }
    )
    if approve_cost.strip():
        from rag.runner.cost_approvals import record_cost_approval

        record_cost_approval(
            run_id=run_id, config_hash=config.config_hash, estimate_usd=run_estimate["total_usd"],
            driver=run_estimate["driver"] or "-", approval=approve_cost, git_sha=git.sha,
        )

    if config.split == HELD_OUT_SPLIT:
        from rag.runner.test_openings import record_test_opening

        count = record_test_opening(
            config_hash=config.config_hash, git_sha=git.sha, reason=reason or "", run_id=run_id
        )
        print(f"    recorded as test-split opening #{count} in docs/DECISIONS.md\n")

    try:
        row = _execute(
            config, run_id, frame, index, chunk_text, slices, store, reason, cost_estimate,
            generation_cache, pricing, chunking_profile, chunker,
        )
    except Exception as exc:
        # An abandoned run is recorded as VOID rather than left out. Silent gaps in
        # the ledger are what make a results document untrustworthy.
        store.finish_run(run_id, status="VOID", notes=f"{type(exc).__name__}: {exc}")
        raise
    return row


def _selection_summary(per_question: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Run-level collapse ratio (mean, p90) and pool exhaustion rate (P1-03)."""
    ratios = sorted(
        row["collapse_ratio"] for row in per_question.values() if row.get("collapse_ratio") is not None
    )
    exhausted = [row["pool_exhausted"] for row in per_question.values() if "pool_exhausted" in row]
    summary: dict[str, Any] = {
        "collapse_ratio_mean": (sum(ratios) / len(ratios)) if ratios else None,
        "collapse_ratio_p90": ratios[int(0.9 * (len(ratios) - 1))] if ratios else None,
        "pool_exhaustion_rate": (sum(exhausted) / len(exhausted)) if exhausted else None,
    }
    return summary


def _split_hash(split: str) -> str:
    from rag.dataset.loader import describe_split

    return describe_split(split)["split_hash"]


def _prompt_versions(config: RunConfig) -> dict[str, str]:
    """Our own prompts only. Ragas manages the judge prompts internally, so those are
    fingerprinted as `metric_prompt_versions` instead."""
    if config.eval_tier is not EvalTier.TIER_2:
        return {}
    return {"answer": config.generator_prompt}


def _judge_config(config: RunConfig) -> JudgeConfig:
    return JudgeConfig(
        model=config.judge_model,
        temperature=config.judge_temperature,
        embedding_model=config.judge_embedding_model,
        max_tokens=config.judge_max_tokens,
        provider_order=tuple(config.judge_provider_order),
        provider_allow_fallbacks=config.judge_allow_fallbacks,
        concurrency=config.judge_concurrency,
    )


def _cost_estimate(config: RunConfig, frame, pricing: PricingTable) -> dict:
    # The generator's context is top_k chunks of whatever the chunker hands it; a
    # chunker without `chunk_size` (P2-07) is estimated at the control's 600 words.
    context_words = config.top_k * int(
        config.chunker_params.get("chunk_size") or config.chunker_params.get("parent_size")
        or config.chunker_params.get("max_words") or 600
    )
    n_judged = int((frame["answer"].fillna("").str.strip() != "").sum()) if "answer" in frame else len(frame)
    return estimate_tier2_cost(
        n_questions=len(frame),
        # DEC-063: no judge means no judged questions, so the estimate's judge half is
        # zero rather than a cost nobody will be charged.
        n_judged=0 if config.skip_judge else n_judged,
        context_words=context_words,
        generator_model=config.generator_model,
        judge_model=config.judge_model,
        judge_provider_order=tuple(config.judge_provider_order),
        pricing=pricing,
    )


# Words of scaffolding in the compressor's prompt, measured from the rendered
# template rather than guessed, so the per-call estimate is the real input size.
_COMPRESSOR_PROMPT_WORDS = len(
    load_prompt("compress_context", "v1").render(question="", passage="", empty_marker="").split()
)


# Words the model is asked to produce, per transform. Measured from the prompts'
# own caps rather than guessed, and replaced by an actual after the first run.
_TRANSFORM_OUTPUT_WORDS = {
    "decompose": 60,      # up to max_parts short questions
    "hyde": 120,          # the prompt's max_words
    "multi_query": 60,    # n rewrites
    "step_back": 20,      # one question
}
# How many query strings each transform sends to the retriever, including the
# original where it keeps it. Drives the extra query-embedding count.
_TRANSFORM_QUERIES = {"decompose": 2.5, "hyde": 1.0, "multi_query": 4.0, "step_back": 2.0}


def _query_transform_estimate(config: RunConfig, frame, pricing: PricingTable) -> dict[str, Any]:
    if not config.query_transform:
        return {}
    from rag.retrieval.query_transform import QUERY_TRANSFORMS

    transform_cls = QUERY_TRANSFORMS[config.query_transform]
    prompt = load_prompt(transform_cls.prompt_id, transform_cls.prompt_version)
    # The scaffolding, measured off the rendered template with the fields blank.
    fields = {"question": ""} | {
        k: 0 for k in ("max_parts", "max_words", "n") if "{" + k + "}" in prompt.template
    }
    overhead = len(prompt.render(**fields).split())
    questions = [str(q) for q in frame["question"]] if "question" in frame else []
    mean_question_words = (
        round(sum(len(q.split()) for q in questions) / len(questions)) if questions else 20
    )
    return estimate_query_transform_cost(
        query_transform=config.query_transform,
        transform_params=config.query_transform_params,
        n_questions=len(frame),
        prompt_overhead_words=overhead,
        question_words=mean_question_words,
        output_words=_TRANSFORM_OUTPUT_WORDS[config.query_transform],
        queries_per_question=_TRANSFORM_QUERIES[config.query_transform],
        pricing=pricing,
    )


def _merge_pipeline_stats(stats: list[dict[str, Any]]) -> dict[str, Any]:
    """One summary row for however many in-pipeline LLMs a run held (P2-03).

    Calls, hits and tokens add up; `model` is a list when they differ, because
    reporting one model's id over another's tokens would be a false provenance.
    """
    if len(stats) == 1:
        return stats[0]
    models = sorted({s["model"] for s in stats})
    calls = sum(s["calls"] for s in stats)
    hits = sum(s["cache_hits"] for s in stats)
    return {
        "model": models[0] if len(models) == 1 else models,
        "temperature": stats[0]["temperature"],
        "calls": calls,
        "cache_hits": hits,
        "cache_misses": sum(s["cache_misses"] for s in stats),
        "hit_rate": (hits / calls) if calls else None,
        "tokens_in": sum(s["tokens_in"] for s in stats),
        "tokens_out": sum(s["tokens_out"] for s in stats),
        "prompts": sorted({p for s in stats for p in s["prompts"]}),
        "sources": len(stats),
    }


def _mean_candidate_words(config: RunConfig, chunk_text: dict[str, str] | None) -> int:
    """Mean words per indexed chunk, for the rerank estimate — measured off the
    chunk index when it exists, else the chunker's configured size, which is an
    over-estimate and so errs towards firing the gate rather than missing it."""
    if chunk_text:
        return max(1, round(sum(len(t.split()) for t in chunk_text.values()) / len(chunk_text)))
    params = config.chunker_params
    return int(params.get("chunk_size") or params.get("parent_size") or params.get("max_words") or 600)


def _chunker_cache_exists(chunker: Chunker) -> bool:
    """Whether a chunker that embeds (semantic) already has its sentence distances
    on disk for this embedder — True for chunkers that embed nothing."""
    path = getattr(chunker, "cache_path", None)
    return True if path is None else Path(path).exists()


def _dense_index_exists(config: RunConfig, *, chunker_id: str) -> bool:
    """Whether the dense index this config needs is already on disk — the difference
    between a ~$0.03 run and a full-corpus embed (P2-06). True for retrievers that
    embed nothing; a retriever that wraps a dense one (hybrid) is asked for its
    embedder settings rather than matched by name. Takes the chunker id rather than
    a built index so it can run before the chunker has (P2-07)."""
    from rag.embedding.base import EmbedderConfig, build_embedder
    from rag.paths import INDEXES_DIR
    from rag.retrieval.dense import VECTORS_FILE, index_key
    from rag.runner.registry import retriever_class

    params = retriever_class(config.retriever).embedding_params(config.retriever_params)
    if params is None or params.get("embedder") is not None:
        return True
    embedder = build_embedder(
        params.get("embedding_backend", "openrouter"),
        EmbedderConfig(
            model=params.get("embedding_model", ""),
            revision=params.get("embedding_revision", ""),
            provider=params.get("embedding_provider", ""),
            prefix_convention=params.get("prefix_convention"),
            dimensions=params.get("dimensions"),
        ),
    )
    corpus = load_corpus()
    key = index_key(
        corpus_hash=corpus.corpus_hash,
        normalization_version=corpus.normalization_version,
        chunker_id=chunker_id,
        model_id=embedder.model_id,
        revision=embedder.pinned_identity,
        prefix_convention=embedder.prefix.name,
        dimensions=embedder.config.dimensions,
    )
    index_dir = Path(params["index_dir"]) if params.get("index_dir") else INDEXES_DIR / key
    return (index_dir / VECTORS_FILE).exists()


def _print_running_totals(store: ResultsStore) -> None:
    """P2-06: spend so far, every run. Actual where recorded, else the estimate."""
    rows = store.cost_rows()
    phase2 = [r for r in rows if r["axis"]]
    def total(items):
        return sum((r["cost_actual_usd"] if r["cost_actual_usd"] is not None else r["cost_estimate_usd"] or 0.0) for r in items)
    print(f"    running totals: Phase 2 (axis runs) ${total(phase2):.4f} over {len(phase2)} runs; "
          f"all recorded runs ${total(rows):.4f} over {len(rows)} runs")


def _estimate_drift(store: ResultsStore) -> dict[str, Any] | None:
    """Actual / estimate over runs that have both. Flagged when the median ratio
    over three or more runs is outside 0.75–1.33 — the estimator is then
    systematically wrong, not just noisy, and needs recalibrating (DEC-035)."""
    ratios = [
        r["cost_actual_usd"] / r["cost_estimate_usd"]
        for r in store.cost_rows()
        if r["cost_actual_usd"] is not None and r["cost_estimate_usd"] and r["cost_estimate_usd"] > 0.001
    ]
    if len(ratios) < 3:
        return None
    ordered = sorted(ratios)
    median = ordered[len(ordered) // 2]
    return {"n": len(ratios), "median_ratio": round(median, 3), "drift": not 0.75 <= median <= 1.33}


def _execute(
    config: RunConfig,
    run_id: str,
    frame,
    index: ChunkIndex,
    chunk_text: dict[str, str],
    slices,
    store: ResultsStore,
    reason: str | None,
    cost_estimate: dict[str, Any],
    generation_cache: GenerationCache,
    pricing: PricingTable,
    chunking_profile: dict[str, Any] | None = None,
    # P2-13: only for its `pipeline_llm` — the contextual chunker calls a model to
    # build the index, so the chunker is a call site like the retriever and reranker.
    chunker: Chunker | None = None,
) -> dict[str, Any]:
    # DEC-084: when `rag ci-eval` switched the call cache on, this run's share of its hits
    # and misses goes on the row, so a replayed run never passes for a fresh measurement.
    from rag.call_cache import active as active_call_cache

    call_cache = active_call_cache()
    call_cache_before = dict(call_cache.stats) if call_cache is not None else None
    retriever = build_retriever(
        config.retriever,
        chunk_to_doc=index.chunk_to_doc,
        chunk_text=chunk_text,
        doc_pooling=config.doc_pooling,
        index=index,
        generation_cache=generation_cache,
        **config.retriever_params,
    )
    # P2-12, Axis 4. A query transform wraps the retriever rather than replacing it:
    # `config.retriever` still names the real one, so the axis diff is one dimension
    # and pooling, the document walk and the collapse ratio stay the base class's.
    if config.query_transform:
        params = dict(config.query_transform_params)
        model = params.pop("model", "")
        workers = int(params.pop("prewarm_workers", 16))
        transform = build_transform(
            config.query_transform,
            PipelineLLM(model, cache=generation_cache, max_tokens=int(params.pop("max_tokens", 600))),
            **params,
        )
        # Generate every question's transform in one concurrent batch BEFORE the loop
        # (MIS-036): 200 sequential round trips is 15+ minutes a run, and the loop then
        # runs entirely from cache.
        transform.prewarm([row["question"] for row in frame.to_dict("records")], workers=workers)
        retriever = TransformingRetriever(retriever, transform)

    store.update_run(run_id, retriever_meta=json.dumps(retriever.provenance(), default=str))
    # P2-10, Axis 5. The reranker is the runner's, not the retriever's: it re-orders
    # a candidate set that any retriever produced, and pooling, the distinct-document
    # walk and every metric are then recomputed from the reranked ranking.
    reranker = (
        build_reranker(
            config.reranker,
            chunk_text=chunk_text,
            generation_cache=generation_cache,
            # P2-13: a reranker that works in the retriever's vector space (MMR) asks
            # the retriever for candidate embeddings rather than building its own.
            # Rerankers that do not need them ignore it.
            vector_source=retriever,
            **config.reranker_params,
        )
        if config.reranker
        else None
    )
    if reranker is not None:
        store.update_run(run_id, reranker_meta=json.dumps(reranker.provenance(), default=str))
    # P2-07: the generator sees each chunk's context (`context_text`), which the
    # "retrieve small, expand" chunkers make larger than the indexed text.
    context_text = index.context_text

    import time

    rows = frame.to_dict("records")
    results = []
    retrieval_latency_ms: dict[str, int] = {}
    rerank_latency_ms: dict[str, int] = {}
    rerank_records: dict[str, dict[str, Any]] = {}
    for row in rows:
        started = time.perf_counter()
        result = retriever.retrieve(
            row["question_id"],
            row["question"],
            top_k=config.retrieval_depth,
            k_docs=config.top_k,
            candidate_pool=config.candidate_pool,
        )
        retrieval_latency_ms[row["question_id"]] = int((time.perf_counter() - started) * 1000)
        if reranker is not None:
            from rag.reranking.base import rerank_result

            started = time.perf_counter()
            result, record = rerank_result(
                result,
                reranker,
                query=row["question"],
                chunk_to_doc=index.chunk_to_doc,
                n_docs=config.rerank_candidates,
                k_docs=config.top_k,
                candidate_pool=config.candidate_pool,
                doc_pooling=config.doc_pooling,
            )
            rerank_latency_ms[row["question_id"]] = int((time.perf_counter() - started) * 1000)
            rerank_records[row["question_id"]] = record
        results.append(result)
    results_by_question = {result.question_id: result for result in results}
    # Re-record after the queries so a hosted embedder's usage covers the whole run.
    store.update_run(run_id, retriever_meta=json.dumps(retriever.provenance(), default=str))

    qrels = qrels_from_split(frame)
    run_dict = run_from_results(results)

    per_question: dict[str, dict[str, Any]] = {row["question_id"]: {} for row in rows}
    aggregate: dict[str, Any] = {}

    # P1-03 — the context is top_k distinct documents. How many chunks the walk
    # scanned per document found is the collapse ratio; stopping on the pool cap
    # without reaching top_k is exhaustion. `gold_in_context` is whether every gold
    # document reached the generator — the input-side fact OQ-019's refusal metrics
    # need — and is None where there is no gold (the unanswerable split).
    for row in rows:
        selection = results_by_question[row["question_id"]].context
        gold = set(row["gold_doc_ids"])
        per_question[row["question_id"]].update(
            {
                "collapse_ratio": selection.collapse_ratio,
                "pool_exhausted": float(selection.exhausted),
                "context_docs": float(len(selection.doc_ids)),
                "gold_in_context": (float(gold <= set(selection.doc_ids)) if gold else None),
            }
        )
    # P2-12: sub-queries per question and the distinct-document yield per sub-query,
    # both required by the story, recorded per question rather than as an average.
    if config.query_transform:
        by_question = getattr(retriever, "per_question", {})
        for row in rows:
            record = by_question.get(row["question"])
            if record:
                per_question[row["question_id"]].update({
                    "n_queries": float(record["n_queries"]),
                    "n_generated": float(record["n_generated"]),
                    "transform_fell_back": record["fell_back"],
                    "distinct_docs_total": float(record["distinct_docs_total"]),
                })
        aggregate["query_transform"] = config.query_transform
        aggregate["query_transform_profile"] = retriever.transform.provenance()
        yields = [
            y for record in by_question.values()
            for y in record["distinct_doc_yield_per_query"][1:]
        ]
        aggregate["mean_new_docs_per_extra_query"] = (
            round(sum(yields) / len(yields), 3) if yields else None
        )
    for question_id, record in rerank_records.items():
        per_question[question_id].update(record)
    if reranker is not None:
        store.update_run(run_id, reranker_meta=json.dumps(reranker.provenance(), default=str))
        aggregate["reranker"] = config.reranker
        aggregate["rerank_candidates"] = config.rerank_candidates
        aggregate["rerank_profile"] = reranker.provenance()
    aggregate.update(_selection_summary(per_question))
    aggregate["chunking_profile"] = chunking_profile

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
    compression_llms: list[dict[str, Any]] = []
    if config.eval_tier is EvalTier.TIER_2:
        generated = _tier2(
            config, rows, results_by_question, context_text, per_question, generation_cache
        )
        judge_failures = generated.pop("__judge_failures__", [])
        # P2-13 — assembly's own record. Popped before `generated` is read per
        # question, since these keys are not question ids.
        aggregate["assembly_profile"] = generated.pop("__assembly__", {})
        grounding_profile = generated.pop("__grounding__", None)
        if grounding_profile is not None:
            aggregate["grounding_check"] = config.grounding_check
            aggregate["grounding_profile"] = grounding_profile
            aggregate["grounding_rejection_rate"] = grounding_profile.get("rejection_rate")
            compression_llms.append(grounding_profile["llm"])
        spans = [r["span_support"] for r in per_question.values()
                 if r.get("span_support") is not None]
        if spans:
            aggregate["span_support"] = sum(spans) / len(spans)
            aggregate["span_support_n"] = len(spans)
        compression_profile = generated.pop("__compression__", None)
        if compression_profile is not None:
            aggregate["compression_profile"] = compression_profile
            aggregate["context_compressor"] = config.context_compressor
            aggregate["context_word_reduction"] = compression_profile.get("word_reduction")
            compression_llms.append(compression_profile["llm"])
        aggregate["judge_failures"] = len(judge_failures)
        aggregate["judge_failure_detail"] = judge_failures
        aggregate.update(refusal_summary(per_question))
        aggregate["citation_parser"] = CITATION_PARSER_VERSION
        aggregate["judge_skipped_no_reference"] = int(
            sum(row.get("judge_skipped_no_reference", 0) for row in per_question.values())
        )
        # DEC-063 — a Tier 2 run without a judge. Recorded affirmatively, because a
        # row with no faithfulness number and no explanation reads as a broken judge.
        if config.skip_judge:
            aggregate["skip_judge"] = True
            aggregate["skipped_criteria"] = list(CRITERIA)
            aggregate["judge_skipped_by_config"] = int(
                sum(row.get("judge_skipped_by_config", 0) for row in per_question.values())
            )
        for criterion in CRITERIA:
            values = [
                row[criterion] for row in per_question.values() if row.get(criterion) is not None
            ]
            if values:
                aggregate[criterion] = sum(values) / len(values)

    # P0-13 asks for p95 latency and cost per query on the baseline row. Retrieval
    # latency is measured per question; generation latency is added in Tier 2. Cost
    # per query is exactly zero in Tier 1 — no LLM is called — and in Tier 2 is the
    # pre-run estimate divided by questions, labelled as such.
    latencies = sorted(
        retrieval_latency_ms[qid]
        + rerank_latency_ms.get(qid, 0)
        + generated.get(qid, {}).get("latency_ms", 0)
        for qid in retrieval_latency_ms
    )
    aggregate["p95_latency_ms"] = latencies[int(0.95 * (len(latencies) - 1))] if latencies else None
    retried = sum(1 for g in generated.values() if isinstance(g, dict) and g.get("attempts", 1) > 1)
    if config.eval_tier is EvalTier.TIER_2:
        aggregate["generation_retries_questions"] = retried
        if config.generator_fallback_models:
            # P3-14: which model in the chain actually answered, per question count.
            served: dict[str, int] = {}
            for g in generated.values():
                if isinstance(g, dict) and "served_model" in g:
                    served[g["served_model"]] = served.get(g["served_model"], 0) + 1
            aggregate["generator_served_models"] = served
    aggregate["p50_latency_ms"] = latencies[len(latencies) // 2] if latencies else None
    # Tier 1 makes no LLM calls, but a hosted embedder charges for query vectors;
    # that is exact (provider-reported) and the one-time index build is recorded
    # separately in retriever_meta rather than folded into a per-query figure.
    query_cost = retriever.query_cost_usd() + (reranker.query_cost_usd() if reranker else 0.0)
    if config.eval_tier is EvalTier.TIER_1:
        # 8 places: a query embedding costs ~$0.0000004 and would round to zero at 6.
        aggregate["cost_per_query_usd"] = round(query_cost / len(rows), 8) if rows else 0.0
        aggregate["cost_per_query_source"] = (
            "exact: Tier 1 makes no LLM calls" if query_cost == 0
            else "exact: provider-reported per-query cost (embeddings and/or rerank); "
                 "index build cost in retriever_meta"
        )
    elif "total_usd" in cost_estimate and rows:
        aggregate["cost_per_query_usd"] = round((cost_estimate["total_usd"] + query_cost) / len(rows), 5)
        aggregate["cost_per_query_source"] = "estimate: pre-run cost estimate / questions, plus exact query embedding cost"
    else:
        aggregate["cost_per_query_usd"] = None
        aggregate["cost_per_query_source"] = "estimate: pre-run cost estimate / questions"

    # P2-03 — a pipeline that called an LLM is not deterministic unless the
    # generation cache served every call. The hit rate goes on the row; a repeat of
    # an identical config with a hit rate under 100% is flagged, not averaged away.
    # P2-13: the chunker can hold one too (contextual retrieval calls a model to
    # build the index), and the compressor's has already finished by here, so its
    # stats arrive as a dict rather than as a live object.
    pipeline_llm = (
        getattr(retriever, "pipeline_llm", None)
        or getattr(reranker, "pipeline_llm", None)
        or getattr(chunker, "pipeline_llm", None)
    )
    all_stats = ([pipeline_llm.stats()] if pipeline_llm is not None else []) + compression_llms
    if all_stats:
        stats = _merge_pipeline_stats(all_stats)
        store.update_run(
            run_id,
            pipeline_nondeterministic=1,
            pipeline_llm_json=json.dumps(all_stats if len(all_stats) > 1 else stats),
        )
        aggregate["pipeline_nondeterministic"] = True
        aggregate["pipeline_llm_temperature"] = stats["temperature"]
        aggregate["pipeline_llm_calls"] = stats["calls"]
        aggregate["pipeline_llm_cache_hit_rate"] = stats["hit_rate"]
        earlier = store.runs_with_config_hash(config.config_hash, exclude=run_id)
        if earlier and (stats["hit_rate"] is None or stats["hit_rate"] < 1.0):
            flag = (
                f"repeat of config {config.config_hash} (earlier: {earlier[-1]['run_id']}) with a "
                f"generation cache hit rate of {stats['hit_rate'] or 0:.0%}: the in-pipeline LLM "
                "calls were not replayed, so retrieval outcomes may differ from the earlier run "
                "for reasons unrelated to the config (P2-03)"
            )
            aggregate["pipeline_cache_flag"] = flag
            warnings.warn(flag, stacklevel=2)
    else:
        store.update_run(run_id, pipeline_nondeterministic=0)
        aggregate["pipeline_nondeterministic"] = False

    # P2-06 — what the run actually cost, against the estimate.
    actual = actual_run_cost(
        retriever_meta=retriever.provenance(),
        reranker_meta=reranker.provenance() if reranker else None,
        # Only answers generated on this run are billed; a call-cache replay costs nothing.
        generator_tokens_in=sum(g.get("tokens_in", 0) for g in generated.values() if not g.get("cached")),
        generator_tokens_out=sum(g.get("tokens_out", 0) for g in generated.values() if not g.get("cached")),
        generator_model=config.generator_model,
        judge_estimate_usd=cost_estimate.get("judge_usd") if config.eval_tier is EvalTier.TIER_2 else None,
        pipeline_llm_stats=all_stats or None,
        pricing=pricing,
    )
    aggregate["cost_actual_usd"] = actual["total_usd"]
    aggregate["cost_actual_source"] = actual["source"]
    store.update_run(run_id, cost_actual_usd=actual["total_usd"], cost_actual_json=json.dumps(actual))
    drift = _estimate_drift(store)
    if drift:
        aggregate["cost_estimate_drift"] = drift
        if drift["drift"]:
            warnings.warn(
                f"cost estimator drift: median actual/estimate ratio {drift['median_ratio']} over "
                f"{drift['n']} runs — recalibrate rag/runner/cost.py (P2-06, DEC-035)",
                stacklevel=2,
            )

    slice_report = aggregate_by_slice(per_question, slices, percentiles={"collapse_ratio": (90,)})
    aggregate["slice_meta"] = slices.meta

    store.add_questions(
        [
            {
                "run_id": run_id,
                "question_id": row["question_id"],
                "retrieved_doc_ids": json.dumps(results_by_question[row["question_id"]].doc_ids),
                "retrieved_chunk_ids": json.dumps(results_by_question[row["question_id"]].chunk_ids),
                "context_chunk_ids": json.dumps(
                    [cid for cid, _ in results_by_question[row["question_id"]].context.chunks]
                ),
                "scores": json.dumps([c.score for c in results_by_question[row["question_id"]].chunks]),
                "gold_doc_ids": json.dumps(list(row["gold_doc_ids"])),
                "metrics_json": json.dumps(per_question[row["question_id"]]),
                "generated_answer": generated.get(row["question_id"], {}).get("text"),
                "cited_doc_ids": json.dumps(generated.get(row["question_id"], {}).get("cited", [])),
                "latency_ms": generated.get(row["question_id"], {}).get("latency_ms", 0),
                "retrieval_latency_ms": retrieval_latency_ms[row["question_id"]],
                "rerank_latency_ms": rerank_latency_ms.get(row["question_id"]),
                "tokens_in": generated.get(row["question_id"], {}).get("tokens_in", 0),
                "tokens_out": generated.get(row["question_id"], {}).get("tokens_out", 0),
                "cost_usd": None,
            }
            for row in rows
        ]
    )

    if call_cache is not None:
        aggregate["call_cache"] = {k: call_cache.stats[k] - call_cache_before[k] for k in call_cache.stats}
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
    generation_cache: GenerationCache,
) -> dict[str, Any]:
    """Generate answers and judge them. The only part of a run that costs money."""
    # P2-13: ordering is the assembler's business; compression happens before it,
    # because it changes the text the budget walk is measuring.
    assembler = ConcatAssembler(max_tokens=config.context_max_tokens, order=config.context_order)
    compressor = None
    if config.context_compressor:
        params = dict(config.context_compressor_params)
        model = params.pop("model", "")
        compressor = build_compressor(
            config.context_compressor,
            PipelineLLM(model, cache=generation_cache),
            **params,
        )
    generator = OpenRouterGenerator(
        GeneratorConfig(
            model=config.generator_model,
            prompt_id=config.generator_prompt_id,
            prompt_version=config.generator_prompt_version,
            max_tokens=config.generator_max_tokens,
            reasoning_effort=config.generator_reasoning_effort,
            fallback_models=config.generator_fallback_models,
        )
    )
    judge = None if config.skip_judge else RagasJudge(_judge_config(config))
    # P2-14, Axis 7: a second call that can replace an answer with a refusal.
    grounding = None
    if config.grounding_check:
        gparams = dict(config.grounding_check_params)
        grounding = GroundednessCheck(
            PipelineLLM(gparams.pop("model", ""), cache=generation_cache,
                        max_tokens=int(gparams.pop("max_tokens", 200)))
        )

    generated: dict[str, Any] = {}
    for row in rows:
        question_id = row["question_id"]
        # Scoring saw `retrieval_depth` chunks; the generator sees one chunk per
        # selected document — `top_k` distinct documents (P1-03), not top_k chunks.
        context_chunks = results_by_question[question_id].context_chunks
        texts = chunk_text
        if compressor is not None:
            compressed = compressor.compress(
                question_id=question_id,
                question=row["question"],
                chunks=context_chunks,
                chunk_text=chunk_text,
            )
            context_chunks, texts = compressed.chunks, compressed.chunk_text
        context = assembler.assemble(context_chunks, texts)
        # Words in and out per question: the tokens-per-query reduction the story
        # asks for is reported from these, not from an average of averages.
        per_question[question_id].update(
            {
                "context_words": float(context.meta["words_out"]),
                "context_chunks_used": float(context.n_chunks),
            }
        )
        answer = generator.generate(row["question"], context.text)
        if answer.prompt_ref != config.generator_prompt:
            raise RuntimeError(
                f"generator used prompt {answer.prompt_ref!r} but the run recorded "
                f"{config.generator_prompt!r} (MIS-015)"
            )

        answer_text = answer.text
        if grounding is not None:
            answer_text, grounding_record = grounding.check(
                question_id=question_id, question=row["question"],
                context=context.text, answer=answer_text,
            )
            per_question[question_id].update(grounding_record)
        # P2-14: a span citation can be checked against the text it names, with no
        # judge. Empty for chunk-level prompts, which is the comparison's point.
        spans = extract_span_citations(answer_text)
        if spans:
            support = span_support(spans, {c.doc_id: texts[c.chunk_id] for c in context_chunks})
            per_question[question_id].update({
                "span_support": support.rate,
                "spans_cited": float(support.total),
            })
        per_question[question_id].update(
            deterministic_metrics(
                generated_answer=answer_text,
                reference_answer=row["answer"],
                cited_doc_ids=extract_citations(answer_text),
                gold_doc_ids=list(row["gold_doc_ids"]),
            )
        )
        # Ragas scores against the retrieved contexts as a list, not one blob:
        # faithfulness decomposes claims and attributes them to individual contexts.
        contexts = [texts[c.chunk_id] for c in context_chunks]
        reference = (row.get("answer") or "").strip()
        if judge is None:
            # DEC-063: the judged criteria are recorded as skipped, not as zero and
            # not as absent. A metric that cannot be scored is None (preflight 6).
            for criterion in CRITERIA:
                per_question[question_id][criterion] = None
            per_question[question_id]["judge_skipped_by_config"] = 1.0
        elif reference:
            scores = judge.score(
                question=row["question"],
                answer=answer_text,
                contexts=contexts,
                reference=reference,
            )
            for criterion, score in scores.items():
                per_question[question_id][criterion] = score.score
        else:
            # The unanswerable split has no reference answers (DEC-007). Answer
            # correctness against an empty reference is not a score, and a refusal's
            # faithfulness is not what that split measures. Judged criteria are
            # recorded as not applicable, and the skip is counted (DEC-044).
            for criterion in CRITERIA:
                per_question[question_id][criterion] = None
            per_question[question_id]["judge_skipped_no_reference"] = 1.0

        generated[question_id] = {
            "text": answer_text,
            "cited": extract_citations(answer_text),
            "latency_ms": answer.latency_ms,
            "attempts": answer.meta.get("attempts", 1),
            # Ragas does not surface per-call token usage, so only the generator's
            # tokens are counted here. Judge cost is the pre-run estimate.
            "tokens_in": answer.tokens_in,
            "tokens_out": answer.tokens_out,
            # DEC-084: replayed from the ci-eval call cache — recorded, never billed.
            "cached": bool(answer.meta.get("cached")),
            "served_model": answer.meta.get("served_model") or config.generator_model,
        }
    if grounding is not None:
        generated["__grounding__"] = grounding.provenance()
    if compressor is not None:
        generated["__compression__"] = compressor.provenance()
    generated["__assembly__"] = {"order": config.context_order}
    return generated
