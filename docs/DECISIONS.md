# Decisions

Append-only. Every consequential decision, who made it, and the condition that
would make us revisit it. A superseded decision keeps its entry and gains a
`Superseded by DEC-NNN` status.

**Test-split openings log:** see the bottom of this file. **Opened once, on 2026-09-26,
for P2-18** — four rows, one per run, all carrying the same reason and the same git SHA
(`663b555`). One opening event, four runs. Nothing has been tuned since.

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
| 3 | 2026-09-23 | `f853a346cdad3e8f` | $0.2001 (rerank) | DEC-053: Krutik approved in chat 2026-09-22, $0.2001 estimate, EXP-0024 Axis 5 opening run | run `run_20260923_052903_c2ea`, git `f337ae2` |
| 4 | 2026-09-23 | `f853a346cdad3e8f` | $0.2001 (rerank) | DEC-053: Krutik approved in chat 2026-09-22, $0.2001 estimate, EXP-0024 Axis 5 opening run | run `run_20260923_052941_4ada`, git `f337ae2` |
| 5 | 2026-09-23 | `dad293c6d06bc518` | $0.4681 (rerank) | DEC-053: Krutik 'run the other two rerankers' 2026-09-23, $0.4681 estimate | run `run_20260923_054802_6566`, git `a62eaec` |
| 6 | 2026-09-23 | `93e5a1d924c80c32` | $0.9168 (rerank) | DEC-053: Krutik 'run the other two rerankers' 2026-09-23, $0.9168 estimate | run `run_20260923_060805_1b9a`, git `a62eaec` |
| 7 | 2026-09-24 | `93e5a1d924c80c32` | $0.9168 (rerank) | DEC-053: Krutik 'run the other two rerankers' 2026-09-23 + 'resume the work' after crediting; $0.9168 estimate; balance $14.77 checked (preflight 40) | run `run_20260924_033136_e51f`, git `2312ff9` |

## Test-split openings log

P0-12 requires a row here for every opening of `test`, with date, config hash, git
SHA, and reason.

| # | Date | Config hash | Git SHA | Reason |
|---|---|---|---|---|
| 1 | 2026-09-26 | `87353cd987f08f78` | `663b555` | P2-18: the single end-of-Phase-2 opening of the test split. Measures the dev-to-test gap for the Phase 1 dense control (which is also promoted.yaml, unchanged across six axes and 45 runs) and the Phase 1 sparse control, at Tier 1 and Tier 2. No tuning follows this run. (run `run_20260926_010435_6495`) |
| 2 | 2026-09-26 | `0ea2ad99f3c1a7ef` | `663b555` | P2-18: the single end-of-Phase-2 opening of the test split. Measures the dev-to-test gap for the Phase 1 dense control (which is also promoted.yaml, unchanged across six axes and 45 runs) and the Phase 1 sparse control, at Tier 1 and Tier 2. No tuning follows this run. (run `run_20260926_011237_58f7`) |
| 3 | 2026-09-26 | `781216f38f8299cb` | `663b555` | P2-18: the single end-of-Phase-2 opening of the test split. Measures the dev-to-test gap for the Phase 1 dense control (which is also promoted.yaml, unchanged across six axes and 45 runs) and the Phase 1 sparse control, at Tier 1 and Tier 2. No tuning follows this run. (run `run_20260926_011244_9d0e`) |
| 4 | 2026-09-26 | `e29d1973b5492cca` | `663b555` | P2-18: the single end-of-Phase-2 opening of the test split. Measures the dev-to-test gap for the Phase 1 dense control (which is also promoted.yaml, unchanged across six axes and 45 runs) and the Phase 1 sparse control, at Tier 1 and Tier 2. No tuning follows this run. (run `run_20260926_012047_6004`) |

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
- **Status:** Superseded by DEC-073 (2026-09-28) — its family ruling below is reversed.
  Originally: Active — **supersedes DEC-025's model choice**
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
- **Status:** **Superseded by DEC-055** for the "retrieval axes decide on `dev_large`"
  rule. The Axis 3 refusal, the Tier 2 refusal on `dev_large`, `--allow-leaky-split`
  and `leakage_affected` stay in force.
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

## DEC-054 — Axis 2 (embeddings): the four models and their provider pins
- **Date:** 2026-09-15
- **Decided by:** Krutik (models, confirming the Phase 2 handover's P2-08 table);
  Claude proposed the provider pins and the gemini disambiguation, Krutik confirmed
- **Status:** Active
- **Context:** P2-08 sweeps four hosted embedding models plus one dimension-truncation
  run, all through OpenRouter's `/embeddings` endpoint. Slugs and availability change,
  so each was verified against `/models/<slug>/endpoints` on **2026-09-15**.
- **Decision — exact slugs, pins, prefix conventions:**

| # | Slug (verified 2026-09-15) | Provider pin | $/Mtok | Context | Prefix convention | Index estimate |
|---|---|---|---|---|---|---|
| 1 | `openai/text-embedding-3-large` | **OpenAI** | 0.13 | 8,192 | `none` (table) | ~$0.42 |
| 2 | `qwen/qwen3-embedding-8b` | DeepInfra (DEC-041) | 0.01 | 32,768 | `qwen3` (instruct prefix on queries) | $0 — index cached from EXP-0005 |
| 3 | `baai/bge-m3` | **DeepInfra** — served as `baai/bge-m3-20251117`, fp32 | 0.01 | 8,192 | `none` (table) | ~$0.03 |
| 4 | `google/gemini-embedding-2` | **Google AI Studio** | 0.20 | 8,192 | `none`, set **explicitly** in the config | ~$0.65 |

  - Pins: OpenAI is first-party for #1 (Azure is the same price, a second vendor for
    nothing). DeepInfra for #3 holds the provider constant with the qwen control, so
    the #2-vs-#3 comparison changes the model and nothing else. For #4 the three
    endpoints named "Google" are Vertex regions (`google-vertex/us|global|eu`, the eu
    one at $0.22) and cannot be told apart by provider name, which is what the pin
    is; "Google AI Studio" is one endpoint at $0.20. The provider is part of the
    index key (DEC-041), so each pin starts its own index.
  - Prefixes, verified per model (P2-08): text-embedding-3 and bge-m3 take no
    query/passage prefix and the table says so; gemini's native API expresses the
    query/document asymmetry as `task_type`, which OpenRouter's `/embeddings` request
    has no field for, so it is embedded symmetrically with `prefix_convention: none`
    stated in the config. Whether OpenRouter passes `task_type` through is
    **unprobed** — OQ-025 — and so is the `dimensions` passthrough run 5 needs.
  - Every chunk fits every model: the longest 600/100 chunk is 1,336 tokens
    (preflight item 19).
- **Cost, before running (P2-06; estimates):** EXP-0008 $0.003 (queries only),
  EXP-0009 $0.46, EXP-0010 $0.04, EXP-0011 $0.71, each `dev` confirmation ~$0.001–0.002
  on the cached index. Axis total ≈ **$1.2** plus the truncation run (≤ the winner's
  index). Nothing crosses the $2 gate; every run still needs Krutik's go-ahead
  (DEC-053). The estimator's corpus token count (3.23M, overlap included) is 3% above
  what DeepInfra billed for EXP-0005's index (3,125,318).
- **Batching and retries (P2-08):** batches of 64 chunks; 4 attempts with exponential
  back-off on transport errors and 408/409/425/429/5xx, retries counted in the index
  meta (EXP-0005 needed 7 over 129 calls, MIS-014).
- **Caching (P2-08):** the index is cached whole under `indexes/<key>/` keyed on
  (corpus hash, normalization, chunker id, model, provider, prefix convention), and
  `cache_hit` is recorded on the run. An identical config re-run costs only its query
  vectors. This is an index-level cache, not the per-chunk cache the story describes;
  the difference matters only when chunking changes (Axis 1), where every chunk is
  new anyway.
- **Evidence:** slugs, prices and context lengths from the OpenRouter endpoints API on
  2026-09-15; no quality data.
- **Consequences:** EXP-0008 through EXP-0012 are Axis 2. The qwen control gets its
  first `dev_large` run (EXP-0008) as the axis baseline.
- **Revisit if:** a slug disappears or a pinned provider's price moves (refresh the
  pricing table, note it in the EXP file); or OQ-025 shows `task_type` does pass
  through, which would make EXP-0011 a symmetric-only measurement of gemini.

## DEC-055 — `dev` decides every axis; `dev_large` is a single-document direction check, never the decider
- **Date:** 2026-09-16
- **Decided by:** Krutik (options and recommendation by Claude)
- **Status:** Active — supersedes DEC-050's split rule for retrieval axes
- **Context:** DEC-050 (from P2-04) made `dev_large` the deciding split for the
  retrieval axes on the assumption that it carried multi-hop questions with
  statistical power. Two measurements this week undid the assumption:
  - **`dev_large` has no multi-document questions** — all 6,221 are synthetic,
    single-gold, and the control already scores 0.973 strict recall@5 on them
    (EXP-0008, MIS-021). The slice the organizing question is about does not exist
    there.
  - **It can give a confident wrong answer.** bge-m3 gained +0.005 (p = 0.019) on
    `dev_large` and lost 0.160 (p = 0.0001, 40 of 200 questions) on `dev` (EXP-0010,
    H-007 wrong). Synthetic questions reuse their article's wording, which flatters a
    model that tracks surface wording — a dense model, not only BM25.
- **Options considered:**
  1. Keep DEC-050 — rejected: it would have promoted gemini-embedding-2 on a +1.5-point
     gain in synthetic single-article questions while the split with real, multi-article
     questions could not tell it from the control (EXP-0011).
  2. **`dev` decides at p < 0.05; `dev_large` must agree in direction** — chosen.
     Cost: with 200 questions a candidate needs roughly 15 more net flips right than
     wrong to clear the bar, so small real gains are recorded as "no measurable
     difference". That is the honest verdict for a 200-question set.
  3. Build a larger multi-document eval set — deferred: forbidden by the Phase 2
     non-goals (changing splits resets the controls) and a new comparison family.
     Noted for Phase 3 / OQ-024.
- **Decision:**
  - `rag promote` takes `--dev a b` as the deciding pair for every axis. Retrieval
    metrics: paired test p < 0.05 and Δ > 0 (DEC-047). Judged and generated metrics:
    MDD label "significant" and Δ > 0 (DEC-048). Retrieval axes also require
    `--dev-large a b`, which must agree in direction and nothing more; disagreement
    is a finding to write up, not a promotion.
  - The `dev_large` runs of Axis 2 remain valid single-document measurements and are
    reported as such; they are never a headline (preflight item 3).
  - Everything else in DEC-050 stands: Axis 3 and Tier 2 are refused on `dev_large`
    without `--allow-leaky-split`, and a leakage-affected run cannot decide anything.
- **Evidence:** EXP-0008 (split composition), EXP-0010 (direction disagreement),
  EXP-0011 (the case the rule change decides).
- **Consequences:** Applied immediately to Axis 2: gemini-embedding-2 is **not
  promoted** (`dev` +0.030, CI [−0.030, +0.090], p = 0.41; `rag promote --dry-run`
  refuses). `configs/promoted.yaml` stays the qwen dense control. Decision 2 (whether
  to pay 20x per token and take a Google dependency for gemini) does not arise.
- **Revisit if:** a larger human-sourced multi-document set exists (then it decides);
  or three axes in a row end in "no measurable difference on `dev`" while `dev_large`
  and nDCG agree on a gain — that would say the bar is above what 200 questions can
  ever clear and the eval set, not the rule, is the problem.

## DEC-056 — Axis 3 fusion definitions: RRF at k=60, weighted fusion as min-max convex combination, each half at the scoring depth
- **Date:** 2026-09-17
- **Decided by:** Claude (design choices made while building `rag/retrieval/hybrid.py`; put to Krutik in chat before the first run)
- **Status:** Active
- **Context:** P2-09 asks for "hybrid via RRF" and "hybrid via weighted score fusion"
  with an alpha sweep, but neither is a single thing: RRF has a constant, weighted
  fusion needs a rule for putting cosine (in [−1, 1]) and Okapi (in [0, ∞)) on one
  scale, and both need to know how deep each half's list goes. Each of these moves
  the fused ranking, so they have to be fixed and recorded before the sweep rather
  than tuned inside it.
- **Options considered:**
  1. **RRF constant.** k = 60, the value from the paper that introduced it (Cormack,
     Clarke & Buettcher 2009) and the default in every library implementation —
     chosen, with no sweep: the story allows one configuration per method.
  2. **Score normalisation for weighted fusion.** (a) Raw scores — rejected, the
     scales are incomparable and alpha would mean nothing. (b) z-score per list —
     rejected because a chunk missing from one list has no natural value on that
     scale. (c) **Min-max over each list's own returned candidates, missing = 0** —
     chosen. It is the convex-combination form studied by Bruch et al. (2023) and has
     one artefact, recorded in the module docstring and pinned by a test: a list's
     lowest-scored candidate normalises to 0 and ties with everything the list did not
     return. At depth 100 that is rank 100 on both sides, below every k this project
     scores (max 20).
  3. **Depth of each half.** Each sub-retriever contributes its top `retrieval_depth`
     (100) chunks and the fused ranking is scored at the same depth — chosen over a
     separate "fusion depth" knob, which would be one more parameter with no story
     behind it. BM25 returns only chunks with a positive score, so its half can be
     shorter than 100 on short queries; the fused list is then whatever the union is.
  4. **Alpha semantics and grid.** `alpha` is the weight on **dense** (so 1.0 is the
     dense control's ranking and 0.0 is BM25's). Grid 0.2 / 0.4 / 0.6 / 0.8 as the
     story suggests; **not refined afterwards**, whatever the curve looks like (P2-09:
     "report the curve as measured, including if it is flat").
