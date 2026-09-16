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
14. **Loops over network calls get bounded, backed-off retries on transient
    failures — and the retry count is recorded.** Retry only what is transient; a
    retried auth error is a hidden bug. Catch the transport library's transient
    *superclass* (`httpx.TransportError`), not the one subclass you have seen.
    (MIS-010, MIS-014)
15. **Fail at the unit that failed.** A per-question pipeline records a per-question
    failure as `None` with a reason and a run-level count — never as zero, never by
    discarding the questions that succeeded. VOID is for failures of the run itself.
    (MIS-011)
16. **A generation metric that judges a decision the generator made must condition
    on what the generator was given.** Refusing when retrieval failed is correct;
    answering when it failed is the failure. (MIS-012)
17. **The current judge is a plumbing placeholder (DEC-018).** Faithfulness, answer
   relevance and answer correctness have no trustworthy values until a real judge is
   chosen. Do not put them in EXPERIMENTS.md or NARRATIVE.md.
18. **e5/bge-style embedding models require query/passage prefixes. Omitting them
    produces no error, just worse numbers that get misattributed to architecture.**
    `Embedder.embed_texts` takes `input_type`; a model whose family the prefix table
    does not know is refused unless `prefix_convention` is set explicitly. Seeded by
    P1-04 before any dense run; not yet a recorded mistake, and the point is that it
    never becomes one.
19. **A 512-token embedding context truncates 36.7% of the 600/100 chunks** (p95 748
    tokens, max 1,336). Check a candidate model's `max_seq_length` against the chunk
    token distribution before indexing with it; truncation is silent and lands in the
    index, not the metrics. (DEC-027 for the hosted model; measured again for P1-04.)
20. **Provenance on a run row is read back from the component that used it, or
    asserted against it — never copied from the config alone.** (MIS-015)
21. **Test every parser of model output on stored model output**, not on the format
    the prompt asked for. Count what the parser drops. (MIS-016)
22. **Never report a judged-metric improvement smaller than its MDD as a win. Report it
    as "within judge noise".** The MDDs are per configuration family in
    `rag/eval/noise_floor.py` (DEC-037, DEC-046); a scorecard entry without its MDD is
    incomplete. Citation precision's MDD on the dense control is 0.08 — the generator,
    not the judge, is the noisiest instrument there.
23. **Never default an object with `__len__` using `or`.** An empty cache, store or
    frame is falsy, and `x or default()` silently swaps it for the default — here a
    test's cold cache for the shared one, which made a fake model look 100% cached.
    Use `if x is None`, and give container-like classes a `__bool__`. (MIS-017)
24. **Retrieval deltas are called by `rag compare` (paired test, DEC-047), judged
    deltas by their MDD family (DEC-048).** A run whose pipeline called an LLM is
    not a fixed outcome unless its cache hit rate was 100% (DEC-049); `rag compare`
    warns, and the warning goes in the EXP file.
25. **A table appended by code ends at the next `## ` heading, and a test proves
    the count.** The openings logger counted every `| ` row to the end of the file.
    (MIS-018)
26. **Changing a config default changes every config's `config_hash`, including
    the controls'.** Match runs to configs by `identity_hash` (the tier's own
    fields); when a default must change, say in the DEC entry which hashes move.
    (MIS-019)
27. **Estimate the index build before a dense run, and check the index key on
    disk first.** A new embedding model or chunk config is a full-corpus embed; the
    $2 gate exists for exactly this, and `rag run --estimate-only` costs nothing.
28. **`git status --short` prints nothing before a run launches — whoever's change it
    is.** A killed run leaves a RUNNING row: set it VOID with the reason at once.
    (MIS-020)
29. **Count a slice before you write a policy about it.** DEC-050 made `dev_large`
    the deciding split for retrieval axes; its multi-document slice has zero rows,
    which `load_split("dev_large")["n_gold_docs"].value_counts()` would have shown in
    one line. Item 1 again, unlearned. (MIS-021)

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

