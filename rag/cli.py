"""`rag` command line. CLI only — Phase 0 ships no UI."""

from __future__ import annotations

import json

import typer

app = typer.Typer(help="RAG experiment harness (WixQA).", no_args_is_help=True)
corpus_app = typer.Typer(help="Frozen corpus commands.", no_args_is_help=True)
data_app = typer.Typer(help="Evaluation split commands.", no_args_is_help=True)
run_app = typer.Typer(help="Experiment runner and results store.", no_args_is_help=True)
app.add_typer(corpus_app, name="corpus")
app.add_typer(data_app, name="data")
app.add_typer(run_app, name="runs")


@corpus_app.command("freeze")
def corpus_freeze(
    force: bool = typer.Option(False, "--force", help="Re-materialize over an existing artifact."),
) -> None:
    """Materialize the KB corpus from the pinned HF revision and print its hash."""
    from rag.corpus.freeze import freeze_corpus

    meta = freeze_corpus(force=force)
    typer.echo(json.dumps(meta, indent=2))
    typer.echo(f"\ncorpus_hash = {meta['corpus_hash']}")


@corpus_app.command("verify")
def corpus_verify() -> None:
    """Recompute the corpus hash from the materialized artifact."""
    from rag.corpus.loader import verify_corpus

    result = verify_corpus()
    typer.echo(json.dumps(result, indent=2))
    if not result["match"]:
        raise typer.Exit(code=1)


@corpus_app.command("profile")
def corpus_profile(
    write_docs: bool = typer.Option(
        False, "--write-docs", help="Append the characterization block to docs/EXPERIMENTS.md."
    ),
    chunk_configs: str = typer.Option(
        "600/100,600/0,512/0",
        "--chunk-configs",
        help="Chunk configs to profile boundaries under, as size/overlap in words.",
    ),
) -> None:
    """Profile the frozen corpus: lengths, one-chunk fit, procedure boundaries (P1-02)."""
    from rag.corpus.profile import (
        profile_corpus,
        profile_summary_lines,
        render_markdown,
        write_profile_artifact,
        write_profile_docs,
    )

    configs = [tuple(int(x) for x in item.split("/")) for item in chunk_configs.split(",")]
    profile = profile_corpus(configs)
    artifact = write_profile_artifact(profile)
    for line in profile_summary_lines(profile):
        typer.echo(line)
    typer.echo(f"artifact    = {artifact}")
    if write_docs:
        outcome = write_profile_docs(profile, artifact)
        typer.echo(f"EXPERIMENTS.md: {outcome}")
    else:
        typer.echo("")
        typer.echo(render_markdown(profile, artifact))


@data_app.command("splits")
def data_splits(
    force: bool = typer.Option(False, "--force", help="Overwrite existing split artifacts."),
) -> None:
    """Build test / dev / dev_large / unanswerable splits with hashes."""
    from rag.dataset.splits import build_splits

    meta = build_splits(force=force)
    typer.echo(json.dumps(meta, indent=2))


@data_app.command("golden")
def data_golden(
    check: bool = typer.Option(False, "--check", help="Verify the committed slice re-derives exactly; write nothing."),
) -> None:
    """Select the golden CI slice (P3-03): seeded, scripted, from dev + unanswerable."""
    from collections import Counter

    from rag.dataset.golden import build_golden, golden_hash, golden_path, load_golden, write_golden

    rows = build_golden()
    counts = dict(Counter(r["stratum"] for r in rows))
    if check:
        same = load_golden() == rows
        typer.echo(f"{golden_path()}: {'matches' if same else 'DIFFERS FROM'} a fresh selection  {golden_hash(rows)}")
        raise typer.Exit(0 if same else 1)
    path = write_golden(rows)
    typer.echo(f"{path}: {len(rows)} questions {counts}  {golden_hash(rows)}")


@data_app.command("describe")
def data_describe(split: str = typer.Argument(..., help="test | dev | dev_large | unanswerable")) -> None:
    """Print the shape and slice counts of a built split."""
    from rag.dataset.splits import describe_split

    typer.echo(json.dumps(describe_split(split), indent=2))