- **Decision:** `hybrid` is registered with `fusion: rrf | weighted`, `rrf_k`
  (default 60), `alpha` (weighted only, refused for rrf), nested `dense:` and `bm25:`
  blocks. Ties in the fused score break on `chunk_id` (MIS-003). The dense half owns
  the index, so the run row's `retriever_meta` carries the dense index key and
  embedder usage at top level (the cost bookkeeping reads them there), plus a
  `fusion` block and per-run `fusion_stats` (mean Jaccard overlap between the two
  candidate sets; how many context documents came from dense only / BM25 only / both).
  The cost estimator and the on-disk index check ask the retriever *class* what it
  embeds (`Retriever.embedding_params`) instead of matching the name "dense", so a
  hybrid run is costed by its dense half and never read as free.
- **Evidence:** No measured data; judgment call on definitions. The BM25 half is the
  EXP-0004 configuration (k1 1.5, b 0.75) and the dense half is the promoted control,
  so both endpoints of the alpha axis have measured runs.
- **Consequences:** Five configs, `configs/exp_0014_hybrid_rrf_dev.yaml` and
  `exp_0015..0018_hybrid_w{02,04,06,08}_dev.yaml`, each a one-dimension diff against
  `promoted.yaml` (`rag promote` sees `retrieval` only). All on `dev`, Tier 1; the
  runner refuses `dev_large` for this axis (DEC-050). `--estimate-only` on EXP-0014:
  index cached, $0.0001 of query embeddings.
- **Revisit if:** the weighted curve behaves asymmetrically at its ends — α=0.8 far
  from the dense control while α=0.2 sits on BM25, or the reverse — which would point
  at the normalisation rather than at the weight; or a later axis needs a third list
  in the fusion (RRF takes any number; the weighted rule is written for two).

## DEC-057 — Axis 1 (chunking): four chunkers, one redefined, one dropped, and how each is costed
- **Date:** 2026-09-18
- **Decided by:** Krutik (options and recommendations by Claude; the three choices below were put to him in chat and taken)
- **Status:** Active
- **Context:** P2-07 lists five chunkers against the fixed-600/100 control:
  sentence-window, parent-document, semantic, structure-aware on headings, and
  late chunking. Two free checks before any code changed the list (counts from
  2026-09-18 over all 6,221 frozen articles):
  - **There are no headings.** 0 articles carry a markdown `#` or HTML `<h1–6>`
    heading. The text's structure is its lines: a title line, prose lines, and
    17,516 of 45,722 lines end in `:` — the "To do X:" procedure headers of DEC-039,
    each followed by a line of steps. Median 4 lines per article, p90 21.
  - **A third of sentence boundaries are glued**: 34,778 of 112,219 `[.?!]`
    boundaries have no space after them ("…account.Before you begin:…"), in 83% of
    articles. A splitter that needs "period, space, capital" would miss them.
  - **Late chunking has no hosted path.** OpenRouter's `/embeddings/models` lists 33
    models, none from Jina; `/embeddings` returns one pooled vector per input,
    `encoding_format` is validated to `float | base64` (HTTP 400 otherwise), and
    `late_chunking: true` / `return_token_embeddings: true` are silently dropped
    (same shape, same 9 tokens billed — the OQ-025 pattern). Four probe calls,
    $0.0000004. Token-level embeddings, which late chunking needs, would require
    the local `sentence-transformers` backend with a different model — changing the
    embedding model and the chunker in one run, which no Axis 1 comparison could
    use.
- **Options considered:**
  1. **Late chunking:** run it locally with a small model as a labelled two-axis
     probe — rejected (not comparable to anything, and "nothing runs on local
     hardware" is the Phase 2 rule); **drop it and record it as unavailable hosted,
     next to ColBERT in HYPOTHESES.md — chosen.**
  2. **Structure-aware:** drop it (no headings) — rejected; **redefine it on the
     line structure — chosen**: cut only at line boundaries; a `:`-terminated line
     is bound to the line after it, the binding chains when a steps line itself ends
     in `:` (it carries the next header), and lines opening with a DEC-039 step verb
     stay with their procedure; pack units to ≤600 words; a single unit over 600
     words is cut at 600. Measured on the corpus: 8,689 chunks, 79.0% of articles in
     one chunk (same as the control), **41 procedure blocks cut of 5,936 — all 41
     inside a unit longer than 600 words**. The control cuts 0 (its 100-word overlap
     covers every block ≤100 words); 600/0 cuts 160.
  3. **Semantic chunking's boundary detector:** a cheaper model for that one job —
     rejected (a new model needs its own DEC and starts a family); **the same
     `qwen3-embedding-8b` on DeepInfra — chosen**, so no new model enters the
     project. Rule: consecutive-sentence cosine distance, boundary where the
     distance exceeds the article's own 95th percentile (LangChain's breakpoint
     rule), groups capped at 600 words. 195,822 sentences to embed (170 articles
     under three sentences are skipped: one distance cannot beat a percentile).
     Distances are cached per article text under `indexes/sentence_distances/`, so
     the chunks are reproducible from the cache; a cold recomputation could move a
     boundary because hosted vectors are not byte-deterministic (OQ-023) — recorded
     here, not hidden.
  4. **Sentence-window unit:** one sentence with a ±3 window (the LlamaIndex default)
     — chosen as the canonical form; measured **196,133 index rows** (median 12 words),
     a ~3.2 GB float32 index, 3,065 embedding calls; context mean 80 words. 3,263 of
     5,936 procedure blocks do not fit in a 7-sentence window. The alternative (a
     3-sentence unit, ~1.1 GB) was offered; the size is an engineering cost, not a
     quality claim, and the run decides the rest.
  5. **Parent-document:** 600-word parents (the control's size, so the generator's
     context size is held constant) with 150-word children, no overlap at either
     level. Measured: 18,884 children, 44.7% of articles in one child; 1,237 blocks
     cut at the child level, **150 at the parent (context) level**.
- **Decision:** Axis 1 is **four** experiments, EXP-0019 sentence-window, EXP-0020
  parent-document, EXP-0021 semantic, EXP-0022 structure — each a one-dimension diff
  against `promoted.yaml` (`chunker` + `chunker_params`), `dev` decides and
  `dev_large` is the direction check (DEC-055), Tier 1, same embedder. Mechanics
  that came with it, all under test:
  - `Chunk.context_text` (P2-07): what the generator sees, distinct from `text`,
    what the retriever indexes. `None` means the same. The runner hands the
    generator and the citation renderer `index.context_text`; the retriever and
    BM25 see `index.chunk_text`. The parquet map persists both.
  - A chunker registry (`build_chunker`, `chunker_class`) — `config.chunker` was a
    field the runner never read before this; it hard-coded the fixed chunker.
  - **Gated pre-spend:** `Chunker.embedding_params` declares what a chunker embeds
    before any chunk exists; the runner estimates it from the corpus word count and
    runs the $2 gate *before* building the chunker's output, then chunks. A test
    proves the embedder is not called when the gate fires.
  - **Chunking profile on every run row** (`chunker_meta`, and
    `metrics_json.chunking_profile`): chunk count, words per chunk, context words,
    articles in one chunk, DEC-039 procedure blocks cut on the indexed text and on
    the context. It reproduces the corpus profile's numbers for the control.
  - Sentence splitting (`sentences-v1`) breaks on newlines, `[.?!]`+space, and
    `[.?!]` followed directly by a capital. No abbreviation list; a heuristic,
    shared by every sentence-based chunker so their units agree. **Side-effect,
    recorded:** sentence-based chunkers put a space at glued boundaries in the text
    they emit ("too. Before"); the fixed and structure chunkers leave the text as is.
  - The dense index build streams into a preallocated float32 matrix in groups of
    2,048 texts; the previous list-then-convert path would have needed ~19 GB of
    temporaries for the sentence-window index.
- **Evidence:** No measured retrieval data; the counts above are corpus
  characterisation, not results. Cost estimates from `--estimate-only`: $0.033,
  $0.033, $0.063 (semantic: $0.030 sentence pass + $0.030 index), $0.033 — ≈$0.16
  for the four `dev_large` builds, plus ~$0.0001 per `dev` run.
- **Consequences:** Late chunking and ColBERT are both "not available hosted" and
  stay in HYPOTHESES.md as future work. The Axis 1 index cache grows by ~3.9 GB
  (gitignored). The per-axis cap warning (5) will fire on the sixth distinct
  config hash — the dev/dev_large pairs count separately by hash, as in Axis 2.
