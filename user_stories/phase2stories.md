# Phase 2 — Experiment Program on WixQA

**Handover document for Claude Code.**
Status: ready once Phase 1 definition-of-done is met. Estimated: 3–5 weeks.
Companion docs: `phase0-user-stories.md` (harness), `phase1-user-stories.md` (baseline).
Story ids referenced as `P0-xx` / `P1-xx`.

---

## 1. Context

Phase 2 is the core of the project. It runs a disciplined experiment program against the Phase 1
control and produces the findings that the whole portfolio narrative rests on.

### The organizing question

Not "which techniques help?" but:

> **What closes the multi-hop gap, and what does it cost?**

Phase 1 is expected to show a substantial gap between single-gold-doc and multi-gold-doc strict
recall, because multi-hop questions require surfacing 2–3 *distinct* documents and adjacent-chunk
collapse works against exactly that. Every axis below is ordered and budgeted by its expected
effect on that question. Axes that don't move it get short, cheap runs and a recorded negative
result.

This ordering is itself a deliverable: it answers "how did you decide what to try?", which is a
harder and more interesting question than "what did you try?".

### What Phase 2 inherits

- Frozen corpus, curated splits, unanswerable set, document-level qrels, chunk→doc max-pooling.
- Two-tier eval; `runs` + `run_questions` results store; `rag diff`.
- Ragas behind the `Judge` interface, pinned, temperature 0, different family from the generator.
- Phase 1 dense control, sparse control, corpus profile, collapse-ratio instrumentation.
- **The MDD table from P1-11** — the per-metric threshold below which a judged difference is
  indistinguishable from judge noise.

---

## 2. Non-goals

- Deployment, serving, API, UI, monitoring. That is Phase 3.
- Fine-tuning embedding models or generators.
- Exhaustive grid search. Combinations are chosen by hypothesis (P2-15), not enumerated.
- Adding new evaluation metrics mid-phase. If a metric is missing, stop and flag; adding one
  retroactively invalidates comparisons.
- Changing the corpus, splits, normalization, or chunk→doc pooling rule. Any of these resets the
  control.

---

## 3. Experiment discipline

These stories govern every axis. Implement them **before** running any axis.

---

### P2-01 — Paired significance testing for retrieval metrics

**As an experimenter, I need to know whether a retrieval difference is real, using the correct
tool for deterministic metrics.**

Context: retrieval metrics are deterministic — same index, same query, same ranking. Running them
three times and averaging tells you nothing. The right tool is a paired test over per-question
outcomes, which `run_questions` already stores.

Acceptance criteria:
- `rag compare <run_a> <run_b> --metric strict_recall@5` produces:
  - the contingency of per-question outcomes (both correct, both wrong, A-only, B-only),
  - the difference in the metric,
  - a **paired bootstrap or permutation test** p-value on that difference,
  - a confidence interval on the difference (not on each run separately).
- Works for any per-question binary or graded metric in `run_questions`.
- Also reports the same test per slice (single-doc, multi-hop, `article_type`).
- Zero LLM calls. Must run in seconds.
- A seed is fixed and recorded so the resampling is reproducible.
- Recorded in `docs/DECISIONS.md`: repeat-and-average is **not** used for deterministic metrics,
  with this rationale.

---

### P2-02 — Judged metrics reported against MDD

**As an experimenter, I must never report a judged improvement that is smaller than my evaluator's
own noise.**

Acceptance criteria:
- Every judged metric written to `docs/EXPERIMENTS.md` carries its MDD from P1-11, e.g.
  `faithfulness 0.74 (baseline 0.71, Δ+0.03, MDD ±0.04 → within judge noise)`.
- The comparison tooling automatically labels a judged delta as **significant** or **within judge
  noise**; this is not left to prose.
- Repeat runs (3×) are used **only** when a judged delta lands within ~1.5× MDD and needs
  resolving — not as a default.
