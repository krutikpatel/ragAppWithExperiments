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

### Retrieval method: RRF, then a four-point alpha curve (EXP-0014 to EXP-0018)

The Phase 1 handover had said this corpus favours lexical matching — enterprise
knowledge-base text full of exact product names — and the dense-versus-BM25 run had
narrowed that to nine questions BM25 won and seventy it lost (EXP-0005). The
retrieval-method axis asked whether fusing the two rankings could keep the nine
without giving back the seventy. It is the cheapest axis in the program: no
re-index, no model calls, $0.00008 a run.

I built one hybrid retriever with two fusion rules and fixed their definitions before
running anything (DEC-056): Reciprocal Rank Fusion at the paper's k = 60, and a
weighted sum of min-max-normalised scores with `alpha` on the dense side, swept at
0.2 / 0.4 / 0.6 / 0.8 and not refined afterwards. I also wrote down what I expected
(H-010 to H-012): no hybrid would clear the paired test, the curve would rise with
the dense weight, and BM25-only documents would rarely reach the context.

RRF lost twelve points of strict recall@5 (0.720 → 0.600, p = 0.0012; EXP-0014). The
reason was legible in the ranks: 22 of the 38 questions it lost had a gold document
that BM25 did not return in its top hundred at all, and under RRF a document in one
list scores below almost anything in both. RRF is a consensus rule; it rewards
agreement, and on this corpus the two retrievers agree on about a fifth of their
candidates. It never lost a question BM25 had (38 gained, 0 lost against the sparse
control), which is the shape of a technique for adding dense to a lexical system, not
the other way round.

The alpha curve was monotone: 0.495, 0.590, 0.705, 0.730 against dense's 0.720
(EXP-0015 to EXP-0018). Its low end sat just above BM25, the middle two points
reproduced RRF (α = 0.4 and RRF agree on 190 of 200 questions), and the top two were
inside noise — α = 0.8 was six questions gained, four lost, p = 0.75, and `rag
promote` refused it. At that weight the lexical half could not introduce a document
dense had not already returned; every gain was a re-ordering of dense's ranks six to
nine, and every loss was a rank-five document nudged to six. The multi-document slice
did not move at any point.

So the handover's premise was right about the corpus and wrong about what it buys:
exact product names make BM25 a strong competitor on a dozen individual questions and
a weak retriever overall, and the fusion weight large enough to recover the dozen is
the weight that starts losing the seventy. I recorded the axis as five negatives and
nulls, kept the dense control, and spent under a cent.

### Chunking: four ways to cut, and a fifth run that measured the ruler (EXP-0019 to EXP-0023)

This was the axis I expected to be boring. The corpus profile said 79% of articles fit
inside a single 600-word chunk, so for four fifths of the corpus a chunker has nothing
to change, and two chunk-size changes under BM25 had each moved exactly one question
(EXP-0002, EXP-0003). I wrote that expectation down (H-013) and it held — but not for
the reason I gave.

Two free checks before any code: the frozen text has **no headings at all** (0 of 6,221
articles), and a third of its sentence boundaries are glued together with no space
("…your account.Before you begin:…"). So "structure-aware splitting on headings" had
nothing to split on, and any sentence-based chunker needed a splitter that knows
"account.Before" is two sentences. I redefined structure-aware on the corpus's own line
structure — cut at line ends, never between a "To do X:" header and its steps — and put
that, plus dropping late chunking (no hosted endpoint returns the token-level
embeddings it needs), to Krutik as a scope change (DEC-057).

Then the results. Nothing beat fixed 600/100. Ordered by how finely each chunker cuts:
parent-document 0.695, semantic 0.675, structure 0.665, sentence-window 0.530, against
the control's 0.720. The two coarse ones are inside the noise; structure-aware is a
five-point loss (p = 0.033); sentence-window is a nineteen-point loss (p = 0.0001) and
the largest negative in Phase 2 — for a 196,133-row index that took 2.8 hours to build
and 3.2 GB to store, against the control's 8,218 rows and 135 MB.

The mechanism is the same in every case and it is not about chunk size as such. A
document's score is the best of its chunks (the pooling rule fixed in Phase 0), so
cutting an article into pieces makes each piece weaker while rival articles keep one
strong piece. Over and over the candidate pool held several chunks of the right
article — the retriever had it — and still ranked it sixth: *"remove the ribbon from one
plan"* had seven chunks of one gold and four of the other in the pool and fell from
ranks 1,3 to 1,7. That is filed as a failure category of its own (F12). What finer
chunks *do* buy is the exact-term question — *"add a full PDF to my portfolio site"*
went from rank 9 to 1 under three of the four chunkers — the same dozen questions BM25
won in Phase 1 and fusion recovered in Axis 3. Ten questions gained, forty lost.

The fifth run is the one I would keep if I could keep only one. Every chunker rebuilds
the index, and re-embedding the same text on a hosted provider does not return the same
vectors — an earlier probe had found only 59% byte-identical. So I ran the control
again with a single change: write the index to a new directory, forcing a fresh embed of
the identical chunks. **Two questions of 200 flipped**, both from rank 5 to rank 6, with
zero multi-document flips and nDCG unchanged to four decimals (EXP-0023). That number
is what makes the rest of the axis readable: a 21-flip config is churn, a 48-flip config
is a real loss, and a caution I had written into the structure-aware writeup — that
maybe half its losses were just re-embedding noise — was wrong and is corrected there.
Measuring your own instrument costs three cents and it is the difference between a
result and a guess.

