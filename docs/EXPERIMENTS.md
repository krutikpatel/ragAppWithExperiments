# Experiments

Index of every run, newest last. Every number here mirrors a `metrics.json` under
a real `RUN_ID`. No row is written before its run has produced artifacts.

| Run ID | Date | Axis | Change vs baseline | Strict R@5 | Loose R@5 | nDCG@10 | MRR (1-doc) | p95 ms | $/query | Status | Detail |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _(none yet)_ | — | — | — | — | — | — | — | — | — | — | — |

**No experiments have been run.** The harness through P0-05 builds and scores
inputs; it does not yet retrieve. The first row will be the P0-13 baseline
(BM25, fixed 512-token chunks, top-5, no reranker, Tier 1, on `dev`), which must be
recorded before any technique work begins.

Status values: `RUNNING`, `VALID`, `VOID`, `SUPERSEDED`.
