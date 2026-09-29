# Phase 3 — Shippable: Golden Set, Faithfulness Eval, CI Quality Gate

**Handover document for Claude Code.**
Status: ready. Phase 2 is closed (413 tests pass, tree clean; promoted config = plain dense retrieval).
Estimated: 2–3 weeks.
Companion docs: `phase0-user-stories.md` (harness), `phase1-user-stories.md` (baseline),
`phase2-user-stories.md` (experiment program). Story ids referenced as `P0-xx` / `P1-xx` / `P2-xx`.

---

## 1. Context

The original plan for this phase has three deliverables:

1. A **golden evaluation set** of ~50–200 manually verified question/answer pairs. WixQA already
   provides this: its expert-reviewed pairs are the golden set (fact 4), so no labelling is done here.
2. An **offline evaluation script** that measures faithfulness: are the claims in a generated answer
   supported by the retrieved chunks?
3. **CI wiring**: every pull request triggers an eval run, and the build fails when quality drops
   below threshold.

Those three remain the core. Everything else in this document exists to make them honest: a gate
that flaps on noise, or only catches catastrophes, or runs on an unvalidated judge, looks like
discipline but isn't.

### The organizing question

> **When a change makes answers less grounded, does the build fail — and how small a regression
> can the gate actually catch?**

The second half is a deliverable in its own right. Phase 3 publishes the gate's detection floor
instead of implying it catches everything.

### Five facts from Phase 2 that shape this phase

1. **The promoted config is plain dense retrieval.** Hybrid and rerank were not promoted. The gate
   protects that config; Phase 3 does not reopen retrieval axes.
2. **There is an evidence gap in the answers.** On dev, gold reached the generator for 0.67 of
   questions, and the refusal rate was 0.08. So roughly a quarter of questions were *answered*
   without the gold document in context. Whether those answers are grounded in a sibling article or
   unsupported is currently unknown. That group is the main reason the faithfulness eval exists.
3. **The noise floor is wide.** The recall@5 dev→test gap had a 95% CI of [−0.13, +0.05]. An
   absolute threshold ("recall@5 ≥ 0.68") on a set this size will flap. The gate compares against a
   frozen baseline with **paired** tests over the same question ids, not against a fixed number.
4. **The golden set already exists, and no manual labelling is in scope.** WixQA ExpertWritten
   answers were drafted by support experts and triple-reviewed (majority vote); Simulated answers
   went through automatic filtering, 3-expert review and replay. All are grounded in the frozen KB
   snapshot (2024-12-02). Phase 3 uses these labels as-is. One known limitation: WixQA has
   near-duplicate help articles, so document-level gold may be incomplete (a non-gold article can
   support an equally correct answer). Phase 3 does not fix this; it is reported as a limitation.
5. **One Phase 2 number is unexplained.** Tier 2 metrics were identical on dev and test
   (0.67 / 0.08) while recall@5 differed. That must be explained before anything is baselined
   (P3-01).

### What Phase 3 inherits

- Frozen corpus, splits (`dev`, `dev_large`, `test`, unanswerable set), document-level qrels,
  chunk→doc max-pooling.
- Two-tier eval; `runs` + `run_questions` results store; `rag diff`; `rag compare` with paired
  significance testing (P2-01).
- Ragas behind the `Judge` interface: pinned, temperature 0, different model family from the
  generator.
- The MDD table (P1-11); cached, reproducible in-pipeline LLM calls; the determinism test.
- `configs/promoted.yaml` and versioned prompts.
- All model calls (embedding, generation, judge) via OpenRouter. The $2-per-run cost gate: estimate,
  print, halt for approval.
- Documentation discipline: `NARRATIVE.md`, `EXPERIMENTS.md`, `DECISIONS.md`, `MISTAKES.md`,
  `FAILURES.md`, `OPEN_QUESTIONS.md`. **No predictions**: record results only after runs complete.

---

## 2. Non-goals

