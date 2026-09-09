# Phase 0 — Evaluation Harness on WixQA

**Handover document for Claude Code.**
Status: ready to implement. Estimated: 1 week.

---

## 1. Context

We are building a production-grade RAG system as a portfolio project. Phase 0 builds the
**measurement harness only** — no retrieval quality work, no clever techniques. Everything in
Phases 1–3 will be judged against the baseline this phase produces, so correctness and
reproducibility matter more than features.

**Dataset: WixQA** (`Wix/WixQA` on HuggingFace, MIT licence, cite "Wix.com AI Research").

| Config | Contents | Rows |
|---|---|---|
| `wix_kb_corpus` | Wix Help-Center snapshot (2024-12-02, English), HTML-stripped | 6,221 |
| `wixqa_expertwritten` | Real support tickets + expert-written answers, multi-doc | 200 |
| `wixqa_simulated` | Answers distilled from user–expert chats, multi-doc | 200 |
| `wixqa_synthetic` | LLM-generated Q-A, single-doc | 6,221 |

Fields — Q-A configs: `question`, `answer` (markdown), `article_ids` (list of KB doc ids).
Corpus: `id`, `url`, `contents`, `article_type` (`article` | `feature_request` | `known_issue`).

Reference paper: Cohen et al. (2025), *WixQA: A Multi-Dataset Benchmark for Enterprise
Retrieval-Augmented Generation*, arXiv:2505.08643.

### Three facts that shape every design decision here

1. **Ground truth is document-level, not chunk-level.** We retrieve chunks but are scored on
   documents. Every retriever must expose a `chunk_id → doc_id` mapping and a documented
   pooling rule.
2. **The golden set already exists and is human-verified.** We curate splits; we do not author
   Q-A pairs. The one exception is the unanswerable set, which WixQA does not provide.
3. **There is no parsing stage.** The corpus ships as clean text, so "freeze the corpus" means
   pinning a dataset revision and hashing the materialized artifact, not building a parser.

---

## 2. Non-goals for Phase 0

Do not implement, and do not let these leak into the harness:

- Any retrieval technique beyond the dumb baseline (BM25, fixed-size chunks, top-k).
- Hybrid retrieval, rerankers, query rewriting, HyDE, multi-query, agentic loops.
- Data cleansing or conditioning beyond the single normalization decision in P0-02.
- A UI. CLI only.
- Fine-tuning anything.

If a story seems to need one of these to pass, stop and flag it rather than building it.

---

## 3. Technical constraints

- Python 3.11+, `uv` or `poetry` for dependency management.
- HuggingFace `datasets` for ingest; local **Parquet** for the frozen corpus and splits.
- **SQLite** for the results store (single file, committed-adjacent but gitignored).
- IR metrics via **`ranx`** or **`pytrec_eval`** — do not hand-roll recall/nDCG/MRR.
- Judged generation metrics via **Ragas**, pinned to an exact version. Used as a *metric library
  only*, never as the experiment or dataset layer — see P0-07.
- Prompts in versioned YAML under `prompts/`, loaded by id + version. Never inline in Python.
- Config objects are frozen dataclasses or Pydantic models, hashable to a stable `config_hash`.
- Everything reproducible from a config file: `run(config) → row in results store`.

### Suggested repo layout

```
rag/
  adapters/        # DatasetAdapter — WixQA -> internal types
  corpus/          # freeze, normalize, hash
  chunking/        # Chunker
  embedding/       # Embedder
  retrieval/       # Retriever, chunk->doc pooling
  reranking/       # Reranker (interface only in Phase 0)
  assembly/        # ContextAssembler
  generation/      # Generator
  eval/            # metrics, Judge, tiers
  runner/          # run(config), results store
prompts/           # versioned YAML
configs/           # experiment configs
data/
  frozen/          # materialized corpus + splits (gitignored, hash-tracked)
docs/
  NARRATIVE.md
  EXPERIMENTS.md
  DECISIONS.md
  MISTAKES.md
tests/
```

