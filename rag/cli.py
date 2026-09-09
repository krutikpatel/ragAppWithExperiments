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


@data_app.command("splits")
def data_splits(
    force: bool = typer.Option(False, "--force", help="Overwrite existing split artifacts."),
) -> None:
    """Build test / dev / dev_large / unanswerable splits with hashes."""
    from rag.dataset.splits import build_splits

    meta = build_splits(force=force)
    typer.echo(json.dumps(meta, indent=2))


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
) -> None:
    """Run one experiment: run(config) -> row in the results store."""
    from rag.runner.config import load_config_file
    from rag.runner.run import run as run_config

    config = load_config_file(config_path)
    row = run_config(config, open_test=open_test, reason=reason or None)
    typer.echo(f"run_id      = {row['run_id']}")
    typer.echo(f"config_hash = {row['config_hash']}")
    typer.echo(f"status      = {row['status']}")
    typer.echo(json.dumps(json.loads(row["metrics_json"]), indent=2, default=str))


@app.command("diff")
def diff(
    run_a: str = typer.Argument(..., help="Baseline run id."),
    run_b: str = typer.Argument(..., help="Run to compare against it."),
    metric: str = typer.Option("strict_recall@5", "--metric"),
) -> None:
    """List questions whose outcome flipped between two runs, in either direction."""
    from rag.runner.diff import diff_runs

    report = diff_runs(run_a, run_b, metric=metric)
    typer.echo(report["comparability"]["verdict"])
    typer.echo(
        f"{report['n_gained']} gained, {report['n_lost']} lost, "
        f"{report['n_unchanged']} unchanged, over {report['n_shared_questions']} questions"
    )
    typer.echo(json.dumps({"gained": report["gained"], "lost": report["lost"]}, indent=2))


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


if __name__ == "__main__":
    app()
