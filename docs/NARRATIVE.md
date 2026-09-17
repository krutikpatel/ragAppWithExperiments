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

**How noise was handled.** Retrieval is deterministic — three runs of the baseline
matched to twelve decimal places — so every retrieval difference is real. The judged
metrics are not, and before interpreting any of them I measured how much they move
when nothing changes: three identical runs on the same hundred questions, then the
same hundred answers judged three times. Faithfulness and answer relevance range about
0.03 between identical runs; answer correctness about 0.01. Nearly all of it is the
judge changing its mind about the same answer — on 12 of 100 questions, re-judging an
identical answer moved faithfulness by a quarter point or more. Those ranges are the
floor: a judged difference inside them is written as no measurable difference, and
`rag diff` says so automatically (DEC-037). Step coverage's floor turned out to be half
its own value, which means that as built it cannot detect anything, and I say so rather
than report it.

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

*Since Phase 1 the control is EXP-0004 (BM25 at 600/100, five distinct documents,
strict recall@5 0.410) and EXP-0005 (dense, 0.715); the numbers above are the Phase 0
baseline they were built from, and section 4 records the steps between.*

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

### Chunking again: 512/0 versus 600/100 (EXP-0003)

Phase 1's dense control was specified at 600 words with a 100-word overlap, and two
controls that differ in chunking as well as retrieval cannot answer "does dense beat
lexical?" So I moved both to 600/100 and re-ran BM25 (DEC-038). Before running I
profiled the corpus: 79% of articles fit in one 600-word chunk, 73% in a 512-word one,
and the frozen text has no list markers at all — the source's numbered procedures
arrive as "To do X:\nClick A. Click B." — so "chunk boundaries inside a numbered list"
had to be measured with a heuristic, and under 600/100 the answer was zero, because a
100-word overlap is longer than all but 20 of 5,936 procedure blocks (MIS-013,
DEC-039).

The re-run moved strict recall@5 from 0.405 to 0.410: six questions gained, five lost,
189 unchanged. Nine of the eleven flipped gold articles were longer than 512 words, so
they were chunked differently; they moved in both directions. Four fifths of the corpus
is one chunk under either setting, which bounds what any chunking change can do here
(EXP-0003).

### Five documents, not five chunks (EXP-0004)

Gold is document-level and forty `dev` questions need two or three articles. A context
of five chunks can hold two articles. So `top_k` became five *distinct documents*,
found by walking the ranking with a fifty-chunk cap, and the number of chunks scanned
per document found — the collapse ratio — became a recorded metric (DEC-040).

Measured on BM25, the ratio was 1.088 on average and 1.20 at the 90th percentile: on 138
of 200 questions the top five chunks already were five articles, and the deepest walk
read fourteen chunks. The cap was never reached. The premise that chunk collapse
"structurally caps" multi-document recall turned out to be small on this corpus,
because most ranked chunks are whole short articles. Retrieval metrics were identical
to EXP-0003 by construction, and I checked that rather than assumed it (EXP-0004).

### Dense retrieval versus BM25 (EXP-0005)

One embedding model, `qwen3-embedding-8b`, hosted on OpenRouter and pinned to a single
provider after a probe showed two providers returning different vectors for the same
text (DEC-041). Index: 8,218 chunks, 4,096 dimensions, 135 MB, twenty minutes and three
cents to build, cached under a key made of the corpus hash, normalisation, chunker,
model, provider and prefix convention. The handover had suggested a local bge-base or
e5-base model; both cap at 512 tokens and 37% of the chunks are longer than that, so
that route would have truncated a third of the index silently.

Dense retrieval found all the required articles for **71.5%** of `dev` questions
against BM25's 41.0% — 70 questions gained, 9 lost, 121 unchanged. The number of
questions with nothing useful in the top five fell from 99 to 37. Every slice moved,
single-document questions most (0.469 → 0.806) and multi-document least in absolute
terms though it doubled (0.175 → 0.350). Of the gold documents dense still missed from
its top five, 62 of 64 were inside its top hundred; BM25's misses were a third outside
the top hundred. The nine losses were all short exact-term questions — *PDF Viewer
App*, *Header Scroll Effects* — where BM25 had the article at rank one to five and
dense put it at six to thirty-three.

Because the query embeddings come from a hosted service, I ran the configuration twice
more against the cached index. Only 38–47 of 200 full rankings came back identical,
but the top-five sets did on 183–188, and strict recall@5 moved by one question. The
0.305 gain is sixty times that spread (EXP-0005, OQ-023).

### The end-to-end control (EXP-0006, EXP-0007)

