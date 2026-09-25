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
- **Resolution:** _pending EXP-0029._

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
- **Resolution:** _pending EXP-0030._

## Not available hosted — recorded as future work, not as experiments
- **Late chunking** (P2-07): needs token-level embeddings; OpenRouter's
  `/embeddings` returns one pooled vector per input and drops `late_chunking` /
  `return_token_embeddings` silently (probed 2026-09-18, DEC-057). Would need the
  local backend and a different model — a two-axis change. Not run.
- **ColBERT late interaction** (P2-10): multi-vector index, not served by a rerank
  endpoint. Not run.
