# CLAUDE.md — Operating Instructions

This file governs how you work in this repository. It is not background reading.
Read it at the start of every session and follow it literally.

---

## 1. What this project is

A production-grade Retrieval-Augmented Generation system over a fixed document
corpus, built as an **experiment platform**, not a demo.

The system exists to answer one question repeatedly: *does technique X measurably
beat technique Y on this corpus, and at what cost?*

Three outputs matter, in this order:

1. **Measured findings** — what actually moved the metrics, backed by reproducible runs.
2. **A production-quality system** — deployed, observed, tested, gated in CI.
3. **A written narrative** — the story of the investigation, usable in hiring conversations.

The narrative is a *byproduct of evidence*, never a story we decide on first and
then justify. If the data is boring, the narrative is boring. That is acceptable.

Data cleaning and document conditioning are explicitly **out of scope**. The corpus
is parsed once, frozen, and treated as a fixed input. Do not propose parsing
improvements as experiments unless asked.

This repo serves as RAG technique learning tool for author.  It will be used to showcase my RAG and AI skills and effort i put to learn RAG techniques.

---

## 2. The documentation contract

Seven files. They are deliverables, not notes. Treat a change to code as incomplete
until the corresponding documentation is written.

| File | Purpose | Write cadence |
|---|---|---|
| `docs/NARRATIVE.md` | The human-readable story of the investigation | End of each phase, or after a batch of related experiments |
| `docs/EXPERIMENTS.md` | Index of every experiment run, with headline metrics | Immediately after every run completes |
| `docs/experiments/EXP-NNNN.md` | Full detail for one experiment | Same time as the index row |
| `docs/DECISIONS.md` | Every consequential decision, by me or by you | At the moment the decision is made |
| `docs/MISTAKES.md` | Every error made, and the rule that prevents recurrence | Immediately on discovery |
| `docs/FAILURES.md` | Taxonomy of queries the system answers badly | After each evaluation run review |
| `docs/OPEN_QUESTIONS.md` | Unanswered questions and untested hypotheses | Whenever one surfaces |

Writing style: not too much technical jargons, easy to understand for someone who is new to RAG and AI. But RAG technique names and popular jargon is ok to use and encouraged. If project and dataset specific terms used, create separate glossary.md to reference them. 

### Source of truth

`results/runs/<RUN_ID>/` holds the machine-written artifacts: `config.yaml`,
`metrics.json`, `predictions.jsonl`, `env.json`, `stdout.log`.

**The markdown files mirror those artifacts. They never originate numbers.**

Every numeric claim in any markdown file must be traceable to a `RUN_ID` whose
directory exists on disk. If you cannot point to the artifact, you may not write
the number.

### Append-only

These files are append-only journals. Never delete or rewrite a past entry.

- A wrong entry gets a **correction entry** appended, and the original gets a
  `> **CORRECTED by <ID> on <date>**` line added directly beneath it.
- An invalidated experiment gets its status set to `VOID` with a reason and a link
  to the `MIS-NNN` entry that explains why. The row stays. The numbers stay.
  Deleted evidence is worse than wrong evidence.

Reorganising the *structure* of a file (adding sections, fixing the index table) is
fine. Rewriting *history* is not.

---

## 3. The no-prediction rule

**This is the strictest rule in this repository. It overrides helpfulness.**

You do not predict experimental outcomes. You run experiments and record what happened.

### Prohibited, without exception

- Stating or implying an outcome for a configuration that has not been run.
  Banned phrasings include: *should improve*, *will likely*, *I expect*, *this is
  better because*, *typically outperforms*, *this should give us around*,
  *the gain will be modest*.
- Writing a results row, metric, or delta before the run has produced `metrics.json`.
- Estimating, interpolating, or extrapolating a metric that was not measured.
  A number from a 20-question smoke run is not a number for the 150-question set.
- Ranking two techniques on this corpus without runs for both.
- Presenting a claim from a paper, blog post, or your own training as if it were a
  finding from this project.
- Writing narrative that describes a result before that result exists.

### Required instead

When you have an intuition or a reason to try something, express it as a **question
plus a decision rule**, and file it in `docs/OPEN_QUESTIONS.md`:

> **OQ-014** — Does sentence-window retrieval beat fixed-600 chunking on multi-hop
> questions? Decided by: recall@10 on the `multi_hop` slice, ≥3 point difference
> across 3 seeds. Not yet run.

External claims are allowed *only* when explicitly labelled as external and framed
as something to test:

> External claim (Anthropic contextual-retrieval post, Sept 2024): prefixing chunks
> with generated document context reduces retrieval failures. **Untested here.**
> Tracked as OQ-021.

### If I ask you to predict

If I ask "which do you think will win?" or "is X worth trying?", answer:

> Not measured on this corpus. The experiment that would answer it is: `<config diff>`,
> decided by `<metric>` on `<slice>`. Want me to queue it?

You may reason about *cost, latency, and implementation effort* before running —
those are engineering estimates, not quality predictions. Label them as estimates.

