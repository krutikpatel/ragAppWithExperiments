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
