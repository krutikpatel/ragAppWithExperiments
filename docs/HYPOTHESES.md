# Hypotheses

What was expected, before the run, versus what happened. `EXPERIMENTS.md` is
strictly no-predictions; this file is where expectations go, so that calibration —
how often the expectation was right — becomes an artifact of its own.

Rules:
- An entry is written **before** the run it names, and never edited afterwards. The
  resolution is appended, with the run id, as **confirmed**, **wrong**, or
  **inconclusive**.
- Entries name their source. An expectation quoted from a handover is the handover
  author's; one written here by Claude is Claude's, and says so.
- Predictions never appear in `EXPERIMENTS.md`, `NARRATIVE.md` or a `DEC-` entry.
  This file is the only place.

Status of each hypothesis is one of `pending`, `confirmed`, `wrong`, `inconclusive`.

---

## A note on timing for the Phase 1 entries

P1-10 asks for four seed entries "written before running". They were not: EXP-0004
through EXP-0007 had already run when this file was created on 2026-09-13. So the
four Phase 1 entries below do not record Claude's predictions — none were made or
recorded. They record the **expectations stated in the Phase 1 handover**, quoted
verbatim from `user_stories/phase1stories.md`, which was written before any Phase 1
run. That is the only honest pre-run source that exists. From H-005 on, entries are
written before their run.

---

## H-001 — Dense beats sparse overall, and per slice
- **Date written:** 2026-09-13 (after the fact; see note above)
- **Source:** Phase 1 handover, §1 fact 4: *"This corpus favours lexical matching.
  Enterprise KB text is dense with exact product names (Wix Payments, Quick Action
  Bar, iCal, og:image). BM25 is a serious opponent here, not a straw man."* The
  handover does not say dense will win; it says the margin should be contested.
- **Hypothesis, as stated:** dense retrieval will not beat BM25 by a wide margin on
  this corpus, and BM25 will win on exact-term questions.
- **Tested by:** EXP-0005 vs EXP-0004, strict recall@5 on `dev` (n=200), per slice.
- **Resolution:** **wrong** on the margin, **confirmed** in a narrow form.
  Dense 0.715 vs sparse 0.410 (+0.305, 61 questions; dense spread 0.005); dense won
  every slice by 0.175–0.371. BM25 won nine individual questions, all short
  exact-term matches (*PDF Viewer App*, *Header Scroll Effects*, *Changing the
  Payment Date*) — the "serious opponent" survives as nine questions, not as a slice.
  `run_20260912_222538_b1dc` vs `run_20260912_215235_ff2f`.

## H-002 — Multi-hop strict recall lags single-document substantially
- **Date written:** 2026-09-13 (after the fact)
- **Source:** Phase 1 handover, §1 fact 2 and P1-08: *"multi-doc questions need 2–3
  distinct documents … a naive top-5-chunks retriever structurally caps strict recall
  on multi-hop questions"*; *"The single-doc vs multi-hop split is the one that
  matters most."*
- **Hypothesis, as stated:** strict recall on `gold_docs:multi` will be substantially
  below `gold_docs:single`.
- **Tested by:** EXP-0004 and EXP-0005, strict recall@5 by slice.
- **Resolution:** **confirmed**, under both retrievers. Sparse: single 0.469, multi
  0.175. Dense: single 0.806, multi 0.350. Dense finds *one* required article for 34
  of 40 multi-document questions (loose 0.850) and all of them for 14. The gap is
  0.456 under dense. The handover's stated *mechanism* — chunk collapse — is H-003
  and was wrong; the lag is real but comes from ranking the second document, not
  from granularity.

## H-003 — The chunk→document collapse ratio will be well above 1
- **Date written:** 2026-09-13 (after the fact)
- **Source:** Phase 1 handover, P1-03: *"Adjacent chunks from one article collapse
  into one document, so a naive top-5-chunks retriever structurally caps strict
  recall"*; the unit test it specifies expects a ratio *"≥ 2.5"* on a constructed
  case; §5 asks *"whether the candidate-pool cap of 50 chunks is right, given the
  collapse ratio observed"*. No number is stated for the corpus; the framing expects
  collapse to be a first-order effect.
- **Hypothesis, as stated:** five ranked chunks will often fold into fewer than five
  articles; the 50-chunk pool may be too small.
- **Tested by:** EXP-0004 (BM25) and EXP-0005 (dense), `collapse_ratio` mean / p90 and
  `pool_exhaustion_rate`.
- **Resolution:** **wrong.** Mean 1.088 (BM25) and 1.106 (dense); p90 1.20 and 1.40;
  maximum 2.8 (one question, 14 chunks for 5 documents); exhaustion 0 of 200 under
  both. On 138 of 200 questions the top five chunks were already five articles. The
  corpus profile explains it: 79% of articles fit in a single 600-word chunk, so most
  ranked chunks are whole articles and cannot collapse (EXP-0004 §Observations,
  DEC-040). The 50-chunk cap was never approached (OQ-021).