@app.command("run")
def run_experiment(
    config_path: str = typer.Argument(..., help="Path to an experiment config YAML."),
    open_test: bool = typer.Option(
        False, "--open-test", help="Required to run against the held-out test split."
    ),
    reason: str = typer.Option("", "--reason", help="Recorded on the run row."),
    allow_leaky_split: bool = typer.Option(
        False, "--allow-leaky-split",
        help="Override the P2-04 split policy (Axis 3 or Tier 2 on dev_large); the run is marked leakage-affected.",
    ),
    approve_cost: str = typer.Option(
        "", "--approve-cost",
        help="Approval reference (DEC-NNN or reason) for a run estimated above the $2 gate; logged in DECISIONS.md.",
    ),
    estimate_only: bool = typer.Option(
        False, "--estimate-only", help="Print the cost estimate and running totals, then stop. Records nothing."
    ),
) -> None:
    """Run one experiment: run(config) -> row in the results store."""
    from rag.runner.config import load_config_file
    from rag.runner.cost import CostGateError
    from rag.runner.run import run as run_config

    config = load_config_file(config_path)
    try:
        row = run_config(
            config, open_test=open_test, reason=reason or None,
            allow_leaky_split=allow_leaky_split, approve_cost=approve_cost, estimate_only=estimate_only,
        )
    except (CostGateError, PermissionError) as exc:
        typer.echo(f"REFUSED: {exc}", err=True)
        raise typer.Exit(code=2)
    if estimate_only:
        return
    typer.echo(f"run_id      = {row['run_id']}")
    typer.echo(f"config_hash = {row['config_hash']}")
    typer.echo(f"status      = {row['status']}")
    typer.echo(json.dumps(json.loads(row["metrics_json"]), indent=2, default=str))


@app.command("ask")
def ask(
    question: str = typer.Argument("", help="The question. Omit when using --question-id."),
    config_path: str = typer.Option(
        "configs/baseline_dense_tier2.yaml", "--config", help="Run config to answer with."
    ),
    question_id: str = typer.Option(
        "", "--question-id", help="Answer a split question by id and score its citations against gold."
    ),
    split: str = typer.Option("dev", "--split", help="Split for --question-id (never `test` without --open-test)."),
    open_test: bool = typer.Option(False, "--open-test"),
    max_chunk_chars: int = typer.Option(0, "--max-chunk-chars", help="Truncate printed chunks (0 = full text)."),
) -> None:
    """Answer one question: question → step-formatted answer → title, URL, exact chunk (P1-06).

    Not an experiment: nothing is written to the results store.
    """
    from rag.ask import answer_question, format_ask

    if bool(question) == bool(question_id):
        raise typer.BadParameter("give exactly one of QUESTION or --question-id")
    if question_id and split == "test" and not open_test:
        raise typer.BadParameter("the test split needs --open-test")
    result = answer_question(
        config_path, question=question or None, question_id=question_id or None, split=split
    )
    typer.echo(format_ask(result, max_chunk_chars=max_chunk_chars or None))


@app.command("diff")
def diff(
    run_a: str = typer.Argument(..., help="Baseline run id."),
    run_b: str = typer.Argument(..., help="Run to compare against it."),
    metric: str = typer.Option("strict_recall@5", "--metric"),
) -> None:
    """List questions whose outcome flipped between two runs, in either direction.
    Either id may be `promoted` — the newest run of configs/promoted.yaml on the other run's split."""
    from rag.runner.diff import diff_runs

    run_a, run_b = _resolve_pair(run_a, run_b)
    report = diff_runs(run_a, run_b, metric=metric)
    typer.echo(report["comparability"]["verdict"])
    floored = {k: v for k, v in report["aggregate_deltas"].items() if v["mdd"] is not None}
    mdd = report["mdd"]
    if floored:
        typer.echo(
            f"MDD verdicts (family {mdd['family'] or 'none'}, retrieval family "
            f"{mdd['retrieval_family'] or 'none'}; DEC-046/048):"
        )
        for v in floored.values():
            typer.echo(f"  {v['text']}")
    for note in mdd["notes"]:
        typer.echo(f"  note: {note}")
    typer.echo(
        f"{report['n_gained']} gained, {report['n_lost']} lost, "
        f"{report['n_unchanged']} unchanged, over {report['n_shared_questions']} questions"
    )
    typer.echo(json.dumps({"gained": report["gained"], "lost": report["lost"]}, indent=2))


