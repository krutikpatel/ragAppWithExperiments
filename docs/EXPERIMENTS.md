# Experiments

Index of every run, newest last. Every number here mirrors a row in the results store
(`results/runs.sqlite`) under a real `run_id`. No row is written before its run has
produced one.

| Exp | Run ID | Date | Axis | Change vs baseline | Strict R@5 | Loose R@5 | nDCG@10 | MRR (1-doc) | Cit. prec. | p95 ms | $/query | Status | Detail |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0001 | `run_20260911_051054_ef08` | 2026-09-11 | baseline | BM25, fixed-512/0, top-5, Tier 1, dev | **0.405** | 0.505 | 0.384 | 0.332 (n=160) | — | 35 | 0.0000 | VALID | [→](experiments/EXP-0001.md) |
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
- Two earlier runs of EXP-0001's config, `run_20260911_051026_e28c` and
  `run_20260911_051033_e88c`, were made on a dirty tree as a determinism check. They
  are identical to the canonical run and are not experiments.
