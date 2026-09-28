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
- **Resolution:** **confirmed.** `dev` Δ −0.015 (p = 0.55), inside the |Δ| ≤ 0.02 bound;
  0.705 at 1024-d against bge-m3's 0.560 at the same width. `dev_large` identical
  (Δ +0.0002). The only significant movement was strict recall@1 on `dev_large`,
  −0.005 (p = 0.004). `run_20260917_071034_7a2d`, `run_20260917_085730_9ea7`.

## H-010 — Fusion does not beat the dense control on `dev` at p < 0.05
- **Date written:** 2026-09-17, before any Axis 3 run
- **Source:** Claude.
- **Hypothesis:** no hybrid configuration (EXP-0014 RRF, EXP-0015–0018 weighted)
  clears DEC-055's bar against `promoted` on `dev` strict recall@5: every Δ has
  p ≥ 0.05. Reasoning from measured data, not from the literature: H-001 found BM25
  won **nine** questions against dense and lost seventy (EXP-0004 vs EXP-0005). Nine
  is the ceiling on what fusion can recover from the sparse side; the bar needs
  roughly fifteen net flips (DEC-055). Unless fusion also re-orders questions that
  *both* halves already answer — possible, since strict recall@5 is decided by ranks
  4–6 on collapsed questions — the arithmetic does not reach significance. If this is
  wrong, the interesting number is how many of the gained questions were ones
  neither half answered alone.
- **Tested by:** `rag compare promoted <run>` on `dev` for each of the five runs.
- **Resolution:** **confirmed.** RRF p = 0.0012 (negative), α=0.2 p = 0.0001 (negative),
  α=0.4 p = 0.0006 (negative), α=0.6 p = 0.72, α=0.8 p = 0.75 — no hybrid clears the
  bar. The reasoning was half right: the gains from the lexical side were 6–14
  questions at every setting (RRF 14, α=0.6 13, α=0.8 6), and 5 of RRF's 14 were
  questions neither half answered alone — the "unless" clause happened, but on five
  questions. What the hypothesis did not anticipate was the size of the *losses* at
  low α and under RRF (38–57), which made three of the five runs significantly
  negative rather than null. `run_20260917_174747_7c9f`, `…_181731_627b`,
  `…_183840_42f5`, `…_184010_ae88`, `…_184123_a6e3`.

## H-011 — The alpha curve rises with the dense weight and its ends bracket the two controls
- **Date written:** 2026-09-17, before any Axis 3 run
- **Source:** Claude.
- **Hypothesis:** strict recall@5 on `dev` is monotone non-decreasing over
  α = 0.2 → 0.4 → 0.6 → 0.8, with α=0.2 below the dense control (0.720) and above the
  sparse control (0.410), and α=0.8 within 0.03 of the dense control. Reasoning: the
  two halves are 0.305 apart on this split, so a weight that moves the ranking toward
  the weaker half should cost recall roughly in proportion. A non-monotone curve — a
  peak in the middle — would be the result worth having, because it would mean the
  lexical signal is complementary on some questions rather than just weaker.
- **Tested by:** the four weighted runs' strict recall@5, plus `rag compare` between
  adjacent alphas for whether adjacent points differ at all.
- **Resolution:** **confirmed** on every clause. 0.495 → 0.590 → 0.705 → 0.730,
  monotone; α=0.2 is above BM25 (0.410, +0.085, p = 0.0001) and below dense (0.720);
  α=0.8 is +0.010 from dense, inside the 0.03 bound. Adjacent steps: +0.095
  (p = 0.0001), +0.115 (p = 0.0002), +0.025 (p = 0.36) — the curve flattens between
  0.6 and 0.8. No peak in the middle: the lexical signal is weaker, not complementary,
  at the document level on this split. `run_20260917_181731_627b`, `…_183840_42f5`,
  `…_184010_ae88`, `…_184123_a6e3`.

## H-012 — Under RRF, BM25-only documents reach the five-document context on fewer than one question in ten
- **Date written:** 2026-09-17, before any Axis 3 run
- **Source:** Claude.
- **Hypothesis:** in EXP-0014's `fusion_stats`, `context_docs_by_source.bm25_only`
  is under 10% of context documents (fewer than 100 of ~1,000 across 200 questions),
  and the mean candidate-set Jaccard overlap between the two halves' top-100 lists is
  above 0.3. Reasoning: the corpus profile says the halves are looking at the same
  6,221 short articles, and H-001's nine BM25 wins were exact product-name matches,
  which dense also finds — just lower. If instead BM25-only documents are common in
  the context, the lexical signal is contributing more than its solo recall suggests.
- **Tested by:** `retriever_meta.fusion_stats` on the EXP-0014 run row.
- **Resolution:** **half wrong.** BM25-only context documents: 1 of 1,000 (the
  "under 10%" half holds — but by a mechanism the hypothesis did not name: under RRF
  a document in one list only is out-scored by almost anything in both, so 999 of
  1,000 context documents came from the intersection). Mean candidate Jaccard:
  **0.196, not above 0.3** — the two halves' top-100 lists share about a fifth of
  their chunks. `run_20260917_174747_7c9f`.

## H-013 — No chunker beats the control on `dev` strict recall@5 at p < 0.05
- **Date written:** 2026-09-18, before any Axis 1 run
- **Source:** Claude.
- **Hypothesis:** none of EXP-0019–0022 clears DEC-055's bar against `promoted` on
  `dev`. Reasoning from measured data: 79.0% of articles fit in one 600-word chunk
  (corpus profile), the collapse ratio is 1.1 (EXP-0005), and two chunking changes
  under BM25 each moved one question (EXP-0002/0003). For four fifths of the corpus
  the chunker has nothing to change; the multi-document slice was called "a ranking
  problem, not a granularity problem" in NARRATIVE §6, and this axis tests that
  sentence directly. If wrong, the gain will be concentrated in the long fifth of
  the corpus, which the per-question flips can show.
- **Tested by:** `rag compare promoted <dev run>` for each of the four.
- **Resolution:** **confirmed.** `dev` strict recall@5: parent-document 0.695
  (p = 0.46), semantic 0.675 (p = 0.078), structure 0.665 (p = 0.033), sentence-window
  0.530 (p = 0.0001) against the control's 0.720. None beats it; two are negative. The
  stated reasoning was wrong in its mechanism, though: I expected a flat curve because
  79% of articles fit in one control chunk, but three of the four chunkers re-cut
  almost everything (semantic left 2.9% of articles whole, sentence-window 0.5%), so
  the axis was never testing "chunk width on the long fifth" — it was testing much
  finer chunking against coarse, and finer lost monotonically. `run_20260919_014505_4c6e`,
  `run_20260919_030111_72ea`, `run_20260922_083410_9f8a`, `run_20260923_042438_c9b1`.

## H-014 — Sentence-window raises the collapse ratio the most and multi-document strict recall the least
- **Date written:** 2026-09-18, before EXP-0019 ran
- **Source:** Claude.
- **Hypothesis:** EXP-0019's collapse ratio (mean) is the highest of the axis and
  above 2.0; its multi-document strict recall@5 is no higher than the control's
  0.350. Reasoning: 196k one-sentence rows means many sentences of one article
  rank near each other; the DEC-040 walk then scans several chunks per document
  found, which is what the collapse ratio counts, and the 50-chunk pool can be
  exhausted before five distinct articles are found on multi-article questions.
  This is the confound P2-07 names (small-to-big overlaps with the document walk)
  turned into a number.
- **Tested by:** `collapse_ratio_mean`, `pool_exhaustion_rate` and the
  `gold_docs:multi` slice on EXP-0019's `dev` run vs `be04`.
- **Resolution:** **half right.** Highest collapse of the axis: yes — 1.314 on `dev`
  and 1.490 on `dev_large` (p90 2.2), against the control's 1.106. **Above 2.0: no**,
  and the reason is instructive: the 50-chunk pool caps the walk, and the gold article
  usually has only one or two sentences in that pool, so there is little to collapse.
  Multi-document strict recall was no higher than the control (0.250 vs 0.350, 3 / 7),
  as stated, but within noise on n = 40 — and the overall loss (−0.190) dwarfs it, so
  the multi-document clause was right for the wrong reason: the ranking got worse
  everywhere, not specifically on multi-article questions. Pool exhaustion stayed 0.
  `run_20260923_042438_c9b1`, `run_20260922_084139_aaf1`.

