# Phase 1 — Dense Baseline on WixQA

**Handover document for Claude Code.**
Status: ready to implement once Phase 0 definition-of-done is met. Estimated: 1 week.
Companion doc: `phase0-user-stories.md` (harness). Story ids referenced as `P0-xx`.

---

## 1. Context

Phase 1 produces the **control** that every later technique is measured against. It is
deliberately boring: fixed chunks, one embedding model, dense retrieval, one prompt, inline
citations, no cleverness. The output is a working end-to-end answer with a traceable source
paragraph, plus a baseline scorecard.

The harness from Phase 0 is assumed to exist: frozen corpus, curated splits, document-level
qrels, two-tier eval, `runs` + `run_questions` results store, `rag diff`.

### Four facts that shape this phase

1. **Phase 0 already recorded a sparse baseline (P0-13).** Phase 1 must not create a second,
   incomparable reference line. The two are reconciled into one control family — see P1-01.
2. **Top-k chunks is not top-k documents.** Gold is document-level and multi-doc questions need
   2–3 *distinct* documents. Adjacent chunks from one article collapse into one document, so a
   naive top-5-chunks retriever structurally caps strict recall on multi-hop questions.
3. **Reference answers are procedural markdown.** If the baseline prompt emits prose, answer
   correctness and step coverage punish format rather than substance, and every later comparison
   inherits that noise.
4. **This corpus favours lexical matching.** Enterprise KB text is dense with exact product names
   (*Wix Payments*, *Quick Action Bar*, *iCal*, *og:image*). BM25 is a serious opponent here, not
   a straw man.

---

## 2. Non-goals for Phase 1

Do not implement, and do not let these leak in:

- Hybrid retrieval, reranking, query rewriting, HyDE, multi-query, agentic loops.
- Structure-aware or semantic chunking. Fixed-size only.
- Citation enforcement or refusal logic. Phase 1 measures how badly the naive system fails at
  refusal; it does not fix it.
- Prompt iteration for quality. One prompt, one version, frozen.
- Embedding model comparison. One model. Sweeps are Phase 2.

If a story appears to need one of these to pass, stop and flag it.

---

## 3. User stories

---

### P1-01 — Reconcile the chunk config with the Phase 0 baseline

**As the project, I need the sparse and dense baselines to differ in exactly one dimension, so
"does dense beat lexical here?" is an answerable question rather than a confounded one.**

Context: P0-13 recorded BM25 with 512-token chunks. Phase 1 uses 600/100. Two controls with
different chunking are not comparable.

Acceptance criteria:
- One chunk configuration is chosen for both controls and recorded in `docs/DECISIONS.md`:
  **fixed 600 tokens, 100 overlap** (default recommendation), or 512/0 if there is a reason to
  prefer the Phase 0 value. Either is acceptable; divergence is not.
- The Phase 0 sparse baseline is **re-run** under the reconciled config and recorded as a new
  experiment row. The original row is kept, not overwritten, and annotated as superseded.
- After this story, sparse and dense controls differ only in the retrieval method.

---

### P1-02 — Corpus profiling before chunking

**As an experimenter, I need to know the shape of the corpus, so chunking results are
interpretable rather than mysterious.**

Acceptance criteria — a `rag corpus profile` command emits, and writes into
`docs/EXPERIMENTS.md` as a characterization (not an experiment):
- Article length distribution over all 6,221 KB docs, in tokens: min, p25, median, p75, p90, max,
  plus a histogram.
- **Fraction of articles that fit entirely within one 600-token chunk.** Rationale: if that
  fraction is large, chunking barely applies to those articles, and any Phase 2 chunk-size sweep
  will show a flat curve on single-doc questions. Knowing this up front converts a confusing
  result into an expected one.
- Count and fraction of articles containing numbered step lists.
- **Count of chunk boundaries that land mid-procedure** (inside a numbered list) under the
  reconciled 600/100 config. This is the "before" number for the Phase 2 structure-aware chunker.
- Breakdown of all of the above by `article_type` (`article` / `feature_request` / `known_issue`).

---

### P1-03 — Retrieve k distinct documents, not k chunks

**As the retriever, I must return 5 distinct documents, because document-level gold with 2–3
required documents cannot be satisfied by chunks that collapse into fewer documents.**

Acceptance criteria:
- The retriever's `k` parameter is defined at the **document** level. It walks the ranked chunk
  list, max-pools by `doc_id` (per P0-05), and continues until 5 distinct documents are collected
  or the candidate pool is exhausted.
- A candidate pool cap exists and is configurable (e.g. scan at most 50 chunks) so a pathological
  query cannot walk the whole index. Exhaustion without reaching k is recorded per question.