## MIS-010 — A hundred sequential API calls with no retry
- **Date:** 2026-09-11
- **Severity:** Low — one voided run, ~15 minutes and a few cents; no results affected.
- **What happened:** The first Tier 2 run of EXP-0001 (`run_20260911_051150_6b65`)
  died with `ReadTimeout` partway through generation. One `gpt-5-nano` call out of a
  hundred exceeded the 90-second timeout, the generator had no retry, and the runner
  recorded the run as `VOID` and stopped.
- **How it was caught:** The runner's own VOID record with the exception as its reason.
  That part worked exactly as designed — a crashed run is a row, not a gap.
- **Root cause:** The generator made raw `httpx.post` calls with no retry policy. A
  sequence of a hundred network calls has a transient failure somewhere in it as a
  matter of course; treating each as fatal makes the run's success a coin toss that
  gets worse with length. The judge side was already covered — the `openai` client
  Ragas uses retries by default — so the asymmetry was an oversight, not a decision.
- **Impact:** One VOID run in the store, kept. The Tier 2 criterion of P0-13 was met
  on the re-run.
- **Fix applied:** Bounded retries with exponential backoff on timeouts and on
  408/409/425/429/5xx, four attempts. Nothing else retries — an auth failure or an
  empty completion is raised on the first occurrence, because retrying those hides a
  real problem. The attempt count travels on every generated answer and the run row
  records how many questions needed a retry, so a run that leaned on retries is
  visible rather than silently lucky.
- **Prevention rule:** Any loop over network calls gets a bounded, backed-off retry on
  transient failures before it is used for a run whose numbers matter — and the retry
  count is recorded, never swallowed. Retry only what is transient; a retried auth
  error is a hidden bug.
- **Added to preflight:** yes

## MIS-011 — One judge failure voided a hundred-question run
- **Date:** 2026-09-11
- **Severity:** Low in cost, medium in design — two voided Tier 2 runs of EXP-0001
  in a row, ~30 minutes and ~$1; no results affected.
- **What happened:** The second Tier 2 attempt (`run_20260911_052616_aa4b`) got
  through generation — the MIS-010 retries held — and then died in judging:
  `IncompleteOutputException` from `instructor`, one question's structured output
  exceeding the 8,192-token judge budget. 8,192 had held for runs of 5, 8 and 20
  questions and failed once in 100. Ninety-nine judged questions were discarded with
  it, along with every generated answer, because per-question rows are written only
  after judging completes.
- **How it was caught:** The runner's VOID record, again. Correct behaviour for a
  crashed run; wrong behaviour to crash.
- **Root cause:** A judge failure on one criterion of one question was treated as
  fatal to the run. That is the wrong unit. Judging one question does not depend on
  another; a failure there is a fact about that question, and the honest record is
  "this criterion could not be scored here", not "this run did not happen".
- **Impact:** Two VOID rows kept in the store. The Tier 2 criterion of P0-13 was met
  on the third attempt.
- **Fix applied:** `RagasJudge._score_one` gathers criteria with
  `return_exceptions=True`. A failing criterion becomes a `JudgeScore` with
  `score=None` and the error text; the run row records `judge_failures` and the
  detail; aggregates exclude `None` (the MIS-002 rule, applied to infrastructure
  failure); the runner warns loudly. Judge budget raised to 16,384 — both pinned
  providers allow 40k+, and the longest reference answer in the subsample is 1,166
  tokens, so 8,192 overflowing was the judge's output ballooning, not the input.
- **Prevention rule:** Fail at the unit that failed. A per-question pipeline records
  per-question failures as `None` with a reason and a run-level count — never as
  zero, and never by discarding the questions that succeeded. Reserve VOID for
  failures of the run itself.
- **Added to preflight:** yes

