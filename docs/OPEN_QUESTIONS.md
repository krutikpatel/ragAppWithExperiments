# Open questions

Untested hypotheses, each with the decision rule that would settle it. Intuitions go
here instead of into predictions.

Status values: `open`, `queued`, `answered by EXP-NNNN`, `dropped`.

## OQ-001 — Does `sum` pooling beat `max` on multi-document questions?
Chunk scores pool into a document score, and the rule alone changes the ranking:
under `max` a document whose best chunk ranks 3rd can never reach rank 1; under
`sum` it can, when several of its chunks match. 79 of 400 questions need 2-3 gold
documents, where repeated weaker matches may be the signal.
**Decided by:** strict recall@5 on the `n_gold_docs > 1` slice of `dev`, `max` vs
`sum`, same index and seeds, ≥3 points difference. **Status:** **queued as EXP-0012** (Krutik, 2026-09-16), decision criteria C1–C3 written
into `configs/exp_0012_qwen_noprefix_*.yaml` before the run. C1 answered at zero cost
from the stored runs: **66 of the 67** `feature_request` flips are the same questions
across EXP-0009, 0010 and 0011, out of 69 the control misses on that type; the
control ranks the how-to article for the nearest *existing* feature first and the
"Request:" article 6th–50th.
**Answered 2026-09-17 by EXP-0012, mostly.** Without the prefix the slice reaches
0.988 (53 of the 67; C2's 0.99 threshold not met) and `dev` loses 0.060 (C3 fails):
the instruct prefix is the main cause of the synthetic `feature_request` misses and is
worth six points on real questions, so it stays. Residual: 16 `feature_request` misses
the prefix does not explain — next hypothesis is the "Request:" title template; a
query-side-only probe would not settle it, since the candidates that reach 0.999 differ
in the passage side too. **Status: answered for the decision; residual open, low
priority.**

## OQ-002 — How much does `dev_large` leakage inflate lexical retrieval?
Synthetic questions were generated from their gold article, so BM25 should be
flattered — but by how much is unmeasured, and knowing the size of the gap would say
whether `dev_large` is usable for ranking techniques or only for detecting large
effects.
**Decided by:** run the same BM25 config on `dev` and on a 200-question sample of
`dev_large`; compare strict recall@5. **Status:** open (needs P0-13).

## OQ-003 — Is 512 whitespace tokens the right chunk width for this corpus?
Chosen to match the handover's baseline, not from anything about Wix articles.
**Decided by:** chunk-width sweep on `dev`, strict recall@10, mean over 3 seeds.
**Status:** open. 2026-09-12: the control moved to 600/100 by decision, not by
measurement (DEC-038); EXP-0003 vs EXP-0001 is one point of a sweep, not the
sweep. The profile (`EXPERIMENTS.md`, corpus profile) shows 79.0% of articles fit
in one 600-word chunk, so any width above that changes nothing for four fifths of
the corpus — which bounds what a sweep can show on single-document questions.

## OQ-004 — Is the refusal set detectable by keyword rather than by grounding?
If a model refuses `out-of-scope-platform` questions on the token "Shopify" alone,
that bucket measures string matching, not grounded refusal.
**Decided by:** compare refusal rate on the `out-of-scope-platform` bucket against a
paraphrased variant with the competitor name removed. **Status:** open.

## OQ-005 — Does keeping bare URLs in indexed text help or hurt?
`norm-v1` keeps them (DEC-002) on the argument that they are exact terms. 128
documents contain one. Untested.
**Decided by:** `norm-v2` stripping bare URLs, strict recall@5 on `dev`.
**Status:** open.

## OQ-006 — Do `feature_request` articles act as retrieval distractors?
2,049 of 6,221 corpus documents are `feature_request` and 63 are `known_issue`, but
no `dev` question has one as a gold document (`test` has 10). A third of the index is
therefore never a right answer for the questions we iterate on, while still competing
for rank.
**Decided by:** strict recall@5 on `dev` with the full index vs. an index restricted
to `article_type == article`, same retriever and seeds. A large gap means a cheap
filter is available and the P0-08 article-type slice is measuring index composition
rather than question difficulty. **Status:** open.

## OQ-007 — Does lexical step matching agree with human reading?
Step coverage matches a reference step to a generated one by Jaccard overlap of
content words at 0.5 (DEC-015). A reworded but correct step may score as missing.
**Evidence from EXP-0001 Tier 2 (2026-09-11):** coverage was 0.123 over 32 procedural
questions, and 0.159 even when every gold document was retrieved. Read pairs show the
matcher missing paraphrases — *"Enabling Sandbox Collections"* vs *"Enable Sandbox in
your CMS"* scores 0.2 because *enabling* ≠ *enable* — alongside genuine omissions
(11 reference steps, 3 generated). The proportion is unknown, so the number currently
describes the matcher as much as the answers. Stemming or lemmatising content tokens
is the obvious first change to test. **DEC-037 raises the stakes:** step coverage's
run-to-run range is 0.064 against values of 0.08-0.14, so as built it cannot detect a
difference of any size yet observed. Fixing the matcher is now a prerequisite for the
metric existing in any useful sense, not a refinement.
**Decided by:** hand-label 30 reference/generated step pairs; report agreement with
the lexical matcher. Under 0.8 agreement, the threshold or the method needs to change.
**Status:** open.

## OQ-008 — Does the lexical refusal detector agree with human judgment?
`refusal-lexical-v1` is a pattern list (DEC-014). It will miss refusals phrased
creatively and may fire on hedged but genuine answers.
**First evidence, from the Tier 2 plumbing smoke run (2026-09-10, 5 questions, not a
measurement):** the detector flagged 1 of 5 answers as a refusal. Reading them, at
least 2 were non-answers — it caught *"I'm unable to find information in the provided
articles"* and missed *"It isn't clear from the provided articles which exact page or
image fit issue you're experiencing"*. So it under-detects the clarification-request
shape of refusal, which is the one an underspecified question provokes. Five answers
prove nothing about the rate; they do show the failure mode is real.
**Decided by:** hand-label 50 generated answers spanning answerable and unanswerable
questions; report precision and recall of the detector. **Status:** open, with a known
gap to close (clarification-style refusals).

2026-09-12 (P1-05): one concrete miss. On a `dev` question with neither gold document
retrieved, `baseline_answer@v1` returned "Restoring the selection … isn't described in
the provided articles … they do not specify how …" — a correct refusal — and
`is_refusal` returned False, because the model paraphrased instead of using the
prompt's fixed phrase. The detector cannot be extended without a metric-definition
decision; count these when the Tier 2 control runs.
2026-09-13 (EXP-0007): counted. On the 45 unanswerable answers, read by hand: 33 refusals,
the detector found 26 — **7 missed (21%)**, all paraphrases ("is not covered by the
provided …", "They do not cover …", "do not specify …"). Recorded false-answer rate 0.422;
hand-read 0.267. The decision rule stands: extend the phrase list, or replace with a
reference-free judged criterion, and re-measure on this run's stored answers.
**2026-09-13 — DEC-045:** `refusal-lexical-v2` agrees with all 45 hand labels
(`data/authored/refusal_labels_v1.yaml`, labelled by Claude, unreviewed). It also found
that v1 missed curly apostrophes, which hid 13–18 refusals per Phase 0 run. **Status:**
answered for this set; open on human agreement beyond 45 answers and on Krutik's
review of the labels.

## OQ-009 — Is `strict_recall@1` worth reporting at all?
It is structurally capped: ~20% of questions need 2-3 documents and can never score
at k=1 (DEC-010).
**Decided by:** judgment after the first baseline — if the number is read as a
failure rather than as a ceiling, drop it or report it over the single-gold subset.
**Status:** open.

## OQ-010 — Can answer correctness be scored without a judge?
The gold answer exists, so lexical (ROUGE) or embedding similarity against it is
possible and would be free, reproducible, and immune to a judge model changing
underneath us. The usual objection is that both are weak on long procedural text: a
correct paraphrase scores low, and a wrong-setting answer that shares vocabulary
scores high. Untested here.
**Decided by:** hand-label 40 generated answers as correct/incorrect against the
reference; report the agreement of (a) ROUGE-L, (b) embedding cosine, (c) an LLM
judge with the same labels. If a free method reaches judge-level agreement, it
replaces the judge for correctness. **Status:** open. Raised by Krutik, 2026-09-09.

## OQ-011 — Which embedding model should this project use?
Ragas's `AnswerRelevancy` needs embeddings, and OpenRouter serves 33 embedding models
through the same key (DEC-026, correcting DEC-022). So this is a choice, not a
blocker. Phase 1 needs an embedding model for dense retrieval anyway, so the two
decisions may as well be one — though they need not be the same model: judging
relevance and indexing 6,221 documents are different jobs with different cost profiles.
One thing to watch: most of the cheap options cap at a **512-token context**, which
would truncate our 512-*word* chunks. `baai/bge-m3` ($0.01/Mtok, 8,194 ctx) and the
OpenAI models do not.
**Decided by:** Krutik chooses; `answer_relevance` is then scored on the Tier 2
subsample and checked for whether it adds signal beyond answer correctness, which it
largely overlaps. **Status:** open — needed for `answer_relevance`, and for Phase 1
dense retrieval.

## OQ-012 — Does the Ragas call multiplier match reality? **ANSWERED**
**Answered 2026-09-11 by DEC-035.** No — it under-reported judge output by 9x. The
multiplier is gone; the estimator is calibrated on a measured run (11,164 in / 5,575
out per question) and validated out of sample to within 4%. Original text below.


The Tier 2 cost estimate assumes roughly 3x the single-call token volume for the
judge, because faithfulness decomposes claims and verifies each one. That number is an
allowance, not a measurement.
**Decided by:** the first real Tier 2 run — compare estimated judge tokens against
OpenRouter's reported usage and correct `RAGAS_CALL_MULTIPLIER`. **Status:** open.

## OQ-013 — Does the generator keep obeying the `[doc:<id>]` citation format? **ANSWERED**
**Answered by EXP-0001 Tier 2 (2026-09-11):** 88 of 100 answers on real BM25 retrieval
carried at least one well-formed tag; the 12 that did not include the 2 refusals.
Citation precision (0.388) tracks strict recall@5 (0.400) on the same questions — the
generator cites what it is given. Format compliance is not a confound. Original text
below.
DEC-017 flagged the risk that a cheap model ignores the citation instruction, which
would tank citation precision for reasons unrelated to retrieval. **First evidence
(Tier 2 smoke run, 2026-09-10, not a measurement):** of 5 answers, the 3 substantive
ones each cited exactly one document and the 2 refusals cited none — which is the
correct behaviour in both cases. So the flagged risk did not appear on 5 questions
with deliberately bad retrieval.
**Decided by:** the P0-13 Tier 2 run on BM25 retrieval — report the share of
substantive answers containing at least one well-formed `[doc:<id>]` tag. Below ~0.95
means the citation metrics are measuring instruction-following, not grounding.
**Status:** open.

## OQ-014 — Does `gpt-oss-120b` show self-preference toward `gpt-5-nano` answers?
DEC-030 treats them as different families on the argument that `gpt-oss-120b` is an
open-weights model with its own training rather than the hosted GPT-5 line. That is an
argument, not a measurement, and shared provenance could still correlate what the two
consider a good answer.
**Decided by:** score the same Tier 2 subsample answers with two judges — the current
one and a clearly unrelated family (e.g. `anthropic/*`) — and compare mean
faithfulness and answer correctness. A systematic gap in favour of the `gpt-oss` judge
is evidence of self-preference; comparable means are evidence against. Cheap, since it
reuses stored answers and only re-runs judging.
**Status:** open. Matters most before any judged number is quoted in the narrative.

## OQ-015 — How much does concurrent judging cut Tier 2 wall clock? **ANSWERED**
**Answered 2026-09-10 by DEC-032 (harness measurement, not an experiment).** Concurrency
was real but secondary: the dominant cause was OpenRouter routing to slow providers, a
37x spread on the same model. Pinning providers took 156s -> 9.6s per question;
concurrency took it to 11.8s on a real 20-question run (the isolated synthetic figure
was 1.1s). Together 13.3x. Original text below.


Measured: 156s per question, 98% of it waiting on the judge (DEC-031). `RagasJudge`
calls `asyncio.run` once per metric per question, sequentially, so 100 questions x 3
metrics is 300 serialized round trips with no overlap. The work is IO-bound.
**Decided by:** run the same 5-question subsample with questions judged concurrently
(a bounded worker pool, so provider rate limits are respected) and compare wall clock
against the 780s baseline. Scores must be identical — judging one question does not
depend on another — so any score change means the change is wrong, not faster.
**Status:** open. This gates whether a full-`dev` Tier 2 run is practical.

## OQ-016 — Should generation be concurrent too?
After DEC-032, generation is the largest serial component of a Tier 2 run: 3.1s per
question, 21% of wall clock, because the generator client is synchronous while judging
is batched. 100 questions is ~5 minutes of a ~20 minute run.
**Decided by:** make generation concurrent under the same bounded semaphore and compare
wall clock on the same 20-question subsample. Generated answers must be unchanged for
questions that were deterministic before, or the change is wrong rather than faster.
**Status:** open. Lower priority than it looks — 21% of 20 minutes is not what makes
Tier 2 painful any more.

## OQ-017 — How much do judged scores move between identical runs? **ANSWERED**
**Answered 2026-09-11 by DEC-037.** Range over three identical runs: faithfulness
0.031, answer correctness 0.010, answer relevance 0.031 — and almost all of it is the
judge, not the generator (judge-only re-scoring of identical answers: 0.025 / 0.013 /
0.030). Generator is non-deterministic (0/100 identical answers) but barely moves the
aggregates. Step coverage's range (0.064) is half its value; it cannot currently detect
anything. Floors are encoded in `rag/eval/noise_floor.py` and applied by `rag diff`.
Original text below.


Two runs of the same config on the same 20 questions gave faithfulness 0.7284 and
0.7236. On one identical input, answer correctness scored 1.00 under default routing
and 0.857 with providers pinned (DEC-032). So judged metrics carry run-to-run and
provider-to-provider noise even at temperature 0.
**Decided by:** run the same Tier 2 config 3 times on the fixed subsample with
providers pinned; report the spread of each judged metric. That spread is the floor
below which a judged difference is not a finding — the same rule the project already
applies to seeds. Until it is measured, no judged delta should be called a result.
**Status:** answered by DEC-037.

## OQ-018 — The cost estimator under-reports pinned judge cost **ANSWERED**
**Answered 2026-09-11 by DEC-035.** It was worse than under-reporting — it printed
$0.00 for a $0.04 run. Now reads per-provider prices and is calibrated on a real run;
out-of-sample validation on 8 different questions: cost within 3%. Real figure for a
100-question Tier 2 run is ~$0.84, not the $0.48 in DEC-034. Original text below.


`rag/runner/cost.py` reads the model-level price from OpenRouter's models endpoint
($0.037/$0.170 for `gpt-oss-120b`). With providers pinned to Cerebras/Groq the real
rate is up to $0.350/$0.750, so the pre-run estimate is low by roughly 6x on the judge
side — the one number it exists to get right.
**Decided by:** make the estimator read per-provider pricing from the endpoints API for
the pinned providers, then compare its estimate against OpenRouter's reported spend for
a full Tier 2 run. Within ~20% is good enough for a number labelled an estimate.
**Status:** open. Cheap to fix and it is actively misleading today.

## OQ-019 — Should refusal metrics condition on retrieval outcome?
MIS-012: `false_refusal` currently counts a refusal as wrong whenever the question has
gold documents in the corpus, so it penalises correct refusals after retrieval fails.
On EXP-0001 Tier 2, both "false" refusals were correct, and the real problem — the
generator answering anyway on 58 of 60 retrieval failures — has no metric at all.
**Proposed:** `false_refusal` = refused with all gold docs in context;
`answered_on_miss` = answered with gold docs absent (the ungrounded-answer rate).
**Decided by:** Krutik's sign-off on the redefinition (CLAUDE.md section 9); then
recompute on `run_20260911_053316_510b`, whose per-question rows already hold
everything needed. **Status:** open — blocks any refusal claim in the narrative.
2026-09-13: `gold_in_context` is now recorded per question (DEC-040), so both proposed
metrics can be computed from any run since EXP-0004 without re-running. On EXP-0006:
refused with all gold in context 3 / 67; answered with gold missing **31 / 33**. The
redefinition still needs Krutik's sign-off.

## OQ-020 — Does the procedure-block heuristic agree with the source HTML's ordered lists?
DEC-039 defines a procedure block on the marker-stripped text: a `:`-terminated header
sentence followed by two or more imperative sentences. It finds 5,936 blocks in 2,350
articles. Whether those are the source's `<ol>` lists — and how many `<ol>` lists it
misses because a step opens with an unlisted verb — is unknown.
**Decided by:** hand-read a fixed random sample of 30 articles with blocks and 30
without; count false blocks and missed procedures. Agreement above 90% on both keeps
`profile-v1`; below it, revise the verb list and bump the version. A re-freeze with
`html_content` would answer it exactly but starts a new comparison family (DEC-003).
**Status:** open.

## OQ-021 — Is a candidate pool of 50 chunks enough to find 5 distinct documents?
DEC-040 caps the document walk at 50 chunks. If the collapse ratio on this corpus is
high, the walk exhausts before reaching five documents and the context is short.
**Decided by:** `pool_exhaustion_rate` and `collapse_ratio__p90` on `dev`, per run
(EXP-0004 is the first measurement). Exhaustion under 1% keeps 50; above it, raise the
cap and re-run the control.
**Status:** answered for BM25 by EXP-0004 — exhaustion 0.000, p90 1.20, max 2.80 (14
chunks). 50 stays. Re-check when the dense control runs; a model that clusters an
article's chunks could collapse more.

## OQ-022 — Should the generator see every retrieved chunk of a selected document, or only its best?
DEC-040 sends one chunk per document. A long article whose answer spans two chunks
loses one of them. The alternative keeps all scanned chunks of the selected documents,
which makes context length depend on the collapse ratio.
**Decided by:** Tier 2 on the fixed subsample, both variants, same retrieval; judged by
citation recall and step coverage (deterministic) — faithfulness only if the delta
clears its floor (DEC-037). Needs a real judge first (DEC-018).
**Status:** open.

## OQ-023 — How much do hosted query embeddings move a dense run, and does it matter beyond one question?
Measured on EXP-0005: three runs of the same config against the cached index gave
strict recall@5 0.715 / 0.715 / 0.720; only 38–47 of 200 full rankings were identical,
183–188 top-5 sets were. So DeepInfra's `qwen3-embedding-8b` is not byte-deterministic
on queries, and a dense run carries a ~0.005 floor on recall metrics that BM25 does not.
**Decided by:** whether any Phase 2 dense-vs-dense delta lands within 0.005; if one does,
run three replicates before calling it. Also worth one probe: is the *index* side
deterministic too (re-embed 200 chunks, compare vectors)? If not, two index builds of the
same config are two different families.
**Status:** open — floor recorded; index-side determinism unprobed. 2026-09-13: three
more runs (P1-11, DEC-046) on the sub100: top-5 sets identical to run 1 on 93 and 95 of
100; strict recall@5 range 0.01, @3/@10/@20 identical. Consistent with the first
measurement.
**Index side answered 2026-09-17 (EXP-0012):** a second DeepInfra build of the same
8,218 passages (same 3,125,318 tokens) reproduced 4,816 vectors byte-for-byte and the
rest to cosine ≥ 0.99977, none below 0.999. Not byte-deterministic; indistinguishable
for any metric here. Two builds of one config are one comparison family. The query-side
floor (0.012 on n=100) remains the binding one. **Status: answered.**

---

## External claims to test, not to cite

External claim (Cohen et al., WixQA, arXiv:2505.08643): the paper reports baseline
retrieval and generation numbers on these datasets. **Not reproduced here.** P0-14
covers deciding where our metric definitions match theirs before any comparison is
drawn. Until then, no number of ours may be presented next to a number of theirs.

## OQ-024 — Does the multi-document slice of `dev` (n=40) have the power to detect the deltas Phase 2 cares about?
DEC-047's paired test on the Phase 1 controls gives the dense advantage on
multi-document questions as +0.175 with CI [+0.025, +0.325] and p = 0.063 — a gain that
every other slice reports at p ≤ 0.014 is not significant at 0.05 on this one, because
40 questions with 11 discordant pairs cannot separate it. The organizing question of
Phase 2 is the multi-hop gap; this is the slice it lives on.
**Decided by:** the width of the multi-document CI on `dev_large` (its multi-gold
count is unknown until measured) versus `dev`. If `dev_large`'s multi-document slice
gives CIs narrower than ~±0.10 on strict recall@5, retrieval axes are decided there
and confirmed on `dev` as P2-04 says; if it is also too small, the slice needs more
questions and that is a split decision, not a tuning one.
**Status:** **answered 2026-09-16 by EXP-0008, and not as posed.** `dev_large` has
**no** multi-document questions: `n_gold_docs = 1` for all 6,221 rows (all
`wixqa_synthetic`). The slice is not small, it is absent, so `dev_large` cannot decide
anything about the multi-hop gap. The only multi-document questions in the project are
the 40 on `dev` (35 two-gold, 5 three-gold) and 39 on `test`. Consequence for P2-04 /
DEC-050 is an open decision — see MIS-021 and DEC-055.

## OQ-025 — Do `task_type` (gemini) and `dimensions` (text-embedding-3, gemini) pass through OpenRouter's `/embeddings`?
Both matter for Axis 2: gemini's query/document asymmetry lives in `task_type`, and
run 5 (dimension truncation) needs `dimensions`. OpenRouter's request schema documents
neither for embeddings; absence from the docs is not evidence (MIS-005).
**Decided by:** one request per parameter on the pinned provider, checking the
response's vector length (for `dimensions`) and whether an unknown field errors or is
ignored (for `task_type`). Cost: a few tokens.
**Status:** **answered 2026-09-15** by seven probe calls (≈$0.00001 total):
- `dimensions` **passes through**: text-embedding-3-large returned 3072 → 256 and
  gemini-embedding-2 3072 → 768 on request. Run 5 is possible.
- `task_type` is **silently dropped**: gemini's vector for the same input is
  byte-identical with no `task_type`, with `RETRIEVAL_QUERY` and with
  `RETRIEVAL_DOCUMENT` (cosine 1.0, arrays equal), and a made-up parameter is also
  accepted without error — so "no error" was never going to be evidence (MIS-005).
  EXP-0011 therefore measures gemini symmetrically, and that is the only gemini
  measurement OpenRouter's endpoint can give. Recorded in DEC-054's config comment.
- Incidental: gemini on Google AI Studio is byte-deterministic call to call (two plain
  calls identical), where DeepInfra's qwen is not (OQ-023).

## OQ-026 — Why is the qwen control weak on `feature_request` articles in `dev_large`, and does it matter on real questions?
Both EXP-0009 (text-embedding-3-large) and EXP-0010 (bge-m3) gained +0.032–0.033 strict
recall@5 on the 2,049 `feature_request` questions of `dev_large` (67 gained / ≤1 lost
each) while losing on ordinary articles. Two unrelated models fixing the same questions
points at the control, not the candidates: "Request:"-titled articles are short and
templated, and the qwen3 instruct prefix ("retrieve relevant passages that answer the
query") may push those away from question-shaped queries. `dev` has **zero**
feature-request gold documents, so nothing measured so far says whether this matters
for user questions.
**Decided by:** (1) the list of the ~67 questions — same set across EXP-0009/0010? (2) a
run of the control with `prefix_convention: none` on `dev_large` and `dev` (one config
change, ~$0.003 + $0.0001, no re-index needed if the passage side is unchanged — it is:
`qwen3` prefixes queries only). If the gap closes, the prefix is the cause.
**Status:** open.

## OQ-027 — Is gemini-embedding-2's better top-5 ordering worth anything once a reranker is in the loop?
EXP-0011: on `dev` gemini did not change which questions had every gold document in the
top five (Δ +0.030, p = 0.41) but placed the gold higher when it was there (strict
recall@1 +0.085, p = 0.020; nDCG@10 +0.066, p = 0.002). A reranker over a 50-chunk pool
re-orders the top of the list anyway; if it recovers the same ordering from the qwen
index, the 20x-per-token model buys nothing. If it does not, ordering quality upstream
of the reranker matters.
**Decided by:** in Axis 5 (P2-10), run the winning reranker over the qwen control *and*
over the gemini index (the index is cached; ~$0.001 of queries plus rerank cost) and
compare nDCG@10 and strict recall@1 on `dev` by paired test.
**Status:** open — queued for Axis 5.

## OQ-028 — Is the α=0.8 re-ordering worth anything once a reranker is in the loop?
The sibling of OQ-027. EXP-0018 moved ten questions and netted one; its six gains were
documents dense had at rank 6–9 and BM25 at 1–7, pulled inside the top five. A reranker
over a 50-chunk pool re-orders exactly that region. If the reranker recovers the same
six from the dense pool, the lexical half buys nothing; if it does not — because the
reranker, like dense, prefers the paraphrase over the exact term — a lexical prior
upstream of the reranker is a cheap second signal.
**Decided by:** in Axis 5 (P2-10), run the winning reranker over the dense control's
pool and over the α=0.8 hybrid's pool (both indexes cached; rerank cost only) and
compare strict recall@5 on `dev` by paired test, reading the ten EXP-0018 flips
individually.
**Status:** open — queued for Axis 5.

## OQ-029 — Would a stronger lexical half change the fusion verdict?
Axis 3 fused dense with the Phase 1 BM25: lowercase `[a-z0-9]+` tokens, no stemming,
no stopwords, Okapi defaults (P0-13: "the dumbest thing that works, on purpose"). 22 of RRF's 38 losses had the gold
absent from BM25's top 100 (EXP-0014); a BM25 that returned those documents anywhere in
its list would change RRF's arithmetic and the whole low-α end of the curve. Whether
stemming or a title-boost would do that is not known — the sparse control was never
tuned, on purpose, and DEC-056 fixed the lexical half as EXP-0004's for comparability.
**Decided by:** count, from the stored EXP-0004 ranking, how many of the 22 absent
gold documents contain a stemmed form of a query term (zero cost); if most do, one run
of RRF over a stemmed BM25 on `dev` (new sparse control first, then the fusion) decides
by paired test against EXP-0014. Not queued: the axis is closed and the result would
be a new comparison family for the sparse side.
**Status:** open.

## OQ-030 — Can late chunking run through OpenRouter's embeddings endpoint?
Late chunking embeds a whole article and pools per-chunk vectors from the token
embeddings, so it needs token-level output. **Answered 2026-09-18 by four probe
calls ($0.0000004):** no. `/embeddings/models` lists 33 models, none from Jina;
`/embeddings` returns one pooled vector per input; `encoding_format` accepts only
`float | base64` (HTTP 400 otherwise); `late_chunking: true` and
`return_token_embeddings: true` are silently ignored — identical shape and identical
9 billed tokens. A local run would change the embedding model too (two axes in one
run). **Status: answered — dropped from Axis 1 (DEC-057); re-probe before assuming
it stays unavailable (MIS-005).**

## OQ-031 — How much of a chunking delta is re-embedding noise?
Every chunker in Axis 1 is a fresh embedding pass over the corpus, and EXP-0012 found
only 59% of vectors byte-identical when the same text was embedded twice on DeepInfra.
The control's measured run-to-run spread (0.005, DEC-046) was taken on a *cached*
index, so it excludes that. EXP-0022 lost 17 questions on `dev`, and for 8 of them the
gold article is a single chunk under both chunkers — identical words, only line breaks
and the re-embed differ. Without a floor, a −0.055 cannot be split into "cut placement"
and "same text, new vectors".
**Decided by:** rebuild the control's index from scratch (same config, `index_dir`
pointed at a fresh directory, ~$0.03) and run `dev`; the flip count against `be04` is
the re-embedding floor for this axis. Two rebuilds would give a spread. Also decides
whether the structure chunker should join lines with spaces to remove the
whitespace difference on single-chunk articles.
**Answered 2026-09-22 by EXP-0023 (`run_20260922_052729_e550`, $0.031).** The floor is
**2 questions of 200**: re-embedding the identical control corpus scored 0.710 vs 0.720
(Δ −0.010, p = 0.49), lost two questions and gained none, both moving rank 5 → 6, with
**zero** multi-document flips and nDCG@10 unchanged to four decimals. So Axis 1's
churn (21–58 flips per config) is the chunking, not the rebuild. It also corrected the
caution in EXP-0022. One rebuild gives the order of magnitude, not a spread; a second
would give the spread if a future axis needs it.
**Status:** answered by EXP-0023.

## OQ-032 — Does the structure chunker's −0.055 survive joining lines with spaces?
The structure chunker preserves the article's line breaks inside a chunk; the control
joins the same words with spaces. For the 4,915 articles that are a single chunk under
both, the words are identical and only **29** of the texts are byte-identical — so
`\n` versus ` ` is the only difference the embedder sees, and 8 of EXP-0022's 17 lost
questions are on such articles. The re-embedding floor is 2 questions (EXP-0023), so
whitespace is a candidate explanation for part of the −0.055 and cut placement for the
rest. This is an implementation side-effect, not the technique.
**Decided by:** one variant of `configs/exp_0022_structure_dev.yaml` that joins units
with a space instead of a newline (a one-line change in `StructureChunker.split`, a new
`chunker_id`, so a fresh index at ~$0.03) run on `dev`; `rag compare` against EXP-0022
and against `promoted`. If it lands within the 2-question floor of the control, the
line breaks were the story and cut placement did nothing; if it stays near 0.665, cut
placement was the story.
**Status:** open — not queued; Axis 1 is closed and this is a follow-up, not a fifth
chunker.

## OQ-033 — Is the `dev_large` direction check worth buying for a reranking winner?
DEC-055 asks every retrieval axis for a `dev_large` check that agrees in direction
before `rag promote` will move the pointer. For every earlier axis that check was
nearly free: the index was already built and the queries cost $0.000002 each. Axis 5
is the first axis billed **per query**, so the same check costs 31x the deciding run
— $6.22 for the cheapest reranker, $26 for `qwen3-reranker-8b`, against $0.20 and
$0.78 on `dev`. And `dev_large` has no multi-document questions at all (MIS-021),
which is the slice a reranker is most likely to move.
**Decided by:** whether any reranker wins on `dev` at p < 0.05. If one does, the
check is bought for that one config only and the cost goes to Krutik first (DEC-053).
If none does, the check is never run and the axis closes on `dev` as a negative
result — nothing `dev_large` could say would promote a configuration that lost.
**Answered 2026-09-23 by EXP-0024: no.** `cohere/rerank-v3.5` did not win on `dev`
(Δ −0.055, p = 0.139), so there is no winner for `dev_large` to check and nothing it
could say would promote a configuration that lost. The check was never run and $7.28
was not spent. If EXP-0025/0026 are ever run and one wins, this question reopens.
**Status:** answered by EXP-0024 (not bought).

## OQ-034 — Does a reranker's gain survive the context the generator actually sees?
Axis 5 is decided on Tier 1, where a reranker is scored on the document ranking. But
a reranker's stated purpose is precision in the **top 5**, which is exactly what
Tier 2's faithfulness and citation precision read. The dense control has a Tier 2
run (EXP-0006, citation precision 0.550, MDD 0.08) and no Axis 2, 3 or 1 config ever
earned one, because none of them won.
**Decided by:** a Tier 2 `dev` sub100 run of the winning reranker against EXP-0006,
citation precision and step coverage, each against its MDD (DEC-048). ~$0.09 of
generation and judge on top of the reranker's own per-query cost.
**Status:** open — conditional on Axis 5 producing a winner, and on the judge still
being the DEC-018 placeholder, whose scores may not reach EXPERIMENTS.md.

## OQ-035 — Is Axis 5's result about reranking, or about Cohere?
DEC-059 opens Axis 5 with one reranker, `cohere/rerank-v3.5`. A single cross-encoder
cannot separate "reranking does not help this corpus" from "this cross-encoder does
not": the two open-weight and LLM-based candidates work by different mechanisms
(`qwen/qwen3-reranker-8b` is a cross-encoder scoring each pair alone; the LLM
reranker sees all 50 candidates together and can compare them), and either could
move a slice Cohere leaves flat.
**Decided by:** EXP-0026 (`qwen/qwen3-reranker-8b`, $0.78) and the LLM reranker
($0.22), both already configured and committed, run on `dev` against `promoted` with
`rag compare`. Both configs exist; neither has a run row, so neither is an experiment.
**Answered 2026-09-23 by EXP-0025: it was about Cohere, and the caution was right.**
`cohere/rerank-4-fast` beat `cohere/rerank-v3.5` on `dev` by **+0.065, CI [+0.010,
+0.125], p = 0.039** (24 questions gained, 11 lost), and on the multi-document slice
by +0.175 (p = 0.067) — while *neither* is distinguishable from the dense control.
Two cross-encoders over an identical candidate set differ significantly from each
other, so EXP-0024's null was a fact about one model. It still does not follow that
some third reranker would win; it follows that one reranker cannot close the axis.
`qwen/qwen3-reranker-8b` remains unrun (VOID on credits, MIS-031) and is the open
part of this.
**Closed 2026-09-24 by EXP-0026.** The open-weight model ran and returned the same
verdict by a different route: Δ **exactly 0.000**, p = 1.000, while behaving unlike
either Cohere model (the only one worse at rank 1, the best at depth, @20 = 0.950).
So the axis's answer rests on three cross-encoders with three distinct behaviours
rather than one, which is a much stronger statement than EXP-0024 alone could make —
and it vindicates running all three. The LLM-as-reranker, a genuinely different
mechanism, is still unrun.
**Status:** answered for cross-encoders (3 of 3 null); the LLM reranker was cut
(DEC-060), so the different-mechanism question is closed unanswered, not resolved.

## OQ-036 — Does the recalibrated Cohere unit multiplier hold out of sample?
`rag/runner/cost.py` now estimates Cohere search units at **1.17 per query at 50
candidate documents**, calibrated on EXP-0024 alone (234 units / 200 queries).
DEC-035 is explicit that matching the calibration run proves nothing: the estimator's
own output says "NOT yet validated out of sample" and will keep saying it until a
second rerank run on different questions is compared against it. The multiplier is a
threshold effect on candidate length, so it should move with `rerank_candidates` and
with the chunker — a 20 -> 5 run would test that directly.
**Decided by:** any second Cohere rerank run — the 20 -> 5 ratio config P2-10 asks
for, or EXP-0025 — with `cost_actual_usd` compared to `cost_estimate_usd` on the row.
Within 10% counts as validated.
**Partially answered 2026-09-23 by EXP-0025: within 4%.** The recalibrated model
predicted $0.4681 and the run billed **$0.4481** (224 search units against 234
predicted) on different questions from the calibration run — inside the 10% bar this
question set. That is one out-of-sample check at the *same* `rerank_candidates` and
the same chunker, so the threshold behaviour the multiplier encodes is still untested:
a 20 → 5 run would move candidate length and is the real test.
**Second check, 2026-09-24, FAILED on the token path.** EXP-0026 was the first
token-billed run and came in **32% over** ($1.2103 against $0.9168): a cross-encoder
bills (query, document) **pairs**, so the query and template are charged once per
document — about 76 tokens per pair, times 58 candidates (MIS-032). Recalibrated to
within 0.1% of the run. So: the search-unit path has one passing out-of-sample check
(4%), the token path has none — it has only just been calibrated. Both remain
labelled as such in the estimator's own output.
**Status:** open — search-unit path one check passed; token path uncalibrated until a
second token-billed run; the varying-candidate-count case untested on either.

## OQ-037 — Does the cross-encoder specifically rescue badly-phrased questions?
Reading EXP-0024's 45 flipped questions, the 17 gains skew towards loose phrasing,
typos and complaints (*"Hoe can I restore…"*, *"i cant create a new gallery"*, *"do I
have to give my login to a website designer"* — golds at rank 33, 24 and 20 lifted to
1 or 2), while the 28 losses skew towards well-formed questions the dense retriever
had already placed at rank 1 to 5. If that is real it is the useful finding in this
axis — it says *when* to pay for a reranker rather than whether to — and it would
also explain the otherwise odd `q_len` split (medium +0.078, long −0.129).
But it is a description of 45 hand-read questions, and the `source:expertwritten` vs
`source:simulated` slices do **not** separate (−0.040 vs −0.070, both flat), which is
evidence against it.
**Decided by:** a pre-registered malformedness label over the `dev` questions —
authored, in `data/authored/`, never derived from the run being tested — and
strict recall@5 on that slice for EXP-0024 vs `promoted`, ≥ 0.10 separation between
the well-formed and malformed halves. Labelling 200 questions is the cost, not compute.
**Status:** open — a follow-up, not a sixth Axis 5 experiment.

## OQ-038 — Does a wider or narrower candidate set close the 25-point ranking gap?
The Axis 5 ceiling is measured: the dense control's strict recall@**50** is **0.985**,
and the best reranker surfaced the gold in the top five for **0.730**. So the gold is
in the candidate set almost always and gets ranked into the context three times in
four. P2-10 asks for two k → n ratio runs and neither has been run; they are now the
most interesting thing left in the axis, because they test the two opposite readings
of that gap. If the reranker is **drowning** in candidates, 20 → 5 should beat 50 → 5.
If it is simply not good enough at this task, the ratio will not matter and both will
sit near the control.
**Decided by:** `rerank_candidates` 20 and 100 against `promoted`, `cohere/rerank-4-fast`
(the better of the two measured), `dev`, `rag compare` on strict recall@5, ≥ 0.03
separation between the ratios. Roughly $0.20 and $0.90. **Blocked: the OpenRouter
account has no credit (MIS-031).**
**Status:** open, **not queued** — cut from P2-10 by DEC-060. Returns if P2-13 shows
context depth is the binding constraint.
**Status note (2026-09-27, DEC-071):** the Phase 3 handover names this as a Phase 2
carry-over ("the reranker headroom diagnostic on the recall@5→recall@20 gap"). It was
**not run before the `phase3-baseline` freeze** and stays open here, unqueued. Phase 3
does not reopen retrieval axes.

## OQ-039 — Should the cost gate check the account balance, not just the estimate?
Every cost control here is per-run: the $2 gate, the estimate, the approval, the
running totals. None of them knows whether the account has money in it, which is how
EXP-0026 came to be approved, estimated, gated and started before dying on HTTP 402
(MIS-031). OpenRouter exposes `GET /api/v1/credits`.
**Decided by:** Krutik — this changes what halts a run, so it is not a change to make
unasked. The options are a hard halt when the balance is below the estimate, a warning
printed beside the running totals, or nothing.
**Status:** open — put to Krutik 2026-09-23.

## OQ-040 — Does a larger context produce better answers, or just more tokens to dilute?
The top-k sweep (P2-13, reconstructed) shows the input-side gain precisely: gold
reaches the generator for 0.720 of questions at `top_k=5`, **0.850 at 10** and 0.920
at 20, with multi-document questions going 0.350 -> 0.625 -> 0.825. All of that is a
statement about what is *in* the context, not about what the generator does with it.
More context also means more tokens to dilute the answer, more chance of citing the
wrong article, and more money per query — and `context_max_tokens` (6,000) truncates
above about k=14, so a test at k=20 must raise that too (two fields, DEC-061).
**Decided by:** a Tier 2 `dev` sub100 run at `top_k=10` against EXP-0006 (`top_k=5`,
citation precision 0.550, MDD 0.08, step coverage 0.289) — citation precision and step
coverage each against their MDD (DEC-048), plus tokens and cost per query. ~$0.09 of
generation and judge, no reranker, no new index. The judged metrics remain the DEC-018
placeholder and must not reach EXPERIMENTS.md as measurements.
**Status:** **answered by EXP-0051** (2026-09-27, `run_20260927_235029_2216`, $0.03831).
**More context does not produce better answers here; it dilutes.** `gold_in_context`
rose 0.6700 → 0.8200, citation recall moved −0.0183 (inside its 0.040 MDD) and citation
precision fell **0.0851 against an MDD of 0.080 — significant and negative**, at ×1.82
the generator input tokens. The decomposition is exact: the 15 questions that newly
gained their gold document improved by **+0.2111** on citation recall, the 67 that
already had it lost **0.0746**, and those two numbers reproduce the −0.0183 overall.
The technique works on the questions it reaches and harms a group 4.5x larger.

## OQ-041 — Would a diversity penalty that is document-aware rather than vector-aware help?
EXP-0027 showed MMR inverts here because gold documents of one question cluster in
embedding space (0.788 against 0.693) and the redundancy term cannot tell "another
chunk of the article I just picked" from "another article about the same task" — it
only sees cosine. The document-level walk (P1-03) already does the first job
perfectly and for free: the control's collapse ratio is 1.106, so the context is
already ~90% distinct documents. A penalty applied to *repeat documents* rather than
to *vector similarity* is therefore close to what the system already does, which
suggests the whole diversity family has little left to offer on this corpus.
**Decided by:** not worth a run on the evidence so far — recorded so that the next
person to propose a diversity method finds the measurement rather than repeating the
experiment. It becomes live only if a future chunker or retriever pushes the collapse
ratio materially above 1.2, which would mean the context has real redundancy to remove.
**Status:** open, **not queued** — parked with its decision rule.

## OQ-042 — Should a Tier 2 axis experiment be diffed against `promoted.yaml` or against the Tier 2 control?
- **Status:** open. Surfaced 2026-09-24 while building the Axis 6 configs.
- **What happened:** `configs/promoted.yaml` is a **Tier 1** config — no generator,
  no judge, because those fields are empty until a model decision fills them. P2-05's
  rule is that every axis experiment is a one-dimension diff against promoted.yaml.
  A Tier 2 experiment therefore differs from it on *two* dimensions: its own axis and
  `generation` (the generator and judge model fields going from empty to set). The
  runner warns accordingly. Axis 6 is the first Tier 2 axis, so it is the first to
  meet this; every P2-14 config will meet it too.
- **Why it is not a bug to fix quietly:** the warning is literally true — the config
  does change two dimensions against that file. What is wrong is the comparison, not
  the check. The honest baseline for a Tier 2 assembly run is
  `configs/baseline_dense_tier2.yaml` (EXP-0006), which is the same retrieval with
  the generation dimension already set.
- **Decided by:** a judgment call, not a measurement. Three options, none yet chosen:
  1. Leave it. The warning fires on every Tier 2 axis run and is explained in each
     EXP file. Cheapest, and it trains whoever reads the logs to ignore a warning,
     which is how a real one gets missed.
  2. Teach `config_diff` to compare against the promoted config *upgraded to the
     candidate's tier*, so Tier 2 fields are only a dimension change when they
     differ from the Tier 2 control's. Correct, and it changes the promotion rule's
     meaning, so it needs a DEC entry.
  3. Promote a Tier 2 config. Rejected on sight: `promoted.yaml` is the current best
     *retrieval* configuration and nothing has earned promotion yet anyway.
- **Current handling:** option 1, documented. `tests/test_assembly_p2_13.py` pins
  both behaviours — the one-dimension diff against the Tier 2 control, and the
  two-dimension diff against promoted — so whichever way this is decided, a test
  states what changed.

## OQ-043 — `chunker_id` is not a complete identity for an LLM-built index
- **Status:** open. Surfaced 2026-09-25 by EXP-0030's warm-cache repeat.
- **What happened:** the dense index is cached under a key containing `chunker_id`, which
  is a hash of the chunker's `params`. For every chunker before P2-13 that was a complete
  identity: the same params over the same corpus produce the same chunks. The contextual
  chunker breaks that, because one of its chunks' text comes from a model call that can
  **fail and later succeed**. EXP-0030's cold run had 1 failed prefix of 8,218 and indexed
  that chunk unprefixed; the warm repeat's retry succeeded, so it reported 8,218 prefixes
  while reusing an index built from 8,217. Same key, different content.
- **Why it is small now and would not always be:** one chunk in 8,218 is 0.012% and cannot
  move a metric. But the failure rate is a property of the provider on the day, not of the
  config — MIS-034 measured the same model failing ~1 in 222 on a different prompt. At that
  rate this would be 37 chunks, and two runs of the "same" config would silently search
  different indexes.
- **Decided by:** a judgment call, not a measurement. Options, none yet chosen:
  1. Put a content hash of the chunks into the index key, so any change in indexed text
     rebuilds. Correct and complete; costs a full re-embed whenever a retry fills a hole.
  2. Refuse to build an index when any chunk's generation failed — VOID the run instead.
     Clean, and it throws away a paid 8,217-call build over one chunk.
  3. Record the failed chunk ids on the row and treat a run whose failure set differs from
     the cached index's as not comparable. Cheapest; relies on a check nobody has written.
- **Current handling:** option 3 without the check — the failure ids are on the row
  (`prefix_call_failures`) and the discrepancy is stated in EXP-0030's Anomalies. Whichever
  way this is decided, it needs a DEC entry, because it changes when an index is rebuilt.

## OQ-045 — Is HyDE's multi-document gain real?
- **Status:** open. Surfaced 2026-09-25 by EXP-0032.
- **What was measured:** on `dev`, HyDE moved `gold_docs:multi` from **0.350 to 0.450**
  — seven questions gained, three lost — at **p = 0.346, 95% CI [−0.050, +0.250], n=40**.
  Not a finding. It is also the **only positive movement that slice has produced** across
  six techniques aimed at it: MMR (0.000), three cross-encoder rerankers, contextual
  retrieval (+0.050, p=0.72) and decomposition (−0.050).
- **Why it cannot simply be re-run bigger:** the obvious move is `dev_large` for
  statistical power, and `dev_large`'s multi-document slice **has zero rows** (MIS-021) —
  its questions were generated one-per-article. There is no larger multi-document sample
  in this project.
- **Decided by:** three seeds of EXP-0032 on `dev` would separate a 0.100 shift on n=40
  from noise only if the run-to-run spread on that slice is well under 0.05, which is
  itself unmeasured. The honest options:
  1. Three repeat runs of EXP-0032 with fresh query embeddings (~$0.001 each, the
     transforms replay free) to measure the multi-doc slice's own noise floor first.
     Cheap, and it answers whether the question is answerable before spending on it.
  2. Combine HyDE with the depth finding (k=20 lifts multi-doc to 0.825) in P2-16 and
     test whether the two compose, rather than chasing 40 questions.
  3. Drop it, and record that the one positive signal on the organizing question's slice
     was left unresolved for want of a sample.
- **Current handling:** open, untaken. It belongs in P2-16's combination set if anywhere.

## OQ-046 — The chosen abstention threshold has never actually executed
- **Status:** open. Surfaced 2026-09-25 by DEC-068.
- **What is true:** EXP-0038 evaluated the threshold by **reconstruction** — replaying
  stored per-question scores and answers through the abstention rule. That is exact for
  the metrics it reports, because the rule is a pure function of numbers already
  recorded, and it cost nothing.
- **What is therefore not true:** no run has ever applied the threshold. There is no
  `abstention_threshold` field in `RunConfig`, no code path that skips generation when a
  score is low, and consequently **`promoted.yaml` cannot adopt DEC-068 without recording
  a configuration that has never run.**
- **What reconstruction cannot show, even in principle:** the reconstruction assumes
  abstaining produces the standard refusal and nothing else changes. A real
  implementation also **skips the generation call**, which changes cost per query and p95
  latency — both of them favourably, and neither of them measured. It would also need a
  decision about what the user sees, which is a product question this project has not
  asked.
- **Decided by:** implementing the field and running it on `dev` + `unanswerable` at
  Tier 2 (~$0.05, ~8 minutes), then confirming the reconstructed numbers reproduce. If
  they do not, the reconstruction has a bug and EXP-0038's curve is wrong.
- **Why it was not done here:** P2-14's experiment count is four and this would be a
  fifth. The curve, not the implementation, is what the story asks for.
