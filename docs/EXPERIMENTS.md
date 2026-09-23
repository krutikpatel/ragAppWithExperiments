# Experiments

Index of every run, newest last. Every number here mirrors a row in the results store
(`results/runs.sqlite`) under a real `run_id`. No row is written before its run has
produced one.

| Exp | Run ID | Date | Axis | Change vs baseline | Strict R@5 | Loose R@5 | nDCG@10 | MRR (1-doc) | Cit. prec. | p95 ms | $/query | Status | Detail |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0001 | `run_20260911_051054_ef08` | 2026-09-11 | baseline | BM25, fixed-512/0, top-5, Tier 1, dev | **0.405** | 0.505 | 0.384 | 0.332 (n=160) | 0.388 (T2, n=88; v1 parser — 0.383 under v2, DEC-043) | 35 | 0.0000 | SUPERSEDED (EXP-0003, DEC-038) | [→](experiments/EXP-0001.md) |
| EXP-0002 | `run_20260911_051322_3bcb` | 2026-09-11 | chunking | whole documents (paper's retrieval config) | 0.410 | 0.500 | 0.378 | 0.329 (n=160) | — | 21 | 0.0000 | VALID | [→](experiments/EXP-0002.md) |
| EXP-0003 | `run_20260912_213248_2471` | 2026-09-12 | control | BM25, fixed-600/100, top-5 chunks, Tier 1, dev (P1-01) | **0.410** | 0.505 | 0.379 | 0.329 (n=160) | — | 31 | 0.0000 | SUPERSEDED (EXP-0004, DEC-040) | [→](experiments/EXP-0003.md) |
| EXP-0004 | `run_20260912_215235_ff2f` | 2026-09-12 | control | **sparse control**: BM25, 600/100, top-5 **distinct docs**, pool 50, Tier 1, dev (P1-07 run 4). Collapse ratio 1.088 mean / 1.20 p90, exhaustion 0 | **0.410** | 0.505 | 0.379 | 0.329 (n=160) | — | 34 | 0.0000 | VALID | [→](experiments/EXP-0004.md) |
| EXP-0005 | `run_20260912_222538_b1dc` (+2 replicates) | 2026-09-12 | control | **dense control**: `qwen3-embedding-8b` (DeepInfra), 600/100, top-5 distinct docs, pool 50, Tier 1, dev (P1-07 run 1). vs EXP-0004: 70 gained / 9 lost; spread 0.005 over 3 runs | **0.715** | 0.815 | 0.629 | 0.557 (n=160) | — | 665 (replicate; 2441 with retries) | 0.0000004 | VALID | [→](experiments/EXP-0005.md) |
| EXP-0006 | `run_20260913_054522_7d37` | 2026-09-13 | control | **dense control, Tier 2**: + `gpt-5-nano`, `baseline_answer@v1`, placeholder judge; dev sub100 (P1-07 run 2). Cit. recall 0.608; step cov 0.289 (n=32); 0 URLs; answered on 31 of 33 retrieval misses | 0.670 (sub100) | 0.840 | 0.629 | — | **0.550** (n=95) | 11744 | 0.0091 (est.) | VALID | [→](experiments/EXP-0006.md) |
| EXP-0007 | `run_20260913_060733_6a9b` | 2026-09-13 | control | **dense control on `unanswerable`** (45 q, P1-07 run 3): refusal rate 0.578 (detector v1, recorded) / **0.733** (hand-read = detector v2, DEC-045); **false-answer rate 0.267**; 10 of 15 underspecified answered with citations; judge skipped (DEC-044) | — | — | — | — | — | 3679 | 0.0091 (est., pre-skip; ≈0.0004 actual) | VALID | [→](experiments/EXP-0007.md) |
| EXP-0008 | `run_20260916_061952_ffc5` | 2026-09-16 | embedding (baseline) | **dense control on `dev_large`** (6,221 synthetic, all single-gold — no multi-doc slice exists); same index as EXP-0005. Not a headline number (preflight 3). strict@1 0.857, strict@20 0.992 | 0.973 | 0.973 | 0.928 | 0.909 (n=6,221) | — | 3490 | 0.0000004 | VALID | [→](experiments/EXP-0008.md) |
| EXP-0009 | `run_20260916_081043_877a` | 2026-09-16 | embedding | `openai/text-embedding-3-large` (OpenAI), 3072-d, on `dev_large`: +0.0085 vs EXP-0008, p=0.0001 — **all of it on `feature_request` articles** (+0.033; `article` −0.003 n.s.). Index $0.40, 245 s | 0.982 | 0.982 | 0.945 | 0.929 (n=6,221) | — | 717 | 0.0000021 | VALID | [→](experiments/EXP-0009.md) |
| EXP-0009 | `run_20260916_091357_887a` | 2026-09-16 | embedding | same, on **`dev`** vs promoted (`be04`, 0.720): **Δ −0.005, p=1.0** (15 gained / 16 lost); multi-doc 0.350→0.300 (p=0.72); strict@1 +0.060 (p=0.078), nDCG +0.035 (p=0.071). **Null; not promoted** | 0.715 | 0.840 | 0.665 | 0.622 (n=160) | — | 735 | 0.0000024 | VALID | [→](experiments/EXP-0009.md) |
| EXP-0010 | `run_20260916_091959_3929` | 2026-09-16 | embedding | `baai/bge-m3` (DeepInfra), 1024-d, on `dev_large`: +0.0053 vs EXP-0008, p=0.019 — again **all on `feature_request`** (+0.032, 67/1); `article` **−0.008, p=0.002**. Index $0.04, 1,448 s (batch 5, MIS-023) | 0.978 | 0.978 | 0.942 | 0.927 (n=6,221) | — | 1535 | 0.0000002 | VALID | [→](experiments/EXP-0010.md) |
| EXP-0010 | `run_20260916_104021_e4ee` | 2026-09-16 | embedding | same, on **`dev`** vs promoted (0.720): **Δ −0.160, CI [−0.225, −0.095], p=0.0001** (8 gained / **40 lost**); every slice down; multi-doc nDCG −0.209. **Splits disagree in direction** (DEC-055). **Negative; not promoted** | **0.560** | 0.640 | 0.504 | 0.461 (n=160) | — | 1491 | 0.0000002 | VALID | [→](experiments/EXP-0010.md) |
| EXP-0011 | `run_20260916_104407_1cb0` | 2026-09-16 | embedding | `google/gemini-embedding-2` (Google AI Studio), 3072-d, symmetric (OQ-025), on `dev_large`: **+0.0153 vs EXP-0008, p=0.0001** — `article` +0.007 (p=0.003) **and** `feature_request` +0.033. strict@1 +0.055. Index $0.63, 249 s | **0.988** | 0.988 | 0.958 | 0.946 (n=6,221) | — | 613 | 0.0000036 | VALID | [→](experiments/EXP-0011.md) |
| EXP-0011 | `run_20260916_113159_79c4` | 2026-09-16 | embedding | same, on **`dev`** vs promoted (0.720): **Δ +0.030, CI [−0.030, +0.090], p=0.41** (22 gained / 16 lost); strict@1 +0.085 (p=0.02), **nDCG@10 +0.066 (p=0.002)**; multi-doc strict +0.025 (7/6), loose 0.85→0.95. **Not promoted under DEC-055** (`dev` decides; p=0.41). Passed DEC-050's superseded rule | 0.750 | 0.865 | 0.697 | 0.650 (n=160) | — | 475 | 0.0000036 | VALID | [→](experiments/EXP-0011.md) |
| EXP-0012 | `run_20260917_050235_e588` | 2026-09-17 | embedding (probe) | **control without the qwen3 query prefix** (OQ-026), on `dev_large`: +0.004 (p=0.03); `feature_request` 0.966→**0.988** (p=0.0001; pre-registered C2 threshold 0.99 **not met**); `article` −0.005 (p=0.025), @1 −0.023 (p=0.0001). Index rebuilt: 59% of vectors byte-identical to EXP-0005's (OQ-023 index side) | 0.977 | 0.977 | 0.927 | 0.907 (n=6,221) | — | 3310 | 0.0000004 | VALID | [→](experiments/EXP-0012.md) |
| EXP-0012 | `run_20260917_070405_a562` | 2026-09-17 | embedding (probe) | same, on **`dev`** vs promoted (0.720): **Δ −0.060, CI [−0.110, −0.010], p=0.035** (8 gained / 20 lost); nDCG −0.057 (p=0.0001); multi-doc nDCG −0.093 (p=0.007). **C3 fails; the prefix stays** | **0.660** | 0.755 | 0.574 | 0.516 (n=160) | — | 2052 | 0.0000002 | VALID | [→](experiments/EXP-0012.md) |
| EXP-0013 | `run_20260917_071034_7a2d` | 2026-09-17 | embedding | **control truncated to 1024-d** (`dimensions: 1024`, DeepInfra honours it), on `dev_large`: Δ +0.0002 vs EXP-0008, p=1.0 (23/22); strict@1 −0.005 (p=0.004). Index 33.7 MB, same $0.031 build | 0.973 | 0.973 | 0.925 | 0.905 (n=6,221) | — | 3989 | 0.0000004 | VALID | [→](experiments/EXP-0013.md) |
| EXP-0013 | `run_20260917_085730_9ea7` | 2026-09-17 | embedding | same, on **`dev`** vs promoted (0.720): **Δ −0.015, CI [−0.050, +0.015], p=0.55** (4 gained / 7 lost); nDCG −0.001; multi-doc unchanged (1/1). Same width as bge-m3, 0.705 vs its 0.560. **No measurable difference; 4096-d stays** | 0.705 | 0.800 | 0.630 | 0.575 (n=160) | — | 489 | 0.0000004 | VALID | [→](experiments/EXP-0013.md) |
| EXP-0014 | `run_20260917_174747_7c9f` | 2026-09-17 | retrieval_method | **hybrid RRF (k=60)**: dense control + EXP-0004 BM25, each top-100, fused by reciprocal rank (DEC-056); dev. vs promoted (0.720): **Δ −0.120, CI [−0.190, −0.055], p=0.0012** (14 gained / **38 lost**; 22 of the lost have gold absent from BM25's top-100 — RRF penalises single-list documents); multi-doc unchanged (5/6). vs BM25 (0.410): +0.190, 38/0. Context docs from both lists 999 / dense-only 0 / BM25-only 1; candidate Jaccard 0.196. **Negative; not promoted** | **0.600** | 0.705 | 0.541 | 0.476 (n=160) | — | 18740 (DeepInfra slow today, see EXP file) | 0.0000004 | VALID | [→](experiments/EXP-0014.md) |
| EXP-0015 | `run_20260917_181731_627b` | 2026-09-17 | retrieval_method | **hybrid weighted α=0.2** (dense weight; min-max per list, DEC-056); dev. vs promoted (0.720): **Δ −0.225, CI [−0.300, −0.150], p=0.0001** (12 / 57); every slice down; multi-doc 0.250 (3/7, p=0.35). vs BM25: +0.085 (17/0). Context BM25-only 198 / dense-only 0. **Negative** | **0.495** | 0.580 | 0.448 | 0.398 (n=160) | — | 16676 (DeepInfra slow) | 0.0000004 | VALID | [→](experiments/EXP-0015.md) |
| EXP-0016 | `run_20260917_183840_42f5` | 2026-09-17 | retrieval_method | **hybrid weighted α=0.4**; dev. vs promoted: **Δ −0.130, CI [−0.200, −0.060], p=0.0006** (14 / 40); multi-doc 0.325 (5/6). vs α=0.2: +0.095 (p=0.0001). **vs RRF: −0.010, p=0.76 (190 of 200 same outcome) — RRF ≈ α=0.4 here.** Context dense-only 12 / BM25-only 103. **Negative** | **0.590** | 0.690 | 0.523 | 0.454 (n=160) | — | 1038 | 0.0000004 | VALID | [→](experiments/EXP-0016.md) |
| EXP-0017 | `run_20260917_184010_ae88` | 2026-09-17 | retrieval_method | **hybrid weighted α=0.6**; dev. vs promoted: **Δ −0.015, CI [−0.070, +0.040], p=0.72** (13 / 16); multi-doc 0.400 (6/4, p=0.75); nDCG −0.011 (p=0.54). vs α=0.4: +0.115 (p=0.0002). Losses are dense's rank 1–5 gold pushed to 6–10 where BM25 missed it. Context dense-only 105 / BM25-only 9. **No measurable difference** | 0.705 | 0.800 | 0.620 | 0.534 (n=160) | — | 589 | 0.0000004 | VALID | [→](experiments/EXP-0017.md) |
| EXP-0018 | `run_20260917_184123_a6e3` | 2026-09-17 | retrieval_method | **hybrid weighted α=0.8**; dev. vs promoted: **Δ +0.010, CI [−0.020, +0.040], p=0.75** (6 / 4; 190 unchanged); single-doc identical (3/3); multi-doc 0.400 (3/1, p=0.62); nDCG +0.011 (p=0.32, 110 tied). Losses all rank 5→6. Context dense-only 207 / **BM25-only 0**. `rag promote --dry-run`: NOT PROMOTED. **No measurable difference; not promoted** | 0.730 | 0.820 | 0.642 | 0.565 (n=160) | — | 625 | 0.0000004 | VALID | [→](experiments/EXP-0018.md) |
| EXP-0022 | `run_20260918_235010_d53e` | 2026-09-18 | chunking | **structure-aware chunking** (line boundaries; `:`-lines bound to their steps; ≤600 words; DEC-057) on `dev_large`: 8,689 chunks, 79.0% one-chunk (same articles as control), 41 procedure blocks cut (control 0). vs EXP-0008: **+0.0088, p=0.0002** (89/34) — **all on `feature_request`** (+0.026, 54/0); `article` +0.0005 (p=0.90). Index $0.032, 776 s, 16 retries (rate limiting began) | 0.982 | 0.982 | 0.938 | 0.921 (n=6,221) | — | 2209 | 0.0000004 | VALID | [→](experiments/EXP-0022.md) |
| EXP-0022 | `run_20260919_014505_4c6e` | 2026-09-19 | chunking | same, on **`dev`** vs promoted (0.720): **Δ −0.055, CI [−0.100, −0.010], p=0.033** (6 / 17); multi-doc 0.300 (0/2); short −0.095 (p=0.015); nDCG −0.007 (p=0.60). **8 of the 17 lost golds are single-chunk under both chunkers** — identical words, only line breaks and a fresh embed differ; re-embed floor unmeasured (OQ-031). **Splits disagree; negative on dev; not promoted** | 0.665 | 0.775 | 0.624 | 0.564 (n=160) | — | 550 | 0.0000004 | VALID | [→](experiments/EXP-0022.md) |
| EXP-0020 | `run_20260919_014614_366b` | 2026-09-19 | chunking | **parent-document / small-to-big** (150-word children indexed, 600-word parent as context) on `dev_large`: 18,884 children, 44.7% one-child, 1,237 blocks cut at child level / 150 at parent. vs EXP-0008: **−0.0072, CI [−0.011, −0.004], p=0.0002** (41/86); `article` −0.011; `feature_request` +0.0005. Collapse 1.262 / p90 1.8. Index $0.031, 725 s | 0.966 | 0.966 | 0.916 | 0.894 (n=6,221) | — | 1888 | 0.0000004 | VALID | [→](experiments/EXP-0020.md) |
| EXP-0020 | `run_20260919_030111_72ea` | 2026-09-19 | chunking | same, on **`dev`** vs promoted (0.720): **Δ −0.025, CI [−0.075, +0.025], p=0.46** (12 / 17); multi-doc 0.350 (3/3); nDCG −0.014 (p=0.42). **Collapse 1.106 → 1.315 (p90 1.4 → 1.8)** — first Phase 2 config to move it; no exhaustion. Gains are the F10 exact-term set. **No measurable difference; not promoted** | 0.695 | 0.800 | 0.617 | 0.556 (n=160) | — | 1361 | 0.0000004 | VALID | [→](experiments/EXP-0020.md) |
| EXP-0019 | `run_20260919_042347_e7dd` | 2026-09-19 | chunking | **sentence-window** (1 sentence indexed, ±3 context) on `dev_large` — index build (196,133 rows) died on DeepInfra **HTTP 429 after 4 retries** ~42 min in; partial embeddings lost. See MIS-024 | — | — | — | — | — | — | — | VOID (MIS-024) | [→](experiments/EXP-0019.md) |
| EXP-0019 | `run_20260919_050519_c444` | 2026-09-19 | chunking | same, `dev` — no index on disk, rebuild attempted, immediate 429. See MIS-024 | — | — | — | — | — | — | — | VOID (MIS-024) | [→](experiments/EXP-0019.md) |
| EXP-0023 | `run_20260922_052729_e550` | 2026-09-22 | control | **the control re-embedded** into a fresh index dir (OQ-031): same config, same 8,218 chunks, new vectors. vs promoted (0.720): **Δ −0.010, CI [−0.025, 0.000], p=0.49 — 0 gained / 2 lost**, both rank 5→6; multi-doc 0 flips; nDCG@10 unchanged to 4 dp. **This is the re-embedding floor every Axis 1 delta is read against.** Index $0.031, 623 s | 0.710 | 0.810 | 0.631 | 0.561 (n=160) | — | 6097 | 0.0000004 | VALID | [→](experiments/EXP-0023.md) |
| EXP-0021 | `run_20260922_061430_500f` | 2026-09-22 | chunking | **semantic chunking** (95th-percentile consecutive-sentence distance, ≤600 words) on `dev_large`: **19,296 chunks, only 2.9% of articles whole** (control 79.0%), mean 123 words, 3,482 procedure blocks cut. vs EXP-0008: **−0.0104, CI [−0.015, −0.006], p=0.0001** (52/117); @1 −0.036. Sentence pass $0.008 (50,852 embedded, 4,505 from cache) + index $0.031, 1,180 s | 0.963 | 0.963 | 0.906 | 0.883 (n=6,221) | — | 4296 | 0.0000004 | VALID | [→](experiments/EXP-0021.md) |
| EXP-0021 | `run_20260922_083410_9f8a` | 2026-09-22 | chunking | same, on **`dev`** vs promoted (0.720): **Δ −0.045, CI [−0.090, 0.000], p=0.078** (6 / 15); multi-doc 0.300 (1/3); nDCG −0.034; collapse 1.238. Losses look like evidence dilution — golds with 2–7 chunks in the pool whose best 123-word piece loses to other articles' best. **No measurable difference; not promoted.** H-016 wrong on chunk count | 0.675 | 0.780 | 0.596 | 0.527 (n=160) | — | 7097 | 0.0000004 | VALID | [→](experiments/EXP-0021.md) |
| EXP-0019 | `run_20260922_084139_aaf1` | 2026-09-22 | chunking | **sentence-window** (1 sentence indexed, ±3 context) on `dev_large`, re-run after MIS-024: **196,133 rows, 3,213 MB, 2.8 h build**, mean 12 words; all 5,936 procedure blocks cut (3,263 still cut in context). vs EXP-0008: **−0.072, CI [−0.080, −0.064], p=0.0001** (89/537); @1 −0.189; collapse 1.490 / p90 2.2. Index $0.034 | 0.901 | 0.901 | 0.813 | 0.771 (n=6,221) | — | 3810 | 0.0000004 | VALID | [→](experiments/EXP-0019.md) |
| EXP-0019 | `run_20260923_042438_c9b1` | 2026-09-23 | chunking | same, on **`dev`** vs promoted (0.720): **Δ −0.190, CI [−0.260, −0.120], p=0.0001** (10 / **48**) — the largest negative in Phase 2; nDCG −0.146; @1 −0.075; multi-doc 0.250 (3/7); collapse 1.314. **Both splits agree in direction** (first in Axis 1). 24x index for a 19-point loss. **Negative; not promoted** | **0.530** | 0.625 | 0.485 | 0.434 (n=160) | — | 1169 | 0.0000004 | VALID | [→](experiments/EXP-0019.md) |

Status values: `RUNNING`, `VALID`, `VOID`, `SUPERSEDED`.

Column notes:
- **Strict R@5** is the headline: all gold documents in the top 5 (DEC-010).
- **MRR** is over the single-gold subset only, with its `n` (DEC-011).
- **Cit. prec.** is citation precision, deterministic, from Tier 2 runs. Judged metrics
  (faithfulness, answer correctness, answer relevance) are **deliberately absent** from
  this table while the judge is a placeholder (DEC-018, preflight item 14). They exist
  in the results store.
- **$/query** is exact for Tier 1 (zero) and an estimate for Tier 2 (DEC-035).
- EXP-0001's citation precision comes from its Tier 2 variant, `run_20260911_053316_510b`,
  on the fixed 100-question subsample. **Corrected by DEC-043:** it was computed with
  the v1 citation parser (MIS-016); under `citation-v2` it is 0.383, recall 0.395.
  Every later Tier 2 row records `citation_parser: citation-v2`. Two VOID Tier 2 attempts precede it (MIS-010,
  MIS-011) and stay in the store.
- Two earlier runs of EXP-0001's config, `run_20260911_051026_e28c` and
  `run_20260911_051033_e88c`, were made on a dirty tree as a determinism check. They
  are identical to the canonical run and are not experiments.
- **EXP-0001 is SUPERSEDED, not VOID.** Its numbers are a valid measurement of the
  512/0 config; it stopped being the control when DEC-038 reconciled both Phase 1
  controls at 600/100. EXP-0003 is the sparse control from 2026-09-12 on. EXP-0001's
  Tier 2 variant and citation-precision figure were not re-run (DEC-038 says why).
- **Axis `control`** marks a row that later experiments diff against; it is not a
  technique.
- **EXP-0003 is SUPERSEDED by EXP-0004** (DEC-040): same ranking, same numbers, but
  `top_k` now counts distinct documents and the collapse ratio is recorded. One
  sparse control row, not two.
- **EXP-0005's $/query is the exact provider-reported query-embedding cost** (Tier 1
  dense runs are no longer free); the one-time index build ($0.031) is in the detail
  file, not amortised into the column. A VOID index-build attempt
  (`run_20260912_222345_671e`, MIS-014) precedes it and stays in the store.
- **EXP-0006 and EXP-0007 are not comparable to EXP-0001's Tier 2 variant on any
  generation metric**: chunker, prompt, context semantics and citation parser all
  differ. They are the generation baseline Phase 2 diffs against.
- **EXP-0007 has no retrieval columns** (no gold, DEC-009). Its refusal rate was
  recorded with detector v1 (0.578); `refusal-lexical-v2` (DEC-045) agrees with the
  hand count of all 45 answers (0.733). **Every refusal figure recorded before
  2026-09-13 is a v1 number**; EXP-0001's Tier 2 refusals were 2 → 20 under v2 (the
  detector missed curly apostrophes). Runs from here record `refusal-lexical-v2`.