- If the judge model, judge prompt, or Ragas version changes at any point in Phase 2, the P1-11
  variance measurement is **re-run** and a new MDD table recorded with its effective date. Old
  results keep the old MDD.

---

### P2-03 — Determinism control for in-pipeline LLM calls

**As an experimenter, I need reproducible runs even when the pipeline itself calls an LLM.**

Context: Axis 4 (query transformation) and Axis 8 (agentic retrieval) put LLM calls *inside*
retrieval. For those configs, retrieval metrics stop being deterministic, which silently breaks
P2-01's assumption.

Acceptance criteria:
- All in-pipeline LLM calls run at temperature 0, recorded per run.
- A **generation cache** keyed on `(question_id, prompt_id, prompt_version, model_id, input_hash)`
  persists generated queries, decompositions, and hypothetical documents.
- Cache hit rate is recorded on every run. A run with hit rate < 100% on a repeat of an identical
  config is flagged.
- Runs whose pipeline contains LLM calls are marked `pipeline_nondeterministic = true` in the
  `runs` table. P2-01 warns when comparing two such runs without cache backing.
- A test: run an Axis 4 config twice; with a warm cache the retrieval metrics must be identical.

---

### P2-04 — Split usage policy

**As the project, I need a rule about which split decides what, so power and validity are traded
off deliberately.**

Acceptance criteria — encoded in the runner and documented in `docs/DECISIONS.md`:
- **Retrieval-axis decisions** (Axes 1, 2, 5, 6): decide on `dev_large` (6,221 synthetic) for
  statistical power, then **confirm on `dev`**. A decision is only recorded once both agree in
  direction; disagreement is itself a finding and gets written up.
- **Axis 3 (dense vs sparse vs hybrid, alpha sweep) is decided on `dev` ONLY.** Hard rule. Synthetic
  questions were generated from the article they are grounded in, so lexical overlap is inflated
  and BM25 is systematically flattered. Using `dev_large` here would produce a hybrid weight tuned
  to an artefact. The runner **refuses** Axis 3 runs on `dev_large` unless `--allow-leaky-split` is
  passed, and any such run is annotated as leakage-affected in the results store.
- **Judged-metric decisions** (Axes 4, 7, 8): `dev` subsample only, with MDD reporting.
- `test` stays closed until P2-17.

---

### P2-05 — Promoted configuration pointer

**As the project, I need "current best" to be a committed artifact, not something reconstructed
from the results table.**

Acceptance criteria:
- `configs/promoted.yaml` exists, starting as a copy of `configs/baseline_dense.yaml`.
- It advances only when an axis winner is confirmed per P2-04, and each advance appends to
  `docs/DECISIONS.md`: date, axis, the run ids compared, the p-value or MDD verdict.
- Every axis experiment runs as a **diff against `promoted.yaml`**, changing one dimension.
- `rag diff <run> promoted` works at any time.

---

### P2-06 — Experiment budget and cost gate

**As the project, I need spending to be visible and approved before it happens, not discovered
afterwards.**

Acceptance criteria:
- **Cost estimator.** Before any run, the runner estimates its cost from actual token counts
  (corpus tokens to embed, query tokens, judge tokens) and current per-model pricing, and prints
  the estimate with a breakdown of what drives it.
- **Any single experiment estimated above $2 halts and requires explicit human approval.** The
  runner prints the estimate and exits. It does not prompt-and-continue, and it does not proceed
  on a default. Approval is recorded in `docs/DECISIONS.md` with the estimate and the decision.
- Actual cost is recorded on every run row and compared against the estimate; systematic estimate
  drift is flagged.
- Running totals for the phase are printed on every run.
- Axis caps are enforced: the runner warns when an axis reaches 5 recorded experiments.
- Prices change; the pricing table is a config file with a dated `pricing_version`, not hardcoded.

Note: the dominant cost in this project is **full-corpus embedding** (Axis 2, and re-indexing for
any chunking change), not judged evaluation. Budget attention accordingly.