Two things also went wrong and are worth stating. The provider began rate-limiting us
mid-batch; our retry waited 2, 4, then 8 seconds, which is nothing against a per-minute
quota, and two experiments died — one of them 42 minutes into a build (MIS-024). The
bookkeeping held: both attempts are VOID rows in the ledger rather than gaps, and the
semantic chunker's boundary cache meant its re-run embedded 50,852 sentences instead of
196,000. The fix gives rate limits their own schedule and honours the provider's
`Retry-After`.

### Reranking: the one that moved everything and changed nothing (EXP-0024)

A reranker is the standard next move, and the reason it is standard is easy to state.
The dense retriever turns the question into a vector and the article into a vector,
separately, and compares them — it never actually reads one against the other. A
cross-encoder does: question and passage go through the model together. That is much
more accurate per pair and far too slow to run over 6,221 articles, so it only ever
re-orders a short candidate list. Which also caps it: it cannot find anything the
retriever missed.

I wrote down two expectations first (H-017, H-018). The first was that this would be
the axis that finally produced a positive result, because every technique so far had
changed *what gets indexed* and this one changes *how the question is read*. It was
wrong. Strict recall@5 went from 0.720 to 0.665 — down — at p = 0.139, which the
paired test calls no measurable difference. Axis 5 joined Axes 1, 2 and 3 in the null
column.

What makes it interesting is where the movement went. The reranker was **better at the
top and worse in the middle**: +0.065 at rank 1, −0.055 at rank 5, and at rank 20,
**0.920 before and 0.920 after — p = 1.000, nine questions gained and nine lost.** I called that
last number the ceiling. It is not, and the next run proved it within the hour: a
reranker re-orders the top **50** documents, so a gold sitting at dense rank 21–50 can
be lifted into the top 20, and `rerank-4-fast` lifted eight, reaching 0.940. The
ceiling is the candidate set's own recall — **strict recall@50 = 0.985** — and I had
not measured it before generalising from one run (MIS-029).

That number is worth more than the mistake cost. The gold document is already in the
50-document candidate set for **98.5%** of questions; the best reranker put it in the
top five for **73%**. So the remaining errors at this depth are not retrieval failures
at all — the right article is in hand almost every time — they are ranking failures,
and two different cross-encoders both declined to fix them.

Underneath the flat aggregate there was a great deal of motion. Tracking where the
gold document went on the 160 single-gold questions: it moved up a rank band on 40 of
them and down on 39. The five-document context changed for 194 of 200 questions, a
mean of 2.28 documents replaced. The null is not the reranker declining to act; it is
a lot of acting that cancels.

Reading the 45 questions that flipped is where the axis earned its keep. The rescues
are striking — *"do I have to give my login to a website designer to work on my site"*
went from rank 33 to rank 2, *"i cant create a new gallery in my website"* from 24 to
1, *"Hoe can I restore the selection of projects…"* from ranks 6 and 20 to 1 and 2.
These are questions with typos, loose phrasing, a complaint instead of a query — the
cases where comparing two separately-made vectors does badly and actually reading the
question helps. The losses are the mirror image and they are not near-misses: *"how to
add more static pages to a Wix website"* fell from rank 1 to 8, *"How to make the
published changes draft?"* from 5 to 20. Three of the six losses I read started at
rank 1. Well-formed questions the retriever had already answered, demoted confidently
by six to sixteen places.

The tempting story is "cross-encoders rescue badly-phrased questions and disturb
well-formed ones", and it would be a genuinely useful finding, because it says *when*
to pay for a reranker rather than whether. But the slices that should support it do
not: expert-written and simulated questions moved −0.040 and −0.070, both flat, both
indistinguishable. So it stays a hypothesis with a test attached (OQ-037) instead of a
conclusion, and the test needs 200 questions hand-labelled for phrasing *before*
anyone looks at the result.

One thing I predicted and got backwards for an instructive reason. P2-10 warns that a
cross-encoder can re-concentrate the context onto a single article and undo the
document diversity the retriever was configured for, and I expected exactly that. The
collapse ratio went 1.106 to 1.113. Nothing happened — not because the reranker
resisted, but because 79% of articles on this corpus are a single chunk, so there is
usually no second chunk of the same article available to promote. The prediction was
about the technique; the answer was about the documents. That keeps happening here.

The cost is the part that transfers. Median latency went 298 ms to 1,194 ms and the
per-query price from $0.0000004 to $0.00117 — roughly 2,900 times — to buy nothing
measurable. Reranking is also the first thing in this project billed *per question*
rather than per corpus: an index is paid for once, a reranker charges again for every
query, so the identical configuration is $0.23 on the 200-question dev set and $7.28
on the 6,221-question one. Which is why, when nothing won, the confirmation run on the
larger split was simply not bought.

Three smaller things went wrong and are logged. The pricing listing reports **$0 for
every rerank model on OpenRouter** while the calls bill real money, which would have
told the $2 spend gate this entire axis was free (MIS-025) — caught by sending one
real call and reading the response before writing the estimator. The first attempt
died because the shell I launched from had never loaded the API key; nothing was spent
and the runner filed it as a VOID row rather than a gap (MIS-026). And I edited a
documentation file while the run was starting, which stamped `git_dirty` on a row that
cannot be un-stamped — the rule I broke was one I had quoted in the previous commit
(MIS-027).

So I ran a second one, and it was worth doing. `cohere/rerank-4-fast` — same
candidate set, same 50 documents, same everything but the model — scored 0.730 where
v3.5 scored 0.665. Against the control that is +0.010 at p = 0.887, another null.
Against **v3.5** it is **+0.065 at p = 0.039**: significant. Two cross-encoders, an
identical candidate set, and they disagree with each other more than either disagrees
with doing nothing. On the multi-document slice the spread is wider still — 0.300
against 0.475 — though on 40 questions that is a suggestion, not a result.