- **EXP-0006 was replicated twice** (`run_20260913_202416_9156`, `run_20260913_205058_dc03`)
  for P1-11; the MDD table below is their spread. They are not separate rows.
- **P1-09 diffability smoke test**: `run_20260913_222423_db8c` is
  `configs/baseline_dense.yaml` with only `top_k` 5 → 10 (`smoke_p1_09_dense_k10.yaml`).
  `rag diff` against EXP-0005: 0 flips on `strict_recall@5` (the scored ranking does not
  depend on `top_k`, DEC-040) and **27 gained / 0 lost on `gold_in_context`**, each a gold
  article at ranks 6–10 — i.e. strict recall@10 (0.850) seen from the context side.
  Collapse ratio 1.106 → 1.126. A harness check, not an experiment; no row.
- **Dense spread is not zero.** Hosted query embeddings vary call to call; three runs
  of EXP-0005 ranged 0.005 on strict recall@5 (OQ-023). Any dense delta at or under
  one question is within that.

## Axis 2 scorecard — embeddings (P2-08, EXP-0008–0013)

Five experiments against the promoted control (`qwen3-embedding-8b`, DeepInfra, 4096-d,
`qwen3` prefix). `dev` decides (DEC-055); `dev_large` is the single-document direction
check. Every retrieval delta is a paired test (DEC-047, seed 20260915). Total actual
spend for the axis: **$1.17** over 11 runs (estimate $1.30).