### Selection and interpretation

- Never tune on the golden evaluation set. If you tune anything, it is on the
  dev slice, and you say so.
- Never report the best of N runs as the result. Report mean and spread across seeds.
- A difference smaller than the run-to-run spread is **not a finding**. Write
  "no measurable difference," not "a slight improvement."
- Do not compare runs that used different corpus hashes, different eval-set
  versions, or different judge models. If they differ, say the comparison is invalid.

---

## 4. `docs/EXPERIMENTS.md` — format

Top of file: an index table, newest last.

```markdown
| Run ID | Date | Axis | Change vs baseline | recall@10 | nDCG@10 | Faithfulness | Cit. precision | p95 ms | $/query | Status | Detail |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0001 | 2026-09-10 | baseline | fixed-600/100, dense k=5 | 0.61 | 0.54 | 0.72 | 0.81 | 2100 | 0.0041 | VALID | [→](experiments/EXP-0001.md) |
| EXP-0002 | 2026-09-11 | retrieval | + BM25 hybrid (RRF) | 0.74 | 0.66 | 0.79 | 0.83 | 2250 | 0.0043 | VALID | [→](experiments/EXP-0002.md) |
| EXP-0003 | 2026-09-11 | chunking | semantic chunking | — | — | — | — | — | — | VOID (MIS-004) | [→](experiments/EXP-0003.md) |
```

Status is one of `RUNNING`, `VALID`, `VOID`, `SUPERSEDED`.

### Per-experiment file — `docs/experiments/EXP-NNNN.md`

```markdown
# EXP-0002 — Hybrid retrieval via Reciprocal Rank Fusion

- **Status:** VALID
- **Date:** 2026-09-11
- **Run IDs:** run_20260911_142233_a91f (seeds 1, 2, 3)
- **Git SHA:** 4f9c1ab
- **Corpus hash:** sha256:7d2e...
- **Eval set version:** golden-v3 (152 questions)
- **Compared against:** EXP-0001 (baseline)

## Question
Does BM25 + dense fusion improve retrieval over dense-only on this corpus?

## Configuration diff
```yaml
retriever:
-  type: dense
+  type: hybrid
+  fusion: rrf
+  rrf_k: 60
+  bm25_top_k: 50
+  dense_top_k: 50
```

## Results
| Metric | Baseline | This run | Delta | Spread (3 seeds) |
|---|---|---|---|---|
| recall@10 | 0.61 | 0.74 | +0.13 | ±0.02 |
| ...

Per-slice breakdown:
| Slice | Baseline | This run |
|---|---|---|
| factual | ... | ... |
| multi_hop | ... | ... |
| exact_term | ... | ... |
| unanswerable | ... | ... |

## Observations
Factual statements about what the numbers show. No causal claims beyond what was
varied. No speculation about the next experiment's outcome.

## Anomalies
Anything unexpected in logs, latency, or outputs. If none: "None observed."

## Reproduce
```bash
python -m rag.run --config configs/exp_0002.yaml --seeds 1,2,3
```
```

Write "Observations" only after reading actual failing examples, not just aggregate
metrics. Pull at least five queries where behaviour changed and look at them.

---

## 5. `docs/DECISIONS.md` — format

Log every decision that would be expensive or confusing to reverse: corpus choice,
eval-set design, metric definitions, framework and model selection, architecture
boundaries, scope cuts, thresholds, deployment targets.

```markdown
## DEC-007 — Freeze the golden set at v3 before the chunking sweep
- **Date:** 2026-09-11
- **Decided by:** Krutik (proposed by Claude)
- **Status:** Active
- **Context:** Chunking changes alter chunk boundaries, so eval questions written
  against v2 chunk text would no longer align.
- **Options considered:**
  1. Regenerate the eval set per chunking config — rejected, breaks comparability.
  2. Freeze at v3 and treat all chunking runs as one comparable family — chosen.
  3. Delay the sweep until v4 is ready — rejected, blocks two weeks of work.
- **Decision:** Freeze golden-v3. All Axis-1 runs use it. Any later version starts
  a new comparison family and cannot be compared across the boundary.
- **Evidence:** No measured data; judgment call on experimental validity.
- **Consequences:** Runs before EXP-0009 are not comparable to runs after a future v4.
- **Revisit if:** eval set proves too small for statistical separation on any slice.
```

Rules:

- **Decided by** must be honest: `Krutik`, `Claude`, or `Joint`. When you make a
  call on your own because I was not in the loop, mark it `Claude` and say so in
  chat. Do not launder your own choices as mine.
- If a decision has no measured basis, write `**Evidence:** No measured data;
  judgment call.` Never manufacture a rationale.
- Every decision needs a **Revisit if** trigger. Decisions without exit conditions
  become dogma.
- When a decision is reversed, append a new entry and set the old one's status to
  `Superseded by DEC-NNN`.

---

## 6. `docs/MISTAKES.md` — format

Everything that went wrong: bugs, invalid comparisons, misread metrics, wasted
runs, wrong assumptions, config errors, my mistakes and yours.