- **Revisit if:** a hosted endpoint starts returning token-level embeddings (probe
  it again, don't assume — MIS-005); or the sentence-window index's size or build
  time proves to be the thing that decides whether the technique is usable, in
  which case the 3-sentence unit gets its own run rather than a guess.

## DEC-058 — Axis 5 reranking: candidates are documents, cost comes from the response, and `dev` decides
- **Date:** 2026-09-22
- **Decided by:** Claude (mechanism only; the **model choice is DEC-059 and is
  Krutik's** — nothing here picks a reranker)
- **Status:** Active
- **Context:** P2-10 adds a reranker between retrieval and the generator. Four
  things had to be settled before any run, and none of them is a model choice.
- **Options considered:**
  1. Make the reranker a retriever that wraps another one, as the hybrid does —
     rejected: it would make every Axis 5 config a change to the `retrieval`
     dimension, so `rag promote` could never tell reranking apart from a retriever
     swap, and the P2-05 one-dimension check would be meaningless for the axis.
  2. Make the reranker its own config dimension (`reranker`, `reranker_params`,
     `rerank_candidates`), applied by the runner — chosen.
- **Decision:** four rules.
  1. **`rerank_candidates` counts distinct documents, not chunks** (P1-03, DEC-040).
     The reranker sees every ranked chunk of the top n documents, so "50 -> 5" means
     the same thing under every chunker. Keeping a document's several chunks in the
     candidate set is deliberate: it is the only way a cross-encoder *can*
     re-concentrate the context onto one article, which is the behaviour P2-10 asks
     to be measured.
  2. **Everything downstream is recomputed from the reranked ranking** — pooling,
     the distinct-document walk, the collapse ratio, pool exhaustion and every
     metric. A post-rerank collapse ratio is the number on the run row.
  3. **Rerank cost is read from the provider's response, never from a price table**
     (MIS-025). The measured rates live in a hand-maintained `rerank:` block in
     `configs/pricing.yaml`; an absent entry is UNAVAILABLE and fails the gate.
  4. **`dev` decides, and `dev_large` is bought only for a winner.** DEC-055 already
     makes `dev` the deciding split. Reranking is billed per query, so the
     `dev_large` direction check costs 31x the `dev` run ($6.22 vs $0.20 for the
     cheapest candidate). Running it for a configuration that lost on `dev` buys
     nothing the promotion rule can use. See OQ-033.
- **Evidence:** measured — the three rerank models' per-query cost and latency on
  real 50-document calls (MIS-025). The rest is judgment on experimental validity;
  no measured data.
- **Consequences:** Axis 5 configs are one-dimension diffs against `promoted.yaml`
  and `rag promote` handles them like any other axis. Adding the three fields would
  have moved the `config_hash` of every run already in the ledger (MIS-019), so an
  axis whose switch is off is excluded from the hash entirely: `promoted.yaml` still
  hashes to `7c99bc8e9a88e878`, asserted in `tests/test_reranking.py`. Any future
  axis added this way must follow the same rule or the ledger breaks.
- **Measured outcome (appended 2026-09-23, EXP-0024).** Rule 4's arithmetic was right
  in shape and low in size: the `dev_large` check is **$7.28**, not the $6.22 written
  above — Cohere's search unit is filled by candidate *length*, not candidate count
  (MIS-028). It was not bought, because nothing won on `dev` (OQ-033, answered).
  Rules 1–3 held: the axis config was a clean one-dimension diff, the post-rerank
  collapse ratio is on the row, and cost came from `usage.cost`.
- **Revisit if:** a reranker wins on `dev` and the `dev_large` check is needed
  (OQ-033), or a second absent-dimension axis makes the hash exclusion list long
  enough to be worth a different mechanism.

## DEC-059 — Which rerankers Axis 5 tests
- **Date:** 2026-09-22
- **Decided by:** Krutik (proposed by Claude)
- **Status:** Active
- **Context:** P2-10 suggests three rerankers. All hosted rerankers go through
  OpenRouter's `POST /api/v1/rerank`, probed 2026-09-22: the endpoint exists and
  works. What it serves is narrower than the story assumed.
- **What was probed** (preflight 10 — the endpoint that would provide it, not a
  neighbouring listing):

  | Model | Result |
  |---|---|
  | `cohere/rerank-v3.5` | served by Cohere. $0.001/query, 778 ms at 50 docs x 600 words |
  | `cohere/rerank-4-fast` | served by Cohere (`rerank-v4.0-fast`). $0.002/query, 1,298 ms |
  | `qwen/qwen3-reranker-8b` | served by Fireworks. $0.008125/query, 1,847 ms |
  | `qwen/qwen3-reranker-4b` | **404 "No endpoints found"** — not served |
  | `baai/bge-reranker-v2-m3` | **400 "does not exist"** — not on OpenRouter |
  | `mixedbread-ai/mxbai-rerank-large-v2` | **400 "does not exist"** — not on OpenRouter |

  There is no rerank model listing to browse: `/rerank/models` is a 404 and
  `/models?category=rerank` is not a valid category, so availability is established
  one model id at a time.
- **Options considered:**
  1. The story's three, substituting `qwen3-reranker-8b` for the unavailable 4B:
     Cohere v3.5 (proprietary baseline), qwen3-8b (open-weight cross-encoder),
     LLM-as-reranker via chat completions (a different mechanism). Estimated `dev`
     cost $0.20 + $0.78 + $0.22 = **$1.20** for the three.
  2. Add `cohere/rerank-4-fast` as a fourth, to separate "Cohere" from "this Cohere
     model" — $0.40 more, and it spends one of the axis's five experiment slots that
     P2-10 reserves for the two k -> n ratio runs.
  3. Cohere v3.5 alone, the cheapest — rejected: one reranker cannot distinguish
     "reranking does not help this corpus" from "this reranker does not".
- **Decision:** **`cohere/rerank-v3.5`, pinned to Cohere, alone** (2026-09-22).
  Krutik chose one reranker rather than Claude's proposed three. The axis opens as a
  single experiment, `configs/exp_0024_rerank_cohere_v35_dev.yaml` on `dev`, $0.20.
  Claude flagged the cost of that narrowness at the time and it is recorded here
  rather than argued: **a negative result from one reranker cannot distinguish "a
  cross-encoder does not help on this corpus" from "this cross-encoder does not".**
  If EXP-0024 is negative, that limit is what the Negative Results entry says, and
  `qwen/qwen3-reranker-8b` ($0.78) and the LLM reranker ($0.22) stay queued in
  OPEN_QUESTIONS rather than being treated as answered.
  `configs/exp_0025_rerank_cohere_4fast_dev.yaml` and `exp_0026_rerank_qwen3_8b_dev.yaml`
  are committed but unrun; they are not experiments until they have a run row.
- **Evidence:** measured availability, cost and latency above. No quality data on
  this corpus for any of them — that is what the experiments are for.
- **Amended 2026-09-23, by Krutik in chat ("run the other two rerankers").** After
  EXP-0024 came back null, Claude flagged that one reranker cannot separate "a
  cross-encoder does not help here" from "this one does not"; Krutik then approved
  both remaining models. EXP-0025 (`cohere/rerank-4-fast`) ran and **beat EXP-0024 at
  p = 0.039 while itself being null against the control**, which settles that the
  narrowness was a real cost and not a hypothetical one (OQ-035). EXP-0026
  (`qwen/qwen3-reranker-8b`) VOIDed on HTTP 402 — the account ran out of credit
  (MIS-031) — and ran on 2026-09-24 once credited: **Δ exactly 0.000, p = 1.000**,
  and behaving unlike either Cohere model (worst at rank 1, best at depth). All three
  approved rerankers are measured, all three are null, and **the decision to widen
  from one model to three is vindicated by the result**: the axis's null now rests on
  three distinct behaviours rather than one. Axis 5 has used **3** of its 5
  experiment slots and closes with no winner.
- **Consequences:** room remains for the two k -> n ratio runs P2-10 asks for
  (20 -> 5 and a wider setting), which OQ-038 now makes the most informative runs
  left in the axis, plus the owed open-weight reranker. `dev_large` is bought
  only for a winner (DEC-058 rule 4, OQ-033).
- **Revisit if:** OpenRouter starts serving a rerank model with a materially
  different mechanism (a multi-vector or late-interaction endpoint — see the ColBERT
  note in HYPOTHESES.md), or a chosen reranker's provider pin changes.

## DEC-060 — P2-10 closes at 3 of 5 experiments; the ratio runs and the LLM reranker are cut
- **Date:** 2026-09-24
- **Decided by:** Krutik ("i want to skip them")
- **Status:** Active
- **Context:** P2-10 specifies five experiments: three rerankers at a fixed 50 -> 5
  ratio, plus two retrieve-k -> rerank-to-n ratios on the best of them. The three
  rerankers ran (EXP-0024/0025/0026) and all three were null on the deciding metric.
  The two ratio runs and the LLM-as-reranker were offered with estimates and declined.
- **Options considered:**
  1. Run the two k -> n ratio runs (~$1.10) — they test the one live reading of the
     axis's central measurement, that a reranker handed 50 candidates might do better
     handed 20 (OQ-038). Declined.
  2. Run the LLM-as-reranker (~$0.22) — a different mechanism from a cross-encoder,
     and the only thing that would exercise the `rerank_llm` prompt and its output
     parser on stored model output. Declined.
  3. Close the axis at three experiments — chosen.
- **Decision:** P2-10 closes with **3 of 5 experiments** and **3 of 4 acceptance
  criteria** met. Met: document-level k and n (P1-03); collapse ratio re-measured
  post-rerank on every run; latency and per-query cost reported per reranker. **Not
  met:** "LLM-as-reranker runs are marked `pipeline_nondeterministic` and cache-backed
  per P2-03" — no such run exists, so that path is built and untested.
- **Evidence:** measured — three null results (Δ −0.055 p=0.139, +0.010 p=0.887,
  +0.000 p=1.000) and a measured ceiling of 0.985 the axis did not approach. The
  judgment that three nulls across three distinct behaviours is enough to close is
  Krutik's.
- **Consequences:**
  - **Code exists that no experiment has exercised.** `rag/reranking/llm.py`, the
    `rerank_llm@v1` prompt and `parse_ranking` are tested against hand-built
    adversarial inputs but **never against stored model output**, which preflight 21
    requires before trusting any parser of model output. The test that would do it
    (`test_parse_ranking_on_stored_model_output`) skips for want of a run and will
    keep skipping. This is recorded rather than removed: the alternative is deleting
    working code to make a gap invisible.
  - OQ-038 (does a narrower or wider candidate set close the 25-point ranking gap?)
    stays open and unqueued rather than answered.
  - Axis 5's null is a statement about **50 -> 5 with three cross-encoders**, and must
    be written that way in NARRATIVE.md — not as "reranking does not help here".
- **Revisit if:** P2-11's revisit pass or P2-16's combinations need a reranker arm, or
  if the assembly axis (P2-13) shows that context depth is the binding constraint — in
  which case the k -> n ratio question returns with a reason attached.

## DEC-061 — Axis 6 (assembly) runs before P2-11 and P2-12, and its top-k sweep is read, not run
- **Date:** 2026-09-24
- **Decided by:** Krutik (ordering); Claude (the reconstruction, flagged here)
- **Status:** Active
- **Context:** The Phase 2 handover's run order is P2-10 -> P2-11 (chunking revisit
  under the winning reranker) -> P2-12 (query transformation) -> P2-13 (assembly).
  P2-10 closed with no winner (DEC-060), and Axis 5 measured a ceiling that reframes
  what is worth doing next: the gold document is in the 50-document candidate set for
  **98.5%** of questions and reaches the generator for **72%** (MIS-029, F16).
- **Options considered:**
  1. Follow the handover order: P2-11 next, ~$0.90 for 2 runs (the control arm already
     exists as EXP-0025 and the Axis 1 indexes are still cached). Rejected: P2-11 asks
     whether chunking differences collapse under a reranker, and the best reranker
     moved the metric by +0.010 at p = 0.887, so the composition question is close to
     arithmetically settled before it is run.
  2. P2-12 (query transformation) next — also targets multi-document questions, but
     every configuration costs an LLM call per query.
  3. **P2-13 (assembly) next — chosen.** It contains the one untested lever that acts
     directly on the measured gap (`top_k`), and MMR, the technique aimed squarely at
     multi-document coverage, which is 20% of the questions and 46% of the failures.
- **Decision:** run Axis 6 next. P2-11 and P2-12 keep their place in the queue behind
  it and are not cancelled.
- **Second decision, and it is Claude's:** P2-13's "top-k sweep" experiment is
  **satisfied at Tier 1 by re-reading a recorded run, not by a new run.** `top_k`
  cannot change a retrieval metric — the metrics score the document ranking and
  `top_k` only sets how far the context walk goes down it — which is shown directly
  by `run_20260913_222423_db8c` (control at `top_k=10`) scoring identically to
  `run_20260912_224833_75b2` (`top_k=5`) at every depth. The sweep is therefore
  reconstructed exactly from the control's stored per-question rankings through the
  runner's own `select_distinct_docs`, and recorded in EXPERIMENTS.md under a heading
  that says no run was made. Spending an experiment slot to re-measure numbers already
  in the store would be theatre.
- **Evidence:** measured — the two top_k runs above; the reconstructed sweep; the
  0.985 ceiling from EXP-0005's stored rankings.
- **Consequences:**
  - Axis 6 spends **4** of its 5 experiment slots on runs (MMR, contextual
    compression, lost-in-the-middle, contextual retrieval), not 5.
  - The sweep exposed an interaction that constrains every later assembly experiment:
    **`context_max_tokens` (6,000) binds at about `top_k=14`**, so recall gained above
    that k cannot reach the generator without also raising the cap — a two-field
    change, therefore not a one-dimension diff (P2-05). Any such run must be declared
    as changing two fields, with the reason.
  - The Tier 2 question the sweep cannot answer — does a larger context produce better
    *answers*? — becomes OQ-040 and needs its own approval.
- **Revisit if:** a later axis changes the document ranking enough that the control's
  reconstructed curve no longer describes the promoted configuration; the sweep is
  then re-read from the new promoted run, still without a dedicated run.

## DEC-062 — MMR occupies the reranker slot, and Axis 6 will exceed the 5-experiment cap
- **Date:** 2026-09-24
- **Decided by:** Claude (Krutik not in the loop; flagged in chat)
- **Status:** Active
- **Context:** MMR is Axis 6's prioritised technique (P2-13). Mechanically it is a
  reranker — it re-orders a candidate set and adds nothing — but the question it
  answers is about what the context should contain, not about scoring quality.
- **Options considered:**
  1. Give MMR its own config dimension (`assembly_reorder` or similar) — rejected: it
     would duplicate the P2-10 machinery (document-level candidates, splicing,
     re-pooling, the recomputed collapse ratio, `check_same_chunks`) for no gain, and
     a second code path that must stay in step with the first is how they drift apart.
  2. **Put MMR in the `reranker` slot with `axis: assembly`** — chosen.
- **Decision:** MMR is registered as a reranker. A run carries `axis: assembly` while
  its config diff reports the `reranking` dimension. Both are true and neither is a
  bug: `axis` records which story owns the run, `dimensions` records which config
  fields moved. The one-dimension check (P2-05) still passes.
- **A guard that came with it.** MMR combines the retriever's relevance score with a
  vector similarity and treats both as cosines. That holds for a dense retriever —
  its score *is* the query-chunk cosine and the index rows are L2-normalized — and
  fails for BM25, whose Okapi scores are unbounded and share no space with any
  vector, which would make `lambda` a dial calibrated to nothing.
  `Retriever.chunk_vectors` returns None for retrievers without a vector space and
  MMR **refuses to run** rather than silently degrading to relevance-only ordering.
  Tested.
- **Evidence:** No measured data; a design judgment. MMR's effect on this corpus is
  EXP-0027 and is not predicted here.
- **Consequences:**
  - **Axis 6 will exceed the P2-06 cap of 5 experiments per axis.** The λ sweep P2-13
    asks for is four configurations, and the axis still has contextual compression,
    lost-in-the-middle and contextual retrieval to run. The runner will warn from the
    fifth distinct config hash on, and the warning is correct. The λ sweep is counted
    as **one experiment reported as a curve** — the same treatment the top-k sweep
    gets (DEC-061) and that Axis 3's α sweep did not — because it is free: no network
    call, no index, $0.0001 of query embeddings per run. **The cap exists to bound
    spend and scope, and a free sweep bounds itself.** If Krutik disagrees, the fix is
    to report fewer λ values, not to hide the count.
  - MMR is the first technique in this project that costs nothing per query and still
    changes the ranking, so it is also the cheapest thing left that could move the
    multi-document slice.
- **Revisit if:** a later axis needs a reorderer that is genuinely not a reranker
  (lost-in-the-middle reorders the *assembled context* without changing which
  documents are in it, and so does NOT belong in this slot — it changes no retrieval
  metric by construction and is Tier 2 only).

## DEC-063 — Run the two Tier 2 assembly experiments without the judge
- **Date:** 2026-09-24
- **Decided by:** Krutik (proposed by Claude)
- **Status:** Active
- **Context:** EXP-0028 (lost-in-the-middle reordering) and EXP-0029 (contextual
  compression) are Tier 2 by necessity — they change only what the generator sees, so
  no retrieval metric can move and there is nothing for Tier 1 to measure. The
  `--estimate-only` output put each run at **$0.9102**, of which **$0.8760 was the
  judge** and $0.0341 the generator. The judge is still the placeholder of DEC-018,
  whose scores "must not reach EXPERIMENTS.md or NARRATIVE.md."
- **The problem stated plainly:** 96% of the cost of each run buys three numbers
  (faithfulness, answer relevance, answer correctness) that the documentation contract
  forbids reporting, that will be superseded the moment a real judge is chosen, and
  that would require re-running both experiments at that point anyway. The metrics
  that actually decide this axis — citation precision and recall, refusal rate, URL
  count, step coverage, and for EXP-0029 the word-reduction ratio — are deterministic,
  label-based and free.
- **Options considered:**
  1. Pay it. $1.82 for the pair, and the judged scores sit in the results store
     alongside EXP-0006's three runs with a valid `dense-control-v1` MDD. Rejected:
     comparability with numbers nobody may quote is not worth 96% of a run.
  2. **Skip the judge on these two runs — chosen.** $0.0341 each instead of $0.9102,
     a 27x reduction, with every reportable metric unchanged.
  3. Choose a real judge now and end the placeholder problem. Rejected *for this
     story*, not on the merits: it is a separate model decision with unmeasured bias
     tradeoffs (OQ-014), and it starts a new comparison family that strands every
     judged number recorded so far. It should be its own decision, not a side effect
     of an assembly experiment.
- **Decision:** `RunConfig.skip_judge` — an **affirmative flag**, not an empty
  `judge_model`. Setting the tier to 2 with no judge model and no flag still fails, so
  a typo cannot silently turn a $0.91 run into a $0.03 one that looks judged in the
  ledger; setting both the flag and a judge model is also refused, because guessing
  which was intended would decide the run's cost. When set, all three judged criteria
  are recorded per question as `None` (never zero — preflight 6) and the run row
  carries `skip_judge`, `skipped_criteria` and a `judge_skipped_by_config` count.
- **Evidence:** the two `--estimate-only` outputs above ($0.9102 vs $0.0341,
  pricing 2026-09-16). No quality claim is made or implied by this entry.
- **Consequences:**
  - EXP-0028 and EXP-0029 produce **no** faithfulness, answer-relevance or
    answer-correctness values at all. Their rows show those criteria as skipped rather
    than empty, so the gap is visibly deliberate.
  - They are **not comparable to EXP-0006 on judged metrics** — there is nothing to
    compare. They remain fully comparable on every deterministic metric, which is what
    P2-13 asks these two experiments to decide.
  - A latent bug was found and fixed while implementing this: `estimate_tier2_cost`
    returned no `judge_usd` when there was no judge price to look up, and
    `estimate_run_cost` correctly reads a *missing* price as "unavailable" and halts at
    the gate (MIS-025). Zero judge tokens is a cost of exactly zero at any price, so
    that case is now stated explicitly rather than falling through the
    price-unavailable path. An absent price is not free; an absent **call** is.
- **Revisit if:** a real judge is chosen (P1-11 / OQ-014). At that point these two
  experiments are re-run under it if a judged number is wanted for them, and this entry
  is what says why they lack one.

## DEC-064 — `openai/gpt-oss-20b` writes the chunk prefixes and does the compression
- **Date:** 2026-09-24
- **Decided by:** Krutik (proposed by Claude, after a probe Krutik asked for)
- **Status:** Active
- **Context:** P2-13's two remaining LLM-using techniques need a model in a role
  nothing in this project had filled: contextual retrieval writes one situating
  statement per chunk (8,218 calls, and the output is **indexed**), and contextual
  compression trims each retrieved chunk per question (500 calls at Tier 2 on `dev`).
- **Why the choice was not obvious:** the failure mode lands inside the index. If the
  model prepends "Here is the statement:", that text is embedded in front of 8,218
  chunks and there is no cheap way to find it afterwards. Before the probe, this repo
  had measured instruction-following evidence for exactly two models — `gpt-5-nano`
  (obeys `[doc:<id>]` 96–98.5% of the time) and `gpt-oss-120b` as judge — so every
  cheaper candidate was an assumption.
- **Options considered:** priced live off `/api/v1/models` on 2026-09-24 against the
  counted workload (10,616,375 tokens in), then the top three probed with **10 real
  calls each on real corpus articles**, six of them chunks of multi-chunk articles:
  1. **`openai/gpt-oss-20b` ($0.018/$0.090) — chosen.** 0/10 flagged. Output names the
     product *and* what the chunk covers, in 22–47 words: *"This Wix Bookings article
     explains payment options in the Wix app, and the chunk details manual card entry,
     tap-to-pay, gift card, and split payment methods."* Measured 66.3 output tokens
     per call. A different model family from the generator (`openai-oss`, not
     `openai`), which costs nothing here and removes a question.
  2. `openai/gpt-5-nano` ($0.050/$0.400). 0/10 flagged and equally usable, but padded
     — *"It pertains to…", "It sits inside the article about…"* — carrying the same
     information in 39–59 words at 79 output tokens per call. **$0.790 against
     $0.240** for the same experiment. Rejected on price for no measured benefit.
  3. `mistralai/mistral-nemo` ($0.019/$0.030), the cheapest with a usable context.
     Rejected on the probe: it wrote **titles, not situating statements**
     (*"Wix Groups: Monetization via Pricing Plans"*, 6–14 words), and **2 of 10 came
     wrapped in quote marks**, which would have been embedded verbatim. It is a
     different technique at a $0.02 saving.
- **Decision:** `openai/gpt-oss-20b` for both roles, unpinned (model-level price).
  Provider is **not** pinned here, unlike the judge (DEC-032): the prefixes are cached
  in the generation cache and the index is keyed on the chunker id, so a provider
  change cannot silently move a recorded number — it can only cause a cache miss,
  which is visible as a hit rate below 100% on the row.
- **Evidence:** the 30-call probe above, ~$0.002, output read by hand. Prices from
  `/api/v1/models` on 2026-09-24. **No quality prediction is made:** the probe tested
  whether the model obeys the prompt's format, not whether prefixing helps retrieval.
  That is EXP-0030 and is pre-registered as H-022.
- **Consequences:**
  - `openai/gpt-oss-20b` is added to `configs/pricing.yaml` by hand and its numbers
    fetched by `rag pricing refresh`, per that file's rule (the model list is curated,
    the numbers never are).
  - Its non-ASCII punctuation (`tap‑to‑pay` with U+2011, curly quotes) goes into the
    indexed text. Harmless for embedding, recorded because a curly apostrophe has
    already cost this project 13–18 hidden refusals once (DEC-045).
  - EXP-0030's total drops to ~$0.28 and Axis 6's three remaining runs to ~$0.37.