---

## 4. User stories

Each story lists acceptance criteria. A story is not done until its criteria are demonstrably
true via a test or a runnable command.

---

### P0-01 — Freeze the corpus

**As the harness, I need a byte-identical corpus across every experiment, so retrieval
differences are never confounded by input differences.**

Acceptance criteria:
- A command `rag corpus freeze` materializes `wix_kb_corpus` from a **pinned HF revision**
  (commit SHA, not `main`) to `data/frozen/corpus.parquet`.
- The pinned revision SHA and the KB snapshot date (2024-12-02) are recorded in the artifact
  metadata and in `docs/DECISIONS.md`.
- A `corpus_hash` is computed over the materialized artifact (sorted by `id`, stable field
  order) and printed. Re-running the command on an unchanged revision produces the same hash.
- Loading the corpus anywhere else in the codebase goes through one function that returns the
  frozen artifact and its hash. No other code path touches HuggingFace at runtime.

---

### P0-02 — Decide and freeze text normalization

**As the harness, I need one explicit, versioned normalization rule, so a quiet change to text
handling can never silently invalidate past results.**

Context: article text contains many markdown links and dashboard deep-links.

Acceptance criteria:
- A `normalization_version` string (e.g. `norm-v1`) is defined and stored with the corpus.
- The rule is implemented and documented in `docs/DECISIONS.md`: whether link URLs are included
  in the **embedded/indexed** text. Link URLs must be preserved in the **stored** document
  regardless, because citation display needs them.
- Default recommendation unless there is a reason to differ: strip URL targets from indexed
  text, keep anchor text, keep full original in the stored doc.
- Changing the rule requires bumping `normalization_version`; the runner records it on every run.

---

### P0-03 — Curate evaluation splits

**As an experimenter, I need fixed, provenance-tracked splits, so I can iterate without
contaminating my final numbers.**

Acceptance criteria:
- `rag data splits` produces four artifacts under `data/frozen/`, each with a hash:
  - `test.parquet` — 100 ExpertWritten + 100 Simulated. **Held out.**
  - `dev.parquet` — the remaining 100 + 100.
  - `dev_large.parquet` — full `wixqa_synthetic` (6,221).
  - `unanswerable.parquet` — see P0-04.
- Split assignment is deterministic (fixed seed, recorded) and stratified by `len(article_ids)`
  so multi-doc questions are represented in both dev and test.
- Each row carries: `question`, `answer`, `gold_doc_ids`, `source_config`, `n_gold_docs`,
  and `article_types` (joined from the corpus).
- `dev_large` is flagged in code and docs with the leakage warning: synthetic questions were
  generated *from* the article they are grounded in, so lexical overlap is inflated and BM25
  scores are optimistic. It is for statistical power on retrieval-only sweeps, never for
  headline numbers.

---

### P0-04 — Build the unanswerable set

**As an experimenter, I need questions the system must refuse, because WixQA contains none and
refusal behaviour is a Phase 2 deliverable.**

Acceptance criteria:
- 40–50 questions in `unanswerable.parquet`, each with `gold_doc_ids = []` and a `reason` field
  drawn from three buckets, roughly balanced:
  - **out-of-scope-platform**: same task phrasing but for Shopify / Squarespace / Webflow.
  - **post-snapshot**: Wix features or changes that postdate 2024-12-02.
  - **underspecified**: ambiguous questions with no single grounded answer.
- Authored by hand (LLM may draft, human verifies each one). Provenance and author recorded in
  the file.
- **Hard constraint:** this set must NOT be constructed by deleting articles from the index.
  Doing so changes `corpus_hash` and breaks comparability with every other run.

---

### P0-05 — Document-level qrels and chunk→doc pooling

**As the harness, I need chunk retrieval scored against document-level ground truth, correctly.**