That is the methodological point of the whole axis, and it nearly did not get made.
Had I stopped at EXP-0024 I would have written "a cross-encoder does not help on this
corpus" and it would have read as a finding about reranking. It was a finding about
one model. The second run cost $0.45 and changed what the first one meant.

`rerank-4-fast` is not really *better* at the task, either. Tracking the gold's rank
band: v3.5 moved 40 up and 39 down, `4-fast` 39 up and 32 down. The gains are the
same; `4-fast` just destroys less. Both still demoted golds out of rank 1 and both
replaced more than two of the five context documents on nearly every question.

The third reranker took two attempts. `qwen/qwen3-reranker-8b`, the open-weight
contrast, died on its first call with `HTTP 402: Insufficient credits` — the account
ran dry mid-batch (MIS-031). Every cost control in this project is per-run and none of
them knows whether there is money in the account, which is how a run got approved,
estimated, gated and started before hitting a wall the gate could not see. Nothing was
billed, the row is VOID rather than missing, and it ran properly once the account was
topped up.

It was worth the second attempt, and not for the reason I expected. Its strict
recall@5 was **0.7200 against the control's 0.7200 — a delta of exactly zero, p =
1.000, with 26 questions gained and 26 lost.** That is the cleanest null I have ever
produced and it is not an inert component: it changed the retrieved set for a quarter
of the questions and the metric did not notice.

What makes it useful is that it is *unlike* the other two. Both Cohere models sharpen
the very top and lose ground in the middle. This one does the opposite — it is the only
reranker that was **worse** at rank 1 (−0.020), and the best at depth: recall@10 +0.030
and **recall@20 = 0.950**, the highest any configuration in this project has produced.
Three cross-encoders, one candidate set, three genuinely different behaviours, and the
identical verdict on the deciding metric. A null that survives three different
behaviours says something about the corpus; three repetitions of one behaviour would
have said something about a model.

And it cost the most of anything here: **$0.00605 a query, about fifteen thousand times
the control**, with 31 transient retries against Cohere's one or two.

One question from this axis stayed open into Phase 3 and was bought just before the
baseline was frozen: does the reranker do better with **fewer** candidates, or more?
Phase 2 had only ever handed it 50. I ran `rerank-4-fast` at 20 and at 100 candidate
documents (EXP-0052, EXP-0053, $1.25 together). Strict recall@5 came out **0.750, 0.730
and 0.715** at 20, 50 and 100 — falling in order, and not separable: 20 against 100 is
−0.035 at p = 0.119, and neither run is distinguishable from plain dense search.

Reading the 15 questions that changed showed why the averages stay flat. Two real effects
cancel. Fewer candidates lose the questions whose answer dense search had buried at rank
24–33, because the reranker never sees them. More candidates bury answers dense search
had ranked well: "Hi I would like to install blog" had its article at rank 1 under dense
search and at 5, 8 and 13 after reranking 20, 50 and 100 documents. So "no measurable
difference" here is not "nothing happened". It is two mechanisms of similar size pulling
in opposite directions, and on 200 questions I cannot tell which one is larger.

### The last question: is retrieval even the bottleneck? (EXP-0051)

One thing was left open at the end of the phase, and it was the largest measured effect
in the whole project. Showing the generator ten documents instead of five puts the
correct article in front of it far more often — 0.720 of questions at five, 0.850 at ten,
and that replicated on the held-out split. No technique across six axes moved anything by
more than three points; this moved thirteen.

But it was only ever an input-side fact. It said the right document was *present* more
often. Nobody had asked whether the answers got better.

They did not.

| | k=5 | k=10 | |
|---|---|---|---|
| Gold document in the prompt | 0.6700 | **0.8200** | +0.150 |
| Citation recall | 0.6100 | 0.5917 | −0.018, inside its noise floor |
| **Citation precision** | 0.5455 | **0.4604** | **−0.085, significant** |
| Generator input tokens | 264,581 | 481,190 | **×1.82** |

Fifteen more questions per hundred had their answer sitting in the context, and the
system cited it no more often — while attributing claims to the wrong article
significantly more.

The decomposition explains it completely, and the arithmetic closes to four decimal
places. Split the hundred questions by whether the gold document was newly available:

- the **fifteen** that gained it improved by **+0.2111** on citation recall
- the **sixty-seven** that already had it lost **0.0746**
- fifteen times 0.2111, plus sixty-seven times −0.0746, is −0.0183 per hundred — exactly
  the overall change

**The mechanism works.** Put the right article in front of this generator and it cites it
more; on the questions that gained their gold document, citation recall more than
doubled. **The distraction it causes is four and a half times larger by population.** The
sixty-seven questions that were already working got five more articles each, and those
articles were, for them, noise.

This reframes everything before it. Six axes failed to improve retrieval, and the natural
reading was that we had hit a retrieval ceiling — that the gold document simply was not
findable often enough. This run found it fifteen points more often than any technique had
managed, and the answers did not improve. **The bottleneck is not how often the right
document is retrieved. It is what the generator does with a context that contains it.**
The axes had not been failing to find headroom; they had been finding headroom the
generation step cannot use.

It is also the cleanest measurement of dilution in the project. Earlier evidence was
indirect — compression shortened the context and citation recall fell (EXP-0029);
enforcing citations made the model describe documents instead of answering them
(EXP-0039, EXP-0040). This one moves the dial in the *helpful* direction, confirms the
gain is real, and then shows it being spent.

