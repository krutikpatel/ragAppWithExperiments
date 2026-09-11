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

The naive system is BM25 over fixed 512-word chunks, pooled to documents by best
chunk, showing five documents. No reranker, no query rewriting, no dense retrieval —
the dumbest configuration that could be defended, so that everything after it has a
number to beat (EXP-0001).

It found **all** the required articles in its top five for **40.5%** of `dev`
questions, and **at least one** for 50.5%. nDCG@10 was 0.384; mean reciprocal rank on
the 160 single-document questions was 0.332. It runs in-process at 35 ms p95 and
costs nothing per query. The number is exactly reproducible: three runs of the
configuration produced identical metrics to twelve decimal places, because nothing in
the pipeline is random (EXP-0001).

Two things about the failures matter more than the headline.

The failure is mostly total. Of 200 questions, 81 had every gold document in the top
five, 20 had some, and **99 had none**. Half the questions get nothing useful.

And multi-document questions fail on the second document. On the 40 questions that
need two or three articles, BM25 found at least one of them 67.5% of the time and all
of them **17.5%** of the time. This is the gap that strict recall exists to expose: a
system that reliably finds one of two required articles looks healthy under any
looser definition and still cannot answer the question (EXP-0001).

Reading the misses rather than counting them: of the 136 gold documents absent from a
top five, 87 were in the top hundred (median rank 18) and 49 were not. So about two
thirds of misses are ranking failures — the right document was scored, and five
others scored higher — and a third are documents BM25 never surfaced. The failing
questions read in full split the same way. Some name the thing differently from the
article — the question says *published*, the article says *visibility*; the question
says *static pages*, and the one article containing *static* is about converting
dynamic pages, while the gold article, which is about adding pages, is not in the top
hundred. Others have the gold article at rank four to nine behind a topically adjacent
one. These are descriptions of the baseline, not claims about what fixes them.

## 4. What was tried, axis by axis

### Chunking: whole documents versus 512-word chunks (EXP-0002)

The WixQA paper retrieves whole articles rather than chunks, so its retrieval
configuration was run as-is — one axis away from the baseline — to anchor against the
published setup and to answer a question I had: does chunking the longest third of
the corpus (1,661 articles exceed 512 words) cost or gain anything at the document
level?

Nothing measurable. Strict recall@5 went from 0.405 to 0.410 — one question net, and
`rag diff` shows the truth of it: eleven questions gained, ten lost, 179 unchanged.
The flips show no pattern in gold-document length (median 716 words gained, 660
lost) and the rank movements are small in both directions. Deeper recall was slightly
lower without chunking (strict recall@20 0.635 → 0.610). I record this as no
measurable difference, which is what it is (EXP-0002).

The paper's own number for this configuration is a GPT-4o-judged "Context Recall" of
about 0.73 on all 200 ExpertWritten questions. Ours is a labelled strict recall of
0.41 on a 100+100 dev split. They measure different things on different questions and
are not placed side by side; the comparison of definitions is in DEC-036.

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

**A generation metric must know what the generator was given.** The first Tier 2 run
reported a 2% false-refusal rate. Both refusals were on questions whose articles had
not been retrieved, and the generator had said so — correct behaviour, scored as
failure. Meanwhile on 58 of the 60 questions where retrieval failed, the generator
answered anyway, and no metric noticed. The metric was designed before any retrieval
had run, with "answerable" meaning *in the corpus* rather than *in the context*. I
found it by reading the two examples, not by looking at the aggregate (MIS-012).

**Fail at the unit that failed.** A hundred-question judging run was voided by one
question's structured output overflowing a token budget. Judging one question never
depends on another; the honest record was "this criterion could not be scored here",
not "this run did not happen". Two voided runs taught that (MIS-010, MIS-011).

## 10. What remains untested

Every retrieval technique — that is Phase 1. Within Phase 0 itself, the open questions
that gate what the numbers can be trusted to mean:

- **The judge's own noise (OQ-017).** No judged difference is a finding until the
  run-to-run spread is measured. The same 20 questions scored faithfulness 0.7284 and
  0.7236 on two runs; one input scored answer correctness 1.00 and 0.857 on two
  providers.
- **Whether step coverage measures the answers or the matcher (OQ-007).** The
  lexical matcher misses paraphrases; the proportion of misses is unknown.
- **Whether refusal metrics should condition on retrieval (OQ-019).** As defined,
  they do not, and the ungrounded-answer rate has no metric.
- **Whether `feature_request` articles act as distractors (OQ-006).** A third of the
  index is never a right answer for any `dev` question.
- **Whether the unanswerable set is detectable by keyword rather than grounding
  (OQ-004)**, and — before any of that — whether its 45 questions survive a human
  read. They were LLM-drafted and have not been verified.

The full list, each with the decision rule that would settle it, is in
`OPEN_QUESTIONS.md`.
