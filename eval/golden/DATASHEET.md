# Golden CI slice — `golden_v1`

The fixed question set the Phase 3 quality gate runs on (P3-03, DEC-074). **Zero manual
labelling**: every question, reference answer and gold article id is WixQA's own.

| | |
|---|---|
| File | `eval/golden/golden_v1.jsonl` — one JSON object per question |
| Content hash | `sha256:baa621b13c481e953b60b6ce07782bbbe4857c321b9f37db9661b8d23384639a` (canonical records, `rag.hashing`) |
| Selection | `rag data golden` (`rag/dataset/golden.py`), seed **20260928**. `rag data golden --check` re-derives it and fails on any difference |
| Sources | `dev` split (`sha256:eeb8d2d3…c015`, WixQA ExpertWritten + Simulated) and the authored `unanswerable` set (`data/authored/unanswerable_seed.yaml`) |
| Never from | `test` (sealed; spent by P2-18) or `dev_large` (synthetic) |
| Corpus | `sha256:74694ad4…0ec0`, `norm-v1`, KB snapshot 2024-12-02 |

## Fields
`question_id`, `question`, `reference_answer` (WixQA's; empty for unanswerable),
`article_ids` (WixQA gold, document level; empty for unanswerable), `stratum`,
`source_config` (`expertwritten` / `simulated` / `unanswerable`), `n_gold_docs`, `reason`
(unanswerable only).

## Strata
Exclusive, assigned in this order:

| Stratum | n | Rule |
|---|---|---|
| `answered_without_gold` | 27 | **All** questions that the Phase 2 closing dev Tier 2 run (`run_20260913_205058_dc03`) answered without any gold document in the generator's context. "Answered" = not a refusal under `refusal-lexical-v3` |
| `multi_doc` | 20 | ≥ 2 gold documents, not in the first stratum; seeded sample of 24 |
| `single_doc` | 33 | 1 gold document, not in the first stratum; seeded sample of 149 |
| `unanswerable` | 15 | 5 per `reason` (`out-of-scope-platform`, `post-snapshot`, `underspecified`), seeded |

Source mix of the 80 answerable questions: 45 ExpertWritten, 35 Simulated.

**The slice deliberately over-samples the risk group.** 27 of 80 answerable questions
(34%) are ones the system answered without its evidence, against about 27% of the
Phase 2 subsample. So **absolute scores on this slice are not comparable to `dev`
scores.** The gate compares a run to a baseline on the same slice, so this does not
matter for gating. Do not quote a golden-slice number as a system-level number.

The first stratum is the only one defined by an outcome. It is taken whole, because the
story defines it that way and it is the group the faithfulness eval exists for. Nothing
else was chosen by looking at results.

## How the labels were verified (by WixQA, not here)
- **ExpertWritten:** answers drafted by Wix support experts and triple-reviewed, with
  majority vote.
- **Simulated:** automatic filtering, three-expert review, and replay.
- All are grounded in the frozen KB snapshot (2024-12-02).
- The unanswerable questions are this project's own authored set (DEC-007, P1-08): added
  questions, never deleted articles.

## Known limitation
WixQA has near-duplicate help articles, so **document-level gold may be incomplete**: a
non-gold article can support an equally correct answer. Strict recall counts that as a
miss. Not fixed here; reported as a limitation.

## Overlap with `dev`
The slice comes from `dev`, which is also the split every Phase 2 experiment ran on.
That overlap is accepted (DEC-074): Phase 3 tunes nothing on it. If a later phase tunes
on `dev`, it must hold these 95 questions out or build a new slice.

## Versioning
Any change to membership, fields or sizes is `golden_v2`, a DEC entry and a baseline
recompute (P3-11). v1 is never edited.
