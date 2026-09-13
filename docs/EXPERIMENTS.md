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
| EXP-0007 | `run_20260913_060733_6a9b` | 2026-09-13 | control | **dense control on `unanswerable`** (45 q, P1-07 run 3): refusal rate 0.578 lexical / 0.733 hand-read; **false-answer rate 0.422 / 0.267**; 10 of 15 underspecified answered with citations; judge skipped (DEC-044) | — | — | — | — | — | 3679 | 0.0091 (est., pre-skip; ≈0.0004 actual) | VALID | [→](experiments/EXP-0007.md) |

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
- **EXP-0007 has no retrieval columns** (no gold, DEC-009) and reports the refusal rate
  twice: the recorded lexical detector and a hand count of all 45 answers, which
  disagree by 7 questions (OQ-008).
- **Dense spread is not zero.** Hosted query embeddings vary call to call; three runs
  of EXP-0005 ranged 0.005 on strict recall@5 (OQ-023). Any dense delta at or under
  one question is within that.

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
