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
