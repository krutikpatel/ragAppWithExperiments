"""`rag` command line. CLI only — Phase 0 ships no UI."""

from __future__ import annotations

import json

import typer

app = typer.Typer(help="RAG experiment harness (WixQA).", no_args_is_help=True)
corpus_app = typer.Typer(help="Frozen corpus commands.", no_args_is_help=True)
data_app = typer.Typer(help="Evaluation split commands.", no_args_is_help=True)
app.add_typer(corpus_app, name="corpus")
app.add_typer(data_app, name="data")


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


if __name__ == "__main__":
    app()