- **New retrieval techniques or axes.** Phase 2 carry-overs (the k=10 run, the reranker headroom
  diagnostic on the recall@5→recall@20 gap) either finish *before* the baseline freeze (P3-02) or
  go to `OPEN_QUESTIONS.md`. Not after.
- **Using `test` in CI.** `test` stays sealed. CI runs on `dev`-derived data only.
- Scaling, auth, multi-tenancy, Kubernetes, load testing.
- Online A/B testing, production monitoring dashboards, alerting.
- Fine-tuning the judge or the generator.
- Metrics beyond those declared in this document. Phase 3 adds claim-level faithfulness,
  unsupported-answer rate, false-answer rate on unanswerables, and citation integrity. These are
  declared here, up front. Adding more mid-phase invalidates comparisons: stop and flag instead.

---

## 3. Stories

Implementation order is the order below. Part F is the first thing to drop if time runs short;
dropping it is a scope decision recorded in `DECISIONS.md`, not a failure.

---

### Part A — Preflight

### P3-01 — Run provenance audit

> **Status: DONE** (2026-09-27) — DEC-070, `rag audit provenance`
> - [x] run ids, splits, question-id sets, cache hits/misses for retrieval, generation and judge reported
> - [x] no `test` output served from a `dev`-created cache entry (answer path uncached; 0 rows)
> - [x] questions in both splits listed: none (0 of 200 ids, 0 identical texts)
> - [x] per-question agreement reported: 0 shared ids — identical aggregates came from different questions
> - [x] outcome in DECISIONS.md (DEC-070); no leak, so no MIS entry needed

**As the maintainer, I need proof that the Phase 2 closing numbers came from independent runs
before I baseline anything on them.**

Acceptance criteria:
- For the Phase 2 closing dev and test Tier 2 runs, report: run ids, split, question-id sets, and
  cache hits vs misses for retrieval, generation and judge calls.
- Confirm no `test` generation or judge output was served from a cache entry created during a `dev`
  run. List any question ids that appear in both splits.
- Report per-question agreement between the dev and test Tier 2 outputs. If identical aggregates
  come from different per-question outcomes, say so explicitly.
- Outcome recorded in `DECISIONS.md`.
- **If a leak is found:** write a `MISTAKES.md` entry, fix the cache keying, and **stop and flag to
  the human** before re-running anything on `test`.

---

### P3-02 — Freeze the Phase 3 baseline

> **Status: DONE** (2026-09-28) — DEC-071, DEC-072, DEC-080
> - [x] Phase 2 carry-overs resolved: k=10 run (EXP-0051); reranker headroom run as OQ-038 (EXP-0052/0053)
> - [x] repo tagged `phase3-baseline` (v1), then `phase3-baseline-v2` after the judge change (DEC-080)
> - [x] recorded with the tag: promoted.yaml hash, prompt version, model slugs and verification dates (`ci/phase3_baseline.yaml`)
> - [x] startup check fails fast on an unresolvable slug or pinned provider (`rag models verify`, runner)

**As the maintainer, I need one fixed reference point that every later CI run is compared to.**

Acceptance criteria:
- Phase 2 carry-overs are resolved: each is either run and recorded, or moved to
  `OPEN_QUESTIONS.md`. One `DECISIONS.md` entry covers this.
- The repo is tagged `phase3-baseline`.
- Recorded alongside the tag: `promoted.yaml` hash, prompt version, exact model slugs for embedder,
  generator and judge, and the date each slug was verified on OpenRouter.
- A startup check fails fast when any configured slug no longer resolves on OpenRouter.

---

### Part B — Golden set

### P3-03 — Select the golden CI slice from WixQA

> **Status: DONE** (2026-09-28) — DEC-074
> - [x] `golden_v1`: 80 answerable (27 answered-without-gold, 20 multi-doc, 33 single-doc) + 15 unanswerable, from `dev` only
> - [x] scripted and seeded (`rag data golden --check`); zero manual labelling
> - [x] `eval/golden/golden_v1.jsonl` + `DATASHEET.md` (over-sampling stated)
> - [x] baseline strict recall per stratum in EXPERIMENTS.md (0.5250 overall)
> - [x] README known-limitations: incomplete document-level gold