I had written the prediction down first and got two of three parts right. The part I got
wrong is the finding: I predicted citation recall would rise, counted the questions that
would gain, and never asked what the same change does to the ones that were already fine.
Reasoning about a numerator while ignoring the population it came from is a mistake that
does not announce itself — the premise was correct and the arithmetic still went the
other way.


### Opening the test split, once (EXP-0046 to EXP-0050)

Two hundred questions were locked away at the start of the project and never looked at.
Every decision, every experiment, all fifty-eight runs, used the other two hundred. On
2026-09-26 the locked set was opened once, with a recorded reason, and nothing has been
changed since.

The reason for locking it is that scoring yourself repeatedly on the same questions and
adjusting until the number improves is memorising a practice exam. The held-out set is
the real exam, and it works exactly once — the moment you see the result and change
something in response, it becomes another practice exam.

**Fifty-eight runs against the same two hundred questions is the shape of programme that
normally produces a large optimism gap. It did not produce one here.**

| | dev | test | gap |
|---|---|---|---|
| **Dense control (= promoted), strict recall@5** | **0.7200** | **0.6800** | **−0.0400** |
| strict recall@20 | 0.9200 | 0.9200 | **0.0000** |
| Tier 2, gold document reached the generator | 0.6700 | 0.6700 | **0.0000** |
| Tier 2, refusal rate | 0.0800 | 0.0800 | **0.0000** |
| BM25 sparse control, strict recall@5 | 0.4100 | 0.3450 | −0.0650 |

Every gap, on every headline metric, both slices and both tiers, falls inside the
sampling noise of two independent two-hundred-question samples. Three came back
numerically identical.

**And the one finding this project ever established as significant got larger.** Dense
retrieval over BM25 was +0.310 on the development set and **+0.335 on the unseen one**,
with a confidence interval of [+0.243, +0.427]. The single real result transfers.

**Why the gap is small, and how we can tell it is not luck.** Overfitting has a
signature: the configuration that was *selected* degrades more than one that was not,
because it carries the noise that made it look good in the first place. The opposite
happened. **BM25 — which has no fitted parameters, was never tuned on anything, and was
only ever the thing dense retrieval was compared against — lost 0.065, while the promoted
dense configuration lost 0.040.** An unselected baseline cannot be overfitted, so its
larger drop is a property of the two splits differing. The selected arm moving *less*
than the unselected one is the cleanest evidence available that almost no selection
pressure was applied.

The ledger says why, and it is the least flattering explanation possible: **selection
never operated, because nothing was ever selected.** Every axis returned "no measurable
difference" or worse. The rule — promote only on a significant positive — fired zero
times across six axes and forty-five runs. `promoted.yaml` carries the same identity hash
today as the day it was written. **A configuration that was never chosen for its
development score cannot have been overfitted to it.** Fifty-eight runs bought knowledge
about techniques and did not buy a tuned configuration, which turns out to be the one way
to run fifty-eight experiments on two hundred questions and not pay for it at the end.

I had written the prediction down before opening the split, and got the dense arm and the
headline finding right and the sparse arm wrong — by exactly the margin I had named as
the thing that would show my reasoning was wrong. I had attributed the expected gap to
the four or five choices made on the development set in Phase 1. The arm with *no* such
choices moved furthest, so that account was incorrect: the gap is the two splits
differing in difficulty, not the configuration fitting its questions. Being wrong there
makes the result stronger than my reasoning deserved.

**The project's headline number is strict recall@5 = 0.68 on two hundred unseen
questions**, not 0.72 on the set it was developed against. The test split is now spent;
any future work needs a new one.

One last thing surfaced in the final hour, and it is worth recording because of when it
happened. The suite went red: an answer on the test split was flagged as containing a
URL, which the prompt forbids. It did not. The answer correctly told a user to *"remove
http:// and replace it with https://"*, and the detector had matched a bare scheme with
no host — the fourth parser in this project to be written against the format its author
imagined rather than the text it would meet. Correcting it would make a test-split number
look better, after the split had been opened, which is the exact shape of thing the rules
forbid. So it was put to Krutik before anything was touched, fixed as a measurement bug
with the timing disclosed, and the record shows what changed: one verdict out of 1,638
stored answers, no system file, and no number appearing in any comparison.


### Grounding: four ways to stop the system answering what it cannot (EXP-0038 to EXP-0041)

Axis 7 is the one that matters commercially. Everything before it asked whether the right
article was found; this one asks what the system does when there is no right article. The
corpus cannot answer 45 of the questions put to it, and the Phase 1 control answered
**27%** of them anyway.

That baseline number took a correction before the axis could start. The ledger said 42%,
because the row was written by a refusal detector that missed the model's curly
apostrophe — a bug fixed months earlier by DEC-045 for all *future* runs, with the
affected historical numbers left standing. Recounting the stored answers put the real
figure at **0.2667**. A stale row does not look stale; it looks like a measurement, and
the next story anchors to it.

**The free win came from the cheapest possible mechanism (EXP-0038).** Before calling the
generator at all, look at the top retrieval score; if it is below a threshold, decline.
No model call, no latency, and — because per-question scores are recorded on every row —
**every threshold could be evaluated exactly from two runs already on disk, for nothing.**

The curve is the deliverable, not a point on it:

| Threshold | False answers | False refusals | Questions still answered |
|---|---|---|---|
| none | 0.2667 | 0.0299 | 93% |
| **0.575** | **0.1333** | **0.0299** | **93%** |
| 0.625 | 0.0667 | 0.1045 | 85% |
| 0.750 | 0.0000 | 0.5224 | 43% |