- **Chunk→document collapse ratio** is a first-class metric: chunks scanned ÷ distinct documents
  returned, reported as mean and p90, per run and per slice.
- Unit test: a query whose top 5 chunks all belong to 2 documents must still return 5 distinct
  documents, and the collapse ratio must be recorded as ≥ 2.5.
- Rationale, recorded in `docs/DECISIONS.md`: without this, strict recall on multi-hop is capped
  by retrieval granularity, and Phase 2 would waste effort tuning embeddings against a problem
  that is not an embedding problem.

---

### P1-04 — Embedding and indexing

**As the baseline, I need one embedding model, indexed reproducibly.**

Acceptance criteria:
- One local sentence-transformers model (bge-base or e5-base class). Model id and revision
  recorded on every run. Rationale for local: 6,221 docs re-indexes in minutes, keeping the
  control cheap and fully reproducible.
- **Query/passage prefixes are handled correctly.** The e5 and bge families require asymmetric
  prefixes; omitting them degrades results silently with no error.
  - The `Embedder` interface takes an explicit `input_type` of `query` or `passage`.
  - A test asserts the prefix is applied for the configured model family.
  - Seed `docs/MISTAKES.md` now: *"e5/bge require query/passage prefixes. Omitting them produces
    no error, just worse numbers that get misattributed to architecture."*
- Index build is deterministic given `(corpus_hash, normalization_version, chunk_config,
  model_id)`, and that tuple is recorded on every run.
- Index build time and index size are logged.

---

### P1-05 — The single baseline prompt

**As the baseline, I need one frozen prompt whose output format matches the reference answers,
so quality metrics measure substance rather than formatting.**

Acceptance criteria:
- Exactly one prompt, in `prompts/` as `baseline_answer@v1`, loaded by id and version (P0-11).
- The prompt instructs **numbered step-list output** when the question is procedural, matching
  the WixQA reference answer style.
- The prompt instructs the model to cite by `doc_id` for every claim.
- **The generator must not emit URLs.** Links are injected from the doc store `url` field at
  render time, never generated. A test asserts no URL-shaped string appears in raw model output.
- Recorded in `docs/DECISIONS.md` as a **controlled confound**: step-list output is chosen to
  match the evaluation reference format, not because it was found to be better. Phase 2 may
  revisit.
- The prompt is frozen for the whole phase. Any edit requires a version bump and invalidates the
  control.

---

### P1-06 — Citation rendering and the traceable source paragraph

**As a user, I need to see the exact paragraph an answer came from.**

Acceptance criteria:
- Citations are carried internally as `doc_id`.
- Rendered output shows, for each citation: article title, article URL (from the doc store), and
  the **exact retrieved chunk text**.
- A CLI command answers a question and prints: question → step-formatted answer → citation block
  as above.
- Because citations are `doc_id`s, citation precision/recall against `gold_doc_ids` is computed
  automatically with no LLM call (P0-07). Verify this path works end to end.

---

### P1-07 — Baseline runs

**As the project, I need the control runs recorded.**

Acceptance criteria — four runs recorded in the results store, all on the reconciled chunk config:

| # | Config | Tier | Split | Purpose |
|---|---|---|---|---|
| 1 | Dense, 5 distinct docs | 1 | `dev` | The dense control |
| 2 | Dense, 5 distinct docs | 2 | `dev` | First end-to-end, with judge metrics |
| 3 | Dense, 5 distinct docs | 1+2 | `unanswerable` | Baseline refusal behaviour |
| 4 | Sparse (BM25), 5 distinct docs | 1 | `dev` | Re-run sparse control (P1-01) |

- Run 3 measures how often the baseline confidently answers with no supporting document. The
  baseline has no refusal mechanism, so this is expected to fail; the number is the target that
  Phase 2 citation enforcement is measured against.
- **`test` stays closed for the whole phase.** No `--open-test`.
- Every run row carries the full provenance tuple from P0-10.

---

### P1-08 — Baseline scorecard

**As the project, I need one scorecard that later phases diff against.**

Acceptance criteria — `docs/EXPERIMENTS.md` gains a Phase 1 scorecard containing, for runs 1–4:
- Strict and loose recall@{1, 3, 5, 10}, document level.
- nDCG@10.
- MRR, single-gold-doc subset only.
- Chunk→document collapse ratio (mean, p90).
- Candidate-pool exhaustion rate.
- Faithfulness, answer relevance, answer correctness (Tier 2).
- Citation precision and recall.
- Step coverage: fraction of gold steps present, and order preservation.
- False-answer rate on `unanswerable`; false-refusal rate on `dev`.
- p95 latency, cost per query, tokens per query.
- Index build time and size.

All of the above **broken out by the P0-08 slices**. The single-doc vs multi-hop split is the
one that matters most — report it first.