**As an evaluator, I need a fixed, expert-labelled question set for CI, taken from WixQA's
existing verified pairs, with zero manual labelling.**

Context: the "manually verified golden set" from the original plan is WixQA's expert-reviewed data
(fact 4). This story selects a CI-sized slice of it; it does not review, rewrite or relabel
anything.

Selection:
- Drawn from `dev` only (expert-reviewed questions). Never `test`, never `dev_large` (synthetic).
- Size 50–100 answerable questions, plus 10–15 from the unanswerable set. Exact numbers are an open
  question for the human.
- Stratified across: single-doc, multi-doc, and the answered-without-gold group from the Phase 2
  closing run.
- Selection is scripted and seeded. It is not hand-picked by looking at pass/fail outcomes.
- The datasheet states that the slice deliberately over-samples the risk group, so absolute scores
  on it are **not** comparable to `dev` scores. The gate is relative, so this is fine.

Storage and versioning:
- `eval/golden/golden_v1.jsonl` (question ids, question, reference answer, `article_ids`, stratum)
  plus `eval/golden/DATASHEET.md`: source configs, selection script and seed, stratum counts, and a
  short provenance note on how WixQA's labels were verified (expert drafting, triple review,
  majority vote).
- Any change to the slice creates a new version, a `DECISIONS.md` entry, and a baseline recompute
  (P3-11).

Reporting:
- Baseline strict recall on the slice (original qrels), per stratum, in `EXPERIMENTS.md`.
- `README.md` known-limitations section records that doc-level gold may be incomplete because of
  near-duplicate help articles.

---

### P3-04 — Synthetic judge sanity check

> **Status: DONE** (2026-09-28) — DEC-075/076/078/079, EXP-0054..0057
> - [x] separation bar declared before running (DEC-076)
> - [x] production judge run on all pairs; confusion matrix, accuracy, precision/recall of the flag; hard negatives separate
> - [x] v1 pairs failed every judge (the labels, not the judges — OQ-047); rebuilt pairs (v2) passed: recall 1.00, supported pass 0.90
> - [x] one judge-side change allowed and recorded; judged metrics marked `gating` (DEC-079)
> - [x] limitation stated in NARRATIVE and README (literal support only; no human agreement)
> - [x] cost estimated before each run

**As an evaluator, I can't gate a build on a judge I haven't checked, and I have no time budget
for human labelling, so the check is built from WixQA's own labels.**

Construction (fully automated, seeded):
- **Known-supported pairs:** each golden-slice reference answer paired with the full text of its
  gold `article_ids`. Expert answers are grounded in those articles, so the correct verdict is
  `supported`.
- **Known-unsupported pairs:** the same reference answers paired with the same number of randomly
  sampled articles that share no `article_ids` with the gold set and come from a different product
  area where that metadata exists. The correct verdict is `unsupported`.
- Optional **hard negatives:** the reference answer paired with the top-ranked *non-gold*
  retrieved articles. These are reported separately and never used for the pass/fail bar, because
  near-duplicate articles mean some of them may legitimately support the answer.

Acceptance criteria:
- **Before running**, declare in `DECISIONS.md` the minimum separation required for the judge to
  gate CI (e.g. accuracy on the known-supported vs known-unsupported split).
- Run the production judge (same slug, prompt version and settings as P3-05) on all pairs.
- Report: confusion matrix, accuracy, and precision and recall of the judge's `unsupported` flag;
  hard-negative results reported separately.
- `NARRATIVE.md` and `README.md` state the limitation plainly: this test proves the judge isn't
  broken on clear cases. It does not prove precision on borderline answers, and no human agreement
  was measured.
- **If separation is below the declared bar:** judged faithfulness becomes **report-only** in CI
  (P3-09). One judge change (prompt or model) is allowed, followed by one re-measurement. The
  outcome is recorded either way.