def _resolve_pair(run_a: str, run_b: str) -> tuple[str, str]:
    from rag.runner.promoted import resolve_run_ref
    from rag.runner.store import ResultsStore

    with ResultsStore() as store:
        other = run_b if run_a == "promoted" else run_a
        return (
            resolve_run_ref(run_a, store=store, like_run=other),
            resolve_run_ref(run_b, store=store, like_run=other),
        )


@app.command("compare")
def compare(
    run_a: str = typer.Argument(..., help="Baseline run id (A)."),
    run_b: str = typer.Argument(..., help="Candidate run id (B). The difference reported is B − A."),
    metric: str = typer.Option("strict_recall@5", "--metric", help="Any per-question metric in run_questions."),
    seed: int = typer.Option(20260915, "--seed", help="Resampling seed; recorded in the report."),
    resamples: int = typer.Option(10000, "--resamples"),
    as_json: bool = typer.Option(False, "--json", help="Print the full report as JSON."),
) -> None:
    """Paired significance test between two runs (P2-01): contingency, Δ, bootstrap CI,
    permutation p — overall and per slice — plus MDD verdicts for judged metrics (P2-02).
    Zero LLM calls."""
    from rag.runner.compare import compare_runs, format_compare

    run_a, run_b = _resolve_pair(run_a, run_b)
    report = compare_runs(run_a, run_b, metric=metric, seed=seed, resamples=resamples)
    typer.echo(json.dumps(report, indent=2, default=str) if as_json else format_compare(report))


