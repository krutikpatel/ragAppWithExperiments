# Decisions

Append-only. Every consequential decision, who made it, and the condition that
would make us revisit it. A superseded decision keeps its entry and gains a
`Superseded by DEC-NNN` status.

**Test-split openings log:** see the bottom of this file. Zero openings so far.

---

## DEC-001 — Pin the corpus to one HuggingFace commit
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-01; Krutik not in the loop)
- **Status:** Active
- **Context:** `Wix/WixQA` on the Hub can move. A retrieval difference caused by a
  changed corpus would be indistinguishable from one caused by a technique.
- **Options considered:**
  1. Track `main` — rejected, silently mutable.
  2. Pin the commit SHA and materialize locally — chosen.
  3. Vendor the raw JSONL into the repo — rejected, ~100MB of data in git.
- **Decision:** Pin `d662dc42479c14e202eccd832f8c4b66a035c4cc`. KB snapshot date
  2024-12-02. Materialize to `data/frozen/corpus.parquet`, gitignored, reproducible
  by `rag corpus freeze`. All reads go through `rag.corpus.loader.load_corpus`; no
  other code path may touch the Hub at runtime.
- **Evidence:** Measured — 6,221 documents; `corpus_hash =
  sha256:74694ad4a96b62433813cf65b4f6f2c7fdbfaad0dfd8a5689121f6851ab80ec0`,
  reproduced identically on a second materialization (`rag corpus verify`).
- **Consequences:** Upstream fixes to WixQA do not reach us until we bump the pin,
  which starts a new comparison family.
- **Revisit if:** Wix publishes a corrected corpus revision, or we add a second
  benchmark.

## DEC-002 — Normalization `norm-v1`: strip markdown link targets only
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-02)
- **Status:** Active
- **Context:** P0-02 asks for one explicit, versioned rule covering link handling.
  The handover assumed article text is dense with markdown links and dashboard
  deep-links.
- **Options considered:**
  1. Strip URL targets from indexed text, keep anchor text, keep the original in
     the stored document — chosen (the handover's default recommendation).
  2. Strip bare URLs too — rejected: URLs are exact terms a user may search for,
     and removing them would delete signal the BM25 baseline can legitimately use.
  3. Also normalize whitespace and unicode — rejected as data cleaning, which is
     out of scope for this project.
- **Decision:** `norm-v1` = `[anchor](target)` → `anchor` in indexed text. Nothing
  else. `contents` is stored verbatim; `indexed_text` is the derived column.
- **Evidence:** Measured — of 6,221 documents, **2 contain any markdown link**
  (3 links total); 128 contain a bare URL. The rule is close to a no-op on this
  corpus. The links the handover expected live in the unused `html_content` field
  and in the gold *answers*, not in article text. See MIS-001.
- **Consequences:** Indexed and stored text are near-identical today. The
  mechanism still matters: it is the seam where a future rule change is forced to
  bump a version rather than change results silently.
- **Revisit if:** we index `html_content`, add a corpus whose text really is
  link-dense, or find retrieval failures traceable to URL tokens.

## DEC-003 — Exclude `html_content` from the frozen corpus
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-01)
- **Status:** Active
- **Context:** The source carries both `contents` (plain text) and `html_content`
  (the same article as markup). The handover's field list mentions neither `title`
  nor `html_content`.
- **Decision:** Freeze `id`, `url`, `title`, `contents`, `article_type`. Drop
  `html_content`. `title` is kept because it is a natural retrieval field.
- **Evidence:** No measured data; judgment call. `html_content` roughly doubles the
  artifact and no Phase 0 component reads it.
- **Consequences:** Any experiment on HTML structure requires a re-freeze, a new
  `corpus_hash`, and a new comparison family.
- **Revisit if:** we want to test structure-aware chunking that needs the markup.

## DEC-004 — `corpus_hash` covers source fields only
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-01/P0-02)
- **Status:** Active
- **Context:** `indexed_text` is stored in the same artifact but is a function of
  the normalization rule, not of the corpus.
- **Decision:** Hash the canonical serialization of the source fields, sorted by
  `id`. Derived columns are excluded. Changing normalization bumps
  `normalization_version` and leaves `corpus_hash` untouched.
- **Evidence:** No measured data; judgment call on provenance design.
- **Consequences:** Two provenance keys must be compared before any run comparison,
  not one. Both are recorded on every run.
- **Revisit if:** it proves error-prone to check two keys instead of one.

## DEC-005 — Chunk width is measured in whitespace tokens
> **CORRECTED by DEC-029 on 2026-09-10** — the decision stands; its token estimate
> was wrong. 512 whitespace words is ~650 BPE tokens, not 380-400.
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-05)
- **Status:** Active
- **Context:** P0-13's baseline is "fixed 512-token chunks". "Token" is ambiguous.
- **Options considered:**
  1. Model tokenizer tokens — rejected for Phase 0: it couples the index to the
     embedding model, so swapping models silently reshapes every chunk.
  2. Whitespace tokens — chosen. Model-independent and trivially reproducible.
- **Decision:** `FixedTokenChunker(chunk_size=512)` means 512 whitespace tokens,
  roughly 380-400 BPE tokens. The unit is named in the chunker's params and its
  `chunker_id`.
- **Evidence:** No measured data; judgment call.
- **Consequences:** Chunk sizes are not directly comparable to papers quoting BPE
  token counts. Context-window budgeting must convert.
- **Revisit if:** we hit context-window overflows, or a chunking experiment needs
  exact model-token control.

## DEC-006 — Split assignment: stratified deal, seed 1729
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-03)
- **Status:** Active
- **Context:** P0-03 requires exactly 100 + 100 in test, determinism, and
  stratification by `len(article_ids)`. Slicing a shuffled stratified list gives
  even strata but not an exact 100/100 total.
- **Decision:** Sort by `question_id`; group into strata by `n_gold_docs` ascending;
  seeded shuffle within each stratum (`seed=1729`, per-source key); deal alternately
  into test and dev. Recorded in `data/frozen/splits.meta.json`.
- **Evidence:** Measured — test/dev are exactly 100+100 per source, with
  `n_gold_docs` counts 161/35/4 (test) and 160/35/5 (dev) against a population of
  {1: 321, 2: 70, 3: 9}. All 400 gold document ids resolve in the frozen corpus.
- **Consequences:** Split membership is fixed for the life of this corpus pin.
- **Revisit if:** the corpus pin changes, or a slice proves too small to separate.

## DEC-007 — The unanswerable set is built by adding questions, never by deleting articles
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-04)
- **Status:** Active
- **Context:** WixQA has no refusal cases. The obvious shortcut — delete the gold
  article and reuse its question — changes `corpus_hash` and destroys comparability
  with every other run.
- **Decision:** 45 authored questions in `data/authored/unanswerable_seed.yaml`,
  version-controlled, `gold_doc_ids = []`, three balanced buckets (15/15/15). The
  index is never modified. `post-snapshot` questions are phrased by *date*
  ("released in 2025") rather than by naming a specific later feature, so each one
  is unanswerable from a 2024-12-02 snapshot without our asserting anything about
  what Wix actually shipped.
- **Evidence:** No measured data; judgment call on construction validity.
- **Consequences:** Refusal metrics measure "not in this snapshot", which is the
  behaviour we want, but the set is small (45) so refusal rates carry wide error
  bars.
- **Revisit if:** a bucket turns out to be trivially detectable by keyword (e.g. the
  model refuses on the word "Shopify" alone), which would make the score
  uninformative.
- **OPEN:** `meta.verified_by` is `null`. These are LLM-drafted and **not yet
  human-verified**. P0-04 requires human verification of each question. Until that
  is done the build emits a warning and any refusal number is provisional.

## DEC-008 — `doc_pooling: max` is the default and is recorded on every run
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-05)
- **Status:** Active
- **Context:** Ground truth is document-level; retrieval is chunk-level. The
  pooling rule changes the document ranking by itself, with no change to retrieval.
- **Decision:** Default `max` (best chunk wins), as specified. `sum` is also
  implemented. The rule is a config field, is carried on every `RetrievalResult`,
  and must be recorded on every run row.
- **Evidence:** Measured in `tests/test_pooling.py` — on one synthetic ranking,
  `max` and `sum` produce different top-ranked documents from identical chunk
  scores. Under `max`, a document whose best chunk ranks 3rd can never reach rank 1.
- **Consequences:** Comparing two runs with different `doc_pooling` is invalid, the
  same way as comparing across corpus hashes.
- **Revisit if:** a pooling sweep shows a rule that measurably beats `max` on strict
  recall.

## DEC-009 — Questions with no gold document are excluded from qrels
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-05)
- **Status:** Active
- **Context:** The unanswerable split has `gold_doc_ids = []`. Recall and nDCG are
  undefined for an empty relevant set, and IR libraries would average zeros into
  the retrieval metrics.
- **Decision:** `qrels_from_split` omits empty-gold questions. Refusal behaviour on
  those questions is scored separately in P0-07.
- **Evidence:** No measured data; definitional.
- **Consequences:** The unanswerable split never contributes to retrieval metrics.
  Any retrieval number quoted "over all splits" excludes it by construction.
- **Revisit if:** we define a retrieval-side refusal metric (e.g. score-threshold
  abstention) that needs those questions in the run.

---

## Promotion log

P2-05: `configs/promoted.yaml` advances only through `rag promote`, which re-runs the
comparison under the P2-04 split policy and appends a row here — date, axis, the
config hashes, the run ids compared, and the p-value or MDD verdict. Rows are written
by code; the reasoning behind each promotion gets its own DEC entry.

| # | Date | Axis | From → to | Metric | Verdict (runs compared) | Reason |
|---|---|---|---|---|---|---|
| 1 | 2026-09-16 | assembly | `7c99bc8e9a88e878` → `028da7f664767700` (cand.yaml) | strict_recall@5 | confirm (dev): a_dev → b_dev, Δ+0.1000, p=0.1226; decide (dev_large): a_dev_large → b_dev_large, Δ+0.2000, p=0.0001 | test win (git `abc1234`) |
| 1 | 2026-09-16 | assembly | `7c99bc8e9a88e878` → `028da7f664767700` (cand.yaml) | strict_recall@5 | confirm (dev): a_dev → b_dev, Δ+0.1000, p=0.1226; decide (dev_large): a_dev_large → b_dev_large, Δ+0.2000, p=0.0001 | test win (git `abc1234`) |

## Cost approvals log

P2-06: a run estimated above $2 halts before it starts. When approved and re-run with
`--approve-cost`, the runner appends the estimate, what drove it, and the approval
reference here. An entry without a matching DEC entry is a process failure.

| # | Date | Config hash | Estimate (driver) | Approval | Run |
|---|---|---|---|---|---|
| 1 | 2026-09-16 | `dddcb9951da9357b` | $3.0000 (index_build) | DEC-TEST | run `run_20260916_051725_8767`, git `7c59851` |
| 1 | 2026-09-16 | `dddcb9951da9357b` | $3.0000 (index_build) | DEC-TEST | run `run_20260916_051736_2dbd`, git `7c59851` |

## Test-split openings log

P0-12 requires a row here for every opening of `test`, with date, config hash, git
SHA, and reason.

| # | Date | Config hash | Git SHA | Reason |
|---|---|---|---|---|
| _(none)_ | — | — | — | The test split has never been opened. |

## DEC-010 — Strict recall@k is the headline retrieval metric
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-06)
- **Status:** Active
- **Context:** `ranx`'s `recall@k` is the mean per-question *fraction* of gold
  documents found. P0-06 asks for "all gold docs in top-k" (strict) and "any gold
  doc in top-k" (loose), neither of which is that.
- **Decision:** `strict_recall@k` = fraction of questions whose per-question recall
  reached 1.0, computed from `ranx`'s per-query output. `loose_recall@k` =
  `ranx`'s `hit_rate@k`. `ranx`'s own `recall@k` is used only as the input to
  strict recall and is never reported under the name "recall".
- **Evidence:** Measured — 79 of the 400 human-grounded questions need 2-3 gold
  documents, so the definitions separate on a fifth of the set.
- **Consequences:** `strict_recall@1` is structurally capped: two gold documents
  cannot both sit in a top-1 list, so ~20% of questions can never score there.
  Read `strict_recall@1` against that ceiling, not against 1.0.
- **Revisit if:** we adopt graded relevance, which would make the binary threshold
  meaningless.

## DEC-011 — MRR is reported only over the single-gold-document subset
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-06)
- **Status:** Active
- **Decision:** `mrr_single_gold` plus `mrr_single_gold_n`. `refuse_full_set_mrr`
  raises if asked for MRR over a set containing multi-gold questions.
- **Evidence:** No measured data; definitional. Reciprocal rank asks where *the*
  answer is; averaged over a mixed population the value tracks the multi-doc
  proportion of the split rather than the retriever.
- **Consequences:** MRR is computed over 160 of 200 `dev` questions. The subset size
  travels with the number so it cannot be quoted as if it covered the split.
- **Revisit if:** a multi-document rank-aware metric is needed; that is a new metric,
  not a redefinition of this one.

## DEC-012 — Retrieval depth is separate from context size
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-09/P0-10)
- **Status:** Active
- **Context:** P0-06 reports k up to 20; P0-13's baseline retrieves top-5. A first
  implementation used `top_k` for both, and `strict_recall@20` came back exactly
  equal to `strict_recall@5` — recall@5 wearing a different label.
- **Decision:** `retrieval_depth` (default 100) is how many chunks are ranked for
  scoring; `top_k` is how many chunks reach the generator's context. The config
  refuses `retrieval_depth < top_k`. Each run records `max_docs_returned` and any
  `k_values_capped_by_depth`.
- **Evidence:** Measured on a harness smoke run — with depth tied to `top_k=5`,
  strict recall was flat at 0.165 for k=5, 10 and 20; with depth 100 it rose
  0.16 -> 0.225 -> 0.335.
- **Consequences:** Every run ranks 100 documents deep even when only 5 are shown,
  which costs retrieval time but no LLM budget.
- **Revisit if:** deep ranking becomes a measurable share of Tier 1 runtime.

## DEC-013 — Metrics score the ranking we return, not raw pooled scores
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-06/P0-10)
- **Status:** Active
- **Context:** See MIS-003. Pooled document scores tie constantly; our pooling rule
  breaks ties on the best chunk's rank, and an IR library re-breaks them its own way.
- **Decision:** `run_from_results` emits strictly decreasing rank-derived scores
  (`1/(rank+1)`) by default, so the library scores exactly the ordering the system
  returns and the ordering recorded in `run_questions`. Raw scores remain available
  via `rank_scores=False` for inspection.