## H-015 — Structure chunking is within noise of the control everywhere
- **Date written:** 2026-09-18, before EXP-0022 ran
- **Source:** Claude.
- **Hypothesis:** |Δ| ≤ 0.02 on `dev` strict recall@5 (p > 0.05), and `dev_large`
  within ±0.005. Reasoning: 8,689 chunks vs 8,218, the same 79.0% of articles in one
  chunk, and the only articles whose cuts move are the long fifth. It cuts 41
  procedure blocks where the control cuts 0, so if anything moves it is the
  procedural questions, and the story wants that number reported either way.
- **Tested by:** EXP-0022 vs `promoted` on `dev`; vs EXP-0008 on `dev_large`.
- **Resolution:** **wrong on both splits.** `dev` Δ −0.055 (p = 0.033; 6 / 17), outside
  the ±0.02 bound; `dev_large` +0.0088 (p = 0.0002), outside ±0.005 — and the two
  disagree in direction. The reasoning missed two things: half the `dev` losses are
  on single-chunk articles whose words did not change (line breaks + a fresh embed
  did, OQ-031), and the `dev_large` gain is once more the `feature_request` slice
  (54 / 0). `run_20260918_235010_d53e`, `run_20260919_014505_4c6e`.

## H-016 — Semantic chunking produces more, shorter chunks than the control and does not change recall
- **Date written:** 2026-09-18, before EXP-0021 ran
- **Source:** Claude.
- **Hypothesis:** the 95th-percentile rule yields between 9,000 and 14,000 chunks
  (one to two boundaries in most multi-sentence articles); `dev` strict recall@5
  within ±0.03 of the control (p > 0.05). Reasoning: with a median of 11 sentences
  per article the 95th percentile of ten distances is usually the single largest
  one, so most articles get one cut; a one-cut article yields two chunks that
  both still map to the same document under max pooling. The number of chunks is
  the part I am least sure of and is why it is written down.
- **Tested by:** `chunking_profile.n_chunks` on the EXP-0021 run row; `rag compare`
  on `dev`.
- **Resolution:** **wrong on the chunk count, right on recall.** 19,296 chunks, not
  9,000–14,000 — and the number that exposes the error is the one I did not predict:
  **only 2.9% of articles stayed whole** (the control leaves 79.0%). My reasoning
  assumed "the 95th percentile of ten distances is usually the single largest one, so
  most articles get one cut"; what I missed is that the rule is per article, so every
  article with three or more sentences gets at least one cut no matter how coherent it
  is, and the median article has eleven. Recall: −0.045 on `dev`, inside the stated
  ±0.03? No — just outside, at p = 0.078, which the tool calls no measurable
  difference. Counted as wrong on the count, inconclusive on the bound.
  `run_20260922_083410_9f8a`, `run_20260922_061430_500f`.

## H-017 — A cross-encoder gains more than any Phase 2 axis so far, and the gain is on `multi_doc`
- **Date written:** 2026-09-22, before any Axis 5 run
- **Source:** Claude.
- **Hypothesis:** at least one of the three rerankers improves `dev` strict
  recall@5 by **more than +0.03 at p < 0.05** over the dense control's 0.720 — the
  first positive Axis result of Phase 2 — and the gain is larger on the `multi_doc`
  slice than on `single_doc`. Reasoning: every Phase 2 axis so far has changed *what
  gets indexed* and the answer has been "no measurable difference or worse" four
  times (Axis 1) and three times (Axis 3). A reranker changes something none of them
  touched: it reads the question against the passage instead of comparing two
  independently-made vectors. The multi-document part of the guess is the shakier
  half — the `multi_doc` slice is 20 questions, so it can move a lot without meaning
  anything, and I am writing it down because it is the part I expect to be wrong.
- **Tested by:** `rag compare promoted <run> --metric strict_recall@5` on `dev`, per
  slice, for EXP-0024 / EXP-0025 / EXP-0026.
- **Resolution:** **wrong, on both halves** — though only EXP-0024 ran, so this is
  answered for `cohere/rerank-v3.5` and not for reranking (OQ-035). Strict recall@5
  went **down** 0.720 → 0.665 (p = 0.139), not up by 0.03; Axis 5 joins Axes 1, 2 and
  3 with no measurable difference. And `multi_doc` was the *worse* of the two gold
  slices to bet on: −0.050 at p = 0.732 against `single_doc`'s −0.056, i.e. both flat
  and neither distinguishable, exactly the "20 questions can move without meaning
  anything" caveat I wrote down. What I did not predict is the shape that did appear:
  **+0.065 at rank 1 and exactly 0.000 at rank 20**. My reasoning — "a reranker reads
  the question against the passage instead of comparing two independently-made
  vectors" — was right about the mechanism doing something, and wrong to assume that
  something would be monotone in recall. `run_20260923_052941_4ada`.

## H-018 — Reranking raises the collapse ratio, and the ceiling is the retriever's recall@50
- **Date written:** 2026-09-22, before any Axis 5 run
- **Source:** Claude, and the P2-10 story, which asks for this explicitly:
  *"a cross-encoder can re-concentrate results onto a single article and undo the
  document diversity the retriever was configured to produce."*
- **Hypothesis:** two parts.
  1. The post-rerank collapse ratio rises above the control's 1.106 for every
     reranker — a cross-encoder scoring each passage alone has no reason to spread
     its top scores across articles, where the retriever's document walk was built
     to. Parent-document chunking is the only Phase 2 config that has moved this
     number so far (1.106 -> 1.315, EXP-0020).
  2. No reranker exceeds the dense control's strict recall **@50 documents**,
     because a reranker cannot retrieve — it can only promote what was already in
     the candidate set. That number is the axis's hard ceiling and it is already on
     the EXP-0005 run row.
- **Tested by:** `collapse_ratio_mean` on each Axis 5 run row vs EXP-0005's; and
  each run's strict recall@5 against the control's strict recall@20/@50.
- **Resolution:** **part 1 wrong, part 2 confirmed.**
  1. The collapse ratio barely moved: **1.106 → 1.113**, p90 unchanged at 1.40, no
     pool exhaustion. I reasoned that a cross-encoder scoring each passage alone "has
     no reason to spread its top scores across articles"; that is true and still
     produced nothing, because on this corpus **79% of articles are a single chunk**,
     so there is usually no second chunk of the same article available to promote.
     The re-concentration P2-10 warns about is a real failure mode that this corpus
     cannot express. The prediction was about the reranker; the answer was about the
     documents.
  2. Confirmed, and more exactly than expected: strict recall@**20** is
     **0.920 → 0.920, p = 1.000**, with 9 questions gained and 9 lost. The reranker
     re-orders 50 candidate documents and cannot exceed that set's recall — the
     ceiling is not approached, it is sitting on it.
  `run_20260923_052941_4ada`.

## H-019 — MMR was expected to help multi-document questions; no entry was written first
- **Date written:** 2026-09-24, **after EXP-0027 ran**. Recorded as a miss.
- **Source:** Claude, and the P2-13 story, which prioritises MMR on the stated ground
  that *"diversity directly serves multi-document coverage, which is the organizing
  question."*
- **What should have been written, and was not:** this file's rule is that an entry is
  written **before** the run it names. For EXP-0027 none was. The expectation existed —
  the story states it, the configs were built around it, and the axis was chosen over
  P2-11 partly because MMR targets the multi-document slice — but it was never
  committed to paper before the numbers arrived. That is a process failure and it is
  recorded here rather than back-filled as though it had been a prediction.
- **What happened:** the opposite, monotonically. `multi_doc` 0.350 → 0.000 at λ=0.3,
  14 questions lost and 0 gained. The handover's premise is measurably wrong on this
  corpus, and the reason is measurable too: two gold documents of one question are
  **+0.095 more similar to each other** than a gold is to an average candidate, so
  MMR's redundancy term penalises the second gold hardest.
- **Resolution:** **not scoreable as a prediction** — nothing was predicted in time.
  The finding stands on the runs (`run_20260924_041357_ebc5` and the λ curve); the
  calibration value of this entry is zero, which is the cost of having skipped it.

