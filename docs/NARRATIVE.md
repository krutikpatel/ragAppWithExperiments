# Narrative

The story of the investigation, written from `EXPERIMENTS.md` and nothing else.
Sections that depend on runs stay empty until those runs exist.

## 1. The problem and the corpus

The corpus is the Wix Help Center: 6,221 support articles, snapshotted 2024-12-02,
shipped as part of the WixQA benchmark (Wix.com AI Research, arXiv:2505.08643, MIT).
Questions are real support tickets with expert-written answers, plus a simulated set
distilled from user-expert chats, plus a large LLM-generated set.

Three properties of this data shape everything that follows.

**Ground truth is document-level.** Each question names the article ids that answer
it — not a passage, not a span. We retrieve chunks and are scored on documents, so
every retriever has to expose how its chunks map back to documents and how their
scores pool into a document score. That pooling rule turns out to change the
document ranking on its own, with identical chunk scores, which is why it is a
recorded config field rather than an implementation detail.

**Most questions are single-document, but not all.** Of the 400 human-grounded
questions, 321 have one gold article, 70 have two, and 9 have three. That
distribution is the reason the headline retrieval metric is *strict* recall — did
we find **all** the gold documents — rather than the more forgiving "any". A system
that reliably finds one of two required articles looks fine under loose recall and
still cannot answer the question.

**The answers are procedures.** Wix support answers are ordered markdown steps. A
system can retrieve exactly the right article and still fail by dropping step 4 or
reordering it, and no faithfulness judge will notice, because every step it did emit
was faithful. That is why step coverage is on the metric list.

## 2. How this was measured

_The harness is built; no experiment has run through it yet._

**Inputs are pinned.** The corpus is one HuggingFace commit, materialized locally and
hashed (`sha256:74694ad4…`, 6,221 articles). Four splits are frozen and hashed: `test`
(100 expert-written + 100 simulated, held out), `dev` (the other 200), `dev_large`
(all 6,221 synthetic questions), and `unanswerable` (45 authored questions with no
answer in the corpus). Split assignment is a seeded stratified deal, so which
questions are held out does not track anything in the data.

**Retrieval metrics.** Strict recall@k — *all* gold documents in the top k — is the
headline, because 79 of the 400 human-grounded questions need two or three documents
and a system that finds one of two looks healthy under any looser definition. Loose
recall@k and nDCG@10 accompany it. MRR is reported only over the single-gold subset,
with the subset size attached: reciprocal rank asks where *the* answer is, and
averaged over a mixed population it tracks the split's multi-doc proportion rather
than the retriever. Everything goes through `ranx`; nothing is hand-rolled.

Two things about the metrics are worth knowing before reading any number they
produce. `strict_recall@1` is structurally capped — two documents cannot both be in a
top-1 list — so a fifth of the questions can never score there. And retrieval depth is
deliberately separate from context size: an early version ranked only `top_k=5`
documents and reported `strict_recall@20`, which was recall@5 wearing a different
label.

**Generation metrics.** The cheap ones do the most work. Citation precision and recall
are computed by comparing the document ids the answer cited against the gold ids — no
LLM call, free, and immune to a judge model changing underneath us. Step coverage
catches the failure mode a faithfulness judge structurally cannot: retrieving the
right article and then dropping or reordering a step, where every step that *was*
emitted is perfectly faithful. Three judge-scored criteria — faithfulness, answer
relevance, answer correctness against the gold answer — sit on top, each with a
versioned prompt whose content hash is pinned in a test, so a prompt edited without a
version bump fails the suite instead of quietly changing every future score.

**What the numbers are guarded against.** Runs record corpus hash, normalization
version, split hash, pooling rule, git SHA and dirty flag, model ids and prompt
versions; `rag diff` refuses to call two runs comparable when any of those differ.
`dev_large` carries a leakage warning in code and metadata — its questions were
generated *from* the articles they are grounded in, so lexical overlap is inflated.
`test` is held behind an explicit flag that prints how many times it has been opened
before. And a run that crashes is recorded as `VOID` rather than dropped, because
silent gaps in the ledger are what make a results document untrustworthy.

The most useful thing built here is not a metric. It is `run_questions`: one row per
question per run, with the ranked documents, the gold ranks, and the per-question
metric values. Aggregates say a technique gained four points; those rows say which
questions flipped and what came back instead, and that is what a findings document is
actually made of.

## 3. The baseline

_Pending P0-13. No baseline has been run._

## 4. What was tried, axis by axis

_Pending. No experiments have been run._

## 5. What actually moved the needle

_Pending. Requires VALID experiments._

## 6. What did not work, and what that suggests

_Pending. Requires VALID experiments._

## 7. Where the system still fails

_Pending P0-07 evaluation runs and `FAILURES.md`._

## 8. Production engineering

_Pending Phase 3._

## 9. Lessons that transfer

Three so far, all from building the harness rather than from a result.

**Count before you build.**  The handover for this phase made three claims about the
data, and counting contradicted all three. Article text is "dense with markdown
links": 2 of 6,221 articles contain one. Answers are "procedural markdown": 54 of 200
are; the rest are prose. The article-type slice would separate `article`,
`feature_request` and `known_issue`: every gold document in `dev` is an `article`, so
two thirds of that slice are empty on the split we iterate on. Each was implemented as
specified and recorded as what it measurably is. (MIS-001, MIS-002)

**Hand a library the order, not the scores.** Pooled document scores tie constantly.
Passing the raw ties to the metrics library let it re-break them by a rule we had not
chosen, so the metrics scored a different ranking than the one the system returns and
records. It surfaced as a nonsense line in a diff — a gold document at rank 4 scoring
zero recall@5 — and would otherwise have quietly shifted every retrieval number in
the project. (MIS-003)

**The empty case is the design.** Step coverage over prose answers, MRR over
multi-document questions, precision when nothing was cited: each has a "not
applicable" that is not zero. Averaging zeros there produces numbers that look like
system failures and are actually category errors.

## 10. What remains untested

Everything. See `OPEN_QUESTIONS.md`.