- **Evidence:** Measured — before the fix, a `dev` smoke run had questions whose gold
  document sat at stored rank 4 while scoring 0 on `strict_recall@5`; after, 0 of 200
  questions disagree, and the aggregate moved (0.160 -> 0.165).
- **Consequences:** The `scores` column in `run_questions` (raw chunk scores) is
  diagnostic only; it is not what produced the metrics.
- **Revisit if:** we adopt a metric that is sensitive to score magnitude rather than
  to rank alone.

## DEC-014 — Refusal detection is lexical in Phase 0
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-07)
- **Status:** Active
- **Options considered:**
  1. Ask the judge whether the answer is a refusal — rejected for now: it adds an
     LLM call per question to a metric that should be free and auditable.
  2. A versioned pattern list (`refusal-lexical-v1`) — chosen.
- **Decision:** Lexical detection, version recorded on every run alongside the rates.
  Refusal on an unanswerable question and refusal on an answerable one are reported
  as two separate metrics, never one "refusal rate".
- **Evidence:** No measured data; the detector's agreement with human judgment is
  untested. Tracked as OQ-008.
- **Revisit if:** OQ-008 shows the detector disagrees with human reading, or a model
  refuses in phrasings the patterns miss.

## DEC-015 — Step coverage is reported over the procedural subset only
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-07)
- **Status:** Active
- **Context:** P0-07 frames WixQA answers as procedural markdown.
- **Decision:** Steps are numbered-list items only. Coverage is `None` when the
  reference has fewer than 2 steps, and the slice report carries
  `step_coverage__n` so every reported value shows what it was computed over.
  Matching is Jaccard overlap of content words at threshold 0.5.
- **Evidence:** Measured — 54 of 200 `dev` reference answers contain a numbered
  list; 146 are prose. See MIS-002.
- **Consequences:** Step coverage on `dev` is a ~27% subset metric, roughly 54
  questions, which is small enough that a few questions move it visibly.
- **Revisit if:** the subset proves too small to separate configurations, or OQ-007
  shows lexical matching disagrees with human reading of "same step".

## DEC-016 — Harness smoke-test runs are marked and never comparable
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-10)
- **Status:** Active
- **Context:** Demonstrating `run(config) -> row` and `rag diff` needs runs, but
  P0-13's BM25 baseline must be the first recorded experiment.
- **Decision:** A `toy_overlap` retriever ranks by raw word overlap and exists only
  to exercise the harness. Configs using it must set `harness_smoke_test: true`,
  which marks the run row, shows as `[SMOKE TEST]` in `rag runs list`, and makes
  `rag diff` report any comparison involving it as NOT COMPARABLE.
- **Evidence:** No measured data; judgment call to keep the ledger clean.
- **Consequences:** Two smoke runs exist in the local results store. They are not
  experiments and must never appear in `docs/EXPERIMENTS.md`.
- **Revisit if:** a real retriever makes the toy redundant for testing.

## DEC-017 — Generator: `openai/gpt-5-nano`
- **Date:** 2026-09-09
- **Decided by:** Krutik (options and recommendation from Claude)
- **Status:** Active
- **Context:** Tier 2 needs a model to write answers from retrieved chunks. Phases
  1-3 vary *retrieval*, so the generator is held constant across every config.
- **Options considered:**
  1. `openai/gpt-5-nano` ($0.05/$0.40 per Mtok, ~$0.06 per Tier 2 dev run) — chosen.
  2. `google/gemini-2.5-flash-lite` ($0.10/$0.40) — rejected, no advantage once the
     judge is not an OpenAI model being graded by its own family.
  3. `meta-llama/llama-3.3-70b-instruct` ($0.10/$0.32) — rejected for now; open
     weights are attractive for reproducibility and this stays the fallback.
  4. `anthropic/claude-sonnet-5` ($2/$10, ~$2.20 per run) — rejected. ~35x the cost
     to raise the floor on every config equally, and a strong generator can paper
     over bad retrieval by writing a plausible answer from thin context, which makes
     retrieval failures *harder* to see.
- **Decision:** `openai/gpt-5-nano`, temperature 0, via OpenRouter.
- **Evidence:** No measured data on this corpus; cost figures are OpenRouter list
  prices read on 2026-09-09, and the per-run estimate is an engineering estimate
  (~4k tokens in, ~300 out per question, 200 questions), not a measurement.
- **Consequences:** Absolute generation numbers will be modest and are not the point;
  they are a constant backdrop for retrieval comparisons. Known risk: the cheapest
  models may ignore the `[doc:<id>]` citation format or the refusal instruction,
  which would tank citation and refusal metrics for reasons unrelated to retrieval.
  The P0-13 Tier 2 smoke run is where that gets checked, before any real Tier 2 work.
- **Revisit if:** the smoke run shows it does not follow the citation or refusal
  instructions, or generation quality becomes the object of study rather than the
  backdrop.

## DEC-018 — The real judge is deferred; `gpt-5-nano` is a smoke-test placeholder
- **Date:** 2026-09-09
- **Decided by:** Krutik (raised the question; options from Claude)
- **Status:** **Superseded by DEC-025** — the placeholder model is invalid under
  P0-07's different-family rule. The *deferral* still stands; only the model changes.
- **Context:** Krutik asked why a judge is needed when WixQA ships gold answers.
  Working through it: the benchmark fully answers "did we retrieve the right
  documents" (gold `article_ids`) and pays for citation precision/recall and step
  coverage for free. It cannot answer **faithfulness** — whether each claim is
  supported by the chunks *this run* retrieved — because that depends on the
  retriever's output and no static benchmark can label it. Answer correctness is the
  contestable one: the gold answer exists, but lexical and embedding similarity are
  weak on long procedural text.
- **Options considered:**
  1. Cheap placeholder now, real judge chosen when answer-quality claims are actually
     being made — chosen.
  2. `anthropic/claude-sonnet-5` now (~$3.30 per Tier 2 dev run) — rejected as
     premature: the judge would be paid for before any claim depends on it.
  3. Drop judge metrics from Phase 0 entirely — rejected; it would leave P0-13's
     "Tier 2 exercised end to end" criterion unmet and the plumbing unproven.
  4. Non-LLM answer correctness (embedding/lexical similarity) — not rejected,
     recorded as OQ-010. It would need an embedding model choice and its agreement
     with human judgment would itself need measuring.
- **Decision:** `judge_model: openai/gpt-5-nano` **solely to prove the Tier 2
  plumbing** — that prompts render, responses parse, and scores land in the store.
  **Its scores are not measurements and must never be written into
  `docs/EXPERIMENTS.md` or quoted in `NARRATIVE.md`.** The real judge is chosen
  before the first Tier 2 run whose generation numbers are meant to be believed.
- **Evidence:** No measured data; judgment call on sequencing. Retrieval is what the
  next phases vary, and every retrieval metric is already free.
- **Consequences:** Faithfulness, answer relevance and answer correctness have no
  trustworthy values until the real judge is chosen. Citation precision stands in as
  the cheap grounding signal in the meantime — an answer citing documents that are
  not gold is a strong hallucination signal, and it costs nothing.
- **Revisit if:** a Tier 2 run's generation numbers are about to enter the narrative,
  or before any experiment whose decision rule names a judge metric. At that point
  the judge choice needs its own DEC entry, and it should be cross-family from
  `gpt-5-nano` to avoid self-preference bias.

## DEC-019 — Ragas is the judged-metric library, and nothing more
- **Date:** 2026-09-09
- **Decided by:** Krutik (P0-07 updated to specify it)
- **Status:** Active
- **Context:** Phase 0's handover originally named only `ranx`/`pytrec_eval` while
  describing P0-07's three criteria in Ragas's vocabulary. The eval layer was
  written custom by default rather than by decision — the gap this file exists to
  prevent. P0-07 was then updated to specify Ragas explicitly.
- **Decision:** Faithfulness, answer relevance and answer correctness come from
  Ragas. Everything else does not: retrieval metrics stay with `ranx`, and citation
  precision/recall, step coverage and refusal detection stay rule-based and free.
  Ragas is called **behind the `Judge` interface** in `rag/eval/judge.py`, which is
  the only module permitted to import it — `tests/test_eval_boundary.py` enforces
  that by scanning for import statements.
- **Ragas's dataset and experiment abstractions are explicitly not adopted.** It has
  drifted from a RAG-eval library toward a general LLM-app eval product with its own
  dataset management and experiment tracking. Adopting those would fork the Phase 0
  results store and break `rag diff`. We call metrics, take scores, write our own rows.
- **Evidence:** No measured data; framework selection. The boundary is enforced by a
  test rather than by intent.
- **Consequences:** A Ragas major-version change, or a swap to another judge library,
  is a one-file change. Judge prompts are no longer ours: `prompts/judge_*.yaml` were
  deleted, and only the generator prompt remains under our version control.
- **Revisit if:** Ragas's metric definitions drift from what we need, or its release
  cadence makes pinning impractical.

## DEC-020 — Ragas `context_precision` / `context_recall` are not used
- **Date:** 2026-09-09
- **Decided by:** Krutik (P0-07/P0-06 updated to specify it)
- **Status:** Active
- **Context:** Ragas ships LLM-judged retrieval metrics built for projects with no
  retrieval ground truth.
- **Decision:** Not used. WixQA ships `article_ids`, so we have real document-level
  qrels; estimating labelled recall with a judge would be slower, costlier,
  non-deterministic and less defensible. Retrieval evaluation belongs to `ranx`;
  Ragas owns P0-07 only.
- **Evidence:** Measured — all 400 gold document ids in `dev` and `test` resolve
  against the frozen corpus, so ground truth is complete and needs no estimation.
- **Consequences:** Retrieval metrics stay free and deterministic. Tier 1 remains
  zero-LLM-call, which is what makes parameter sweeps affordable.
- **Revisit if:** a benchmark without document-level ground truth is added, where
  judged context metrics would be the only option.

## DEC-021 — Ragas is pinned exactly, and its metric code is fingerprinted
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-07)
- **Status:** Active
- **Context:** P0-07 requires an exact pin and `ragas_version` on every run row.
  Ragas manages metric prompts internally and revises them between releases.
- **Decision:** `ragas==0.4.3`, exact. Every run records `ragas_version` and
  `metric_prompt_versions`. Ragas's collections API exposes no prompt objects, so
  the fingerprint is a SHA-256 over each metric package's source — it changes when
  Ragas changes the metric, which is the thing that would silently move scores.
  Both fields are part of `rag diff`'s comparability check.
- **Evidence:** Measured during implementation — see MIS-004. `ragas.metrics` is
  already deprecated in favour of `ragas.metrics.collections` "removed in v1.0", so
  the API is actively moving.
- **Consequences:** A Ragas upgrade is a deliberate act that starts a new comparison
  family for judged metrics, and `rag diff` will say so.
- **Revisit if:** Ragas stabilises and publishes prompt versions we can record directly.

## DEC-022 — `answer_relevance` is unavailable until an embedding model is chosen
> **CORRECTED by DEC-026 on 2026-09-10** — the premise below is factually wrong.
> OpenRouter *does* serve embedding models, through a separate endpoint I did not
> check. The entry stays as written; see DEC-026 and MIS-005.
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-07); the model choice itself is Krutik's
- **Status:** Active — **blocking one of P0-07's three judged metrics**
- **Context:** Ragas's `AnswerRelevancy` requires an embeddings model (it embeds
  generated questions to compare against the original). Our only configured LLM
  access path is OpenRouter, which **serves no embedding models** — checked against
  its `/models` endpoint on 2026-09-09: zero models expose an embeddings endpoint.
- **Options considered:**
  1. Ship faithfulness and answer correctness now, skip relevance and record it —
     chosen.
  2. Add a second provider for embeddings — deferred; needs another key and a model
     decision that is Krutik's.
  3. Local embeddings via `sentence-transformers` — deferred; free and deterministic,
     but a heavy dependency and still a model choice.
- **Decision:** `JudgeConfig.criteria` omits `answer_relevance` when no embedding
  model is configured, and `skipped_criteria` is recorded on the run so its absence
  is visible rather than assumed.
- **Evidence:** Measured — `AnswerRelevancy.__init__` requires `embeddings`;
  OpenRouter's model list contains no embedding models.
- **Consequences:** P0-07 ships two of three judged metrics. Answer relevance is the
  weakest of the three and largely overlaps answer correctness, so the loss is small,
  but it is a gap and is recorded as one. Tracked as OQ-011.
- **Revisit if:** an embedding model is chosen — which Phase 1 needs anyway for dense
  retrieval, so this likely resolves itself there.

## DEC-023 — Answer correctness is scored on factuality alone
- **Date:** 2026-09-09
- **Decided by:** Claude (implementing P0-07)
- **Status:** Active
- **Context:** P0-07 notes Ragas's `AnswerCorrectness` "blends factual and
  semantic-similarity components and is noisy on long procedural answers; record the
  weighting used." Its default is `[0.75 factual, 0.25 similarity]`.
- **Decision:** `weights = [1.0, 0.0]` — factuality only. This removes the component
  the story flags as noisy on exactly the answer shape this corpus has, and it also
  removes the embeddings dependency from this metric (Ragas requires embeddings only
  when the similarity weight is above zero). Recorded on every run as
  `answer_correctness_weights`.
- **Evidence:** No measured data on this corpus; follows P0-07's own warning.
- **Consequences:** Our answer-correctness numbers are not comparable to any
  published Ragas number using default weights. Anyone quoting one against ours must
  say so.
- **Revisit if:** an embedding model arrives and a weighting sweep shows the
  similarity component adds signal rather than variance.

## DEC-024 — Tier 2 scores a fixed 100-question subsample by default
> **AMENDED by DEC-031 on 2026-09-10** — the decision stands, but its premise was
> incomplete. Cost is not the binding constraint on Tier 2; wall-clock latency is.
- **Date:** 2026-09-09
- **Decided by:** Krutik (P0-09 updated to specify it)
- **Status:** Active
- **Context:** Ragas faithfulness decomposes an answer into claims and verifies each,
  so one question is several LLM calls per metric. Across dozens of experiments on
  200 dev questions that compounds.
- **Decision:** Tier 2 defaults to a fixed subsample of 100, seed 7, recorded as
  `eval_subsample_id` on every run and included in `rag diff`'s comparability check.
  *Fixed* is the point: the same questions every run, so two Tier 2 runs differ by
  configuration and not by which questions they happened to score. `full_eval: true`
  takes the whole split. Tier 1 is free and always scores everything.
- **Evidence:** Cost is an engineering estimate, printed before every Tier 2 run —
  roughly $3 per 100-question run with a mid-tier judge, dominated by the judge.