## H-020 — Lost-in-the-middle reordering does nothing here, because the prompt is too short for it
- **Date written:** 2026-09-24, before EXP-0028 ran
- **Source:** Claude.
- **Hypothesis:** reordering changes **no** deterministic generation metric by more
  than its noise floor — citation precision, citation recall, refusal rate and step
  coverage all land inside the `dense-control-v1` MDD. Reasoning, and this is an
  engineering argument rather than a quality one: Liu et al. 2023 measured the
  mid-prompt dip across contexts of **2,700 to 21,000 tokens** with 10 to 30
  retrieved documents. This run assembles **5** documents into a prompt whose budget
  is 6,000 words, and the measured mean context is ~1,740 words. There may be no
  "middle" to get lost in at that length. The part I expect to be wrong: if the
  generator is more position-sensitive than its context window suggests, citation
  **recall** is where it would show, because a document the model never read is a
  document it cannot cite.
- **What would change my mind before the run:** nothing — it is cheap and it runs.
- **Tested by:** the deterministic generation metrics of EXP-0028 against EXP-0006's
  three runs, labelled by `rag/eval/noise_floor.py`. **No retrieval delta may be
  reported for this run**, by construction (P2-13); `tests/test_assembly_p2_13.py`
  proves the reordering is a permutation.
- **Resolution:** **confirmed, and the reasoning held rather than merely the
  conclusion.** Every deterministic generation metric landed inside its MDD: citation
  precision Δ −0.021 (p = 0.558), citation recall Δ −0.005 (p = 1.000), step coverage
  Δ −0.008 (p = 0.792), refusal Δ −0.010 (p = 1.000), step order Δ 0.000 (p = 1.000).
  Nothing significant on any slice, lowest p anywhere 0.106. The stated mechanism was
  also measured: the assembled context came in at **1,712 words ≈ 2,174 tokens**,
  *below* the 2,700-token floor of the range Liu et al. measured — so "there may be no
  middle to get lost in at that length" was checkable and checked, not a hedge.
  The part I flagged as most likely wrong — "citation **recall** is where it would
  show" — was the right thing to flag: recall is exactly where the churn appeared.
  **15 questions changed citations and 13 of them had an identical retrieved set and
  ranking**, six up and seven down, netting −0.005 at p = 1.000. I predicted no metric
  movement and got it; I did not predict that 13% of answers would change underneath a
  flat number. `run_20260925_014154_2d6b`.

## H-021 — Compression buys a large token reduction and loses procedure steps doing it
- **Date written:** 2026-09-24, before EXP-0029 ran
- **Source:** Claude.
- **Hypothesis:** two halves, and they are deliberately separable.
  1. `context_word_reduction` is **above 0.40** — the technique removes at least 40%
     of the words reaching the generator.
  2. **Step coverage falls by more than its noise floor**, and falls further than
     citation precision does. Reasoning: this corpus's answers are procedures, and a
     procedure is the one kind of text where the *least individually relevant*
     sentence ("Click Save.") is load-bearing. An extractive filter scoring sentences
     against the question has no way to see that step 4 matters only because steps 1
     to 3 preceded it. The prompt explicitly tells the model to keep whole procedures
     including lead-in lines, so this hypothesis is also a test of whether that
     instruction is obeyed — `chunks_kept_verbatim_check_failed` and
     `chunks_dropped` are the diagnostic if it is not.
- **Tested by:** EXP-0029's `context_word_reduction` for part 1; step coverage and
  citation precision/recall against EXP-0006, MDD-labelled, for part 2. No retrieval
  delta is reported.
- **Resolution:** **part 1 confirmed, part 2 wrong — and wrong about the mechanism,
  which is the more useful half of the miss.**
  1. Word reduction **0.467**, above the 0.40 I named. (0.542 under the checker fixed in
     MIS-035, simulated over the same cached completions.)
  2. Step coverage did **not** fall. It rose, +0.0191 at p = 0.734, and step order was
     preserved slightly more often. The prompt's instruction to keep whole procedures
     including their lead-in lines was evidently obeyed — my reasoning that "an
     extractive filter has no way to see that step 4 matters only because steps 1 to 3
     preceded it" was a real risk that the prompt had already covered.
  What actually broke is a thing I never named: **citation recall, −0.0883 at p = 0.0358
  (MDD 0.040)** — the first significant deterministic result in Axis 6. The mechanism is
  not lost steps but **lost documents**: the compressor dropped 37.4% of retrieved chunks
  entirely. It dropped them well (43.9% of non-gold against 8.7% of gold, a five-fold
  discrimination ratio), and still, of the 17 questions whose citation recall fell, 6 had
  a gold chunk dropped and **11 kept every gold chunk and lost the citation anyway**.
  Shortening the text around a relevant passage makes this generator less likely to cite
  the document it came from. I predicted the wrong metric via the wrong mechanism and got
  the direction right by accident. `run_20260925_025103_28d7`.

## H-022 — Contextual retrieval is the first Phase 2 technique to beat the dense control
- **Date written:** 2026-09-24, before EXP-0030 ran
- **Source:** Claude, and OQ-021 (the external claim this run converts into a measurement).
- **Hypothesis:** `dev` strict recall@5 improves by **more than +0.03 at p < 0.05**
  over the control's 0.720. Reasoning, and the reason this is worth $0.82: every Axis
  1, 2, 3 and 5 experiment either re-cut the index or re-ordered a fixed candidate
  set, and all of them failed. This one adds *information that is not in the chunk* —
  the article's subject, written in the article's own vocabulary — to the thing being
  embedded. The measured failure mode on this corpus is "right document, ranked 6th",
  which is a discrimination problem, and a prefix naming the product is discriminating
  information.
- **The half I expect to be wrong, and why it is written down:** **79% of articles
  are a single chunk** (DEC-038). For those, the prefix summarises a document the
  chunk already contains in full, so it can add almost nothing and may actively
  dilute the embedding by spending 60 of the chunk's words on restatement. If the
  effect is real it should therefore be **concentrated in the 21% of chunks from
  multi-chunk articles**, and the overall number may be flat while that subset moves.
  That subset comparison is the measurement I care about more than the headline.
- **Tested by:** `rag compare promoted <run> --metric strict_recall@5` on `dev`, per
  slice, for EXP-0030. Plus the one-time index cost, recorded on the row.
- **Resolution:** **the headline claim is wrong; the caveat I flagged as most likely to
  matter is right, and it is the more useful half.**
  I predicted strict recall@5 would improve by **more than +0.03 at p < 0.05**. Measured:
  **+0.0050 at p = 1.000** (16 gained / 15 lost), and +0.0100 at p = 0.857 on the
  warm-cache repeat. Axis 6 joins Axes 1, 2, 3 and 5 with no measurable difference.
  The caveat was the valuable part. I wrote that the effect "should therefore be
  concentrated in the 21% of chunks from multi-chunk articles" and that "that subset
  comparison is the measurement I care about more than the headline." It was, and it is:
  **one-chunk gold articles are perfectly inert — 0.780 → 0.780, four gained and four
  lost** — while every bit of movement sits in the multi-chunk half at **+0.010 (12/11)**.
  The mechanism I reasoned about was real and its magnitude was nil.
  Two things I did not anticipate. **The dev split is 50% multi-chunk against the
  corpus's 21%**, so this ran on a subset 2.4x enriched for the condition the technique
  needs and still returned +0.010 — a stronger negative than the headline alone. And the
  losses are **not** failures of the prefix: a gold with an accurate prefix fell from rank
  1 to outside the top 5, because **every competitor was prefixed too**. I framed this as
  "does the prefix add discriminating information?" when the right question was "does it
  add information that discriminates *between candidates*?" A uniform lift cannot
  re-rank. `run_20260925_045759_b1c7`.

## H-023 — Decomposition helps multi-document questions, and mostly declines to fire
- **Date written:** 2026-09-25, before EXP-0031 ran
- **Source:** Claude, and the P2-12 story, which orders decomposition first on the
  ground that it is aimed most directly at the organizing question.
- **Hypothesis, in two separable halves.**
  1. `multi_doc` strict recall@5 improves by **more than +0.05**, against the control's
     0.350. Reasoning: this is the only technique in the project that lets one question
     issue more than one retrieval, and the measured failure on multi-document questions
     is that one query cannot rank two different articles into the top five at once.
  2. **Overall strict recall@5 does not move**, because the transform will decline to
     split most questions. A 6-question probe produced a mean of **1.33 sub-questions**,
     with 4 of 6 returned unsplit — and 160 of the 200 dev questions have a single gold
     document, so for most of the split there is nothing to decompose.