## H-004 — The baseline will answer most unanswerable questions
- **Date written:** 2026-09-13 (after the fact)
- **Source:** Phase 1 handover, P1-07 run 3: *"Run 3 measures how often the baseline
  confidently answers with no supporting document. The baseline has no refusal
  mechanism, so this is expected to fail."*
- **Hypothesis, as stated:** the false-answer rate on `unanswerable` will be high —
  "expected to fail" reads as a majority of the 45 answered.
- **Tested by:** EXP-0007, false-answer rate on `unanswerable` (n=45), by reason.
- **Resolution:** **wrong overall, confirmed on one third.** The system refused 33 of
  45 (false-answer rate 0.267, `refusal-lexical-v2` = hand count). It refused every
  other-platform question (15/15) and 13 of 15 post-snapshot ones — the prompt's
  "use ONLY the articles" and fixed refusal phrase were enough when the answer is
  visibly absent from the retrieved text. It failed as expected on the
  **underspecified** third: 10 of 15 answered, all with citations
  (`run_20260913_060733_6a9b`). The handover's mechanism ("no refusal mechanism") is
  true; its consequence was overstated for two of the three reasons.

---

## Calibration so far

| Entry | Source | Resolution |
|---|---|---|
| H-001 dense vs sparse | handover | wrong on margin; confirmed narrowly |
| H-002 multi lags single | handover | confirmed |
| H-003 collapse ratio ≫ 1 | handover | wrong |
| H-004 baseline answers most unanswerables | handover | wrong overall; confirmed on the underspecified third |

Four expectations from the handover: one confirmed, two wrong, one split. The two that
were wrong (H-003, H-004) were the two that reasoned from a mechanism ("chunks
collapse", "no refusal logic") to a size without measuring the corpus first — the same
shape as MIS-001, MIS-002 and MIS-013. The one that was right (H-002) was a structural
fact about the eval set (40 questions need 2–3 documents).

No entry here is Claude's prediction. Claude's intuitions go to `OPEN_QUESTIONS.md` as
questions with decision rules, per CLAUDE.md §3; if a Phase 2 story asks for a written
expectation before a run, it goes here as H-005 onward, dated before the run.

## H-005 — Embedding model differences will be small next to the dense-vs-sparse gap
- **Date written:** 2026-09-15, before any Axis 2 run
- **Source:** Claude. Not from the handover, which states no expectation for Axis 2.
- **Hypothesis:** on `dev_large`, the spread of strict recall@5 across the four
  models (text-embedding-3-large, qwen3-embedding-8b, bge-m3, gemini-embedding-2)
  will be under 0.10 — less than a third of the dense-vs-sparse gap on `dev`
  (0.305, EXP-0005 vs EXP-0004). Reasoning: all four are current, ≥1024-dim,
  long-context models on a corpus where 79% of articles fit one chunk; the retrieval
  task is closer to "find the right article" than to fine-grained passage ranking.
- **Tested by:** EXP-0008–EXP-0011, strict recall@5 on `dev_large`, max minus min.
- **Resolution:** pending.

## H-006 — bge-m3 will trail the two large models on multi-document questions
- **Date written:** 2026-09-15, before any Axis 2 run
- **Source:** Claude.
- **Hypothesis:** bge-m3 (1024-dim) will have the lowest multi-document strict
  recall@5 of the four on `dev_large`, and the gap to the best will be significant by
  `rag compare` (p < 0.05). Reasoning: it is the smallest model by a wide margin;
  multi-document questions need two or three distinct articles in the top five, the
  hardest slice on this corpus.
- **Tested by:** EXP-0010 vs the best of EXP-0008/0009/0011 on `gold_docs:multi`.
- **Resolution:** pending.

## H-007 — The `dev_large` and `dev` verdicts will agree in direction for every candidate
- **Date written:** 2026-09-15, before any Axis 2 run
- **Source:** Claude.
- **Hypothesis:** each candidate's sign of Δ strict recall@5 against the qwen control
  will be the same on `dev_large` and on `dev`. Reasoning: embedding quality is not
  the thing `dev_large`'s leakage inflates (that is lexical overlap, which flatters
  BM25, not one dense model over another). If this is wrong it is the more interesting
  result: it would mean the synthetic questions favour one model's training
  distribution.
- **Tested by:** the P2-04 agreement check in `rag promote` for EXP-0009–0011.
- **Resolution:** pending — first data point (EXP-0009) **disagrees**: `dev_large`
  +0.0085 (p = 0.0001), `dev` −0.005 (p = 1.0). The `dev` delta is one question and
  within noise, so "disagreement" here is a null on `dev` against a small real gain on
  `dev_large`, not opposite findings. Resolved after EXP-0010 and EXP-0011.