Acceptance criteria:
- Every `Chunker` output carries `chunk_id` and `doc_id`. The mapping is persisted with the index.
- The `Retriever` interface returns ranked chunks **and** a ranked document list produced by an
  explicit pooling rule. Default: **max score over a document's chunks**. The rule is named in
  the config (`doc_pooling: max`) and recorded on every run.
- Qrels are emitted in a format `ranx`/`pytrec_eval` accepts, with binary relevance.
- Unit test: a synthetic case where the correct document's best chunk ranks 3rd among chunks but
  the document must rank 1st after pooling.

---

### P0-06 — Retrieval metrics

**As an experimenter, I need retrieval metrics that reflect how this dataset actually fails.**

Acceptance criteria, all computed at document level via `ranx`/`pytrec_eval`:
- **Strict recall@k** — fraction of questions where *all* gold docs appear in top-k. This is the
  headline retrieval metric.
- **Loose recall@k** — fraction where *any* gold doc appears in top-k.
- **nDCG@10**, binary relevance.
- **MRR**, computed **only** on the single-gold-doc subset. It is not meaningful with 2–3 gold
  docs; the harness must refuse to report it over the full set.
- k values reported: 1, 3, 5, 10, 20.
- Every metric is also emitted per slice (see P0-08).
- **Ragas `context_precision` and `context_recall` are explicitly NOT used.** They are LLM-judged
  approximations of retrieval quality, built for projects with no retrieval ground truth. WixQA
  ships `article_ids`, so we have real qrels; estimating labelled recall with a judge would be
  slower, costlier, non-deterministic and less defensible. Record this as a decision in
  `docs/DECISIONS.md`. Retrieval evaluation belongs to `ranx`/`pytrec_eval`; Ragas owns P0-07 only.

---

### P0-07 — Generation metrics

**As an experimenter, I need answer-quality metrics that exploit the gold answers and gold
article ids we now have.**

**Judged metrics come from Ragas. Label-based and rule-based metrics do not.**

Acceptance criteria — via Ragas:
- **Faithfulness** — are generated claims supported by the retrieved context.
- **Answer relevance** — does the answer address the question.
- **Answer correctness** — generated answer vs. the WixQA reference answer, with the reference
  supplied. Note it blends factual and semantic-similarity components and is noisy on long
  procedural answers; record the weighting used.

Acceptance criteria — NOT via Ragas:
- **Citation precision / recall** — computed by comparing cited `doc_id`s against `gold_doc_ids`.
  No LLM call, no manual judgment. Free because of `article_ids`.
- **Step coverage** — WixQA answers are procedural markdown. Extract the ordered step list from
  the reference answer and from the generated answer, and report (a) fraction of gold steps
  present and (b) whether order is preserved. **Rule-based, not LLM-judged** — this is exactly
  computable, and a judge would only add variance to a deterministic quantity. Rationale:
  procedural QA fails by retrieving the right article and then dropping or reordering steps;
  faithfulness will not catch that.
- **Refusal metrics** on the unanswerable set: refusal rate (should approach 1.0) and, on the
  answerable dev set, false-refusal rate (should approach 0.0).

Acceptance criteria — Ragas integration boundary:
- Ragas is called **behind the `Judge` interface** (P0-11). Nothing outside `rag/eval/` imports it.
- **Do not adopt Ragas's `Dataset`, `experiment`, or result-logging abstractions.** Ragas has moved
  from a RAG-eval library toward a general LLM-app eval product with its own dataset management
  and experiment tracking; using those would duplicate and fork the Phase 0 results store, and
  `rag diff` would stop working. Call metrics, take scores, write them to our own SQLite rows.
- **Pin Ragas to an exact version** and record `ragas_version` on every run row. The v0.1→v0.2
  migration was breaking (`EvaluationDataset`/`SingleTurnSample` replacing HF datasets; metrics
  initialized with an explicit evaluator LLM rather than passed to `evaluate()`; `ascore`
  deprecated for `single_score`), and it has kept moving. A silent prompt change inside a Ragas
  metric on upgrade would invalidate every historical comparison in `docs/EXPERIMENTS.md`.
  Seed this into `docs/MISTAKES.md`.
