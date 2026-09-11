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