## MIS-012 — `false_refusal` penalises the generator for retrieval's failure
> **CORRECTED by DEC-045 on 2026-09-13** — the "two false refusals" were the two the v1
> detector could see. Under `refusal-lexical-v2` the same run refused 20 times, 17 of
> them on retrieval misses. The definitional point is unchanged and larger.
- **Date:** 2026-09-11
- **Severity:** Medium — a metric definition that would have misattributed a
  failure across every Tier 2 run. No results affected: caught on the first real
  Tier 2 run, by reading the examples.
- **What happened:** EXP-0001's Tier 2 variant reported `false_refusal_rate = 0.02`.
  Reading the two refused questions: both had `strict_recall@5 = 0`. The articles
  needed were not retrieved, and the generator said it could not find the
  information — which is precisely what the answer prompt instructs and what a
  grounded system should do. The metric counted both as failures.
- **How it was caught:** The contract's rule that observations are written only after
  reading actual failing examples. The aggregate looked fine.
- **Root cause:** `false_refusal` was defined as "refused on a question that has gold
  documents", with "has" meaning *in the corpus* — decided when the metric was
  designed (P0-07), before any retrieval had run. The right condition is *in the
  retrieved context*. A question can be answerable in principle and unanswerable
  from what this run retrieved, and refusing in the second case is correct.
- **Impact:** As defined, every future run would report refusals-on-retrieval-failure
  as generator faults. Worse, the mirror-image failure is invisible: on the same run,
  the generator **answered anyway on 58 of 60 questions where retrieval had failed**,
  and nothing in the deterministic metrics flags those 58 as ungrounded.
- **Fix applied:** None to code — redefining a metric needs Krutik's sign-off
  (CLAUDE.md section 9). Proposed: condition refusal metrics on retrieval outcome.
  `false_refusal` = refused when all gold documents were in the context.
  `correct_refusal_on_miss` = refused when they were not. `answered_on_miss` = the
  58: answered when the gold documents were absent — the ungrounded-answer rate, and
  probably the most important cheap generation metric this project has. Tracked as
  OQ-019.
- **Prevention rule:** A generation metric that judges a decision the generator made
  must condition on what the generator was given. Retrieval outcome is an input to
  every generation metric, not a separate axis.
- **Added to preflight:** yes

## MIS-013 — P1-02's "numbered step lists" do not exist in the frozen text
- **Date:** 2026-09-12
- **Severity:** Low — caught before implementation by preflight item 1; no results
  affected.
- **What happened:** The Phase 1 handover asks for the count of articles containing
  numbered step lists and the number of chunk boundaries that land inside one. The
  WixQA extraction stripped ordered-list markers from `contents`: 21 of 6,221 articles
  have a `1.`-style line, 5 have two. Procedures are there — 2,350 articles (37.8%)
  have a "To do X:" header followed by imperative sentences — but not as numbered
  lists. Implemented literally, the story would have recorded 0.3% and a boundary
  count near zero, and Phase 2's structure-aware chunker would have had no "before".
- **How it was caught:** Counting the pattern on the corpus before writing the
  profiler, as MIS-001 requires. The first article inspected showed the shape.
- **Root cause:** Same as MIS-001 and MIS-002: a handover premise about the data's
  format, written without looking at the frozen text.
- **Impact:** None. Half a day would have gone to a metric that measured extraction.
- **Fix applied:** The profile reports the literal count *and* a heuristic
  procedure-block count with a fixed, documented definition (DEC-039). The
  heuristic's agreement with the source HTML is an open question (OQ-020), not a
  claim.
- **Prevention rule:** Already preflight item 1. This entry exists because it is the
  third time the same premise class has appeared in a handover, and the rule is
  earning its place.
- **Added to preflight:** already there (item 1)

## MIS-014 — The retry loop caught timeouts but not transport errors; the first dense index build died on a TLS read error
- **Date:** 2026-09-12
- **Severity:** Low — one VOID run (`run_20260912_222345_671e`), ~76 seconds and a
  few cents of embedding calls lost; no results affected.