---

## 4. The axes

Each axis story specifies: what to sweep, which split and tier, and what to report.

**Two rules apply to every axis:**

1. **Maximum 4–5 experiments per axis.** This is a learning repository, not an exhaustive study.
   Run the listed configurations once each, record the results, and move on. Do not refine grids,
   add variants, or re-tune an axis after moving past it. If an axis looks interesting enough to
   deserve more, note that in `docs/HYPOTHESES.md` as future work rather than expanding scope.
2. **Cost gate: any single experiment estimated to cost more than $2 must be flagged for approval
   before running.** Print the estimate, state what drives it, and stop. Do not proceed on
   assumption. See P2-06.

There are no kill criteria. Every listed experiment runs; results are recorded whether positive,
negative, or null.

Run order is given in §5, and is **not** the axis numbering.

---

### P2-07 — Axis 1: Chunking

**Sweep:** fixed+overlap (control), sentence-window (retrieve small, expand context),
parent-document / small-to-big, semantic chunking, structure-aware splitting on headings,
late chunking.

**Split/tier:** `dev_large` to decide, `dev` to confirm. Tier 1.

Acceptance criteria:
- **Chunk→document collapse ratio is reported for every chunking config.** Chunking is the primary
  lever on collapse, and collapse is what caps multi-hop strict recall.
- Structure-aware splitting reports the **mid-procedure boundary count** from P1-02 alongside the
  quality metrics, so the writeup can state: fixed chunking split N procedures across boundaries,
  heading-aware reduced it to M, and multi-hop strict recall moved X.
- All metrics reported **per slice**. Expect a flat curve on single-doc questions if P1-02 showed
  many articles fit inside one chunk — that flatness is an expected result to be explained, not a
  bug to be chased.
- The writeup must address an expected confound: sentence-window and parent-document/small-to-big
  partially overlap with the chunk→doc max-pooling already implemented in P0-05. Some of the lift
  these techniques normally provide is already priced into the baseline, so deltas may be smaller
  than published results suggest. Record this reasoning — it is a genuine insight.

**Experiment count:** 5. The fixed+overlap control is already the Phase 1 baseline run, so the five
new experiments are sentence-window, parent-document/small-to-big, semantic, structure-aware, and
late chunking. One configuration each — no parameter refinement within a strategy.

**Cost note:** each chunking variant requires a full re-index. Estimate before running (P2-06).

---

### P2-08 — Axis 2: Embeddings

**All embedding models are accessed through OpenRouter's embeddings endpoint
(`/api/v1/embeddings`). The rule is about where inference runs, not which models are eligible:
execution is hosted for speed, and open-weight models are preferred where OpenRouter serves them.
Nothing runs on local hardware.**

**Sweep — 5 experiments:**

| # | Model | Rationale |
|---|---|---|
| 1 | `openai/text-embedding-3-large` | Hosted reference point; supports output-dimension truncation |
| 2 | `qwen/qwen3-embedding-8b` | Highest-usage embedding model on OpenRouter; open weights |
| 3 | `baai/bge-m3` | Open weights, 1024-dim, 8192-token context — the model closest to what would otherwise have been run locally, executed hosted for speed. Self-hosting remains a real Phase 3 deployment option for it |
| 4 | `google/gemini-embedding-2` | Different provider lineage; flexible output dims (128–3072) |
| 5 | Dimension truncation | Best model from 1–4 that supports it, at one reduced dimension |

**Split/tier:** `dev_large` to decide, `dev` to confirm. Tier 1.

Acceptance criteria:
- **Model slugs are verified against OpenRouter's models page before running** — slugs and
  availability change, and a wrong slug returns 404. Record the exact slug and the date checked.