At 0.575 the false-answer rate **halves and nothing is paid for it**: no false refusals,
no questions lost. Every unanswerable question it newly declines scored below every
answerable question's top score. Past that the trade turns steep — the next halving costs
three and a half times the false refusals — and eliminating false answers entirely would
mean declining more than half the questions the system can actually answer.

That became the operating point, on the reasoning that for a support assistant a false
answer is worse than a false refusal and not symmetrically so. A refused user goes to a
human and still gets a correct answer; an over-answered user changes a setting on a live
site on the strength of a confident, cited paragraph that is wrong. Because the system
cites its sources, a wrong answer arrives wearing the appearance of evidence. But "worse"
is not "worth any price", which is why the point sits at the last free spot on the curve
rather than deeper in.

**The two citation experiments went spectacularly the wrong way (EXP-0039, EXP-0040).**
The obvious lever on grounding is to demand citations harder. One prompt made a citation
a precondition for writing a step; another required the model to quote the exact words it
relied on. Both **tripled** the false-answer rate — 0.2667 to **0.8444** and **0.8889** —
and drove refusals to **zero across 145 questions**.

The mechanism is worth stating carefully, because it generalises. Told that every step
must carry a citation, the model does not refuse more carefully. It writes a numbered,
cited sentence *about* a document: *"1. The provided articles cover currency changes for
Wix products, not Squarespace."* That is cited, formatted, confident, and not an answer to
the question — and every metric that counts refusals scores it as an answer, as would a
user. **A citation requirement is a formatting requirement, and a model can satisfy it
without being grounded.** Step coverage measured the same thing from the other side: it
fell from 0.193 to 0.033 and 0.019, the two lowest figures in the project. The answers had
stopped being procedures and become descriptions of sources.

Span-level citation added a second finding. Its whole appeal is that a quote is checkable
where a document id is not — so I checked, and **one quoted span in five does not appear
in the document it is attributed to**. Support was 0.796 on answerable questions and 0.743
on unanswerable ones. The technique produces a verifiable artifact and then fails its own
verification 20% of the time, while document-level citation precision falls 0.110 as well.
A reader who trusts the quotes ends up worse informed than one who only had document ids.

**The self-check was beaten by the free option (EXP-0041).** A second model — from a
different family, deliberately, so it was not grading its own lineage — read each answer
against its context and replaced unsupported ones with a refusal. It worked mechanically:
zero unparseable verdicts, zero failed calls, every existing refusal short-circuited
without a call. It reduced false answers from 0.2667 to 0.2222 and raised false refusals
from 0.0299 to 0.1212, at **4.6 seconds per answered question**. Of the twelve answers it
rejected, **six had the gold document sitting in the context**. It rejects about as much
good work as bad — and the free threshold beats it on **both** axes at once.

**What the axis cost in instrument failures is the part I would tell another team.**
Three of the four techniques were measured through a broken instrument before they were
measured correctly. The stale detector version put the target 15.6 points off. The
citation parser matched span-form citations as *nothing*, so the span experiment's first
reading was "zero citations, every question" — a finding that would have been entirely an
artifact. And the refusal detector's rule of "a refusal has no numbered steps", calibrated
on a prompt whose refusals are bare sentences, inverted under prompts that *demand*
numbered steps: a refusal written as "1. The provided articles do not cover this" was
scored as an answer, and one experiment's false-answer rate read a perfect 1.0000.

Each was caught by the same reflex — a number too extreme to believe, checked against the
raw output. **A generation metric is calibrated against a prompt, and this was the one
axis whose entire purpose was changing the prompt.**


### Query transformation: four ways to ask again, and a rule about fusing (EXP-0031 to EXP-0034)

Axis 4 changes the question rather than the index. Four techniques, eight runs, and the
whole axis cost **two cents**. None of them won, two of them lost significantly, and
together they produced the clearest quantitative rule in the project.

**Decomposition was run first, and it supplies its own control (EXP-0031).** The model
splits a question into the sub-questions it depends on; each is retrieved for separately
and the rankings fused. Strict recall@5 fell 0.720 → 0.665, **p = 0.019**.

What makes this one unusually legible is that it declined to fire on most questions. Only
**50 of 200** were split; the other 150 came back as a single line, 145 of them verbatim,
and those reproduce the control almost exactly (0.713 → 0.707). All the damage is in the
50, and there it is severe: **0.740 → 0.540**, thirteen lost against three gained. Those
questions were not harder to begin with — their control recall was *above* the rest.

Before running it I wrote down that the risk was the sub-queries retrieving the *same*
documents, making the technique a no-op. The opposite happened: each extra sub-query
found **40.8 documents the others had not**. The decomposition works exactly as designed,
and that is why it fails. *"How can I add a personalized name to my automated emails? I
was advised to use dynamic values"* becomes two good questions. Each has its own
best-matching article. Neither is the gold, which answers both — and the gold falls from
rank 1 to rank 10. Reciprocal Rank Fusion reads ranks, so a document that is first for
one sub-question beats a document that is third for two.

**Decomposition assumes the corpus is indexed by sub-fact. A help centre is indexed by
task, and a user's multi-part question is usually one task.**