- Cost estimate before the run; the $2 gate applies.

---

### Part C — Offline faithfulness evaluation

### P3-05 — Faithfulness eval script

> **Status: DONE** (2026-09-28) — DEC-081, DEC-087
> - [x] `rag faithfulness <run_id>`: per-claim verdicts with a chunk pointer (heuristic, labelled)
> - [x] declared metrics: mean faithfulness, unsupported-answer, refusal, false-answer, citation integrity (+ citation validity, DEC-087)
> - [x] broken down by stratum
> - [x] JSON in the runs store + markdown report of the 10 lowest answers
> - [x] judge cache keyed as specified; an unchanged answer is never re-judged
> - [x] cost estimate before any call; $2 gate

**As an evaluator, I need to know, per answer, which claims are supported by the retrieved chunks
and which aren't.**

`rag faithfulness <run_id>`:
- Per answer: extracted claims, each labelled supported/unsupported with the supporting chunk id.
  Faithfulness = supported claims / total claims (Ragas faithfulness via `Judge`).
- Declared metrics:
  - **mean faithfulness**
  - **unsupported-answer rate**: an answer with ≥1 unsupported claim counts as unsupported (strict
    definition, declared here, not tuned later)
  - **refusal rate** on answerable questions
  - **false-answer rate**: unanswerable questions that got an answer instead of a refusal
  - **citation integrity** (deterministic): every cited chunk id exists in the retrieved set
- All metrics broken down by stratum: gold-in-context vs gold-not-in-context, single vs multi-doc,
  unanswerable.
- Outputs: JSON into the runs store, plus a markdown report listing the 10 lowest-faithfulness
  answers with claim, cited chunk and verdict.
- Judge calls are cached, keyed on `(judge_slug, judge_prompt_version, question, context_hash,
  answer_hash)`. An unchanged answer is never re-judged.
- Cost estimate is printed before any calls; the $2 gate applies.

---

### P3-06 — Resolve the answered-without-gold question

> **Status: DONE** (2026-09-28) — EXP-0058
> - [x] P3-05 run on the Phase 2 promoted dev run
> - [x] answered-without-gold: fully 6 / partially 21 / unsupported 0 (vs gold-in-context 25 / 40 / 0)
> - [x] numbers in EXPERIMENTS.md; interpretation in NARRATIVE.md
> - [x] FAILURES.md updated (F18–F23)

**As the project owner, I need to know whether the ~quarter of answers produced without the gold
document are grounded or hallucinated.**

Acceptance criteria:
- Run P3-05 on the Phase 2 promoted `dev` run.
- For the answered-without-gold group, report counts: fully supported by the retrieved non-gold
  chunks, partially supported, unsupported. Report the same breakdown for the gold-in-context group
  as the comparison.
- `EXPERIMENTS.md` gets the numbers only. Interpretation goes to `NARRATIVE.md` after results
  exist.
- `FAILURES.md` taxonomy is updated with the unsupported-answer patterns observed.

---

### Part D — CI quality gate

### P3-07 — Measure the gate's detection floor

> **Status: DONE** (2026-09-28), corrected 2026-09-29 — EXP-0059, DEC-083, DEC-091
> - [x] judge variance re-measured on the golden slice (3 fresh runs + 2 re-judges)
> - [x] retrieval floor at α = 0.05 on `dev`
> - [x] `ci/DETECTION_FLOOR.md` published
> - [x] corrected after the first GitHub run: the gate compares two runs, so its thresholds are pairwise (MIS-047)

**As the maintainer, I need to know the smallest regression the gate can catch before I set gate
rules.**

Acceptance criteria:
- Judged metrics: re-measure judge variance on the golden slice (three runs with the judge cache
  bypassed, same method as P1-11) and compute the MDD per judged metric *at golden-slice size*.
  The P1-11 table was computed on a different set size and is not reused.
- Retrieval metrics on `dev`: report the minimum drop in recall@5 detectable by the paired test at
  the declared α.