- **Prefix handling is verified per model, not per family** (extends P1-04). These four differ:
  `text-embedding-3-large` and `bge-m3` need no query/passage prefixes; Qwen3 embedding uses an
  instruction prefix on the query side. A model evaluated with the wrong prefix convention is an
  invalid run — discard it, do not report it. This is the silent-failure mode from
  `docs/MISTAKES.md`.
- **Embedding cache.** Vectors are cached on disk keyed by
  `(model_slug, normalization_version, chunk_hash)`. Re-running an identical config must cost
  nothing. Cache hit rate recorded. Without this, every re-run re-pays for the whole corpus.
- Cost per full index recorded per model, estimated **before** the run (P2-06). Full-corpus
  embedding is the largest single cost in the project; expect the $2 gate to trigger here.
- Index build time, index size, and embedding dimension recorded per model.
- Batch sizes and rate-limit/retry handling documented — embeddings do not stream, and 429s are
  expected at corpus scale.
- **Dimension truncation is framed as quality-vs-dimension, not cost savings.** At 6,221 documents
  the storage and serving savings are negligible. The writeup must state explicitly that the cost
  argument only bites at a scale this project does not operate at. Overclaiming here is a
  credibility risk.

---

### P2-09 — Axis 3: Retrieval method

**Sweep:** dense only, BM25 only, hybrid via Reciprocal Rank Fusion, hybrid via weighted score
fusion, alpha sweep on the hybrid weight.

**Split/tier:** **`dev` ONLY** (see P2-04). Tier 1.

Acceptance criteria:
- Both fusion methods implemented and compared; alpha swept at documented granularity.
- k defined at the **document** level throughout (P1-03); collapse ratio reported per config.
- Results reported per slice, including by `article_type` — `known_issue` and `feature_request`
  articles may behave differently from `article`.
- The writeup notes the corpus character: enterprise KB text is dense with exact product names
  (*Wix Payments*, *Quick Action Bar*, *iCal*, *og:image*), so lexical matching is a strong
  contender here rather than a straw man.
- Chosen alpha is recorded with its confidence interval, not just its point estimate.

**Experiment count:** 5. Dense-only and BM25-only already exist as the Phase 1 controls, so the
five experiments are RRF, and weighted score fusion at four alpha values (e.g. 0.2 / 0.4 / 0.6 /
0.8). Do not refine the alpha grid further — report the curve as measured, including if it is flat.

**Cost note:** cheapest axis in the phase. No re-index, no LLM calls; reuses the winning embedding
index from P2-08.

---

### P2-10 — Axis 5: Reranking

**All rerankers run through OpenRouter's rerank endpoint (`/api/v1/rerank`), which serves both
open-weight and proprietary rerank models.**

**Sweep — 5 experiments:** three rerankers at a fixed 50→5 ratio, plus two retrieve-k → rerank-to-n
ratios on the best of those (20→5 and one wider setting). Suggested three:

| Reranker | Why |
|---|---|
| `qwen/qwen3-reranker-8b` (or 4B) | Open weights, instruction-aware, the open-weight cross-encoder equivalent of what would have run locally |
| `cohere/rerank-v3.5` or Rerank 4 Fast | Strong proprietary baseline; check current pricing — Cohere rerank models were listed at $0 on OpenRouter at launch, which if still true makes this axis nearly free |
| LLM-as-reranker | Via OpenRouter chat completions, not the rerank endpoint — a different mechanism worth contrasting |

ColBERT late interaction is **out of scope**: multi-vector late interaction needs its own index
format and is not served by a rerank endpoint. This is an availability constraint, not a
hosted-vs-local one. Note it in `docs/HYPOTHESES.md` as future work.

**Split/tier:** `dev_large` to decide, `dev` to confirm. Tier 1 (LLM-as-reranker also needs P2-03).

Acceptance criteria:
- k and n defined at the **document** level (P1-03).
- **Collapse ratio re-measured after reranking.** A cross-encoder can re-concentrate results onto a
  single article and undo the document diversity the retriever was configured to produce. If
  post-rerank collapse rises while multi-hop recall falls, that is the finding — report it.
