# Experiments

Index of every run, newest last. Every number here mirrors a row in the results store
(`results/runs.sqlite`) under a real `run_id`. No row is written before its run has
produced one.

| Exp | Run ID | Date | Axis | Change vs baseline | Strict R@5 | Loose R@5 | nDCG@10 | MRR (1-doc) | Cit. prec. | p95 ms | $/query | Status | Detail |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0001 | `run_20260911_051054_ef08` | 2026-09-11 | baseline | BM25, fixed-512/0, top-5, Tier 1, dev | **0.405** | 0.505 | 0.384 | 0.332 (n=160) | 0.388 (T2, n=88) | 35 | 0.0000 | VALID | [→](experiments/EXP-0001.md) |
| EXP-0002 | `run_20260911_051322_3bcb` | 2026-09-11 | chunking | whole documents (paper's retrieval config) | 0.410 | 0.500 | 0.378 | 0.329 (n=160) | — | 21 | 0.0000 | VALID | [→](experiments/EXP-0002.md) |

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
  on the fixed 100-question subsample. Two VOID Tier 2 attempts precede it (MIS-010,
  MIS-011) and stay in the store.
- Two earlier runs of EXP-0001's config, `run_20260911_051026_e28c` and
  `run_20260911_051033_e88c`, were made on a dirty tree as a determinism check. They
  are identical to the canonical run and are not experiments.

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