With one frozen prompt — numbered steps for how-to questions, English, a citation on
every claim, no links, a fixed refusal phrase (DEC-042) — the dense control was run
through generation on the hundred-question subsample and on the 45 unanswerable
questions.

Citation precision was 0.550 and recall 0.608. Split by what the generator was given,
the picture is sharper: with every gold article in its context, precision 0.654 and
recall 0.813; with one missing, 0.323 and 0.192 — and on 30 of those 33 questions it
answered anyway, from whatever five articles it had. Zero answers contained a URL
(EXP-0006).

On the unanswerable questions the system refused 33 of 45. It refused every question
about another platform (Shopify, Squarespace, Webflow) and 13 of 15 about events after
the corpus snapshot. The twelve false answers are almost all *underspecified*
questions — "How do I fix it?", "Why was my account charged?" — where the retriever
returns five plausible articles and the generator treats their presence as the
answer, with citations. That 12 in 45, and 10 in 15 on the underspecified third, is
what Phase 2's refusal logic is measured against (EXP-0007).

Then the same Tier 2 configuration was run three times unchanged to measure its noise
(DEC-046). The judge was quieter than on the Phase 0 configuration at the corpus
level — faithfulness moved 0.013 between runs of nothing — but the generator's
citations were not: citation precision came back 0.550, 0.478 and 0.546, so a
citation-precision difference under 0.08 on this control is noise. Step coverage's
floor is still a third of its own value. On the multi-document slice, faithfulness
has a minimum detectable difference of 0.112 at n=26; small slice effects are not
readable there. The full table is the standing reference every later scorecard
carries (P1-11).

### Embeddings: four models, one control kept (EXP-0008 to EXP-0013)

Before the first Phase 2 axis ran I built the discipline it needed: a paired test for
deterministic metrics (`rag compare`, DEC-047), noise-floor labels for judged ones
(DEC-048), a generation cache for any model call inside retrieval (DEC-049), a
committed "current best" that only a checked promotion can move (DEC-051), and a cost
gate that estimates the corpus-embedding bill before a byte is sent (DEC-052). The
first axis then spent most of its value on two things I had not planned to measure.

The plan was to decide embedding models on `dev_large`, 6,221 questions, for
statistical power, and confirm on the 200-question `dev`. The control's first run on
`dev_large` showed the split had no multi-document questions at all and the control
already at 0.973 strict recall@5 there (EXP-0008). I had encoded a decision rule
without counting the slice it was for — the first item on my own preflight list
(MIS-021). The second candidate made it worse than an oversight: `bge-m3` gained on
`dev_large` (+0.005, p = 0.019) and lost 40 of 200 questions on `dev` (−0.160,
p = 0.0001; EXP-0010). Synthetic questions reuse their article's wording, and a model
that tracks wording is flattered by them. Krutik moved the decision to `dev` (DEC-055).

On `dev` no model beat the control. `text-embedding-3-large` was a null (−0.005,
p = 1.0; EXP-0009). `gemini-embedding-2` was the only one to improve ordinary articles
on `dev_large` and it lifted nDCG@10 on `dev` by 0.066 (p = 0.002), but changed which
questions had every gold document in the top five by six of two hundred (p = 0.41;
EXP-0011). Under the new rule that is "no measurable difference", and I filed the
ordering gain for the reranking axis rather than pay 20x per token for it (OQ-027).
Truncating the control to a quarter of its width was a null on both splits
(EXP-0013), which also settled that `bge-m3`'s deficit was the model, not its 1024
dimensions.

The one finding that changed how I read the others came from a probe. All three
candidates had fixed the same 66 synthetic questions — "Can I do X?" questions whose
gold is a *Request:* article for a feature that does not exist, where the control
returns the how-to for the nearest feature that does. The control's query prefix tells
the model to retrieve passages that *answer* the query. Removing it recovered 53 of the
66 on `dev_large` and cost six points of strict recall@5 on `dev` (p = 0.035;
EXP-0012). So four fifths of every candidate's apparent gain on the large split was the
absence of an instruction that is worth six points on real questions. The prefix
stayed; the axis closed with the control unchanged and $1.17 spent.

## 5. What actually moved the needle

One experiment is a technique comparison in this phase; the rest are the control
being built. Ranked by measured strict recall@5 on `dev` (n=200), against cost and
latency:

| Change | strict R@5 | Δ vs sparse control | Spread | p95 latency | Cost | Ref |
|---|---|---|---|---|---|---|
| Dense retrieval (`qwen3-embedding-8b`) over BM25 | 0.410 → **0.715** | **+0.305** (61 questions) | 0.005 | 34 ms → 665 ms | $0 → $0.0000004/query + $0.03 index | EXP-0005 vs EXP-0004 |
| Chunking 512/0 → 600/100 (BM25) | 0.405 → 0.410 | +0.005 (1 question) | 0 | — | $0 | EXP-0003 vs EXP-0001 |
| Whole documents instead of 512-word chunks (BM25) | 0.405 → 0.410 | +0.005 | 0 | — | $0 | EXP-0002 vs EXP-0001 |
| Five distinct documents instead of five chunks | 0.410 → 0.410 | 0 (identical by construction) | 0 | — | $0 | EXP-0004 vs EXP-0003 |

One thing moved: the retriever. Everything on the chunking axis was within one
question, and the document-level walk changed what a generator sees on 62 of 200
questions without changing a retrieval number. No generation technique has been
compared yet — the Tier 2 rows are the control, not a treatment.

## 6. What did not work, and what that suggests

**Chunk size, twice.** Whole documents (EXP-0002) and 600/100 (EXP-0003) each moved BM25
by one question against 512/0. The corpus profile explains the flatness before any
sweep is run: four fifths of the articles fit in a single chunk at any of those
settings, so the chunker only touches the long fifth, and those articles moved in both
directions. A Phase 2 chunk-size sweep on this corpus will be a flat line on
single-document questions unless it changes something other than width; I know that
now rather than after the sweep (OQ-003).

**The premise that chunks collapse into documents.** The handover expected a naive
top-five-chunk retriever to be capped by adjacent chunks of one article; the measured
collapse ratio was 1.09 under BM25 and 1.11 under dense, with no question exhausting
the pool (EXP-0004, EXP-0005). The document-level walk was the right thing to build —
it costs nothing and makes the context semantics honest — but it is not where the
multi-document problem lives. Dense retrieval still finds all the required articles
for only 14 of 40 multi-document questions; it finds *one* of them for 34. The second
document is a ranking problem, not a granularity problem.