- Latency and cost per query reported per reranker; hosted rerankers report per-query cost
  separately from local ones.
- LLM-as-reranker runs are marked `pipeline_nondeterministic` and cache-backed per P2-03.

**Cost note:** reranking runs per query, not per corpus, and rerank-endpoint pricing is typically
per search rather than per token. On `dev_large` (6,221 queries) the LLM-as-reranker config at 50
candidates each will likely exceed the $2 gate — estimate first, and consider deciding that one on
`dev` with a `dev_large` confirmation only if it wins.

**Note for P2-11:** if no reranker improves multi-hop strict recall at significance, still run the
revisit pass with the best-performing reranker. "Chunking differences persist because reranking
didn't help" is a different finding from "chunking differences collapsed under reranking", and both
are worth recording.

---

### P2-11 — Revisit pass: chunking under the winning reranker

**As the project, I need to test whether one-factor winners actually compose, because assuming
they do is the most common error in this kind of program.**

Context: a strong reranker often erases the differences between chunking strategies. If that is
true here it is a headline finding, and it only exists if the revisit is planned rather than hoped
for.

Acceptance criteria:
- Re-run the **top 3 chunking configurations** from P2-07 (by multi-hop strict recall) with the
  winning reranker from P2-10 enabled. 3 experiments, not a full re-sweep.
- Produce a side-by-side table: chunking deltas without reranker vs. with reranker, per slice.
- State explicitly whether the Phase 2 winners composed, partially composed, or cancelled.
- If chunking differences collapse under reranking, `promoted.yaml` reverts to the **simplest**
  chunking strategy that is statistically indistinguishable from the best — simplicity wins ties,
  and the reasoning is recorded.

---

### P2-12 — Axis 4: Query transformation

**Sweep:** query decomposition for multi-hop (**run first**), HyDE, multi-query expansion,
step-back prompting.

**Split/tier:** `dev` and `dev_large` for retrieval effects; Tier 1 primarily. All configs require
P2-03 caching.

Acceptance criteria:
- **Decomposition is run first** — it is the technique aimed most directly at the organizing
  question. Do not run it fourth.
- For decomposition, report the number of sub-queries generated per question and the distinct-
  document yield per sub-query.
- HyDE and step-back are expected to help single-doc recall more than multi-hop; report per slice
  and note if single-doc is already near ceiling, which would make those axes uninformative here.
- Added latency and LLM cost per query recorded for every config.
- Cache hit rate recorded (P2-03).

**Experiment count:** 4 — decomposition, HyDE, multi-query expansion, step-back. One configuration
each, no prompt tuning within a technique.

**Cost note:** every config adds an LLM call per query. On `dev_large` this will exceed the $2 gate;
decide this axis on `dev` and confirm only the winner more broadly, if at all. The P2-03 cache makes
repeat runs free.

---

### P2-13 — Axis 6: Context assembly

**Sweep:** top-k sweep, MMR for diversity, contextual compression, lost-in-the-middle reordering,
Anthropic-style contextual retrieval (prefixing each chunk with LLM-generated document context
before embedding).

**Split/tier:** retrieval effects on `dev_large` + `dev`, Tier 1; assembly effects on answer quality
need Tier 2 on the `dev` subsample.

Acceptance criteria:
- **MMR is prioritised within this axis** — diversity directly serves multi-document coverage, which
  is the organizing question. Sweep the diversity parameter and report collapse ratio alongside.
- **Contextual retrieval is budgeted explicitly before running.** It requires one LLM call per chunk
  across the whole corpus. Use prompt caching, estimate the cost first, print it, and record the
  **one-time index cost** as part of the result. The writeup should state that this is bounded and
  affordable at ~6k documents and would not be at 6M — that scale honesty is part of the finding.
- Lost-in-the-middle reordering is evaluated on generation metrics (Tier 2), since it cannot change
  retrieval metrics by construction. Do not report retrieval deltas for it.