| EXP | Change vs control | `dev` strict R@5 (Δ, p) | `dev` nDCG@10 (Δ, p) | `dev` multi-doc R@5 | `dev_large` strict R@5 (Δ, p) | Index | Verdict |
|---|---|---|---|---|---|---|---|
| 0008 | — (control on `dev_large`) | 0.720 (be04) | 0.631 | 0.350 | **0.973** | cached | baseline |
| 0009 | `text-embedding-3-large` (OpenAI), 3072-d | 0.715 (−0.005, 1.0) | 0.665 (+0.035, 0.07) | 0.300 | 0.982 (+0.0085, 0.0001; `feature_request` only) | $0.40, 101 MB | null |
| 0010 | `bge-m3` (DeepInfra), 1024-d | **0.560 (−0.160, 0.0001)** | 0.504 (−0.127, 0.0001) | 0.225 | 0.978 (+0.005, 0.02) | $0.04, 34 MB | **negative; splits disagree** |
| 0011 | `gemini-embedding-2` (AI Studio), 3072-d | 0.750 (+0.030, 0.41) | **0.697 (+0.066, 0.002)** | 0.375 | **0.988 (+0.015, 0.0001)** | $0.63, 101 MB | not promoted (DEC-055) |
| 0012 | control, no query prefix (probe) | 0.660 (−0.060, 0.035) | 0.574 (−0.057, 0.0001) | 0.250 | 0.977 (+0.004, 0.03) | $0.03 rebuild | negative; prefix stays |
| 0013 | control at 1024-d | 0.705 (−0.015, 0.55) | 0.630 (−0.001, 0.93) | 0.350 | 0.973 (+0.0002, 1.0) | $0.03, 34 MB | null |

