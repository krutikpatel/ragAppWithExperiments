# CLAUDE.md — Operating Instructions

This file governs how you work in this repository. It is not background reading.
Read it at the start of every session and follow it literally.

---

## 1. What this project is

A production-grade Retrieval-Augmented Generation system over a fixed document
corpus, built as an **experiment platform**, not a demo.

The system exists to answer one question repeatedly: *does technique X measurably
beat technique Y on this corpus, and at what cost?*

Three outputs matter, in this order:

1. **Measured findings** — what actually moved the metrics, backed by reproducible runs.
2. **A production-quality system** — deployed, observed, tested, gated in CI.
3. **A written narrative** — the story of the investigation, usable in hiring conversations.

The narrative is a *byproduct of evidence*, never a story we decide on first and
then justify. If the data is boring, the narrative is boring. That is acceptable.

Data cleaning and document conditioning are explicitly **out of scope**. The corpus
is parsed once, frozen, and treated as a fixed input. Do not propose parsing
improvements as experiments unless asked.

This repo serves as RAG technique learning tool for author.  It will be used to showcase my RAG and AI skills and effort i put to learn RAG techniques.

---

## 2. The documentation contract

Seven files. They are deliverables, not notes. Treat a change to code as incomplete
until the corresponding documentation is written.

| File | Purpose | Write cadence |
|---|---|---|
| `docs/NARRATIVE.md` | The human-readable story of the investigation | End of each phase, or after a batch of related experiments |
| `docs/EXPERIMENTS.md` | Index of every experiment run, with headline metrics | Immediately after every run completes |
| `docs/experiments/EXP-NNNN.md` | Full detail for one experiment | Same time as the index row |
| `docs/DECISIONS.md` | Every consequential decision, by me or by you | At the moment the decision is made |
| `docs/MISTAKES.md` | Every error made, and the rule that prevents recurrence | Immediately on discovery |
| `docs/FAILURES.md` | Taxonomy of queries the system answers badly | After each evaluation run review |
| `docs/OPEN_QUESTIONS.md` | Unanswered questions and untested hypotheses | Whenever one surfaces |
| `docs/HYPOTHESES.md` | Expectations written before a run, resolved after (P1-10). Never in EXPERIMENTS.md | Before the run it names; resolution after |

Writing style: not too much technical jargons, easy to understand for someone who is new to RAG and AI. But RAG technique names and popular jargon is ok to use and encouraged. If project and dataset specific terms used, create separate glossary.md to reference them. 

### Source of truth

`results/runs/<RUN_ID>/` holds the machine-written artifacts: `config.yaml`,
`metrics.json`, `predictions.jsonl`, `env.json`, `stdout.log`.

**The markdown files mirror those artifacts. They never originate numbers.**

Every numeric claim in any markdown file must be traceable to a `RUN_ID` whose
directory exists on disk. If you cannot point to the artifact, you may not write
the number.

### Append-only

These files are append-only journals. Never delete or rewrite a past entry.

- A wrong entry gets a **correction entry** appended, and the original gets a
  `> **CORRECTED by <ID> on <date>**` line added directly beneath it.
- An invalidated experiment gets its status set to `VOID` with a reason and a link
  to the `MIS-NNN` entry that explains why. The row stays. The numbers stay.
  Deleted evidence is worse than wrong evidence.

Reorganising the *structure* of a file (adding sections, fixing the index table) is
fine. Rewriting *history* is not.

---

## 3. The no-prediction rule

**This is the strictest rule in this repository. It overrides helpfulness.**

You do not predict experimental outcomes. You run experiments and record what happened.

### Prohibited, without exception

- Stating or implying an outcome for a configuration that has not been run.
  Banned phrasings include: *should improve*, *will likely*, *I expect*, *this is
  better because*, *typically outperforms*, *this should give us around*,
  *the gain will be modest*.
- Writing a results row, metric, or delta before the run has produced `metrics.json`.
- Estimating, interpolating, or extrapolating a metric that was not measured.
  A number from a 20-question smoke run is not a number for the 150-question set.
- Ranking two techniques on this corpus without runs for both.
- Presenting a claim from a paper, blog post, or your own training as if it were a
  finding from this project.
- Writing narrative that describes a result before that result exists.

### Required instead

When you have an intuition or a reason to try something, express it as a **question
plus a decision rule**, and file it in `docs/OPEN_QUESTIONS.md`:

> **OQ-014** — Does sentence-window retrieval beat fixed-600 chunking on multi-hop
> questions? Decided by: recall@10 on the `multi_hop` slice, ≥3 point difference
> across 3 seeds. Not yet run.

