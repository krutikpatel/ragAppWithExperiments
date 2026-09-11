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

**Phase 0 complete — P0-01 through P0-14.** The evaluation harness is built, tested,
and has produced its first two experiments.

**The baseline exists.** EXP-0001: BM25 over 512-word chunks, top-5, on the 200-question
`dev` split — **strict recall@5 0.405**, loose 0.505, nDCG@10 0.384, deterministic to
twelve decimal places across three runs. Half the questions get no gold document in
the top five; multi-document questions find one required article two thirds of the
time and all of them under a fifth. EXP-0002 ran the WixQA paper's own retrieval
configuration (whole documents) one axis away: no measurable difference.

What the harness does:

- **Inputs are pinned and hashed.** Corpus frozen to one HuggingFace commit (6,221
  articles, 2.96M tokens); four hashed splits; 45 authored unanswerable questions
  (**LLM-drafted, human verification pending**).
- **Document-level scoring** with strict and loose recall@{1,3,5,10,20}, nDCG@10, and
  MRR on the single-gold subset, all via `ranx`, all on labelled `article_ids`.
- **Generation metrics.** Citation precision/recall, step coverage and refusal are
  deterministic and free. Judged metrics come from **Ragas**, pinned exactly, behind
  the `Judge` interface, with providers pinned for speed and reproducibility.
- **Two tiers.** Tier 1 scores `dev` in ~12 seconds with zero LLM calls. Tier 2 scores
  a fixed 100-question subsample in ~20 minutes for ~$0.84, and prints a validated
  cost estimate first.
- **A results store** with per-question rows and `rag diff`, which refuses to call two
  runs comparable when their corpus, split, pooling, judge, provider or Ragas version
  differ.
- **Interfaces for Phase 1** — `DatasetAdapter`, `Embedder`, `Reranker` (interface
  only) — with a test that the runner has no benchmark-specific import.
- **Test-split discipline.** Opening `test` needs `--open-test` and a reason, and
  every opening is appended to `docs/DECISIONS.md` automatically. It has been opened
  zero times.

**Models.** Generator `openai/gpt-5-nano` (DEC-017). Judge `openai/gpt-oss-120b`,
pinned to Cerebras/Groq (DEC-030/032) — still a **plumbing placeholder** whose scores
are not measurements. Embeddings `qwen/qwen3-embedding-8b` (DEC-027).

**The investigation is recorded as it happened.** `docs/DECISIONS.md` has 36 entries,
`docs/MISTAKES.md` has 9 — including three wrong premises in the handover caught by
counting, a metric that scored a different ranking than the system returned, a
capability I wrongly declared absent, and a provider pin that cost 6× more than
recorded. Each carries the rule that prevents it recurring.

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