- Contextual compression reports tokens-per-query reduction alongside quality.

**Experiment count:** 5 — top-k sweep (one run covering the k values), MMR, contextual compression,
lost-in-the-middle reordering, contextual retrieval. One configuration each.

**Cost note:** contextual retrieval is the single most expensive experiment in the phase — one LLM
call per chunk across the whole corpus. It will trigger the $2 gate. Estimate it, present the
number, and get approval before running. If approval is withheld, record that in
`docs/DECISIONS.md` as a scope decision with the estimate attached — an honest "we priced this and
chose not to spend it" is a legitimate entry.

---

### P2-14 — Axis 7: Generation and grounding

**Sweep:** citation enforcement, span-level vs chunk-level citations, abstention thresholds,
groundedness self-check pass before returning.

**Split/tier:** Tier 2 on `dev` subsample, **plus the full `unanswerable` set** every run.

Acceptance criteria:
- The hard target is the **false-answer rate on `unanswerable` from Phase 1 run 3**. Every config
  in this axis is measured against that number.
- The deliverable artifact is a **threshold sweep plotting false-answer rate on `unanswerable`
  against false-refusal rate on `dev`.** The trade-off curve is the finding; a single operating
  point is not.
- An operating point is chosen from that curve and recorded in `docs/DECISIONS.md` with the
  reasoning (which error is worse for an enterprise support assistant, and why).
- Citation precision/recall (label-based, free) reported for span-level vs chunk-level.
- Groundedness self-check reports its added latency and cost per query, and its own
  false-refusal contribution.
- All judged deltas reported against MDD (P2-02).

**Experiment count:** 4 — citation enforcement, span-level vs chunk-level citations, abstention
threshold sweep (one run covering the thresholds), groundedness self-check.

**Cost note:** Tier 2 on the dev subsample plus the ~50-question unanswerable set. Judge cost per
run is modest; the self-check config adds a generation call per query.

---

### P2-15 — Axis 8: Agentic retrieval

**Sweep — 3 experiments:** an iterative loop that critiques its own retrieval and re-queries, at
three iteration caps (e.g. max 1, 2, 3 extra rounds).

**Split/tier:** `dev` only. Tier 1 for retrieval effect, one Tier 2 run on the best setting.

Acceptance criteria:
- A **hard per-query iteration cap and a hard per-run cost ceiling** are set in config before the
  first run. These are runtime safety limits, not performance judgments — an unbounded agentic loop
  can spend real money fast.
- Cost per query and p95 latency reported alongside every quality number. The claim being tested is
  a ratio, not a numerator.
- Runs are `pipeline_nondeterministic` and cache-backed (P2-03).
- Report the iteration-count distribution and how often extra iterations changed the retrieved
  document set at all — that second number is often the more interesting one.
- Cost-gated per P2-06 like every other axis.

**Explicitly acceptable outcome:** iterative retrieval cost 4× and gained less than MDD. A recorded
negative result here is more valuable — and rarer in portfolios — than a marginal positive one.
This axis runs last and is the first thing to drop if budget or time runs short; dropping it is
recorded as a scope decision, not a failure.

---

### P2-16 — Combination set

**As the project, I need to test that the per-axis winners work together, without running a grid.**

Acceptance criteria:
- **3–5 combination configs, each chosen by a stated hypothesis** written into
  `docs/HYPOTHESES.md` before the run. No enumeration.
- Suggested shape: (a) all winners combined, (b) winners minus the most expensive component,
  (c) simplest config within significance of the best, (d) a deliberately cheap config optimised
  for latency/cost, (e) one hypothesis-driven pairing where interaction is suspected.
- Each combination is compared to `promoted.yaml` via P2-01/P2-02, per slice.
- Report explicitly where combined gains were **sub-additive** — this is the interaction story and
  is a primary Phase 2 deliverable.