**"BM25 is a serious opponent on this corpus."** It was not, at the document level:
dense won every slice by 0.175 to 0.371 and lost nine individual questions. What
survived of the premise is those nine — short questions carrying one exact product
term. Whether a hybrid recovers them without losing the seventy is exactly the kind of
question that gets a run, not a guess (OQ-001's family).

**Two instruments, before any technique.** The citation parser dropped a citation
shape the model uses (MIS-016) and the refusal detector could not read a curly
apostrophe (DEC-045). Neither is a technique result, but both cost historical numbers
their first decimal, and both are recorded as corrections rather than overwritten.
The lesson is in section 9.

## 7. Where the system still fails

Seven categories, each named from a run rather than in advance, with the questions
that define them, live in `FAILURES.md`. The three that matter most, by count:

- **Answered on a retrieval miss** — 30 of the 33 `dev` questions whose gold article
  was not retrieved got a confident, cited answer from the wrong articles (EXP-0006).
  The retriever is the largest source of wrong answers and the generator hides it.
- **Answered an unanswerable question** — 12 of 45, ten of them underspecified
  (EXP-0007). The system has no way to say "which one?".
- **Refused with the answer in context** — 2 of 67 (EXP-0006). Rare, and each was the
  model wanting a closer wording match than the reference needed.

Two are measurement failures rather than system failures and are tracked as such:
step coverage of zero on a correct-looking procedure because the reference's steps sit
under headings the matcher does not see (OQ-007), and the prompt's own instruction
text echoed into two answers (a `v2` prompt item, DEC-042).

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

> **CORRECTED by DEC-045 on 2026-09-13.** The "2%" and "58 of 60" above were what the
> refusal detector could see, and it could not see much: its patterns matched `don't`
> while the model wrote `don’t`. Re-run over the same stored answers with the fixed
> detector, that run refused **20 of 100** questions, **17 of them on the 60 retrieval
> misses** — so the generator answered anyway on 43 of 60, not 58. Nothing about the
> system changed; the instrument did. The point of the paragraph stands, at a smaller
> size, and the lesson it actually taught is the next one.

**Test every parser of model output on model output.** Twice in Phase 1 a metric was
wrong because the code that read the model's answers was written against the format
the prompt *asked for* rather than what the model *produced*. The citation parser
matched `[doc:id]` exactly and dropped `[doc: id]` with a space — 4 to 13 citations per
hundred answers (MIS-016, DEC-043). The refusal detector matched straight apostrophes
and the model used curly ones — 13 to 18 refusals per hundred answers, invisible
(DEC-045). Both were found by reading answers in full, not by looking at a table, and
both fixes moved historical numbers: citation precision on the Phase 0 baseline went
0.388 → 0.383, its refusal rate 0.02 → 0.20, and the run-to-run floor for refusals
0.010 → 0.060. I recorded those as corrections beside the originals rather than
overwriting them, because a reader of the earlier rows needs to know which parser
produced them. The rule now in the preflight list: count what the parser drops on
stored output before trusting any number it feeds, and version the parser on every
run so a change in it is visible in the results store.

**Fail at the unit that failed.** A hundred-question judging run was voided by one
question's structured output overflowing a token budget. Judging one question never
depends on another; the honest record was "this criterion could not be scored here",
not "this run did not happen". Two voided runs taught that (MIS-010, MIS-011).

**Measure the instrument before you measure with it.** This one cost the most and
taught the most, so it gets the full story.

The judged metrics — faithfulness, answer correctness, answer relevance — come from
an LLM reading each answer and forming a judgment. The first Tier 2 run took 156
seconds per question, and I wrote that up as the judge model being slow (DEC-031).
It was not. Instrumenting every HTTP call showed the model returning 460 tokens in
1.6 seconds when I called it directly; the time was going to OpenRouter routing the
same model to whichever of twenty-two providers it liked, with a 37× spread between
the fastest and slowest (DEC-032). Pinning two providers and judging concurrently
took it to 12 seconds a question. Then I discovered I had pinned the most expensive
provider of the twenty-two without checking, and the cost estimate I had built was
reading the wrong price and printing $0.00 for runs that cost $0.04 (DEC-034,
DEC-035). Each of these was found by measuring the thing I had just assumed, and
each is in `MISTAKES.md`.

But the finding that changed how every later number gets read was smaller and
quieter. Along the way, one identical answer scored 1.00 on one provider and 0.857 on
another. Two runs of the same configuration on the same twenty questions gave
faithfulness 0.728 and 0.724. If the judge moves when nothing changes, then a
technique that moves faithfulness by 0.03 has not necessarily done anything — and I
had no idea whether the judge's own wobble was 0.003 or 0.3.

So before Phase 1, I measured it. Three identical runs of the baseline's Tier 2
configuration on the same hundred questions, then the same hundred answers judged
three times with nothing else changing. The spread across identical runs was 0.031
for faithfulness, 0.010 for correctness, 0.031 for relevance — and re-judging
byte-identical answers reproduced almost all of it. The generator turned out not to
be deterministic either: zero of a hundred answers came back identical across runs.
But its variation barely touched the aggregates. The noise was the judge, changing
its mind about the same answer. On twelve questions in a hundred it changed its mind
by a quarter point or more (DEC-037).

Two consequences. First, those spreads are now the floor: a judged difference inside
them is written as "no measurable difference", and `rag diff` says so automatically
rather than leaving it to whoever is reading. Second, one metric did not survive the
measurement. Step coverage's run-to-run range was 0.064 against values between 0.08
and 0.14 — the noise is half the signal, so as built it cannot detect anything, and
it is reported as such rather than as a number. What it cost: about three hours of
wall clock across the false starts, roughly four dollars, and eleven entries in the
mistakes ledger. What it bought: the right to interpret a judged number at all.

The transferable part is not "LLM judges are noisy" — that is well known. It is
that the noise has to be *measured on your judge, your prompt, your questions*
before the first comparison, because the figure is specific to all three, and
because the cheapest time to learn it is before you have written a results table
against it.

## 10. What remains untested

Every retrieval technique — that is Phase 1. Within Phase 0 itself, the open questions
that gate what the numbers can be trusted to mean:

- ~~The judge's own noise (OQ-017).~~ Measured: faithfulness and relevance range
  ~0.03 between identical runs, correctness ~0.01, almost entirely the judge
  (DEC-037). Now the floor every judged delta is read against.
- **Whether step coverage measures the answers or the matcher (OQ-007).** The
  lexical matcher misses paraphrases; the proportion of misses is unknown.
- **Whether refusal metrics should condition on retrieval (OQ-019).** As defined,
  they do not, and the ungrounded-answer rate has no metric. Since DEC-040 the
  per-question fact needed (`gold_in_context`) is recorded, so the redefinition is a
  decision, not a re-run.
- **Whether the refusal detector agrees with a human beyond 45 answers (OQ-008).**
  Version 2 agrees with my reading of all 45 unanswerable-split answers (DEC-045); that
  is one reader and one split.
- **Whether `feature_request` articles act as distractors (OQ-006).** A third of the
  index is never a right answer for any `dev` question.
- **Whether the unanswerable set is detectable by keyword rather than grounding
  (OQ-004)**, and — before any of that — whether its 45 questions survive a human
  read. They were LLM-drafted and have not been verified.

The full list, each with the decision rule that would settle it, is in
`OPEN_QUESTIONS.md`.