External claims are allowed *only* when explicitly labelled as external and framed
as something to test:

> External claim (Anthropic contextual-retrieval post, Sept 2024): prefixing chunks
> with generated document context reduces retrieval failures. **Untested here.**
> Tracked as OQ-021.

### If I ask you to predict

If I ask "which do you think will win?" or "is X worth trying?", answer:

> Not measured on this corpus. The experiment that would answer it is: `<config diff>`,
> decided by `<metric>` on `<slice>`. Want me to queue it?

You may reason about *cost, latency, and implementation effort* before running —
those are engineering estimates, not quality predictions. Label them as estimates.

### Selection and interpretation

- Never tune on the golden evaluation set. If you tune anything, it is on the
  dev slice, and you say so.
- Never report the best of N runs as the result. Report mean and spread across seeds.
- A difference smaller than the run-to-run spread is **not a finding**. Write
  "no measurable difference," not "a slight improvement."
- Do not compare runs that used different corpus hashes, different eval-set
  versions, or different judge models. If they differ, say the comparison is invalid.

---

## 4. `docs/EXPERIMENTS.md` — format

Top of file: an index table, newest last.

```markdown
| Run ID | Date | Axis | Change vs baseline | recall@10 | nDCG@10 | Faithfulness | Cit. precision | p95 ms | $/query | Status | Detail |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0001 | 2026-09-10 | baseline | fixed-600/100, dense k=5 | 0.61 | 0.54 | 0.72 | 0.81 | 2100 | 0.0041 | VALID | [→](experiments/EXP-0001.md) |
| EXP-0002 | 2026-09-11 | retrieval | + BM25 hybrid (RRF) | 0.74 | 0.66 | 0.79 | 0.83 | 2250 | 0.0043 | VALID | [→](experiments/EXP-0002.md) |
| EXP-0003 | 2026-09-11 | chunking | semantic chunking | — | — | — | — | — | — | VOID (MIS-004) | [→](experiments/EXP-0003.md) |
```

Status is one of `RUNNING`, `VALID`, `VOID`, `SUPERSEDED`.

### Per-experiment file — `docs/experiments/EXP-NNNN.md`

```markdown
# EXP-0002 — Hybrid retrieval via Reciprocal Rank Fusion

- **Status:** VALID
- **Date:** 2026-09-11
- **Run IDs:** run_20260911_142233_a91f (seeds 1, 2, 3)
- **Git SHA:** 4f9c1ab
- **Corpus hash:** sha256:7d2e...
- **Eval set version:** golden-v3 (152 questions)
- **Compared against:** EXP-0001 (baseline)

## Question
Does BM25 + dense fusion improve retrieval over dense-only on this corpus?

## Configuration diff
```yaml
retriever:
-  type: dense
+  type: hybrid
+  fusion: rrf
+  rrf_k: 60
+  bm25_top_k: 50
+  dense_top_k: 50
```

## Results
| Metric | Baseline | This run | Delta | Spread (3 seeds) |
|---|---|---|---|---|
| recall@10 | 0.61 | 0.74 | +0.13 | ±0.02 |
| ...

Per-slice breakdown:
| Slice | Baseline | This run |
|---|---|---|
| factual | ... | ... |
| multi_hop | ... | ... |
| exact_term | ... | ... |
| unanswerable | ... | ... |

## Observations
Factual statements about what the numbers show. No causal claims beyond what was
varied. No speculation about the next experiment's outcome.

## Anomalies
Anything unexpected in logs, latency, or outputs. If none: "None observed."

## Reproduce
```bash
python -m rag.run --config configs/exp_0002.yaml --seeds 1,2,3
```
```

Write "Observations" only after reading actual failing examples, not just aggregate
metrics. Pull at least five queries where behaviour changed and look at them.

---

## 5. `docs/DECISIONS.md` — format

Log every decision that would be expensive or confusing to reverse: corpus choice,
eval-set design, metric definitions, framework and model selection, architecture
boundaries, scope cuts, thresholds, deployment targets.

```markdown
## DEC-007 — Freeze the golden set at v3 before the chunking sweep
- **Date:** 2026-09-11
- **Decided by:** Krutik (proposed by Claude)
- **Status:** Active
- **Context:** Chunking changes alter chunk boundaries, so eval questions written
  against v2 chunk text would no longer align.
- **Options considered:**
  1. Regenerate the eval set per chunking config — rejected, breaks comparability.
  2. Freeze at v3 and treat all chunking runs as one comparable family — chosen.
  3. Delay the sweep until v4 is ready — rejected, blocks two weeks of work.
- **Decision:** Freeze golden-v3. All Axis-1 runs use it. Any later version starts
  a new comparison family and cannot be compared across the boundary.
- **Evidence:** No measured data; judgment call on experimental validity.
- **Consequences:** Runs before EXP-0009 are not comparable to runs after a future v4.
- **Revisit if:** eval set proves too small for statistical separation on any slice.
```

