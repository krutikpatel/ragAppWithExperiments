# ragAppWithExperiments

A Retrieval-Augmented Generation system over a fixed document corpus, built as an
**experiment platform** rather than a demo.

The system exists to answer one question, repeatedly and with evidence:

> Does technique X measurably beat technique Y on this corpus, and at what cost?

## What this repo is trying to produce

1. **Measured findings** — what actually moved the metrics, backed by reproducible runs.
2. **A production-quality system** — deployed, observed, tested, gated in CI.
3. **A written narrative** — the story of the investigation, written from the evidence.

The narrative is a byproduct of the measurements, never decided first and justified
afterwards. If the data turns out boring, the narrative is boring.

Data cleaning and document conditioning are out of scope. The corpus is parsed once,
frozen, and treated as a fixed input.

## The house rules

Two rules shape everything here, and they are worth stating up front because they
explain why the repo looks the way it does.

**No predictions.** No outcome is stated for a configuration that has not been run.
No metric is estimated, interpolated, or borrowed from a paper and presented as a
finding. Intuitions are filed in `docs/OPEN_QUESTIONS.md` as a question plus the
decision rule that would settle it — not as an expectation.

**Append-only evidence.** The documentation files are journals. A wrong entry gets a
correction appended and a pointer added beneath the original; it is never rewritten.
An invalidated experiment is marked `VOID` with a reason, and its numbers stay on the
page. Deleted evidence is worse than wrong evidence.

## Where the numbers live

`results/runs/<RUN_ID>/` holds the machine-written artifacts of a run:

```
config.yaml       the exact configuration that ran
metrics.json      the measured numbers
predictions.jsonl per-query outputs
env.json          environment, model versions, corpus hash
stdout.log        the run log
```

Every numeric claim anywhere in this repo traces back to a `RUN_ID` whose directory
exists on disk. The markdown files mirror those artifacts — they never originate a
number.

## Documentation map

| File | What it holds |
|---|---|
| `docs/NARRATIVE.md` | The human-readable story of the investigation |
| `docs/EXPERIMENTS.md` | Index of every run, with headline metrics |
| `docs/experiments/EXP-NNNN.md` | Full detail for one experiment |
| `docs/DECISIONS.md` | Consequential decisions, with context and a revisit trigger |
| `docs/MISTAKES.md` | Every error made, and the rule that prevents recurrence |
| `docs/FAILURES.md` | Taxonomy of queries the system answers badly |
| `docs/OPEN_QUESTIONS.md` | Untested hypotheses and their decision rules |

An experiment is not finished when the run completes. It is finished when the index
row and the detail file are written.

## Status

**Phase 0 — evaluation harness. Stories P0-01 through P0-05 are complete.** The
harness builds and scores inputs; it does not retrieve yet.

Done:

- The corpus is pinned to one HuggingFace commit and materialized locally with a
  reproducible `corpus_hash` (6,221 articles, snapshot 2024-12-02).
- One versioned text-normalization rule, `norm-v1`, with the stored article kept
  verbatim for citation display.
- Four hashed splits — `test` (held out), `dev`, `dev_large`, `unanswerable` — built
  by a seeded, stratified deal.
- 45 authored unanswerable questions in three buckets, added as questions rather
  than by deleting articles from the index. **LLM-drafted; human verification
  pending.**
- Document-level qrels and an explicit chunk-to-document pooling rule, recorded on
  every run because it changes the document ranking by itself.

Not yet built: retrieval metrics (P0-06), generation metrics (P0-07), slice
reporting (P0-08), the two-tier loop (P0-09), the runner and results store (P0-10),
the remaining interfaces (P0-11), test-split discipline (P0-12), and the baseline
run (P0-13). **No experiments have been run, so there are no results to report.**

## Quickstart

```bash
uv venv --python 3.11 && uv pip install -e ".[dev]"

rag corpus freeze          # materialize the pinned corpus, print corpus_hash
rag corpus verify          # recompute the hash from the artifact
rag data splits            # build test / dev / dev_large / unanswerable
rag data describe dev      # shape and slice counts

pytest
```

`data/frozen/` is gitignored. It is reproduced from the pinned revision by the two
commands above, and its provenance travels in `corpus.meta.json` and
`splits.meta.json`.

## Working in this repo

`CLAUDE.md` is the operating contract — for me and for any AI assistant working here.
It is read at the start of every session and followed literally. Read it before
making changes.