- **Revisit if:** the recorded prefixes show preamble, truncation or non-English text
  at a rate above ~1% when EXP-0030's `chunker_meta` is reviewed; or if a later axis
  needs a longer prefix than 60 words, which is a new workload and a new estimate.

## DEC-065 — `openai/gpt-oss-20b` also writes Axis 4's query transforms
- **Date:** 2026-09-25
- **Decided by:** Krutik (proposed by Claude)
- **Status:** Active. Extends DEC-064 rather than superseding it.
- **Context:** P2-12's four techniques each send the question to a model and retrieve
  for what comes back. DEC-064 chose `gpt-oss-20b` for the *in-pipeline prefix writer
  and compressor*; query transformation is a third role and a fourth, fifth, sixth and
  seventh prompt, so it is not covered by that entry.
- **Why it needed its own probe rather than an inheritance:** MIS-034 is exactly this
  mistake. The same model on the same settings used 54 output tokens per call on the
  chunk-prefix prompt and 32,848 on one compression call. A model is licensed for a
  **(model, prompt) pair**, never for a model.
- **Evidence:** all four prompts probed on **6 real dev questions** (3 multi-gold, 3
  single-gold) before any config was committed: **zero fallbacks, zero format
  failures**, 46–105 output tokens per call, no reasoning blow-ups. Decomposition
  produced a mean of 1.33 sub-questions; HyDE produced corpus-shaped passages; the
  multi-query rewrites were faithful; step-back produced one question each time.
- **Decision:** `openai/gpt-oss-20b`, unpinned, `max_tokens=600`, for all four Axis 4
  transforms. Same reasoning as DEC-064 on the provider: the completions are cached and
  a provider change can only cause a visible cache miss, never a silent number change.
- **Recorded against it, from the same probe:** on **2 of 6** questions the step-back
  prompt produced a question naming **"Wix Bookings"** when the original named no
  product. That is a defect of the (prompt, corpus) pair, not a reason to reject the
  model, and it is pre-registered as H-026 rather than fixed by tuning the prompt —
  P2-12 allows one configuration per technique and no prompt tuning within it.
- **Consequences:** Axis 4 costs **$0.0084** for all four runs, the cheapest axis in the
  phase. Every run is `pipeline_nondeterministic` and cache-backed (P2-03).
- **Revisit if:** the fallback rate on a full 200-question run exceeds ~2%, or the
  step-back product-hallucination rate proves high enough to make EXP-0034 a test of the
  prompt rather than of the technique.

## DEC-066 — P2-11 is priced and not bought; the composition question is unanswerable as posed
- **Date:** 2026-09-25
- **Decided by:** Krutik (proposed by Claude, with the estimate and the arithmetic)
- **Status:** Active
- **Context:** P2-11 asks for the **top 3 chunking configurations re-run under the
  winning reranker from P2-10**, to test whether a strong reranker erases chunking
  differences. Its premise does not survive contact with Axis 5's result.
- **The premise failed before the runs:** **P2-10 closed with no winner** (DEC-060).
  Three cross-encoders were measured on `dev` and the best of them, `cohere/rerank-4-fast`,
  moved strict recall@5 from 0.7200 to **0.7300 — Δ +0.010, 95% CI [−0.055, +0.080],
  p = 0.887** (EXP-0025). The revisit asks whether chunking differences *survive* a strong
  reranker. A reranker that moves the metric by one point at p = 0.887 is not a strong
  reranker on this corpus, so the question becomes "do chunking differences survive an
  intervention that does nothing", whose answer is arithmetic rather than empirical.
- **What was priced:** three runs — parent-document, semantic and structure-aware
  chunking, the top 3 by multi-document strict recall@5 — each with `cohere/rerank-4-fast`
  at 50 candidate documents. Indexes for all three are already on disk, so nothing is
  re-embedded. **`--estimate-only`: $0.4681 each, $1.4043 for the three**, gate $2.00.
  Configs are committed unrun as `configs/exp_0035..0037_*.yaml`.
  A caveat that would have needed watching: the rerank estimator's search-unit
  calibration was measured on `fixed_token`'s 309-word chunks (MIS-028), and these
  chunkers cut very differently — parent-document is 18,884 chunks at 124 words. The
  estimate is stable across them because 50 candidate *documents* is roughly 50
  documents' worth of text however it is cut, but that is reasoning, not measurement, and
  the plan was to check run 1's actual before launching runs 2 and 3.
- **Options considered:**
  1. Run all three with `cohere/rerank-4-fast` ($1.40). Rejected: buys a composition
     test whose stronger arm is a measured null.
  2. Run with `qwen/qwen3-reranker-8b` instead ($1.21/run, ~$3.63 plus a fourth run for
     the control arm), on the argument that its depth behaviour — recall@20 0.950, the
     highest in the project — is the property that would erase chunking differences.
     Rejected on the same ground at 2.6x the price: its recall@5 is 0.720, *exactly* the
     control's.
  3. Run with `cohere/rerank-v3.5` ($0.70). Rejected: at recall@5 0.665 it is below the
     control, and calling it "the winning reranker" in a writeup would be false.
  4. **Price it, decline it, and record the verdict — chosen.** P2-17 explicitly provides
     for "any axis that was priced, gated at $2, and deliberately not run, with its
     estimate attached."
- **The composition verdict P2-11 asks for, stated explicitly: neither. The winners did
  not compose, partially compose, or cancel, because there were no winners to compose.**
  Axis 1 produced no chunker that beat the control and Axis 5 produced no reranker that
  did. Composition is a question about two positive results and this phase has none.
  That is the finding, and it is a real one — it says the most common error in this kind
  of programme (assuming one-factor winners stack) could not be committed here for want
  of any one-factor winner.
- **The story's last criterion is already satisfied, and was before it was asked.**
  P2-11 says that if chunking differences collapse, `promoted.yaml` reverts to the
  **simplest** chunking strategy statistically indistinguishable from the best. The
  simplest strategy — `fixed_token` 600/100 — **is** the best: every alternative is at or
  below it, and two are significantly below (sentence-window −0.190 at p = 0.0001,
  structure-aware −0.055 at p = 0.0325). `promoted.yaml` already names it. No revert is
  needed because nothing ever displaced it.
- **Evidence:** measured, all from the results store — the four Axis 1 `dev` runs, the
  three Axis 5 `dev` runs, EXP-0025's paired test, and the three `--estimate-only`
  outputs. No outcome is predicted for the unrun configs.
- **Consequences:**
  - **Phase 2 definition-of-done item 9 — "the chunking revisit pass (P2-11) has been run
    and its composition verdict recorded" — is NOT fully met.** The verdict is recorded;
    the pass was not run. That gap is stated here rather than papered over by calling a
    declined run a completed one.
  - If a later axis produces a reranker or a chunker that actually beats the control, this
    decision should be revisited: the configs are committed and cost $1.40 to execute.