Rules:

- **Decided by** must be honest: `Krutik`, `Claude`, or `Joint`. When you make a
  call on your own because I was not in the loop, mark it `Claude` and say so in
  chat. Do not launder your own choices as mine.
- If a decision has no measured basis, write `**Evidence:** No measured data;
  judgment call.` Never manufacture a rationale.
- Every decision needs a **Revisit if** trigger. Decisions without exit conditions
  become dogma.
- When a decision is reversed, append a new entry and set the old one's status to
  `Superseded by DEC-NNN`.

---

## 6. `docs/MISTAKES.md` — format

Everything that went wrong: bugs, invalid comparisons, misread metrics, wasted
runs, wrong assumptions, config errors, my mistakes and yours.

**Read this file before starting any new experiment.** It is a preflight checklist,
not an archive.

```markdown
## MIS-004 — Compared runs across different eval-set versions
- **Date:** 2026-09-11
- **Severity:** High — invalidated EXP-0003
- **What happened:** EXP-0003 ran against golden-v3 while its stated baseline
  EXP-0001 used golden-v2. The reported +0.04 faithfulness delta was meaningless.
- **How it was caught:** Question count differed (152 vs 141) in the run manifest.
- **Root cause:** The runner did not assert eval-set version equality against the
  declared baseline.
- **Impact:** EXP-0003 marked VOID. Two hours of compute wasted.
- **Fix applied:** Runner now records `eval_set_version` and refuses to emit a
  delta table when it differs from the baseline run.
- **Prevention rule:** Before writing any comparison, verify corpus hash, eval-set
  version, and judge model match across both runs.
- **Added to preflight:** yes
```

Maintain a short **Preflight checklist** section at the top of the file, derived
from the prevention rules. Run through it before each experiment and say in chat
that you did.

Do not soften entries. "We could have been clearer" is not a mistake entry.
Write what broke.

---

## 7. `docs/NARRATIVE.md` — format

The document a hiring manager reads. Written from `EXPERIMENTS.md` and nothing else.

Structure:

1. **The problem and the corpus** — what domain, why, what makes it hard.
2. **How this was measured** — eval-set construction, slices, metrics, why these
   metrics, how noise was handled. This section is the credibility anchor; write
   it carefully.
3. **The baseline** — what the naive system scored.
4. **What was tried, axis by axis** — for each: the question, what was run, what
   the numbers were, what was concluded. Include the things that did nothing.
5. **What actually moved the needle** — a ranked table of techniques by measured
   delta, against cost and latency.
6. **What did not work, and what that suggests** — the most interesting section.
   Negative results with honest interpretation.
7. **Where the system still fails** — from `FAILURES.md`.
8. **Production engineering** — deployment, observability, CI eval gate, caching,
   degradation, injection surface.
9. **Lessons that transfer** — what I would do differently on a real system, and why.
10. **What remains untested** — from `OPEN_QUESTIONS.md`. Naming your gaps is a
    strength signal, not a weakness.

Style rules:

- Past tense, first person, specific. "Hybrid retrieval improved recall@10 from
  0.61 to 0.74 (EXP-0002)." Not "we leveraged hybrid retrieval for improved results."
- Every claim carries an `EXP-NNNN` reference.
- No marketing language. No "revolutionary", "cutting-edge", "seamless", "robust".
- Include at least one section describing something that failed and what it cost.
- Do not write section 5 or 6 until the corresponding experiments are `VALID`.
  Leave the heading with `_Pending: EXP-0011 through EXP-0016._` underneath.

---

## 8. `docs/FAILURES.md` and `docs/OPEN_QUESTIONS.md`

**FAILURES.md** — after each evaluation run, sample the worst-scoring queries and
categorise them. Track: query, expected answer, what the system returned, which
stage failed (retrieval / reranking / assembly / generation), category, and whether
any later experiment fixed it. Categories emerge from the data; do not invent a
taxonomy up front.

**OPEN_QUESTIONS.md** — every untested hypothesis, with the decision rule that
would settle it and its current status (`open`, `queued`, `answered by EXP-NNNN`,
`dropped`). This is where intuitions go instead of into predictions.

---

## 9. Working rules