- Publish `ci/DETECTION_FLOOR.md`, in the form: "This gate catches a drop of ≥X in metric Y.
  Smaller drops pass."
- Cost estimate before the variance runs; the $2 gate applies.

---

### P3-08 — CI eval command

> **Status: DONE** (2026-09-28) — DEC-084, EXP-0060
> - [x] `rag ci-eval --baseline ci/baseline.json`: Tier 1 dev + golden recall, Tier 2 golden generation + P3-05 metrics
> - [x] paired test for retrieval, measured thresholds for judged metrics
> - [x] pass/fail per metric, PR-comment markdown, JSON artifact, changed-question lists
> - [x] non-zero exit on a gated failure (0 pass / 1 fail / 2 error / 3 needs approval)

**As a developer, I need one command that runs the full gate, identically on my machine and in
CI.**

`rag ci-eval --baseline ci/baseline.json`:
- **Tier 1:** retrieval on all of `dev` (deterministic, cheap, query embeddings cached), plus strict
  recall on the golden slice.
- **Tier 2:** generation plus P3-05 metrics on the golden slice, including its unanswerable questions.
- Comparison to baseline uses paired tests on identical question ids: `rag compare` (P2-01) for
  retrieval, P3-07 MDD thresholds for judged metrics.
- Outputs: pass/fail per metric, a markdown summary suitable for a PR comment, a JSON artifact, and
  the `rag diff` list of questions that changed outcome.
- Non-zero exit code on any gated failure.

---

### P3-09 — Gate rules

> **Status: DONE** (2026-09-28), revised 2026-09-29 — DEC-087, DEC-088, DEC-091; `ci/gate.yaml` v3
> - [x] rules declared before the first gated PR
> - [x] retrieval: paired test at α = 0.05; newly failed ids always listed
> - [x] judged metrics fail beyond their threshold, else "within noise"
> - [x] hard fails: citing a real unretrieved article; schema-invalid output (zero tolerance on garbled ids replaced by a measured rate — flagged to Krutik)
> - [x] each judged metric marked gating/report-only
> - [x] improvements never update the baseline automatically

**As the maintainer, I need the pass/fail rules written down before the first gated PR, so I can't
tune them after seeing results.**

Declared in `ci/gate.yaml` and a `DECISIONS.md` entry:
- **Retrieval:** fail when recall@5 on `dev` drops and the paired test is significant at the
  declared α. Newly failed question ids are always listed, pass or fail.
- **Judged metrics** (faithfulness, unsupported-answer rate, false-answer rate): fail when the
  degradation exceeds the P3-07 MDD. Smaller differences pass with a "within noise" note.
- **Deterministic hard fails, zero tolerance:** a citation to a non-retrieved chunk; malformed or
  schema-invalid output.
- Each judged metric is marked `gating` or `report-only` according to P3-04.
- Improvements never update the baseline automatically.

---

### P3-10 — CI workflow

> **Status: DONE** (2026-09-28) — DEC-088, DEC-089
> - [x] unit tests on every PR
> - [x] ci-eval only on pipeline paths; docs-only PRs show "eval skipped: no pipeline change"
> - [x] model-call caches restored between runs; hit rate in the summary
> - [x] cost estimate before any model call; over budget ⇒ NEEDS APPROVAL; `eval-approved` label re-runs
> - [x] key from CI secrets (added by Krutik); forks get NOT VERIFIED
> - [x] PR comment + job summary + artifact
> - [x] `unit-tests` and `ci-eval` required on `main`
> - [x] infra failure (ERROR) distinct from quality failure (FAIL); bounded retries

**As a developer, every PR that could change answer quality runs the gate, and nothing merges to
`main` without passing it.**

Acceptance criteria:
- Unit tests run on every PR.
- `rag ci-eval` runs only when pipeline-affecting paths change: `src/`, `configs/`, `prompts/`,
  `eval/golden/`, dependency lock files. Docs-only PRs show a visible "eval skipped: no pipeline
  change" status.
