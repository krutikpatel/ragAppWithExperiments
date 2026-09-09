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

---

## External claims to test, not to cite

External claim (Cohen et al., WixQA, arXiv:2505.08643): the paper reports baseline
retrieval and generation numbers on these datasets. **Not reproduced here.** P0-14
covers deciding where our metric definitions match theirs before any comparison is
drawn. Until then, no number of ours may be presented next to a number of theirs.