- **Consequences:** Tier 2 metrics carry the error bars of 100 questions, not 200.
  Sliced further — step coverage applies to about 27% of answers — some Tier 2 slices
  will be too small to separate configurations, and must be reported with their `n`.
- **Revisit if:** a Tier 2 slice is consistently too small to support a finding.

## DEC-025 — The placeholder judge must leave the generator's family
> **SUPERSEDED by DEC-030 on 2026-09-10** — the judge model changes from
> `deepseek/deepseek-v3.2` to `openai/gpt-oss-120b`. The different-family requirement
> and the placeholder status both still stand.
- **Date:** 2026-09-09
- **Decided by:** Krutik (options and recommendation from Claude)
- **Status:** Active — **resolved: `deepseek/deepseek-v3.2`**
- **Context:** DEC-018 chose `openai/gpt-5-nano` as a plumbing placeholder judge while
  DEC-017 chose the same model as the generator. P0-07 was then updated to require
  that the judge be from a different model family than the generator, to avoid
  same-family self-preference bias. `RunConfig` now refuses that pairing outright
  rather than warning, so the placeholder as recorded cannot run.
- **Decision:** DEC-018's *deferral* stands — the judge is still a plumbing
  placeholder and its scores are still not measurements. What must change is the
  model: it has to come from a non-OpenAI family, and it must be an **exact pinned
  id**, not a floating alias like `anthropic/claude-haiku-latest` (CLAUDE.md section
  10 forbids aliases; a provider updating the model behind one invalidates every
  comparison across that boundary with nothing in the artifacts showing it).
- **Evidence:** Measured — `RunConfig.__post_init__` raises on same-family pairings;
  `tests/test_runner.py::test_judge_must_not_share_the_generators_family` covers it.
- **Chosen:** `deepseek/deepseek-v3.2` ($0.27/$0.40 per Mtok, roughly $0.36 per
  100-question Tier 2 run). Non-OpenAI family, exact pinned id, and stronger at
  reasoning than the flash tier — Ragas drives its metrics through `instructor`, so
  the judge has to return parseable structured output reliably, and the cheapest
  small models are the ones that fail at that.
- **Options considered:**
  1. `deepseek/deepseek-v3.2` (~$0.36/run) — chosen. Middle ground: cheap enough to
     stay a placeholder, capable enough that its scores are roughly indicative.
  2. `google/gemini-2.5-flash-lite` (~$0.15/run) — rejected; marginally cheaper, less
     reasoning headroom.
  3. `qwen/qwen3.5-flash-02-23` (~$0.10/run) — rejected; highest structured-output risk.
  4. `anthropic/claude-sonnet-5` (~$3.12/run) — rejected for now; ending the deferral
     costs ~9x per run before we know which judged metrics we actually rely on.
- **Status of its scores:** DEC-018's deferral **still stands**. This is a plumbing
  judge. Faithfulness and answer correctness from it are not measurements and must not
  enter `docs/EXPERIMENTS.md` or `NARRATIVE.md`. The real judge decision comes before
  the first Tier 2 run whose generation numbers are meant to be believed.
- **Consequences:** Tier 2 can now be constructed and P0-13's end-to-end criterion is
  unblocked. Judge cost is roughly $0.36 per 100-question run — the estimate is
  printed before every Tier 2 run and OQ-012 will replace it with observed usage.
- **Revisit if:** DeepSeek fails Ragas's structured-output requirement (surfaces as
  parse errors, not wrong scores), or judged numbers are about to enter the narrative.

## DEC-026 — Corrects DEC-022: OpenRouter does serve embedding models
- **Date:** 2026-09-10
- **Decided by:** Krutik (corrected the claim); verification by Claude
- **Status:** Active — **corrects DEC-022**
- **Context:** DEC-022 recorded that "OpenRouter serves no embedding models" and
  concluded that Ragas's `answer_relevance` could not run. That conclusion rested on
  a single check of `GET /api/v1/models`, which does not list embedding models.
- **What is actually true:** OpenRouter exposes a unified embeddings API at
  `POST /api/v1/embeddings`, and its embedding models are listed at
  `GET /api/v1/embeddings/models` — a **different endpoint**. Verified 2026-09-10:
  33 embedding models are available through the same key, including
  `openai/text-embedding-3-small`, `openai/text-embedding-3-large`,
  `qwen/qwen3-embedding-8b`, `google/gemini-embedding-001` and `baai/bge-m3`.
- **Decision:** `answer_relevance` is available. It is gated on *configuration*, not
  capability: set `judge_embedding_model` and the criterion runs.
  `RagasJudge._embeddings()` now returns `ragas.embeddings.OpenAIEmbeddings` backed by
  an OpenAI-compatible client pointed at OpenRouter — Ragas accepts any such client,
  so no custom wrapper is needed.
- **Evidence:** Measured — `GET /api/v1/embeddings/models` returns 33 models with
  pricing from $0.004/Mtok. See MIS-005 for how the wrong conclusion was reached.
- **Consequences:** All three of P0-07's judged metrics are reachable. The embedding
  model itself is still unchosen, and that is Krutik's call (OQ-011). Until it is set,
  `skipped_criteria` records `answer_relevance` as skipped — which was always the
  right mechanism; only the stated reason was wrong.
- **Revisit if:** OpenRouter changes its embeddings API surface, or a chosen embedding
  model needs a provider OpenRouter does not proxy.

## DEC-027 — Embedding model: `qwen/qwen3-embedding-8b`
- **Date:** 2026-09-10
- **Decided by:** Krutik (measurements and options from Claude)
- **Status:** Active
- **Context:** Needed for Ragas `answer_relevance` (DEC-026) and for Phase 1 dense
  retrieval. The corpus was measured first so the choice rested on data rather than
  on defaults.
- **Measured corpus size:** 6,221 articles = 14.1M chars / 2.34M words /
  **2.96M tokens** (`cl100k_base`, so ±10% for any other tokenizer). Mean 476 tokens
  per article, median 256, max 10,624. At `chunk_size=512` words: **8,694 chunks,
  2.86M tokens**, mean 329, median 284, p95 644, max 1,326.
- **What decided it:**
  1. **Cost is irrelevant at this scale.** Embedding the whole index costs $0.03 at
     $0.01/Mtok and $0.37 at the most expensive option considered. Re-indexing for a
     chunking sweep is pennies, so quality and context length decide, not price.
  2. **Context length is not irrelevant.** 2,983 of 8,694 chunks (34%) exceed 512
     tokens. Every $0.005/Mtok option caps at 512 and would silently truncate a third
     of the index — a retrieval confound baked into the index and invisible in the
     metrics.
- **Options considered:**
  1. `qwen/qwen3-embedding-8b` — $0.010/Mtok, **32,768 context** — chosen. Clears our
     1,326-token maximum with 25x headroom.
  2. `baai/bge-m3` — $0.010/Mtok, 8,194 context — same price, adequate headroom.
  3. `openai/text-embedding-3-small` — $0.020/Mtok, 8,192 context.
  4. `sentence-transformers/all-minilm-l12-v2` — $0.005/Mtok but **512 context**;
     rejected on the truncation finding above.
- **Evidence:** Measured — corpus and chunk token counts above; OpenRouter list prices
  and context lengths read 2026-09-10.
- **Consequences:** Chunk-width experiments up to ~30,000 tokens need no embedding
  model change, so chunking and embedding stay independent axes. Used for
  `answer_relevance` today; Phase 1 dense retrieval will reuse it unless a decision
  says otherwise.
- **Revisit if:** dense retrieval quality becomes the object of study, or a chunking
  experiment exceeds the context window.

## DEC-028 — Generator and judge token budgets, and generator reasoning effort
- **Date:** 2026-09-10
- **Decided by:** Claude (implementing the Tier 2 smoke run; Krutik not in the loop)
- **Status:** Active
- **Context:** The first Tier 2 smoke run failed three times on token budgets, not on
  logic. See MIS-006 for the sequence.
- **Decision:**
  - `generator_max_tokens: 2000` (was 800).
  - `generator_reasoning_effort: "minimal"`.
  - `judge_max_tokens: 4096`.
  Each is a `RunConfig` field, so each is part of `config_hash`.
- **Evidence:** Measured on `openai/gpt-5-nano` with an 812-word prompt.
  `max_tokens=800`: `finish_reason=length`, **content `None`**, all 768 completion
  tokens spent on reasoning. `max_tokens=3000`: worked, but 1,984 of 2,275 completion
  tokens (87%) were reasoning. With `reasoning.effort="low"`: 256 reasoning tokens.
  With `"minimal"`: **0 reasoning tokens** and a complete 1,257-character answer. The
  judge needed 4096 because Ragas asks for structured output through `instructor`,
  which raises `IncompleteOutputException` at `finish_reason=length`, and faithfulness
  emits one statement per claim — the budget has to hold a whole decomposed answer.
- **Consequences:** `"minimal"` means the generator does no reasoning. That is
  consistent with DEC-017's rationale — it is a deliberately cheap constant backdrop
  for retrieval comparisons — but it *is* a quality choice made without Krutik, and
  `"low"` remains available at ~256 extra tokens per question. Measured per-question
  generator usage on the smoke run: ~3,420 tokens in, 118-183 out.
- **Revisit if:** generation quality becomes the object of study, or a stronger
  generator is chosen for whom reasoning changes the answers materially.

## DEC-029 — Corrects DEC-005: 512 whitespace words is ~650 tokens, not 380-400
- **Date:** 2026-09-10
- **Decided by:** Claude (correcting my own estimate)
- **Status:** Active — **corrects DEC-005**
- **Context:** DEC-005 chose whitespace words as the chunk unit and estimated that
  512 of them is "roughly 380-400 BPE tokens". That estimate was never measured.
- **What is actually true:** The measured ratio on this corpus is **1.27 tokens per
  whitespace word**, so a full 512-word chunk is about **650 tokens** — I understated
  it by roughly 60%. Measured chunk distribution: mean 329 tokens, median 284, p95
  644, max 1,326 (chunks are usually short because most articles are).