- **What happened:** The first EXP-0005 index build raised
  `httpx.ReadError: [SSL: SSLV3_ALERT_BAD_RECORD_MAC]` on one of 129 batch calls.
  The embedder's retry loop caught `httpx.TimeoutException` and retryable HTTP
  statuses only; a `ReadError` is neither, so it propagated and voided the run. The
  generator's loop (MIS-010) had the identical gap and had simply not been hit yet.
- **How it was caught:** The run crashed; the runner recorded it VOID as designed.
- **Root cause:** Retrying on the one transient class that had been observed
  (timeouts, MIS-010) rather than on the superclass of transient transport failures.
  `httpx.TransportError` covers timeouts, connection errors and read/write errors.
- **Impact:** One VOID row; the index build restarts from scratch (batches already
  embedded are not persisted until the build completes).
- **Fix applied:** Both loops now catch `httpx.TransportError`. Retries are still
  bounded (4 attempts, exponential backoff) and counted in `usage.retries`.
- **Prevention rule:** Retry on the transport library's transient *superclass*, not on
  the one subclass you have seen. Auth and bad-request errors stay non-retryable.
- **Added to preflight:** folded into item 14.

## MIS-015 — `generator_prompt` was recorded on every run but never passed to the generator
- **Date:** 2026-09-12
- **Severity:** Low — caught while adding the second prompt; every run so far used the
  only prompt that existed, so recorded and actual agree for all of them.
- **What happened:** `RunConfig.generator_prompt` ("answer@v1") went into the run
  row's `prompt_versions`, but `_tier2` built `GeneratorConfig` without it, so the
  generator always loaded `answer@v1` from its own defaults. With
  `baseline_answer@v1` configured, a run would have recorded the new prompt and
  used the old one.
- **How it was caught:** Reading the generator construction before wiring P1-05.
- **Root cause:** Two sources of truth for the prompt ref — the run config and the
  generator config — with nothing asserting they agree.
- **Impact:** None to results. Would have silently invalidated every Phase 1 Tier 2
  comparison against Phase 0.
- **Fix applied:** The runner passes the configured id and version through, and
  raises if the answer's `prompt_ref` differs from what the run recorded.
- **Prevention rule:** Provenance recorded on a run row must be read back from the
  component that used it, or asserted against it — never copied from the config
  alone.
- **Added to preflight:** yes

## MIS-016 — The citation parser drops `[doc: id]` (with a space); 1.5–4% of citations in the Phase 0 Tier 2 runs were lost
> **CORRECTED by DEC-043 on 2026-09-12** — fix applied (`citation-v2`), the three rows
> recomputed, floors re-measured. The "Fix applied: None" below describes the state
> before Krutik's sign-off.
- **Date:** 2026-09-12
- **Severity:** Low-to-medium — affects citation precision/recall on every Tier 2 run
  by a few citations per hundred answers; no VOID.
- **What happened:** `extract_citations` matches `\[doc:([0-9a-f]{8,64})\]` exactly.
  `rag ask` output showed `[doc: ec3f…]` with a space after the colon, silently
  dropped. Counting in the stored answers of the three EXP-0001 Tier 2 runs: strict
  matches 271 / 277 / 271, tolerant matches 275 / 289 / 284 — **4, 12 and 13
  citations per run** the metric never saw.
- **How it was caught:** Reading a rendered answer in full, not its aggregate.
- **Root cause:** The parser was written against the prompt's example format and never
  tested on what the model actually emits.
- **Impact:** Citation precision and recall for those runs are slightly understated;
  the direction is known, the size is a few points at most. DEC-037's citation
  floors (0.007 / 0.005) were measured with the same parser, so they are internally
  consistent.