**Session start.** Read `MISTAKES.md` preflight, the last five rows of
`EXPERIMENTS.md`, and the active entries in `DECISIONS.md`. Say in one line what
state the project is in and what you understand the next step to be. Wait for
confirmation before large work.

**Before an experiment.** Confirm the config diff is minimal — one axis at a time
unless the run is explicitly a combination run. State which baseline it compares
against. Run the preflight checklist.

**During.** Do not modify the eval set, the corpus, the judge model, or the metric
definitions mid-batch. If one must change, stop, log a decision, and start a new
comparison family.

**After.** Write the index row and detail file before starting anything else. An
unrecorded run does not exist. If a run crashed or was abandoned, record it as
`VOID` with the reason — silent gaps in the ledger destroy the narrative's
credibility.

**Commits.** One experiment per commit where possible.
`EXP-0002: hybrid RRF retrieval — recall@10 0.61→0.74`.
Docs update lands in the same commit as the run it describes.
**Every story is committed before the next one begins.** A story's code, tests
and documentation land in one commit (`P2-05: promoted.yaml pointer + rag promote`)
and the next story starts from that SHA. Do not carry two stories in one working
tree; if it has happened, split the commits before continuing.

**Spend.** Every experiment run that costs money needs Krutik's explicit go-ahead in
chat before it starts, regardless of the $2 gate — the gate is a backstop, not the
approval. Give the heads-up as: config, split, `--estimate-only` output, and what
the run decides. Budget is flexible; surprise is not. (DEC-053)

**Scope.** Do not refactor beyond the task. Do not add pipeline stages, swap
libraries, or restructure configs without an entry in `DECISIONS.md`.

**Honesty.** If something is broken, uncertain, slower than expected, or if you
are unsure a comparison is valid, say so plainly in chat and log it. Never smooth
over a problem to keep momentum. If I propose something that would invalidate an
experiment or contaminate the eval set, tell me directly and do not implement it
until we have resolved it.

**Ask before:** changing metric definitions, regenerating the eval set, switching
embedding or judge models, deleting run artifacts, or changing anything that
breaks comparability with prior runs.

---

## 10. Repository structure, tech stack, and models

Reference material. Keep it accurate: when you add a directory, a dependency, or a
model, update this section in the same commit. A stale map here is worse than none,
because it gets trusted.

**Directories marked _(planned)_ do not exist yet.** Do not describe them as if they
do, and do not create one until the story that owns it is in scope.

### Directory structure

