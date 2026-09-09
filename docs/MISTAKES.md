# Mistakes

Read the preflight checklist before starting any experiment. This file is a
checklist, not an archive. Append-only; do not soften entries.

## Preflight checklist

Derived from the prevention rules below. Run through it and say in chat that you did.

1. **Verify dataset assumptions against the data before implementing a rule that
   depends on them.** Count the thing. Do not implement from a description. (MIS-001)
2. Before writing any comparison, confirm both runs share: `corpus_hash`,
   `normalization_version`, `split_hash`, `doc_pooling`, and judge model.
3. Never quote a `dev_large` number as a headline result — synthetic questions were
   generated from their gold article and lexical overlap is inflated.
4. Never build a refusal case by deleting articles from the index. It changes
   `corpus_hash` and invalidates every cross-run comparison. (DEC-007)
5. Opening `test` requires `--open-test` and a row in the DECISIONS.md openings log.
6. **Before building a metric, count how many questions it can apply to**, and design
   the not-applicable case before the happy path. A metric averaged over questions it
   cannot score reads as a system failure. (MIS-002)
7. **When handing a ranking to an external library, hand it the order, not the
   scores.** Then assert the library agrees with the ranking recorded in the
   artifacts, on real data. (MIS-003)
8. Never report a `toy_overlap` number as a result. It is a harness smoke test.
9. **Never upgrade Ragas without starting a new comparison family.** It revises
   metric prompts between releases; `ragas_version` and `metric_prompt_versions` are
   recorded and checked by `rag diff` for exactly this reason. (MIS-004)
10. **The current judge is a plumbing placeholder (DEC-018).** Faithfulness, answer
   relevance and answer correctness have no trustworthy values until a real judge is
   chosen. Do not put them in EXPERIMENTS.md or NARRATIVE.md.

---

## MIS-001 — Implemented a normalization rule from a description, not from the data
- **Date:** 2026-09-09
- **Severity:** Low — caught before any run; no results affected.
- **What happened:** The Phase 0 handover states that article text "contains many
  markdown links and dashboard deep-links", and P0-02 is framed around deciding
  what to do with them. Work started on that premise.
- **How it was caught:** Counting link patterns across the frozen corpus before
  finalizing the rule: **2 of 6,221 documents** contain any markdown link, 3 links
  in total. The links are in the `html_content` field and in the gold *answers* —
  not in the `contents` field we index.
- **Root cause:** A plausible premise in a handover document was taken as a fact
  about the data.
- **Impact:** None to results. Had it gone unchecked, `norm-v1` would have been
  presented as a meaningful preprocessing decision when it is a near-no-op, and a
  later reader could have mistaken it for an explanation of retrieval behaviour.
- **Fix applied:** DEC-002 records the measured counts and states plainly that the
  rule is close to a no-op on this corpus.
- **Prevention rule:** Verify dataset assumptions against the data before
  implementing a rule that depends on them. Count the thing.
- **Added to preflight:** yes

## MIS-002 — Assumed WixQA answers are procedural, from the handover's description
- **Date:** 2026-09-09
- **Severity:** Low — caught during implementation; no results affected.
- **What happened:** P0-07 introduces step coverage on the premise that "WixQA
  answers are procedural markdown". Step coverage was designed as a metric to report
  over every question.
- **How it was caught:** Counting numbered lists in the `dev` reference answers
  before writing the metric: **54 of 200** contain one. The other 146 are prose.
  Separately, only 2 of 6,221 corpus articles contain a markdown link (MIS-001), and
  every gold document in `dev` is `article_type: article` — the `feature_request`
  and `known_issue` slices required by P0-08 are empty on the split we iterate on,
  and `test` has 10 `feature_request` questions and no `known_issue` ones.
- **Root cause:** Same as MIS-001: a handover description treated as a fact about
  the data. Three premises checked, three wrong.
- **Impact:** None to results. Had step coverage been averaged over all questions,
  146 prose answers would have contributed zeros and the metric would have read as
  "the system drops most steps" when the reference had no steps to drop.
- **Fix applied:** Step coverage returns `None` outside the procedural subset and
  the slice report carries `step_coverage__n` (DEC-015). Empty slices are omitted
  from the report rather than shown as zero.
- **Prevention rule:** Before building a metric, count how many questions it can
  actually apply to, and design the not-applicable case before the happy path.
- **Added to preflight:** yes

## MIS-003 — Metrics scored a different ranking than the one the system returned
- **Date:** 2026-09-09
- **Severity:** High — would have silently corrupted every retrieval number.
- **What happened:** `run_from_results` handed `ranx` the raw pooled document scores.
  Pooled scores tie constantly — with `max` pooling, every document whose best chunk
  scored the same value ties exactly. Our pooling rule breaks those ties on the rank
  of the document's best chunk; `ranx` re-sorts by score and breaks ties by its own
  rule. The metric therefore scored a different ordering than the one the system
  returns and the one written to `run_questions`.
- **How it was caught:** Reading a `rag diff` line that made no sense — a question
  with one gold document showing that document at stored rank 4 while scoring 0.0 on
  `strict_recall@5`.
- **Root cause:** Treating "scores" as the interface to the metrics library when the
  system's actual output is an *ordering*. The tie-break rule was documented in one
  place and silently overridden in another.
- **Impact:** None to recorded results — caught before any experiment. On the smoke
  run it moved `strict_recall@5` from 0.160 to 0.165 and left an unknown number of
  per-question values misattributed.
- **Fix applied:** `run_from_results` emits strictly decreasing rank-derived scores
  by default (DEC-013). Verified: 0 of 200 questions now disagree between the stored
  ranking and the metric. Regression test in `tests/test_runner.py`.
- **Prevention rule:** When handing a ranking to an external library, hand it the
  order, not the scores that produced the order. Then assert the library's result
  agrees with the ranking recorded in the artifacts, on real data, not just a fixture.
- **Added to preflight:** yes

## MIS-004 — Ragas's dependency spec resolves to a version its own code cannot import
- **Date:** 2026-09-09
- **Severity:** Medium — blocked P0-07 until pinned; no results affected.
- **What happened:** Installing `ragas` (tried 0.2.15, then 0.4.3, the newest) gave a
  hard `ModuleNotFoundError: No module named 'langchain_community.chat_models.vertexai'`
  on `import ragas`. Ragas imports that module; `langchain-community` 0.4.x removed
  it; Ragas's dependency spec does not exclude 0.4.x, so the resolver installed a
  combination that cannot import.
- **How it was caught:** The first `import ragas` failed, before any code was written
  against it.
- **Root cause:** A dependency's own version constraints were trusted to produce a
  working install.
- **Impact:** None to results. Roughly half an hour of version bisection.
- **Fix applied:** Pinned `ragas==0.4.3` exactly and added the ceiling Ragas should
  have had: `langchain-community<0.4`. Both are in `pyproject.toml` with the reason
  written next to them.
- **Prevention rule:** Pin judged-metric dependencies exactly and record the version
  on every run. Ragas revises metric prompts between releases, so an upgrade can move
  every historical judged score with no config change — record
  `metric_prompt_versions` fingerprints too, and let `rag diff` refuse the comparison.
  Do not trust a library's dependency spec to yield a working install; assert the
  import.
- **Added to preflight:** yes
- **Note:** `ragas.metrics` is already deprecated for `ragas.metrics.collections`
  "removed in v1.0". This API is moving, and the pin is what stands between that and
  the results ledger.