@app.command("promote")
def promote_cmd(
    candidate: str = typer.Argument(..., help="Config YAML to promote (the run under --confirm/--decide must be its run)."),
    axis: str = typer.Option(..., "--axis", help="Which axis this decides (see rag.runner.config.AXES)."),
    dev: tuple[str, str] = typer.Option(..., "--dev", help="baseline_run candidate_run on `dev` — the deciding pair (DEC-055)."),
    dev_large: tuple[str, str] = typer.Option((None, None), "--dev-large", help="baseline_run candidate_run on `dev_large` — required direction check for retrieval axes."),
    metric: str = typer.Option("strict_recall@5", "--metric"),
    reason: str = typer.Option(..., "--reason", help="Written into the promotion log."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Check the policy, change nothing."),
) -> None:
    """Advance configs/promoted.yaml to CANDIDATE if the `dev` comparison passes (DEC-055: dev decides)."""
    from rag.runner.promoted import promote
    from rag.runner.run import git_state
    from rag.runner.store import ResultsStore

    with ResultsStore() as store:
        result = promote(
            candidate, axis=axis, dev=dev, dev_large=None if dev_large == (None, None) else dev_large,
            metric=metric, reason=reason, store=store, git_sha=git_state().sha, dry_run=dry_run,
        )
    typer.echo(json.dumps(result, indent=2, default=str))
    if result["problems"]:
        typer.echo("NOT PROMOTED — see problems above.", err=True)
        raise typer.Exit(code=2)
    typer.echo("promoted.yaml advanced" if result["promoted"] else "dry run: policy passed, nothing changed")


promoted_app = typer.Typer(help="The promoted configuration pointer (P2-05).", no_args_is_help=True)
app.add_typer(promoted_app, name="promoted")


@promoted_app.command("show")
def promoted_show() -> None:
    """Print the promoted config's hash and its newest recorded run per split."""
    from rag.runner.promoted import PROMOTED_PATH, load_promoted
    from rag.runner.store import ResultsStore

    promoted = load_promoted()
    typer.echo(f"{PROMOTED_PATH}: config_hash {promoted.config_hash}  ({promoted.name})")
    with ResultsStore() as store:
        for split in ("dev", "dev_large", "unanswerable"):
            row = store.latest_run_of(promoted, split=split)
            typer.echo(f"  {split:<13} {row['run_id'] if row else '— no VALID run'}")


@promoted_app.command("diff")
def promoted_diff(config_path: str = typer.Argument(..., help="Experiment config YAML.")) -> None:
    """Which fields, and which dimensions, CONFIG changes against promoted.yaml."""
    from rag.runner.config import load_config_file
    from rag.runner.promoted import config_diff, load_promoted

    typer.echo(json.dumps(config_diff(load_config_file(config_path), load_promoted()), indent=2, default=str))


pricing_app = typer.Typer(help="The dated pricing table the cost estimator reads (P2-06).", no_args_is_help=True)
app.add_typer(pricing_app, name="pricing")


@pricing_app.command("refresh")
def pricing_refresh() -> None:
    """Re-fetch every listed model's prices from OpenRouter and stamp today's date."""
    from rag.runner.cost import refresh_pricing

    table = refresh_pricing()
    typer.echo(f"pricing_version = {table.pricing_version}  ({table.path})")
    for model, providers in {**table.chat, **table.embeddings}.items():
        typer.echo(f"  {model}: {len(providers) - ('_model' in providers)} providers")


@pricing_app.command("show")
def pricing_show() -> None:
    from rag.runner.cost import PRICING_PATH

    typer.echo(PRICING_PATH.read_text())


@run_app.command("list")
def runs_list(limit: int = typer.Option(20, "--limit")) -> None:
    """List recorded runs, newest first."""
    from rag.runner.store import ResultsStore

    with ResultsStore() as store:
        for row in store.list_runs(limit):
            smoke = "  [SMOKE TEST]" if row["harness_smoke_test"] else ""
            dirty = "  [git dirty]" if row["git_dirty"] else ""
            typer.echo(
                f"{row['run_id']}  {row['status']:<9} {row['eval_tier']}  "
                f"{row['split']:<12} {row['name']}{smoke}{dirty}"
            )


@run_app.command("test-openings")
def runs_test_openings() -> None:
    """How many times the held-out test split has been opened, and when."""
    from rag.runner.store import ResultsStore

    with ResultsStore() as store:
        openings = store.test_openings()
    typer.echo(f"test split openings: {len(openings)}")
    for opening in openings:
        typer.echo(f"  {opening['timestamp']}  {opening['run_id']}  {opening['notes'] or ''}")


models_app = typer.Typer(help="Configured model checks (P3-02).", no_args_is_help=True)
app.add_typer(models_app, name="models")


@models_app.command("verify")
def models_verify(
    config_paths: list[str] = typer.Argument(..., help="One or more config YAMLs."),
) -> None:
    """Check every model slug (and pinned provider) the configs name still resolves on
    OpenRouter. Free — no API key, no model call. Exits 1 on any failure."""
    from rag.runner.config import load_config_file
    from rag.runner.model_check import ModelResolutionError, format_checks, verify_config_models

    failed = False
    for path in config_paths:
        typer.echo(path)
        try:
            typer.echo(format_checks(verify_config_models(load_config_file(path))))
        except ModelResolutionError as exc:
            typer.echo(str(exc))
            failed = True
    raise typer.Exit(1 if failed else 0)


judge_app = typer.Typer(help="P3-04 synthetic judge sanity check.", no_args_is_help=True)
app.add_typer(judge_app, name="judge-check")

PROBE_QUESTIONS = 2


def _judge_inputs(candidate: str):
    from rag.eval.judge_check import CANDIDATES, build_pairs, load_inputs

    if candidate not in CANDIDATES:
        raise typer.BadParameter(f"unknown candidate {candidate!r}; known: {sorted(CANDIDATES)}")
    golden, texts, ranked, corpus = load_inputs()
    return CANDIDATES[candidate], build_pairs(golden, list(texts), ranked), texts, corpus


@judge_app.command("probe")
def judge_probe(candidate: str = typer.Argument(..., help="deepseek | qwen | gemini")) -> None:
    """A few real calls (2 questions x 3 kinds) to measure tokens, reasoning, cost and
    failures on the REAL prompt before costing the full run (preflight 42). Recorded."""
    import random

    from rag.eval.judge_check import SEED, judge_config, record_run, run_pairs, summarize

    (model, provider), pairs, texts, corpus = _judge_inputs(candidate)
    qids = sorted({p.question_id for p in pairs})
    chosen = set(random.Random(f"{SEED}:probe").sample(qids, PROBE_QUESTIONS))
    probe = [p for p in pairs if p.question_id in chosen]
    results, usage = run_pairs(probe, texts, judge_config(model, provider))
    usage["context_words"] = sum(len(texts[a].split()) for p in probe for a in p.article_ids)
    summary = summarize(results)
    run_id = record_run(name=f"P3-04 probe — {model} @{provider}", model=model, provider=provider, pairs=probe,
                        results=results, usage=usage, summary=summary, corpus=corpus,
                        notes="probe: 2 questions x 3 kinds, preflight 42", cost_estimate=None, approval="probe approved by Krutik 2026-09-28")
    typer.echo(json.dumps({"run_id": run_id, "usage": usage,
                           "results": [{k: r[k] for k in ("pair_id", "score", "flag", "error")} for r in results]}, indent=2))


@judge_app.command("run")
def judge_run(
    candidate: str = typer.Argument(..., help="deepseek | qwen | gemini"),
    estimate_only: bool = typer.Option(False, "--estimate-only"),
    approve_cost: str = typer.Option("", "--approve-cost", help="Approval reference; required above the $2 gate."),
) -> None:
    """All 240 pairs on one candidate judge. Estimated from its latest probe."""
    from rag.eval.judge_check import estimate, judge_config, record_run, run_pairs, summarize
    from rag.runner.cost import COST_GATE_USD
    from rag.runner.store import ResultsStore

    (model, provider), pairs, texts, corpus = _judge_inputs(candidate)
    with ResultsStore() as store:
        row = store.conn.execute(
            "SELECT run_id, cost_actual_json FROM runs WHERE eval_tier='judge_check' AND name LIKE ? "
            "AND status='VALID' ORDER BY timestamp DESC LIMIT 1", (f"P3-04 probe — {model} @{provider}",)).fetchone()
    if row is None:
        raise typer.BadParameter(f"no probe recorded for {model} @{provider}; run `rag judge-check probe {candidate}` first")
    est = estimate(pairs, texts, {"run_id": row["run_id"], **json.loads(row["cost_actual_json"])})
    typer.echo(f"*** P3-04 ESTIMATE (calibrated on a {PROBE_QUESTIONS}-question probe) {model} @{provider}: "
               f"${est['usd']:.4f} for {est['n_pairs']} pairs, {est['context_words']:,} context words ({est['source']})")
    if estimate_only:
        return
    if est["usd"] > COST_GATE_USD and not approve_cost.strip():
        raise typer.Exit(f"estimate above the ${COST_GATE_USD:.2f} gate; re-run with --approve-cost")
    if not approve_cost.strip():
        raise typer.BadParameter("--approve-cost is required: every paid run needs Krutik's go-ahead (DEC-053)")
    results, usage = run_pairs(pairs, texts, judge_config(model, provider))
    summary = summarize(results)
    run_id = record_run(name=f"P3-04 judge check — {model} @{provider}", model=model, provider=provider, pairs=pairs,
                        results=results, usage=usage, summary=summary, corpus=corpus, notes="P3-04 bake-off",
                        cost_estimate=est["usd"], approval=approve_cost)
    typer.echo(json.dumps({"run_id": run_id, "usage": usage, **summary}, indent=2))


audit_app = typer.Typer(help="Provenance audits over the results store (P3-01).", no_args_is_help=True)
app.add_typer(audit_app, name="audit")


@audit_app.command("provenance")
def audit_provenance(
    dev_run: str = typer.Argument(..., help="The dev-split run."),
    test_run: str = typer.Argument(..., help="The test-split run it was compared with."),
    dev_tier1: str = typer.Option(None, "--dev-tier1", help="Dev Tier 1 run, to recompute recall on the subsample."),
    test_tier1: str = typer.Option(None, "--test-tier1", help="Test Tier 1 run, same."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Were two runs independent? Question overlap, cache reuse, per-question agreement.
    Zero model calls."""
    from rag.runner.audit import format_audit, provenance_audit

    report = provenance_audit(dev_run, test_run, dev_tier1=dev_tier1, test_tier1=test_tier1)
    typer.echo(json.dumps(report, indent=2, default=str) if as_json else format_audit(report))


if __name__ == "__main__":
    app()
