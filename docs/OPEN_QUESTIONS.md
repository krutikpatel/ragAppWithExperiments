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
`sum`, same index and seeds, ≥3 points difference. **Status:** open.

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
**Status:** open.

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
is the obvious first change to test.
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

## OQ-017 — How much do judged scores move between identical runs?
Two runs of the same config on the same 20 questions gave faithfulness 0.7284 and
0.7236. On one identical input, answer correctness scored 1.00 under default routing
and 0.857 with providers pinned (DEC-032). So judged metrics carry run-to-run and
provider-to-provider noise even at temperature 0.
**Decided by:** run the same Tier 2 config 3 times on the fixed subsample with
providers pinned; report the spread of each judged metric. That spread is the floor
below which a judged difference is not a finding — the same rule the project already
applies to seeds. Until it is measured, no judged delta should be called a result.
**Status:** open. This one gates the credibility of every judged number.

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

---

## External claims to test, not to cite

External claim (Cohen et al., WixQA, arXiv:2505.08643): the paper reports baseline
retrieval and generation numbers on these datasets. **Not reproduced here.** P0-14
covers deciding where our metric definitions match theirs before any comparison is
drawn. Until then, no number of ours may be presented next to a number of theirs.