What the axis established, in order of how much it changes later axes:
1. **`dev_large` cannot decide a dense-model comparison.** It has no multi-document
   questions, sits at 0.973 for the control, and gave bge-m3 a significant gain while
   `dev` gave it a 16-point loss (DEC-055, MIS-021).
2. **Four fifths of every candidate's `dev_large` gain was one thing**: 66 synthetic
   `feature_request` questions the control's answer-oriented query prefix mis-ranks.
   Removing the prefix recovers 53 of them and loses 6 points on `dev` (EXP-0012).
3. **No embedding model beats the control on `dev` at p < 0.05.** Gemini improves the
   ordering inside the top five (nDCG +0.066, strict R@1 +0.085) without changing
   which questions have every gold document there; that is filed for the reranking
   axis (OQ-027).
4. **Width is not the lever at this scale**: a quarter of the dimensions is a null
   (EXP-0013), and the model that lost 16 points was not losing them to width.
5. **The multi-document slice did not move for any candidate** (0.225–0.375 on n=40, all
   p ≥ 0.12). The organizing question is untouched by the embedding axis.

## Axis 3 scorecard — retrieval method (P2-09, EXP-0014–0018)

Five experiments against the promoted control (dense, `qwen3-embedding-8b`), all on
`dev` (the only split this axis may use, P2-04 / DEC-055), Tier 1, same index, same
BM25 as the sparse control (EXP-0004). Fusion definitions in DEC-056. Every delta is a
paired test (DEC-047, seed 20260915). Total actual spend for the axis: **$0.0004** over
5 runs (200 query embeddings each).

| EXP | Fusion | strict R@5 (Δ vs dense, 95% CI, p) | gained / lost | multi-doc R@5 (n=40) | nDCG@10 (Δ, p) | vs BM25 (0.410) | context docs dense-only / BM25-only | Verdict |
|---|---|---|---|---|---|---|---|---|
| 0004 | BM25 only (control) | 0.410 | | 0.175 | 0.379 | — | | sparse control |
| 0015 | weighted α=0.2 | 0.495 (−0.225, [−0.300, −0.150], 0.0001) | 12 / 57 | 0.250 | 0.448 (−0.183, 0.0001) | +0.085 (17 / 0) | 0 / 198 | negative |
| 0016 | weighted α=0.4 | 0.590 (−0.130, [−0.200, −0.060], 0.0006) | 14 / 40 | 0.325 | 0.523 (−0.108, 0.0001) | +0.180 (36 / 0) | 12 / 103 | negative |
| 0014 | RRF k=60 | 0.600 (−0.120, [−0.190, −0.055], 0.0012) | 14 / 38 | 0.325 | 0.541 (−0.090, 0.0005) | +0.190 (38 / 0) | 0 / 1 | negative |
| 0017 | weighted α=0.6 | 0.705 (−0.015, [−0.070, +0.040], 0.72) | 13 / 16 | 0.400 | 0.620 (−0.011, 0.54) | +0.295 (61 / 2) | 105 / 9 | no measurable difference |
| 0018 | weighted α=0.8 | 0.730 (+0.010, [−0.020, +0.040], 0.75) | 6 / 4 | 0.400 | 0.642 (+0.011, 0.32) | +0.320 (70 / 6) | 207 / 0 | no measurable difference; not promoted |
| 0005 | dense only (control) | 0.720 (be04) | | 0.350 | 0.631 | +0.310 | | promoted control |

Adjacent points on the curve: 0.2→0.4 **+0.095** (p = 0.0001); 0.4→0.6 **+0.115**
(p = 0.0002); 0.6→0.8 +0.025 (p = 0.36). RRF vs α=0.4: −0.010 (p = 0.76, 190 of 200
identical outcomes). Collapse ratio 1.10–1.12 mean, p90 1.2–1.4, for every point —
fusion did not change how many chunks fold into one article.

What the axis established:
1. **No retrieval-method change beats dense on `dev`.** The curve is monotone in the
   dense weight and the best point (α=0.8, +0.010, p = 0.75) is ten flipped questions
   with a net of one. The chosen α, if one had to be chosen, is 0.8 with a 95% CI on
   its delta of [−0.020, +0.040] — a CI that contains zero, so nothing is chosen and
   the control stays.