- The model-call cache is restored between CI runs. An unchanged pipeline means all cache hits and
  a near-zero-cost run. Cache hit rate appears in the summary.
- A cost-estimate step runs before any model call. If the estimate exceeds the declared per-run CI
  budget, the job stops with "needs approval"; a maintainer-applied `eval-approved` label re-runs
  it.
- The OpenRouter key comes from CI secrets. PRs from forks don't get secrets: the eval job reports
  "not verified", which blocks merge.
- The summary is posted as a PR comment and job summary; the JSON artifact is uploaded.
- `ci-eval` is a required status check on `main`.
- **Infra failure is distinct from quality failure.** Transient OpenRouter errors get bounded
  retries with backoff. A provider outage ends the job as `error`, never as a quality `fail`.

---

### P3-11 — Baseline ratchet and drift check

> **Status: DONE** (2026-09-29) — DEC-090, DEC-091, DEC-092, DEC-093, DEC-094; PRs #2, #4
> - [x] `ci/baseline.json` holds run ids, config hashes, metrics, per-question outcomes (+ integrity stamp)
> - [x] changes only through `rag ci-baseline update --reason <DEC-id>`
> - [x] CI rejects a PR changing both the pipeline and the baseline's results (the ratchet)
> - [x] drift job (`drift.yml`, `--no-cache`); a failure opens an issue and never blocks PRs
> - [x] cadence declared: **on demand only** — Krutik declined a weekly schedule (DEC-094)
> - [x] baseline moved into CI: `main` run 36529043366 (EXP-0063), via a baseline-only PR (DEC-093)

**As the maintainer, I need the bar to move only on purpose, and I need to know when an upstream
model changes under me.**

Acceptance criteria:
- `ci/baseline.json` holds: run id, config hash, metrics, per-question outcomes.
- It changes only through `rag ci-baseline update --reason <DEC-id>`, which requires an existing
  `DECISIONS.md` entry.
- CI rejects any PR that changes both pipeline paths and `ci/baseline.json`. Lowering the bar and
  changing the system in one PR is not allowed.
- A scheduled job re-runs `rag ci-eval` on `main` with generation and judge caches bypassed, to
  detect provider-side model drift on OpenRouter. Cadence and budget are declared (open question).
  A drift failure opens an issue; it does not block PRs.

---

### Part E — Prove the gate works

### P3-12 — Regression drill