- **Judge temperature is 0** and is recorded.
- **The judge must be a different model family from the generator**, to avoid same-family
  self-preference bias. Record the pairing in `docs/DECISIONS.md`.
- The judge model id, judge family, temperature, Ragas version, and metric prompt versions are
  recorded on every score. Swapping any of them must be visible in the results store.

---

### P0-08 — Slice reporting

**As an experimenter, I need every metric broken down by slice, because aggregates hide the
findings.**

Acceptance criteria — every run emits metrics for the whole split and for these slices:
- `n_gold_docs == 1` (single-doc) vs `> 1` (multi-hop).
- `article_type`: `article` / `feature_request` / `known_issue`.
- Source config: `expertwritten` vs `simulated`.
- Question length buckets (tercile split, boundaries recorded).

---

### P0-09 — Two-tier evaluation loop

**As an experimenter, I need cheap experiments to be cheap, so I can sweep parameters without
burning judge-model budget.**

Acceptance criteria:
- **Tier 1** — retrieval metrics only. Zero LLM calls. Must complete a full `dev` run in seconds
  and a full `dev_large` run in minutes. This is the default tier.
- **Tier 2** — Tier 1 plus generation and judge metrics. Run only on promoted configs.
  - Ragas is expensive per sample: faithfulness decomposes an answer into claims and verifies each
    one, so a single question costs several LLM calls per metric. At 400 dev questions across
    dozens of experiments this compounds fast.
  - Tier 2 therefore **defaults to a fixed dev subsample** (recommend 100, seed recorded, same
    subsample every run so results stay comparable). Full-dev Tier 2 requires an explicit
    `--full-dev` flag.
  - Estimated judge cost is printed before a Tier 2 run starts.
- The tier is a first-class config field and is recorded on every run row.
- The runner refuses to run Tier 2 against `test` unless an explicit `--open-test` flag is
  passed, and logs the event (see P0-12).

---

### P0-10 — Experiment runner and results store

**As an experimenter, I need `run(config) → recorded result`, with enough provenance to
reproduce and enough detail to diagnose.**

Acceptance criteria — SQLite with two tables:

**`runs`** (one row per experiment):
`run_id`, `timestamp`, `config_hash`, `config_json`, `corpus_hash`, `normalization_version`,
`hf_revision`, `dataset_config`, `split`, `split_hash`, `git_sha`, `git_dirty` (bool),
`eval_tier`, `eval_subsample_id`, `doc_pooling`, `judge_model`, `judge_family`,
`judge_temperature`, `ragas_version`, `prompt_versions`, `metric_prompt_versions`,
plus all aggregate metrics.

**`run_questions`** (one row per question per run):
`run_id`, `question_id`, `retrieved_doc_ids` (ranked), `retrieved_chunk_ids` (ranked), `scores`,
`gold_doc_ids`, per-question metric values, `generated_answer` (Tier 2), `cited_doc_ids`,
`latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`.

Additional criteria:
- `git_dirty = true` runs are recorded but marked; the runner warns loudly.
- A `rag diff <run_a> <run_b>` command lists questions whose strict-recall outcome flipped in
  either direction, with their gold docs and retrieved ranks.
- Rationale for `run_questions`: aggregates tell us a technique gained 4 points; per-question
  rows tell us *which* questions flipped and why. That is the entire content of the findings
  document.

---

### P0-11 — Interfaces and prompt versioning

**As a future phase, I need to swap components without touching the runner.**

Acceptance criteria — these interfaces exist with at least one concrete implementation each
(Phase 0 implementations may be trivial):
- `DatasetAdapter` — maps a source dataset to `(question, answer, gold_doc_ids, metadata)`. The
  runner must not import anything WixQA-specific. Dropping in a second benchmark later should
  require only a new adapter.