**HyDE was the only technique that did not fuse, and the only one that did not lose
(EXP-0032).** Instead of embedding the question, generate the help article that would
answer it and embed that. One query, nothing to fuse. Recall went 0.720 → **0.735**, at
p = 0.754 — no measurable difference, but the only positive direction in the axis. It
also produced the single most interesting slice result in the phase: `gold_docs:multi`
went **0.350 → 0.450**, seven questions gained against three lost. At forty questions
that is p = 0.35 and not a finding. It is also the only positive signal the
multi-document slice has shown after six techniques aimed at it, and it cannot be
settled by running bigger, because the large split's multi-document slice has no rows at
all. That one is written down as an open question rather than a result.

**Multi-query expansion produced the cleanest null the instrument can make (EXP-0033).**
Three paraphrases retrieved alongside the original: **delta exactly zero**, twelve
questions gained and twelve lost. But the slice underneath is not flat — short questions
fell **0.095 at p = 0.016, seven lost and none gained**. A short question is already
close to a bare keyword query, and three longer paraphrases pull the fused ranking off
the literal match with nothing ambiguous to resolve.

**Step-back prompting was the worst (EXP-0034).** Derive a more general question, retrieve
for both, fuse. Recall fell 0.720 → **0.645, p = 0.017** — twenty-five questions lost
against ten gained.

I had predicted this one would lose, from a six-question probe in which the model twice
invented "Wix Bookings" for questions that named no product. Across all two hundred that
defect runs at **23%**: *"How to make the published changes draft?"* becomes *"How does
Wix Bookings handle published changes draft?"*. The prompt tells it to keep the product
name; when there is none, it supplies one, and Bookings is its default guess.

But only **six of those forty-six** questions actually lost the gold. The defect I
predicted explains about a quarter of the damage. The rest is the same fusion problem
everything else in this axis hit: the general question retrieved **34.7 documents the
original did not**, doing precisely its job, and at equal fusion weight "best overview
article" outranks "good specific article" — while on a help centre the answer is almost
always the specific one.

**The rule the axis produced.** Order the three fusing techniques by how different the
extra query's results were, and the outcomes fall in step:

| Technique | New documents per extra query | Δ recall@5 | p |
|---|---|---|---|
| HyDE — *replaces* the query, no fusion | — | **+0.015** | 0.754 |
| Multi-query — 3 paraphrases | 16.8 | **0.000** | 1.000 |
| Step-back — 1 general question | 34.7 | **−0.075** | 0.017 |
| Decomposition — 1.3 sub-questions | 40.8 | **−0.055** | 0.019 |

**A second ranking does not add evidence to the first. At equal weight it competes with
it,** and the more genuinely different it is, the more damage it does. The only technique
that avoided this replaced the query rather than fusing with it.

Two things worth carrying forward. Every transform did exactly what it was asked —
sensible sub-questions, faithful paraphrases, a correctly more-general question, a
corpus-shaped fake passage, **zero fallbacks and zero failed calls across eight hundred
model calls**. This is not a story about a model disobeying; it is a story about four
reasonable instructions being wrong for this corpus. And three meaning-preserving
paraphrases retrieved nearly seventeen new documents each, which says this embedding
space is far more sensitive to phrasing than the words "semantic search" suggest. Two
separate hypotheses here predicted otherwise and both were wrong the same way.


### Context assembly: five ways to rearrange the answer, and what they taught (EXP-0027 to EXP-0030)

Axis 6 asks a different question from the rest. Every earlier axis changed what gets
*found*; this one changes what the found documents look like by the time the model
writes an answer. Five techniques, and between them they cost **$0.34**.

**MMR made things worse, monotonically (EXP-0027).** Maximal Marginal Relevance trades
relevance against diversity: it demotes a candidate that looks too much like one already
picked. It is the technique the phase handover singled out, on the reasoning that
diversity ought to help multi-document questions. It halved recall. Strict recall@5 went
0.720 → 0.685 → 0.570 → 0.360 → **0.335** as the diversity weight rose, every step worse,
and the multi-document slice — the one it was chosen for — went **0.350 → 0.000**, losing
fourteen questions and gaining none.

The cause was measurable rather than guessable. Two gold documents of the same question
are **+0.095 more similar to each other** than a gold is to an average candidate, because
they describe the same task. So the redundancy term punishes the second gold harder than
it punishes an irrelevant article. And candidate-to-candidate similarity has more than
twice the dynamic range of relevance in a candidate set, so below a moderate weight the
objective is effectively selecting semantic outliers. **On a single-product help centre,
being unlike the other candidates is evidence of irrelevance, not of novelty.** A run at
the identity setting reproduced the control exactly, so this was the technique and not
the harness.

**Lost-in-the-middle reordering did nothing, and the reason is a number (EXP-0028).** The
idea, from Liu et al. 2023, is that long-context models attend to the beginning and end
of a prompt and lose the middle, so the strongest documents should go at both ends. Every
deterministic generation metric landed inside its noise floor; the lowest p-value
anywhere in the per-slice breakdown was 0.106. The measured reason: this prompt averages
**2,174 tokens**, and the paper measured that dip across roughly 2,700 to 21,000 tokens
with ten to thirty documents. Five documents is not a long context. There was no middle
to get lost in.

It is not an inert component, though, which is the interesting part. Fifteen of a hundred
questions changed which documents they cited, and **thirteen of those had a byte-identical
retrieved set and ranking** — only the position in the prompt differed. Six improved,
seven worsened. One question flipped to the *opposite factual claim*: asked about
migrating a site between editors, the control said it was impossible and cited the article
that says so, while the reordered run described a migration path that same article says
does not exist. Same five documents, different order. That is worth knowing about a
generator even when the metric shrugs.