```
rag/
  cli.py            `rag` entry point (typer). CLI only — no UI in Phase 0.
  paths.py          every filesystem location, in one place
  hashing.py        canonical-JSON hashing for corpora, splits, configs
  prompts.py        versioned prompt loading by (id, version), content-hashed
  assembly.py       ContextAssembler — retrieved chunks into the generator prompt
  citations.py      P1-06: [doc:<id>] -> title, URL (doc store) and the exact retrieved
                    chunk; invented ids are shown and flagged, never hidden
  ask.py            `rag ask` — one question through the configured pipeline, rendered;
                    writes nothing to the results store
  corpus/           freeze.py (pinned HF revision -> parquet), normalize.py
                    (norm-vN), loader.py (the ONLY runtime read path),
                    profile.py (`rag corpus profile` — lengths, one-chunk fit,
                    procedure-block cuts; a characterization, not an experiment)
  dataset/          adapter.py (DatasetAdapter, QARow), wixqa.py (WixQAAdapter),
                    loader.py (reads frozen splits — NO benchmark import; the
                    runner's only dataset dependency), splits.py (builds them),
                    unanswerable.py (the authored refusal set)
  chunking/         base.py (Chunker, Chunk with `text` = what is indexed and
                    `context_text` = what the generator sees, FixedTokenChunker, and
                    the chunker registry — `config.chunker` names one, P2-07),
                    index_map.py (ChunkIndex — persists chunk_id -> doc_id and both
                    texts; `.profile()` = the chunking characterisation on every run
                    row), sentences.py (sentences-v1: newline / `[.?!]`+space /
                    `[.?!]`+capital — a third of the corpus's boundaries are glued),
                    profile.py (chunks, words, one-chunk share, DEC-039 procedure
                    blocks cut on indexed text and on context, for ANY chunker),
                    sentence_window.py (1 sentence indexed, ±3 context; 196k rows),
                    parent_document.py (150-word children, 600-word parent context),
                    semantic.py (95th-percentile consecutive-sentence distance cuts;
                    embeds every sentence FIRST — a gated pre-spend via
                    `Chunker.embedding_params`; distances cached under
                    indexes/sentence_distances/), structure.py (line-boundary cuts,
                    `:`-lines bound to their steps; the corpus has NO headings).
                    Late chunking is not available hosted (OQ-030). All DEC-057.
  retrieval/        base.py (Retriever, RetrievalResult — ranking for scoring plus a
                    DocSelection context of top_k DISTINCT documents, P1-03),
                    pooling.py (doc_pooling; select_distinct_docs + collapse ratio),
                    bm25.py (the sparse control; rank-bm25 Okapi), dense.py (cosine
                    over a numpy index cached under indexes/<key>/, key = provenance
                    tuple, P1-04), hybrid.py (P2-09: dense + BM25 fused by RRF k=60 or
                    min-max weighted `alpha` on dense, DEC-056; owns no index — the
                    dense half does, and `Retriever.embedding_params` is how the
                    runner costs a retriever by what it embeds, not by its name),
                    toy.py (smoke tests only; toy_llm_rewrite puts a
                    fake non-deterministic LLM call inside retrieval for the P2-03 test)
  eval/             qrels.py (binary document-level qrels + alignment check),
                    retrieval_metrics.py (strict/loose recall, nDCG, subset MRR),
                    generation_metrics.py (citations, refusal — no LLM calls),
                    steps.py (procedural step coverage), slices.py (P0-08),
                    judge.py — the ONLY module that may import Ragas,
                    noise_floor.py — measured run-to-run spread (MDD) per configuration
                    family, matched from a run row's judge/generator/prompt provenance;
                    labels every delta significant / within judge noise / no MDD
                    measured; rag diff and rag compare use it (DEC-037/046/048)
  generation/       base.py — Generator interface + OpenRouter generator;
                    cache.py — GenerationCache, SQLite keyed on (question_id, prompt_id,
                    prompt_version, model_id, input_hash) for in-pipeline LLM calls;
                    pipeline_llm.py — PipelineLLM, the ONLY way retrieval-side code calls
                    a model: temperature 0 constant, cached, hit rate counted (P2-03)
  runner/           config.py (RunConfig, EvalTier, AXES, config_hash = exact identity,
                    identity_hash = the tier's identity, MIS-019), run.py (run(config)
                    -> row; split policy, cost gate, promoted diff, pipeline cache
                    stats, actual cost), store.py (SQLite runs + run_questions),
                    diff.py (rag diff), compare.py (rag compare — paired bootstrap CI +
                    permutation p per question, per slice, P2-01), promoted.py (the
                    promoted.yaml pointer, P2-04 split policy, `rag promote`, resolves
                    `promoted` as a run ref), cost.py (PricingTable over
                    configs/pricing.yaml, whole-run estimate, $2 gate, actuals),
                    decision_log.py (machine-appended tables in DECISIONS.md, bounded
                    at the next heading — MIS-018), test_openings.py and
                    cost_approvals.py (the openings and approvals rows),
                    registry.py (retrievers by name), subsample.py (fixed Tier 2 subsample)
  embedding/        base.py — Embedder interface with explicit input_type (query |
                    passage) and a per-family prefix table that REFUSES unknown
                    models; backends: sentence_transformers (local, pinned revision)
                    and openrouter. `dimensions` asks a hosted model for truncated
                    output, is asserted on the response, and joins the index key
                    (P2-08 run 5)
  reranking/        base.py — Reranker interface ONLY; a test fails if an
                    implementation appears without a story

prompts/            versioned YAML, addressed by (id, version). answer.yaml (Phase 0)
                    and baseline_answer.yaml (the Phase 1 control, DEC-042: numbered
                    steps, English, [doc:<id>] on every claim, NO URLs) — Ragas owns
                    the judge prompts. Never inline a prompt in Python. Content hashes
                    are pinned in tests/test_prompts.py, so an edit without a version
                    bump fails the suite. The runner asserts the generator's prompt_ref
                    equals the recorded one (MIS-015).
configs/            experiment configs. promoted.yaml is the committed "current best"
                    (P2-05) — moved only by `rag promote`, never by hand; every axis
                    config is a one-dimension diff against it and carries `axis:`.
                    pricing.yaml is the dated price table the cost estimator reads
                    (`rag pricing refresh`). smoke_p1_09_dense_k10.yaml is the P1-09 diff
                    smoke (baseline_dense with top_k 10). Otherwise: exp_NNNN_*.yaml are experiments and are
                    committed BEFORE their run so git_sha is clean. baseline_dense.yaml
                    is the dense control (EXP-0005) that Phase 2 diffs against (P1-09);
                    baseline_dense_tier2.yaml adds generation + judge (P1-07 run 2,
                    and `rag ask`'s default); exp_0004_bm25_distinct_docs.yaml is the
                    sparse control; exp_0014..0018_hybrid_*_dev.yaml are Axis 3
                    (RRF, then weighted α 0.2/0.4/0.6/0.8; dev only, DEC-056);
                    exp_0019..0022_{sentence_window,parent_document,semantic,
                    structure}_{dev_large,dev}.yaml are Axis 1 (DEC-057; dev_large
                    builds the index, dev decides).
                    smoke_toy*.yaml, smoke_p2_03_llm_rewrite.yaml
                    and tier2_smoke.yaml are harness smoke tests, not experiments.
indexes/            dense vector indexes, <key>/vectors.npy + index.meta.json.
                    GITIGNORED, rebuilt on demand; key = (corpus_hash, normalization,
                    chunker_id, model_id, revision, prefix_convention).
                    sentence_distances/<embedder key>.json is the semantic chunker's
                    cache of consecutive-sentence distances per article text (P2-07)
results/            runs.sqlite — the results store; generation_cache.sqlite — the
                    in-pipeline LLM cache (P2-03). Both GITIGNORED.
  corpus_profile/   <key>.json written by `rag corpus profile`; the EXPERIMENTS.md
                    profile block mirrors it

data/
  authored/         hand-written inputs, VERSION CONTROLLED.
                    unanswerable_seed.yaml lives here; refusal_labels_v1.yaml holds 45
                    hand-labelled answers the refusal detector is tested against (DEC-045)
  frozen/           materialized corpus and splits + *.meta.json. GITIGNORED,
                    rebuilt by `rag corpus freeze` and `rag data splits`,
                    tracked by hash rather than by content.

docs/               the documentation contract (section 2). Deliverables.
  experiments/      per-experiment EXP-NNNN.md files, written from the results store
tests/              pytest. A story is not done until its criteria are a test
                    or a runnable command.
user_stories/       phase handover documents. Input, not deliverable.
```