- A short dense-vs-sparse comparison section: where each wins, by slice. No conclusions beyond
  what the numbers show.
- Every judged metric in the scorecard is reported **with its minimum detectable difference from
  P1-11**, e.g. `faithfulness 0.71 (MDD ±0.04)`. A scorecard entry without an MDD is incomplete.

---

### P1-09 — Diffability exit criterion

**As Phase 2, I need every technique to be expressible as a diff against this control.**

Acceptance criteria:
- The dense control config is saved as `configs/baseline_dense.yaml` and referenced by id.
- `rag diff <phase2_run> <baseline_dense_run>` runs successfully and lists questions whose strict
  recall outcome flipped in either direction, with gold docs and retrieved ranks.
- A smoke test proves this: take the baseline, change only `k` from 5 to 10, run it, and confirm
  `rag diff` produces a sensible flip list.

---

### P1-10 — Hypotheses log

**As the hiring narrative, I want a record of what I expected versus what happened.**

Context: `docs/EXPERIMENTS.md` is strictly no-predictions — run the experiment, record the result.
But expectations are worth capturing somewhere, because calibration is a more interesting artifact
than execution alone.

Acceptance criteria:
- New file `docs/HYPOTHESES.md`. Each entry: date, the hypothesis, the run that will test it,
  and later a resolution marked **confirmed**, **wrong**, or **inconclusive** with a link to the
  experiment row.
- Predictions never appear in `docs/EXPERIMENTS.md`.
- Seed entries for this phase (write before running):
  - Whether dense beats sparse overall on this corpus, and per slice.
  - Whether multi-hop strict recall lags single-doc substantially.
  - Expected chunk→document collapse ratio.
  - Expected false-answer rate on `unanswerable`.

---

### P1-11 — Judge variance and minimum detectable difference

**As the project, I need to know how noisy my evaluator is, before I trust any improvement it
reports.**

Context: Ragas metrics are LLM-judged and therefore stochastic. If a Phase 2 reranker improves
faithfulness by 3 points and the judge's own run-to-run spread is 4 points, nothing has been
learned — and that will not be visible unless it is measured. This is the difference between a
portfolio project that reports gains confidently and one that reports them correctly.

Acceptance criteria:
- The Phase 1 dense baseline Tier 2 config is run **three times, entirely unchanged**, on the same
  fixed dev subsample, at judge temperature 0.
- For each judged metric (faithfulness, answer relevance, answer correctness), compute mean and
  standard deviation across the three runs, at both corpus level and per slice.
- Derive and record a **minimum detectable difference (MDD)** per metric — the threshold below
  which a change is indistinguishable from judge noise. State the rule used to derive it
  (e.g. 2× the observed standard deviation) in `docs/DECISIONS.md`.
- MDD values are written into `docs/EXPERIMENTS.md` as a standing reference table, and referenced
  by the Phase 1 scorecard (P1-08).
- Sanity check: the rule-based and label-based metrics — citation precision/recall, step coverage,
  and all retrieval metrics — must be **identical** across all three runs. Any variance there is a
  bug (non-determinism leaking into retrieval or parsing), not judge noise. Fail the story if they
  differ.
- Seed `docs/MISTAKES.md`: *"Never report a judged-metric improvement smaller than its MDD as a
  win. Report it as 'within judge noise'."*
- Cost of the three runs is recorded, since this repeats at any judge or Ragas version change.

---

## 4. Phase 1 definition of done

1. Chunk config reconciled; sparse baseline re-run under it.
2. Corpus profile recorded, including mid-procedure boundary count.
3. Retriever returns k **distinct documents**; collapse ratio instrumented; pooling test passes.
4. One embedding model indexed reproducibly, with query/passage prefixes verified by test.
5. One frozen prompt producing step-list output; generator emits no URLs.
6. CLI shows question → answer → article title, URL, exact chunk.
7. Four runs recorded; `test` untouched.
8. Baseline scorecard in `docs/EXPERIMENTS.md`, sliced.
9. `rag diff` smoke test passes against `configs/baseline_dense.yaml`.
10. `docs/HYPOTHESES.md` exists with Phase 1 entries resolved.
11. Judge variance measured over three identical runs; MDD table recorded; non-judged metrics
    verified identical across all three.

---

## 5. Open questions for the human

Flag rather than guess:
- Which embedding model specifically, and confirmation of its prefix convention.
- Generator model for Tier 2. The judge-family question is **resolved** — it must differ from the
  generator's family (P0-07) — but the specific pairing still needs choosing.
- Whether the candidate-pool cap of 50 chunks is right, given the collapse ratio observed in P1-02.
- Whether the prompt should branch on procedural vs non-procedural questions, or use one
  step-list instruction throughout. One prompt is simpler and is the recommended default.