- **The part I expect to be wrong:** that the sub-queries retrieve *different*
  documents. On a single-product help centre two sub-questions about one task may pull
  back the same articles, in which case RRF over near-identical rankings reproduces the
  control. `distinct_doc_yield_per_query` is recorded to settle exactly this, and it is
  the number I care about most in this run.
- **Tested by:** `rag compare promoted <run> --metric strict_recall@5` on `dev`, per
  slice; plus `mean_generated_per_question` and `mean_new_docs_per_extra_query`.
- **Resolution:** **wrong on both halves, and wrong about the part I flagged as most
  uncertain — which turned out to be the mechanism.**
  1. I predicted `multi_doc` would improve by **more than +0.05**. It **fell 0.050**
     (0.350 → 0.300, 3 lost / 1 gained, p = 0.628 at n=40).
  2. I predicted overall recall would **not move**, because the transform would decline
     to split most questions. The premise was right — 1.27 sub-questions, 150 of 200
     unsplit, 145 of those verbatim — and the conclusion was wrong: those 150 reproduce
     the control (0.713 → 0.707) while the **50 that were split went 0.740 → 0.540**,
     which moves the whole split by −0.055 at **p = 0.0186**.
  3. The part I named as most likely wrong, and said I cared about most, was whether the
     sub-queries retrieve *different* documents. Measured: **40.8 new documents per extra
     sub-query.** They retrieve very different documents. **I had the sign of that
     quantity inverted** — I treated a high distinct-document yield as the success
     condition, when it is the failure condition. Retrieving 41 documents that answer
     half the question is *how* the one document answering all of it leaves the top five.
  The corpus fact underneath: decomposition assumes documents are indexed by sub-fact. A
  help centre is indexed by task, and a multi-part user question is usually one task.
  `run_20260925_063044_0da8`.

## H-024 — HyDE helps single-document recall and this split cannot show it
- **Date written:** 2026-09-25, before EXP-0032 ran
- **Source:** Claude, and the P2-12 story's note that HyDE and step-back are expected to
  help single-doc recall more than multi-hop.
- **Hypothesis:** overall strict recall@5 lands **within ±0.03 of the control**, i.e. no
  measurable difference, and the `gold_docs:single` slice moves less than the story
  expects because it is close to its ceiling: single-gold recall@5 is already **0.8125**,
  and the measured ceiling for the whole split at candidate depth 50 is 0.985. There is
  about 0.17 of headroom on that slice and 40 questions' worth of noise around it.