Two notes on where things live:

- The handover for Phase 0 suggested `rag/adapters/`. It is `rag/dataset/` here,
  which holds both the WixQA loading and the split curation that consumes it. The
  `DatasetAdapter` interface required by P0-11 belongs in that package.
- `data/authored/` versus `data/frozen/` is the load-bearing distinction. Anything a
  human wrote is version controlled and reviewable in a diff. Anything a command
  can regenerate from a pinned revision is gitignored and identified by hash.

### Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | `.python-version` pins 3.11 locally |
| Dependencies | `uv` | `uv pip install -e ".[dev]"` |
| Ingest | HuggingFace `datasets` | split building only; never at runtime |
| Storage | Parquet via `pandas` + `pyarrow` | frozen corpus and splits |
| CLI | `typer` | one `rag` entry point |
| Authored data | `pyyaml` | seed files under `data/authored/` |
| Tests | `pytest` | |
| IR metrics | `ranx` | never hand-roll recall/nDCG/MRR |
| Baseline retriever | `rank-bm25` (Okapi) | tokenizer is ours: lowercase `[a-z0-9]+`, nothing else |
| Corpus profiling | `tiktoken` (`cl100k_base`) | BPE token counts for `rag corpus profile` only; never on the retrieval path |
| Dense index | `numpy` | brute-force cosine; no ANN, nothing approximate to record |
| Local embeddings | `sentence-transformers` — backend built, **not declared** | DEC-041 chose hosted; the local backend stays for Phase 2 and gets declared when a story uses it |
| Results store | SQLite | `runs` and `run_questions` tables |
| LLM access | `httpx` / `openai` client -> OpenRouter | key in `.env`. Chat at `/chat/completions`, embeddings at `/embeddings` (models listed at `/embeddings/models`, NOT `/models`) |
| Judged metrics | `ragas==0.4.3` (exact pin) | metric library ONLY. Not its dataset or experiment layer |
| Config objects | frozen dataclasses today; `pydantic` declared for P0-10 | must hash to a stable `config_hash` |

Rules that outlive any particular library:

- Hash *records*, never file bytes. Parquet output is not byte-reproducible across
  writer versions, so every hash is computed over a canonical serialization of the
  rows. See `rag/hashing.py`.
- One read path per artifact. If a second code path can reach HuggingFace or read a
  parquet file directly, provenance stops being enforceable.
- Everything reproducible from a config file: `run(config) -> row in results store`.
- Hand a metrics library the *ordering* you return, not the scores that produced it.
  Tied scores get re-broken by a rule you did not choose. (MIS-003)