- **Revisit if:** any technique in Phase 2 achieves a significant positive result on
  `dev` strict recall@5, which would give composition something to test.

## DEC-067 — `openai/gpt-oss-20b` runs the groundedness self-check
- **Date:** 2026-09-25
- **Decided by:** Krutik (proposed by Claude)
- **Status:** Active. Third role for this model, after DEC-064 (chunk prefixes,
  compression) and DEC-065 (query transforms).
- **Evidence:** the (model, prompt) pair probed on **10 real stored answers** with their
  real contexts before any config was committed (preflight 42): 4 refusals correctly
  short-circuited without a call, 6 checked, 1 rejected, **zero unparseable, zero
  failures**, and **4,600 ms per answered question** — the latency number P2-14 requires.
  > **CORRECTED by DEC-073 on 2026-09-28** — `gpt-oss-20b` is family `openai`, so this
  > check was same-lab, not cross-family. EXP-0041 carries the caveat.
- **Why it is the right family for this job:** the check grades `gpt-5-nano`'s output,
  so `gpt-oss-20b` makes it a **cross-family** check. P0-07 refuses same-family judging
  for the Ragas judge on self-preference grounds; the same argument applies to a model
  asked whether an answer is grounded. Using the generator's own model here would have
  been the cheaper-looking option and the wrong one.
- **Recorded against it, from the same probe:** one `unanswerable` question that the
  generator had **answered** was judged **SUPPORTED** by the check. That is the failure
  mode this technique is supposed to catch, missed on a 10-answer sample. It is
  pre-registered as H-029 rather than treated as a reason to change the prompt —
  P2-14 allows one configuration per technique.
- **Consequences:** ~$0.0055 per 100 dev questions and 4.6 s per answered question, both
  now in the cost estimator (`estimate_grounding_cost`, calibrated on this probe) so the
  gate sees them. Runs carrying it are `pipeline_nondeterministic` and cache-backed.
- **Revisit if:** the rejection rate on the full split is near zero (the check is doing
  nothing for its latency) or very high (it is rejecting good answers, and its
  false-refusal contribution is the thing to look at).

## DEC-068 — The abstention operating point is a retrieval-score threshold of 0.575
- **Date:** 2026-09-25
- **Decided by:** Krutik (proposed by Claude, from the EXP-0038 curve)
- **Status:** Active
- **Context:** P2-14 requires an operating point chosen **from the trade-off curve**, with
  the reasoning about which error is worse for an enterprise support assistant recorded
  alongside it. The curve is EXP-0038, reconstructed from two existing runs for $0.
- **Which error is worse, and why.** For an assistant whose job is pointing a user at the
  right help article, a **false answer is worse than a false refusal**, and not
  symmetrically. A false refusal routes the user to a human agent: it costs money and
  some goodwill, and the user still gets a correct answer. A false answer sends someone
  to change a setting on a live site on the strength of a confident, cited paragraph that
  is wrong — and because this system cites its sources, a wrong answer arrives wearing
  the appearance of evidence. The asymmetry is not just in the outcome but in
  *recoverability*: a refused user knows they have not been helped, an over-answered one
  does not.
- **What that implies, and where it stops.** It implies buying false-answer reductions
  wherever they are cheap — but "worse" is not "worth any price". At T = 0.625 the false
  answer rate quarters, and **15% of dev questions stop being answered at all**. An
  assistant that declines one question in six is not an assistant; the support queue
  absorbs the difference, and the user-visible failure just moves.
- **Decision: T = 0.575.** Abstain before generating when the top-1 retrieval score is
  below 0.575.

  | | control | T = 0.575 |
  |---|---|---|
  | False-answer rate (`unanswerable`) | 0.2667 | **0.1333** |
  | False-refusal rate (`dev`) | 0.0299 | **0.0299** |
  | Dev questions answered | 0.930 | **0.930** |

  **It halves the false-answer rate and costs nothing measurable** — no false refusals, no
  dev questions lost, no LLM call, no added latency. Every unanswerable question it newly
  declines scored below every answerable question's top-1, so nothing was traded. It is
  chosen not because 0.1333 is a good number but because it is the last point on the curve
  that is **free**, and the reasoning above only justifies paying past that point if the
  payment is small. It is not: the next halving costs a **3.5x rise in false refusals**.
- **Evidence:** EXP-0038, `run_20260913_205058_dc03` and `run_20260913_060733_6a9b`,
  recounted under `refusal-lexical-v3`. **No quality prediction** is made for any
  configuration not in that table.
- **Consequences and the caveat that limits this entry.**
  - **The threshold is selected on the same data it is evaluated on.** Tuning on `dev` is
    permitted and declared, but `unanswerable` is being used here to *choose* the point
    and to *report* its performance, so **0.1333 is optimistic**. This entry is a chosen
    operating point, not a measured production number.
  - **`promoted.yaml` is not changed by this decision.** The threshold is not implemented
    in the pipeline — EXP-0038 evaluated it by reconstruction, not by running it — so
    promoting it would record a configuration that has never executed. Implementing and
    running it is the follow-up, tracked as OQ-046.
  - It must be re-read on the held-out split in P2-18 before it is trusted. If the
    dev-to-test gap is large on this curve, the operating point moves with it.
- **Revisit if:** the retriever or the embedding model changes — the threshold is a raw
  cosine score and has no meaning across a change of either; or P2-18 shows the curve
  does not hold out of sample.

## DEC-069 — Phase 2 closes with `promoted.yaml` unchanged, and the test split confirms it
- **Date:** 2026-09-26
- **Decided by:** Krutik (opening approved); Claude (the reading of the result)
- **Status:** Active
- **Context:** P2-18 opened `test` once, at the end of Phase 2, and measured the
  dev-to-test gap for both Phase 1 controls at Tier 1 and Tier 2. The Phase 1 dense
  control and `promoted.yaml` are the same configuration (`identity_hash`
  70610a6119fb9223) because no technique in six axes earned promotion.
- **The result.** Strict recall@5: dense **0.7200 → 0.6800** (gap −0.0400, 95% CI
  [−0.130, +0.050]); sparse **0.4100 → 0.3450** (gap −0.0650, CI [−0.160, +0.030]).
  **Every gap measured, on every headline metric and both slices, is within the sampling
  noise of two independent 200-question samples.** `strict recall@20` and Tier 2
  `gold_in_context` and `refusal_rate` came back **numerically identical** across the
  two splits.
- **The finding that survives.** Dense over sparse — the one real result of Phase 1 —
  is **+0.3100 on dev and +0.3350 on test**, with a test CI of [+0.243, +0.427]. It is
  the only thing in this project that was ever significant, and it holds out of sample.
- **Decision: `promoted.yaml` is unchanged and Phase 2 is closed.** Nothing has been
  modified in response to these numbers and nothing will be. The split is not burned.
- **Evidence:** EXP-0046–0050, all VALID, openings log rows 1–4.
- **Consequences:**
  - The project's headline number is now **strict recall@5 = 0.68 on 200 unseen
    questions**, not 0.72 on the set it was developed against.
  - Every Phase 2 comparison was made against a baseline that transfers, so the 45
    "no measurable difference" verdicts are not artefacts of a lucky control.
  - **`test` is spent.** Any future phase needs a new held-out split, and comparisons
    across that boundary are invalid.
- **Revisit if:** never, for this split. A Phase 3 would freeze a new one.

## DEC-070 — P3-01: the Phase 2 dev and test runs were independent; Phase 3 may baseline on them
- **Date:** 2026-09-27
- **Decided by:** Claude (the audit and its reading). Krutik has not yet reviewed it.
- **Status:** Active
- **Context:** Phase 3 fact 5: Tier 2 `gold_in_context` (0.67) and refusal rate (0.08)
  came back identical on `dev` and `test`, while Tier 1 strict recall@5 differed
  (0.72 vs 0.68). Identical numbers from two splits look like a cache serving one
  split's outputs to the other. P3-01 requires that to be ruled in or out before
  anything is baselined.
- **Runs audited** (the P2-18 comparison pairs, EXP-0046/0047):
  - Tier 2 dev `run_20260913_205058_dc03` (EXP-0006 replicate, subsample `sub100:b551f7f49c91`)
    vs Tier 2 test `run_20260926_011244_9d0e` (`sub100:9f0dee4cacd0`).
  - Tier 1 dev `run_20260912_225005_be04` (0.72, the value quoted in EXP-0046) vs
    Tier 1 test `run_20260926_010435_6495`.
- **Command:** `rag audit provenance run_20260913_205058_dc03 run_20260926_011244_9d0e
  --dev-tier1 run_20260912_225005_be04 --test-tier1 run_20260926_010435_6495`. Reads the
  results store and the generation cache; zero model calls.
- **What was found:**

  | Check | dev | test |
  |---|---|---|
  | Question ids in the run | 100 | 100 — **0 shared** |
  | Full splits (200 each) | — | **0 shared ids, 0 identical question texts** |
  | Index (passage vectors) | cache hit, key `f0e720da2aa33751` | same key, cache hit — corpus-level and split-blind by design, not a leak |
  | Query embeddings | 100 fresh calls, 3,889 tokens | 100 fresh calls, 3,735 tokens — no query cache exists |
  | In-pipeline LLM cache | no LLM call in this config | same; 0 hits |
  | Answer generation | 100 fresh calls | 100 fresh calls — the generator has no cache, and the cache DB holds **0 rows** for `baseline_answer@v1` |
  | Judge | ran (`gpt-oss-120b`, Cerebras/Groq), no cache | **skipped** (DEC-063) — no judge output exists to leak |
  | Test answers identical to any dev answer | — | **0** |

  **No leak. No test output was served from anything a dev run created.**
- **Why the numbers were identical — explained, and it is one coincidence, not two:**
  1. `gold_in_context` equals strict recall@5 on **every** question of both runs (0
     disagreements of 100 each). At `top_k=5` distinct documents they are the same
     quantity, so "gold_in_context identical while recall@5 differed" is really
     "recall@5 on the subsample identical while recall@5 on the full split differed".
  2. Tier 2 runs on a **100-question subsample**; Tier 1 on all 200. Recall@5 on the
     subsamples was 67/100 on dev and 67/100 on test. The Tier 1 gap lives in the
     *other* 100 questions: dev's scored **0.78**, test's **0.69**.
     Check: (66 + 78) / 200 = 0.72; (67 + 69) / 200 = 0.68.
  3. The dev Tier 1 run scored 66/100 on the subsample and the Tier 2 run 67/100: one
     question (`47ed1fdd553ce70f`) flipped 0 → 1 between them. That is query-embedding
     non-determinism (OQ-023), not a leak — the two runs embedded the question
     separately, twelve hours apart.
  4. Refusals (recounted under `refusal-lexical-v3`): 8/100 on each side, on disjoint
     question sets. A separate coincidence of counts, not of outcomes.
- **Per-question agreement:** not computable — the two runs share no question id. **The
  identical aggregates come from entirely different per-question outcomes**, which is
  what P3-01 asked to have stated explicitly.
- **Decision:** the Phase 2 closing numbers are independent measurements and Phase 3
  may baseline on them. No cache keying change is needed; no `MISTAKES.md` entry.
- **Evidence:** the audit output above, from the four run ids named.
- **Consequences:**
  - `rag audit provenance` exists and is tested (`tests/test_audit_p3_01.py`): a shared
    question id, a copied answer, or a cache row that could serve the answer prompt
    each set `leak_found`.
  - A limitation this audit does not remove: the answer path being uncached is what
    made it clean. P3-05's judge cache and P3-10's CI cache will be the first caches
    on that path, and both key on question id, so dev/test separation depends on the
    two splits never sharing an id — true today (0 of 200).
- **Revisit if:** any cache is added to the answer or judge path (re-run this audit on
  the first run that uses it), or a new held-out split is built.

## DEC-071 — P3-02: Phase 2 carry-overs resolved, and the Phase 3 baseline frozen at `phase3-baseline`
- **Date:** 2026-09-27
- **Decided by:** Claude. The story fixes the shape of this (resolve carry-overs, tag,
  record slugs); the disposition of the one unrun carry-over — moving it rather than
  buying it — is my call, made without Krutik in the loop, and is flagged to him in chat.
- **Status:** Active
- **Context:** P3-02 needs one fixed reference point for every later CI comparison, and
  the Phase 3 non-goals say Phase 2 carry-overs either finish before the freeze or go to
  `OPEN_QUESTIONS.md` — never after.
