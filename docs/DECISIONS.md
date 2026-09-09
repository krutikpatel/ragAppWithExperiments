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