- `Chunker`, `Embedder`, `Retriever`, `Reranker` (interface only — no implementation in Phase 0),
  `ContextAssembler`, `Generator`.
- `Judge` — wraps Ragas. Takes `(question, answer, contexts, reference)` and returns named scores
  plus the provenance fields in P0-10. This interface is the *only* place Ragas is imported, so a
  Ragas major-version change or a swap to another judge library is a one-file change. A test
  asserts no Ragas import exists outside `rag/eval/`.
- Prompts live in `prompts/*.yaml`, addressed by `(id, version)`. The runner records the exact
  versions used. A prompt edit without a version bump should fail a test.

---

### P0-12 — Test-split discipline

**As the project, I need protection against overfitting 400 gold questions across dozens of
experiments.**

Acceptance criteria:
- Running against `test` requires the explicit `--open-test` flag.
- Each opening appends a row to `docs/DECISIONS.md`: date, config hash, git SHA, reason.
- The runner prints the number of previous test openings and the date of the last one.
- `docs/MISTAKES.md` is seeded with the entry: *"Risk: 400 gold pairs, dozens of experiments.
  Iterating on test numbers will produce a system tuned to the test set and disappointing real
  performance. Test split opens at phase boundaries only."*

---

### P0-13 — Baseline run (exit criterion)

**As the project, I need one recorded baseline number that every later result is measured against.**

Acceptance criteria:
- A single command runs: BM25, fixed 512-token chunks (no overlap), top-5, no reranker, Tier 1,
  on `dev`.
- It produces a `runs` row with strict recall@5, loose recall@5, nDCG@10, MRR (single-doc subset),
  p95 latency, and cost per query.
- The result is written into `docs/EXPERIMENTS.md` as experiment #1, **before any technique work
  begins**.
- A Tier 2 variant of the same config is run once so generation and judge metrics are exercised
  end to end.

---

### P0-14 — Optional: reproduce the published baseline

**As the hiring narrative, I want a reference point rather than an unanchored number.**

Acceptance criteria:
- Read the eval section of arXiv:2505.08643 and record in `docs/DECISIONS.md` where our metric
  definitions match the paper's and where they deliberately differ.
- If comparable, run the paper's baseline configuration and record our numbers next to theirs in
  `docs/EXPERIMENTS.md`.
- Do this **before** finalizing metric definitions in P0-06, so the definitions are comparable.

---

## 5. Documentation discipline (applies to every story)

- `docs/NARRATIVE.md` — the running story of the project.
- `docs/EXPERIMENTS.md` — every run and its results. **No predictions.** Run the experiment,
  then record what happened.
- `docs/DECISIONS.md` — decisions made, by whom, and why. Includes the test-openings log.
- `docs/MISTAKES.md` — mistakes not to repeat.

Claude Code should append to these as part of the work, not as an afterthought.

---

## 6. Phase 0 definition of done

1. `rag corpus freeze` produces a stable `corpus_hash`.
2. Four splits exist with hashes and provenance; the unanswerable set is hand-verified.
3. Document-level qrels work, with a passing pooling unit test.
4. Tier 1 runs `dev` in seconds; Tier 2 runs end to end at least once.
5. The results store has both `runs` and `run_questions`; `rag diff` works between two runs.
6. Baseline experiment #1 is recorded in `docs/EXPERIMENTS.md`.
7. Test split has been opened zero or one times, and the log says which.

---

## 7. Open questions for the human

Flag rather than guess:
- Embedding model and generator model choices for the Tier 2 smoke run (cost/latency implications).
- Judge model — **resolved**: must be a different family from the generator (P0-07). Still open is
  *which* family, given the generator choice above.
- Whether `dev_large` sweeps should run on a subsample (e.g. 1,000) by default to keep the loop fast.