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
**Decided by:** hand-label 30 reference/generated step pairs; report agreement with
the lexical matcher. Under 0.8 agreement, the threshold or the method needs to change.
**Status:** open.

## OQ-008 — Does the lexical refusal detector agree with human judgment?
`refusal-lexical-v1` is a pattern list (DEC-014). It will miss refusals phrased
creatively and may fire on hedged but genuine answers.
**Decided by:** hand-label 50 generated answers spanning answerable and unanswerable
questions; report precision and recall of the detector. **Status:** open (needs a
Tier 2 run).

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

---

## External claims to test, not to cite

External claim (Cohen et al., WixQA, arXiv:2505.08643): the paper reports baseline
retrieval and generation numbers on these datasets. **Not reproduced here.** P0-14
covers deciding where our metric definitions match theirs before any comparison is
drawn. Until then, no number of ours may be presented next to a number of theirs.
