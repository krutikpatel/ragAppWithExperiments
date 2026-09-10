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

**Phase 0 — evaluation harness. Stories P0-01 through P0-10 are complete.**

Done:

- **Inputs are pinned and hashed.** Corpus frozen to one HuggingFace commit (6,221
  articles, snapshot 2024-12-02) with a reproducible `corpus_hash`; one versioned
  normalization rule; four hashed splits built by a seeded stratified deal; 45
  authored unanswerable questions (**LLM-drafted, human verification pending**).
- **Document-level scoring.** Binary qrels, an explicit chunk-to-document pooling
  rule recorded on every run, strict and loose recall@{1,3,5,10,20}, nDCG@10, and MRR
  restricted to the single-gold subset with its size attached.
- **Generation metrics.** Citation precision/recall and step coverage computed from
  artifacts with no LLM call; refusal and false-refusal tracked separately. Judged
  metrics come from **Ragas**, pinned exactly and confined behind the `Judge`
  interface — a test asserts nothing else imports it, so swapping judge libraries is
  a one-file change. Its dataset and experiment abstractions are deliberately not
  adopted; they would fork the results store.
- **Slice reporting** on every axis P0-08 requires, with `n` carried alongside each
  number and empty slices omitted.
- **Two-tier loop.** Tier 1 (retrieval only, zero LLM calls) runs `dev` end to end in
  about 12 seconds. Tier 2 adds generation and judging, scores a fixed 100-question
  subsample so runs stay comparable and affordable, and prints a cost estimate before
  it starts. The held-out `test` split refuses to open without an explicit flag and
  prints its opening history.
- **Runner and results store.** `run(config) -> row`, SQLite with `runs` and
  `run_questions`, full provenance including git dirty state, crashed runs recorded
  as `VOID`, and `rag diff` listing the questions that flipped in either direction
  with their gold ranks — refusing to call two runs comparable when their inputs
  differ.

Not yet built: the remaining P0-11 interfaces, the P0-12 test-openings log wiring,
and the P0-13 baseline run. **No experiments have been run, so there are no results
to report.** The only runs in the store are harness smoke tests using a deliberately
bad retriever; they are marked as such and are not experiments.

**Models.** Generator `openai/gpt-5-nano` (DEC-017); judge `deepseek/deepseek-v3.2`
(DEC-025), from a different family because `RunConfig` refuses same-family judging as
self-preference bias. Embeddings are `qwen/qwen3-embedding-8b` (DEC-027), chosen on context length rather
than price: 34% of our chunks exceed 512 tokens, and the whole index costs ~$0.03 to
embed either way. The judge is still a **plumbing placeholder** — its scores prove
Tier 2 works and are not measurements.

**Tier 2 has been exercised end to end** (2026-09-10, 5 questions, toy retrieval): all
three Ragas metrics returned values, provenance and per-question rows landed in the
store. It took three attempts, all failing on token budgets rather than logic — see
MIS-006, which is the most useful thing the run produced.

Measured on that run: **156s per question, 98% of it waiting on the judge.** So Tier 2
is latency-bound, not cost-bound — a 100-question run is on the order of hours while
costing cents (DEC-031). Judging is currently serialized one metric at a time;
concurrency is the untried lever (OQ-015).

## Quickstart

```bash
uv venv --python 3.11 && uv pip install -e ".[dev]"

rag corpus freeze          # materialize the pinned corpus, print corpus_hash
rag corpus verify          # recompute the hash from the artifact
rag data splits            # build test / dev / dev_large / unanswerable
rag data describe dev      # shape and slice counts

rag run configs/smoke_toy.yaml   # harness smoke test — NOT an experiment
rag runs list
rag diff <run_a> <run_b> --metric strict_recall@5

pytest
```

`data/frozen/` is gitignored. It is reproduced from the pinned revision by the two
commands above, and its provenance travels in `corpus.meta.json` and
`splits.meta.json`.

## Working in this repo

`CLAUDE.md` is the operating contract — for me and for any AI assistant working here.
It is read at the start of every session and followed literally. Read it before
making changes.
