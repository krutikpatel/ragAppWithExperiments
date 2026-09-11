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
10. **To claim a capability is absent, probe the endpoint that would provide it and
    show the failure.** A missing entry in a neighbouring listing is not evidence, and
    a wrong "can't" is costlier than a wrong "can" because nobody re-tests it. (MIS-005)
11. **Assert that a provider response contains what you asked for, at the point of
    the call.** An empty completion is a broken call, not a bad answer, and a metric
    will happily score nothing as zero. Check whether a new model spends completion
    tokens on reasoning before setting its budget. (MIS-006)
12. **Never delete the results store to get past a schema change.** Migrate it, or
    use a different database file. `rag diff` needs both runs to exist. (MIS-007)
13. **A provider pin is a purchasing decision, not a tuning knob.** Cost it before
    committing it, and put it to Krutik. When optimising one dimension, check what it
    spends in the others before recording the change as a win. (MIS-008)
14. **The current judge is a plumbing placeholder (DEC-018).** Faithfulness, answer
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

## MIS-005 — Concluded a capability did not exist after checking one endpoint
- **Date:** 2026-09-10
- **Severity:** Medium — wrote a false claim into DECISIONS.md, CLAUDE.md and the
  README, and needlessly scoped one of P0-07's three judged metrics out of Phase 0.
- **What happened:** To find out whether OpenRouter could supply the embedding model
  Ragas's `AnswerRelevancy` needs, I fetched `GET /api/v1/models`, filtered ids for
  "embed", got nothing, and recorded in DEC-022 that "OpenRouter serves no embedding
  models". I then designed around the gap: `_embeddings()` raised
  `NotImplementedError`, and the claim was repeated in CLAUDE.md's tech-stack table,
  the models table and the README.
- **How it was caught:** Krutik said it was wrong and named the actual endpoint.
  `GET /api/v1/embeddings/models` returns 33 models.
- **Root cause:** Checked an adjacent listing rather than the documented endpoint for
  the capability, then treated one negative result as proof of absence. The
  `/models` endpoint answers "which chat models are there", not "does this API do
  embeddings" — I asked the wrong question and trusted the answer.
- **Impact:** No results affected; nothing had been run. A false constraint was
  written into three files and one metric was wrongly recorded as unavailable.
- **Fix applied:** DEC-026 corrects DEC-022 (original kept, per the append-only rule).
  `RagasJudge._embeddings()` is implemented against OpenRouter's embeddings API.
  CLAUDE.md and the README are corrected.
- **Prevention rule:** To establish that a capability is absent, probe the endpoint
  that *would* provide it and show the failure. A missing entry in a neighbouring
  listing is not evidence. And when a negative finding is about to become a recorded
  constraint that removes scope, say so out loud before writing it down — a wrong
  "can't" is more expensive than a wrong "can", because nobody re-tests it.
- **Added to preflight:** yes

## MIS-006 — A reasoning model returned no answer, and the harness crashed instead of saying so
- **Date:** 2026-09-10
- **Severity:** Medium — caught by the first Tier 2 smoke run; no results affected.
- **What happened:** The first Tier 2 run died with
  `TypeError: expected string or bytes-like object, got 'NoneType'` inside
  `extract_steps`. The cause was upstream: `openai/gpt-5-nano` had returned
  `content: None`. `max_tokens` was 800, and gpt-5-nano is a reasoning model whose
  reasoning tokens count against that budget — all 768 completion tokens went to
  reasoning and none to an answer (`finish_reason=length`). The generator handed the
  `None` straight through as if it were an answer.
- **How it was caught:** The crash. Which was luck: `is_refusal` already tolerated
  `None`, and `citation_scores([])` returns `None` precision by design, so had
  `extract_steps` been defensive the run would have **completed** and recorded five
  empty answers as five genuinely bad answers — zero citations, zero step coverage,
  low faithfulness. A silent infrastructure failure dressed as a quality finding.
- **Root cause:** Two mistakes. A token budget set from an estimate that predates
  reasoning models, and no assertion that a generated answer contains anything. The
  second is the real one: the pipeline trusted a provider response without checking it.
- **Impact:** No results affected. Three failed smoke runs, each on a token budget
  rather than on logic:
  1. generator `max_tokens=800` -> `content: None` -> crash;
  2. Ragas `agenerate()` refused a *synchronous* OpenAI client (it detects the client
     kind rather than adapting, so `AsyncOpenAI` is required for `ascore`);
  3. judge hit `IncompleteOutputException` — `instructor` raises when structured
     output is cut off at `finish_reason=length`, and faithfulness emits one statement
     per claim, so 4096 tokens are needed to hold a decomposed answer.
- **Fix applied:** `EmptyGenerationError` — the generator now raises when content is
  empty, naming `finish_reason`, `completion_tokens`, `reasoning_tokens` and
  `max_tokens`, so the message diagnoses itself. Budgets and reasoning effort set per
  DEC-028. `extract_steps` also tolerates `None` as a belt-and-braces measure, but the
  loud failure is the actual fix. `reasoning_tokens` is now carried on every generated
  answer.
