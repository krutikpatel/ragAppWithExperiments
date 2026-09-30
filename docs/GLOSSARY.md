# Glossary

Project- and dataset-specific terms. RAG jargon that is standard in the field is
used freely elsewhere; this file covers what is specific to *this* corpus and
harness.

**WixQA** — The benchmark this project runs on: a Wix Help Center snapshot plus
three question sets. Wix.com AI Research, arXiv:2505.08643, MIT licence.

**`wix_kb_corpus`** — The 6,221-article knowledge base, snapshotted 2024-12-02.

**ExpertWritten / Simulated / Synthetic** — The three WixQA question sets. Expert
written: real support tickets with expert answers (200). Simulated: answers
distilled from user-expert chats (200). Synthetic: LLM-generated from single
articles (6,221).

**`corpus_hash`** — Hash over the frozen corpus's *source* fields, sorted by id.
Two runs with different corpus hashes are not comparable. Derived columns such as
`indexed_text` are excluded, so a normalization change does not masquerade as a
corpus change.

**`normalization_version`** (`norm-v1`) — Which text-normalization rule produced the
indexed text. Bumped whenever the rule changes; recorded on every run.

**`indexed_text` vs `contents`** — `contents` is the article verbatim and is what
citations display. `indexed_text` is what gets embedded or indexed, derived from
`contents` by the current normalization rule.

**Split hash** — Hash over a split's rows. Guards against silently comparing runs
that used different question sets.

**`dev_large`** — The 6,221 synthetic questions. Carries a leakage warning: each
question was generated from the article it is grounded in, so question-document
lexical overlap is inflated and lexical retrievers score optimistically. For
statistical power on retrieval-only sweeps, never for headline numbers.

**Unanswerable set** — 45 authored questions with no answer in the frozen corpus, in
three buckets: `out-of-scope-platform` (a competitor's product), `post-snapshot`
(explicitly asks about a period after 2024-12-02), `underspecified` (no referent).
Built by adding questions, never by deleting articles.

**Strict recall@k** — Fraction of questions where *all* gold documents appear in the
top k. The headline retrieval metric here, because 79 of 400 human-grounded
questions need more than one document.

**Loose recall@k** — Fraction where *any* gold document appears in the top k.

**qrels** — Query relevance judgments: `{question_id: {doc_id: 1}}`. Binary and
document-level, because that is the granularity of WixQA's ground truth.

**`doc_pooling`** — The rule turning ranked chunks into ranked documents. `max`
(default) takes a document's best chunk score; `sum` adds them. The rule changes the
document ranking on its own, so it is recorded on every run.

**`chunk_id`** — An opaque hash of (chunker identity, doc id, ordinal). Opaque on
purpose: document identity comes from the persisted chunk→doc mapping, never from
parsing a chunk id.

**Tier 1 / Tier 2** — Tier 1 is retrieval metrics only, zero LLM calls, the default.
Tier 2 adds generation and judge metrics and is run only on promoted configs.

**Reranker** — A second, slower scorer that re-orders the candidates a retriever
already found. It cannot add a document the retriever missed, so its best possible
result is the retriever's recall at the candidate depth.

**Cross-encoder** — The usual kind of reranker. Where the dense retriever turns the
question and the passage into vectors *separately* and compares them, a cross-encoder
reads the question and the passage together in one pass and outputs a relevance
score. That is far more accurate and far too slow to run over a whole corpus, which
is why it only ever sees a short candidate list.

**LLM-as-reranker** — Instead of a purpose-built scorer, the candidates are numbered
and a chat model is asked to put them in order. The difference from a cross-encoder
is that the model sees every candidate at once and can compare them to each other.

**`rerank_candidates`** — How many **documents** go into the reranker (not chunks).
"50 → 5" means the top 50 articles are re-scored and the best 5 reach the generator.

**Search unit** — Cohere's billing unit for reranking: one query with up to 100
documents. It is a per-*query* charge, so a reranking experiment costs more on a
bigger question set, unlike an index which is paid for once.

## Phase 3 — the quality gate

**Golden slice (`golden_v1`)** — The fixed set of 95 questions the CI gate runs on: 80
answerable (single-doc, multi-doc, and the ones the system once answered without its
evidence) and 15 unanswerable. Chosen by a script, never by hand. Its scores are not system
scores, because it over-samples hard cases on purpose; they are only compared with each other.

**Gold in context** — Did every gold article actually reach the generator's prompt? Recall@5
is read off the ranking; this is read off what the model was shown, so it moves when `top_k`
changes and recall@5 cannot.

**Faithfulness (claim-level)** — The judge splits an answer into claims and checks each one
against the exact context the generator saw. Mean faithfulness is the share of supported
claims. An **unsupported answer** has at least one claim the judge could not find in the
context. A **false answer** is an answer (not a refusal) to an unanswerable question.

**Citation validity** — The share of answers whose citations are all well-formed ids of
articles the answer was given. Garbled ids count against it.

**MDD / detection floor** — Minimum detectable difference: the smallest change a metric can
show that run-to-run noise does not. A change smaller than it passes the gate, not because
it is harmless, but because it cannot be told from noise. `ci/DETECTION_FLOOR.md` lists them.

**Pairwise threshold** — The MDD for comparing *two* runs (a PR run against the baseline
run), about √2 times one run's spread. The gate uses these (DEC-091).

**Baseline (CI)** — `ci/baseline.json`: the per-question results of a reference gate run,
written only by `rag ci-baseline update --reason DEC-NNN` and stamped with a hash so a hand
edit is detected.

**Ratchet** — The rule that a pull request may not change pipeline code and the baseline's
results together. A change is measured against the old baseline before it can become the new
one.

**Call cache** — The gate's cache of query embeddings, answers and judgments. An unchanged
pipeline replays them and the gate costs $0; experiments never use it.

**Drill** — A deliberately planted regression opened as a throwaway pull request, to check
that the gate fails (or passes) as it should.

**PASS / FAIL / ERROR / NEEDS APPROVAL** — The gate's four outcomes (exit 0 / 1 / 2 / 3). FAIL
means quality got measurably worse; ERROR means the gate could not measure (a judge failure,
an outage), which is never reported as a quality failure.