**Compression bought a 47% shorter prompt and paid for it in citations (EXP-0029).** An
extractive pass trimmed each retrieved chunk to the sentences bearing on the question.
The prompt fell from 1,712 to 912 words and from five documents to 3.13. Citation recall
fell **0.598 → 0.522, p = 0.036** — the only significant result in the axis, and negative.

The diagnosis is the part I would keep. The compressor is *good*: measured against the
labels it dropped 43.9% of non-gold chunks and only 8.7% of gold ones, a five-fold
discrimination ratio. It is genuinely reading the question. But of the seventeen questions
that lost citation recall, only six had a gold chunk dropped — **eleven kept every gold
chunk and lost the citation anyway**. The relevant sentences were still sitting in the
prompt. Shortening the document *around* them made the model less willing to cite it, and
the rate of citing nothing at all rose from 5.7% to 9.0% on the same retrieved documents.
**That is a fact about the generation step, not about compression**, and it would apply to
any technique that shortens a retrieved document in place.

**Contextual retrieval was inert exactly where the corpus said it must be (EXP-0030).**
This is the technique from Anthropic's September 2024 post, and the most expensive thing
in the phase: one model call per chunk across the whole corpus — 8,218 calls — writing a
sentence that situates each chunk inside its article, with the *prefixed* text indexed and
the original chunk still shown to the generator. Strict recall@5 went 0.720 → 0.725,
**p = 1.000**, sixteen questions gained and fifteen lost.

Before running it I wrote down that if the effect were real it should concentrate in the
21% of articles too long to fit in one chunk, since for the rest the prefix restates text
the chunk already contains — and that I cared about that split more than the headline. It
was the right thing to have written:

| Gold article | n | Control | Contextual | Δ | gained / lost |
|---|---|---|---|---|---|
| Fits in one chunk | 100 | 0.780 | 0.780 | **+0.000** | **4 / 4** |
| Spans several chunks | 100 | 0.660 | 0.670 | +0.010 | 12 / 11 |

The one-chunk half is *perfectly* inert — four up, four down, delta exactly zero. And the
dev split turns out to be **50% multi-chunk against the corpus's 21%**, because longer
articles attract more questions, so the technique was measured on a subset two and a half
times enriched for the condition it needs, and still returned +0.010.

Where it works, it works cleanly: asked *"do I have to give my login to a website designer
to work on my site"*, the control never surfaced the right article in five; the prefixed
index put it at rank 1, because the generated sentence named "collaborators" and "Roles &
Permissions" — vocabulary the question never used and the chunk never contained.

Why that does not add up to a gain is the lesson. The losses are **not** bad prefixes. One
gold article with an accurate, well-written prefix fell from rank 1 to outside the top
five. Every competing document was prefixed too, so the lift is near-uniform across the
index and relative ordering barely moves. I had framed the question as *does the prefix
add discriminating information?* The right question was *does it discriminate between
candidates?* A technique that improves every candidate equally cannot re-rank them.

At 6,221 articles this cost **$0.25** and twenty-one minutes. At six million documents the
same technique is roughly **$250 per index build**, repeated every time the chunking, the
prompt or the model changes. It is bounded and affordable here, and a standing budget line
there. That difference belongs with the result rather than in a footnote.


### Choosing a judge, and a check that failed its own labels (EXP-0054 to EXP-0057)

Phase 3 needed a faithfulness judge good enough to fail a build on. Before choosing one
I found that my existing judge was not independent of my generator. I had classed
`gpt-oss-120b` as a separate family from `gpt-5-nano` because its weights are open. Both
are OpenAI models, and the bias the different-family rule guards against comes from
shared training, not from how the weights are distributed. I reclassified family as the
training lab, which retired that judge and caveated the Phase 2 judged noise floors and
the Axis 7 self-check that had used a same-lab model (DEC-073, MIS-042).

The replacement was chosen by a bake-off on a synthetic check, with the pass bar written
down before any run: flag at least 95% of answers paired with unrelated articles, pass at
least 85% of expert answers paired with their own gold articles, and fail no more than 5%
of calls (DEC-076). Three judges from three labs ran it (EXP-0054–0056, $3.69). **All three
failed, the same way.** Each flagged every unrelated pair, and each passed only 35–40% of
the "known supported" ones.

The judges agreed with each other on 58 of 73 of those pairs, and that agreement was the
clue. Reading the answers they all rejected against their articles, the answers said
things the articles did not: one described group bookings while its gold article covered
multi-service appointments; another answered with the Layers panel while its articles were
about browser caching. The check assumed WixQA's expert answers are grounded in their gold
articles, and for about half of my slice they are not. The test was measuring the labels.

I kept the bar exactly as declared and rebuilt the supported pairs so they were true by
construction: three sentences copied from a gold article, against three copied from an
unrelated one, both judged against the same gold text (DEC-078). The cheapest judge,
`deepseek-v4.1-flash`, then flagged 80 of 80 foreign extracts and passed 72 of 80 genuine
ones, for $0.33 (EXP-0057). Five of its eight false flags came from my own extraction
cutting in FAQ questions and headings, not from the judge.

