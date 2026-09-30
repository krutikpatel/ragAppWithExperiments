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
| `docs/HYPOTHESES.md` | Expectations written before a run, resolved after |
| `docs/GLOSSARY.md` | Project and dataset terms |
| `ci/DETECTION_FLOOR.md` | What the quality gate can and cannot catch |
| `eval/golden/DATASHEET.md` | How the golden CI slice was chosen |

An experiment is not finished when the run completes. It is finished when the index
row and the detail file are written.

## Status

**Phases 0–3 complete (2026-09-30).** 64 recorded experiments, and a quality gate that runs on
every pull request. The story, with a run id behind every number, is `docs/NARRATIVE.md`.

- **Phase 0 — the harness.** Pinned, hashed corpus and splits; document-level retrieval
  metrics via `ranx`; deterministic generation metrics; a results store with one row per
  question per run. Baseline: BM25 over 512-word chunks, strict recall@5 **0.405** on `dev`
  (EXP-0001).
- **Phase 1 — the controls.** Dense retrieval (`qwen3-embedding-8b`) beat BM25 by 0.305
  (EXP-0005). It is the one technique change in the project that measurably won, and on the
  held-out test split the gap was larger (+0.335, EXP-0046).
- **Phase 2 — seven technique axes.** Chunking, embeddings, hybrid retrieval, reranking,
  query transformation, context assembly, grounding, and combinations. Nothing beat the dense
  control on retrieval beyond run-to-run noise; the best number, 0.750, was not significant
  (EXP-0042). The one free win was abstaining on a low retrieval score, which halved false
  answers (EXP-0038). The test split, opened once, showed no measurable optimism gap: 0.720 on
  dev, 0.680 on test (EXP-0046).
- **Phase 3 — the shippable gate.** A validated faithfulness judge (EXP-0057), a golden CI
  slice, a measured detection floor, `rag ci-eval` as a required check on `main`, a baseline
  ratchet, six regression drills that all behaved as specified (EXP-0064), and a local answer
  API with a request log.

**Models** (each a `DECISIONS.md` entry, each pinned to an exact id):

| Role | Model | Decision |
|---|---|---|
| Generator | `openai/gpt-5-nano` | DEC-017 |
| Retrieval embeddings | `qwen/qwen3-embedding-8b` @DeepInfra | DEC-041 |
| Faithfulness judge | `deepseek/deepseek-v4.1-flash` @DeepInfra, no fallbacks | DEC-079 |

## Running the evaluation and the gate

```bash
uv venv --python 3.11 && uv pip install -e ".[dev]"      # add ",api" for the answer API
echo "OPENROUTER_API_KEY=..." > .env                      # gitignored; read from the environment

rag corpus freeze && rag data splits                      # rebuild the pinned corpus and splits
rag data golden --check                                   # re-derive the golden CI slice, fail on drift

# One experiment
rag run configs/promoted.yaml --estimate-only             # cost first; free
rag run configs/promoted.yaml                             # Tier 1 retrieval on dev, ~$0.0001
rag faithfulness <run_id> --judge-config configs/baseline_dense_tier2_v2.yaml

# The quality gate, exactly as CI runs it
rag ci-eval --estimate-only
rag ci-eval                                               # exit 0 pass, 1 fail, 2 error, 3 needs approval
rag ci-baseline verify                                    # the baseline's integrity stamp

# The answer API and demo page (local only)
RAG_API_REPLAY=1 docker compose up                        # http://localhost:8000; replay = $0 on golden questions
```

A run that would cost more than $2 stops before it starts and needs `--approve-cost`. The gate
has its own $1.00 budget per run (`ci/gate.yaml`).

**What a gate run costs** (36 GitHub runs, `docs/EXPERIMENTS.md`): **$0 and about 1.5 minutes**
when the answers are unchanged, because the gate replays cached calls. **$0.21–$0.36 and
33–62 minutes** when every answer is regenerated. $2.03 in total so far.