- **Decision:** The unit stays whitespace words (DEC-005's reasoning is unaffected).
  Only the conversion figure is corrected. Use **1.27 tokens/word** for context-window
  budgeting.
- **Evidence:** Measured with `tiktoken` `cl100k_base` over all 6,221 frozen articles
  and all 8,694 chunks.
- **Consequences:** Any context-budget arithmetic done with the old figure understates
  by ~60%. This directly mattered for DEC-027: at 1.27 tokens/word, a third of chunks
  exceed a 512-token embedding context.
- **Revisit if:** the tokenizer of a chosen model differs materially from
  `cl100k_base`.

## DEC-030 — Ragas judge LLM: `openai/gpt-oss-120b`
> **CORRECTED by DEC-034 on 2026-09-10** — the model choice stands; the price below
> is wrong for the config actually shipped. $0.037/$0.170 is DeepInfra's rate. With
> providers pinned to Cerebras/Groq (DEC-032) the real rate is up to $0.350/$0.750.
- **Date:** 2026-09-10
- **Decided by:** Krutik
- **Status:** Active — **supersedes DEC-025's model choice**
- **Decision:** The LLM that drives every Ragas metric is `openai/gpt-oss-120b`, via
  OpenRouter. $0.037/$0.170 per Mtok, 131,072 context — roughly 7x cheaper on input
  than the `deepseek/deepseek-v3.2` it replaces ($0.27/$0.40).
- **Placeholder status is unchanged.** DEC-018's deferral still stands: this judge
  proves the Tier 2 plumbing. Its faithfulness, answer-correctness and
  answer-relevance scores are **not measurements** and must not enter
  `docs/EXPERIMENTS.md` or `NARRATIVE.md`.

### The family question — a judgment call, not a derivation

P0-07 requires the judge to be a different model family from the generator, to avoid
self-preference bias. The generator is `openai/gpt-5-nano` (DEC-017), and OpenRouter
namespaces this judge under `openai/` too, so a literal prefix reading makes them the
same family and `RunConfig` would refuse the pairing outright.

They are treated as **different** families here, and `model_family()` maps
`openai/gpt-oss-*` to `openai-oss`. The reasoning: `gpt-oss-120b` is an open-weights
model with its own training, served by third-party providers — it is not the hosted
GPT-5 line, and self-preference bias is a model preferring *its own* outputs, not a
vendor's. A shared namespace is a packaging fact, not a lineage one.

**The residual risk is real and unmeasured:** shared provenance may still correlate
what the two models consider a good answer, and nothing here rules that out. Two
things make it tolerable rather than resolved — the judge is a placeholder whose scores
are not being believed, and this bias, if present, applies equally to every retrieval
configuration, so it would shift absolute judged numbers rather than reorder configs.
It would still inflate any absolute figure quoted in the narrative.

- **Options considered:**
  1. Treat `gpt-oss-*` as a distinct family and use it — chosen.
  2. Change the generator to a non-OpenAI model so the prefix rule passes literally —
     rejected: it discards DEC-017 to satisfy a string comparison.
  3. Relax P0-07's different-family requirement — rejected: the rule is sound; the
     prefix heuristic implementing it is what was too crude.
- **Evidence:** Model availability, pricing and 131k context read from OpenRouter
  2026-09-10. The bias question has **no measured data on this corpus**; it is a
  judgment call, and OQ-014 records what would settle it.
- **Consequences:** Judged metrics get materially cheaper, which makes a full-`dev`
  Tier 2 run (200 questions) affordable rather than something to ration. The
  `openai-oss` family label is now load-bearing: anyone adding a model under
  `openai/gpt-oss-*` inherits this decision, and anyone who disagrees with it should
  change `_FAMILY_OVERRIDES` rather than work around the guard.
- **Revisit if:** OQ-014 shows measurable self-preference between the two, or a real
  (non-placeholder) judge is chosen — at which point the family question should be
  settled by measurement rather than by argument.

## DEC-031 — Tier 2's binding constraint is latency, not cost
> **AMENDED by DEC-032 on 2026-09-10** — the finding held, the diagnosis did not.
> The judge model was never slow; OpenRouter was routing to slow providers. The
> ~4-hour figure below is obsolete: a 100-question run is now ~20 minutes.
- **Date:** 2026-09-10
- **Decided by:** Claude (recording a measurement; the response to it is Krutik's call)
- **Status:** Active — **amends DEC-024's premise**
- **Context:** DEC-024 capped Tier 2 at a 100-question subsample because Ragas is
  expensive per question. The first full Tier 2 run with the real judge
  (`openai/gpt-oss-120b`, DEC-030) shows the money was never the problem.
- **Measured** — run `run_20260910_175820_b8b5`, 5 questions, 3 Ragas metrics,
  toy retrieval, judge `openai/gpt-oss-120b`:
  - **780s wall clock for 5 questions — 156s per question.**
  - Generator: **19s total, 2% of wall clock** (per-question 2.3-7.4s).
  - Judge and indexing: **760s, ~152s per question.**
  - A single isolated judge call (2 metrics, no embeddings) measured 45.9s.
- **Extrapolated, an estimate and not a measurement:** a 100-question Tier 2 run is
  on the order of **4 hours** if latency scales linearly. Cost over the same run is
  cents.
- **What this changes:** Tier 2 is something to schedule, not iterate on. The
  two-tier design still holds — Tier 1 runs `dev` in ~12s with zero LLM calls, which
  is where sweeps belong — but "promoted configs only" now means promoted for reasons
  of *time*, and a full-`dev` (200 question) Tier 2 run is an overnight job.
- **The largest and most obvious lever is our own implementation, not the model.**
  `RagasJudge.score` calls `asyncio.run` once per metric per question, strictly
  sequentially, so nothing overlaps: 100 questions x 3 metrics is 300 serialized
  round trips, each of which is mostly waiting. Concurrency across questions is the
  fix, and it is untried — tracked as OQ-015. No conclusion is recorded here about how
  much it would help, because none has been measured.
- **Evidence:** Measured as above. The 4-hour figure is an engineering estimate,
  labelled as such.
- **Consequences:** Any plan that assumed Tier 2 could be re-run casually needs
  revising. P0-13's Tier 2 smoke run should stay small until OQ-015 is settled.
- **Revisit if:** OQ-015 lands and changes the per-question figure, or a faster judge
  is chosen. Judge *latency* now belongs in the judge-selection tradeoff alongside
  price and bias — it was absent from DEC-025 and DEC-030 because it was unmeasured.

## DEC-032 — Pin judge providers and judge concurrently
> **AMENDED by DEC-034 on 2026-09-10** — the speed and reproducibility findings hold.
> What is missing below is that pinning these two providers also raised the price
> ~6x, and that tradeoff was never surfaced. See MIS-008.
- **Date:** 2026-09-10
- **Decided by:** Claude (investigating at Krutik's request); the provider list is a
  routing choice he can overrule
- **Status:** Active — **amends DEC-031's diagnosis**

### What was actually slow

DEC-031 measured 156s per question and blamed the judge model. That was wrong. The
model is fast: a direct call to `openai/gpt-oss-120b` returned 460 tokens in 1.6s
(280 tok/s), and 486 tok/s when routed for throughput.

Instrumenting every HTTP call during real Ragas metrics showed the cause. OpenRouter
serves one model from many providers, and **it routed to whichever, with a 37x spread
in speed** on comparable work:

| Provider | Call time |
|---|---|
| Groq | 0.9s |
| Google | 3.1s |
| DeepInfra | 12.3s |
| AkashML | 20.0s / 33.3s |
| CoreWeave | 24.5s / 29.4s |
| Together | 31.2s |

Ragas's call volume is a secondary factor and is inherent to the metrics: 8 chat
calls plus 2 embedding calls per question (faithfulness 2, answer correctness 3,
answer relevance 3 — it generates `strictness=3` candidate questions). Eight calls at
~20s each is the 156s. Eight calls at ~1s each is not a problem.

### Decision

1. **Pin providers.** Every judge call carries
   `provider: {order: ["Cerebras", "Groq"], allow_fallbacks: true}`.
   `judge_provider_order` is a `RunConfig` field, is recorded on every run, and is a
   `rag diff` comparability key.
2. **Judge concurrently.** `RagasJudge.score_batch` runs the whole batch in one event
   loop under a semaphore, `judge_concurrency: 20`. Judging one question never
   depends on another, so this is safe by construction.

### Measured

| Configuration | Per question |
|---|---|
| Default routing, serial judging (DEC-031 baseline) | 156s |
| Providers pinned, serial | 9.6s |
| Pinned, metrics concurrent within a question | 2.6s |
| Pinned, 4 questions fully concurrent (synthetic) | 1.1s |
| **Real 20-question run, pinned, concurrency 8** | **14.5s** |
| **Real 20-question run, pinned, concurrency 20** | **11.8s** |

End to end: **156s -> 11.8s per question, 13.3x.** A 100-question Tier 2 run goes from
~4 hours to **~20 minutes**, an estimate by linear extrapolation. On the real 20-question
run all 64 chat calls landed on Cerebras or Groq — no fallback leakage — mean 1.4s,
max 5.8s.

### Pinning is also a reproducibility control, and that matters more

Providers serving the same open weights do not return identical outputs — different
quantizations, kernels and sampling. Measured on one identical input, answer
correctness scored **1.00 under default routing and 0.857 pinned**. Two runs of the
same config on the same 20 questions gave faithfulness 0.7284 and 0.7236.

So provider identity is part of the judge, not a delivery detail. Recording it and
treating it as a comparability key is what stops a silent routing change from looking
like a quality change. This argument stands even if the speed difference vanished.

- **Evidence:** All measured, 2026-09-10, via HTTP-level instrumentation of real Ragas
  calls and two full 20-question Tier 2 runs. The ~20-minute figure is an estimate.
- **Consequences:** Tier 2 is now cheap enough in time to run on the full 200-question
  `dev` split (~40 min estimated), which reopens DEC-024's subsample question — it was
  decided when a full run looked like 8 hours. Not reopened here; flagged.
  Generation is now the largest serial component (3.1s per question, 21% of the run)
  and is the next lever (OQ-016). An additive store migration also landed, so a schema
  change no longer tempts anyone to delete the results store (MIS-007).
- **Revisit if:** Cerebras or Groq stop serving the model, throughput changes, or the
  judge model changes — the provider list is model-specific and does not transfer.

## DEC-033 — Tier 2 stays at 100 questions after the speedup
- **Date:** 2026-09-10
- **Decided by:** Krutik
- **Status:** Active — **reaffirms DEC-024**
- **Context:** DEC-024 capped Tier 2 at a fixed 100-question subsample because Ragas
  looked expensive per question. DEC-031 found the real constraint was latency, and
  DEC-032 removed most of it — 13.3x, so a full 200-question `dev` Tier 2 run is now
  roughly 40 minutes rather than 8 hours. That made the cap worth reconsidering, since
  the reason for it had changed.
- **Decision:** Keep the cap. `eval_subsample_size: 100`, seed 7, subsample
  `sub100:b551f7f49c91`, unchanged. `full_eval: true` remains available per run.
- **Evidence:** No measured data; judgment call. Affordability was never the only
  argument for a fixed subsample — a stable question set is what makes two Tier 2 runs
  differ by configuration rather than by which questions they scored, and that holds
  regardless of speed.
- **Consequences:** Judged metrics keep the error bars of 100 questions, and the
  slices stay small: 26 multi-gold, 32 procedural. Any judged finding on those slices
  rests on tens of questions, and `aggregate_by_slice` carries the `n` next to every
  number for that reason. Changing the size later starts a new `eval_subsample_id` and
  breaks comparability with every Tier 2 run before it — which is the cost this
  decision avoids paying twice.
- **Revisit if:** a judged slice proves too small to separate configurations once
  OQ-017 has measured the run-to-run spread, which is the number that would say
  whether 100 is enough.

## DEC-034 — Judge provider pricing, and the decision to keep the fast pair
> **CORRECTED by DEC-035 on 2026-09-11** — the decision stands; the "~$0.48 per
> 100-question run" figure was from a synthetic probe with a one-sentence context.
> Measured on a real run it is **$0.81**. The cheap-provider figure of ~$0.07 was
> similarly low; at real token volumes it is ~$0.13.
- **Date:** 2026-09-10
- **Decided by:** Krutik (raised the question; costing and options from Claude)
- **Status:** Active — **corrects DEC-030's price, amends DEC-032**
- **Context:** Krutik asked why Groq and Cerebras were appearing when he had not asked
  for them, and whether he was paying for them. Answering it surfaced a cost fact that
  DEC-032 had not checked: OpenRouter prices the *same model* differently per
  provider, across a 12x range.
- **The corrected figures** — `openai/gpt-oss-120b`, 22 providers, read 2026-09-10:

| Provider | $/Mtok in | $/Mtok out | Quantization | Observed latency |
|---|---|---|---|---|
| AkashML | 0.030 | 0.170 | bf16 | 20-33s |
| CoreWeave | 0.030 | 0.170 | fp4 | 24-29s |
| DeepInfra | 0.037 | 0.170 | bf16 | 12.3s |
| **Groq** (pinned) | 0.150 | 0.600 | unknown | 0.9s |
| **Cerebras** (pinned) | 0.350 | 0.750 | fp16 | 0.4-0.8s |

  DEC-030 recorded $0.037/$0.170 — DeepInfra's rate, and the model-level headline
  price. It is not what the shipped configuration pays. **Cerebras is the most
  expensive of all 22 providers.**
- **Measured cost per 100-question Tier 2 run**, from instrumented token counts
  (~7,240 in / ~2,990 out per question across 8 judge calls): **~$0.48 pinned to
  Cerebras/Groq, versus ~$0.07 on the cheapest providers.**
- **Decision:** Keep `["Cerebras", "Groq"]`. 41 cents per run to avoid roughly 3.5
  hours of wall clock is worth paying, and Cerebras serves **fp16** — the highest
  fidelity quantization on the list, where several cheaper providers serve fp4. For a
  judge whose scores need to be stable, that is a second reason to prefer it, not just
  speed.
- **The structural point:** the cheap providers *are* the slow ones. Speed on
  OpenRouter is bought, not found. Any future provider pin should be costed before it
  is committed — which is what did not happen in DEC-032 (MIS-008).
- **Evidence:** Measured — per-provider pricing and quantization from OpenRouter's
  endpoints API; latencies from the DEC-032 instrumentation; token counts from the
  same instrumented run. Account spend at the time of this decision: $24.42 total,
  $0.76 that day.
- **Consequences:** Tier 2 costs roughly $0.48 per 100-question run rather than the
  cents implied by DEC-030. Twenty such runs is about $10. The pre-run cost estimator
  (`rag/runner/cost.py`) reads model-level prices, so **it under-reports the judge
  cost for a pinned configuration** — tracked as OQ-018.
- **Revisit if:** Tier 2 run frequency rises enough for the difference to matter, a
  cheaper provider becomes fast, or OQ-017 shows fp16 versus fp4 does not measurably
  affect judged scores — in which case the cheap providers become defensible.

## DEC-035 — The cost estimator reads pinned-provider prices and is calibrated on a real run
- **Date:** 2026-09-11
- **Decided by:** Claude (fixing OQ-018 at Krutik's request)
- **Status:** Active — **corrects DEC-034's cost figures**
- **Context:** OQ-018 recorded that `rag/runner/cost.py` under-reported pinned judge
  cost. Measuring it properly showed it was worse than "under-reports": on a 5-question
  run that cost $0.0404, the estimator printed **$0.00**. Two causes — it read the
  model-level price (DeepInfra's $0.037, not Cerebras' $0.350), and its output-token
  model was a `x3.0 call allowance` guess that was **9x low**. Ragas emits far more
  than one sentence per call: statement lists, per-claim verdicts with reasons.
- **Measured** — `run_20260911_045508_9f7c`, 5 real `dev` questions, real 5-chunk
  contexts, all three Ragas metrics, judge pinned to Cerebras (all 40 chat calls
  landed there); cost is OpenRouter's own per-call `usage.cost`:

| | Per question | Synthetic probe (DEC-034) had |
|---|---|---|
| Chat calls | 8.0 | 8.0 |
| Embedding calls | 2.0 | 2.0 |
| Judge tokens in | **11,164** | 7,241 |
| Judge tokens out | **5,575** | 2,993 |
| Judge cost | **$0.0081** | $0.0048 |

  Embedding cost was below $0.00001 per question and is ignored.

- **Decision:** The estimator now (a) reads per-provider pricing from
  `/models/<id>/endpoints` and charges the judge at the first pinned provider that
  serves the model; (b) uses per-question token volumes calibrated on the run above,
  scaling input linearly with context size (faithfulness re-sends the context) and
  holding output at the measured figure; (c) prints which provider it priced at and
  the rate; (d) says **UNAVAILABLE — do not read as free** rather than $0.00 when it
  cannot price something. The generator is unpinned, so it is priced at model level
  and labelled as a floor.
- **Validation, out of sample** — `run_20260911_045705_cc73`, **8 different questions**
  (seed 11), not the calibration set: judge tokens in **+1%**, tokens out **+4%**, cost
  **+3%** versus OpenRouter's reported spend. Matching the calibration run itself to 0%
  is a tautology and is not claimed as evidence.
- **The corrected headline figures:**
  - 100-question Tier 2 run, judge pinned to Cerebras: **~$0.84** ($0.81 judge +
    $0.03 generator). DEC-034 said $0.48.
  - Same run on the cheapest providers (AkashML/CoreWeave, $0.030/$0.170): **~$0.13**,
    at 20-33s per call. DEC-034 said $0.07.
  - The tradeoff Krutik accepted in DEC-034 is therefore ~$0.71 per run, not ~$0.41,
    to save roughly 3.5 hours. Recorded so the decision rests on the real number; it
    was not re-put to him, since it does not change the shape of the choice.
- **Evidence:** All measured as above. The estimator's own output is an estimate and
  says so on every line it prints.
- **Consequences:** The pre-run estimate is now within a few percent of the bill for
  the default configuration. Calibration is tied to `top_k=5`, `chunk_size=512` and
  this judge; a chunking experiment that changes context size is covered by the
  linear scaling, but a different judge model or Ragas version changes how much it
  emits and needs a fresh calibration run — which is one instrumented 5-question run.
- **Revisit if:** judge model, Ragas version, or metric set changes; or the estimate
  drifts more than ~20% from reported spend on a real run.

## DEC-036 — Our metrics versus the WixQA paper's: where they match, where they differ, and why the numbers are not placed side by side
- **Date:** 2026-09-11
- **Decided by:** Claude (P0-14 research; Krutik not in the loop)
- **Status:** Active
- **Context:** P0-14 asks where our metric definitions match the paper's (Cohen et
  al., *WixQA*, arXiv:2505.08643) and where they deliberately differ, and to run the
  paper's baseline if comparable. The full text was read on 2026-09-11.

### What the paper measures

| Aspect | Paper | This project |
|---|---|---|
| Retrieval metric | **Context Recall**: GPT-4o judges, 0-1, whether "essential information required to formulate the ground truth answer is present within the retrieved context" | **Strict / loose recall@k, nDCG@10, MRR** over gold `article_ids` — labelled, deterministic, no judge |
| Retrieval unit | Whole documents, top-5 | 512-word chunks pooled to documents, top-5 shown, 100 ranked |
| Retrievers | BM25; `e5-large-v2` dense | BM25 (Phase 0); dense in Phase 1 |
| BM25 tokenizer / params | Not stated | lowercase `[a-z0-9]+`, Okapi k1=1.5 b=0.75 |
| Generation metrics | token F1, BLEU, ROUGE-1/2; **Factuality** (GPT-4o judge, 0-1) | citation precision/recall, step coverage, refusal (deterministic); Ragas faithfulness / correctness / relevance (judged, placeholder) |
| Generators | Claude 3.7, Gemini 2.0 Flash, GPT-4o, GPT-4o mini | `gpt-5-nano`, held constant |
| Question sets | all 200 ExpertWritten, all 200 Simulated, all 6,221 Synthetic | `dev` = 100 + 100, `test` held out; `dev_large` = Synthetic with a leakage warning |
| Splits | none — all test-only | dev / test / dev_large / unanswerable |
| Unanswerable set | none | 45 authored |

### Where we match
- Same corpus and question sets, pinned to one revision.
- Same retrieval unit at the point of scoring: documents. (We chunk, then pool.)
- Same top-5 for what a generator sees. Same BM25 baseline family.
- Same multi-article proportions, as a sanity check: the paper reports 27%
  ExpertWritten and 14% Simulated; we measured 26% and 13.5%.

### Where we deliberately differ, and why
1. **No judged retrieval metric.** The paper's Context Recall is exactly what
   DEC-020 rejected: an LLM estimate of retrieval quality for a dataset that ships
   labelled `article_ids`. Ours is cheaper, deterministic, and answers a sharper
   question ("were all the required documents retrieved?") rather than a softer one
   ("was enough information present?"). The paper's number is also a property of the
   judge model, and GPT-4o at the time of writing is not the GPT-4o of the paper.
2. **Strict recall.** The paper has no metric that penalises finding one of two
   required articles. 79 of the 400 human-grounded questions need 2-3 documents, and
   EXP-0001 shows loose 0.675 vs strict 0.175 on them — the metric the paper lacks is
   where the largest effect in our baseline lives.
3. **No token-overlap generation metrics.** F1/BLEU/ROUGE against a reference answer
   are weak on long procedural text — a correct paraphrase scores low. We use the
   gold `article_ids` for citation precision instead, which the paper does not, and
   step coverage, which nothing in the paper resembles.
4. **A held-out split.** The paper evaluates on everything; we hold 200 back. So
   even an identical metric would be computed on different questions.

### Decision
- **The paper's numbers are not placed next to ours.** Context Recall 0.73 and strict
  recall@5 0.41 measure different things on different question sets, and putting them
  in one table would invite a comparison that is invalid.
- **The paper's retrieval configuration was run**, as EXP-0002 — BM25, whole
  documents, top-5 — because it is reproducible as a *configuration* even though its
  *numbers* are not comparable. It differs from EXP-0001 on one axis (chunking) and
  scored strict recall@5 0.410 against the baseline's 0.405: no measurable difference.
  That is the anchor the narrative gets: "on the paper's own retrieval setup, our
  labelled headline metric is 0.41".
- **Evidence:** The paper's tables 3-5, read 2026-09-11; EXP-0001 and EXP-0002.
- **Consequences:** Nothing in this project can be described as reproducing the
  paper's results. The narrative may say the paper's *setup* was run and what it
  scored on our metrics, and must say why the two are not comparable.
- **Revisit if:** the paper releases its BM25 implementation or a labelled-recall
  number, or if we ever compute a judged context-recall for another reason and want
  a one-off comparison, clearly labelled as such.

## DEC-037 — The judged-metric noise floor, measured; and the rule it imposes
- **Date:** 2026-09-11
- **Decided by:** Claude (running OQ-017 at Krutik's request); the floors are
  measurements, the rule follows from CLAUDE.md section 3
- **Status:** Active
- **Context:** OQ-017 asked how much judged scores move between identical runs. Until
  answered, no judged difference could honestly be called a finding, because the rule
  "a difference smaller than the run-to-run spread is not a finding" had no spread to
  compare against.

### What was run
1. **Three identical full runs** of EXP-0001's Tier 2 config on the fixed 100-question
   subsample: `run_20260911_053316_510b`, `run_20260911_055914_a8b3`,
   `run_20260911_061624_3792`. Same config hash, zero judge failures, zero retries.
   (Runs 2 and 3 carry `git_dirty=1`; the only uncommitted change was an edit to
   `user_stories/phase1stories.md`, not code.)
2. **Two judge-only re-scorings** of run 1's stored answers — identical answers,
   contexts and references, so any change is the judge alone. Saved as
   `results/oq017/rejudge_*.json`; summary in `results/oq017/summary.json`.

### Measured — full pipeline (generator and judge both vary)

| Metric | run 1 | run 2 | run 3 | **range** | stdev |
|---|---|---|---|---|---|
| faithfulness | 0.8185 | 0.8338 | 0.8025 | **0.031** | 0.016 |
| answer_correctness | 0.3486 | 0.3476 | 0.3577 | **0.010** | 0.006 |
| answer_relevance | 0.7577 | 0.7603 | 0.7288 | **0.031** | 0.018 |
| citation_precision | 0.3883 | 0.3815 | 0.3841 | 0.007 | 0.003 |
| citation_recall | 0.3950 | 0.3933 | 0.3983 | 0.005 | 0.003 |
| false_refusal_rate | 0.020 | 0.030 | 0.030 | 0.010 | 0.006 |
| step_coverage | 0.1234 | 0.0800 | 0.1434 | **0.064** | 0.032 |
| strict_recall@5 | 0.400 | 0.400 | 0.400 | 0.000 | 0.000 |

### Measured — judge only (same 100 answers, judged three times)

| Metric | original | pass 1 | pass 2 | range | stdev |
|---|---|---|---|---|---|
| faithfulness | 0.8185 | 0.8241 | 0.7988 | 0.025 | 0.013 |
| answer_correctness | 0.3486 | 0.3356 | 0.3454 | 0.013 | 0.007 |
| answer_relevance | 0.7577 | 0.7873 | 0.7660 | 0.030 | 0.015 |

### What the numbers say
- **The noise is the judge, not the generator.** The judge-only range is nearly the
  whole full-pipeline range (faithfulness 0.025 of 0.031; relevance 0.030 of 0.031).
  The generator is *not* deterministic — **0 of 100 answers were byte-identical
  across the three runs** — but its variations barely move the aggregates: citation
  precision, which depends only on the generator, ranged 0.007.
- **At the question level the judge is unstable; at the aggregate it averages out.**
  Re-judging the identical answer, faithfulness moved by ≥0.25 on **12 of 100
  questions** and was identical on 50. Mean absolute movement 0.08, median 0.002.
  A per-question judged score is not evidence of anything on its own.
- **Step coverage cannot currently detect anything.** Its range (0.064) is half its
  value (0.08-0.14). It applies to 32 questions and its lexical matcher flips on
  paraphrase (OQ-007). Until the matcher is fixed, no step-coverage difference is a
  finding, at any size that has been observed.
- **Retrieval metrics have zero spread**, as expected: BM25 is deterministic. Every
  retrieval delta is real; the floors are for the judged and generated half only.

### Decision — the floors, and the rule
Encoded in `rag/eval/noise_floor.py` with their provenance, and applied by
`rag diff`, which now prints a verdict for every judged and generated aggregate:

| Metric | Floor (range, 3 runs) |
|---|---|
| faithfulness | **0.032** |
| answer_correctness | **0.011** |
| answer_relevance | **0.032** |
| citation_precision | 0.007 |
| citation_recall | 0.005 |
| false_refusal_rate | 0.010 |
| step_coverage | 0.064 |

> **CORRECTED by DEC-043 on 2026-09-12** — the two citation floors were measured with
> the v1 parser. Under `citation-v2` on the same runs: precision **0.001**, recall
> **0.018**. `noise_floor.py` carries the v2 values.

> **CORRECTED by DEC-045 on 2026-09-13** — `false_refusal_rate`'s floor was measured with
> the v1 detector, which missed most refusals. Under `refusal-lexical-v2` the three runs
> are 0.20 / 0.15 / 0.21: floor **0.060**. `noise_floor.py` carries the v2 value.

**A judged or generated delta at or below its floor is written as "no measurable
difference".** Not "a slight improvement", not "directionally positive". The range
is used rather than a standard-deviation multiple because three samples cannot
support a distributional claim, and the range is the conservative reading.

- **Evidence:** All measured as above; artifacts in the results store and
  `results/oq017/`.
- **Consequences:**
  - These floors hold for *this* judge, provider pin, Ragas version and subsample.
    Any change to those re-measures them: three runs, ~$2.50, ~1 hour.
  - DEC-033 kept Tier 2 at 100 questions pending this number. At n=100 the floor on
    faithfulness is ~0.03 — usable for detecting effects of a few points, not for
    finer ones. Whether that is enough depends on effect sizes not yet seen.
  - The judge is still a placeholder (DEC-018). A real judge would need its own
    three runs before any of its numbers are interpreted.
  - Per-question judged scores must not be used to explain individual failures in
    `FAILURES.md` without a re-judge to confirm them; 12% of them move by a quarter
    point on identical input.
- **Revisit if:** judge, provider, Ragas version, subsample or generator changes; or
  if a fourth-plus replicate on any config shows a range outside these floors.

## DEC-038 — Reconcile the chunk config at 600 words / 100 overlap for both controls
- **Date:** 2026-09-12
- **Decided by:** Joint — the Phase 1 handover (Krutik) names 600/100 as the default
  and 512/0 as acceptable if there is a reason to prefer it; Claude looked for such a
  reason, found none, and took the default. Krutik has not been asked separately.
- **Status:** Active
- **Context:** P1-01. The Phase 0 sparse baseline EXP-0001 was run on 512-word
  chunks with no overlap; the Phase 1 dense control is specified at 600/100. Two
  controls that differ in chunking *and* retrieval method cannot answer "does dense
  beat lexical here?" — the question Phase 1 exists to set up.
- **Options considered:**
  1. Keep 512/0 and run the dense control on it — keeps EXP-0001 as the control
     unchanged. Rejected only because the handover prefers 600/100 and nothing in the
     corpus profile argues against it; a Tier 1 BM25 re-run costs seconds and $0.
  2. Move both controls to 600/100 and re-run BM25 — chosen.
- **Decision:** Both controls use `fixed_token` with `chunk_size: 600`,
  `overlap: 100`, in **whitespace words** (DEC-005 stands; 600 words is ~760 BPE
  tokens at the measured 1.265 tokens/word). BM25 is re-run under it as EXP-0003;
  EXP-0001 is marked SUPERSEDED, its row and numbers kept. `RunConfig`'s default
  `chunker_params` moves from 512/0 to 600/100 so an omitted field lands on the
  control; every experiment config still spells it out.
- **Evidence:** No measured retrieval data — a judgment call on comparability. The
  corpus profile (`rag corpus profile`, `results/corpus_profile/c852878d74a8.json`)
  describes what the two configs do to the corpus, and is a characterization, not a
  quality claim: 600/100 produces 8,218 chunks and 79.0% of articles fit in one chunk;
  512/0 produces 8,694 and 73.3%. Under 600/100 no procedure block (DEC-039) is cut,
  because the 100-word overlap is longer than all but 20 of the 5,936 blocks (max 144
  words); under 512/0, 210 blocks (3.5%) are cut. Whether any of that moves a
  retrieval metric is what EXP-0003 versus EXP-0001 will show and is not asserted here.
- **Consequences:** EXP-0001 and EXP-0002 remain valid measurements of their own
  configs but are no longer the control. Any Phase 1 or later row compares against
  EXP-0003 (sparse) or the dense control once it exists. EXP-0001's Tier 2 variant is
  **not** re-run under this decision: P1-01 asks for the sparse control row, and the
  Tier 2 re-run belongs to P1-07 run 4 once P1-03's distinct-document retrieval
  exists, so that it is done once rather than twice.
- **Revisit if:** the Phase 2 chunk-size sweep (OQ-003) is run — then the control
  becomes whichever config that sweep's comparison family is built on.

## DEC-039 — Procedure blocks are detected by a fixed heuristic, because the frozen text has no list markers
- **Date:** 2026-09-12
- **Decided by:** Claude (implementing P1-02); definition is open to Krutik's revision
- **Status:** Active
- **Context:** P1-02 asks for "count and fraction of articles containing numbered
  step lists" and "chunk boundaries that land mid-procedure". Counted before
  implementing (preflight item 1): **21 of 6,221** articles contain a line starting
  `1.`/`1)`, and 5 contain two or more. The source's ordered lists lose their markers
  at extraction; a procedure in `contents` reads "To remove animation:\nClick the
  element. Click the Animation icon. Click None." The literal count answers the
  story's question with a number that describes the extraction, not the articles.
- **Options considered:**
  1. Report the literal count only — honest and useless as a "before" number.
  2. Re-freeze with `html_content` and count `<ol>` — needs a new `corpus_hash`
     (DEC-003) and starts a new comparison family for a profiling number. Rejected.
  3. Define a text heuristic, report it alongside the literal count, and validate it
     later — chosen.
- **Decision:** A **procedure block** is: a header sentence ending in `:` at the end
  of a line (the text since the previous sentence terminator or newline), followed by
  two or more consecutive sentences that each open with a verb from the fixed list
  `IMPERATIVE_VERBS` in `rag/corpus/profile.py`. The header is part of the block. A
  block is **cut** under a chunk config when no single chunk contains all of it. The
  literal numbered-line count is reported beside it. Both are labelled as what they
  are in `EXPERIMENTS.md`; the profile version string (`profile-v1`) is bumped on any
  change to the definition, and the old block stays.
- **Evidence:** Counts above, from the frozen corpus. The heuristic was checked by
  reading ~15 detected blocks and the first three cut blocks under each config; an
  earlier version that took the whole *line* as the header dragged preceding prose
  into blocks (articles have a median of three newlines) and was corrected before
  any number was recorded. Agreement with the source HTML is **untested** (OQ-020).
- **Consequences:** `tiktoken` is now a declared dependency (it was already installed
  transitively) for the BPE-token column, using `cl100k_base` as DEC-029 did. The
  "mid-procedure boundary" number for Phase 2's structure-aware chunker is the
  heuristic's, and inherits its error; a Phase 2 comparison must use the same
  `profile-v1` definition on both sides.
- **Revisit if:** OQ-020 finds the heuristic disagrees with hand reading on more than
  a handful of a 30-article sample, or Phase 2 re-freezes with markup for its own
  reasons.

## DEC-040 — `top_k` counts distinct documents, found by walking a capped candidate pool
- **Date:** 2026-09-12
- **Decided by:** Claude (implementing P1-03; the story specifies the mechanism, the
  three details below are mine)
- **Status:** Active
- **Context:** Gold is document-level and 40 of 200 `dev` questions need two or three
  distinct articles. The generator's context was the first `top_k` **chunks** of the
  ranking, and adjacent chunks of one long article collapse into one document, so a
  five-chunk context could hold two articles and structurally fail a three-document
  question no matter how good the ranking. Phase 2 would then be tuning embeddings
  against a granularity problem.
- **Decision:**
  1. `top_k` is the number of **distinct documents** in the context. The retriever
     walks its ranked chunk list, keeps the first chunk seen per document, and stops
     at `top_k` documents or after `candidate_pool` chunks (default **50**; must
     satisfy `top_k ≤ candidate_pool ≤ retrieval_depth`). Stopping on the pool is
     recorded per question as `pool_exhausted`, never hidden.
  2. **One chunk per document reaches the generator** — the document's best-ranked
     chunk, which under `max` pooling is the chunk that scored it. Keeping every
     scanned chunk of a selected document would make the context size depend on
     the collapse ratio and is a different design; it is OQ-022, not this decision.
  3. **Collapse ratio** = chunks scanned ÷ distinct documents returned, per question;
     reported as mean and p90 per run and per slice (`collapse_ratio`,
     `collapse_ratio__p90`). `gold_in_context` (every gold document reached the
     generator; `None` where there is no gold) is recorded per question because it
     is the input-side fact OQ-019's refusal metrics need. Neither is a retrieval
     quality metric.
  4. Scoring is unchanged: retrieval metrics are still computed over the `max`-pooled
     document ranking at `retrieval_depth` (DEC-012, DEC-013). The walk governs
     what the generator sees, not what `ranx` scores. Tier 1 numbers of a config
     therefore do not move when this lands; the Tier 2 context does.
- **Evidence:** No measured data on the ratio yet — EXP-0004 measures it. The
  structural argument is arithmetic: k chunks from fewer than k documents cannot
  satisfy a k-document gold set.
- **Consequences:** `candidate_pool` is a new `RunConfig` field, so every config's
  `config_hash` changes; comparability is unaffected (it is keyed on corpus, split,
  normalization, pooling and judge, not on config hash). `run_questions` gains
  `context_chunk_ids`; `runs` gains `retriever_meta`. Existing rows keep NULL.
  EXP-0003's Tier 1 metrics are reproduced exactly by EXP-0004; the rows differ in
  what a Tier 2 run of each would feed the generator.
- **Revisit if:** the measured p90 collapse ratio makes 50 too small (exhaustion rate
  above a few percent on `dev`), or OQ-022 shows one-chunk-per-document costs
  answer quality.

## DEC-041 — Dense-retrieval embedding model: `qwen/qwen3-embedding-8b`, hosted, pinned to DeepInfra
- **Date:** 2026-09-12
- **Decided by:** Krutik (model; asked for "hosted, cheap but good" over the handover's
  local option). Claude chose the provider pin between the two equal-price
  providers and says so here.
- **Status:** Active
- **Context:** P1-04 asks for one embedding model for the dense control, suggesting a
  local bge-base / e5-base class model. Measured before asking: **36.7% of the 600/100
  chunks exceed 512 tokens** (p95 748, max 1,336), and both suggested classes cap at
  512 — the truncation DEC-027 rejected for the Ragas embedder. Local options that
  clear it (bge-m3, Qwen3-Embedding-0.6B) need torch (~2 GB) on a 16 GB machine.
- **Options put to Krutik** (live OpenRouter prices, 2026-09-12; index = 3.22M tokens):
  `qwen/qwen3-embedding-8b` $0.032/index, 32k ctx; `baai/bge-m3` $0.032, 8k;
  `openai/text-embedding-3-small` $0.064, 8k; `voyageai/voyage-4-lite` $0.064, 32k,
  prefix handling unknown. Local options were offered first and declined.
- **Decision:** `qwen/qwen3-embedding-8b` via OpenRouter, **provider pinned to
  DeepInfra with fallbacks disabled**, `qwen3` prefix convention (instruct prefix on
  queries, none on passages, per the model card). One model now serves both dense
  retrieval and Ragas `answer_relevance` (DEC-027).
- **Why the pin, and why it is part of the index key:** probed both $0.01 providers
  with identical input. Both honour `provider.order` + `allow_fallbacks: false` and
  name themselves in the response — and **return different vectors** (first
  component 0.02954 on DeepInfra vs 0.02967 on Nebius). A fallback mid-build would
  mix two embedding spaces in one index. The embedder refuses an unpinned hosted
  model, asserts the responding provider, and the index key includes
  `provider:DeepInfra`. DeepInfra over Nebius: same price, same context; DeepInfra
  also serves bge-m3 and is the model-card price provider. No measured basis for
  preferring one — a coin with a recorded side.
- **Evidence:** Measured — chunk token distribution, provider probe, prices. **No
  retrieval quality data**; the only external claim in play (Qwen3-Embedding-8B led
  MTEB multilingual at release) is labelled external and untested.
- **Consequences:** The dense control costs ~$0.03 to index and fractions of a cent
  per query; Tier 1 dense runs are no longer $0 and the runner records the exact
  provider-reported query cost. The `sentence_transformers` backend stays as built,
  undeclared in `pyproject` until a story needs it. Comparability of dense runs is
  keyed on `(model, provider, prefix_convention)` alongside the existing keys.
- **Revisit if:** DeepInfra stops serving the model (re-index on another provider
  starts a new family), or Phase 2 makes embedding models the axis under study.

## DEC-042 — The Phase 1 prompt: `baseline_answer@v1`, one prompt, step-list output as a controlled confound
- **Date:** 2026-09-12
- **Decided by:** Claude (implementing P1-05; the handover names the format and
  recommends one prompt over a branching pair)
- **Status:** Active
- **Context:** WixQA reference answers are procedural markdown for about a quarter of
  `dev` (54 of 200 have a numbered list, MIS-002). Step coverage is lexical and
  order-aware, and answer correctness is judged against the reference. A prompt that
  returns prose for a "how do I" question is scored as omitting every step, and every
  later comparison inherits that noise.
- **Decision:**
  1. One prompt, `prompts/baseline_answer.yaml` version `v1`, content hash
     `sha256:a5e9b4d936151a8`, pinned in `tests/test_prompts.py`. Frozen for the
     phase: any edit is `v2` and invalidates the control.
  2. **Output format is chosen to match the evaluation reference, not because it
     was found to be better.** The prompt demands a numbered list (`1. `, `2. `, one
     action per line, no bullets) for how-to questions, short prose otherwise, and
     English regardless of the question's language. This is a **controlled
     confound**: it removes format from the measurement rather than measuring it.
     Phase 2 may revisit.
  3. One prompt with an in-prompt condition, not two prompts selected by a
     classifier — the handover's recommended default; a classifier would be a
     component with its own error rate.
  4. `[doc:<id>]` on every step or sentence; **no URLs** — links are rendered from the
     doc store's `url` field (P1-06). A fixed refusal phrase, "The provided articles
     do not cover this.", chosen because DEC-014's lexical detector matches it.
  5. `RunConfig.generator_prompt` defaults to `baseline_answer@v1`. The Phase 0 Tier 2
     configs now pin `answer@v1` explicitly so they still reproduce their runs.
- **Before freezing — a format check, not tuning:** the first draft, tried on one
  procedural `dev` question through `rag ask`, came back as bullet points with several
  actions per bullet (step coverage 0.00 on format alone). The format rule was made
  explicit and re-checked on three procedural questions: all three returned numbered
  lists. One of them, whose question opens with the typo "Hoe", was answered in
  **Dutch**; "Answer in English" was added and re-checked. Four generator calls in
  total, on `dev`, looking only at whether the output *shape* matched the instruction.
  No metric was compared between drafts.
- **Evidence:** No measured data on quality. The format facts above are observations
  from four calls.
- **Consequences:** Tier 2 runs from here use `baseline_answer@v1`; EXP-0001's Tier 2
  variant (`answer@v1`) is not comparable to them on generation metrics — the
  prompt differs. `answers_with_url` is recorded per run and must be 0.
- **Revisit if:** step coverage stays near zero on questions whose gold documents
  were retrieved (then the matcher, not the format, is the problem — OQ-007), or a
  Phase 2 story measures prompt format as an axis.

## DEC-043 — Citation parser `citation-v2`: accept whitespace inside `[doc: <id>]`; recompute the affected rows
- **Date:** 2026-09-12
- **Decided by:** Krutik (on MIS-016; recomputation and floor update by Claude)
- **Status:** Active — **corrects EXP-0001's Tier 2 citation figures and DEC-037's
  citation floors**
- **Context:** MIS-016: the v1 regex `\[doc:([0-9a-f]{8,64})\]` dropped citations the
  model wrote as `[doc: <id>]`. Counted on the three EXP-0001 Tier 2 runs: 4, 12 and
  13 citations per 100 answers never reached the metric.
- **Decision:** `_CITATION` becomes `\[\s*doc\s*:\s*([0-9a-f]{8,64})\s*\]`,
  case-insensitive. `CITATION_PARSER_VERSION = "citation-v2"` is recorded in every
  Tier 2 run's metrics. The three affected rows are recomputed from their stored
  answers and recorded as corrections; the originals stay.
- **Recomputed (v1 reproduces the stored values exactly; v2 is the correction):**

  | Run | precision v1 → v2 (n) | recall v1 → v2 | cited nothing | questions changed |
  |---|---|---|---|---|
  | `run_20260911_053316_510b` | 0.3883 → **0.3826** (88) | 0.3950 → 0.3950 | 12 → 12 | 1 |
  | `run_20260911_055914_a8b3` | 0.3815 → **0.3832** (93 → 95) | 0.3933 → **0.4133** | 7 → 5 | 4 |
  | `run_20260911_061624_3792` | 0.3841 → **0.3831** (87) | 0.3983 → 0.3983 | 13 → 13 | 1 |

  Precision *fell* on two runs: the recovered citations there were to non-gold
  articles. Recall rose only on the run where two previously uncited answers gained
  a correct citation. Six questions changed across 300 answers.
- **Noise floors (DEC-037), re-measured under v2 on the same three runs:** citation
  precision range 0.0067 → **0.0006**; citation recall range 0.0050 → **0.0183**.
  `rag/eval/noise_floor.py` now carries the v2 values. The recall floor is larger
  because the four recovered citations were not spread evenly across runs.
- **Evidence:** Measured, from stored answers; no new calls.
- **Consequences:** Every later Tier 2 row is on v2. The EXP-0001 index cell
  (0.388) is a v1 number and is annotated, not rewritten. Any citation delta against
  EXP-0001 must use the v2 figures above.
- **Revisit if:** the model produces a third citation shape the parser misses —
  preflight item 21 says count it on stored output first.

## DEC-044 — On the unanswerable split, the judge is skipped and citation recall is not applicable
- **Date:** 2026-09-12
- **Decided by:** Claude (preflight item 6, before P1-07 run 3)
- **Status:** Active
- **Context:** The 45 unanswerable questions have no gold document and an empty
  reference answer (DEC-007). Ragas answer correctness scores against the reference;
  with an empty one it either errors per question (MIS-011 would record 45 failures)
  or returns a number that means nothing. Citation recall divides by the number of
  gold documents; with none, the code returned 0.0 — a zero that would read as "the
  system cited nothing right" on a split where there is nothing to cite.
- **Decision:** When a question's reference is empty, the runner records every judged
  criterion as `None` and counts it in `judge_skipped_no_reference`; no judge call is
  made. `citation_scores` returns `recall=None` when there is no gold (precision is
  still computed: citing anything on an unanswerable question is a wrong citation).
  Neither change touches a `dev` number — every `dev` question has gold and a
  reference.
- **What run 3 measures:** `refusal_rate` (fraction refused, lexical detector,
  DEC-014 / OQ-008) and its complement, the **false-answer rate**; plus how many
  false answers carried a citation. Retrieval metrics do not exist on this split
  (DEC-009).
- **Evidence:** No measured data; the not-applicable cases were designed before the
  run, as MIS-002 requires.
- **Consequences:** Judge cost on this split is zero. A future judged metric for
  refusal quality would need its own decision.
- **Revisit if:** a reference-free judged criterion (e.g. "is this a refusal?") is
  adopted to replace the lexical detector (OQ-008).

## DEC-045 — Refusal detector `refusal-lexical-v2`: normalised apostrophes, wider phrase list, opening-window rule; affected rows recomputed
- **Date:** 2026-09-13
- **Decided by:** Krutik (on OQ-008's count; design, labels and recomputation by Claude)
- **Status:** Active — **corrects EXP-0001's Tier 2 refusal figures, EXP-0006, EXP-0007
  and DEC-037's `false_refusal_rate` floor**
- **Context:** OQ-008: on EXP-0007's 45 unanswerable answers the v1 detector found 26
  refusals; reading them found 33. While fixing that, a second defect surfaced: v1's
  patterns use straight apostrophes (`don't`, `can't`) and the model writes curly ones
  (`don’t`), so "I don’t have enough information in the provided articles" never
  matched. And a naive phrase-list extension flagged 15–21 *hedged answers* per Phase 0
  run — a procedure followed by "but the articles do not give a timeline" — which are
  not refusals.
- **Decision — what a refusal is, mechanically:**
  1. Apostrophes are normalised (`’ ‘ ʼ` → `'`) before matching.
  2. The phrase list is extended with the paraphrases seen: "is not covered by the …",
     "they do not cover/describe/specify …", "I would need …", "I'm not seeing any
     article …", "there isn't information/guidance … in/about", "none of the
     articles …", "not possible to answer".
  3. A phrase counts **only within the first 300 characters** of the answer, and
     **only if the answer contains no numbered steps**. Measured basis: on the 45
     labelled answers every refusal put its phrase at character 0–259 with zero
     steps; the hedged Phase 0 answers put it at 617–2,127 after three or more steps.
  4. `REFUSAL_DETECTOR_VERSION = "refusal-lexical-v2"`, recorded on every Tier 2 run.
- **Validation:** `data/authored/refusal_labels_v1.yaml` holds the 45 EXP-0007 answers
  with a label each — **read and labelled by Claude on 2026-09-13, not reviewed by
  Krutik**. v2 agrees with all 45 (v1: 38). `tests/test_generation_metrics.py` holds
  the detector to those labels. On the `dev` runs every newly flagged answer was read;
  all open by declining ("I'm sorry, but I can't find …", "there is no information
  about …").
- **Recomputed from stored answers (v1 → v2):**

  | Run | refused | on strict@5 misses | on strict@5 hits |
  |---|---|---|---|
  | EXP-0007 (unanswerable, 45) | 26 → **33** (0.578 → **0.733**); false-answer rate 0.422 → **0.267** | — | — |
  | EXP-0006 (dense, sub100) | 5 → 5 | 2 → 3 of 33 | 3 → 2 of 67 |
  | EXP-0001 T2 `…510b` | 2 → **20** (0.020 → **0.200**) | 2 → **17** of 60 | 0 → 3 of 40 |
  | EXP-0001 T2 `…a8b3` | 3 → **15** | 3 → 13 of 60 | 0 → 2 of 40 |
  | EXP-0001 T2 `…3792` | 3 → **21** | 2 → 17 of 60 | 1 → 4 of 40 |

  EXP-0001's Tier 2 observation "refused twice, answered 58 of 60 misses" was the
  apostrophe defect: the old prompt refused on **13–17 of 60** misses. MIS-012's point
  (that `false_refusal` should condition on retrieval) stands and is now visibly
  larger. EXP-0006's total is unchanged; one hedged answer moved out, one paraphrased
  refusal moved in.
- **Noise floor (DEC-037):** `false_refusal_rate` range over the three EXP-0001 runs is
  0.010 under v1 and **0.060** under v2 (0.20 / 0.15 / 0.21). `noise_floor.py` carries
  0.060. The old prompt's decision to refuse is itself a noisy generator behaviour.
- **Evidence:** measured, from stored answers; no new calls. The labelled set is the
  only ground truth and is one person's reading of 45 answers.
- **Consequences:** Every refusal figure in `EXPERIMENTS.md` before this date is a v1
  number; the rows are annotated, not rewritten. OQ-008 is answered for this set and
  stays open on human agreement beyond it. The window (300) and the no-steps rule are
  part of the definition; changing either is `v3`.
- **Revisit if:** Krutik's review of the 45 labels disagrees with any; a later run
  shows refusals opening with a phrase the list lacks (count first, preflight 21); or a
  reference-free judged criterion replaces the lexical proxy.

## DEC-046 — Minimum detectable differences for the dense control, measured; floors are per configuration family
- **Date:** 2026-09-13
- **Decided by:** Claude (running P1-11 at Krutik's request); the floors are
  measurements, the rule is a judgment call stated here
- **Status:** Active — **supersedes DEC-037's floors as the active set**; DEC-037's
  values stay on record for reading Phase 0 rows
- **Context:** P1-11. DEC-037 measured the judge's run-to-run noise on the Phase 0
  config (BM25, `answer@v1`). The Phase 1 control differs in retriever, prompt,
  context semantics and parsers, and DEC-037 said its floors hold only for the
  configuration they were measured on. So they were re-measured on the control.

### What was run
Three identical runs of `configs/baseline_dense_tier2.yaml` (config hash
`86cd401cbdac80c7`) on the fixed subsample `sub100:b551f7f49c91`, judge at
temperature 0, provider pinned to Cerebras, index key `f0e720da2aa33751` cached in all
three: `run_20260913_054522_7d37` (EXP-0006, git `4fd0b43`), `run_20260913_202416_9156`
and `run_20260913_205058_dc03` (git `a061be6`). The code differences between the two
SHAs are the refusal detector, the cost estimator and documentation — none touch
retrieval, generation or judging — and the refusal metric below is recomputed from the
stored answers with `refusal-lexical-v2` for all three. Zero judge failures, zero
generation retries. **Cost: ~$0.91 per run, $2.73 for the three**, of which one was
already EXP-0006.

### The rule
**MDD = max(range, 2 × sample stdev) over the three runs, rounded up to 0.001.**
DEC-037 used the range because three samples cannot support a distributional claim;
P1-11's example rule is 2 × stdev. For n = 3 the two rarely differ by more than
0.001 and 2 × stdev is usually the larger, so taking the larger keeps DEC-037's
conservatism and satisfies the story. A delta at or below the MDD is "no measurable
difference". `rag/eval/noise_floor.py` now carries floors **per configuration family**
with the runs that produced them; `dense-control-v1` is active and `rag diff` names
the family in its output.

### Measured — corpus level (n = 100)

| Metric | run 1 | run 2 | run 3 | mean | stdev | range | **MDD** |
|---|---|---|---|---|---|---|---|
| faithfulness | 0.883 | 0.896 | 0.893 | 0.891 | 0.007 | 0.013 | **0.014** |
| answer_correctness | 0.434 | 0.426 | 0.414 | 0.425 | 0.010 | 0.020 | **0.020** |
| answer_relevance | 0.794 | 0.775 | 0.792 | 0.787 | 0.010 | 0.019 | **0.021** |
| citation_precision (n=95) | 0.550 | 0.478 | 0.546 | 0.525 | 0.040 | 0.071 | **0.080** |
| citation_recall | 0.608 | 0.575 | 0.610 | 0.598 | 0.020 | 0.035 | **0.040** |
| cited_nothing | 0.050 | 0.050 | 0.070 | 0.057 | 0.012 | 0.020 | **0.023** |
| step_coverage (n=32) | 0.289 | 0.227 | 0.193 | 0.236 | 0.049 | 0.096 | **0.097** |
| step_order_preserved (n=32) | 0.906 | 0.938 | 0.938 | 0.927 | 0.018 | 0.031 | **0.036** |
| refused (v2) / false_refusal_rate | 0.050 | 0.080 | 0.070 | 0.067 | 0.015 | 0.030 | **0.031** |
| has_url | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| strict_recall@5 | 0.670 | 0.660 | 0.670 | 0.667 | 0.006 | 0.010 | **0.012** |
| strict_recall@1 | 0.300 | 0.310 | 0.310 | 0.307 | 0.006 | 0.010 | **0.012** |
| strict_recall@3 / @10 / @20 | identical | | | | 0 | 0 | 0 |
| loose_recall@5 | 0.840 | 0.830 | 0.830 | 0.833 | 0.006 | 0.010 | **0.012** |
| nDCG@10 | 0.6287 | 0.6318 | 0.6318 | 0.6308 | 0.002 | 0.003 | **0.004** |
| MRR (single-gold) | 0.5776 | 0.5840 | 0.5840 | 0.5819 | 0.004 | 0.006 | **0.008** |
| collapse_ratio_mean | 1.102 | 1.100 | 1.102 | 1.101 | 0.001 | 0.002 | **0.003** |

Judged scores are in the results store and are transcribed here only as spreads — the
judge is still the placeholder (DEC-018). The judged *values* do not go into
EXPERIMENTS.md; their MDDs do.

### Measured — per slice, judged metrics (MDD)

| Slice | n | faithfulness | answer_correctness | answer_relevance |
|---|---|---|---|---|
| all | 100 | 0.014 | 0.020 | 0.021 |
| gold_docs:single | 74 | 0.042 | 0.028 | 0.005 |
| **gold_docs:multi** | 26 | **0.112** | 0.050 | 0.074 |
| source:expertwritten | 57 | 0.039 | 0.030 | 0.021 |
| source:simulated | 43 | 0.025 | 0.024 | 0.043 |
| q_len:short | 45 | 0.041 | 0.053 | 0.019 |
| q_len:medium | 24 | 0.007 | 0.033 | 0.023 |
| q_len:long | 31 | 0.047 | 0.050 | 0.067 |

### The sanity check, and why "identical" is the wrong criterion here
P1-11 says the rule-based metrics "must be identical across all three runs; any
variance there is a bug". Two measured facts make byte-identity impossible without any
bug: hosted query embeddings differ call to call (OQ-023 — here 93 and 95 of 100
top-5 document sets identical to run 1, and strict recall@3/@10/@20 identical), and
the generator is not deterministic at temperature 0 (1 of 100 answers byte-identical
between runs; DEC-037 found 0 of 100). The check is therefore evaluated as: index key
identical (yes, all three), retrieval within the OQ-023 floor (yes: one question at
k=1 and k=5, none at k=3/10/20), and generation-dependent metrics reported with their
own MDDs rather than asserted equal. **Nothing here is a bug.**

### What the numbers say
- **The judge is quieter on this config than on Phase 0's** at corpus level:
  faithfulness MDD 0.014 (DEC-037: 0.032), relevance 0.021 (0.032), correctness 0.020
  (0.011 — larger). Per question it is as unstable as before: correctness moved by
  ≥0.25 on 41 of 100 questions between runs of nothing, faithfulness on 31.
- **The generator's citation behaviour is the noisiest thing measured.** Citation
  precision was 0.550, 0.478, 0.546 — a 0.071 swing with no change anywhere. Under
  the Phase 0 prompt it was 0.001. Any citation-precision delta under 0.08 on this
  control is noise, and citation recall under 0.04.
- **Step coverage still cannot detect anything**: MDD 0.097 against a value of
  0.19–0.29 (OQ-007).
- **Slice MDDs are two to eight times the corpus MDD.** Multi-document faithfulness at
  n=26 has an MDD of 0.112; nothing short of a large effect is readable on that slice.
- **The refusal rate on `dev` moved 0.05–0.08** — the same order as the 5 refusals it
  counts.
- Latency is not a quality metric and has no floor, but it varied enormously: p95
  11.7 s / **36.3 s** / 4.3 s. Run 2's judge calls were slow; nothing failed or retried.

- **Evidence:** all measured; runs in the results store.
- **Consequences:** P1-08's scorecard reports every judged metric with these MDDs. The
  Phase 0 floors remain valid for reading Phase 0 rows and are kept in the module under
  their family name. `rag diff` now gives verdicts on dense retrieval deltas too.
- **Revisit if:** judge, provider, Ragas version, generator, prompt, retriever or
  subsample changes — three runs, ~$2.75, ~1 hour; or a fourth replicate falls outside
  these floors.

## DEC-047 — Deterministic metrics are compared with a paired test over per-question outcomes, never by repeat-and-average
- **Date:** 2026-09-15
- **Decided by:** Claude, implementing P2-01 from the Phase 2 handover (Krutik's
  spec); the choice of tests and the seed are Claude's
- **Status:** Active
- **Context:** Retrieval metrics are deterministic for BM25 and near-deterministic
  for hosted dense retrieval (OQ-023). Running the same config three times and
  averaging measures the embedding provider's jitter, not the technique. What does
  carry information is the *pairing*: every question was scored under both runs, and
  the per-question differences are the sample. `run_questions` already stores them.
- **Options considered:**
  1. Repeat-and-average with seeds, as for a stochastic system — rejected: the
     "seeds" change nothing in a deterministic pipeline, and three identical numbers
     look like precision they are not.
  2. A parametric paired t-test — rejected: outcomes are 0/1 per question and the
     multi-document slice has n=40 on `dev`; no distributional assumption is safe.
  3. **Paired resampling tests on the per-question difference** — chosen. A paired
     bootstrap (10,000 resamples, percentile) gives a 95% CI *on the difference*, and
     a sign-flip permutation test gives the p-value under exchangeability. For binary
     metrics the exact McNemar p on the discordant pairs is reported as a cross-check
     that needs no resampling.
- **Decision:** `rag compare <run_a> <run_b> --metric <m>` (`rag/runner/compare.py`)
  is the verdict on every retrieval-metric comparison in Phase 2. It reports the
  contingency (both correct / both wrong / A-only / B-only, or B-higher / A-higher /
  tied for graded metrics), the difference, the CI, the permutation p, and the same
  per slice (single, multi, article type, source, question length). Seed
  `20260915` and the resample count are recorded in every report. Zero LLM calls;
  ~1 s on `dev`, under 20 s on `dev_large` (tested). Questions where the metric is
  not applicable on either side are excluded and counted, not zeroed (MIS-002).
  Repeat-and-average is **not used** for deterministic metrics. The OQ-023 floor for
  hosted dense retrieval (0.012 on n=100) remains a second, independent check: a
  dense-vs-dense delta must clear both.
- **Evidence:** Re-running the Phase 1 control comparison through the tool reproduces
  EXP-0005's flip counts exactly (70 gained / 9 lost on strict recall@5; +0.305,
  CI [+0.230, +0.380], p = 0.0001). On the multi-document slice (n=40) the same
  comparison gives +0.175, CI [+0.025, +0.325], **p = 0.063** — the dense advantage
  on multi-hop questions, which EXP-0005 reported as a 0.175 gain, is not
  significant at 0.05 on `dev` alone. That is a fact about power on a 40-question
  slice, not a retraction; it is why P2-04 decides retrieval axes on `dev_large` and
  confirms on `dev`. Tracked as OQ-024.
- **Consequences:** Every EXP file from Phase 2 on quotes `rag compare` output (Δ, CI,
  p) for retrieval deltas. "Gained N / lost M" alone is no longer a result.
- **Revisit if:** a retriever with genuinely stochastic outcomes appears without a
  cache (P2-03 forbids it); or the CI and permutation p disagree on direction on any
  real comparison, which would mean the difference is too small to call either way.

## DEC-048 — Judged deltas are labelled against MDD by the tooling, from the floor family the run's provenance matches
- **Date:** 2026-09-15
- **Decided by:** Claude, implementing P2-02; the family-matching rule and the
  marginal zone are Claude's judgment calls, stated here
- **Status:** Active — extends DEC-046
- **Context:** DEC-046 measured MDDs and left the verdict to the reader of `rag
  diff`. P2-02 requires the label to be the tool's ("significant" / "within judge
  noise"), every judged metric in `EXPERIMENTS.md` to carry its MDD, replicates
  only in a defined marginal zone, and a re-measured MDD whenever the judge changes,
  with old results keeping their old MDD.
- **Options considered:**
  1. One active floor table applied to every run — rejected: a run under a changed
     judge or prompt would silently borrow floors measured on another instrument.
  2. **Floors per family, matched from the run row** — chosen. A run is placed in a
     family by exact equality on `judge_model`, `judge_provider_order`,
     `judge_embedding_model`, `ragas_version`, `metric_prompt_versions`,
     `generator_model` and `prompt_versions` — P2-02's re-measurement triggers plus
     the generator, which DEC-046 showed is the noisier instrument on citation
     metrics. No match → **"no MDD measured"** and no verdict, never a borrowed number.
     Retriever and subsample are *context* keys: a mismatch is printed as a caveat,
     because the P2-02 rule keeps P1-11's MDD across the axes unless the judge
     changes (DEC-046's revisit trigger is recorded, not enforced).
  3. Retrieval floors keyed on the judge — rejected: they come from hosted query
     embeddings (OQ-023), so a Tier 1 dense run gets the dense control's retrieval
     floors and a BM25 run gets none (its spread is exactly zero).
- **Decision:**
  - Labels: **significant** when round(|Δ|, 3) > MDD; **within judge noise** (judged
    criteria) or **within noise** (generated and retrieval metrics) otherwise; **no
    MDD measured** when no family matches. The delta is compared at the MDD's own
    precision — DEC-046 states MDDs to three decimals, and a fourth would be false.
  - Marginal zone: MDD < |Δ| ≤ **1.5 × MDD** is "significant — marginal, resolve
    with 3 replicates". Replicates are spent there and nowhere else; a delta within
    noise is left as within noise, a delta above 1.5 × MDD needs none.
  - The line format for every judged number in `EXPERIMENTS.md`:
    `faithfulness 0.740 (baseline 0.710, Δ+0.030, MDD ±0.014 → significant)`,
    produced by `format_judged`, printed by `rag diff` and `rag compare`.
  - Per-slice judged deltas use DEC-046's per-slice MDDs (multi-document faithfulness
    0.112 at n=26); slices without a measured floor get "no MDD measured".
  - Each family carries an `effective_date` and its decision id. A judge, judge
    prompt or Ragas change adds a **new** family after three identical runs; old rows
    keep matching the old one.
- **Evidence:** Sanity check on the two DEC-046 replicates
  (`run_20260913_054522_7d37` → `run_20260913_202416_9156`): every corpus-level and
  per-slice delta lands "within judge noise" / "within noise", as it must for the
  runs the floors were measured on. Judged *values* still do not go into
  `EXPERIMENTS.md` while the judge is the placeholder (DEC-018); the rule applies the
  day a real judge is chosen and a family measured for it.
- **Consequences:** `rag diff` output changed: verdicts name the family and its
  caveats. `rag/eval/noise_floor.py` is the only place floors live; `verdict()` now
  returns the P2-02 labels.
- **Revisit if:** a real judge is chosen (new family required before any judged
  delta is reported); or the 1.5 × multiple proves either too wide (replicates
  routinely confirm) or too narrow (a delta just above it later fails to replicate).

## DEC-049 — In-pipeline LLM calls run at temperature 0 through a generation cache, and such runs are marked non-deterministic
- **Date:** 2026-09-15
- **Decided by:** Claude, implementing P2-03; the cache key, location and the
  repeat-flag rule are Claude's
- **Status:** Active
- **Context:** Axis 4 (query transformation), the LLM-as-reranker in Axis 5 and Axis
  8 (agentic retrieval) put an LLM call inside retrieval. Without control, retrieval
  metrics for those configs are random variables and DEC-047's paired test silently
  assumes something false.
- **Options considered:**
  1. Trust temperature 0 — rejected: DEC-046 measured the generator at temperature 0
     producing byte-identical answers on 1 of 100 questions.
  2. Cache in the config (a path or a flag) — rejected: a cold cache changes cost and
     reproducibility, not the configuration under test, so it must not move
     `config_hash`.
  3. **A generation cache owned by the runner, outside the config** — chosen.
- **Decision:**
  - `PipelineLLM` (`rag/generation/pipeline_llm.py`) is the only way pipeline code
    calls a model. Temperature is a constant 0.0, not a parameter. It goes through
    `GenerationCache` (`rag/generation/cache.py`, SQLite at
    `results/generation_cache.sqlite`, gitignored) keyed on
    `(question_id, prompt_id, prompt_version, model_id, input_hash)`, where the input
    hash covers the rendered prompt and the decoding settings.
  - A retriever that calls a model exposes it as `pipeline_llm`; the runner records
    `pipeline_nondeterministic = 1` on the run row and the stats (model, temperature,
    calls, hits, misses, hit rate, prompts used, cache path) as `pipeline_llm_json`,
    with the hit rate also in `metrics_json`.
  - A run of a config that has an earlier VALID run with the same `config_hash`, and
    a hit rate under 100%, is a **repeat without cache backing**: the row gets
    `pipeline_cache_flag` and a warning is printed. `rag compare` warns when either
    run is non-deterministic and under-cached.
  - The runner hands every retriever the cache; retrievers without an LLM ignore it
    and are recorded `pipeline_nondeterministic = 0`.
- **Evidence:** `tests/test_pipeline_cache.py` runs an LLM-in-the-loop smoke config
  (`configs/smoke_p2_03_llm_rewrite.yaml`, a fake deliberately non-deterministic
  model rewriting each query) twice on one cache and once on a fresh one: the warm
  repeat has hit rate 1.0, identical retrieval metrics and identical retrieved
  document lists on all 200 questions; the fresh-cache repeat has hit rate 0.0 and
  is flagged. Harness test only; no real model was called.
- **Consequences:** Every Axis 4/5/8 config must obtain its model through
  `PipelineLLM`; a direct HTTP call from a retriever is a bug. Model choice for those
  axes is still Krutik's (`PipelineLLM` refuses an empty model id).
- **Revisit if:** a technique genuinely needs sampling (temperature > 0) — that would
  need its own decision and would take the run out of DEC-047's scope entirely; or
  the cache grows past what SQLite handles comfortably (unlikely under ~100k rows).

## DEC-050 — Split usage policy: which split decides which axis, enforced by the runner
- **Date:** 2026-09-15
- **Decided by:** Claude, encoding P2-04 from the Phase 2 handover (Krutik's spec);
  the enforcement mechanics are Claude's
- **Status:** Active
- **Context:** `dev` has 200 questions (40 multi-document); `dev_large` has 6,221
  synthetic ones whose text was generated from the gold article, so lexical overlap
  is inflated (preflight item 3). Power and validity pull in opposite directions
  and the trade-off has to be made once, per axis, not per run.
- **Decision:**
  - **Retrieval axes (chunking, embedding, reranking, assembly): decide on
    `dev_large`, confirm on `dev`.** `rag promote` requires both comparisons; the
    `dev_large` one must be significant (DEC-047, p < 0.05) and the `dev` one must
    agree in direction. Disagreement refuses the promotion and is printed as a
    finding to write up.
  - **Axis 3 (retrieval method: dense / BM25 / hybrid / alpha) is decided on `dev`
    ONLY.** The runner refuses `axis: retrieval_method` on `dev_large` unless
    `--allow-leaky-split` is passed, and a run allowed through is recorded with
    `leakage_affected = 1` and cannot be used by `rag promote`.
  - **Judged-metric decisions (Tier 2) are on the `dev` subsample only.** Tier 2 on
    `dev_large` is refused the same way. Axes 4, 7 and 8 and combinations therefore
    decide on `dev`.
  - `test` stays closed (P0-12 guard) until P2-18.
  - A run's `axis` is a config field (`rag/runner/config.py`, `AXES`), recorded on
    the row and excluded from `config_hash` like `name`: it labels, it does not
    change a number.
- **Evidence:** No measured data; the policy is the handover's, with one measured
  motivation: OQ-024 shows the multi-document slice of `dev` cannot separate a
  0.175 gain at p < 0.05.
- **Consequences:** every Phase 2 config carries `axis:`. A `dev_large` run of the
  hybrid sweep is impossible by accident.
- **Revisit if:** `dev_large`'s multi-document slice turns out too small as well
  (OQ-024), which would need a split decision rather than a policy one.

## DEC-051 — `configs/promoted.yaml` is the current best; it moves only through `rag promote`, which matches runs to configs by tier identity
- **Date:** 2026-09-15
- **Decided by:** Claude, implementing P2-05; the tier-identity rule is Claude's
- **Status:** Active
- **Context:** "Current best" reconstructed from the results table is a claim; a
  committed file with a log of every advance is a record. The file starts as a copy
  of `configs/baseline_dense.yaml` (the dense control, EXP-0005, DEC-041).
- **Options considered:**
  1. Match a run to a config by `config_hash` — rejected after it failed on the
     control itself: DEC-042 changed the default `generator_prompt` after EXP-0005
     ran, which moved `baseline_dense.yaml`'s hash (`c535f774bff4b067` →
     `7c99bc8e9a88e878`) without changing a single Tier 1 number. See MIS-019.
  2. **Match by `identity_hash`** — chosen: for a Tier 1 run, the hash over the
     fields that can move a Tier 1 number (split, tier, retriever and params,
     chunker and params, depth, top_k, pool, pooling, seed); for Tier 2, every
     hashed field. `config_hash` stays the exact identity on the row.
- **Decision:**
  - `promoted` is a valid run reference in `rag diff` and `rag compare`: it resolves
    to the newest VALID run of `promoted.yaml`'s configuration on the other run's
    split (today: `run_20260912_225005_be04` on `dev`, the third EXP-0005 replicate).
  - `rag promote <candidate.yaml> --axis A --confirm <a> <b> [--decide <a> <b>]
    --metric M --reason R` re-runs the comparisons, checks DEC-050's split rule, that
    the baseline runs are runs of the current pointer and the candidate runs are
    runs of the candidate file, that neither is leakage-affected, and that the
    verdict passes — the paired test for retrieval metrics (DEC-047), the MDD label
    for judged and generated ones (DEC-048). It then rewrites `promoted.yaml` with a
    dated header and appends to the **Promotion log** table in this file. `--dry-run`
    checks without changing anything.
  - Every run with an `axis` records its diff against `promoted.yaml`
    (`vs_promoted_json`, `promoted_config_hash`) grouped into dimensions (chunking,
    retrieval, assembly, generation); a non-`combination` run that changes more
    than one dimension gets a warning. `rag promoted diff <config>` shows the same.
- **Evidence:** No measured data; process decision. `tests/test_phase2_discipline.py`
  exercises a promotion that passes, one where `dev_large` and `dev` disagree, and
  one with swapped runs.
- **Consequences:** an advance of the pointer without a log row is impossible by
  construction; a log row without its own DEC entry explaining the reasoning is a
  process failure to be fixed in the same commit.
- **Revisit if:** simplicity should win a tie (P2-11 says it does for chunking) —
  `rag promote` currently demands a positive, significant delta; a "revert to the
  simplest indistinguishable config" needs a manual DEC entry and a hand-run of the
  command with the reverse pair, and that is deliberate for now.

## DEC-052 — The cost gate: a dated pricing table, a whole-run estimate, a $2 halt, actuals on every row
- **Date:** 2026-09-15
- **Decided by:** Claude, implementing P2-06; the gate value is the handover's, the
  table format and drift rule are Claude's
- **Status:** Active — **amends DEC-035** (prices now come from the table, not a live
  call at run time)
- **Context:** DEC-035 reads pinned-provider prices from OpenRouter at run time. That
  is right about *which* price applies and wrong about reproducibility: the same
  config estimated a week apart can print two numbers with nothing in the artifacts
  to say why. P2-06 also asks for the dominant cost — embedding the whole corpus for
  a new index — which the Tier 2 estimator never saw.
- **Decision:**
  - **`configs/pricing.yaml`** is the price source: $/Mtok per model per provider,
    with `pricing_version` (a date) and the source endpoints. `rag pricing refresh`
    re-fetches every listed model from `/models` and `/models/<id>/endpoints` and
    stamps the date; the model list is edited by hand when a DEC entry chooses a
    model, the numbers never are. Today's table (version `2026-09-16`, UTC) agrees
    with DEC-034/035: judge on Cerebras $0.35/$0.75, generator $0.05/$0.40,
    embeddings on DeepInfra $0.01. The version is recorded on every run row.
  - **Estimate before anything is spent**, printed with its breakdown and driver:
    index build (corpus tokens × embedding price, **zero when the index is cached**
    — the runner checks the P1-04 index key on disk first), query embeddings,
    generator, judge (DEC-035's calibration), in-pipeline LLM. An unpriced model is
    UNAVAILABLE and gates the run; it is never read as free (MIS-005's lesson,
    applied to money).
  - **Above $2.00 the runner raises `CostGateError` before `start_run`**: nothing is
    recorded, nothing is prompted. Re-running with `--approve-cost '<DEC-NNN>'` lets
    it proceed and appends the estimate, driver and approval to the **Cost approvals
    log** in this file. `--estimate-only` prints the estimate and totals and stops.
  - **Actuals on every row**: provider-reported embedding cost (build and queries
    separately), generator tokens at table price, in-pipeline LLM tokens at table
    price — all measured; the judge's share is the pre-run estimate, because Ragas
    surfaces no token usage, and the row says so (`cost_actual_source`).
  - **Drift**: the median actual/estimate ratio over runs that have both, once there
    are three; outside 0.75–1.33 the runner warns to recalibrate.
  - **Running totals** (Phase 2 axis runs, and all runs) print before every run.
  - **Axis cap**: a new configuration under an axis that already has five recorded
    experiments (distinct config hashes, VALID, non-smoke) gets a warning, not a
    refusal — the handover's rule 1 is a scope rule and P2-15 explicitly allows
    dropping an axis, so a hard stop would be the wrong tool.
- **Evidence:** the estimate for `baseline_dense.yaml` on `dev` with the cached index
  is $0.0001 (query embeddings); for `baseline_dense_tier2.yaml` it is $0.9102, of
  which the judge is $0.8760 — consistent with DEC-035's measured ~$0.84–0.91 per
  Tier 2 run. No new spend was made to establish this.
- **Consequences:** `rag/runner/cost.py`'s live fetch functions remain only as the
  refresh path. A Phase 2 run's cost is traceable to a dated table in git.
- **Revisit if:** OpenRouter changes a pinned provider's price mid-phase (refresh,
  bump the version, note it in the EXP file); or the drift warning fires.

## DEC-053 — Every paid experiment run is approved in chat before it starts; the $2 gate is a backstop
- **Date:** 2026-09-15
- **Decided by:** Krutik
- **Status:** Active
- **Context:** P2-06 gates single runs above $2. Krutik's rule is broader: the budget
  is flexible, but every experiment that spends money gets a heads-up and an
  explicit approval first, whatever the estimate.
- **Decision:** Before any run with a non-zero estimate, Claude posts the config,
  the split, the `--estimate-only` output and what the run decides, and waits.
  The $2 gate and its approvals log stay as the mechanical backstop. Runs of the
  harness smoke tests and `--estimate-only` need no approval (they spend nothing).
- **Evidence:** No measured data; Krutik's instruction, 2026-09-15.
- **Consequences:** No phase spending ceiling is set; the running totals printed on
  every run are the envelope's record.
- **Revisit if:** Krutik sets a ceiling, or the per-run heads-up becomes a
  bottleneck on a cheap axis (Axis 3 costs ~$0 and could be batch-approved).