What this proves is narrow, and I have written it down as narrowly: the judge verifies
literal support and rejects foreign content. How it treats paraphrase, which is what a
generated answer is, remains unmeasured, and no human checked it.

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
| Hybrid dense + BM25, weighted α=0.8 (best of five fusion settings) | 0.720 → 0.730 | +0.010 vs dense control (6 / 4; CI [−0.020, +0.040], p = 0.75) | — | 635 ms → 625 ms | $0 extra | EXP-0018 vs EXP-0005 |
| Hybrid dense + BM25, RRF k=60 | 0.720 → 0.600 | **−0.120** vs dense control (14 / 38; p = 0.0012) | — | — | $0 extra | EXP-0014 vs EXP-0005 |
| Parent-document chunking (150-word children, 600-word parents) | 0.720 → 0.695 | −0.025 vs dense control (12 / 17; p = 0.46) | floor: 2 questions | — | $0.031 index | EXP-0020 vs EXP-0005 |
| Semantic chunking (95th-percentile boundaries) | 0.720 → 0.675 | −0.045 (6 / 15; p = 0.078) | floor: 2 questions | — | $0.008 + $0.031 | EXP-0021 vs EXP-0005 |
| Structure-aware chunking (line boundaries) | 0.720 → 0.665 | −0.055 (6 / 17; p = 0.033) | floor: 2 questions | — | $0.031 index | EXP-0022 vs EXP-0005 |
| Sentence-window chunking (1 sentence, ±3) | 0.720 → **0.530** | **−0.190** (10 / 48; p = 0.0001) | floor: 2 questions | — | $0.034, 2.8 h, 3.2 GB | EXP-0019 vs EXP-0005 |
| Cross-encoder reranking, 50 candidate documents → 5 (`cohere/rerank-v3.5`) | 0.720 → 0.665 | −0.055 vs dense control (17 / 28; CI [−0.120, +0.010], p = 0.139) | — | 635 ms → **2,727 ms** | **$0.00117/query** (~2,900x) | EXP-0024 vs EXP-0005 |
| Cross-encoder reranking, same 50 → 5 (`cohere/rerank-4-fast`) | 0.720 → 0.730 | +0.010 vs dense control (24 / 22; CI [−0.055, +0.080], p = 0.887); **+0.065 vs `v3.5`, p = 0.039** | — | 635 ms → **18,774 ms** | **$0.00224/query** (~5,600x) | EXP-0025 vs EXP-0005 |
| Cross-encoder reranking, same 50 → 5 (`qwen/qwen3-reranker-8b`, open weights) | 0.720 → 0.720 | **+0.000** vs dense control (26 / 26; CI [−0.070, +0.070], p = 1.000); best depth in the project (@20 0.950) | — | 635 ms → 9,372 ms | **$0.00605/query** (~15,000x) | EXP-0026 vs EXP-0005 |

One thing moved: the retriever. Everything on the chunking axis was within one
question, the document-level walk changed what a generator sees on 62 of 200
questions without changing a retrieval number, the embedding axis kept its control
(EXP-0008 to EXP-0013), the retrieval-method axis ranged from a null to a twelve-point
loss (EXP-0014 to EXP-0018), the chunking axis from a null to a nineteen-point loss
(EXP-0019 to EXP-0022) against a measured two-question noise floor (EXP-0023), and
reranking produced no measurable change at any depth while multiplying latency by four
and cost per query by roughly 2,900 (EXP-0024). No generation technique has been
compared yet — the Tier 2 rows are the control, not a treatment.

## 6. What did not work, and what that suggests

**Chunking, six times now.** Whole documents (EXP-0002) and 600/100 (EXP-0003) each moved BM25
by one question against 512/0. The corpus profile explains the flatness before any
sweep is run: four fifths of the articles fit in a single chunk at any of those
settings, so the chunker only touches the long fifth, and those articles moved in both
directions. The Phase 2 sweep then tested four real chunkers and none beat 600/100
(EXP-0019 to EXP-0022): what I got wrong in advance was assuming the curve would be
*flat* because most articles fit in one chunk — three of the four chunkers re-cut nearly
every article (semantic left 2.9% whole, sentence-window 0.5%), so the axis measured
fine-versus-coarse rather than width-on-the-long-fifth, and finer lost every time.
Pooling is why: a document scores as its best chunk, so splitting an article dilutes it
(F12).

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

**Hybrid retrieval, both ways.** The run answered it: RRF recovered fourteen questions
and lost thirty-eight (−0.120, p = 0.0012; EXP-0014), and the weighted curve never
separated from dense at any α (best +0.010, p = 0.75; EXP-0018). What that suggests
is a property of the corpus rather than of fusion: when one retriever is thirty points
ahead of the other, the questions the weaker one wins are few and the questions it
misses outright are many, and any fusion rule that lets the weaker list veto — RRF by
construction, weighted fusion at α ≤ 0.4 — pays for the vetoes. The lexical signal
on this corpus is worth a re-order inside dense's top ten, not a second opinion on what
belongs there.

**A reranker, which is the technique everyone reaches for next — three times.** The
three cross-encoders produced the most movement of anything in Phase 2 and the least result:
strict recall@5 came out at −0.055 (p = 0.139), +0.010 (p = 0.887) and +0.000
(p = 1.000), while roughly 40 golds moved up a rank band and roughly 35 moved down on
each run, and more than two of five context documents were replaced on nearly every
question. Two things in it are worth more than the headline. First, it was **better at
rank 1 and worse at rank 5** — so the mechanism does work, at a depth this system does
not read; a one-document context would have scored it differently, and that is a live
question for the combination phase rather than a closed one. Second — and this is where I got it
wrong and had to correct it — strict recall@20 was identical before and after, and I
read that as the ceiling. The ceiling is actually the candidate set's recall at 50
documents, **0.985**, which I had never measured. The gold is in the candidate set
98.5% of the time and the best reranker surfaced it in the top five 73% of the time.
That inverts the conclusion: the remaining errors are **not** questions whose answer
is missing from the candidate set. The answer is almost always there. It is a ranking
problem, and two cross-encoders both failed to solve it (MIS-029).

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