**Read this file before starting any new experiment.** It is a preflight checklist,
not an archive.

```markdown
## MIS-004 — Compared runs across different eval-set versions
- **Date:** 2026-09-11
- **Severity:** High — invalidated EXP-0003
- **What happened:** EXP-0003 ran against golden-v3 while its stated baseline
  EXP-0001 used golden-v2. The reported +0.04 faithfulness delta was meaningless.
- **How it was caught:** Question count differed (152 vs 141) in the run manifest.
- **Root cause:** The runner did not assert eval-set version equality against the
  declared baseline.
- **Impact:** EXP-0003 marked VOID. Two hours of compute wasted.
- **Fix applied:** Runner now records `eval_set_version` and refuses to emit a
  delta table when it differs from the baseline run.
- **Prevention rule:** Before writing any comparison, verify corpus hash, eval-set
  version, and judge model match across both runs.
- **Added to preflight:** yes
```

Maintain a short **Preflight checklist** section at the top of the file, derived
from the prevention rules. Run through it before each experiment and say in chat
that you did.

Do not soften entries. "We could have been clearer" is not a mistake entry.
Write what broke.

---

## 7. `docs/NARRATIVE.md` — format

The document a hiring manager reads. Written from `EXPERIMENTS.md` and nothing else.

Structure:

1. **The problem and the corpus** — what domain, why, what makes it hard.
2. **How this was measured** — eval-set construction, slices, metrics, why these
   metrics, how noise was handled. This section is the credibility anchor; write
   it carefully.
3. **The baseline** — what the naive system scored.
4. **What was tried, axis by axis** — for each: the question, what was run, what
   the numbers were, what was concluded. Include the things that did nothing.
5. **What actually moved the needle** — a ranked table of techniques by measured
   delta, against cost and latency.
6. **What did not work, and what that suggests** — the most interesting section.
   Negative results with honest interpretation.
7. **Where the system still fails** — from `FAILURES.md`.
8. **Production engineering** — deployment, observability, CI eval gate, caching,
   degradation, injection surface.
9. **Lessons that transfer** — what I would do differently on a real system, and why.
10. **What remains untested** — from `OPEN_QUESTIONS.md`. Naming your gaps is a
    strength signal, not a weakness.

Style rules:

- Past tense, first person, specific. "Hybrid retrieval improved recall@10 from
  0.61 to 0.74 (EXP-0002)." Not "we leveraged hybrid retrieval for improved results."
- Every claim carries an `EXP-NNNN` reference.
- No marketing language. No "revolutionary", "cutting-edge", "seamless", "robust".
- Include at least one section describing something that failed and what it cost.
- Do not write section 5 or 6 until the corresponding experiments are `VALID`.
  Leave the heading with `_Pending: EXP-0011 through EXP-0016._` underneath.

---

## 8. `docs/FAILURES.md` and `docs/OPEN_QUESTIONS.md`

**FAILURES.md** — after each evaluation run, sample the worst-scoring queries and
categorise them. Track: query, expected answer, what the system returned, which
stage failed (retrieval / reranking / assembly / generation), category, and whether
any later experiment fixed it. Categories emerge from the data; do not invent a
taxonomy up front.

**OPEN_QUESTIONS.md** — every untested hypothesis, with the decision rule that
would settle it and its current status (`open`, `queued`, `answered by EXP-NNNN`,
`dropped`). This is where intuitions go instead of into predictions.

---

## 9. Working rules

**Session start.** Read `MISTAKES.md` preflight, the last five rows of
`EXPERIMENTS.md`, and the active entries in `DECISIONS.md`. Say in one line what
state the project is in and what you understand the next step to be. Wait for
confirmation before large work.

**Before an experiment.** Confirm the config diff is minimal — one axis at a time
unless the run is explicitly a combination run. State which baseline it compares
against. Run the preflight checklist.

**During.** Do not modify the eval set, the corpus, the judge model, or the metric
definitions mid-batch. If one must change, stop, log a decision, and start a new
comparison family.

**After.** Write the index row and detail file before starting anything else. An
unrecorded run does not exist. If a run crashed or was abandoned, record it as
`VOID` with the reason — silent gaps in the ledger destroy the narrative's
credibility.

**Commits.** One experiment per commit where possible.
`EXP-0002: hybrid RRF retrieval — recall@10 0.61→0.74`.
Docs update lands in the same commit as the run it describes.

**Scope.** Do not refactor beyond the task. Do not add pipeline stages, swap
libraries, or restructure configs without an entry in `DECISIONS.md`.

**Honesty.** If something is broken, uncertain, slower than expected, or if you
are unsure a comparison is valid, say so plainly in chat and log it. Never smooth
over a problem to keep momentum. If I propose something that would invalidate an
experiment or contaminate the eval set, tell me directly and do not implement it
until we have resolved it.

**Ask before:** changing metric definitions, regenerating the eval set, switching
embedding or judge models, deleting run artifacts, or changing anything that
breaks comparability with prior runs.