2. **Every hybrid loses nothing against BM25 and the lexical half never wins a slice.**
   H-001's "serious opponent" (nine BM25-alone wins on `dev`) is real but small: at
   most 13–14 questions gain from lexical signal at any fusion setting, and 5–6 of
   those are questions neither half answered alone. Against that, RRF and α ≤ 0.4
   lose 38–57 questions whose gold document BM25 does not return at all (22 of RRF's
   38 losses had the gold absent from BM25's top 100).
3. **RRF is a consensus rule, and on this corpus it costs 12 points** (EXP-0014). A
   document in one list only can score at most 1/61 under RRF; anything at ranks (5, 8)
   in both lists beats it. 999 of RRF's 1,000 context documents came from the
   intersection of the two top-100 lists, which overlap by a Jaccard of 0.196. RRF at
   k=60 behaved like weighted fusion at α≈0.4 (EXP-0016).
4. **The multi-document slice did not move at any point** (0.250–0.400 on n=40, all
   p ≥ 0.35). The organizing question is untouched by the retrieval-method axis, as it
   was by the embedding axis.
5. **The corpus-character claim from the Phase 1 handover is settled in the direction
   it did not expect**: exact product names (*Wix Payments*, *iCal*, *og:image*) make
   BM25 a strong single-question competitor — a rank-1 hit on *"add a full PDF to my
   portfolio site"* where dense had rank 9 — but not a strong retriever. Lexical
   matching here is worth a re-order inside dense's top ten on a dozen questions and
   nothing more.

## Axis 1 scorecard — chunking (P2-07, EXP-0019–0023)

Four chunkers against the promoted control (fixed 600 words / 100 overlap), plus a
control rebuild that measures the floor. `dev` decides (DEC-055); `dev_large` is the
single-document direction check. Every delta is a paired test (DEC-047, seed 20260915).
Definitions and the two scope changes (late chunking dropped, structure-aware
redefined) are DEC-057. Total actual spend for the axis: **$0.161** over 9 runs
(2 VOID on rate limiting, MIS-024), of which $0.128 is index builds.

| EXP | Chunker | chunks | articles whole | proc. blocks cut (indexed / context) | `dev` strict R@5 (Δ, CI, p) | flips (+/−) | `dev` multi-doc | `dev` nDCG@10 | `dev` collapse | `dev_large` Δ | index | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | **control** fixed 600/100 | 8,218 | 79.0% | 0 / 0 | 0.720 | — | 0.350 | 0.631 | 1.106 | 0.973 | 135 MB | promoted |
| 0023 | control, **re-embedded** | 8,218 | 79.0% | 0 / 0 | 0.710 (−0.010, [−0.025, 0.000], **0.49**) | 0 / 2 | 0.350 (0/0) | 0.631 | 1.107 | — | 135 MB | **the floor** |
| 0020 | parent-document (150 → 600) | 18,884 | 44.7% | 1,237 / 150 | 0.695 (−0.025, [−0.075, +0.025], 0.46) | 12 / 17 | 0.350 (3/3) | 0.617 | 1.315 | −0.007 (p=0.0002) | 309 MB | no measurable difference |
| 0021 | semantic (95th pct) | 19,296 | 2.9% | 3,482 / 3,482 | 0.675 (−0.045, [−0.090, 0.000], 0.078) | 6 / 15 | 0.300 (1/3) | 0.596 | 1.238 | −0.010 (p=0.0001) | 316 MB | no measurable difference |
| 0022 | structure (line boundaries) | 8,689 | 79.0% | 41 / 41 | 0.665 (−0.055, [−0.100, −0.010], **0.033**) | 6 / 17 | 0.300 (0/2) | 0.624 | 1.111 | **+0.009** (p=0.0002) | 142 MB | negative on `dev`; splits disagree |
| 0019 | sentence-window (1, ±3) | **196,133** | 0.5% | 5,936 / 3,263 | **0.530 (−0.190, [−0.260, −0.120], 0.0001)** | 10 / **48** | 0.250 (3/7) | 0.485 | 1.314 | −0.072 (p=0.0001) | **3,213 MB** | negative, both splits |

What the axis established:

1. **No chunker beats fixed 600/100 on `dev`.** Two are indistinguishable from it, two
   are worse, and the best of the four (parent-document, −0.025) is still negative.
   **H-013 confirmed.** The control was not tuned into this position — it was chosen in
   DEC-038 before any of these chunkers existed.
2. **The re-embedding floor is 2 questions of 200** (EXP-0023), so the churn in these
   runs is real and not an artifact of rebuilding the index. It also corrects a caution
   written into EXP-0022 before the floor existed.
3. **Finer chunks cost recall on this corpus, monotonically in how fine they are.**
   Ordered by mean indexed length: 309 words → 0.720, 124 → 0.695, 123 → 0.675,
   12 → 0.530. Max pooling takes one chunk as a document's score, so splitting an
   article spreads its evidence and weakens every piece. The losses are dominated by
   golds that sit at rank 1–5 under the control and slide past the boundary, with a
   tail that falls out of the top 100 entirely.
4. **What finer chunks do buy is the exact-term question** — the same 6–10 questions
   gained by every config, and the same family BM25 wins (F10): *"add a full PDF to my
   portfolio site"* (control rank 9 → 1 or 2 under three of the four chunkers),
   *"header background to black when scrolling"*, *"grid gallery"*. Worth about ten
   questions; the control's coarse chunks are worth about forty.
5. **The flat curve the story predicted for single-document questions did not appear,
   because no chunker left the articles alone.** 79.0% of articles fit in one control
   chunk, but semantic left only 2.9% whole and sentence-window 0.5%. Flatness would
   have required a chunker that mostly agrees with the control; only structure-aware
   does (same 79.0%, same 4,915 articles), and it is the one that landed within a few
   points — and part of its −0.055 is a whitespace side-effect (OQ-032), not where it cut.
6. **The document-level walk (DEC-040) does not rescue a worse ranking.** Collapse rose
   with chunk fineness (1.11 → 1.24 → 1.31 → 1.49 on `dev_large`) and the pool was never
   exhausted, so the walk did exactly what it was built to do — and the deltas are still
   negative. This is the P2-07 confound, measured: small-to-big overlaps with the walk,
   and the overlap is not where the loss comes from.
7. **Procedure blocks: the control's overlap already protects them.** Fixed 600/100 cuts
   0 of 5,936; every alternative cuts more (41, 1,237, 3,482, 5,936). The story asked for
   "fixed chunking split N procedures, heading-aware reduced it to M, and multi-hop
   recall moved X"; measured, the sentence reads the other way round, and multi-hop
   recall did not move at significance under any chunker (0.250–0.350 on n=40, all
   p ≥ 0.34).
8. **`dev_large` disagreed with `dev` again** (structure: +0.009 vs −0.055), and again the
   `dev_large` gain was concentrated in the `feature_request` slice. Three axes in, the
   synthetic split has not once changed a decision correctly (DEC-055).

## Negative results (P2-17)

Standing section, populated as Phase 2 runs. Each entry: what was tried, the measured
delta, the verdict that makes it null, what it would have cost, the decision taken.

- **EXP-0009 — `openai/text-embedding-3-large` for `qwen3-embedding-8b`.** On `dev`
  (the only split with multi-document questions) strict recall@5 went 0.720 → 0.715,
  Δ −0.005, 95% CI [−0.060, +0.050], p = 1.0 (15 gained / 16 lost); multi-document
  0.350 → 0.300, p = 0.72. On `dev_large` it gained +0.0085 (p = 0.0001), entirely on
  `feature_request` articles. Cost it would have added: 13x per embedded token ($0.40
  vs $0.03 per index; $0.0000021 vs $0.0000004 per query). **Decision: control
  retained; not promoted.** Worth noting for later: top-1 placement and nDCG on
  single-document questions were better (nDCG single-doc +0.045, p = 0.043), which
  a reranking or k=1 context might care about and a five-document context does not.
- **EXP-0010 — `baai/bge-m3` for `qwen3-embedding-8b`.** On `dev`, strict recall@5
  0.720 → 0.560, Δ −0.160, 95% CI [−0.225, −0.095], p = 0.0001 (8 gained / 40 lost);
  nDCG@10 −0.127; multi-document nDCG −0.209. On `dev_large` it *gained* +0.005
  (p = 0.019) — the two splits disagree in direction, which is the P2-04 finding this
  program was told to look for. Cost it would have saved: 3/4 of the index size at the
  same per-token price. **Decision: control retained; not promoted; `dev_large` cannot
  be the sole decider for a dense-model comparison (DEC-055).**
- **EXP-0011 — `google/gemini-embedding-2` for `qwen3-embedding-8b`.** No measurable
  difference on the headline: `dev` strict recall@5 0.720 → 0.750, Δ +0.030, 95% CI
  [−0.030, +0.090], p = 0.41 (22 gained / 16 lost); multi-document +0.025 (7 / 6).
  What did move: strict recall@1 +0.085 (p = 0.020) and nDCG@10 +0.066 (p = 0.002)
  on `dev`, and +0.0153 (p = 0.0001) on `dev_large` including ordinary articles. Cost
  it would have added: 20x per embedded token ($0.63 vs $0.03 per index), 9x per
  query, and a Google-only dependency in place of open weights. **Decision: control
  retained under DEC-055; the ranking gain is filed for the reranking axis (OQ-027)
  — a better-ordered top 5 is what a reranker would otherwise have to buy.**
- **EXP-0012 — the control without its qwen3 instruct prefix (OQ-026).** On `dev`
  strict recall@5 0.720 → 0.660, Δ −0.060, 95% CI [−0.110, −0.010], p = 0.035; nDCG@10
  −0.057 (p = 0.0001). On `dev_large` the `feature_request` slice rose 0.966 → 0.988
  (p = 0.0001) but short of the pre-registered 0.99, while ordinary articles fell
  (−0.005 at k=5, −0.023 at k=1). Cost: nothing either way (query-side only).
  **Decision: the prefix stays. Finding: about 4/5 of every Axis 2 candidate's
  `dev_large` gain was the absence of an answer-oriented query instruction, not a
  better model.**
- **EXP-0013 — the control at 1024 of its 4096 dimensions.** `dev` strict recall@5
  0.720 → 0.705, Δ −0.015, 95% CI [−0.050, +0.015], p = 0.55 (4 gained / 7 lost);
  nDCG@10 −0.001; `dev_large` strict recall@5 identical (p = 1.0). What it would have
  saved: 100 MB of index and nothing on the embedding bill — a saving that does not
  register at 8,218 vectors. **Decision: 4096-d retained (no reason to change a
  control for a null); the null itself is the finding — width is not what separated
  bge-m3 (0.560 at 1024-d) from the control (0.705 at 1024-d).**
- **EXP-0014 — hybrid retrieval by Reciprocal Rank Fusion (k = 60).** `dev` strict
  recall@5 0.720 → 0.600, Δ −0.120, 95% CI [−0.190, −0.055], p = 0.0012 (14 gained /
  38 lost); nDCG@10 −0.090 (p = 0.0005); multi-document unchanged (5 / 6). 22 of the
  38 lost questions had their gold document absent from BM25's top 100, and RRF
  scores a single-list document below almost anything in both lists. Cost either way:
  $0.00008 per run, no re-index. **Decision: control retained. Finding: RRF is a
  consensus rule; it is the right tool for adding dense to a lexical system (38 / 0
  over BM25) and the wrong one for adding lexical signal to dense on this corpus.**
- **EXP-0015–0018 — weighted score fusion at α = 0.2 / 0.4 / 0.6 / 0.8 (dense weight).**
  `dev` strict recall@5 0.495 / 0.590 / 0.705 / 0.730 against dense 0.720: the curve is
  monotone in the dense weight, its lower end sits 0.085 above BM25 and its upper end
  +0.010 above dense (95% CI [−0.020, +0.040], p = 0.75; 6 gained / 4 lost, 190
  unchanged). The paired test cannot separate α=0.6 or α=0.8 from the control, and
  the grid is not refined further (DEC-056, P2-09). Cost: nothing either way.
  **Decision: control retained; `rag promote` refuses α=0.8. The α-curve is the
  finding: on this corpus the value of the lexical half is a re-ordering of dense's
  ranks 6–9 on about a dozen questions, and any weight large enough to introduce a
  document dense did not have costs more than it recovers.**
- **EXP-0019 — sentence-window chunking (1 sentence indexed, ±3 sentences of context).**
  `dev` strict recall@5 0.720 → 0.530, Δ −0.190, 95% CI [−0.260, −0.120], p = 0.0001
  (10 gained / 48 lost); nDCG@10 −0.146; `dev_large` −0.072 (p = 0.0001) — both splits
  agree, the only Axis 1 config where they do. What it cost to find out: a 196,133-row
  index, 3,213 MB, 2.8 hours to build, $0.034, against the control's 8,218 rows and
  135 MB. **Decision: control retained. Finding: a 12-word median index row cannot
  represent a help article on this corpus — 21 of the 48 lost questions fell past rank
  10 and one left the top 100 entirely. The ±3-sentence context still cut 3,263 of
  5,936 procedure blocks, so the window would have to be chosen against the
  procedure-length distribution rather than taken from a library default.**
- **EXP-0020 — parent-document / small-to-big (150-word children indexed, 600-word
  parent as context).** `dev` Δ −0.025, CI [−0.075, +0.025], p = 0.46 (12 / 17);
  `dev_large` −0.007 (p = 0.0002). Collapse 1.106 → 1.315. **Decision: control
  retained. Finding: the technique's usual lift is partly priced into the baseline
  already (DEC-040's document-level walk), and what remains is evidence dilution under
  max pooling — several lost golds had 3–6 children in the candidate pool while their
  best child ranked below other articles' best.**
- **EXP-0021 — semantic chunking (95th-percentile consecutive-sentence distance).**
  `dev` Δ −0.045, CI [−0.090, 0.000], p = 0.078 (6 / 15); `dev_large` −0.010
  (p = 0.0001). Cost: the only chunker that pays twice — $0.008 for the sentence pass
  (plus ~$0.02 lost to MIS-024) on top of a $0.031 index. **Decision: control retained.
  Finding: a per-article percentile rule cuts a coherent short article as readily as a
  rambling long one — 19,296 chunks, only 2.9% of articles left whole — so on this
  corpus "semantic chunking" is a much finer chunker, not a smarter one.**
- **EXP-0022 — structure-aware chunking on the corpus's line structure.** `dev` Δ −0.055
  (p = 0.033, 6 / 17); `dev_large` **+0.009** (p = 0.0002, entirely `feature_request`).
  **Decision: control retained; the splits disagree, so the `dev_large` gain cannot
  promote (DEC-055). Finding: keeping procedures intact was already delivered by the
  control's 100-word overlap (0 blocks cut vs this chunker's 41), so the premise of the
  technique does not apply to a corpus whose chunker already overlaps.**
- **EXP-0023 — the control, re-embedded (not a technique; the axis's measuring stick).**
  Same config, new vectors: 2 questions of 200 flip, both rank 5 → 6, nDCG@10 unchanged
  to four decimals. **Decision: none — this is the floor the four chunkers above are read
  against, and it is what lets EXP-0020's and EXP-0021's 21–29 flips be called churn
  rather than noise.**

## Phase 1 scorecard — the controls (P1-08)

Every number below mirrors a row in the results store. Runs: **sparse control** EXP-0004 (`run_20260912_215235_ff2f`), **dense control** EXP-0005 (`run_20260912_222538_b1dc`), **dense Tier 2** EXP-0006 (`run_20260913_054522_7d37`), **dense on `unanswerable`** EXP-0007 (`run_20260913_060733_6a9b`). All on corpus `sha256:74694ad4…`, `norm-v1`, chunker `fixed_token-0ad99a2d` (600/100, DEC-038), `top_k` 5 distinct documents with a 50-chunk pool (DEC-040), pooling `max`. Dense: `qwen/qwen3-embedding-8b` on DeepInfra (DEC-041). Generator `gpt-5-nano` with `baseline_answer@v1` (DEC-042), parsers `citation-v2` / `refusal-lexical-v2` (DEC-043/045).

**MDD** columns are the dense control's minimum detectable differences (DEC-046). A delta at or below its MDD is no measurable difference. Sparse (BM25) retrieval has zero spread.

**Judged metrics are absent by rule, not by omission.** Faithfulness, answer correctness and answer relevance were computed for EXP-0006 (and its two replicates) and are in the results store, but the judge is a placeholder (DEC-018, preflight item 17) and its values may not be transcribed here. Their MDDs are: faithfulness 0.014, answer correctness 0.020, answer relevance 0.021 (corpus); per slice in the MDD table below. The scorecard is complete on the day a real judge is chosen — a model decision (CLAUDE.md §10).

There is **no sparse Tier 2 row under the reconciled config**: EXP-0001's Tier 2 variant ran on 512/0 with `answer@v1` and top-5 chunks and is not comparable (DEC-038). A sparse Tier 2 run of `exp_0004_bm25_distinct_docs.yaml` costs ~$0.91 and would fill the column.

### 1. Single-document vs multi-document — the split that matters most

| Metric | single (n=160) sparse | single dense | multi (n=40) sparse | multi dense |
|---|---|---|---|---|
| strict recall@1 | 0.212 | **0.375** | 0.000 | **0.000** |
| strict recall@3 | 0.381 | **0.656** | 0.050 | **0.200** |
| **strict recall@5** | 0.469 | **0.806** | 0.175 | **0.350** |
| strict recall@10 | 0.575 | **0.906** | 0.300 | **0.625** |
| loose recall@1 | 0.212 | **0.375** | 0.225 | **0.425** |
| loose recall@3 | 0.381 | **0.656** | 0.575 | **0.775** |
| loose recall@5 | 0.469 | **0.806** | 0.650 | **0.850** |
| loose recall@10 | 0.575 | **0.906** | 0.700 | **0.925** |
| nDCG@10 | 0.380 | **0.639** | 0.375 | **0.590** |
| collapse ratio mean | 1.091 | **1.105** | 1.075 | **1.110** |
| collapse ratio p90 | 1.200 | **1.200** | 1.400 | **1.400** |
| pool exhaustion | 0.000 | **0.000** | 0.000 | **0.000** |
| citation precision (Tier 2, sub100) | — | **0.529** (n=70) | — | **0.608** (n=25) |
| citation recall | — | **0.676** (n=74) | — | **0.417** (n=26) |
| step coverage | — | **0.260** (n=22) | — | **0.352** (n=10) |

MRR is over the single-gold subset by definition (DEC-011): sparse 0.329, dense **0.557** (n=160, MDD 0.008).

### 2. Retrieval, every slice (Tier 1, full `dev`, n=200)

Sparse / **dense**. Strict = all gold documents retrieved; loose = any.

| Slice | n | strict@1 | strict@3 | strict@5 | strict@10 | loose@1 | loose@3 | loose@5 | loose@10 | nDCG@10 | collapse mean | collapse p90 | exhaustion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 200 | 0.170 / **0.300** | 0.315 / **0.565** | 0.410 / **0.715** | 0.520 / **0.850** | 0.215 / **0.385** | 0.420 / **0.680** | 0.505 / **0.815** | 0.600 / **0.910** | 0.379 / **0.629** | 1.088 / **1.106** | 1.20 / 1.40 | 0.00 / 0.00 |
| gold_docs:single | 160 | 0.212 / **0.375** | 0.381 / **0.656** | 0.469 / **0.806** | 0.575 / **0.906** | 0.212 / **0.375** | 0.381 / **0.656** | 0.469 / **0.806** | 0.575 / **0.906** | 0.380 / **0.639** | 1.091 / **1.105** | 1.20 / 1.20 | 0.00 / 0.00 |
| gold_docs:multi | 40 | 0.000 / **0.000** | 0.050 / **0.200** | 0.175 / **0.350** | 0.300 / **0.625** | 0.225 / **0.425** | 0.575 / **0.775** | 0.650 / **0.850** | 0.700 / **0.925** | 0.375 / **0.590** | 1.075 / **1.110** | 1.40 / 1.40 | 0.00 / 0.00 |
| source:expertwritten | 100 | 0.180 / **0.260** | 0.290 / **0.570** | 0.390 / **0.690** | 0.510 / **0.850** | 0.220 / **0.370** | 0.430 / **0.730** | 0.530 / **0.830** | 0.630 / **0.940** | 0.392 / **0.636** | 1.094 / **1.112** | 1.20 / 1.20 | 0.00 / 0.00 |
| source:simulated | 100 | 0.160 / **0.340** | 0.340 / **0.560** | 0.430 / **0.740** | 0.530 / **0.850** | 0.210 / **0.400** | 0.410 / **0.630** | 0.480 / **0.800** | 0.570 / **0.880** | 0.366 / **0.622** | 1.082 / **1.100** | 1.20 / 1.40 | 0.00 / 0.00 |
| q_len:short | 74 | 0.257 / **0.432** | 0.392 / **0.635** | 0.473 / **0.797** | 0.568 / **0.878** | 0.284 / **0.500** | 0.446 / **0.730** | 0.541 / **0.865** | 0.608 / **0.919** | 0.423 / **0.697** | 1.081 / **1.103** | 1.20 / 1.20 | 0.00 / 0.00 |
| q_len:medium | 64 | 0.062 / **0.172** | 0.219 / **0.484** | 0.344 / **0.562** | 0.438 / **0.766** | 0.141 / **0.266** | 0.344 / **0.625** | 0.453 / **0.688** | 0.531 / **0.859** | 0.300 / **0.531** | 1.088 / **1.103** | 1.20 / 1.40 | 0.00 / 0.00 |
| q_len:long | 62 | 0.177 / **0.274** | 0.323 / **0.565** | 0.403 / **0.774** | 0.548 / **0.903** | 0.210 / **0.371** | 0.468 / **0.677** | 0.516 / **0.887** | 0.661 / **0.952** | 0.408 / **0.649** | 1.097 / **1.113** | 1.20 / 1.20 | 0.00 / 0.00 |

Corpus-level MDDs (dense): strict/loose recall@1 and @5 0.012; @3 and @10 0 (identical across three runs); nDCG@10 0.004; collapse ratio mean 0.003. `article_type` slices are omitted: every gold document in `dev` is `article`.

### 3. Generation (Tier 2, dense control, `dev` sub100 — EXP-0006) and refusal (EXP-0007)

| Metric | Value | n | MDD | Notes |
|---|---|---|---|---|
| faithfulness | *in store, not transcribed* | 100 | 0.014 | placeholder judge (DEC-018) |
| answer correctness | *in store, not transcribed* | 100 | 0.020 | placeholder judge (DEC-018) |
| answer relevance | *in store, not transcribed* | 100 | 0.021 | placeholder judge (DEC-018) |
| **citation precision** | **0.550** | 95 | 0.080 | of answers that cited; generator variance dominates this MDD |
| **citation recall** | **0.608** | 100 | 0.040 | |
| cited nothing | 0.05 | 100 | 0.023 | |
| step coverage | 0.289 | 32 | 0.097 | procedural references only; MDD is a third of the value (OQ-007) |
| step order preserved | 0.906 | 32 | 0.036 | of matched steps |
| refused on `dev` (`refusal-lexical-v2`) | 0.05 | 100 | 0.031 | |
| `false_refusal_rate` as defined (MIS-012) | 0.05 | 100 | 0.031 | refused on any answerable question |
| refused with all gold in context | 2/67 = 0.030 | 67 | — | the honest false-refusal rate (OQ-019, not yet adopted) |
| **answered with a gold document missing** | **30/33 = 0.909** | 33 | — | the ungrounded-answer rate (OQ-019) |
| **false-answer rate on `unanswerable`** | **0.267** (12/45) | 45 | — | EXP-0007; 12 of the 12 cited an article |
| answers with a URL | 0 | 100 | 0 | also 0 / 45 on `unanswerable` |
| answers formatted as a numbered list | 80 | 100 | — | 32 references are procedural |
| tokens per query (generator) | 2654 in / 363 out | 100 | — | |
| p50 / p95 latency, end to end | 4,278 / 11,744 ms | 100 | — | replicates: p95 36,315 and 4,285 ms — judge-side variance |
| cost per query | $0.0091 | 100 | — | estimate (DEC-035): generator + judge; ~$0.91 per run |

Refusal on `unanswerable` by reason (EXP-0007, v2): other-platform 15/15 refused; post-snapshot 13/15; underspecified 5/15 — **10 of 15 underspecified questions answered, all with citations**.

### 4. Generation by slice (Tier 2, dense control, sub100)

Slice boundaries for question length are the subsample's own terciles (P0-08), so `n` differs from section 2.

| Slice | n | strict@5 | citation precision (n) | citation recall | step coverage (n) | refused (v2) | answered with gold missing |
|---|---|---|---|---|---|---|---|
| all | 100 | 0.670 | 0.550 (95) | 0.608 | 0.289 (32) | 0.05 | 30/33 |
| gold_docs:single | 74 | 0.811 | 0.529 (70) | 0.676 | 0.260 (22) | 0.04 | 13/14 |
| gold_docs:multi | 26 | 0.269 | 0.608 (25) | 0.417 | 0.352 (10) | 0.08 | 17/19 |
| source:expertwritten | 57 | 0.667 | 0.526 (54) | 0.626 | 0.289 (32) | 0.05 | 18/19 |
| source:simulated | 43 | 0.674 | 0.581 (41) | 0.585 | — (—) | 0.05 | 12/14 |
| q_len:short | 45 | 0.733 | 0.622 (42) | 0.652 | 0.368 (8) | 0.07 | 10/12 |
| q_len:medium | 24 | 0.458 | 0.479 (24) | 0.465 | 0.207 (7) | 0.00 | 13/13 |
| q_len:long | 31 | 0.742 | 0.504 (29) | 0.656 | 0.285 (17) | 0.06 | 7/8 |

Per-slice judged MDDs (DEC-046): single 0.042 / 0.028 / 0.005, multi 0.112 / 0.050 / 0.074 (faithfulness / correctness / relevance). All 32 procedural references are expert-written.

### 5. Index, latency and cost

| | Sparse (BM25) | Dense (qwen3-embedding-8b, DeepInfra) |
|---|---|---|
| index build | in-process, seconds, $0 | **1213 s**, 129 calls, 7 retries, $0.031 |
| index size | — | **134.6 MB** (8,218 × 4096 float32), key `f0e720da2aa33751` |
| Tier 1 p50 / p95 latency | 15 / 34 ms | 325 / 2,441 ms (canonical, 7 retries); 289–298 / 635–665 ms (replicates) |
| Tier 1 cost per query | $0 exact | $0.0 exact (provider-reported) |
| Tier 2 cost per query | — | $0.0091 estimate |

### 6. Dense versus sparse — where each wins, by slice

From EXP-0004 and EXP-0005 (`rag diff`: 70 questions gained strict recall@5 under dense, 9 lost, 121 unchanged). Statements of what the numbers show; no conclusions beyond them.

- **Dense wins on every slice at every k.** The smallest strict recall@5 gain is +0.175 on multi-document questions (0.175 → 0.350); the largest is +0.371 on long questions (0.403 → 0.774). All are more than twenty times the dense MDD of 0.012.
- **Sparse wins on nine individual questions**, all short exact-term matches where BM25 had the article at rank 1–5 and dense placed it at 6–33 (*PDF Viewer App*, *Header Scroll Effects*, *Changing the Payment Date*; three refund-policy questions). No slice aggregates them.
- **Multi-document is the weakest slice under both**: dense finds one required article for 34 of 40 (loose 0.850) and all of them for 14 (strict 0.350); at k=10, 25 of 40.
- **Medium-length questions (13–17 words) are the worst length tercile under both** (0.344 → 0.562) and remain so on citation recall and step coverage in Tier 2 (0.465, 0.207). Not explained.
- **Collapse is small under both** (mean 1.088 vs 1.106; p90 1.20 vs 1.40; no exhaustion): on this corpus five chunks are nearly always five articles, so the document-level walk of DEC-040 rarely changes the context.
- **Misses are ranking misses under dense, vocabulary misses under sparse**: of the gold documents outside the top 5, **2 of 64** are outside the top 100 under dense against **52 of 135** under sparse (EXP-0004).

## Minimum detectable differences — standing reference (P1-11, DEC-046)

Measured on three identical runs of the dense control's Tier 2 config
(`configs/baseline_dense_tier2.yaml`) on the fixed 100-question subsample:
`run_20260913_054522_7d37`, `run_20260913_202416_9156`, `run_20260913_205058_dc03`.
Rule: **MDD = max(range, 2 × stdev), rounded up to 0.001**. A delta at or below its MDD is
"no measurable difference". Every judged or generated number in a scorecard carries its MDD.
Active in `rag/eval/noise_floor.py` as family `dense-control-v1`; the Phase 0 family (DEC-037)
is kept there for reading older rows. Full tables with the per-run values: DEC-046.

| Metric | MDD (corpus, n=100) | Notes |
|---|---|---|
| faithfulness | **0.014** | judged; per-slice up to 0.112 (multi-doc, n=26) |
| answer_correctness | **0.020** | judged; per-slice up to 0.053 |
| answer_relevance | **0.021** | judged; per-slice up to 0.074 |
| citation_precision | **0.080** | generator variance; 0.550 / 0.478 / 0.546 across runs of nothing |
| citation_recall | **0.040** | |
| cited_nothing | 0.023 | |
| step_coverage | **0.097** | value 0.19–0.29: cannot detect anything yet (OQ-007) |
| step_order_preserved | 0.036 | |
| refused / false_refusal_rate | **0.031** | `refusal-lexical-v2` |
| strict_recall@5 | 0.012 | hosted query embeddings (OQ-023); one question |
| strict_recall@1, loose_recall@5 | 0.012 | |
| nDCG@10 | 0.004 | |
| MRR (single-gold) | 0.008 | |
| collapse_ratio_mean | 0.003 | |
| strict_recall@3 / @10 / @20 | 0 | identical across the three runs |

Per-slice judged MDDs:

| Slice | n | faithfulness | answer_correctness | answer_relevance |
|---|---|---|---|---|
| gold_docs:single | 74 | 0.042 | 0.028 | 0.005 |
| gold_docs:multi | 26 | 0.112 | 0.050 | 0.074 |
| source:expertwritten | 57 | 0.039 | 0.030 | 0.021 |
| source:simulated | 43 | 0.025 | 0.024 | 0.043 |
| q_len:short | 45 | 0.041 | 0.053 | 0.019 |
| q_len:medium | 24 | 0.007 | 0.033 | 0.023 |
| q_len:long | 31 | 0.047 | 0.050 | 0.067 |

The two replicate runs are not experiments and have no index row; they are the noise
measurement for EXP-0006's configuration. Cost of the three: ~$2.73.

**How deltas are called from Phase 2 on (P2-01 / P2-02; DEC-047, DEC-048, DEC-049).**
Retrieval deltas are called by `rag compare <baseline> <candidate> --metric <m>`: a paired
test over per-question outcomes (contingency, Δ, bootstrap 95% CI, permutation p; seed
recorded), overall and per slice — never by repeating a deterministic run and averaging.
Judged and generated deltas are labelled by the tooling against the MDD of the family the
run's judge/generator/prompt provenance matches, in this form:
`faithfulness 0.740 (baseline 0.710, Δ+0.030, MDD ±0.014 → significant)`. The labels are
**significant**, **within judge noise** / **within noise**, or **no MDD measured** (a run
under a judge no family was measured for — P1-11 is re-run for it first). A delta above
the MDD but within 1.5 × MDD is marked marginal and gets three replicates before
anything is promoted. A run whose pipeline called an LLM carries its generation-cache
hit rate; below 100% on a repeat, `rag compare` warns and the warning is quoted.

<!-- corpus-profile:c852878d74a8 start -->
## Corpus profile — characterization, not an experiment (profile-v1)

Written by `rag corpus profile` from `results/corpus_profile/c852878d74a8.json`. Corpus `sha256:74694ad4a96b…`, `norm-v1`, 6,221 articles. Two units, always labelled: **words** are whitespace tokens, the chunker's unit (DEC-005); **tokens** are `cl100k_base` BPE tokens, 1.265 per word on this corpus.

### Article length

| Unit | min | p25 | median | p75 | p90 | p95 | max | mean |
|---|---|---|---|---|---|---|---|---|
| words | 4 | 68 | 201 | 538 | 911 | 1,216 | 6,653 | 376.5 |
| tokens | 6 | 84 | 256 | 678 | 1,156 | 1,528 | 10,624 | 476.3 |

Histogram, in words:

```
    0–99     2263  36.4% ███████████████
  100–199     834  13.4% █████
  200–299     530   8.5% ███
  300–399     502   8.1% ███
  400–499     377   6.1% ██
  500–599     406   6.5% ███
  600–799     520   8.4% ███
  800–999     267   4.3% ██
 1000–1499    333   5.3% ██
 1500–1999    109   1.8% █
 2000–2999     64   1.0% 
 3000+         16   0.3% 
```

### Fit in one chunk, and procedure boundaries

A **procedure block** is a heuristic (DEC-039): a line ending in `:` followed by two or more sentences that open with an imperative verb from a fixed list. It exists because the frozen text has no list markers — the source's numbered lists arrive as "To do X:\nClick A. Click B." — so the literal numbered-line count the story asks for is also reported, and is tiny. A block is **cut** when no single chunk contains all of it, header included; with overlap, straddling a stride boundary is not a cut if one of the two overlapping chunks still holds the whole block.

- Articles with a literal numbered line (`1.` / `1)`): **21** (0.3%); with two or more: 5 (0.1%).
- Articles with at least one procedure block: **2,350** (37.8%); 5,936 blocks in total, median 32 words, p90 55, max 144.

| Chunk config (words) | chunks | articles that fit in one chunk | procedure blocks cut | blocks longer than the overlap (eligible to be cut) | blocks longer than a chunk | articles with a cut block |
|---|---|---|---|---|---|---|
| 600/100 | 8,218 | 4,915 (79.0%) | 0 (0.0%) | 20 | 0 | 0 (0.0%) |
| 600/0 | 8,036 | 4,915 (79.0%) | 160 (2.7%) | 5,936 | 0 | 154 (2.5%) |
| 512/0 | 8,694 | 4,560 (73.3%) | 210 (3.5%) | 5,936 | 0 | 199 (3.2%) |

A block no longer than the overlap cannot be cut: whichever stride boundary it straddles, one of the two chunks that share the overlap holds all of it. The "eligible" column is therefore the ceiling on the cut count for that config.

### By article type

| Type | n | words median | words p90 | words max | tokens median | literal numbered line | procedure block | blocks | block words median / max |
|---|---|---|---|---|---|---|---|---|---|
| article | 4,109 | 409 | 1091 | 6,653 | 515 | 20 (0.5%) | 2,309 (56.2%) | 5,891 | 32 / 144 |
| feature_request | 2,049 | 56 | 94 | 846 | 71 | 0 (0.0%) | 35 (1.7%) | 39 | 39 / 77 |
| known_issue | 63 | 30 | 121 | 264 | 37 | 1 (1.6%) | 6 (9.5%) | 6 | 24 / 63 |

| Type | chunk config | chunks | fit in one chunk | blocks cut | articles with a cut block |
|---|---|---|---|---|---|
| article | 600/100 | 6,104 | 2,805 (68.3%) | 0 (0.0%) | 0 (0.0%) |
| article | 600/0 | 5,922 | 2,805 (68.3%) | 160 (2.7%) | 154 (3.8%) |
| article | 512/0 | 6,580 | 2,450 (59.6%) | 210 (3.6%) | 199 (4.8%) |
| feature_request | 600/100 | 2,051 | 2,047 (99.9%) | 0 (0.0%) | 0 (0.0%) |
| feature_request | 600/0 | 2,051 | 2,047 (99.9%) | 0 (0.0%) | 0 (0.0%) |
| feature_request | 512/0 | 2,051 | 2,047 (99.9%) | 0 (0.0%) | 0 (0.0%) |
| known_issue | 600/100 | 63 | 63 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| known_issue | 600/0 | 63 | 63 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| known_issue | 512/0 | 63 | 63 (100.0%) | 0 (0.0%) | 0 (0.0%) |

<!-- corpus-profile:c852878d74a8 end -->