> **Status: IN PROGRESS** — DEC-095 (gate v4, prerequisites the drills exposed)
> - [x] gate v4 step 1: judge-side threshold matching; jobs in parallel; gold-in-context reported (PR #6)
> - [x] step 2: baseline carries per-question gold-in-context (baseline-only PR, DEC-096)
> - [x] step 3: gold-in-context gating (gate v5)
> - [ ] drills 1–6 run as throwaway PRs; results table in EXPERIMENTS.md
> - [ ] MISTAKES entry + fix for any drill not behaving as specified (drill 4 exempt)

**As the project owner, I need evidence the gate catches real regressions and doesn't fire on
harmless changes.**

Planted-regression branches, never merged. Each has a declared target metric:

| # | Planted change | Must fail on |
|---|----------------|--------------|
| 1 | Retrieval top-k 5 → 1 | recall@5 |
| 2 | Remove grounding/citation instruction from the prompt | faithfulness or citation integrity |
| 3 | Remove the abstention rule | false-answer rate |
| 4 | Retrieval top-k 5 → 4 (near the detection floor) | recorded either way; tests the P3-07 claim |
| 5 | Comment-only change to a file in `src/` (control) | **must pass**, with all cache hits |
| 6 | Pipeline change plus baseline edit in one PR | **must be rejected** by P3-11 |

Acceptance criteria:
- Results table in `EXPERIMENTS.md`: drill, target metric, actual gate outcome, metric deltas, run
  cost, link to the CI run.
- Any drill that doesn't behave as specified gets a `MISTAKES.md` entry and a fix, then re-runs.
  Drill 4 is exempt: its outcome is a finding, not a pass/fail.

---

### Part F — Thin ship (first to drop)

### P3-13 — Answer API and demo page

> **Status: NOT STARTED** — Part F, first to drop

**As a reviewer, I want to ask a question and see the answer next to the exact source paragraph.**

Acceptance criteria:
- FastAPI `POST /ask` returns `{answer, citations: [{article_title, url, chunk_text}], refused,
  meta: {config_hash, latency_ms, cost_usd}}`.
- It loads `promoted.yaml` and the versioned prompts and imports the **same** pipeline code as the
  eval. No forked logic.
- A minimal page (plain HTML or Streamlit) shows question → answer → cited source paragraph. This
  closes the loop on the Phase 1 deliverable.
- Runs locally via Docker Compose.
- Contract test: for 5 golden questions, API output equals `ci-eval` pipeline output.

---

### P3-14 — Request logging and resilience

> **Status: NOT STARTED** — Part F, first to drop

**As an operator, I need per-request cost and latency, and requests that fail cleanly.**

Acceptance criteria:
- Structured JSON log per request: per-stage latency (embed, retrieve, generate), tokens, cost,
  config hash, refused flag. A tracing tool (Langfuse or OpenTelemetry) is optional (open
  question).
- Timeouts and bounded retries with backoff on every OpenRouter call.
- Fallback models are **off by default**. An enabled fallback counts as its own config and must
  pass `rag ci-eval`, because an unevaluated fallback bypasses the gate.

---

### Part G — Close-out

### P3-15 — Phase 3 report and narrative

> **Status: NOT STARTED**

**As the project owner, I need the whole lifecycle story written from recorded numbers.**

Acceptance criteria:
- `EXPERIMENTS.md` includes: golden-slice composition and baseline recall per stratum, the
  synthetic judge sanity-check results, the answered-without-gold breakdown, the detection floor,
  drill results, and CI cost and wall time per run (cached vs uncached).
- `NARRATIVE.md` covers the full arc: harness → baseline → experiments → shippable gate. Every
  number links to a run id.
- `README.md` explains how to run the eval and the gate, states the detection floor, and lists
  known limitations (incomplete doc-level gold; judge validated only on clear-cut synthetic
  cases).
- `DECISIONS.md` and `MISTAKES.md` are up to date.

---

## 4. Definition of done

1. P3-01 audit recorded; any leak fixed and flagged.
2. `phase3-baseline` tag exists with config hash, prompt version and verified model slugs.
3. Golden slice v1 selected from WixQA by script, versioned, with a datasheet; zero manual
   labelling.
4. Synthetic judge sanity check run against a pre-declared bar; each judged metric marked `gating`
   or `report-only`.
5. `rag faithfulness` produces per-claim verdicts and all declared metrics by stratum.
6. The answered-without-gold question has a recorded, numeric answer.
7. `ci/DETECTION_FLOOR.md` published.
8. `ci/gate.yaml` declared before the first gated PR.
9. `rag ci-eval` is a required check on `main`; infra errors are distinct from quality failures.
10. Baseline ratchet enforced; drift job scheduled.
11. Regression drills 1–3, 5 and 6 behave as specified; drill 4 outcome recorded.
12. Part F done, or dropped with a `DECISIONS.md` entry.
13. `NARRATIVE.md` and `README.md` complete; cost gate respected throughout.

---

## 5. Open questions for the human

Flag rather than guess:
- **Golden-slice size:** how many answerable questions (50–100), how many unanswerables, and the
  stratum proportions.
- **Golden slice vs dev overlap:** the slice comes from `dev`, which is also the experiment split.
  Accept the overlap for a learning repo, or hold the slice out of future experiments?
- **Judge separation bar** for gating (declared before the P3-04 run).
- **α** for the retrieval paired test.
- **CI budget** per run, and the cadence and budget of the drift job.
- **CI host:** GitHub Actions assumed.
- **Part F:** local Docker Compose only, or a hosted deploy? Structured logs only, or Langfuse /
  OpenTelemetry?