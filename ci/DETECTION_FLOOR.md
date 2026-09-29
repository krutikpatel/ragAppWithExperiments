# Detection floor of the Phase 3 quality gate (P3-07)

> **CORRECTED by DEC-091 on 2026-09-29** — the judged-metric floors below measure how far
> ONE run strays. The gate compares TWO runs, and on its first GitHub run it false-alarmed
> on an unchanged pipeline (EXP-0061, MIS-047). **What the gate actually uses is in the
> "Correction" section at the end.** The retrieval table is unaffected.

What the gate can and cannot see. **A drop smaller than the floor passes — not because it
is harmless, but because the gate cannot tell it from run-to-run noise.** Measured
2026-09-28 (DEC-083, EXP-0059). Every number traces to a run id in the results store.

## Judged and generated metrics — golden slice `golden_v1` (95 questions)

Measured with P1-11's method: the unchanged v2 control run **three times from scratch** —
fresh answers and fresh judging each time (`rag faithfulness --no-cache`) — and
**MDD = max(range, 2 × stdev) over the three, rounded up to 0.001**. Judge
`deepseek/deepseek-v4.1-flash` @DeepInfra, no fallbacks; generator `openai/gpt-5-nano`;
prompt `baseline_answer@v1`.

| Metric | This gate catches a change of at least | Smaller changes pass | of which the judge alone | Values in the three runs |
|---|---|---|---|---|
| **mean faithfulness** | **0.026** (drop) | < 0.026 | 0.023 | 0.8506 / 0.8621 / 0.8369 |
| **unsupported-answer rate** | **0.064** (rise) | < 0.064 | 0.057 | 0.6076 / 0.6447 / 0.6711 |
| **false-answer rate** (15 unanswerable questions) | **0.077** (rise) — i.e. **2 questions** | 1 question | 0.000 | 0.2667 / 0.3333 / 0.3333 |
| refusal rate (80 answerable questions) | 0.073 (rise) — 6 questions | ≤ 5 questions | 0.000 | 0.0500 / 0.1125 / 0.1125 |
| citation integrity | 0.016 (drop) — see warning | | 0.000 | 0.9875 / 0.9737 / 0.9868 |
| **citation validity** (DEC-087) | **0.041** (drop) — about 3 answers | < 0.041 | 0.000 | 0.9625 / 0.9474 / 0.9474 (+ 0.9221, a fourth fresh run) |

In plain words: **"This gate catches a drop of ≥ 0.026 in mean faithfulness. Smaller drops
pass."** Likewise a rise of ≥ 0.064 in the share of answers with an unsupported claim, and
a rise of 2 or more answered unanswerable questions out of 15.

**Where the noise comes from.** Re-judging the *same* answers (two extra `--no-cache`
judgings of run 1) moves mean faithfulness by 0.023 — almost the whole 0.026. The judge,
not the generator, is most of the judged-metric noise. Refusals, false answers and citation
integrity do not move at all under re-judging: their noise is the generator's.

**Per stratum the floors are larger** (fewer questions): mean faithfulness 0.041 on
single-doc (n ≈ 30), 0.028 on multi-doc (n ≈ 18), 0.067 on answered-without-gold (n ≈ 24),
0.092 on the few answered unanswerables (n = 4–5). Full table: `rag/eval/noise_floor.py`,
family `golden-v1-deepseek`.

## Retrieval — strict recall@5, paired test at α = 0.05

The paired test (`rag compare`, exact McNemar) fires on the number of questions a change
**loses** against the number it **gains**. Retrieval is close to deterministic here: two
identical runs flip 1 of 200 questions on `dev` and 2 of 80 on the golden slice
(hosted query embeddings, OQ-023), so noise alone never fires it.

| The change also gains … questions | It must lose at least … | Net drop caught on `dev` (200) | on golden slice (80) |
|---|---|---|---|
| 0 | 6 | **0.030** | 0.075 |
| 2 | 10 | 0.040 | 0.100 |
| 5 | 15 | 0.050 | 0.125 |
| 10 | 23 | 0.065 | 0.163 |
| 20 | 36 | 0.080 | 0.200 |
| 25 | 42 | 0.085 | 0.212 |

**"This gate catches a drop of ≥ 0.030 in recall@5 on `dev` when the change only loses
questions; a change that also wins some back needs a larger net drop — about 0.08 at the
churn the Phase 2 rerankers produced."** Smaller drops pass.

## Warnings for the gate rules (P3-09)

- **Citation integrity is not stable under no change** (resolved by DEC-087: a real-but-unretrieved citation is a hard fail — 0 in six runs; garbled and malformed citations are gated as citation validity against its MDD). Identical runs invent a document id
  in 1–2 answers of ~80 by chance (0.9737–0.9875). A zero-tolerance rule on invented
  citations would fail every build. P3-09 must decide how to gate it (DEC-083).
- **Refusal and false-answer rates move in whole questions.** On 15 unanswerable questions
  one question is 0.067; the floor is two.
- **These floors hold for this exact judge, host, generator and prompt.** A run whose
  provenance differs gets "no MDD measured" from the tooling until they are re-measured.

## What this does not measure
Paraphrase handling by the judge (P3-04 validated literal support only); human agreement;
the golden slice's representativeness — it over-samples the risk group on purpose.

## Correction (DEC-091, 2026-09-29) — what the gate can catch when it compares two runs

A PR run and the baseline run are two independent draws, so the noise the gate must stand
above is the noise of their **difference**: about √2 times one run's spread. Measured over
the five fresh golden runs on record (P3-07 ×3, ci-eval run 1, GitHub run 36523052541),
threshold = 2·√2·stdev, rounded up:

| Metric | **This gate catches a change of at least** | Smaller changes pass | Largest gap seen between two unchanged runs |
|---|---|---|---|
| mean faithfulness | **0.032** (drop) | < 0.032 | 0.027 |
| unsupported-answer rate | **0.109** (rise) | < 0.109 | 0.100 |
| false-answer rate (15 unanswerable) | **0.158** (rise) — **3 questions** | 1–2 questions | 0.133 |
| citation validity | **0.051** (drop) — about 4 answers | < 0.051 | 0.040 |
| refusal rate (report only) | 0.078 | | 0.063 |

In plain words: **"This gate catches a drop of ≥ 0.032 in mean faithfulness. Smaller drops
pass."** The earlier table claimed 0.026; that was one run's noise, and a gate built on it
fails unchanged pipelines by chance.

**When nothing changes, none of this applies**: an unchanged PR replays the baseline's own
answers from CI's cache and compares exactly equal (DEC-084, DEC-091). The thresholds matter
only when answers are regenerated — which is exactly when a pipeline change can hurt.