- **Mechanism worth naming:** HyDE replaces a 20-word question with a ~120-word generated
  passage, so the query vector is dominated by generic help-article phrasing ("Log in to
  your Wix account and go to…") that every article in this corpus shares. On a
  single-product corpus that may be *anti*-discriminating, which is the same failure MMR
  had in EXP-0027 — a technique whose premise is variety, applied to a corpus with none.
- **Tested by:** `rag compare` per slice on `dev`, reporting single-doc explicitly
  against its ceiling.
- **Resolution:** **the headline claim was right and the reasoning behind it was wrong.**
  Overall strict recall@5 landed at **+0.0150 (p = 0.754)**, inside the ±0.03 I named.
  The ceiling half held exactly: `gold_docs:single` went 0.8125 → 0.8063 at p = 1.000,
  with about 0.17 of headroom to the measured 0.985 ceiling and 40 questions of noise
  around it — the story's expectation that HyDE would help single-doc most is not
  testable on this split, which is itself the answer to that part.
  The **mechanism I proposed is not supported**. I argued that a 120-word generated
  passage would be dominated by generic help-article phrasing and so be
  *anti*-discriminating on a single-product corpus — "the same failure MMR had". If that
  were happening recall would have fallen. Instead it rose slightly, and
  **`gold_docs:multi` rose 0.350 → 0.450**, the largest movement that slice has shown
  across six techniques. I reasoned by analogy to EXP-0027 and the analogy did not hold:
  MMR's problem was choosing *between* candidates on similarity, HyDE's input is a
  different query, and those are not the same operation. `run_20260925_064215_4033`.

## H-025 — Multi-query expansion is the one most likely to do nothing at all
- **Date written:** 2026-09-25, before EXP-0033 ran
- **Source:** Claude.
- **Hypothesis:** overall strict recall@5 within **±0.02** of the control, and
  `mean_new_docs_per_extra_query` **below 1.0** — each paraphrase finds less than one
  document the original did not. Reasoning: the probe's rewrites are faithful and
  fluent, and that is precisely the problem. *"How do I change my domain?"* rewritten as
  *"How can I switch the web address of my Wix site?"* is a different sentence with the
  same content words after embedding. Dense retrieval is not keyword matching; a
  paraphrase that preserves meaning should retrieve nearly the same ranking, and RRF over
  near-identical rankings returns the original.
- **What would falsify it:** a high new-document yield per rewrite. If paraphrases *do*
  pull back different articles, the embedding space is more phrasing-sensitive than
  assumed, which would be a more interesting finding than the recall number.
- **Tested by:** `rag compare` on `dev`, plus `mean_new_docs_per_extra_query`.
- **Resolution:** **number right, mechanism wrong — and I said in advance which would be
  the more interesting outcome.**
  Overall strict recall@5 moved by **exactly 0.0000 (p = 1.000, 12 gained / 12 lost)**,
  inside the ±0.02 I named and about as clean a null as the instrument can produce.
  The mechanism was **wrong**. I predicted `mean_new_docs_per_extra_query` **below 1.0**,
  on the reasoning that "a paraphrase that preserves meaning should retrieve nearly the
  same ranking". Measured: **16.8**. I wrote that a high yield "would be a more
  interesting finding than the recall number", and it is: together with EXP-0031's 40.8,
  it says this embedding space is far more sensitive to phrasing than a "semantic search"
  framing suggests. Two hypotheses in this axis predicted phrasing-insensitivity and both
  were wrong the same way.
  One thing I did not predict at all: **`q_len:short` fell 0.0946 at p = 0.016, with 7
  questions lost and 0 gained** — the only slice in the axis with an empty side. A short
  question is already close to a bare keyword query; three longer paraphrases pull the
  fused ranking off the literal match and there is nothing ambiguous for them to
  resolve. `run_20260925_070609_71df`.

## H-026 — Step-back hurts, because it invents a product the question never named
- **Date written:** 2026-09-25, before EXP-0034 ran
- **Source:** Claude, from a measured defect in the 6-question probe.
- **Hypothesis:** overall strict recall@5 **falls**, by more than the re-embedding floor
  of 0.010 (EXP-0023). This is the only technique in the axis I expect to be actively
  negative, and the reason is not the technique but its interaction with this corpus.
- **Measured in the probe, not predicted:** on **2 of 6** dev questions the step-back
  question named **"Wix Bookings"** when the original mentioned no product at all —
  *"How to make the published changes draft?"* became *"How does Wix Bookings handle
  published changes draft?"*, and a payment-settings question became *"How does Wix
  Bookings handle payouts being on hold?"*. The prompt instructs the model to keep the
  product name; when there is none to keep, it supplies one. A fabricated product name
  is a strong retrieval signal pointing at the wrong articles, and RRF will promote
  whatever that ranking agrees with.
- **The honest caveat:** 2 of 6 is a rate measured on six questions and could be
  anywhere from rare to typical. `n_queries`, the per-question rankings and the failure
  list are recorded; if the rate is low the effect may be invisible.
- **Tested by:** `rag compare` on `dev`, plus a count of step-back questions naming a
  product absent from the original.
- **Resolution:** **direction right, magnitude under-stated, mechanism over-attributed.**
  I predicted a fall of more than the 0.010 re-embedding floor. It fell **0.0750, CI
  [−0.130, −0.020], p = 0.0169** — significant, the worst result in Axis 4, 25 questions
  lost against 10 gained.
  The defect I named from a 6-question probe is real and **more common than I would have
  guessed: 46 of 200 step-back questions (23.0%) named a Wix product the original never
  mentioned**, the model's default guess being "Bookings". *"How to make the published
  changes draft?"* became *"How does Wix Bookings handle published changes draft?"*.
  **But only 6 of those 46 questions lost the gold — about a quarter of the 25 losses.**
  I attributed the damage to a mechanism that accounts for a minority of it. The rest is
  the failure the whole axis shares: the step-back question retrieved **34.7 documents
  the original did not**, doing exactly what it was meant to, and RRF at equal weight
  then ranks "best overview article" above "good specific article" — while the gold on a
  help centre is almost always the specific one.
  I also wrote "if the rate is low the effect may be invisible." The rate was high *and*
  the effect is significant, but largely through a different channel. Being right for
  partly the wrong reason is worth recording as plainly as being wrong.
  `run_20260925_074024_9154`.

## H-027 — Citation enforcement cuts false answers and costs false refusals
- **Date written:** 2026-09-25, before EXP-0039 ran
- **Source:** Claude.
- **Hypothesis:** the false-answer rate on `unanswerable` falls below the corrected
  baseline of **0.2667** by more than 0.05, and the false-refusal rate on answerable
  `dev` questions rises above the control's **0.0299**. Reasoning: the prompt makes a
  citation a precondition for writing a step and names refusal as the explicit fallback,
  so it should push behaviour toward refusing — in both directions at once. This is the
  cheapest possible intervention on the trade-off and I expect it to be a *trade*, not a
  free move.
- **The part I expect to be wrong:** that the two move by similar amounts. A prompt
  instruction is a blunt instrument and may move one number a lot and the other not at
  all, in which case the interesting question is which.
- **Tested by:** false-answer rate on the full `unanswerable` split and false-refusal
  rate on `dev` (gold-in-context questions only, MIS-012), against EXP-0007/EXP-0006.
- **Resolution:** **wrong on both halves, and wrong in the same direction on each.**
  I predicted the false-answer rate would **fall** by more than 0.05 and the
  false-refusal rate would **rise** — a trade. Measured: false answers rose
  **0.2667 → 0.8444 (+0.578)** and false refusals fell to **exactly zero**, with the
  system producing **no refusals at all across 145 questions on both splits**.
  My reasoning was that naming refusal as the explicit fallback "should push behaviour
  toward refusing". It pushed the opposite way, because the *other* instruction in the
  same prompt — cite every step — is easier to satisfy by describing a document than by
  declining: *"1. The provided articles cover currency changes for Wix products, not
  Squarespace."* I treated two instructions in one prompt as additive when they compete,
  and the cheaper one won.
  I did write that I expected the two numbers to move by dissimilar amounts and that
  "the interesting question is which". They did move dissimilarly, in directions that
  were not among the options I allowed for. `run_20260925_205710_eb8f`.

## H-028 — Span citations are frequently unfaithful, and that is the finding
- **Date written:** 2026-09-25, before EXP-0040 ran
- **Source:** Claude.
- **Hypothesis:** `span_support` — the share of quoted spans that actually appear
  verbatim in the document they are attributed to — comes in **below 0.80**. Reasoning:
  the model is being asked to copy character-for-character from a 1,700-word context
  while composing a numbered answer, and every prior parser in this project found models
  reformatting what they were told to reproduce exactly (MIS-016, DEC-045, MIS-035).
  Document-level citation precision meanwhile stays within its MDD of 0.080, because
  naming the right article is an easier task than quoting it.
- **Why the number matters either way:** span-level citation is only worth its cost if
  the span can be trusted. A high support rate makes citations checkable for free; a low
  one means span citations look more rigorous while being less verifiable than a bare
  document id, which is the worse outcome and the more useful thing to know.
- **Tested by:** `span_support` on `dev` (EXP-0040) and citation precision/recall
  against EXP-0006.
- **Resolution:** **first half right, second half wrong, and the first half is the
  finding.**
  `span_support` came in at **0.7964** on dev — below the 0.80 I named, and **0.7429** on
  `unanswerable`. Roughly **one quoted span in five is not in the document it is
  attributed to**, at 4.87 spans per answer. My reasoning held exactly: every prior
  parser in this project found models reformatting what they were told to reproduce
  verbatim, and this is the fourth instance.
  The second half was **wrong**. I predicted document-level citation precision would
  stay inside its MDD of 0.080 because "naming the right article is an easier task than
  quoting it". It fell **0.1102**, well outside. Asking for quotes did not leave document
  selection alone; it degraded it, along with step coverage (0.193 → 0.019, the lowest in
  the project). I underestimated how much a citation *format* reshapes the entire answer
  rather than just its citations.
  I also wrote that a low support rate "means span citations look more rigorous while
  being less verifiable than a bare document id, which is the worse outcome and the more
  useful thing to know." That is what happened. `run_20260925_210039_c048`.

## H-029 — The self-check rejects too few answers to matter, at 4.6 s each
- **Date written:** 2026-09-25, before EXP-0041 ran
- **Source:** Claude, with a rate measured on a 10-answer probe.
- **Hypothesis:** the false-answer rate on `unanswerable` falls by **less than 0.10**,
  and the check's rejection rate on `dev` is **under 0.20**. Reasoning: on the probe it
  rejected **1 of 6** answers it judged, and — the observation that drives this — one of
  the `unanswerable` questions it was shown had been *answered* by the generator and the
  checker called it **supported**. A model asked whether its own family's output is
  grounded in a context that was retrieved to look relevant is being asked a question it
  is poorly placed to answer.
- **What it costs regardless of what it fixes:** **4.6 s per answered question**
  (measured) and ~$0.0055 per 100 dev questions. P2-14 requires those next to the
  quality numbers, which is why they are written down before the run.
- **The part I expect to be wrong:** the rejection rate. Six judged answers is a very
  thin basis, and the full split may behave nothing like it.
- **Tested by:** false-answer rate on `unanswerable`, `grounding_rejection_rate`,
  false-refusal contribution on `dev`, and `mean_check_ms`.
- **Resolution:** **both numbers correct, the reasoning correct, and one cost I failed
  to price.**
  I predicted the false-answer rate would fall by **less than 0.10** — it fell **0.0444**
  — and the dev rejection rate would be **under 0.20** — it was **0.1200**. The mechanism
  I named held too: a model asked whether its own family's output is grounded in a
  context retrieved to look relevant is poorly placed to answer, and the probe
  observation that drove the hypothesis (an answered `unanswerable` question judged
  SUPPORTED) recurred at scale — the check caught **2 of the 12** false answers the
  control produced.
  What I did not predict is the **false-refusal cost: +0.0913, three times the control's
  entire false-refusal rate.** Of 12 dev answers it rejected, **6 had the gold document
  in context.** I priced this technique's latency (4,600 ms, measured in advance) and its
  money ($0.0055/100q) and never asked what it would cost in *quality* — which turned
  out to be the number that decides it. Being right about the headline while missing the
  deciding cost is its own kind of miss.
  The verdict is cleaner than the hypothesis: it is dominated on **both** axes by
  EXP-0038's free threshold (0.1333 / 0.0299 against 0.2222 / 0.1212).
  `run_20260925_211103_1e43`.

## H-030 — HyDE and the cross-encoder rescue the same questions, so the pairing is sub-additive
- **Date written:** 2026-09-26, before EXP-0042 ran
- **Source:** Claude. P2-16 shape (e), the pairing where interaction is suspected.
- **The arithmetic being tested.** On the 40-question multi-document slice the control
  scores 0.350. HyDE alone reaches **0.450** (+0.100, p = 0.346) and `cohere/rerank-4-fast`
  alone reaches **0.475** (+0.125, p = 0.180). If the two are real and independent,
  combining them lands near **0.575**. If they rescue the same questions, it lands near
  **0.475** — the better of the two, and no more.
- **Hypothesis: near 0.475, i.e. strongly sub-additive.** Multi-doc comes out **at or
  below 0.500**, and overall strict recall@5 stays within ±0.03 of the better single
  technique (0.735).
- **The mechanism, measured rather than assumed.** A reranker cannot exceed the recall of
  the candidate set it is given (DEC-058), so the pairing can only be additive if HyDE
  hands it a *better pool*. It does not: **HyDE's recall@20 is 0.925 against the control's
  0.920**, and at candidate depth the two are indistinguishable. Both techniques are
  therefore re-ordering within the same recoverable set. They also fail the same way at
  the same place — both sharpen rank 1 (@1 0.365 and 0.375 against the control's 0.305)
  and neither moves @20 — which is the signature of two methods finding the same
  documents rather than different ones.
- **What would falsify it:** multi-doc at or above 0.550. That would mean the two are
  picking out different questions, and would be the first evidence in this project that
  any two of its techniques are independent.
- **Tested by:** `rag compare promoted <run> --metric strict_recall@5` per slice, plus a
  question-level intersection of which multi-doc questions each of the three runs rescues.
- **Resolution:** **confirmed, including the mechanism and the magnitude — the first
  hypothesis in this project to get all three right.**
  Multi-doc landed at **0.450**, inside the "at or below 0.500" I named and nowhere near
  the additive 0.575–0.600. Overall strict recall@5 reached **0.7500**, the highest in
  the project, at the edge of the ±0.03 band I gave around HyDE's 0.735 — and at
  p = 0.444, so not a finding.
  The mechanism was measured directly rather than inferred. I predicted the two
  techniques "rescue the same questions"; question by question on the 40 multi-document
  questions, HyDE rescues 7 the control misses, the reranker rescues 7, and **4 of those
  are the same 4**. The union is 10, so even a perfect combination was capped at 0.600.
  What I did **not** predict is the second half of the shortfall: the combination
  captures 8 of those 10 and **loses 6 questions that at least one arm had already
  solved**, some of which the plain control got right. I expected sub-additivity and got
  sub-additivity *plus* interference. Two techniques that each improve a ranking do not
  leave each other's improvements intact, and nothing in my reasoning anticipated that.
  `run_20260925_223023_fbcd`.

## H-031 — The two free techniques compose no better, and HyDE hurts BM25
- **Date written:** 2026-09-26, before EXP-0043 ran
- **Source:** Claude. P2-16 shape (d), the deliberately cheap config.
- **Hypothesis:** overall strict recall@5 lands **below HyDE alone (0.735)** — this is the
  one combination I expect to be actively worse than its better component, not merely
  sub-additive.
- **Reasoning, and it is specific to this pairing.** Hybrid α=0.8 fuses a dense ranking
  with a **BM25** ranking, and HyDE hands both of them a 120-word generated passage
  instead of a 20-word question. BM25 scores on term overlap; a generated help-article
  passage is full of this corpus's most common words ("Wix", "click", "settings",
  "dashboard"), which are exactly the terms BM25's IDF weighting treats as least
  informative — while the handful of rare terms that made the original question findable
  are diluted to 1/6 of the query. The dense half should behave as HyDE did alone; the
  sparse half should get worse, and α=0.8 still gives it 20% of the fused score.
- **The part I expect to be wrong:** the magnitude. 20% weight on a degraded ranking may
  simply not matter, in which case this reproduces HyDE alone and the interesting fact is
  that BM25 contributed nothing either way.
- **Tested by:** overall and per-slice strict recall@5 against EXP-0032 (HyDE alone) and
  EXP-0018 (hybrid alone), not only against promoted.
- **Resolution:** **wrong on the headline, and right on the branch I called less likely.**
  I predicted EXP-0043 would land **below HyDE alone (0.735)** — actively worse, not
  merely sub-additive. It landed **above, at 0.7400**.
  The reasoning was that hybrid gives BM25 20% of the fused score and HyDE hands BM25 a
  120-word generated passage of this corpus's most common terms, diluting the rare terms
  that made the question findable. I also wrote: *"the part I expect to be wrong is the
  magnitude — 20% weight on a degraded ranking may simply not matter, in which case this
  reproduces HyDE alone and the interesting fact is that BM25 contributed nothing either
  way."* That is exactly what happened: 0.740 against HyDE's 0.735 is within the
  run-to-run noise this project has measured repeatedly at 0.005–0.010.
  One thing neither half of the hypothesis covered: this run has the **highest nDCG@10 in
  the project (0.6819)** while sitting third on strict recall@5. It ranks gold documents
  better and gets *all* of them inside five no more often — a distinction worth keeping
  in view whenever nDCG and strict recall disagree. `run_20260925_223430_553c`.

## H-032 — Two generated-text techniques at opposite ends of retrieval overlap almost completely
- **Date written:** 2026-09-26, before EXP-0044 ran
- **Source:** Claude.
- **Hypothesis:** multi-doc lands **within ±0.05 of contextual retrieval alone (0.425)**,
  and overall within ±0.03 of HyDE alone (0.735) — no gain from stacking them.
- **Reasoning.** Contextual retrieval and HyDE are the same idea applied at opposite ends:
  write text with a model, then embed it. Contextual retrieval adds article context to the
  *indexed* chunk; HyDE adds answer-shaped text to the *query*. Both, if they work at all,
  work by closing the same vocabulary gap between how a user asks and how the corpus
  writes — and a gap can only be closed once. EXP-0030 measured that contextual retrieval
  is **perfectly inert on one-chunk articles** (0.780 → 0.780, 4 gained / 4 lost), which
  is 79% of the corpus, so there is little for it to contribute on top of anything.
- **Tested by:** per-slice comparison against EXP-0030 and EXP-0032 individually.
- **Resolution:** **right on overall, wrong on the slice, and wrong in the more
  interesting direction.**
  Overall came in at **0.7250** against HyDE alone's 0.735 — inside the ±0.03 I named.
  Multi-doc came in at **0.375**, a 0.050 miss on the "within ±0.05 of contextual
  retrieval alone (0.425)" boundary, and **below both components**: contextual retrieval
  alone reaches 0.400 and HyDE alone reaches 0.450.
  I predicted the two would overlap and therefore add nothing, on the reasoning that both
  close the same vocabulary gap and a gap can only be closed once. They overlapped —
  **destructively**. Stacking two generated-text techniques on the same slice each
  improves alone produced a result worse than either. My model of the interaction was
  "redundant, therefore neutral"; the measured interaction is "redundant, therefore
  mutually disruptive", which is the same thing EXP-0042 showed at larger scale.
  `run_20260925_223951_153c`.

## H-033 — Stacking three null techniques produces a null, and the frontier has one point on it
- **Date written:** 2026-09-26, before EXP-0045 ran
- **Source:** Claude. P2-16 shape (a) all positives combined, and (b) the same minus the
  most expensive component.
- **Hypothesis:** overall strict recall@5 within **±0.03 of the control's 0.720** — the
  three-way stack is indistinguishable from changing nothing — and **no combination in
  EXP-0042 to EXP-0045 beats the control significantly**, so the cost/quality frontier
  P2-16 asks for collapses to a single point: the control, at $0.0000004 per query.
- **Reasoning:** six axes have produced no significant positive retrieval result, and
  sub-additivity among null techniques cannot manufacture one. The specific risk in a
  three-way stack is compounding: HyDE degrades the BM25 half (H-031), contextual
  retrieval adds 60 words of restatement to every chunk, and both perturb the ranking the
  other is trying to improve.
- **What would make this entry wrong in the interesting direction:** any combination
  reaching p < 0.05 positive. That would make the phase's conclusion "the techniques are
  individually too weak to detect but compose", which is a materially different finding
  from "nothing works here".
- **Tested by:** `rag compare` for all four combinations, plus the frontier table.
- **Resolution:** **confirmed on both halves.**
  Overall strict recall@5 came in at **0.7100** — within the ±0.03 of the control's 0.720
  I named, and on the wrong side of it. And **no combination in EXP-0042 to EXP-0045
  reached significance** (p = 0.444, 0.683, 1.000, 0.885), so the cost/quality frontier
  collapses to a single point exactly as predicted: the control, at $0.0000000 per query.
  The compounding risk I named — "HyDE degrades the BM25 half, contextual retrieval adds
  60 words of restatement to every chunk, and both perturb the ranking the other is
  trying to improve" — shows up as a clean monotone: **0.750 / 0.740 / 0.725 at two
  components, 0.710 at three**, with the multi-document slice returning to **exactly**
  the control's 0.350 after passing through three techniques that each raised it alone.
  The falsifying condition I set — any combination reaching p < 0.05 positive, which
  would have made the phase's conclusion "individually too weak to detect but they
  compose" — did not occur. The conclusion stays "nothing here beats the control".
  `run_20260925_224144_bebc`.

## H-034 — The dev-to-test gap is small, because nothing was ever selected on dev
- **Date written:** 2026-09-26, before EXP-0046–0050 ran and before the test split was opened
- **Source:** Claude. The last hypothesis in Phase 2.
- **Hypothesis:** the dense control's strict recall@5 on `test` lands **within ±0.05 of its
  dev value of 0.720**, and the sparse control's within ±0.05 of 0.410. The dense-over-sparse
  gap — the one real finding of Phase 1 — **survives at more than +0.20**.
- **Reasoning, and it is the interesting part of this entry.** **58 runs were executed
  against the same 200 dev questions**, which is exactly the shape of experiment that
  normally produces a large optimism gap. It should not here, because of something the
  ledger makes unusually easy to check: **`promoted.yaml` never moved.** Not once, across
  six axes and 45 Phase 2 runs. Its `identity_hash` is 70610a6119fb9223 today and was on
  the day it was written.
  The usual overfitting mechanism is *selection*: run many configurations, keep the best
  on dev, and the kept one carries the noise that made it look best. That mechanism never
  operated. Every axis returned "no measurable difference" or worse, and the decision rule
  — promote only on a significant positive — fired zero times. **A configuration that was
  never chosen for its dev score cannot have been overfitted to its dev score.**
- **Where the real exposure is, and why the band is ±0.05 rather than tighter.** The
  control is not unselected. Its chunk size (600/100, DEC-038), its embedding model and
  provider (DEC-041), its `top_k` and pooling rule (DEC-040) were all chosen in Phase 1
  by looking at dev numbers. That is roughly **four or five selection decisions**, not
  fifty-eight — but it is not zero, and those choices are where any gap will come from.
- **The part I expect to be wrong:** the sparse control. BM25 is a lexical method with no
  fitted parameters beyond `k1` and `b` at their defaults, so it should transfer almost
  exactly; if anything moves more than the dense arm, my account of where the exposure
  lies is wrong.
- **What would make this project's conclusion worse, not better:** a large gap would mean
  the Phase 1 control itself was a dev artifact, which would undermine every Phase 2
  comparison made against it — all 45 of them are relative to that baseline.
- **Tested by:** EXP-0046–0049 against EXP-0005, EXP-0006, EXP-0004 and EXP-0050, per
  metric, with `rag compare` where the splits permit and plain deltas where they do not
  (dev and test are different questions, so no paired test is possible across them).
- **Resolution:** **right on the dense arm and on the headline finding; wrong on the
  sparse arm, in precisely the way I named as the falsifier — and the error strengthens
  the conclusion.**
  - Dense within ±0.05 of 0.720 → **0.6800, gap −0.0400.** Correct.
  - Dense-over-sparse survives above +0.20 → **+0.3350 on test** against +0.3100 on dev,
    test CI [+0.243, +0.427]. Correct, and it is *larger* out of sample.
  - Sparse within ±0.05 of 0.410 → **0.3450, gap −0.0650.** **Wrong**, outside the band.
  I wrote: *"the part I expect to be wrong is the sparse control. BM25 is a lexical
  method with no fitted parameters beyond `k1` and `b` at their defaults, so it should
  transfer almost exactly; if anything moves more than the dense arm, my account of where
  the exposure lies is wrong."* BM25 moved **more**. So the account was wrong: I located
  the exposure in the four or five Phase 1 selection decisions, and the arm carrying
  **zero** selection decisions moved furthest.
  The gap is the two splits differing in difficulty, not the configuration fitting the
  dev questions. And that makes the result *stronger* than my reasoning predicted:
  overfitting's signature is the selected arm degrading more than the unselected one, and
  we observed the reverse. Every gap, on every headline metric, both slices and both
  tiers, sits inside the sampling noise of two 200-question samples; `strict recall@20`,
  Tier 2 `gold_in_context` and Tier 2 refusal rate came back numerically identical.
  `run_20260926_010435_6495` and `run_20260926_011237_58f7`.

## H-035 — Doubling the context raises citation recall and costs citation precision
- **Date written:** 2026-09-27, before EXP-0051 ran. Answers OQ-040.
- **Source:** Claude.
- **Hypothesis, against the decision rule OQ-040 already names** (citation precision and
  step coverage each against their MDD, plus tokens and cost per query):
  1. **Citation recall rises by more than its MDD of 0.040** — the control's 0.6100 goes
     above 0.6500. Reasoning: 13 more questions per 100 have their gold document in the
     context at k=10 than at k=5 (0.720 → 0.850), and a document that is not in the
     prompt cannot be cited. This is close to arithmetic rather than a guess.
  2. **Citation precision falls, but stays inside its MDD of 0.080.** Ten documents give
     twice as many chances to cite a wrong one, and precision is the metric this project
     has measured as noisiest — the generator, not the judge, is the loose instrument
     there.
  3. **Step coverage does not move beyond its MDD of 0.097.** The reference procedure
     lives in one article; having five more articles alongside it does not add steps.
- **The evidence that makes this checkable rather than a hunch, and it cuts both ways.**
  EXP-0029 moved this exact dial in the opposite direction: compression cut the context
  from 1,712 to 912 words and citation recall fell **0.0883 at p = 0.036**, the only
  significant deterministic result in Axis 6. Less context measurably cost citation
  recall on this system. Doubling it is the same axis the other way — but EXP-0029 also
  saw citation *precision* fall (−0.051) when context shrank, so the relationship is not
  simply monotone in length, and that is the part of this hypothesis I trust least.
- **The part I expect to be wrong:** that any of it reaches significance. Six axes and
  45 runs have produced two significant deterministic results in this project, both
  negative. A prior that says "this one moves a metric" has been wrong far more often
  than it has been right here.
- **What would make the run interesting in the other direction:** citation precision
  falling *beyond* its MDD. That would mean more context actively degrades attribution,
  which is a real cost to weigh against 13 extra questions having their answer present —
  and would make k=10 a trade rather than a free upgrade.
- **Not tested and not claimed:** any retrieval metric. `top_k` cannot change one
  (DEC-040/061), so none is reported.
- **Resolution:** **two of three right, and the one I got wrong is the entire finding.**
  1. Predicted **citation recall rises beyond its 0.040 MDD**, because 13 more questions
     per 100 would have their gold document present and a document not in the prompt
     cannot be cited. **Wrong — it fell 0.0183.** The premise was exactly right: 15
     questions gained their gold and their citation recall rose **+0.2111**. The
     conclusion did not follow because **I counted only the questions that would gain and
     never asked what the same change does to the 67 that were already fine.** They lost
     0.0746 each, and `(15 × 0.2111) + (67 × −0.0746)` reproduces the observed −0.0183 to
     four decimals. I reasoned about a numerator and ignored the denominator it came from.
  2. Predicted citation precision **falls but stays inside its 0.080 MDD**. Half right:
     it fell to **−0.0851, outside** the MDD and significant. I named the mechanism
     ("twice as many chances to cite a wrong one") and then assumed it would be small.
  3. Predicted step coverage stays inside its 0.097 MDD. **Correct**, +0.0104.
  I also wrote that the part I most expected to be wrong was "that any of it reaches
  significance". One metric did — and it was the one I had explicitly placed inside the
  noise band. `run_20260927_235029_2216`.

## Not available hosted — recorded as future work, not as experiments
- **Late chunking** (P2-07): needs token-level embeddings; OpenRouter's
  `/embeddings` returns one pooled vector per input and drops `late_chunking` /
  `return_token_embeddings` silently (probed 2026-09-18, DEC-057). Would need the
  local backend and a different model — a two-axis change. Not run.
- **ColBERT late interaction** (P2-10): multi-vector index, not served by a rerank
  endpoint. Not run.

## H-036 — The candidate ratio does not matter: 20 → 5 and 100 → 5 both sit near the control
- **Date written:** 2026-09-27, before EXP-0052 and EXP-0053 ran. Answers OQ-038.
- **Source:** Claude.
- **The two readings OQ-038 was written to separate.** The dense control has the gold in its
  top 50 almost always (strict recall@50 = 0.985) and `cohere/rerank-4-fast` put it in the
  top five for 0.730 of questions at 50 candidates (EXP-0025, against the control's 0.720,
  p = 0.887). If the reranker is **drowning** in candidates, 20 → 5 beats 50 → 5 and
  100 → 5 is worst. If it is **not good enough at this task**, the ratio does not matter.
- **Hypothesis:** the second. Neither run separates from EXP-0025 or from `promoted` on
  strict recall@5 by the 0.03 OQ-038 names with a significant paired test.
  1. **20 → 5** lands within ±0.03 of 0.730. At 20 candidates the reranker can only
     re-order documents the dense retriever already ranked highly; its ceiling is the
     control's recall@20, 0.920, which is still far above what either side achieves.
  2. **100 → 5** lands within ±0.03 of 0.730 as well. It adds only the documents ranked
     51–100 by the dense retriever, and recall@50 is already 0.985, so at most 3 questions
     in 200 have gold that only 100 candidates can reach.
- **Reasoning, with its weak point named.** Axis 5 produced three rerankers with three
  different profiles at 50 candidates (v3.5 −0.055, 4-fast +0.010, qwen3-8b +0.000) and none
  significant against the control. A mechanism that varies that much by model but never
  moves the headline number looks like a model-quality ceiling, not a candidate-count one.
  **The weak point:** EXP-0024 showed v3.5 *better* at rank 1 and *worse* at ranks 3–5 —
  a signature that could be distractors pulling the gold down, which is exactly what a
  narrower candidate set would remove. If 20 → 5 beats 50 → 5 by the full 0.03, that
  signature was drowning, and I was wrong.
- **What would surprise me most:** 100 → 5 *improving*. Only three questions can gain from
  documents 51–100, so an improvement beyond ~0.015 would have to come from re-ordering
  inside the top 50 changing because of what sits beneath it — which a pointwise
  cross-encoder should not do.
- **Not claimed:** anything about the generator. Tier 1 only; OQ-034 stays open.
- **Resolution (2026-09-28, EXP-0052 `run_20260928_005141_97e5`, EXP-0053
  `run_20260928_012526_ded9`): confirmed on the numbers I committed to; my reasoning
  dismissed a mechanism that turned out to be real.**
  1. 20 → 5 within ±0.03 of 0.730 → **0.750**. Confirmed.
  2. 100 → 5 within ±0.03 of 0.730 → **0.715**. Confirmed.
  3. Neither separates from EXP-0025 or promoted with a significant paired test →
     confirmed (lowest p 0.253 against EXP-0025, 0.403 against promoted).
  - **What I got wrong:** I argued the ratio did not matter because the reranker hits a
    model-quality ceiling, and named drowning as the reading I was rejecting. Question by
    question, drowning is plainly there: in 8 questions the gold's reranked rank worsens
    steadily as candidates are added ("install blog": 5 → 8 → 13). It does not show in the
    aggregate because fewer candidates also lose the 4 questions whose gold sat at dense
    rank 24–33. The null is two real effects cancelling, not an absence of effect. The
    three means fall in order (0.750 / 0.730 / 0.715), which is the drowning direction.
    The 20-vs-100 gap of 0.035 reaches the size OQ-038 names but not significance
    (p = 0.119).
  - **The "surprise" I named did not happen:** 100 docs improved nothing; it lost 3
    questions and gained 0.

## H-037 — All three judges clear the unsupported-flag bar; the supported pass rate is where they differ
- **Date written:** 2026-09-28, before the three P3-04 full runs (DEC-076).
- **Source:** Claude.
- **Hypothesis:**
  1. All three clear **recall ≥ 0.95** on clearly unsupported pairs. Random articles far
     from the question give a judge nothing to hold on to; every probe scored those 0.0.
  2. The **supported pass rate** is the criterion that separates them, and at least one
     candidate falls below 0.85 on it. The strict flag needs *every* claim supported, and
     reference answers are long procedures written by people who knew the product beyond
     the article.
  3. Qwen's failure count is the highest of the three. It was the only probe with a failed
     call (1 of 6); at that rate it would exceed 12 of 240, so I expect it close to or over
     the failure bar.
- **The part I trust least:** (2). Two probe questions put both DeepSeek and Gemini at 1.0
  on supported pairs, which is weak evidence in either direction.
- **Resolution (2026-09-28, EXP-0054 `run_20260928_052254_e257`, EXP-0055
  `run_20260928_054308_6f23`, EXP-0056 `run_20260928_054455_44bb`):**
  1. All three clear recall ≥ 0.95 → **confirmed**: 1.0000 for all three.
  2. The supported pass rate separates them and at least one is below 0.85 → **half right,
     and the half that is wrong matters.** All three are below 0.85, by a wide margin
     (0.35–0.40) — and that criterion does **not** separate them: they agree on 58 of 73
     supported pairs. I expected the judges to differ in leniency on long procedures. They
     did not differ much at all; the labels were the problem. I named (2) as the part I
     trusted least, for the wrong reason: I doubted the judges, not the "known supported"
     set.
  3. Qwen has the most failures → **confirmed**: 22, against 1 and 0.

## H-038 — DeepSeek clears the v2 bar
- **Date written:** 2026-09-28, before the v2 run (DEC-078).
- **Source:** Claude.
- **Hypothesis:** on v2, DeepSeek keeps recall ≥ 0.95 and its supported pass rate rises
  above 0.85, with failures ≤ 12. Reasoning: in v1 it scored 1.0 on the supported pairs
  whose answers were actually in the article (the 22 all three judges passed), and v2's
  supported answers are verbatim article text.
- **The part I trust least:** the strict flag. Ragas splits an answer into statements
  and rewrites them; a rewritten statement can drift from the text (a pronoun resolved
  wrongly, a qualifier dropped) and be judged unsupported even though the source sentence
  was copied. If the pass rate lands between 0.70 and 0.85, that is where I would look.
- **Resolution (2026-09-28, EXP-0057 `run_20260928_143152_c11c`): confirmed.** Recall
  1.0000, supported pass rate 0.9000, failures 0. The part I trusted least — statement
  rewriting drifting from copied text — is not what the 8 false flags show: 5 come from
  the extraction cutting in questions, headings and UI labels, 2 from hypothetical
  examples, 1 is a plain miss. My worry was about the judge's rewriting; the larger effect
  was my own instrument's sentence cuts.

## H-039 — Answers written without their gold article are mostly partially supported, not invented
- **Date written:** 2026-09-28, before the P3-06 run (`rag faithfulness run_20260913_205058_dc03`).
- **Source:** Claude.
- **Buckets, declared now:** per answered question, **fully supported** = faithfulness
  1.0; **partially supported** = 0 < faithfulness < 1; **unsupported** = faithfulness 0.
  Judge failures are counted apart. Groups: gold in context (65 answered),
  answered-without-gold (27: 14 with no gold article in context, 13 multi-doc with only
  part of their gold).
- **Hypothesis:**
  1. In the answered-without-gold group, **partially supported is the largest bucket.** The
     retriever returns near-neighbour articles (F9, F12, F16), and a generator told to cite
     them will write some claims they support and some they do not.
  2. The gold-in-context group has a **higher share fully supported** than the
     answered-without-gold group.
  3. Of the 14 answers with no gold article at all, **fewer than half are fully supported.**
- **The part I trust least:** (2) could fail in a direction that matters. If near-neighbour
  articles are complete enough, the without-gold answers may be as grounded as the
  with-gold ones — in which case "answered without gold" is not a grounding problem at all,
  only a labelling one (OQ-047).
- **Resolution (2026-09-28, EXP-0058 `run_20260928_175207_f723`):**
  1. Partially supported is the largest bucket without gold → **confirmed**: 21 of 27.
  2. Gold in context has a higher fully-supported share → **right direction, not a
     finding**: 0.385 vs 0.222, difference CI [−0.034, +0.359].
  3. Fewer than half of the 14 no-gold answers fully supported → **confirmed**: 4 of 14.
  - **The part I trusted least came true.** Without gold, answers were about as grounded
    as with it: mean faithfulness 0.854 vs 0.866, CI [−0.045, +0.069]. "Answered without
    gold" is not measurably a grounding problem on this sample — the near-neighbour
    articles carry most of what the answers say. And "partially supported" turned out to
    mean mostly style, not invention: 3 of 30 unsupported claims read were factual errors.

## H-040 — On the golden slice, the gate can catch a faithfulness drop of about 0.03 or more, and the judge is the smaller part of the noise
- **Date written:** 2026-09-28, before the P3-07 noise runs (DEC-082).
- **Source:** Claude.
- **Hypothesis:**
  1. **Mean faithfulness MDD** at golden size (≈ 85 judged answers) lands between 0.02
     and 0.05. P1-11 measured 0.014 for the old judge on 100 answers, and regenerating the
     answers adds the generator's noise on top.
  2. **Unsupported-answer rate MDD** is much larger — above 0.08. It is a yes/no per
     answer and two thirds of answers sit near the line (EXP-0058: 61 of 92 partially
     supported), so one flipped claim flips an answer.
  3. **The re-judges vary less than the fresh runs**: judge-only spread on mean
     faithfulness is under half the full-run spread.
- **The part I trust least:** (3). DeepSeek is a reasoning model at temperature 0, and
  MIS-034 showed a reasoning model's output is not deterministic at temperature 0; its
  claim splitting alone could vary as much as the generator.