## What the gate can and cannot catch

From `ci/DETECTION_FLOOR.md`, measured on this judge, generator, prompt and slice (EXP-0059,
DEC-091). **A change smaller than these passes, not because it is harmless, but because the
gate cannot tell it from noise:**

| Metric | Caught at |
|---|---|
| strict recall@5 / gold-in-context on `dev` | a drop of **0.030** if the change only loses questions (paired test, α = 0.05); about 0.08 if it also wins some back |
| mean faithfulness | a drop of **0.032** |
| share of answers with an unsupported claim | a rise of **0.109** |
| answered unanswerable questions | **3 more** of 15 |
| citation validity | a drop of **0.051** |

Zero tolerance for citing a real article that was not retrieved, empty answers, and a changed
corpus, split, question set or judge. A judge failure or provider outage is an error, never a
quality failure.

## Known limitations

- **Document-level gold may be incomplete.** WixQA has near-duplicate help articles, so an
  article that is not labelled gold can support an equally correct answer. Strict recall
  counts it as a miss. The labels are used as-is (Phase 3 fact 4); this is not fixed.
- **The golden CI slice over-samples the questions the system answered without its
  evidence** (`eval/golden/DATASHEET.md`). Its absolute scores are not `dev` scores; the
  gate only compares a run to a baseline on the same slice.

- **The gate's golden slice overlaps `dev`**, the split every Phase 2 experiment used
  (DEC-074). Phase 3 tuned nothing on it; a future phase that tunes on `dev` must hold its 95
  questions out.
- **Blind spots the drills found** (EXP-0064): a change that only stops answers citing passes
  every rule (OQ-050), and the share of answers with an unsupported claim mostly measures
  style, not errors (OQ-048).
- **Not measured:** live per-request latency of the API, behaviour under prompt injection
  (OQ-052), and model drift under an unchanged pipeline (the on-demand drift check has never
  run, DEC-094). The API runs locally only; there is no hosted deployment.

- **The faithfulness judge is validated only on clear-cut synthetic cases.**
  `deepseek/deepseek-v4.1-flash` passed the P3-04 check (EXP-0057): it flagged 80 of 80
  answers copied from unrelated articles and passed 72 of 80 copied from the right ones.
  That shows it verifies literal support. It does not show how it treats paraphrase, which
  is what generated answers are, and no human agreement was measured. A first version of
  the check, built on WixQA's expert answers, failed every judge because about half of
  those answers are not supported by their own gold articles (EXP-0054–0056, OQ-047).

## Quickstart — the harness commands

```bash
uv venv --python 3.11 && uv pip install -e ".[dev]"

rag corpus freeze          # materialize the pinned corpus, print corpus_hash
rag corpus verify          # recompute the hash from the artifact
rag data splits            # build test / dev / dev_large / unanswerable
rag data describe dev      # shape and slice counts

rag run configs/smoke_toy.yaml   # harness smoke test — NOT an experiment
rag runs list
rag diff <run_a> <run_b> --metric strict_recall@5      # which questions flipped, MDD verdicts
rag compare <run_a> <run_b> --metric strict_recall@5   # paired test: Δ, CI, p, per slice (P2-01)
rag compare promoted <run_b>                           # `promoted` = newest run of configs/promoted.yaml
rag run configs/exp_0008_x.yaml --estimate-only        # cost estimate + running totals, spends nothing
rag promote configs/exp_0008_x.yaml --axis chunking --decide <a> <b> --confirm <a> <b> --reason "..."
rag pricing refresh                                    # re-date configs/pricing.yaml from OpenRouter

pytest
```

`data/frozen/` is gitignored. It is reproduced from the pinned revision by the two
commands above, and its provenance travels in `corpus.meta.json` and
`splits.meta.json`.

## Working in this repo

`CLAUDE.md` is the operating contract — for me and for any AI assistant working here.
It is read at the start of every session and followed literally. Read it before
making changes.