- Design a metric's not-applicable case before its happy path. `None` is not zero,
  and averaging zeros over questions a metric cannot score reads as a system
  failure. (MIS-002)
- Pin judged-metric dependencies **exactly** and record the version on every run.
  Ragas revises metric prompts between releases; an upgrade can move every historical
  score with no config change. `ragas_version` and `metric_prompt_versions` are
  recorded and checked by `rag diff`. (MIS-004, DEC-021)
- Pin the *provider*, not just the model, for any hosted open-weights model. On
  OpenRouter one model is served by many providers with a ~37x speed spread and
  non-identical outputs. Provider identity is part of the judge and is a comparability
  key. (DEC-032)
- **Test every parser of model output on stored model output.** The citation parser
  dropped `[doc: id]` (MIS-016); the refusal detector matched `don't` while the model
  wrote `don’t` and hid 13–18 refusals per Phase 0 run (DEC-045). A refusal is a
  phrase in the answer's first 300 characters with no numbered steps anywhere — a
  caveat after a procedure is a hedged answer, not a refusal.
- **A provider pin is a purchasing decision.** Per-provider prices vary ~12x for the
  same model and live behind `/models/<id>/endpoints`, not the model listing. Cost a
  pin before committing it, and put it to Krutik. (MIS-008, DEC-034)
- **Calibrate estimators on a measured run, then validate them out of sample.** The
  cost estimator's `x3.0` guess was 9x low on output tokens; matching the calibration
  run to 0% proves nothing. `rag/runner/cost.py` records its calibration run id and
  was validated on different questions to within 4%. (DEC-035)
- Third-party eval libraries are metric providers, never the experiment or dataset
  layer. Ragas lives behind the `Judge` interface and a test enforces the boundary,
  so swapping it is a one-file change. (DEC-019)
- To establish that a capability is absent, probe the endpoint that would provide it
  and show the failure. A missing entry in a neighbouring listing is not evidence, and
  a wrong "can't" is costlier than a wrong "can" because nobody re-tests it. (MIS-005)
- Assert that a provider response contains what you asked for, at the point of the
  call. An empty completion is a broken call, not a bad answer — never let a metric be
  the thing that discovers it, because a metric will score nothing as zero. (MIS-006)
- Corpus size, measured: 6,221 articles = 2.96M tokens; 8,694 chunks at 512 words =
  2.86M tokens (mean 329, p95 644, max 1,326). **1.27 tokens per whitespace word.**
  (DEC-029 corrects DEC-005)
- **The control chunk config is 600 words / 100 overlap** (DEC-038) — 8,218 chunks;
  79.0% of articles fit in one chunk. **36.7% of those chunks exceed 512 tokens**
  (p95 748, max 1,336): a 512-context embedding model truncates a third of the
  index silently (preflight item 19).
- **Phase 2 run discipline is in the runner, not in memory.** `axis:` on every
  experiment config; **`dev` decides every axis** — `dev_large` is 6,221 synthetic
  single-gold questions at ceiling (0.973) that flattered a model `dev` rejected by
  16 points, so it is only a direction check (DEC-055 supersedes DEC-050's split rule;
  EXP-0008/0010); Axis 3 and Tier 2 are refused on `dev_large` (DEC-050); a run
  estimated above $2 halts before it starts and needs `--approve-cost` (DEC-052;
  `--estimate-only` is free); `promoted` is a run reference and `rag promote` is the
  only thing that moves `configs/promoted.yaml` (DEC-051).
- **Deterministic metrics get a paired test, judged metrics get an MDD label, and
  both come from the tool, not from prose.** `rag compare` (DEC-047) for retrieval
  deltas; `rag/eval/noise_floor.py` (DEC-048) for judged ones, with "no MDD measured"
  when the run's judge/generator/prompt match no measured family. Any LLM call inside
  retrieval goes through `PipelineLLM` (DEC-049) or it is a bug.
- **`top_k` is distinct documents, not chunks** (DEC-040). The walk scans at most
  `candidate_pool` (50) ranked chunks; one chunk per document reaches the generator;
  the collapse ratio and exhaustion are recorded per question. The frozen text has **no list markers**:
  procedures appear as "To do X:\nClick A. Click B." and are counted by the DEC-039
  heuristic, never by `1.`-style lines (21 articles have one). (MIS-013)

### Models

