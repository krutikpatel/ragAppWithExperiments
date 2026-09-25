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
| EXP-0024 | `run_20260923_052903_c2ea` | 2026-09-23 | reranking | **cohere/rerank-v3.5**, 50 candidate docs → top-5 (DEC-058/059) — died on the first query embedding: `OPENROUTER_API_KEY` was not in the launching shell's environment. No provider call was made and **nothing was spent**. Recorded rather than dropped; the run row exists | — | — | — | — | — | — | — | VOID (no API key in env) | [→](experiments/EXP-0024.md) |
| EXP-0024 | `run_20260923_052941_4ada` | 2026-09-23 | reranking | **cohere/rerank-v3.5 cross-encoder**, 50 candidate **documents** (58.4 chunks/query) → top-5, dev (DEC-058/059). vs promoted (0.720): **Δ −0.055, CI [−0.120, +0.010], p=0.139** (17 gained / 28 lost). **Better at the top, worse in the middle, identical at the bottom**: strict@1 +0.065 (p=0.08), nDCG@10 +0.024 (p=0.28), **strict@20 0.920 → 0.920, p=1.000 — the candidate set is the ceiling**. Gold's rank moved up a band for 40 single-gold questions and down for 39; 2.28 of 5 context docs replaced per question. Collapse 1.106→1.113 (the feared re-concentration did not happen; 79% of articles are one chunk). **No measurable difference, at 4x latency and ~2,900x cost/query. Not promoted** | 0.665 | 0.775 | 0.655 | 0.600 (n=160) | — | 2727 | 0.00117 | VALID | [→](experiments/EXP-0024.md) |
| EXP-0025 | `run_20260923_054802_6566` | 2026-09-23 | reranking | **cohere/rerank-4-fast**, same 50 candidate docs → top-5. vs promoted (0.720): **Δ +0.010, CI [−0.055, +0.080], p=0.887** (24 gained / 22 lost) — null. But **vs EXP-0024's v3.5: Δ +0.065, CI [+0.010, +0.125], p=0.039 — the two rerankers ARE distinguishable** (OQ-035 answered). strict@1 +0.070 (p=0.052), nDCG@10 +0.042 (p=0.057), **multi-doc 0.350→0.475 (+0.125, p=0.18)**, strict@20 **0.940** > control's 0.920 — which disproves EXP-0024's ceiling claim (MIS-029; true ceiling = control recall@50 = **0.985**). Cost $0.448 vs $0.468 estimated (4% under — first out-of-sample check of MIS-028). **No measurable difference vs control; not promoted** | 0.730 | 0.805 | 0.673 | 0.618 (n=160) | — | 18774 | 0.00224 | VALID | [→](experiments/EXP-0025.md) |
| EXP-0026 | `run_20260923_060805_1b9a` | 2026-09-23 | reranking | **qwen/qwen3-reranker-8b** (the open-weight contrast), dev — died on its first rerank call: **HTTP 402, OpenRouter account out of credits**. 402 correctly not retried; **nothing billed** (`cost_actual_usd` NULL). Config committed and unrun; the open-weight question is still open. See MIS-031 | — | — | — | — | — | — | — | VOID (MIS-031, no credits) | [→](experiments/EXP-0026.md) |
| EXP-0026 | `run_20260924_033136_e51f` | 2026-09-24 | reranking | **qwen/qwen3-reranker-8b** (open-weight, Fireworks), same 50 candidate docs → top-5, after crediting. vs promoted: **Δ +0.0000, CI [−0.070, +0.070], p=1.000 — 26 gained / 26 lost**, the cleanest null in the project. **Opposite shape to the Cohere pair**: the only reranker *worse* at rank 1 (−0.020) and the best at depth — @10 +0.030, **@20 0.950, the highest recall@20 any config here has produced**. multi-doc 0.350→0.450 (p=0.38). vs 4-fast −0.010 (p=0.88); vs v3.5 +0.055 (p=0.118). 31 transient retries. Cost **$1.210 vs $0.917 estimated (32% over — a cross-encoder bills the query once PER DOCUMENT, MIS-032)**. **No measurable difference; not promoted** | 0.720 | 0.820 | 0.645 | 0.552 (n=160) | — | 9372 | 0.00605 | VALID | [→](experiments/EXP-0026.md) |
| EXP-0027 | `run_20260924_041357_ebc5` (+λ 0.5/0.7/0.9/1.0) | 2026-09-24 | assembly | **MMR diversity sweep**, λ = 0.3/0.5/0.7/0.9/1.0 over 50 candidate docs → top-5 (P2-13, DEC-062). **Monotone and monotonically harmful**: 0.335 / 0.360 / 0.570 / 0.685 / 0.715 against the control's 0.720. λ=0.3 vs promoted **Δ −0.385, CI [−0.460, −0.315], p=0.0001 (3 gained / 80 lost)**; λ=0.9 **Δ −0.035, p=0.039**. **multi-doc 0.350 → 0.000** at λ=0.3 (14 lost / 0 gained, p=0.0002) — the slice MMR exists to serve, hurt worst. λ=1.0 reproduces the control (0.715, collapse 1.107), so the machinery is verified. Collapse falls to **1.000** — perfect diversity, halved recall. Measured cause: candidate-candidate cosine spans 0.5–0.87 while relevance spans 0.173, so diversity out-leverages relevance and selects semantic outliers; and **two golds of one question are +0.095 MORE similar to each other (0.788) than to an average candidate (0.693)**, so MMR penalises the second gold hardest. **Negative; not promoted.** Whole sweep cost **$0.0005** | 0.335 | 0.440 | 0.381 | 0.415 (n=160) | — | 6454 | 0.0000004 | VALID | [→](experiments/EXP-0027.md) |
| EXP-0028 | `run_20260925_014154_2d6b` | 2026-09-25 | assembly | **lost-in-the-middle reordering** — the five selected documents written into the prompt as rank 1, 3, 5, 4, 2 (P2-13). Tier 2, **no judge (DEC-063)**. **Retrieval columns are deliberately blank: this technique is a permutation of the same chunks and cannot change a retrieval metric** (asserted in tests; P2-13 forbids reporting one). Deterministic generation metrics, paired test vs `run_20260913_205058_dc03`: citation precision 0.525→0.513 (Δ −0.021, p=0.558), citation recall Δ −0.005 **p=1.000**, step coverage Δ −0.008 (p=0.792), refusal Δ −0.010 p=1.000 — **every metric inside its MDD, nothing significant on any slice** (lowest p anywhere 0.106). The finding is the churn: **15 questions changed citations, and for 13 of them the retrieved set AND ranking were identical** — 6 up, 7 down, net zero. One question (`3f42c8a9`) flipped to the **opposite factual claim** on identical evidence. Measured cause of the null: the assembled context is **1,712 words ≈ 2,174 tokens**, below the **2,700-token floor** of the range Liu et al. 2023 measured the effect over. **No measurable difference; not promoted.** $0.0278 vs $0.0341 est | — | — | — | — | — | 5441 | 0.00034 | VALID | [→](experiments/EXP-0028.md) |
| EXP-0029 | `run_20260925_015243_dd41` | 2026-09-25 | assembly | **contextual compression** attempt 1 — died on call ~222 of ~500 with `EmptyGenerationError`: `openai/gpt-oss-20b` returned `finish_reason='length'`, `completion_tokens=1000`, **`reasoning_tokens=1000`** — the whole budget spent reasoning before any output. **221 calls had succeeded (~$0.009) and all are in the generation cache, so nothing was wasted.** Two faults: the model was licensed on a probe of a *different prompt* (DEC-064 tested `contextual_chunk`, not `compress_context`), and a per-chunk failure was allowed to VOID a 100-question run. The same input **succeeds on retry** (123 reasoning tokens) — the failure is non-deterministic at temperature 0. See MIS-034 | — | — | — | — | — | — | — | VOID (MIS-034) | [→](experiments/EXP-0029.md) |
| EXP-0029 | `run_20260925_025103_28d7` | 2026-09-25 | assembly | **contextual compression** — each retrieved chunk trimmed by `gpt-oss-20b` to the sentences bearing on the question (P2-13, DEC-063/064). Tier 2, no judge. **Retrieval columns blank by construction: compression runs after the document walk.** Prompt went **1,712 → 912 words (reduction 0.467)** and **5.00 → 3.13 documents**; 187 of 500 chunks dropped entirely. Paired test: **citation recall 0.598 → 0.522, Δ −0.0883, CI [−0.168, −0.010], p = 0.0358, MDD 0.040 — significant and negative**, the first significant deterministic result in Axis 6. Citation precision −0.051 (p=0.21), **step coverage +0.019 (p=0.73)**, refusal **Δ 0.0000 p=1.000**. The compressor discriminates well — drops **43.9% of non-gold vs 8.7% of gold chunks** — yet of the 17 questions that lost citation recall, only 6 lost a gold chunk: **11 kept every gold chunk and lost the citation anyway.** Reduction is understated by my own checker (MIS-035; 0.542 corrected, simulated on the same completions) — a bug that worked *against* this finding. **Negative; not promoted.** $0.0306 actual vs $0.0566 est (221 calls replayed free) | — | — | — | — | — | 18440 | 0.00031 | VALID | [→](experiments/EXP-0029.md) |
| EXP-0030 | `run_20260925_045759_b1c7` | 2026-09-25 | assembly | **Anthropic-style contextual retrieval** — every chunk prefixed with an LLM-generated situating statement (`gpt-oss-20b`, mean 34.2 words) and the **prefixed text indexed**; the generator still sees the original chunk, and the 600/100 boundaries are the control's, so only retrieval can move (P2-13, DEC-064). **8,218 calls, 1 failed** (0.012% — cost one chunk, not the run: MIS-034's hardening). vs promoted (0.720): **Δ +0.0050, CI [−0.050, +0.060], p = 1.000 — 16 gained / 15 lost.** Same depth shape as the rerankers from a different mechanism: **@1 +0.035, @10 −0.020, @20 −0.025**, nDCG@10 +0.017 (p=0.32). multi-doc 0.350→0.400 (p=0.72). **The pre-registered subset test: one-chunk gold articles are perfectly inert (0.780→0.780, 4 gained / 4 lost), all movement is in multi-chunk golds (+0.010, 12/11)** — and dev is 50% multi-chunk against the corpus's 21%, so the technique was tested on a 2.4x enriched subset and still returned +0.010. Losses are not bad prefixes: a gold with an accurate prefix fell rank 1 → >5 because **every competitor got a prefix too**. Index build **$0.2550** (21 min at 16 workers; 16 h before MIS-036). **No measurable difference; not promoted** | 0.725 | 0.830 | 0.648 | 0.584 (n=160) | — | 3818 | 0.0000008 | VALID | [→](experiments/EXP-0030.md) |
| EXP-0030 | `run_20260925_051847_7c33` | 2026-09-25 | assembly | **the P2-03 warm-cache repeat** of the row above: 99.99% of the 8,218 prefix calls replayed from cache, **$0.00016**, byte-identical index. strict@5 **0.730**, Δ +0.0100 vs promoted (p = 0.857). The **0.005 gap between two runs of this identical config is hosted query-embedding non-determinism alone** (OQ-023) — the cleanest measurement of that noise floor so far. Caveat on the row: the one prefix call that failed cold **succeeded here**, so this run reports 8,218 prefixes while reusing the cold run's 8,217-prefix index (OQ-043) | 0.730 | 0.830 | 0.648 | 0.584 (n=160) | — | 3654 | 0.0000008 | VALID | [→](experiments/EXP-0030.md) |
| EXP-0031 | `run_20260925_062204_6667` | 2026-09-25 | query_transform | **query decomposition** (P2-12, run first per the story), cold cache: sub-questions replace the question, retrieved separately, RRF fused. **1.27 sub-queries/question, 0 fallbacks, 50 of 200 questions actually split.** vs promoted: Δ −0.0450, CI [−0.085, −0.005], **p = 0.0501 / McNemar 0.0490 — straddling the threshold**, reported as such. Superseded as the headline by the warm-cache repeat below (3% hit rate here, so the paired test's fixed-outcome assumption does not hold, P2-03) | 0.675 | 0.820 | 0.613 | 0.545 (n=160) | — | — | 0.0000113 | VALID | [→](experiments/EXP-0031.md) |
| EXP-0031 | `run_20260925_063044_0da8` | 2026-09-25 | query_transform | **the P2-03 warm-cache repeat — the headline.** 100% of transforms replayed, **$0.00009**. vs promoted (0.720): **Δ −0.0550, CI [−0.095, −0.015], p = 0.0186 — significant and negative** (4 gained / 15 lost); single-doc −0.0563 (**p=0.035**), long questions −0.113 (**p=0.041**). **multi-doc 0.350 → 0.300** — the slice it was ordered first to serve, and the fourth technique in a row not to move it. **The entire loss is in the 50 questions actually split: 0.740 → 0.540 (3 gained / 13 lost), while the 150 unsplit reproduce the control (0.713 → 0.707), 145 of them returned verbatim.** Cause measured: each extra sub-query finds **40.8 new documents** — they work exactly as designed. The gold answers the WHOLE question; each part has a better-matching article that is not the gold, and RRF ranks 'best answer to part A' above 'good answer to both'. **Significant negative; not promoted** | 0.665 | 0.820 | 0.614 | 0.545 (n=160) | — | — | 0.0000005 | VALID | [→](experiments/EXP-0031.md) |
| EXP-0032 | `run_20260925_064215_4033` | 2026-09-25 | query_transform | **HyDE** — a generated 120-word help passage **replaces** the question as the query (Gao et al. 2022); one query, so no fusion. 200/200 generated, 0 fallbacks. vs promoted: Δ **+0.0150**, CI [−0.050, +0.080], p = 0.754 — **no measurable difference**, but the only positive direction in the axis. **multi-doc 0.350 → 0.450 (+0.100, p=0.35, 7 gained / 3 lost) — the largest multi-document movement any technique in this project has produced, and not significant at n=40** (OQ-045). Highest churn in the axis: 43 of 200 questions changed outcome to net +0.015. single-doc flat (p=1.000) against a 0.8125 start. **Not promoted.** $0.00035 warm | 0.735 | 0.830 | 0.653 | 0.578 (n=160) | — | — | 0.0000018 | VALID | [→](experiments/EXP-0032.md) |
| EXP-0033 | `run_20260925_070609_71df` | 2026-09-25 | query_transform | **multi-query expansion** — 3 paraphrases + the original, RRF fused. 2.985 generated/question, 0 fallbacks. vs promoted: **Δ exactly +0.0000, p = 1.000 (12 gained / 12 lost)** — the cleanest null in the axis. But **q_len:short −0.0946, p = 0.0160, 7 lost / 0 gained** — the only slice in the axis with an empty side: a short question is already near-keyword, and paraphrases pull the fusion off the literal match. Each rewrite found **16.8 documents the original did not**, falsifying the premise that a meaning-preserving paraphrase retrieves the same ranking. **Not promoted.** $0.00030 warm | 0.720 | 0.845 | 0.641 | 0.567 (n=160) | — | — | 0.0000015 | VALID | [→](experiments/EXP-0033.md) |
| EXP-0034 | `run_20260925_074024_9154` | 2026-09-25 | query_transform | **step-back prompting** — one general question + the original, RRF fused (Zheng et al. 2023). vs promoted: **Δ −0.0750, CI [−0.130, −0.020], p = 0.0169 — significant and negative** (10 gained / 25 lost), the worst result in Axis 4. long questions −0.129 (**p=0.037**); multi-doc 0.350 → 0.250. **Measured defect: 46 of 200 step-back questions (23.0%) invented a Wix product the original never named** — *"How to make the published changes draft?"* → *"How does **Wix Bookings** handle published changes draft?"*. **But only 6 of those 46 lost the gold, so it explains ~a quarter of the 25 losses**; the rest is the axis's fusion problem — the general question found **34.7 new documents** and RRF then ranks 'best overview' above 'good specific'. **Significant negative; not promoted.** $0.00014 warm | 0.645 | 0.780 | 0.584 | 0.512 (n=160) | — | — | 0.0000007 | VALID | [→](experiments/EXP-0034.md) |
| EXP-0038 | _(no run — reconstructed)_ | 2026-09-25 | generation | **abstention threshold sweep**, the P2-14 deliverable. Rebuilt exactly from EXP-0006 and EXP-0007's stored per-question scores and answers — **$0.00**, same argument as the top-k sweep (DEC-061). Abstain before generating when top-1 retrieval score < T. Signal separates answerable from unanswerable at **AUC 0.712**. **At T=0.575 the false-answer rate HALVES, 0.2667 → 0.1333, with false-refusal unchanged at 0.0299 and no dev question lost — the only free move in the phase.** Past it the trade is steep: 0.0667 costs 3.5x the false refusals; 0.0000 costs 52%. Caveat stated: the threshold is selected on the data it is evaluated on, so 0.1333 is optimistic until P2-18 | — | — | — | — | — | — | 0.0 | VALID | [→](experiments/EXP-0038.md) |
| EXP-0039 | `run_20260925_204905_8e9a` + `…205710_eb8f` | 2026-09-25 | generation | **citation enforcement** — every step must carry a citation or be dropped (`enforced_answer@v1`), dev + full unanswerable, no judge. **False-answer rate 0.2667 → 0.8444 (+0.578) — the largest regression on the axis's hard target in the phase.** The system **stopped refusing entirely**: 0 refusals in 145 questions. Step coverage **0.193 → 0.033**. Citation precision −0.056, recall +0.047, cited-nothing → 0.000. Mechanism: told to cite every step, the model writes a numbered cited statement *about* the articles instead of refusing — *"1. The provided articles cover currency changes for Wix products, not Squarespace…"*. **Negative; not promoted.** $0.0374 | — | — | — | — | — | — | 0.00037 | VALID | [→](experiments/EXP-0039.md) |
| EXP-0040 | `run_20260925_210039_c048` + `…210747_6539` | 2026-09-25 | generation | **span-level vs chunk-level citation** — quote the exact words, not just the id (`span_answer@v1`). **span_support 0.7964 on dev, 0.7429 on unanswerable: one quoted span in five is NOT in the document it names**, at 4.87 spans per answer. Citation precision **0.546 → 0.435 (−0.110)**, step coverage **0.193 → 0.019** (lowest in the project), false-answer 0.2667 → 0.8889. Needed **citation-v3** to run at all — under v2 the span form matched nothing and every citation metric would have read zero. **Span citation delivers a verifiable artifact and fails its own verification 1 time in 5. Negative; not promoted.** $0.0428 | — | — | — | — | — | — | 0.00043 | VALID | [→](experiments/EXP-0040.md) |
| EXP-0041 | `run_20260925_211103_1e43` + `…212428_6bc5` | 2026-09-25 | generation | **groundedness self-check** — a second cross-family call (`gpt-oss-20b`, DEC-067) that replaces an unsupported answer with a refusal. **False-answer 0.2667 → 0.2222 (−0.044) at a false-refusal cost of 0.0299 → 0.1212 (+0.091)** — it rejects roughly as much good work as bad (12 dev rejections, 6 of them on questions whose gold was in context). Costs **4,600 ms per answered question** and $0.0055/100q. 0 unparseable, 0 failed, all 41 refusals short-circuited without a call. **Dominated on BOTH axes by the free threshold of EXP-0038 (0.1333 / 0.0299). Not promoted.** $0.0409 | — | — | — | — | — | — | 0.00041 | VALID | [→](experiments/EXP-0041.md) |
| EXP-0042 | `run_20260925_223023_fbcd` | 2026-09-25 | combination | **HyDE + cohere/rerank-4-fast** (P2-16). **R@5 0.7500 — the highest in the project — at Δ +0.0300, p = 0.444, so not a finding.** multi-doc 0.450. **The sub-additivity result:** control solves 14/40 multi-doc, HyDE 18, rerank 19, **additive prediction 24 (0.600), measured 18 (0.450)** — the combination equals its *weaker* component. Decomposes into overlap (**4 of each technique's 7 gains are the same questions**) and interference (the combination **loses 6 questions an arm had solved**). Costs **$0.0022918/query forever** against the control's $0.0000000. **Not promoted** | 0.750 | 0.845 | 0.676 | 0.588 (n=160) | — | 2980 | 0.0022918 | VALID | [→](experiments/EXP-0042.md) |
| EXP-0043 | `run_20260925_223430_553c` | 2026-09-25 | combination | **HyDE + hybrid weighted α=0.8** — the deliberately cheap arm. R@5 0.7400 (+0.0200, p = 0.683), multi-doc 0.425, **$0.0000018/query**. Highest **nDCG@10 in the project (0.6819)** while third on strict recall@5 — better at ranking, no better at the deciding metric. H-031 predicted it would land *below* HyDE alone because HyDE feeds BM25 a 120-word passage of high-frequency corpus vocabulary; it landed above. **Not promoted** | 0.740 | 0.840 | 0.682 | 0.582 (n=160) | — | 6444 | 0.0000018 | VALID | [→](experiments/EXP-0043.md) |
| EXP-0044 | `run_20260925_223951_153c` | 2026-09-25 | combination | **contextual retrieval + HyDE** — index-side + query-side, both 'write text with a model then embed it'. R@5 0.7250 (+0.0050, **p = 1.000**), multi-doc **0.375 — below contextual retrieval alone (0.400) and HyDE alone (0.450)**. The two overlap destructively on the slice both improve individually. **Not promoted** | 0.725 | 0.830 | 0.646 | 0.571 (n=160) | — | 2299 | 0.0000018 | VALID | [→](experiments/EXP-0044.md) |
| EXP-0045 | `run_20260925_224144_bebc` | 2026-09-25 | combination | **contextual retrieval + HyDE + hybrid α=0.8** — all three free positives stacked, and EXP-0042 minus its paid component. **R@5 0.7100 — BELOW the control (Δ −0.0100, p = 0.885) — and multi-doc lands on exactly 0.350, the control's value**, after passing through three techniques each of which raised it alone. **Adding components degrades monotonically: 0.750 / 0.740 / 0.725 at two components, 0.710 at three.** **Not promoted** | 0.710 | 0.830 | 0.664 | 0.569 (n=160) | — | 1167 | 0.0000018 | VALID | [→](experiments/EXP-0045.md) |
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

## Axis 5 scorecard — reranking (P2-10, EXP-0024–0026) — CLOSED

Three cross-encoders against the promoted dense control, over an identical 50-document
candidate set. `dev` decides (DEC-055); the `dev_large` check was never bought because
nothing won (OQ-033). Every delta is a paired test (DEC-047, seed 20260915). Axis
spend: **$1.892** over 5 runs (2 VOID — MIS-026 no API key, MIS-031 no credits).

| EXP | Reranker | `dev` strict R@5 (Δ, CI, p) | flips (+/−) | R@1 | R@10 | R@20 | nDCG@10 | multi-doc R@5 | collapse | p50 ms | $/query | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | **control** (no reranker) | 0.720 | — | 0.305 | 0.850 | 0.920 | 0.631 | 0.350 | 1.106 | 298 | $0.0000004 | **promoted** |
| 0024 | `cohere/rerank-v3.5` | 0.665 (−0.055, [−0.120, +0.010], 0.139) | 17 / 28 | **0.370** | 0.825 | 0.920 | 0.655 | 0.300 | 1.113 | 1,194 | $0.00117 | no measurable difference |
| 0025 | `cohere/rerank-4-fast` | **0.730** (+0.010, [−0.055, +0.080], 0.887) | 24 / 22 | **0.375** | 0.840 | 0.940 | **0.673** | **0.475** | 1.119 | 3,847 | $0.00224 | no measurable difference |
| 0026 | `qwen/qwen3-reranker-8b` | 0.720 (**+0.000**, [−0.070, +0.070], **1.000**) | 26 / 26 | 0.285 | **0.880** | **0.950** | 0.645 | 0.450 | 1.101 | 3,172 | $0.00605 | no measurable difference |
| — | **ceiling**: control recall@**50** | **0.985** | — | — | — | — | — | — | — | — | — | what the candidate set contains |

What the axis established:

1. **No reranker moved the deciding metric.** −0.055 (p = 0.139), +0.010 (p = 0.887),
   +0.000 (p = 1.000). `promoted.yaml` is unchanged and Axis 5 closes with no winner.
2. **The nulls are not inaction — they are balanced churn.** EXP-0026 gained 26
   questions and lost 26 for a delta of exactly zero. Across the three, each replaced
   roughly 2.3 of the 5 context documents on nearly every question. A reranker changed
   what the generator sees for ~97% of questions and changed the measured outcome for
   none of them.
3. **They do not share a shape, and two of them differ significantly.**
   `rerank-4-fast` beat `rerank-v3.5` by +0.065 (p = 0.039). The Cohere pair sharpen
   rank 1 (+0.065, +0.070) and lose ground at rank 5; `qwen3-reranker-8b` runs the
   other way — the only one *worse* at rank 1 (−0.020) and the best at depth
   (**@20 = 0.950**, the highest any configuration in this project has produced).
   Three cross-encoders, one candidate set, three different behaviours, one identical
   verdict. That is why one reranker could never have closed this axis (OQ-035).
4. **The ceiling is 0.985 and none of them approached it.** The gold document is in
   the 50-document candidate set for **98.5%** of questions; the best reranker put it
   in the top five for **73%**. Twenty-five points sit between "retrieved" and
   "ranked", untouched by any of the three (F16). The control's depth curve:
   **@5 0.720, @10 0.850, @20 0.920, @30 0.955, @40 0.975, @50 0.985.**
   (This replaces EXP-0024's claim that 0.920 was the ceiling — MIS-029.)
5. **`multi_doc` moved most and can still not be called.** 0.350 → 0.300 / 0.475 /
   0.450. The best is +0.125 on 40 questions at p = 0.18. Suggestive, and exactly the
   slice size that moves without meaning anything.
6. **The re-concentration risk P2-10 named did not appear** for any of the three
   (collapse 1.106 → 1.113 / 1.119 / **1.101**). 79% of articles are a single chunk,
   so there is rarely a second chunk of the same article to promote. The corpus cannot
   express that failure mode.
7. **Cost and latency are the only unambiguous results.** 4x, 13x and 11x the
   control's median latency; ~2,900x, ~5,600x and **~15,000x** its per-query cost;
   nothing measurable bought. Reranking is also the first axis billed **per query**,
   so these configs cost $0.23–$1.21 on `dev` and would cost $7–$38 on `dev_large`.
8. **Three cost-model errors in one axis, all the same mistake** (MIS-025, MIS-028,
   MIS-032): assuming the provider bills the thing we happened to be counting. Prices
   listed at $0 that are not free; search units filled by candidate length rather than
   count; a cross-encoder billing the query once per document. The estimator now
   reproduces both billing models to within 0.1–4%, calibrated on these runs and
   **not yet validated out of sample** (OQ-036).

**Cut from this axis (DEC-060):** the two k → n ratio runs and the LLM-as-reranker.
So this axis's null is a statement about **50 → 5 with three cross-encoders**, not
about reranking in general: a narrower candidate set is untested (OQ-038), and the one
mechanism that is not a cross-encoder was never run. `rag/reranking/llm.py` and its
output parser are therefore built and never exercised on real model output.

## Top-k sweep (P2-13) — reconstructed from a recorded run, not a new run

**No run was made for this.** Every number below is computed from
`run_20260912_225005_be04` (the promoted dense control, `dev`, n=200) by replaying
its stored per-question chunk ranking through the same `select_distinct_docs` the
runner uses. It is exact, not an approximation, for a reason worth stating:

**`top_k` cannot change a retrieval metric.** The metrics score the pooled document
*ranking*; `top_k` only decides how far down that ranking the context walk goes.
Measured directly — `run_20260913_222423_db8c` is the control at `top_k=10` and
scores strict recall@1/@5/@10/@20 of 0.305 / 0.715 / 0.850 / 0.920, identical to the
`top_k=5` run `run_20260912_224833_75b2` at every depth (nDCG differs by 0.00016,
which is the dense retriever's known non-determinism, OQ-023, not `top_k`). So a
"top-k sweep" at Tier 1 re-measures numbers the ledger already holds, and the
honest move is to read them rather than buy them.

| top_k | gold in context | single-doc | multi-doc | collapse | exhaustion | ctx words | ~ctx tokens |
|---|---|---|---|---|---|---|---|
| 1 | 0.305 | 0.381 | 0.000 | 1.000 | 0.000 | 357 | 453 |
| 3 | 0.565 | 0.656 | 0.200 | 1.078 | 0.000 | 1,034 | 1,313 |
| **5** (promoted) | **0.720** | **0.812** | **0.350** | 1.106 | 0.000 | 1,711 | 2,172 |
| 10 | 0.850 | 0.906 | 0.625 | 1.126 | 0.000 | 3,341 | 4,243 |
| 15 | 0.890 | 0.925 | 0.750 | 1.147 | 0.000 | 4,963 | **6,303** |
| 20 | 0.920 | 0.944 | 0.825 | 1.151 | 0.000 | 6,531 | 8,294 |
| 30 | 0.955 | 0.963 | 0.925 | 1.151 | 0.000 | 9,773 | 12,411 |
| 40 | 0.975 | 0.975 | 0.975 | 1.163 | 0.005 | 12,953 | 16,450 |
| 50 | 0.985 | 0.988 | 0.975 | 1.164 | 0.000 | 16,089 | 20,433 |

`candidate_pool` was held at the promoted 50 through `top_k=20`; beyond that the walk
needs a deeper pool to find that many distinct documents, so it was widened (53 / 69 /
85) and the exhaustion column confirms the widening was sufficient. **The promoted
`candidate_pool` of 50 supports `top_k` up to about 30 without exhaustion.**

What it shows:

1. **Depth is where the multi-document questions live.** The slice that is 20% of the
   question set and 46% of the failures goes **0.350 → 0.625 → 0.825** at k = 5, 10,
   20. It more than doubles by k=10. Single-document questions gain far less over the
   same range (0.812 → 0.906 → 0.944) because they are mostly already satisfied.
2. **`context_max_tokens` binds before the recall does.** The promoted config caps
   the assembled context at **6,000 tokens**, which is reached at about **k=14**. So
   raising `top_k` past ~14 hands the assembler more documents than it will pass on,
   and the retrieval gain from k=15 to k=50 (0.890 → 0.985) **cannot reach the
   generator** without also raising that cap. Any top-k experiment that moved one
   without the other would be measuring truncation, not context depth. This is a
   two-field change and so is not a one-dimension diff (P2-05).
3. **Collapse stays flat.** 1.106 at k=5 to 1.164 at k=50 — the walk does not have to
   work much harder for ten times the documents, because 79% of articles are a single
   chunk.

What it does **not** show, and what a Tier 2 run would cost: whether a larger context
produces better *answers*. Everything above is an input-side fact. More context also
means more tokens to dilute, more opportunity to cite the wrong article, and more
money per query. Faithfulness and citation precision at k=10 or k=20 against EXP-0006
are unmeasured, and that is the experiment worth buying here (OQ-040).

## P2-11 revisit pass — priced at $1.40 and not bought (DEC-066)

P2-11 asks for the top 3 chunking configurations re-run under **the winning reranker from
P2-10**. Axis 5 closed with **no winner**, so the pass was priced, declined and recorded
per P2-17's provision for an axis that was costed and deliberately not run.

**The side-by-side table the story asks for, with the column that exists.** All on `dev`,
strict recall@5, paired against the control (`rag compare`, 10,000 resamples):

| Chunking | Without reranker | p | multi-doc | With `rerank-4-fast` |
|---|---|---|---|---|
| **fixed_token 600/100** (control) | **0.7200** | — | 0.350 | **0.7300** (+0.010, p=0.887) — EXP-0025 |
| parent-document (150/600) | 0.6950 | 0.457 | 0.350 | _not bought — $0.4681_ |
| semantic (95th pct) | 0.6750 | 0.078 | 0.300 | _not bought — $0.4681_ |
| structure-aware | 0.6650 | **0.0325** | 0.300 | _not bought — $0.4681_ |
| sentence-window | 0.5300 | **0.0001** | 0.250 | _excluded: 4th by multi-doc_ |

**Why the right-hand column was not bought.** The revisit's question is whether chunking
differences *survive* a strong reranker. The strongest reranker measured here moved the
metric by **+0.010 at p = 0.887** — it is not a strong reranker on this corpus. Asking
whether chunking differences survive an intervention that does nothing is arithmetic, not
an experiment. The three configs are committed unrun (`exp_0035..0037`) so the estimate
stays checkable and the pass can be executed later for $1.40.

**Composition verdict, which P2-11 requires to be stated explicitly: neither composed,
partially composed, nor cancelled — there were no winners to compose.** Axis 1 produced
no chunker that beat the control; Axis 5 produced no reranker that beat it. Composition
is a question about two positive results and this phase has none. The most common error
in this kind of programme — assuming one-factor winners stack — could not be committed
here for want of any one-factor winner.

**And the tie-break rule was already satisfied.** P2-11 says that if chunking differences
collapse, `promoted.yaml` reverts to the simplest strategy statistically indistinguishable
from the best. The simplest strategy *is* the best: `fixed_token` 600/100 is at or above
every alternative, two of which are significantly below it. `promoted.yaml` already names
it and no revert is needed.

**Honest gap:** Phase 2 definition-of-done item 9 says the revisit pass "has been run and
its composition verdict recorded". The verdict is recorded. The pass was not run.


## P2-16 combination set — sub-additivity, and the frontier (EXP-0042–0045) — CLOSED

P2-16 asks whether the per-axis winners compose. **There were none to compose**: six axes
produced a single positive result and it is not a retrieval technique (DEC-068). So the
four combinations pair the techniques that were individually **positive but null** on the
multi-document slice — the organizing question's slice — and ask whether their gains add.
**Axis spend: $0.4594** against a $0.9762 estimate; every contextual prefix and HyDE
transform was already cached.

| Config | R@5 | Δ | p | multi-doc | $/query |
|---|---|---|---|---|---|
| control | 0.7200 | — | — | 0.350 | $0.0000000 |
| **EXP-0042** HyDE + rerank | **0.7500** | +0.0300 | 0.444 | 0.450 | $0.0022918 |
| EXP-0043 HyDE + hybrid | 0.7400 | +0.0200 | 0.683 | 0.425 | $0.0000018 |
| EXP-0044 ctx + HyDE | 0.7250 | +0.0050 | 1.000 | 0.375 | $0.0000018 |
| EXP-0045 ctx + HyDE + hybrid | 0.7100 | −0.0100 | 0.885 | 0.350 | $0.0000018 |

**The sub-additivity result, question by question on the 40 multi-document questions:**

| | solved | rate |
|---|---|---|
| control | 14 | 0.350 |
| HyDE alone | 18 | 0.450 |
| `rerank-4-fast` alone | 19 | 0.475 |
| **additive prediction** | **24** | **0.600** |
| **measured combination** | **18** | **0.450** |

1. **Overlap.** Each technique rescues 7 questions the control misses, and **4 of those
   are the same 4 questions**. The union is 10, not 14 — a perfect combination could
   never have exceeded 0.600, and the two techniques were far less independent than
   their separate scores implied.
2. **Interference.** The combination captures 8 of those 10 and **loses 6 questions that
   an arm had already solved**, some of which the plain control got right. Two techniques
   that each improve a ranking do not leave each other's improvements intact.
3. **Monotone degradation with component count.** 0.750 / 0.740 / 0.725 at two
   components; **0.710 at three — below the control**. The three-way stack's multi-doc
   slice returns to exactly 0.350 after passing through three techniques that each raised
   it alone.

**The cost/quality frontier** (`docs/figures/p2_16_frontier.png`) is nearly flat. A
**1,300x** price difference between the cheapest and dearest configuration buys +0.030
strict recall@5 at p = 0.444. The only large real separation on it is the one Phase 1
established — dense over BM25, 0.720 against 0.410 — and both of those points cost
nothing per query.

**Verdict: no combination promoted. `promoted.yaml` unchanged.** The phase's most
expensive configuration is also its best-scoring and its least justifiable.

## Axis 7 scorecard — generation and grounding (P2-14, EXP-0038–0041) — CLOSED

Tier 2 on the `dev` subsample **plus the full 45-question `unanswerable` set** every run,
judge skipped (DEC-063), detector `refusal-lexical-v3` on **both arms of every
comparison** (MIS-038). **Axis spend: $0.1211** — EXP-0038 cost nothing.

The hard target is the Phase 1 false-answer rate on `unanswerable`, which is **0.2667**
and not the 0.4222 printed in EXP-0007's row; that row was written by a detector that hid
7 refusals of 45 (MIS-037).

| EXP | Technique | False-answer ↓ | False-refusal ↓ | Cost / query | Verdict |
|---|---|---|---|---|---|
| — | **control** (`baseline_answer@v1`) | 0.2667 | 0.0299 | — | promoted |
| **0038** | **abstention threshold T=0.575** | **0.1333** | **0.0299** | **$0, 0 ms** | **free; the only positive result** |
| 0041 | groundedness self-check | 0.2222 | 0.1212 | $0.000055, **4,600 ms** | dominated on both axes |
| 0039 | citation enforcement | **0.8444** | 0.0000 | — | **severe regression** |
| 0040 | span-level citation | **0.8889** | 0.0000 | — | **severe regression**; span support 0.796 |

What the axis established:

1. **Hardening the citation requirement made the system answer questions it cannot
   answer, three times more often.** Both citation prompts drove refusals to zero across
   145 questions. Told that every step needs a citation, the model finds it easier to
   write a cited sentence *describing* a document than to decline — *"1. The provided
   articles cover currency changes for Wix products, not Squarespace."* That is cited,
   formatted, confident, and not an answer. **A citation requirement is not a grounding
   mechanism; it is a formatting requirement, and the model can satisfy it without being
   grounded.**
2. **Both citation prompts destroyed step coverage** — 0.193 → 0.033 and → 0.019, the
   two lowest values in the project. Measured from the other side, this is the same
   finding: the answers stopped being procedures and became descriptions of sources.
3. **Span-level citation fails its own verification once in five.** `span_support`
   0.7964. The technique's whole appeal is that a quote is checkable where an id is not —
   and the check fails 20% of the time, while document-level precision *also* falls
   0.110. A reader who trusts the quotes ends up worse informed than one who had only
   document ids.
4. **The cheapest technique won, and it was free.** A retrieval-score threshold needs no
   model call and no latency, and at T=0.575 it halves false answers at zero cost in
   false refusals. The self-check — the only technique here that costs a second LLM call
   — is beaten on **both** axes simultaneously by a number already sitting in the results
   store.
5. **Three of the four techniques were measured through a broken instrument first.**
   MIS-037 (a stale detector version left the target wrong by 15.6 points), MIS-038 (the
   detector inverted under a prompt that demands numbered steps) and `citation-v2`'s
   blindness to the span form would each have produced a confident false headline. The
   axis's real lesson may be that **a generation metric is calibrated against a prompt,
   and this is the one axis whose purpose is changing the prompt.**

**Axis 7 verdict: one winner, and it is not an LLM technique.** `promoted.yaml` is
unchanged pending the operating-point decision (DEC-068).

## Axis 4 scorecard — query transformation (P2-12, EXP-0031–0034) — CLOSED

`dev` decides (DEC-055); every run is Tier 1, cache-backed and repeated warm so the
paired test's fixed-outcome assumption holds (P2-03). Model: `gpt-oss-20b` (DEC-065).
**Axis spend: $0.0208** across eight runs — four cold, four warm.

| EXP | Technique | `dev` strict R@5 (Δ, CI, p) | multi-doc | new docs / extra query | Verdict |
|---|---|---|---|---|---|
| — | **control** | 0.720 | 0.350 | — | promoted |
| 0032 | HyDE (replaces the query) | 0.735 (+0.015, [−0.050, +0.080], 0.754) | **0.450** (+0.100, p=0.35) | — (one query) | null, best direction |
| 0033 | multi-query, 3 paraphrases | 0.720 (**+0.000**, [−0.050, +0.050], **1.000**) | 0.375 | 16.8 | null; short questions **−0.095, p=0.016** |
| 0031 | decomposition | 0.665 (−0.055, [−0.095, −0.015], **0.0186**) | 0.300 | 40.8 | **significant negative** |
| 0034 | step-back | **0.645** (−0.075, [−0.130, −0.020], **0.0169**) | 0.250 | 34.7 | **significant negative** |

What the axis established:

1. **Adding a second query to the fusion is monotonically harmful, in proportion to how
   different its results are.** Order the three fusing techniques by how many documents
   the extra query contributed that the original did not — 16.8, 34.7, 40.8 — and the
   deltas fall in step: **0.000, −0.075, −0.055**. The one technique that *replaces* the
   query instead of fusing with it (HyDE) is the only one not negative. A second ranking
   does not add evidence to the first; at equal RRF weight it competes with it.
2. **The transforms work. That is the problem.** Every one of them did what it was asked:
   1.27 sub-questions with sensible content, 2.985 faithful paraphrases, a correctly
   more-general question, a corpus-shaped hypothetical passage. Zero fallbacks and zero
   failed calls across 800 calls. This axis is not a story about a model failing to
   follow instructions; it is a story about the instructions being wrong for the corpus.
3. **The gold document answers the whole question, and the corpus has no better match
   for its parts than for the whole.** Decomposition's losses are questions whose gold
   ranked 1 or 2 and fell to 10, 19 or out of 20, because each sub-question's own
   best-matching article outranks the article that answers both. Step-back's are the same
   shape with "general" in place of "part". **These techniques assume documents are
   indexed by sub-fact or by topic; a help centre is indexed by task.**
4. **Dense retrieval on this corpus is far more phrasing-sensitive than "semantic search"
   implies.** Three meaning-preserving paraphrases retrieved **16.8 new documents each**.
   Two separate hypotheses in this axis (H-023, H-025) predicted that rewrites would
   retrieve near-identical rankings, and both were wrong in the same direction. That is a
   fact about the embedding model worth carrying into any later axis.
5. **HyDE is the only untaken lead in the phase.** `multi_doc` 0.350 → 0.450, 7 gained
   against 3 lost, p = 0.35 at n = 40. Not a finding, and the only positive signal that
   slice has produced across six techniques. It cannot be settled on `dev_large`, whose
   multi-document slice has zero rows (MIS-021). See OQ-045.

**Axis 4 verdict: no winner, four techniques, two significant negatives,
`promoted.yaml` unchanged.**

## Axis 6 scorecard — context assembly (P2-13, EXP-0027–0030) — CLOSED

`dev` decides (DEC-055). The top-k sweep is read from a recorded run rather than run
(DEC-061, section above); MMR occupies the reranker slot with `axis: assembly`
(DEC-062); the two Tier 2 techniques skip the judge (DEC-063) and the two LLM-using
ones run on `gpt-oss-20b` (DEC-064). **Axis spend: $0.3441** across five techniques —
$0.0005 MMR, $0.0278 reordering, $0.0306 compression, $0.2852 contextual retrieval
(both runs).

| EXP | Technique | `dev` strict R@5 (Δ, CI, p) | multi-doc | collapse | $/query | Verdict |
|---|---|---|---|---|---|---|
| — | **control** (top_k=5, no reorder) | 0.720 | 0.350 | 1.106 | $0.0000004 | promoted |
| — | top-k sweep (**not a run**, reconstructed) | k=10 → 0.850, k=20 → 0.920, k=50 → 0.985 | 0.625 / 0.825 / 0.975 | 1.13–1.16 | — | input-side only; Tier 2 unanswered (OQ-040) |
| 0027 | MMR, λ sweep 0.3–1.0 | **0.335** at λ=0.3 (−0.385, [−0.460, −0.315], **0.0001**); 0.685 at λ=0.9 (−0.035, **0.039**) | **0.000** at λ=0.3 | **1.000** | $0.0000004 | **negative, monotone** |
| 0028 | lost-in-the-middle reordering | **not reported — permutation, cannot change retrieval** | — | — | $0.00034 | **null** (Tier 2: every metric inside its MDD) |
| 0029 | contextual compression | **not reported — runs after the document walk** | — | — | $0.00031 | **negative** (Tier 2: citation recall −0.088, **p=0.036**) |
| 0030 | contextual retrieval (prefix + re-index) | 0.725 (+0.005, [−0.050, +0.060], **1.000**) | 0.400 (+0.050, p=0.72) | 1.124 | $0.0000008 | **null**; $0.2550 one-off |

What the axis established:

1. **Diversity was never the binding constraint.** The control's collapse ratio is
   1.106 — the context was already ~90% distinct documents — so MMR had almost
   nothing to fix and a great deal to break. It drove collapse to exactly **1.000**
   (perfect document diversity) and halved recall doing it.
2. **MMR is structurally biased against multi-document answers on this corpus**, which
   is the precise opposite of why P2-13 prioritised it. Two gold documents of one
   question are **+0.095 more similar to each other** (0.788) than a gold is to an
   average candidate (0.693) — they are about the same task — so the redundancy term
   penalises the second gold harder than it penalises an irrelevant article.
   `multi_doc` 0.350 → 0.000, 14 lost, 0 gained.
3. **The failure has a measurable cause that generalises.** Candidate-candidate cosine
   spans 0.505–0.832 (mean 0.667) while relevance spans **0.173** within a candidate
   set, so at λ ≤ 0.5 the diversity term out-leverages relevance by more than 2:1 and
   the ordering selects **semantic outliers**. On a single-product help centre, being
   unlike the other candidates is evidence of irrelevance, not of novelty.
4. **Depth is what moves multi-document questions, and it is free to measure but not
   free to use.** 0.350 → 0.625 → 0.825 at k = 5/10/20, against `context_max_tokens`
   binding at about k=14 and an unmeasured effect on answer quality (OQ-040).

5. **Assembly cannot be fixed by reordering what is already there.** Two of the five
   techniques act purely on the assembled context — reordering and compression — and
   neither can change a retrieval metric by construction. Reordering moved **no**
   deterministic generation metric beyond its MDD, and the measured reason is that this
   prompt is **~2,174 tokens**, below the 2,700-token floor of the range Liu et al. 2023
   measured the mid-prompt dip over. Five documents is not a long context.
6. **The generator's willingness to cite a document depends on how much of it it is
   shown.** Compression's loss (citation recall −0.088, p = 0.036) is **not** information
   loss: of the 17 questions that regressed, only 6 lost a gold chunk and **11 kept every
   gold chunk and lost the citation anyway**. That is a property of the generation step
   and would bite any technique that shortens a retrieved document in place.
7. **Contextual retrieval is inert exactly where the corpus says it must be, and
   near-inert where it could have helped.** On the 100 dev questions whose gold article
   fits in one chunk: **0.780 → 0.780, four gained and four lost.** On the multi-chunk
   half: +0.010 (12/11). Dev is **50% multi-chunk against the corpus's 21%**, so the
   technique was measured on a subset 2.4x enriched for the condition it needs.
   The losses are not bad prefixes — a gold with an accurate prefix fell from rank 1 to
   outside the top 5, because **every competitor was prefixed too**. A uniform lift
   cannot re-rank.
8. **Three techniques, two mechanisms, one depth shape.** Contextual retrieval produced
   the reranker profile — better at rank 1 (+0.035), worse at depth (@20 −0.025) — by
   changing what is *indexed* rather than by re-ordering a candidate set. Whatever this
   corpus is doing at rank 1 versus rank 20 is not specific to reranking.

**Axis 6 verdict: no winner, five techniques, `promoted.yaml` unchanged.** One
significant result in the axis and it was negative (compression). The axis's most
transferable output is item 6: a fact about the generator, found while measuring
something else.

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

- **EXP-0024 — `cohere/rerank-v3.5` cross-encoder reranking, 50 candidate documents
  → top 5.** On `dev`, strict recall@5 0.720 → 0.665, Δ −0.055, 95% CI [−0.120,
  +0.010], p = 0.139 (17 gained / 28 lost). Nothing significant at any depth:
  @1 +0.065 (p = 0.082), @10 −0.025 (p = 0.442), **@20 +0.000 (p = 1.000)**,
  nDCG@10 +0.024 (p = 0.279). Cost it would have added: **$0.00117 per query against
  $0.0000004** (~2,900x) and **1,194 ms median latency against 298 ms** (4x); $7.28
  to run the same config on `dev_large`. **Decision: control retained; not promoted;
  the `dev_large` check was not bought (OQ-033).** Two things worth carrying forward:
  the candidate set's recall@20 of 0.920 is the hard ceiling for any reranker over 50
  documents here [**CORRECTED by MIS-029 on 2026-09-23**: the ceiling is recall@**50**
  = **0.985**; EXP-0025 beat 0.920], and the +0.065 at rank 1 says the mechanism does work — it just
  works at a depth this system does not read. A one-document context, or P2-11's
  revisit pass, is where that would matter. Caveat that limits this entry: **one
  reranker was run, so "a cross-encoder does not help here" is not established — only
  that this one did not** (DEC-059, OQ-035).

- **EXP-0025 — `cohere/rerank-4-fast` cross-encoder reranking, 50 candidate documents
  → top 5.** On `dev`, strict recall@5 0.720 → 0.730, Δ +0.010, 95% CI [−0.055,
  +0.080], p = 0.887 (24 gained / 22 lost). Closer to the line elsewhere and still
  over it: @1 +0.070 (p = 0.052), nDCG@10 +0.042 (p = 0.057), multi-document
  0.350 → 0.475 (+0.125, p = 0.180). Cost it would have added: **$0.00224 per query**
  (~5,600x the control) and a p50 of 3,847 ms against 298 ms. **Decision: control
  retained; not promoted.** Two things this run settled that EXP-0024 could not.
  It **beat EXP-0024's reranker at p = 0.039**, so the axis's two nulls are not one
  finding repeated — cross-encoders differ materially on this corpus and a single
  one proves nothing (OQ-035, answered). And it **exceeded the recall@20 that
  EXP-0024 called a hard ceiling**, which forced the real bound to be measured:
  the control's recall@**50** is **0.985** (MIS-029). That last number is the axis's
  most useful output — the gold is in the candidate set 98.5% of the time and the
  best reranker surfaces it in the top five 73% of the time, so what remains at this
  depth is a ranking problem with the documents already in hand, not a retrieval one.

- **EXP-0026 — `qwen/qwen3-reranker-8b` open-weight cross-encoder, 50 candidate
  documents → top 5.** On `dev`, strict recall@5 0.7200 → 0.7200, **Δ exactly zero,
  95% CI [−0.070, +0.070], p = 1.000 — 26 questions gained and 26 lost.** Elsewhere it
  is the mirror of the Cohere pair: the only reranker *worse* at rank 1 (−0.020) and
  the best at depth (@10 +0.030, **@20 0.950**, the highest recall@20 in the project).
  Cost it would have added: **$0.00605 per query** (~15,000x the control, 2.7x the
  dearer Cohere model) and a p50 of 3,172 ms against 298 ms, with 31 transient retries
  against Cohere's 1–2. **Decision: control retained; not promoted; Axis 5 closed with
  no winner.** What it adds to the axis is the demonstration that the three rerankers
  do not share a mechanism — two sharpen the top and lose the middle, this one
  improves the middle and blunts the top — and all three return the same verdict on
  the deciding metric. A null that survives three different behaviours is a stronger
  statement about the corpus than three repetitions of one behaviour would have been.

- **EXP-0027 — MMR diversity-aware assembly, λ sweep 0.3–1.0 over 50 candidate
  documents.** On `dev`, strict recall@5 went 0.720 → 0.685 / 0.570 / 0.360 / **0.335**
  as λ fell from 0.9 to 0.3 — monotone, and every step worse. λ=0.3: Δ −0.385, 95% CI
  [−0.460, −0.315], p = 0.0001 (3 gained / 80 lost). λ=0.9, the gentlest setting
  tested: Δ −0.035, p = 0.039, already significant and negative. **multi-document
  0.350 → 0.000** (14 lost, 0 gained, p = 0.0002) — the slice the technique was
  prioritised for. Cost it would have added: **nothing.** MMR reads the cached index,
  makes no network call and builds no index; the entire five-run sweep cost $0.0005.
  **Decision: control retained; not promoted.** The interesting part is that the
  failure is explained rather than observed: two golds of one question are +0.095
  *more* similar to each other than to an average candidate, so the redundancy term
  demotes the second gold hardest; and candidate-candidate similarity has more than
  twice the dynamic range of relevance, so below λ≈0.7 the objective selects semantic
  outliers. **A diversity technique needs the gold documents to be spread out in
  embedding space. On a single-product help centre they are clustered, and MMR
  inverts.** The identity run at λ=1.0 reproduces the control exactly, so this is the
  technique and not the harness.

- **EXP-0028 — lost-in-the-middle reordering, five documents per prompt.** Tier 2 on
  `dev`. **No deterministic generation metric moved beyond its noise floor**: citation
  precision Δ −0.021 (p = 0.558, MDD 0.080), citation recall Δ −0.005 (**p = 1.000**,
  MDD 0.040), step coverage Δ −0.008 (p = 0.792, MDD 0.097), refusal Δ −0.010
  (p = 1.000, MDD 0.031). Nothing is significant on any slice; the lowest p value in the
  whole per-slice breakdown is 0.106. No retrieval delta is reported, and none *could*
  be: the reordering is a permutation, asserted in `tests/test_assembly_p2_13.py`.
  Cost it would have added: **nothing per query** — assembly ordering is a list
  operation, and the run itself was $0.0278.
  **Decision: control retained; not promoted.**
  Two things make this more than a shrug. The null is **explained**: the assembled
  context averages 1,712 words ≈ **2,174 tokens**, and Liu et al. 2023 measured the
  mid-prompt dip across roughly **2,700–21,000** tokens with 10–30 documents. Five
  documents in ~2,174 tokens is below the shortest condition in the work the technique
  comes from, so the mechanism had little room to act. And the null is **not
  inaction**: 15 of 100 questions changed their citations, and on **13 of those the
  retrieved documents and their ranking were byte-identical** — only the position in
  the prompt differed. Six improved, seven worsened. One question answered the
  *opposite* of the gold article's claim purely because a different document led the
  prompt. The technique moves this system's individual answers around measurably while
  moving none of its metrics, which is a useful thing to know about the generator's
  stability and a poor reason to adopt the reordering.

- **EXP-0029 — contextual compression, one extractive LLM call per retrieved chunk.**
  Tier 2 on `dev`. The only technique in Axis 6 that moved a metric, and it moved it the
  wrong way: **citation recall 0.5978 → 0.5217, Δ −0.0883, 95% CI [−0.168, −0.010],
  p = 0.0358, against an MDD of 0.040 — significant and negative.** Citation precision
  −0.051 (p = 0.21) and step coverage +0.019 (p = 0.73) stayed inside their floors, and
  refusal did not move at all (Δ exactly 0.0000, p = 1.000). What it bought: the
  generator's prompt fell from **1,712 to 912 words (−46.7%)** and from 5.00 to 3.13
  documents. Cost it would have added: **$0.0224 per 100 questions**, one call per
  retrieved chunk, on top of a 4x slower p50.
  **Decision: control retained; not promoted.** For an assistant whose job is to point
  the user at the right help article, 0.088 of citation recall is the wrong thing to
  trade for a shorter prompt.
  The diagnosis is worth more than the verdict. The compressor is **good at its stated
  task** — it dropped 43.9% of non-gold chunks against only 8.7% of gold ones, a
  five-fold discrimination ratio measured against the labels. But of the 17 questions
  whose citation recall fell, only 6 had a gold chunk dropped; **11 kept every gold chunk
  and lost the citation anyway.** The relevant sentences were still in the prompt.
  Shortening the document around them made the generator less likely to cite it, and
  `cited_nothing` rose from 0.057 to 0.090 on the same retrieved documents. **The failure
  is not information loss, it is that this generator's willingness to cite a document
  depends on how much of that document it is shown.** That is a fact about the
  generation step, not about compression, and it would apply to any technique that
  shortens a retrieved document in place.

- **EXP-0030 — Anthropic-style contextual retrieval, one LLM call per chunk across the
  corpus.** On `dev`, strict recall@5 0.7200 → 0.7250, **Δ +0.0050, 95% CI
  [−0.050, +0.060], p = 1.000 — 16 questions gained, 15 lost.** The warm-cache repeat
  gave +0.0100 at p = 0.857. Cost it would have added: **$0.2550 once** (8,218 calls,
  21 minutes, plus a $0.0385 re-embed) and nothing per query.
  **Decision: control retained; not promoted.**
  This is the one negative result in the project with a mechanism measured on **both**
  sides of the question. It works where it should: gold documents moved from outside the
  top 5 to rank 1 when the prefix supplied vocabulary the question used and the chunk
  lacked — *"do I have to give my login to a website designer"* found an article whose
  prefix named "collaborators" and "Roles & Permissions", words the question never used.
  And it is inert where it should be: on the 100 dev questions whose gold article fits in
  a single chunk, the result is **0.780 → 0.780, four gained and four lost**, because the
  prefix there restates text the chunk already contains in full.
  What kills it is the half in between. The losses are **not** bad prefixes — a gold
  article with an accurate, well-written prefix fell from rank 1 to outside the top 5.
  **Every competing document got a prefix too, so the lift is near-uniform across the
  index and relative ordering barely moves.** A technique that improves every candidate
  equally cannot re-rank them. Recall@20 actually fell 0.025, which a purely additive
  "more findable" account would not predict.
  The scale point belongs with the number: **$0.25 is affordable at 6,221 articles and
  would be ~$250 per index build at 6 million**, repeated on every re-chunk, prompt
  revision and model change. Bounded here, a standing budget line there.

- **EXP-0031 — query decomposition, sub-questions retrieved separately and RRF fused.**
  On `dev`, strict recall@5 0.7200 → 0.6650, **Δ −0.0550, 95% CI [−0.095, −0.015],
  p = 0.0186 — significant and negative**, 4 gained against 15 lost. Single-document
  recall −0.056 (p = 0.035); long questions −0.113 (p = 0.041). Cost it would have
  added: **$0.00009 per run warm, $0.0023 cold** — the cheapest technique in the phase,
  and still not worth it.
  **Decision: control retained; not promoted.**
  The diagnosis is unusually clean because the technique supplies its own control. Only
  **50 of 200** questions were split; the other 150 came back as a single line, 145 of
  them verbatim, and those **reproduce the control exactly** (0.713 → 0.707). All of the
  damage is in the 50: **0.740 → 0.540**, 13 lost against 3 gained. The technique is not
  diluting everything — it is destroying precisely the questions it acts on, and those
  questions were *easier* than average to begin with.
  Why it fails is the transferable part. Each extra sub-query retrieved **40.8 documents
  no earlier sub-query had**, so the decomposition is working exactly as designed. That
  is the problem. *"How can I add a personalized name to my automated emails? I was
  advised to use dynamic values"* splits into two good questions, each of which has its
  own best-matching article — and neither is the gold, which answers both. RRF reads
  ranks, so a document at rank 1 of one list beats a document at rank 3 of two lists.
  **Decomposition assumes the corpus is organised by sub-fact. A help centre is organised
  by task, and a user's multi-part question is usually one task.** Splitting it asks the
  index for something it does not contain.

- **EXP-0032 / 0033 / 0034 — HyDE, multi-query expansion and step-back prompting.** On
  `dev`: HyDE **+0.0150** (p = 0.754), multi-query **exactly 0.0000** (p = 1.000),
  step-back **−0.0750** (**p = 0.0169**, significant). Cost they would have added:
  **$0.00014 to $0.00035 per run** warm — the cheapest experiments in the project.
  **Decision: control retained; none promoted. Axis 4 closes with no winner.**
  Two slice results are worth more than the headlines. HyDE moved `gold_docs:multi`
  **0.350 → 0.450**, seven questions gained against three lost — the largest
  multi-document movement anything in this project has produced, and **not significant**
  at n = 40 (p = 0.35). It is the only positive signal on that slice after MMR, three
  rerankers, contextual retrieval and decomposition all failed to move it (OQ-045). And
  multi-query lost `q_len:short` by **0.0946 at p = 0.016 with 7 lost and 0 gained** —
  the only slice in the axis with an empty side — because a short question is already
  close to a keyword query and paraphrasing pulls the fused ranking off the literal
  match.
  Step-back's defect is measured rather than inferred: **46 of 200 step-back questions
  (23%) named a Wix product the original never mentioned**, the model's default guess
  being "Bookings". That is a real and large failure of the (prompt, corpus) pair — and
  it explains only **6 of the 25 losses**. The rest is the axis's common failure, below.

- **P2-11 — the chunking revisit pass, priced at $1.4043 and deliberately not run
  (DEC-066).** Three configs (parent-document, semantic, structure-aware chunking, each
  under `cohere/rerank-4-fast` at 50 candidate documents), indexes already cached so
  nothing re-embedded, `--estimate-only` $0.4681 each, gate $2.00. **What was tried: the
  premise.** P2-11 tests whether a *strong* reranker erases chunking differences; the
  strongest of the three cross-encoders measured in Axis 5 moved `dev` strict recall@5 by
  **+0.010, 95% CI [−0.055, +0.080], p = 0.887**. There is no strong reranker here for
  chunking differences to survive. **Decision: priced, declined, configs committed unrun
  so the estimate remains checkable.** The composition verdict the story demands is
  recorded as *neither composed nor cancelled — there were no winners to compose*, and
  that is itself the finding: the classic error of assuming one-factor winners stack was
  unavailable to us, because after six axes not one factor has won.

- **EXP-0039 / EXP-0040 — citation enforcement and span-level citation.** On the full
  `unanswerable` set, false-answer rate **0.2667 → 0.8444** and **→ 0.8889**; on `dev`,
  step coverage **0.193 → 0.033** and **→ 0.019**; refusals **zero out of 145 questions**
  under both. Cost they would have added: nothing per query — these are prompt changes.
  **Decision: control retained; neither promoted.**
  The mechanism is the finding and it generalises past this corpus. Told that every step
  must carry a citation, the model does not refuse more carefully — it writes a numbered,
  cited sentence *about* a document and stops answering the question. **A citation
  requirement is a formatting requirement, and a model can satisfy it without being
  grounded.** Span-level citation adds a verifiable artifact and then fails the
  verification: **20% of quoted spans do not appear in the document they are attributed
  to**, while document-level citation precision falls 0.110 as well.
- **EXP-0041 — groundedness self-check.** False-answer **0.2667 → 0.2222** at a
  false-refusal cost of **0.0299 → 0.1212**, plus **4,600 ms per answered question** and
  $0.0055 per 100 questions. Of 12 dev answers it rejected, **6 had the gold document in
  context** — it rejects about as much good work as bad. **Decision: not promoted, and
  the reason is unusually clean: it is dominated on both axes of its own trade-off by
  EXP-0038's free retrieval-score threshold** (0.1333 false answers at 0.0299 false
  refusals, no call, no latency). Zero unparseable verdicts and zero failed calls across
  both splits, so this is a judgment failure and not a plumbing one.

- **EXP-0042 to EXP-0045 — the P2-16 combination set.** Four combinations of the
  individually positive-but-null techniques. Best: **0.7500, the highest strict recall@5
  in the project, at p = 0.444.** Worst: 0.7100, below the control. Cost they would have
  added: **$0.0022918 per query, forever**, for the best one; the other three are free.
  **Decision: none promoted.**
  The finding is the interaction, not the scores. On the multi-document slice HyDE and
  `rerank-4-fast` each rescue 7 questions the control misses — and **4 of those are the
  same questions**, so the most an ideal combination could reach is 0.600 rather than the
  0.600+ their separate deltas imply. The measured combination reaches **0.450**: it
  captures 8 of the 10 available and **loses 6 questions an arm had already solved.**
  Stacking is sub-additive *and* lossy. Adding a third component takes the multi-doc
  slice back to **exactly the control's 0.350**, having passed through three techniques
  that each raised it alone.

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
