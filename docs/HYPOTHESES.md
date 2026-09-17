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
- **Resolution:** **confirmed as stated, and the statement was about the wrong split.**
  On `dev_large` the four models span 0.973–0.988 (spread 0.015, well under 0.10) —
  but `dev_large` is single-gold synthetic questions at ceiling. On `dev` they span
  **0.560–0.750 (spread 0.190)**, more than half the dense-vs-sparse gap, driven by
  bge-m3's −0.160. The reasoning ("find the right article, all models current") held
  for synthetic questions and failed for user phrasings. `run_20260916_*`, EXP-0008–0011.

## H-006 — bge-m3 will trail the two large models on multi-document questions
- **Date written:** 2026-09-15, before any Axis 2 run
- **Source:** Claude.
- **Hypothesis:** bge-m3 (1024-dim) will have the lowest multi-document strict
  recall@5 of the four on `dev_large`, and the gap to the best will be significant by
  `rag compare` (p < 0.05). Reasoning: it is the smallest model by a wide margin;
  multi-document questions need two or three distinct articles in the top five, the
  hardest slice on this corpus.
- **Tested by:** EXP-0010 vs the best of EXP-0008/0009/0011 on `gold_docs:multi`.
- **Resolution:** **confirmed, and understated** — but only on `dev`, since `dev_large`
  has no multi-document slice (MIS-021). On `dev` bge-m3 has the lowest multi-document
  strict recall@5 of the three measured so far (0.225 vs 0.350 control, 0.300
  text-embedding-3-large); the paired test on that slice alone is p = 0.12 (n = 40, 1
  gained / 6 lost), while multi-document nDCG@10 is −0.209, p = 0.0001. The "smallest
  model" reasoning was right in direction; the gap is not confined to multi-document
  questions — single-document lost 0.169. Final ranking waits for EXP-0011.

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
  `dev_large`, not opposite findings. **EXP-0010 resolves it: wrong.** bge-m3 is
  +0.005 (p = 0.019) on `dev_large` and −0.160 (p = 0.0001) on `dev`. The reasoning
  ("leakage inflates lexical overlap, which favours BM25 but not one dense model over
  another") was wrong: a dense model trained toward surface paraphrase is flattered by
  synthetic questions in exactly the way BM25 is. Recorded as the direct evidence for
  DEC-055.

## H-008 — The qwen instruct prefix is why the control misses synthetic `feature_request` questions
- **Date written:** 2026-09-16, before EXP-0012 ran
- **Source:** Claude.
- **Hypothesis:** with `prefix_convention: none`, the control's strict recall@5 on
  `dev_large`'s `feature_request` slice rises from 0.966 to ≥ 0.99 (C2 in the config
  header of `configs/exp_0012_qwen_noprefix_dev_large.yaml`). Reasoning: the prefix
  instructs the model to find passages that *answer* the query; for "Can I do X?"
  questions whose gold is a "Request: X" article (a feature that does not exist), the
  answering passage is the how-to for the nearest existing feature — which is what the
  control ranks first (66 of 66 common flips). Without the instruction the query
  should sit closer to the request article's title wording.
- **Also expected:** on `dev` (no feature-request gold documents) the change is within
  noise either way — the prefix's value on real questions is the part I cannot guess.
- **Tested by:** EXP-0012 against EXP-0008 (`dev_large`) and `promoted` (`dev`), per
  the criteria C2/C3 in the config header.
- **Resolution:** **wrong by the pre-registered threshold, right in direction.** The
  slice rose 0.966 → 0.988 (p = 0.0001; 53 of the 67 questions), not to ≥ 0.99 — the
  prefix is most of the cause, not all of it. The part I said I could not guess was
  the decisive one: removing the prefix cost 0.060 strict recall@5 on `dev`
  (p = 0.035), so "within noise either way" was **wrong** too. `run_20260917_050235_e588`,
  `run_20260917_070405_a562`.

## H-009 — Truncating the control to 1024 dimensions costs less than bge-m3's 1024 dimensions did
- **Date written:** 2026-09-17, before EXP-0013 ran
- **Source:** Claude.
- **Hypothesis:** the 1024-d control will be within noise of the 4096-d control on
  `dev` strict recall@5 (|Δ| ≤ 0.02, p > 0.05), and far above bge-m3's 0.560 at the
  same width. Reasoning: Qwen3-Embedding is trained with Matryoshka objectives so its
  leading dimensions carry most of the ranking signal; bge-m3's deficit (EXP-0010) came
  with the model, not the width. If instead the 1024-d control lands near 0.560, width
  was the story all along and EXP-0010's conclusion needs rewriting.
- **Tested by:** EXP-0013 vs `promoted` on `dev` (paired test), and vs EXP-0008 on
  `dev_large`.
- **Resolution:** pending.