| Role | Model | Chosen in | Notes |
|---|---|---|---|
| Generator | `openai/gpt-5-nano` | DEC-017 | Held constant across configs. ~$0.06 per Tier 2 dev run. Mostly obeys `[doc:<id>]`, but writes `[doc: id]` with a space 1.5–4% of the time; the parser accepts that since `citation-v2` (MIS-016, DEC-043) and records its version on every run. Answered one typo'd question in Dutch until the prompt said "Answer in English" (DEC-042). |
| Judge (Ragas LLM) | `openai/gpt-oss-120b` — **PLACEHOLDER** | DEC-030, DEC-034 | $0.037/$0.170 per Mtok, 131k ctx. Open-weights, so treated as family `openai-oss`, distinct from the generator's `openai` — a judgment call, see DEC-030 and OQ-014. Judge calls pin `provider: [Cerebras, Groq]` — a 37x speed spread otherwise, and providers do not return identical scores (DEC-032). **Real rate is Cerebras' $0.350/$0.750, not the model-level $0.037/$0.170**: measured **~$0.84 per 100-question Tier 2 run** (DEC-035 corrects DEC-034's $0.48). **Its scores are not measurements and must not reach EXPERIMENTS.md or NARRATIVE.md** (DEC-018). |
| Embedding (Ragas `answer_relevance`) | `qwen/qwen3-embedding-8b` | DEC-027 | $0.010/Mtok, **32,768 context**. Whole index = 2.86M tokens = ~$0.03 to embed. Chosen on context length, not price: 34% of chunks exceed 512 tokens, so a 512-context model would truncate a third of the index. |
| Embedding (dense retrieval) | `qwen/qwen3-embedding-8b` **pinned to DeepInfra** | DEC-041 | Same model as the Ragas embedder; Krutik chose hosted over the handover's local option. **Provider is part of the index key**: DeepInfra and Nebius return different vectors for the same input. Index: 8,218 × 4096 float32 = 134.6 MB, ~20 min and $0.031 to build (EXP-0005), cached under `indexes/`. Queries cost ~$0.0000004 each and are **not byte-deterministic** — three runs ranged 0.005 on strict recall@5 (OQ-023). `qwen3` prefix: instruct prefix on queries, none on passages. |
| Reranker | _not chosen_ | — | Phase 1 at the earliest; interface only in Phase 0. |

An empty row is the honest state, not an omission to paper over. The benchmark's gold
`article_ids` pay for every retrieval metric plus citation precision/recall and step
coverage for free, so a judge is only needed for faithfulness (which no static
benchmark can label, since it depends on what *this run* retrieved) and for answer
correctness.

Two constraints now bind this table, both enforced in code rather than by intent:

- **Judge family must differ from generator family.** `RunConfig` refuses the pairing
  outright — same-family judging carries unmeasured self-preference bias (P0-07).
  Family comes from `model_family()`, which maps `openai/gpt-oss-*` to `openai-oss`
  because those are open-weights models rather than the hosted GPT line. Disagree with
  that? Change `_FAMILY_OVERRIDES` in `rag/eval/judge.py` and log a decision — do not
  work around the guard. (DEC-030)
- **Ragas `answer_relevance` needs an embedding model.** Now configured (DEC-027), so
  all three judged metrics run. If `judge_embedding_model` is ever cleared, the
  criterion is recorded in `skipped_criteria` rather than quietly absent.
- **Reasoning models spend completion tokens before answering.** `gpt-5-nano` at
  `max_tokens=800` returned `content: None`. The generator now raises
  `EmptyGenerationError` rather than passing an empty answer to the metrics, which
  would score as a genuinely bad answer. (MIS-006, DEC-028)

Access is via **OpenRouter**; the API key is already in `.env` at the repo root
(gitignored). Read it from the environment — never print, commit, or echo it.

Rules for this table:

- **Krutik chooses every model. Ask him.** When a model decision comes up, stop and
  put the choice to him with the cost, latency, and bias tradeoffs laid out. Do not
  pick a reasonable default and carry on, and do not log the choice as `Joint` or
  `Krutik` in `docs/DECISIONS.md` if you made it. Do everything that does not depend
  on the answer first, then ask.
- Every entry needs a `DEC-NNN` in `docs/DECISIONS.md` before it is used in a run.
  Model choice is exactly the kind of decision that is expensive to reverse: it
  starts a new comparison family.
- **Pin an exact model id**, never a floating alias. A provider silently updating
  the model behind an alias invalidates every comparison across that boundary, and
  nothing in the artifacts would show it.
- The judge model id and the judge prompt version are recorded on every score
  (P0-07). Swapping either must be visible in the results store.
- **Open question, flag rather than guess:** using the same model family for judge
  and generator risks self-preference bias. That needs a decision entry with its
  reasoning, not a default.
- Runs that used different judge models are not comparable. Say so rather than
  quietly presenting the delta.