- **Fix applied:** **None.** Loosening the parser changes the citation metric's
  definition and the historical numbers on recomputation — Krutik's sign-off
  (CLAUDE.md §9). `tests/test_citations.py` pins the current behaviour so the change,
  when made, is visible. Proposed: accept optional whitespace inside the brackets,
  record the parser version on the run row, and recompute the three EXP-0001 Tier 2
  rows as a correction entry.
- **Prevention rule:** Test every parser of model output on stored model output, not
  on the format the prompt asked for.
- **Added to preflight:** yes

## MIS-017 — `cache or GenerationCache()` replaced a test's empty cache with the shared one
- **Date:** 2026-09-15
- **Severity:** Low — caught by the P2-03 determinism test before any experiment;
  no run affected. The stray shared cache held 200 fake-model rows and was deleted.
- **What happened:** `ToyLLMRewriteRetriever` picked its cache with
  `self.generation_cache or GenerationCache()`. `GenerationCache` defines `__len__`,
  so an *empty* cache is falsy and the expression fell through to the default under
  `results/`. The test's "fresh cache" third run therefore hit the shared cache the
  first run had just filled, reported a 100% hit rate, and the cold-repeat flag never
  fired.
- **How it was caught:** `test_repeat_run_with_warm_cache_is_identical_and_flags_a_cold_repeat`
  expected a warning and got none; the recorded `cache_path` pointed at `results/`.
- **Root cause:** Python truthiness on a container-like object, used as a null check.
- **Impact:** None on results. Had it shipped, every Axis 4 run would have read as
  fully cached whenever the test suite had warmed the shared cache — a false
  determinism claim that is exactly what P2-03 exists to prevent.
- **Fix applied:** `if self.generation_cache is not None`, and `GenerationCache.__bool__`
  returns True so the trap cannot recur on this class.
- **Prevention rule:** Never default a container-like object with `or`; check
  `is None`. Any class with `__len__` that is passed around as a handle gets a
  `__bool__`.
- **Added to preflight:** yes (item 23)

## MIS-018 — The test-split openings logger counted every table row after its heading
- **Date:** 2026-09-15
- **Severity:** Low — latent; the test split has never been opened, so no count was
  ever wrong on record.
- **What happened:** `record_test_opening` split `DECISIONS.md` at the "Test-split
  openings log" heading and counted every `| ` row in the *rest of the file* as an
  opening. The log sits in the middle of the file (before DEC-010) and DEC-046 has
  since added MDD tables after it, so the first real opening would have been logged
  as opening #30-something.
- **How it was caught:** Adding two more machine-written tables (promotion log,
  cost approvals) for P2-05/P2-06 and reading the existing appender before reusing it.
- **Root cause:** No section boundary; no test of the count against a file with
  other tables in it.
- **Impact:** None recorded. Would have made P2-18's "opened exactly once" claim
  unverifiable from the file.
- **Fix applied:** `rag/runner/decision_log.py` bounds a section at the next `## `
  heading; all three logs use it; `test_log_sections_end_at_the_next_heading`
  proves the count with a DEC-046-style table following the log.
- **Prevention rule:** A parser of our own documents gets a test on a realistic
  document, not on the minimal one it was written against.
- **Added to preflight:** yes (item 25)

## MIS-019 — A Tier-2-only default change moved the Tier 1 control's `config_hash`
- **Date:** 2026-09-15
- **Severity:** Medium — no number affected; identity of the control broken. Every
  citation of EXP-0005's hash `c535f774bff4b067` remains correct for those rows, but
  `configs/baseline_dense.yaml` now hashes to `7c99bc8e9a88e878`.
- **What happened:** DEC-042 changed `RunConfig.generator_prompt`'s default from
  `answer@v1` to `baseline_answer@v1` after EXP-0005 had run. `config_hash` covers
  every field, so the dense control's hash changed although Tier 1 never reads that
  field. `rag promoted show` found no run of the promoted config; the P2-03 repeat
  detector (`runs_with_config_hash`) would likewise not recognise a repeat of the
  control.