- **Carry-overs:**
  1. **The `top_k=10` run** — *run and recorded.* EXP-0051 (`run_20260927_235029_2216`)
     answered OQ-040: `gold_in_context` +0.150, citation precision −0.0851 against an MDD
     of 0.080. Not promoted.
  > **Carry-over 2 reversed by DEC-072 on 2026-09-27** (Krutik asked for OQ-038 to be run;
  > answered by EXP-0052/0053). The freeze itself stands: nothing was promoted.
  2. **The reranker headroom diagnostic on the recall@5 → recall@20 gap** — *not run;
     stays in `OPEN_QUESTIONS.md` as OQ-038* (status note appended there). It is a paid
     run (roughly $0.20 + $0.90, OQ-038's own estimate) on an axis that returned "no
     measurable difference" at every depth (EXP-0024), and Phase 3 does not reopen
     retrieval axes. Buying it would need Krutik's go-ahead (DEC-053) and would not
     change what the gate protects.
  3. Other open Phase 2 questions (OQ-034, OQ-035, OQ-041–OQ-046) are not carry-overs of
     a named run; they stay open with their decision rules, unchanged.
- **Options considered for the freeze:**
  1. Freeze `promoted.yaml` alone — rejected: it is Tier 1 and names no generator, judge
     or prompt (OQ-042), so it cannot pin what Phase 3's answer-side gate compares.
  2. Freeze `promoted.yaml` **and** the Tier 2 control `configs/baseline_dense_tier2.yaml`,
     which is the same retrieval plus `baseline_answer@v1`, the generator and the judge —
     chosen.
- **Decision:** tag `phase3-baseline` on the commit that lands this entry. Recorded in
  `ci/phase3_baseline.yaml`:
  - `promoted.yaml`: file sha256 `229f22ec…50ee`, `config_hash` 7c99bc8e9a88e878,
    `identity_hash` 70610a6119fb9223.
  - Tier 2 control: `config_hash` 86cd401cbdac80c7; reference runs
    `run_20260913_205058_dc03` (dev) and `run_20260913_060733_6a9b` (unanswerable).
  - Prompt `baseline_answer@v1`, content hash `sha256:a5e9b4d9…61ac`.
  - Models, each verified on OpenRouter **2026-09-27** by `rag models verify`:
    embedder `qwen/qwen3-embedding-8b` pinned to DeepInfra; generator `openai/gpt-5-nano`
    (unpinned); judge `openai/gpt-oss-120b` with provider order [Cerebras, Groq]; judge
    embedder `qwen/qwen3-embedding-8b`.
  - Corpus hash, `norm-v1`, dev split hash, Ragas 0.4.3.
- **The judge slug is still the DEC-018 placeholder.** It is recorded because it is what
  the Tier 2 control runs. P3-04 is its validation; P3-04 allows one judge change, and
  that change would be a new version of the record and a new DEC entry, not an edit.
  Choosing the production judge is Krutik's call (CLAUDE.md section 10) and is open.
- **Startup check:** `rag/runner/model_check.py`. Before the first paid call of every run
  (after the free estimate and the cost gate, before the retriever is built), and at the
  start of `rag ask`, each configured slug is probed on `GET /models/<id>/endpoints`. A
  404 or a hard-pinned provider missing from the served list raises
  `ModelResolutionError` naming the slug; nothing has been spent. OpenRouter being
  unreachable is a separate `ModelCheckUnavailable` — an infrastructure failure, not a
  configuration one (P3-10 needs that distinction). The judge needs one provider of its
  order, because it is sent with fallbacks allowed.
- **Evidence:** EXP-0051 for carry-over 1; `rag models verify` output of 2026-09-27;
  hashes from `RunConfig`, `load_prompt` and `shasum -a 256`. No new measurement.
- **Consequences:**
  - `tests/test_model_check_p3_02.py` asserts the record matches the files it names. A
    change to `promoted.yaml`, the Tier 2 control or the answer prompt fails the suite
    until the record is re-versioned under a new DEC.
  - Every run now makes one free HTTP GET per distinct slug before it spends. A run with
    no hosted model (the toy smoke configs) makes none.
- **Revisit if:** P3-04 changes the judge; any slug stops resolving; or Krutik wants
  OQ-038 bought before the gate is built (the tag would then move, with a new entry).

## DEC-072 — OQ-038 is run before the Phase 3 gate, at 20 and 100 candidate documents
- **Date:** 2026-09-27
- **Decided by:** Krutik (to run it, reversing the carry-over disposition in DEC-071);
  Claude (the `retrieval_depth` change below, and the run shape).
- **Status:** Active
- **Context:** DEC-071 left OQ-038 — the reranker candidate-ratio diagnostic on the
  recall@5 → recall@20 gap — unrun. Krutik asked for it to be run first. The
  `phase3-baseline` tag was placed on b0b98b9 before that; it moves only if a result is
  promoted (neither run is a promotion candidate by default: OQ-038 is a diagnostic).
- **Run shape:** `configs/exp_0052_rerank_4fast_c20_dev.yaml` and
  `configs/exp_0053_rerank_4fast_c100_dev.yaml`: EXP-0025 (`cohere/rerank-4-fast` pinned
  to Cohere, 50 candidates) with `rerank_candidates` 20 and 100. `dev`, Tier 1. Decided by
  OQ-038's own rule: `rag compare` on strict recall@5 against promoted and EXP-0025,
  ≥ 0.03 separation between the ratios. Hypothesis H-036, written first.
- **`retrieval_depth` 150 on the 100-candidate run — a second changed field.** Depth is
  counted in chunks, candidates in distinct documents, and with ~1.2 chunks per document
  near the top 100 ranked chunks cannot hold 100 documents; left at 100, the run would be
  a ~80-candidate run labelled 100. Deeper retrieval only appends chunks below rank 100,
  so it cannot alter the dense ordering of the top-20 documents any metric reads.
  `rag promoted diff` reports it as a second dimension (`assembly`); the warning is
  expected.
- **Options considered:** (1) depth 100 and report the candidates actually reached —
  rejected, the run would not test the ratio it is named for; (2) depth 150 — chosen;
  (3) raise depth on both runs for symmetry — rejected, the 20-candidate run does not
  need it and it would change a field for no reason.
- **Cost:** estimates $0.1881 and $0.9361 (`--estimate-only`, pricing 2026-09-25); both
  under the $2 gate. Account balance $12.28. EXP-0025's measured cost was $0.448 against a
  $0.468 estimate.
- **Evidence:** No measured data for the decision itself; judgment call on run validity.
- **Revisit if:** the 100-candidate run's recorded candidate count per query falls short
  of 100 documents, which would mean 150 chunks was still too shallow.

## DEC-073 — Model family means the lab that trained the model; `gpt-oss` is `openai` (supersedes DEC-030)
- **Date:** 2026-09-28
- **Decided by:** Krutik. (Claude found the consequences below and implemented them.)
- **Status:** Active — **supersedes DEC-030's family ruling.** DEC-030's model choice was
  already a placeholder (DEC-018); what this reverses is its argument that open weights
  make `gpt-oss-*` a separate family.
- **Context:** P0-07 requires the judge to be from a different family than the generator,
  because a judge tends to favour outputs that look like its own. DEC-030 put
  `openai/gpt-oss-120b` in family `openai-oss`, separate from the generator
  `openai/gpt-5-nano`, on the argument that it is an open-weights model with its own
  training. That argument misplaced the source of the bias.
- **Decision:** family means the **lab that trained the model**, not how the weights are
  distributed. Self-preference comes from lineage — training data, post-training recipe,
  answer style — and both models are OpenAI's. So `gpt-oss-*` is family `openai`, and a
  `gpt-oss` judge of a `gpt-5-nano` generator is refused.
- **Options considered:**
  1. Keep DEC-030 and leave the residual risk to OQ-014's measurement — rejected: it keeps
     a judge whose independence rests on an argument that does not hold.
  2. Family = training lab — chosen.
  3. Change the generator instead — rejected: the generator is held constant across every
     Phase 1–2 comparison (DEC-017).
- **Implemented:**
  - `rag/eval/judge.py`: `_FAMILY_OVERRIDES` is empty; the OpenRouter namespace is the lab
    for every model this project has used. An override is now only for a model whose
    namespace is not its lineage (a third-party fine-tune) and needs its own DEC entry.
  - `rag/runner/config.py`: `historical_configs()`. A config rebuilt from a stored run row
    describes what already ran, so it is rebuilt without today's family rule. Without
    this, results-store lookups — which skip rows that fail to rebuild — would silently
    stop finding every Phase 0–2 judged run, including EXP-0006 (P3's reference run).
    `latest_run_of` keeps its `.with_()` copy inside the exemption too. Nothing that runs
    a config uses it.
  - `rag ask` loads its config with the judge fields cleared: it never judges, and the
    Tier 2 control's judge is now a refused pairing.
  - Tests: `gpt-oss` maps to `openai` and the pairing is refused; a stored run still
    rebuilds and is still found; the exemption does not leak out of its context.
- **Now refused (kept on disk unchanged, readable as history):**
  `configs/baseline_dense_tier2.yaml` (the frozen v1 Tier 2 control — left byte-identical
  because `ci/phase3_baseline.yaml` v1 pins its hash), `configs/baseline_dense_unanswerable.yaml`,
  `configs/exp_0001_baseline_tier2.yaml`, `configs/tier2_smoke.yaml` (the last three carry
  a header note). Their "Reproduce" commands no longer run as written.
- **What this does to Phase 1–2 results:**
  - **Retrieval findings: unaffected.** Every retrieval metric is deterministic and uses
    no judge — dense over sparse, the promotion record, the `top_k=5` decision, all 45
    "no measurable difference" verdicts, EXP-0052/0053.
  - **Deterministic generation metrics: unaffected** — citation precision/recall, refusal,
    step coverage and gold-in-context involve no judge.
  - **Judged scores:** never reached the ledger as findings (DEC-018). The **judged MDDs**
    in `EXPERIMENTS.md` (faithfulness 0.014, answer correctness 0.020, answer relevance
    0.021, and the per-slice table; DEC-037/046) were measured with a same-lab judge.
    They get a caveat, not a deletion. `rag/eval/noise_floor.py` labels a run with a new
    judge "no MDD measured" automatically, and P3-07 re-measures anyway.
  - **EXP-0041, the groundedness self-check**, used `openai/gpt-oss-20b` to grade
    `gpt-5-nano`'s answers — a judging role. DEC-067 justified it as cross-family on
    DEC-030's reasoning. Under this decision it was a same-lab check; EXP-0041 gets the
    caveat. `gpt-oss-20b`'s other Phase 2 roles (chunk prefixes, compression, query
    transforms) do not judge the generator, and the family rule does not apply to them.
  - **OQ-014** (does `gpt-oss` show self-preference?) is closed by this decision rather
    than by a measurement: the pairing is no longer used.
- **Next:** the P3-04 bake-off picks a cross-lab judge. Candidates, per Krutik:
  `deepseek/deepseek-v4.1-flash` (pinned to one host with structured outputs) and
  `google/gemini-3.8-flash`; `qwen/qwen3.8-flash` optional (slug verified 2026-09-28,
  $0.15/$0.47, Alibaba only, structured outputs yes). `gpt-oss-120b` and
  `openai/gpt-6-luna` are excluded. The winner goes into a new Tier 2 control and
  `ci/phase3_baseline.yaml` version 2 under tag `phase3-baseline-v2`; the existing
  `phase3-baseline` tag is not moved. After the bake-off, the Phase 2 judged runs are
  re-scored with the new judge from their stored answers, and whether any judged
  conclusion changes is recorded.
- **Evidence:** No measured data; a judgment about where self-preference comes from.
- **Revisit if:** a measurement shows cross-lab judges disagree with each other as much as
  a same-lab judge disagrees with them, which would say lineage is not the dominant term.

## DEC-074 — P3-03: golden slice v1 is 80 answerable + 15 unanswerable, seed 20260928
- **Date:** 2026-09-28
- **Decided by:** Claude — Krutik delegated the choice ("make your best choice").
- **Status:** Active
- **Context:** P3-03 leaves slice size (50–100 answerable, 10–15 unanswerable), stratum
  proportions and the `dev` overlap to the human.
- **Decision:**
  - **Answered-without-gold: all 27** from the Phase 2 closing dev Tier 2 run
    (`run_20260913_205058_dc03`). The risk group is the reason the faithfulness eval
    exists, and it is small, so it is taken whole rather than sampled.
  - **Multi-doc: 20** of the 24 not already in the first stratum.
  - **Single-doc: 33**, so the answerable total is 80.
  - **Unanswerable: 15**, 5 per reason — the top of the story's range, so each refusal
    type has more than a handful.
  - **Overlap with `dev` accepted.** Phase 3 runs no tuning experiments; a later phase
    that tunes on `dev` must hold the slice out.
- **Why 80 and not 50 or 100:** a judgment about cost against resolution, not a
  measurement. Every CI run that changes the pipeline judges every answer, and P3-07
  runs the judge three times uncached, so judge cost scales with the slice. At 50, the
  multi-doc and single-doc strata would fall to ~12 each, too few for a per-stratum
  number to mean anything. At 100, the extra 20 would all be single-doc questions the
  system already gets right 91% of the time. P3-07 measures what 80 can actually detect.
- **Options considered:** 50/10 (cheapest, strata too thin); 100/15 (more single-doc,
  little new information); 80/15 — chosen.
- **Evidence:** No measured data; judgment call. Stratum availability counted from the
  data first (preflight 29): 27 / 24 / 149 / 45.
- **Consequences:** `eval/golden/golden_v1.jsonl` and `DATASHEET.md`, reproducible with
  `rag data golden --check`. Baseline strict recall per stratum is in `EXPERIMENTS.md`.
- **Revisit if:** P3-07 shows the slice cannot detect a regression the gate must catch,
  or a stratum's MDD makes its per-stratum number meaningless.

## DEC-075 — P3-04 bake-off: three cross-lab judges, each pinned to one host, one fixed pair set
- **Date:** 2026-09-28
- **Decided by:** Joint. Krutik: the candidates, the DeepSeek host (DeepInfra), including
  Qwen, and the probes. Claude: the Gemini host, the pair construction, the verdict rule
  and the link rule below, flagged in chat.
- **Status:** Active
- **Candidates and pins** (all `allow_fallbacks: false`, temperature 0, faithfulness only,
  through the unchanged `RagasJudge` path):

  | Candidate | Pinned host | Host price $/Mtok in/out | Why this host |
  |---|---|---|---|
  | `deepseek/deepseek-v4.1-flash` | DeepInfra | 0.14 / 0.42, fp8 | Krutik: 99.99% uptime, structured outputs; the cheapest host (InferenceNet) does not state quantization and showed 94% uptime |
  | `qwen/qwen3.8-flash` | Alibaba | 0.15 / 0.47 | the only host |
  | `google/gemini-3.8-flash` | Google AI Studio | tiered, from 0.375 / 1.875 | Claude: same listed price as Vertex ("Google"); AI Studio is the host EXP-0011 already used for a Gemini model |
  > **CORRECTED on 2026-09-28** (same day, from the probe `run_20260928_050025_932e`): the
  > probe was billed at the **$0.75 / $3.75** tier — 15,105 × 0.75 + 10,245 × 3.75 per Mtok =
  > $0.0497, exactly the recorded cost. The bottom tier quoted in the row does not apply.

  Families `deepseek`, `qwen`, `google` — none is the generator's lab (DEC-073). Qwen is
  also the lab of the retrieval embedder and the answer-relevance embedder; the P0-07
  rule is about the judge and the generator, so it does not apply, and it is recorded here.
- **Pairs** (`rag/eval/judge_check.py`, seed 20260928): each of the 80 answerable
  `golden_v1` questions gives three pairs, 240 in all, with the same article count per pair:
  - **supported** — WixQA's reference answer with its gold articles' full frozen text;
  - **unsupported** — the same answer with random articles that are neither gold nor in the
    dense control's top 50 for that question (`run_20260912_225005_be04`). The corpus has
    no product-area field, so distance in retrieval stands in for "a different area";
  - **hard_negative** — the dense control's top-ranked non-gold articles. **Report-only,
    never part of the bar**: near-duplicate articles may genuinely support the answer.
- **Verdict:** a pair is flagged unsupported when faithfulness < 1.0 — the strict
  "≥ 1 unsupported claim" definition P3-05 gates on, so the check tests the flag CI uses.
  A threshold-free AUROC on the raw score is reported beside it. A judge failure is
  counted, never scored as a verdict.
- **Reference links (`reference-links-v1`):** 26 of 80 reference answers contain 75 URLs.
  The corpus was frozen with link targets stripped (norm-v1) and the generator is told
  never to write URLs, so an unstripped URL is a claim no article can support, and the
  strict flag would fire on a supported pair over formatting. norm-v1's regex matches only
  35 of the 75 (these answers write `[text] (url)` and nest URLs); the new rule keeps link
  text, drops targets, and is validated on all 80 answers: 75 → 0.
- **Order:** one probe per candidate (2 questions × 3 kinds; approved by Krutik) to measure
  tokens, reasoning and failures on the real prompt (preflight 42). Then the pass/fail bar
  is declared in its own entry **before** any full run, and each full run is approved on
  its estimate.
- **Evidence:** no measured data yet; the design is a judgment call.
- **Revisit if:** a probe shows a candidate cannot return structured output on its pinned
  host, or fails more than one call in six.

## DEC-076 — The P3-04 pass/fail bar, declared before the bake-off runs
- **Date:** 2026-09-28
- **Decided by:** Joint — proposed by Claude, approved by Krutik in chat before any full run.
- **Status:** Active
- **The bar**, on the 160 gating pairs (80 supported, 80 unsupported; DEC-075), with the
  flag "unsupported if faithfulness < 1.0":
  1. **Unsupported-flag recall ≥ 0.95** — at least 76 of 80 clearly unsupported pairs flagged.
  2. **Supported pass rate ≥ 0.85** — at least 68 of 80 expert answers with their own gold
     articles NOT flagged. Looser than (1) on purpose: the strict flag fires on one
     unsupported claim, and long procedural expert answers can paraphrase their article.
  3. **Judge failures ≤ 5% of all 240 pairs** — at most 12.
  Hard negatives, accuracy and AUROC are reported and never part of the bar.
- **Selection:** the cheapest candidate, by measured `cost_actual_usd` on its full run, that
  clears all three becomes the production judge. If none clears the bar, judged metrics
  are **report-only** in CI (P3-09), one judge change (prompt or model) is allowed, and it
  is re-measured once. The outcome is recorded either way.
- **Approval:** Krutik, in chat 2026-09-28, on the estimates DeepSeek $0.4739, Qwen $0.5526,
  Gemini $2.8614 (above the $2 gate; approved explicitly). Balance $11.01.
- **Evidence:** No measured data for the thresholds; judgment call, made before the data.
- **Revisit if:** a candidate misses only (2) and the misses read as paraphrase rather than
  unsupported content — which would say the strict flag, not the judge, is the problem,
  and that belongs to P3-05's definition, not to this bar.

## DEC-077 — P3-04 outcome: no judge clears the bar, so judged metrics are report-only in CI for now
- **Date:** 2026-09-28
- **Decided by:** the rule pre-declared in DEC-076 (Krutik-approved); the reading of the
  evidence is Claude's. What to do next is open for Krutik (below).
- **Status:** Active
- **Result** (EXP-0054–0056): all three judges flag 100% of clearly unsupported pairs and
  pass only **35–40%** of the "known supported" pairs, against a bar of 85%. Qwen also
  fails the failure bar (22 of 240). Under DEC-076: **judged faithfulness, unsupported-answer
  rate and false-answer rate are `report-only` in CI (P3-09)**. The gate relies on
  retrieval and deterministic metrics until a judge clears a bar.
- **Why this is not simply "the judges are bad":** the three judges agree on 58 of 73
  supported pairs, and five of the 36 they all flag, read against their articles, contain
  claims the gold articles do not make (EXP-0054 Observations). The supported set assumed
  WixQA reference answers are grounded in their gold articles' text (Phase 3 fact 4). For
  about half of this slice they are not. **Criterion 2 as built cannot tell a correct
  judge from a lenient one.** That is DEC-076's own revisit trigger.
- **What the story allows next:** "one judge change (prompt or model), followed by one
  re-measurement". The evidence points at the instrument, not the judge, so a judge change
  is unlikely to be the informative move. The options, for Krutik:
  1. **Accept report-only** and move on to P3-05 with a judge chosen for reporting only.
     Among candidates meeting criteria 1 and 3, DeepSeek is cheapest (measured $0.00244
     per pair against Gemini's $0.01003).
  2. **Rebuild the supported set so it is supported by construction** (for example: claims
     quoted verbatim from the gold article, or reference answers screened for article
     support by a rule declared in advance), keep the DEC-076 thresholds unchanged, and
     re-measure. The v1 result stays recorded as a failure; v2 is a new instrument with
     its own DEC entry, not a re-scoring.
  3. **Use the judge change the story allows** on the cheapest candidate and re-measure on
     the same v1 pairs.
- **Evidence:** EXP-0054–0056 and their per-pair rows; five pairs read by hand.
- **Revisit if:** Krutik picks option 2 or 3 — its outcome is a new entry, not an edit here.

## DEC-078 — P3-04 pair set v2: "supported" built from the gold articles themselves; bar unchanged
- **Date:** 2026-09-28
- **Decided by:** Krutik chose to rebuild the supported set (DEC-077 option 2); Claude
  designed the construction below, declared here before any v2 run.
- **Status:** Active
- **Why:** v1's supported pairs assumed WixQA reference answers are grounded in their gold
  articles' text. EXP-0054–0056 showed that assumption fails for about half of golden_v1,
  so criterion 2 measured the labels, not the judges (DEC-077). v1 stays recorded as a
  failure; v2 is a new instrument, not a re-scoring of v1.
- **Construction (`build_pairs_v2`, seed 20260928):** for each of the 80 answerable
  golden_v1 questions, three pairs, **all judged against the same context — the question's
  gold articles' full text**:
  - **supported** — 3 consecutive sentences copied verbatim from one gold article;
  - **unsupported** — 3 consecutive sentences copied from a far article (not gold, not in
    the dense control's top 50);
  - **hard_negative** — 3 consecutive sentences from the top-ranked non-gold article that
    has an eligible window. Report-only, as before.
  - A sentence is eligible when it has 6–60 words and occurs in **exactly one** corpus
    article, so shared boilerplate can never make an unsupported pair true. Counted first:
    all 80 questions have a gold window and a hard-negative window; 90.1% of distinct
    sentences are unique; 5,157 of 6,221 articles have a window.
  - The answer text and its source article are stored on every per-pair row.
- **Unchanged:** the verdict (flag if faithfulness < 1.0), the judge path, the pins, and
  **the DEC-076 bar — recall ≥ 0.95, supported pass rate ≥ 0.85, failures ≤ 12**. Nothing
  about the bar is tuned after seeing v1.
- **What v2 proves and does not:** a judge that clears it verifies literal support and
  rejects foreign content in the same register. It does **not** measure how the judge
  treats paraphrase, which is what generated answers do. That limitation goes in README
  and NARRATIVE with the result.
- **Run order and money:** DeepSeek first — the cheapest measured candidate (EXP-0054,
  $0.00244/pair) — approved by Krutik with option 2 at "about $0.60"; `--estimate-only`
  gives $0.6066, and v1's estimate ran 24% low for this judge. If it clears, it is the
  production judge by DEC-076's selection rule and no other candidate is run. If it does
  not, Qwen (est. $0.7074) and Gemini (est. $3.6627) each need a new go-ahead.
- **Evidence:** No measured data for the construction; judgment call, declared in advance.
- **Revisit if:** a hand read of flagged v2 supported pairs shows the flag firing on a
  genuine extraction — which would point at the strict "< 1.0" rule rather than the labels.

## DEC-079 — P3-04 closed: `deepseek/deepseek-v4.1-flash` @DeepInfra is the production judge; judged metrics are gating
- **Date:** 2026-09-28
- **Decided by:** the selection rule pre-declared in DEC-076 (Krutik-approved), applied by Claude.
- **Status:** Active — **supersedes DEC-077's "report-only"** (DEC-077's v1 outcome stands as recorded).
- **Result:** EXP-0057 (`run_20260928_143152_c11c`): on the v2 pairs, recall 1.0000,
  supported pass rate 0.9000, failures 0 — all three DEC-076 criteria met. DeepSeek is the
  cheapest measured candidate ($0.00138/pair on v2, $0.00244 on v1 against Qwen $0.00292
  and Gemini $0.01003), so by the selection rule it is the production judge and Qwen and
  Gemini are not run on v2.
- **P3-09 marking (from P3-04):** faithfulness, unsupported-answer rate and false-answer
  rate are **`gating`**.
- **The judge, exactly:** `deepseek/deepseek-v4.1-flash`, provider DeepInfra only,
  `allow_fallbacks: false`, temperature 0, Ragas 0.4.3, slug verified on OpenRouter
  2026-09-28. Family `deepseek` — not the generator's lab (DEC-073).
- **Limits carried forward, stated in README and NARRATIVE:** the check proves literal
  support is verified and foreign content rejected; paraphrase behaviour and human
  agreement are unmeasured. Two of the eight false flags were verbatim *hypothetical
  examples*: the strict "≥ 1 unsupported claim" rule reacts to illustrations. P3-05 declares
  that rule up front and it is not changed here; the effect is tracked as OQ-048.
- **Next, in this order:** (1) a v2 Tier 2 control config with this judge, and
  `ci/phase3_baseline.yaml` version 2 under tag `phase3-baseline-v2` (DEC-073); RunConfig
  has no field for `allow_fallbacks` yet, so pinning without fallbacks at run level needs
  one, costed for hash movement first (MIS-019). (2) P3-05. (3) Re-score the Phase 2 judged
  runs from stored answers (DEC-073).
- **Evidence:** EXP-0057; EXP-0054 for the per-pair cost ranking.
- **Revisit if:** P3-07's variance runs show this judge's MDD at golden-slice size too wide
  to catch the regressions P3-12 must catch, or the slug stops resolving.

## DEC-080 — Baseline record v2: the production judge, pinned without fallbacks, tagged `phase3-baseline-v2`
- **Date:** 2026-09-28
- **Decided by:** Krutik ("finish step 1"); implementation choices Claude's, below.
- **Status:** Active — completes what DEC-073 and DEC-079 promised. Does not move the
  `phase3-baseline` tag (DEC-071), which stays as v1.
- **Context:** the v1 record named the placeholder judge `gpt-oss-120b`, now a refused
  same-lab pairing (DEC-073). P3-04 chose `deepseek/deepseek-v4.1-flash` validated on one
  host with fallbacks off (DEC-079), and run configs had no way to say "no fallbacks": a run
  could have been judged partly by hosts P3-04 never tested.
- **Decision:**
  - **New RunConfig field `judge_allow_fallbacks`** (default `True`, the Phase 0–2
    behaviour). Its default is an absent dimension, so **no existing config hash moved** —
    checked on all 76 configs before and after, and pinned by a test (MIS-019). `False`
    requires a non-empty `judge_provider_order`, reaches the judge's OpenRouter routing,
    and makes the startup model check treat the judge's provider as a hard pin.
  - **New Tier 2 control `configs/baseline_dense_tier2_v2.yaml`** — the v1 control with only
    the judge changed: `deepseek/deepseek-v4.1-flash`, `[DeepInfra]`, no fallbacks.
    `config_hash` 2d7800625af53774. The v1 file stays byte-identical (the v1 tag pins it).
    `rag ask` now defaults to v2.
  - **`ci/phase3_baseline.yaml` version 2**, tag **`phase3-baseline-v2`**: promoted.yaml,
    the v2 control, `baseline_answer@v1`, corpus/dev hashes, `golden_v1` and its hash,
    and the four slugs, each verified on OpenRouter 2026-09-28 by `rag models verify`.
    The v2 control has **no reference run yet** — no judged run with this judge exists.
- **What this is and is not:** a record of settings. It holds no judged numbers; the first
  trustworthy ones come from P3-05, and P3-11's `ci/baseline.json` freezes them.
- **Evidence:** the hash comparison over 76 configs; `rag models verify` output; tests.
- **Revisit if:** the judge, generator, prompt, retrieval config or golden slice changes —
  each is a version 3 with its own entry.

## DEC-081 — P3-05: how `rag faithfulness` measures, and where it had to choose
- **Date:** 2026-09-28
- **Decided by:** Claude (implementation of P3-05's declared metrics), not yet reviewed by Krutik.
- **Status:** Active
- **What it does:** `rag faithfulness <run_id>` reads a Tier 2 run's stored answers,
  rebuilds each answer's prompt context from its stored `context_chunk_ids` through the
  same `ConcatAssembler` (asserted equal to the assembler's own output), judges every
  non-refused answer claim by claim, and records one `faithfulness` row plus one row per
  answer in the results store. A markdown report of the 10 lowest-faithfulness answers
  (claim, verdict, judge's reason, chunk) goes to `results/reports/`.
- **The declared metrics, exactly as P3-05 lists them:** mean faithfulness; unsupported-
  answer rate (≥ 1 unsupported claim, strict); refusal rate on answerable questions
  (`refusal-lexical-v3`); false-answer rate on unanswerable ones; citation integrity. All
  per stratum: all, answerable, unanswerable, `gold_docs:single|multi`,
  `gold_in_context|gold_not_in_context` (the run's own stored flag — all gold present).
- **Choices P3-05 left open:**
  1. **Claims come from Ragas's own two steps** (`_create_statements`, `_create_verdicts`,
     `_compute_score`), in `ascore`'s order, because `ascore` returns only a number. A test
     on a fake Ragas LLM asserts the score equals `ascore`'s. Private methods: acceptable
     only because Ragas is pinned exactly and fingerprinted (MIS-004).
  2. **Supporting chunk = `attribution-lexical-v1`**, a heuristic: the context chunk with
     the largest share of the claim's content words. Ragas judges against the joined
     context and names no chunk. The verdict is the judge's; the pointer is ours, and the
     report says so.
  3. **Citation integrity is document-level**: every cited `[doc:<id>]` must be a document
     in the assembled context. This project cites documents, not chunks (P1-06). On the
     Phase 2 dev run it already finds 2 of 92 answers citing ids that exist nowhere in the
     corpus (one a near-copy of a real id).
  4. **The judge comes from a config, never from the run row** — default
     `configs/baseline_dense_tier2_v2.yaml` (DEC-079). Phase 0–2 rows name a refused judge.
  5. **Not applicable first:** refusals have no claims and are not judged; a judge failure
     or NaN is `None`, counted, never zero, and **never cached**.
  6. **Cache** (`results/judge_cache.sqlite`, gitignored) keyed on (judge identity incl.
     host and fallback flag, Ragas version + faithfulness fingerprint, question, context
     hash, answer hash). `--no-cache` reads and writes nothing, for P3-07's variance runs.
  7. **Estimate:** linear in context words, calibrated on EXP-0054 (the same judge on
     realistic-length answers), $0.00292 per 1,000 words. Any uncached spend needs
     `--approve-cost` (DEC-053); above $2 it must cite a DEC.
- **Evidence:** offline tests (10) and a free dry run on `run_20260913_205058_dc03`: all 100
  contexts rebuild, 8 refusals, estimate $0.4681 for 92 answers. **No judged run yet** —
  P3-06 is the first.
- **Revisit if:** P3-06's report shows the attribution heuristic pointing at the wrong chunk
  often enough to mislead a reader, or P3-07 needs claim-level variance the cache hides.

## DEC-082 — The golden slice is a runner split; P3-07 measures noise with fresh answers, α = 0.05
- **Date:** 2026-09-28
- **Decided by:** Joint. Krutik: α = 0.05, including the judge-only re-judges, and pausing
  before spend. Claude: the split mechanics below.
- **Status:** Active
- **Context:** P3-07 needs judge variance on the golden slice, and no run had ever
  generated answers for it: the runner only knew the four frozen splits.
- **Decision:**
  - `load_split("golden_v1")` returns the committed slice in the runner's split shape,
    read through `rag.dataset.golden` (its only read path); article types come from `dev`.
    Its hash covers `stratum` and `reason`: `sha256:25398286…dd55`. Runs report a
    `stratum:<name>` slice for each of the four strata. Verified on a free toy run: retrieval
    metrics average over the 80 answerable questions, the 15 unanswerable ones are not
    applicable (MIS-002).
  - `configs/golden_generate_v2.yaml`: the v2 control on `golden_v1`, all 95 questions,
    `skip_judge: true`. Answers are judged by `rag faithfulness` (the gate's path), never
    by the runner's built-in three-criterion judge.
  - **P3-07 method = P1-11's**: three identical full runs — fresh generation AND fresh
    judging (`--no-cache`) each time — MDD = max(range, 2 × stdev), rounded up to 0.001.
    Plus two extra `--no-cache` re-judges of the first run's answers, to separate judge
    noise from generator noise.
  - **α = 0.05** for the retrieval paired test (P3-09 will declare it in `ci/gate.yaml`).
- **Evidence:** no measured data; method choices.
- **Revisit if:** the three golden runs disagree on which questions are refused by more
  than a handful — the floor would then be dominated by refusal flips, not faithfulness.

## DEC-083 — P3-07: the measured floors are the gate's thresholds; three consequences for P3-09
- **Date:** 2026-09-28
- **Decided by:** Claude (reading the measurement); the thresholds themselves are P3-09's
  to declare and Krutik's to approve.
- **Status:** Active
- **Result:** EXP-0059. Corpus-level MDDs on `golden_v1` (three fresh full runs): mean
  faithfulness **0.026**, unsupported-answer rate **0.064**, false-answer rate **0.077**,
  refusal rate **0.073**, citation integrity **0.016**. Registered as noise-floor family
  `golden-v1-deepseek` in `rag/eval/noise_floor.py`, matched from a faithfulness row's
  provenance (judge, host, Ragas, generator, prompt) so a changed judge gets "no MDD
  measured". Published as `ci/DETECTION_FLOOR.md`. Retrieval: α = 0.05 (DEC-082).
- **Consequences P3-09 has to face before it declares rules:**
  1. **Citation integrity cannot be zero-tolerance as the story wrote it.** Identical runs
     produce 1–2 answers citing ids outside their context. Options for P3-09: gate on the
     rate against its MDD like the judged metrics, or keep zero tolerance only for ids that
     exist nowhere in the corpus *and* show it is also noisy (both P3-06 cases were of that
     kind). Not decided here.
  2. **The judge is most of the judged noise** (0.023 of 0.026). A cheaper floor would need
     a steadier judge, not more generator control.
  3. **False-answer rate is gated in whole questions**: 2 of 15. The slice has only 15
     unanswerable questions; if the gate must catch one more false answer, the slice needs
     more of them (a golden_v2, P3-03's versioning rule).
- **Also decided:** one reviewed URL exception. Run `run_20260928_194258_4916`, question
  `47337149535f21c6` quotes `www.mystunningwebsite.com`, Wix's example domain, from an
  article in its context (36 corpus articles contain it). P1-05's rule is about links the
  generator writes; this is an illustration copied from evidence. Listed in
  `tests/test_prompts.py::REVIEWED_URL_EXCEPTIONS`, scoped to that run and the faithfulness
  rows copying it; any other URL still fails the test.
- **Evidence:** EXP-0059's eight runs; the retrieval table from `mcnemar_exact_p`.
- **Revisit if:** the judge, host, generator, prompt or golden slice changes (the floors are
  for this family only), or P3-12's drills show a planted regression inside the floor.

## DEC-084 — P3-08: how `rag ci-eval` works, and the opt-in call cache it needs
- **Date:** 2026-09-28
- **Decided by:** Claude (implementation of P3-08), not yet reviewed by Krutik. The gate
  rules in `ci/gate.yaml` are a DRAFT; P3-09 declares them.
- **Status:** Active
- **What it does:** `rag ci-eval --baseline ci/baseline.json` runs (1) Tier 1 retrieval on
  all of `dev` with `configs/promoted.yaml`, (2) Tier 2 generation on `golden_v1` with
  `configs/golden_generate_v2.yaml`, (3) `rag faithfulness` on those answers with the v2
  judge, then (4) compares to the baseline and writes `ci/out/ci_eval.json` (the artifact)
  and `ci/out/ci_eval.md` (the PR comment). Exit codes: **0 pass, 1 gated quality failure,
  2 error, 3 needs approval** — an outage or a retired slug is 2, never 1 (P3-10).
- **Choices the story left open:**
  1. **An opt-in call cache** (`rag/call_cache.py`, `results/ci_call_cache.sqlite`):
     query embeddings and generated answers are replayed **only inside `ci-eval`**, so an
     unchanged pipeline is near-free and compares equal to its baseline. Experiments never
     see it — P1-11 and P3-07 measure noise from fresh calls. Keys cover everything that
     shapes the output (embedding: model, pinned host, prefix, dimensions, prefixed text;
     answer: model, prompt ref, temperature, max_tokens, reasoning effort, the full rendered
     prompt). Passages are never cached (they live in the index). Every run row made under
     it records its own hits and misses (`metrics_json.call_cache`), so a replay never
     passes for a fresh measurement. The judge uses its own cache (DEC-081).
  2. **The baseline carries per-question outcomes** (dev recall@5, golden recall@5, golden
     answer flags). The comparison needs no results store, which a CI machine does not have.
  3. **Retrieval is gated with the exact McNemar test** at the gate's α — the same test
     `ci/DETECTION_FLOOR.md` is computed from. Lost and gained ids are always listed.
  4. **Judged metrics fail only beyond the MDD** of the family the faithfulness run matches.
     **No matching family ⇒ FAIL (fail closed)**: a changed judge cannot be gated until
     P3-07 is re-measured for it.
  5. **Hard fails in the draft:** empty answer, judge failure, a changed question set, a
     changed provenance (corpus, splits, judge, judge prompt version). Citation integrity is
     **report-only** in the draft (DEC-083).
  6. **`rag ci-baseline update --from ci/out/ci_eval.json --reason DEC-NNN`** writes the
     baseline, and refuses without an existing DEC entry or from a run with empty answers
     or judge failures. P3-11 adds the ratchet (the PR rule and the drift job).
- **Cost of one run, estimated:** uncached — generation $0.03, query embeddings under
  $0.001, judging ~$0.30 at EXP-0059's measured rate; cached (nothing changed) — near zero.
  The draft budget is `ci_budget_usd: 1.00`: above it the command stops before spending
  (exit 3) unless `--approve-cost` is given.
- **Evidence:** offline tests; no real ci-eval run yet — the first one creates the baseline.
- **Revisit if:** a cached run and a fresh run of the same config disagree on a gated
  metric beyond its MDD — the cache key would be missing something that shapes the output.

## DEC-085 — The first CI baseline: `rag ci-eval` run 1 of 2026-09-28
- **Date:** 2026-09-28
- **Decided by:** Krutik approved the two first ci-eval runs; Claude chose to baseline run 1.
- **Status:** Active
- **What:** `ci/baseline.json`, written by `rag ci-baseline update --from
  ci/out/run1/ci_eval.json --reason DEC-085`, from runs `run_20260928_215614_21fb` (dev
  retrieval), `run_20260928_220408_7f7b` (golden generation) and `run_20260928_221629_42ad`
  (faithfulness), git `cc6945e`, clean. Cost $0.3024.
- **Its numbers:** strict recall@5 0.72 on `dev`, 0.525 on `golden_v1`; mean faithfulness
  0.8596, unsupported-answer rate 0.5714, false-answer rate 0.4000 (6 of 15), refusal rate
  0.1125, citation integrity 0.9740; 77 answers judged, 0 judge failures.
- **Why this run and not a mean of several:** the gate compares per-question outcomes, which
  only a real run has. Noise is handled by the MDDs (DEC-083), not by averaging the baseline.
  Note that its false-answer rate (0.40) is above all three P3-07 runs (0.27–0.33): a later
  run landing there reads as "better, within noise", never as a failure.
- **Revisit if:** P3-11's ratchet replaces it — only through a new DEC entry.