- A cost/quality frontier plot across all combination configs plus the two Phase 1 controls.

---

### P2-17 — Negative results section

**As the project, I need failures presented as findings, because a monotonic improvement story is
not credible to anyone who has done this work.**

Acceptance criteria:
- `docs/EXPERIMENTS.md` gains a standing **Negative Results** section, populated as the phase runs,
  not written at the end.
- Each entry states: what was tried, the measured delta, the p-value or MDD verdict that justifies
  calling it null, the cost it would have added, and the decision taken.
- Target form: *"Semantic chunking cost 3× at index time and gained 0.4 points strict recall@5,
  below the 1.2-point detectable threshold on this split, so fixed chunking was retained."*
- Every experiment that produced a null or negative result gets an entry — including any axis that
  was priced, gated at $2, and deliberately not run, with its estimate attached.

---

### P2-18 — Open the test split, once

**As the project, I need an honest final number and an honest measure of how much I overfitted.**

Acceptance criteria:
- `test` is opened **exactly once**, at the end of Phase 2, with `--open-test`, logged per P0-12.
- Run: the Phase 1 dense control, the Phase 1 sparse control, and the final promoted config —
  Tier 1 and Tier 2.
- Report the **dev-to-test gap** for every headline metric. This is a result in its own right and
  goes in `docs/EXPERIMENTS.md` under its own heading.
- The writeup states plainly how many experiments were run against 200 dev questions and what that
  implies about the gap.
- If the gap is large, that is reported, not hidden or re-tuned away. Re-tuning after opening
  `test` is forbidden; if it happens, it must be disclosed and the split treated as burned.

---

## 5. Run order

Not the axis numbering. Cheap and deterministic first.

1. Discipline stories P2-01 → P2-06. Nothing else starts until these work.
2. **Cheap deterministic axes, Tier 1:** P2-08 (embeddings) → P2-09 (retrieval/hybrid) →
   P2-07 (chunking) → P2-10 (reranking).
3. **Revisit pass:** P2-11 — chunking under the winning reranker.
4. **Multi-hop targeted:** P2-12 (decomposition first) → P2-13 (MMR, then contextual retrieval).
5. **Grounding, Tier 2:** P2-14 against the Phase 1 unanswerable baseline.
6. **Last and droppable:** P2-15 (agentic), if budget and time allow.
7. **Combinations:** P2-16.
8. **Test:** P2-18, once.

`docs/HYPOTHESES.md` gets seeded entries before each axis and resolved after.

---

## 6. Phase 2 definition of done

1. Paired significance testing works and is used for every retrieval comparison.
2. Every judged delta in the experiments doc carries an MDD verdict.
3. In-pipeline LLM calls are cached and reproducible; determinism test passes.
4. Split usage policy enforced in code, including the Axis 3 refusal on `dev_large`.
5. `configs/promoted.yaml` reflects the final configuration, with a decision trail for each advance.
6. Every axis has either a confirmed winner or a Negative Results entry.
7. No axis exceeded 5 experiments.
8. Every run above $2 was flagged and approved before execution; no unapproved spend occurred.
9. The chunking revisit pass (P2-11) has been run and its composition verdict recorded.
10. The abstention trade-off curve exists and an operating point is chosen and justified.
11. 3–5 hypothesis-driven combinations run; sub-additivity reported; cost/quality frontier plotted.
12. `test` opened once; dev-to-test gap reported.
13. Total actual spend recorded and compared against estimates.

---

## 7. Open questions for the human

Flag rather than guess:
- Total phase spending ceiling, so the $2 per-experiment gate sits inside a known envelope.
- Which hosted rerankers are in budget (Cohere Rerank, others).
- Whether the abstention operating point should favour refusing too often or answering too often,
  for an enterprise support assistant.
- Confirmation of the four OpenRouter embedding slugs at implementation time — slugs and
  availability change, so verify against the models page rather than trusting this document.