- **How it was caught:** `rag promoted show` printed "no VALID run" for a config
  with three recorded runs.
- **Root cause:** One hash for two purposes — the exact record of what ran (right to
  include everything) and the identity used to find runs of "the same experiment"
  (must not include fields the tier never reads).
- **Impact:** None on any recorded metric. Comparability keys (corpus, split, judge)
  were never involved.
- **Fix applied:** `RunConfig.identity_hash` — Tier 1 fields only for a Tier 1 run,
  everything for Tier 2 — and `ResultsStore.latest_run_of` / `rag promote` match on
  it, rebuilt from each row's `config_json`. `config_hash` is unchanged and still
  the exact identity on the row. The repeat detector still uses `config_hash`
  (stricter; a missed repeat is the safe failure).
- **Prevention rule:** When a config default changes, the DEC entry says which
  configs' hashes move and why that is acceptable. Match runs to configs by the
  tier's identity, never by the exact hash.
- **Added to preflight:** yes (item 26)

## MIS-020 — Launched EXP-0008 on a dirty tree
- **Date:** 2026-09-15
- **Severity:** Low — killed after ~30 s, ~$0.00001 of query embeddings; row
  `run_20260916_061852_f583` set to VOID by hand with the reason.
- **What happened:** Krutik's revision of `user_stories/phase2stories.md` was sitting
  uncommitted since the session began. I committed my own files around it and launched
  the run; the runner warned `GIT WORKING TREE IS DIRTY` and recorded `git_dirty = 1`.
- **How it was caught:** Reading the launch log's first lines.
- **Root cause:** I treated "my files are committed" as "the tree is clean". The
  runner's check is on the tree, and rightly so.
- **Impact:** One VOID row. No numbers.
- **Fix applied:** Committed the spec revision (it is the document the P2 work was
  built against), relaunched.
- **Prevention rule:** `git status --short` must print nothing before a run is
  launched, whoever's change is pending. A killed run leaves a RUNNING row — set it
  VOID with the reason at once.
- **Added to preflight:** yes (item 28)

## MIS-021 — Encoded "decide retrieval axes on `dev_large`" without counting its multi-document slice, which is empty
- **Date:** 2026-09-16
- **Severity:** Medium — no run invalid; a Phase 2 policy (DEC-050, from P2-04) rests on
  a slice that does not exist, and OQ-024 asked the wrong question ("is it big
  enough?").
- **What happened:** The handover assumed `dev_large` carries multi-hop questions
  ("decide on `dev_large` for statistical power"). It carries 6,221 synthetic
  single-gold questions and nothing else. EXP-0008 made it visible: strict and loose
  recall identical at every k, MRR's single-gold "subset" equal to the whole split,
  `gold_docs:multi` slice absent from `slices_json`.
- **How it was caught:** Reading EXP-0008's aggregate before writing its row, then
  counting `n_gold_docs` on all three splits (dev 160/35/5; dev_large 6,221/0/0; test
  161/35/4).
- **Root cause:** I implemented the split policy from the handover's description and
  did not count the thing it depended on — preflight item 1, verbatim. The split
  builder's own `describe_split` output would have shown it.
- **Impact:** DEC-050's "decide on `dev_large`" gives power on single-document
  questions only, at a ceiling (strict recall@5 0.973 for the control). Every
  multi-hop verdict in Phase 2 comes from 40 questions on `dev` — the power problem
  OQ-024 measured (p = 0.063 on a 0.175 gain). The organizing question is decided at
  n = 40 whatever the policy says.
- **Fix applied:** Recorded here and in OQ-024; the policy change is Krutik's call
  (DEC-055, pending). No code change until it is made.
- **Prevention rule:** Before a DEC entry names a split or slice as the decider, the
  entry quotes its row count from the data.
- **Added to preflight:** yes (item 29)
