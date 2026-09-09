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

_Pending P0-06 through P0-09. The splits and ground-truth format exist; the metrics
that consume them do not yet._

What exists so far: the corpus is pinned to one HuggingFace commit and hashed
(`sha256:74694ad4…`), so any two runs can be checked for input equality. Four splits
are frozen and hashed: `test` (100 expert-written + 100 simulated, held out), `dev`
(the other 200), `dev_large` (all 6,221 synthetic questions), and `unanswerable` (45
authored questions with no answer in the corpus). Split assignment is a seeded,
stratified deal, so the choice of which questions are held out does not track
anything in the data.

Two things are deliberately fenced off. `dev_large` carries a leakage warning in
code and in metadata: its questions were generated *from* the articles they are
grounded in, so lexical overlap is inflated and any lexical retriever scores
optimistically on it. And `test` is held out behind an explicit flag with a logged
opening — 400 gold questions across dozens of experiments is few enough that
iterating on them would produce a system tuned to the test set and disappointing
everywhere else.

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

One so far, from building the harness rather than from a result: the handover
document for this phase described the article text as dense with markdown links, and
P0-02 exists to decide how to handle them. Counting first showed that 2 of 6,221
articles contain any markdown link — the links live in a field we do not index and
in the answers. The normalization rule was implemented as specified, but it is
recorded as what it measurably is: close to a no-op on this corpus. Writing it up as
a meaningful preprocessing decision would have been a small, quiet fiction of
exactly the kind that makes the rest of a results document untrustworthy. (MIS-001)

## 10. What remains untested

Everything. See `OPEN_QUESTIONS.md`.