- **Prevention rule:** Assert that a provider response contains what you asked for,
  at the point of the call. An empty completion is a broken call, not a bad answer —
  and never make a metric the thing that discovers it, because a metric will happily
  score nothing as zero. When adding a model, check whether it spends completion
  tokens on reasoning before budgeting.
- **Added to preflight:** yes

## MIS-007 — Deleted the results store between two runs I wanted to compare
> **UPDATE 2026-09-10** — "Fix applied: none in code" is no longer true. An additive
> schema migration landed with DEC-032, so a schema change no longer tempts anyone to
> delete the store.
- **Date:** 2026-09-10
- **Severity:** Low — cost one comparison; no recorded results lost.
- **What happened:** I ran the Tier 2 smoke test with the `deepseek/deepseek-v3.2`
  judge, then swapped to `openai/gpt-oss-120b` (DEC-030) and re-ran it — prefixing each
  run with `rm -f results/runs.sqlite` to start clean. The judged aggregates differed
  substantially between the two runs (answer correctness 0.44 then 0.10 on the same 5
  questions), which is the most interesting thing either run produced.
- **How it was caught:** Wanting to explain the gap, and finding the earlier
  per-question rows gone.
- **Root cause:** `rm` used as a convenience to avoid schema-migration friction, on
  the store whose entire purpose is to make two runs comparable. `rag diff` was built
  for exactly this question and I destroyed its input.
- **Impact:** The 0.44 -> 0.10 gap cannot be attributed. It could be the judge change,
  or the generator producing different answers between runs, or both. Two placeholder
  runs of 5 questions each, so nothing of value was measured — but the comparison was
  available and is now not.
- **Fix applied:** None in code. The rule below is the fix.
- **Prevention rule:** Never delete the results store to get past a schema change.
  Migrate it, or point the run at a different database file. A run that exists is
  evidence; the ledger is append-only for the same reason the markdown journals are.
- **Added to preflight:** yes

## MIS-008 — Pinned the two most expensive providers without checking prices
- **Date:** 2026-09-10
- **Severity:** Low in money, medium in process — no results affected.
- **What happened:** Fixing the Tier 2 latency problem (DEC-032), I pinned judge calls
  to Cerebras and Groq purely on measured speed. I never looked at what they cost.
  They are the **most expensive and fifth-most expensive** of the 22 providers serving
  `openai/gpt-oss-120b` — Cerebras at $0.350/Mtok input against $0.030 at the cheapest,
  a 12x spread. The shipped configuration costs ~$0.48 per 100-question Tier 2 run
  where DEC-030 recorded a price implying cents.
- **How it was caught:** Krutik asked why Groq and Cerebras were appearing at all, and
  whether he was paying for them. Not by any check of mine.
- **Root cause:** I treated provider choice as a performance setting rather than a
  purchasing decision. Having just measured a 37x speed spread, I assumed the pricing
  was flat because the *model-level* price is a single number — the per-provider
  prices live behind a different endpoint I did not open. That is MIS-005 again in a
  new costume: a conclusion drawn from the listing I happened to be looking at.
- **Impact:** No results affected and the absolute amounts are small. But the
  recorded price in DEC-030 was wrong for the shipped config, and Krutik was spending
  ~6x what the documentation said without having been asked.
- **Fix applied:** DEC-034 records the real per-provider table and the ~$0.48/run
  figure, and the choice was put to Krutik, who kept the fast pair. DEC-030 carries a
  correction pointer.
- **Prevention rule:** A provider pin is a purchasing decision, not a tuning knob.
  Cost it before committing it, and put it to Krutik like any other model choice —
  cost is one of the tradeoffs he is owed. More generally: when optimising one
  dimension, check what it spends in the others before recording the change as a win.
- **Added to preflight:** yes

## MIS-009 — Risk on record: the test split is small enough to overfit by iteration
- **Date:** 2026-09-11 (seeded by P0-12, before any opening)
- **Severity:** Not yet a mistake. Recorded here so that when it happens it is a
  failure of a known rule rather than a surprise.
- **The risk, as P0-12 states it:** *"Risk: 400 gold pairs, dozens of experiments.
  Iterating on test numbers will produce a system tuned to the test set and
  disappointing real performance. Test split opens at phase boundaries only."*
- **Why it is real here:** `test` is 200 questions, `dev` is 200. Every retrieval
  technique in Phases 1-2 will be tuned on `dev`, and each tuning step is a chance to
  fit `dev`'s particular questions. `test` is the only number that says whether the
  gains transfer — and it says so exactly once per opening. Each opening after the
  first is a little less informative, because the previous number is already known.
- **What is enforced:** `--open-test` plus a `--reason`, or the runner refuses. Every
  opening is appended automatically to the log at the end of `docs/DECISIONS.md` with
  date, config hash, git SHA and reason, and the runner prints the count of previous
  openings before it proceeds.
- **Prevention rule:** Open `test` at phase boundaries only, on a configuration that
  was chosen on `dev` before `test` was looked at. Never change a configuration in
  response to a `test` number.
- **Added to preflight:** yes (item 5 already covers the mechanics; this is the why)
