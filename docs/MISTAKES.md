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
30. **Send one real batch through a new embedding endpoint before the index build,
    and read the error body.** OpenRouter applies some endpoints' context length to
    a batch's *total* tokens and then drops the pinned provider; the 404 body's
    `routing_funnel` says so, and our embedder was discarding it. (MIS-023)
31. **A rate limit (HTTP 429) outlasts an ordinary retry schedule — give it its own
    budget, honour `Retry-After`, and record the count.** 2 / 4 / 8 s expires inside
    a per-minute window; two index builds died that way, one 42 minutes in. Batch
    long builds so the slowest is last, and never let two builds share a rate
    window. (MIS-024)
32. **A chunking comparison is also a re-embedding comparison.** Every chunker is a
    fresh embed, and 59% of vectors change on re-embedding the same text
    (EXP-0012). Measure the control-rebuild floor before calling a chunking delta
    smaller than it (OQ-031). (EXP-0022)
33. **A price of zero for a paid product is an absent field, not a free product.**
    OpenRouter lists every rerank model at `prompt: "0"` and bills real money per
    call. Before costing a new endpoint, send one real call and read `usage`; where
    the billing unit is one the price table cannot express (Cohere's search unit),
    the table gets a hand-measured block and the refresher is told to skip it.
    (MIS-025)
34. **Reranking is billed per query, so its cost scales with the split, not with
    the corpus.** An index build is a one-off; a reranker charges again for every
    question. The same Axis 5 config is $0.23 on `dev` and $7.28 on `dev_large`.
    Estimate against the split you are about to run, never against the last one.
35. **Before a paid run from a non-interactive shell, assert the credential is in the
    ENVIRONMENT, not that `.env` exists.** `set -a && . ./.env && set +a` — one line,
    costs nothing; the failure costs a run. (MIS-026)
36. **A run in flight owns the working tree.** No edit until its row is finished —
    not documentation, not the next run's config. The runner reads git state after
    the process starts, so an edit during the launch window lands on the row as
    `git_dirty=1` and cannot be taken off. Bookkeeping waits. (MIS-027)
37. **When a provider's billing unit has a capacity, find what fills it before
    assuming your unit is theirs**, and check the first real run's actual against its
    estimate *per run* — the three-run drift check is too coarse to catch a 17%
    error. (MIS-028)
38. **A ceiling, floor or bound is a MEASUREMENT, not an inference from a mechanism.**
    Before writing that something cannot be exceeded, compute the quantity that
    bounds it — usually one query against the results store. "No reranker beats
    0.920 here" was beaten by the next run; the real bound, recall@50 = 0.985, was
    in `run_questions` the whole time. (MIS-029)
39. **The runner writes to `docs/DECISIONS.md`, so it dirties the tree it measures.**
    The second and later runs of any approved batch record `git_dirty=1` through
    nobody's fault. Expect it, state its cause on the row, and do not read it as a
    code change. (MIS-030)
40. **Before a batch, check the account balance, not just the estimate.** Every cost
    control here is per-run and none of them knows whether the account has money.
    The failure lands on the last run in the queue. (MIS-031)
41. **Work out what the provider's UNIT OF WORK is before estimating: per call, per
    document, per pair, per search unit.** Get it from one real response's `usage`,
    not from the shape of the request you sent. A cross-encoder bills (query,
    document) pairs, so the query is charged once per document. All three Axis 5
    cost errors were the same mistake — assuming the provider bills the thing we
    happened to be counting. (MIS-025, MIS-028, MIS-032)
42. **Write the HYPOTHESES entry in the same action as the config, before the run.**
    A free or fast run is the most likely to skip it, because nothing forces a pause,
    and a hypothesis written afterwards is not evidence of anything. (MIS-033)

---

42. **Probe every (model, prompt) PAIR, not every model.** A model that obeys one
    prompt at 54 output tokens can spend 32,848 completion tokens on another — the same
    model, the same settings. Read `reasoning_tokens` off a real response for the prompt
    you are about to use, not for a neighbouring one. (MIS-034)
43. **A per-unit provider failure is recorded per unit and the loop continues.** If a
    loop of N paid calls can be killed by call k, the money spent on the first k−1 is at
    risk. Keep the fallback that equals the control's behaviour, count the failure, put
    it on the row. VOID is for failures of the run itself. (MIS-034, preflight 15 again)
44. **`reasoning_effort` is a request, not a guarantee, and at temperature 0 a
    reasoning model is still not deterministic.** `"minimal"` and `"low"` produced
    identical reasoning-token counts on `gpt-oss-20b`, and the same input that emptied
    its budget once succeeded on retry. Assert the token behaviour you assumed; never
    infer it from the parameter you sent. (MIS-034)

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

## MIS-022 — Wrote "every gold document is `article`" into EXP-0008 without looking at the slice table
- **Date:** 2026-09-16
- **Severity:** Low — one wrong sentence in an EXP file, corrected within the hour by an
  appended correction; no number affected.
- **What happened:** EXP-0008's Results section claimed `dev_large`'s `article_type`
  slices were the whole split. The run's own `slices_json` has three types (4,109 /
  2,049 / 63). I had printed only the `gold_docs` and `q_len` slices and generalised.
- **How it was caught:** `rag compare` for EXP-0009 printed the three slices.
- **Root cause:** Writing a statement about the slice table from a partial print of it.
- **Impact:** None on results. It would have hidden the `feature_request` finding of
  EXP-0009 had it been trusted.
- **Fix applied:** Correction appended to EXP-0008.md; the original line marked.
- **Prevention rule:** Print the whole slice table before writing about slices; a claim
  that a slice is empty or total is checked against `n_questions`, not assumed.
- **Added to preflight:** covered by item 1 and item 29; no new item.

## MIS-023 — bge-m3 index build died on a 404 whose body the embedder threw away
- **Date:** 2026-09-16
- **Severity:** Low — one VOID row (`run_20260916_091734_7664`), $0; ~40 minutes.
- **What happened:** The first 64-chunk batch to `baai/bge-m3` on DeepInfra returned
  `404 No endpoints found`. The single-input probe an hour earlier had succeeded.
  Re-sending with the body captured showed OpenRouter's `routing_funnel`: 2 endpoints
  → "Filter by Context Length" → 1 (DeepInfra dropped) → "Filter by Fallback" → 0
  (we pin one provider, no fallbacks). The endpoint's 8,192 context is applied to the
  **batch's total tokens**, so 16 chunks (5–12k tokens) failed or passed depending on
  their lengths, and 5 or 8 always passed. `text-embedding-3-large` (also 8,192) and
  `gemini-embedding-2` (8,192; 64 real chunks = 26k tokens) are not filtered this way,
  so it is endpoint-specific.
- **How it was caught:** The run's VOID note said only `404 Not Found`; reproducing
  outside the runner and printing `response.text`.
- **Root cause:** Two. The embedder raised `HTTPStatusError` without the response
  body, so the one line that explained the failure was discarded. And I validated the
  endpoint with one short input instead of one real batch (preflight item 10, in
  spirit: probe the thing you will actually do).
- **Impact:** None on results.
- **Fix applied:** `OpenRouterEmbedder` now raises with the status, batch size and the
  first 500 characters of the body on any non-retryable status. Both bge-m3 configs
  use `batch_size: 5` (5 × the longest chunk, 1,336 tokens, stays under 8,192), with
  the reason in the file. Batch size is in `retriever_params`, so it is in the config
  hash; it does not change any vector.
- **Prevention rule:** Before an index build on a new endpoint, send one batch of
  real chunks at the configured batch size and read the response; raise every
  non-transient provider error with its body.
- **Added to preflight:** yes (item 30)

## MIS-024 — Two index builds died on DeepInfra rate limiting because 429 was retried like a blip
- **Date:** 2026-09-19
- **Severity:** Medium — EXP-0019 (sentence-window) VOID twice, EXP-0021 (semantic)
  failed before its run row existed; ~$0.02–0.03 of embedding calls lost; two
  experiments of the axis still unrun.
- **What happened:** The four Axis 1 configs ran back to back, each building an index.
  During the first build DeepInfra began returning 429 (16 retries in EXP-0022's
  build). The semantic chunker's sentence pass (195,822 sentences, batch 256) hit
  429s that outlasted the embedder's 4 attempts at 2 / 4 / 8 s and raised after 4,505
  of ~6,050 articles were cached. The sentence-window build (3,065 calls) raised
  ~42 minutes in; its `dev` run then tried to rebuild and hit 429 immediately.
- **How it was caught:** The batch's summary showed `HTTPStatusError 429` for the last
  four runs; the results store had two VOID rows and no row for the semantic runs.
- **Root cause:** 429 sat in the same retry set as 5xx and timeouts. A rate limit is
  not transient on the 2–14 s scale; it is a per-minute (or longer) quota, and the
  provider's `Retry-After` header — when sent — was ignored. Running four builds
  consecutively also kept the quota saturated, so each run inherited the previous
  one's limit.
- **Impact:** EXP-0019 needs a full re-run ($0.03); EXP-0021's sentence pass resumes
  from its cache (1,500 articles left, ~$0.01) then needs its index ($0.03). The
  partial sentence-window embeddings were not saved, because the dense index is
  written whole at the end.
- **Fix applied:** `OpenRouterEmbedder` gives 429 its own budget: up to 8 rate-limited
  attempts, waiting `Retry-After` seconds when the provider sends a number, else
  15 s doubling to a 300 s cap, on top of the ordinary attempts; `usage.rate_limited`
  is recorded so a slow build reads as rate limiting, not latency. Pinned by two
  tests (tests/test_embedding.py).
- **Prevention rule:** Rate limits get a schedule of their own and a counter on the
  run row. Do not chain long index builds without a gap. The dense index builder
  should checkpoint groups to disk so a failed build keeps what it paid for —
  **not done yet**, filed as a follow-up in the EXP-0019 re-run.
- **Added to preflight:** yes (item 31).

## MIS-025 — Took OpenRouter's rerank prices from the listing, which says every rerank model is free
- **Date:** 2026-09-22
- **Severity:** Medium — caught before any experiment ran; no results affected. Had
  it gone unchecked, the $2 gate would have read every Axis 5 run as $0.00 and the
  `dev_large` sweep the story suggests (~$50) would have started without approval.
- **What happened:** P2-10's story says "Cohere rerank models were listed at $0 on
  OpenRouter at launch, which if still true makes this axis nearly free". It is
  still true, and it is still wrong. `GET /models/<id>/endpoints` reports
  `pricing: {prompt: "0", completion: "0"}` for `cohere/rerank-v3.5`,
  `cohere/rerank-4-fast` and `qwen/qwen3-reranker-8b` alike. `rag pricing refresh`
  reads exactly that field, so the pricing table would have been populated with
  zeros for all three.
- **How it was caught:** sending one real call through the endpoint before writing
  the estimator (preflight 30) and reading the response body. Every call returns a
  `usage` block that bills real money:

  | Model | 50 documents x 600 words | latency |
  |---|---|---|
  | `cohere/rerank-v3.5` | 1 search unit, **$0.001** | 778 ms |
  | `cohere/rerank-4-fast` | 1 search unit, **$0.002** | 1,298 ms |
  | `qwen/qwen3-reranker-8b` | 40,627 tokens, **$0.008125** | 1,847 ms |

- **Root cause:** the rerank endpoint bills in units the `/models` schema has no
  field for — Cohere charges a *search unit* per query, not tokens — so the
  token-price fields are zero because they do not apply, not because the model is
  free. A price schema that cannot express a product's billing unit reports the
  absence as zero.
- **Impact:** none to results. The measured rates are what the estimator uses:
  $0.20 / $0.40 / $0.78 for a 200-question `dev` run, and $6.22 / $12.44 / $26 on
  `dev_large` — the difference between "nearly free" and an axis that needs
  approval for every run.
- **Fix applied:** `configs/pricing.yaml` gained a hand-maintained `rerank:` block
  whose numbers come from `usage.cost` on real calls, with the measurement recorded
  beside each rate. `refresh_pricing` copies the block through untouched rather than
  re-fetching it (a test asserts this). `OpenRouterReranker` records cost from the
  response, never from the table, and `estimate_rerank_cost` treats an absent entry
  as UNAVAILABLE, which fails the gate.
- **Prevention rule:** a price field of zero for a paid product is an absent field,
  not a free product. Before costing a new endpoint, send one real call and read
  `usage`; if the billing unit is not one the price table can express, the table
  gets a new block and the refresher is told to leave it alone.
- **Added to preflight:** yes (item 33)

## MIS-026 — Launched a paid run from a shell that had no API key
- **Date:** 2026-09-23
- **Severity:** Low — the run died before any provider call; nothing was spent.
- **What happened:** EXP-0024's first attempt (`run_20260923_052903_c2ea`) raised
  `OPENROUTER_API_KEY is not set` on its first query embedding. The key is in `.env`
  at the repo root and `rag` reads it from the environment by design (CLAUDE.md §10);
  the launching shell had never sourced it.
- **How it was caught:** the run exited non-zero and the runner recorded it VOID with
  the exception on the row, which is the behaviour that made it obvious rather than
  mysterious.
- **Root cause:** an assumption that "the key is in `.env`" means "the key is in the
  environment". It means a human's interactive shell usually exports it and a fresh
  non-interactive one does not.
- **Impact:** none to results, none to spend. One VOID row in the ledger, kept.
- **Fix applied:** the run command is `set -a && . ./.env && set +a && python -m
  rag.cli run ...`, and EXP-0024's Reproduce block spells that out. `rag` was **not**
  changed to load `.env` itself: reading the key from the environment is the
  contract, and a library that quietly loads secrets from the working directory is a
  worse default than an explicit failure.
- **Prevention rule:** before a paid run from a non-interactive shell, assert the
  credential is *in the environment*, not that the file exists. The check is one
  line and it costs nothing; the failure costs a run.
- **Added to preflight:** yes (item 35)

## MIS-027 — Edited a tracked file while a run was launching, so it recorded git_dirty=1
- **Date:** 2026-09-23
- **Severity:** Low — the numbers are sound and the dirt was documentation, but the
  row now carries a flag that cannot be removed, and the flag is the point.
- **What happened:** EXP-0024 was launched from a clean tree. While it was starting,
  `docs/EXPERIMENTS.md` was edited to record the VOID row from MIS-026. The runner
  reads git state at the top of `_run`, after the process starts, so it saw a dirty
  tree and recorded `git_dirty=1` against `f337ae2`.
- **How it was caught:** the runner's own warning in the run log.
- **Root cause:** treating preflight item 28 as "commit before you launch" when it
  says the tree prints nothing *before a run launches* — and then not extending that
  to the launch window itself. The rule was quoted in the commit one before this one
  and broken in the next action.
- **Impact:** `git diff f337ae2` over the window touches one file,
  `docs/EXPERIMENTS.md`, and nothing under `rag/`, `configs/` or `prompts/`, so
  `f337ae2` does describe the code that produced the numbers. The run is **not**
  VOID: re-running to clear a docs-file timestamp would spend $0.23 to change a flag
  and not a number. The flag stays and EXP-0024 explains it in *Anomalies*.
- **Fix applied:** none in code. The runner already warned loudly and recorded the
  fact; it behaved correctly.
- **Prevention rule:** a run in flight owns the working tree. No edit — not docs, not
  a config for the *next* run — until the run row is finished. Bookkeeping waits.
- **Added to preflight:** yes (item 36)

## MIS-028 — Costed Cohere's search unit by document count; it is billed by candidate length
- **Date:** 2026-09-23
- **Severity:** Low — 17% under, inside the gate. Would have mattered at `dev_large`
  scale or nearer the $2 line.
- **What happened:** the Axis 5 estimator read Cohere's "one search unit = one query
  with up to 100 documents" and billed 50 candidate documents as 1 unit per query.
  EXP-0024 estimated $0.2001 and was billed **$0.2341** — 234 units for 200 queries.
- **How it was caught:** `cost_actual_usd` against `cost_estimate_usd` on the run
  row. The drift check did not fire (it needs a median ratio outside 0.75–1.33 over
  three runs); the per-run comparison did.
- **Root cause:** two compounding errors, both from counting the wrong thing.
  `rerank_candidates` counts *documents*, but the reranker receives every ranked
  chunk of them — 58.4 chunks per 50 documents. Cohere then splits each into
  ~500-token pieces, and 44% of candidate chunks exceed that: candidates average 348
  words against the corpus-wide 309, because longer articles produce more chunks and
  so have more chances to be retrieved. Most queries land near 84 billable pieces,
  under the 100-per-unit line; ~34 whose candidates skew long cross it and bill twice.
- **Impact:** $0.034 of unanticipated spend on one run. No result affected.
- **Fix applied:** the multiplier is now what was billed — 1.17 units per query at 50
  candidate documents, calibrated on `run_20260923_052941_4ada` and **labelled in the
  estimator's own output as not yet validated out of sample** (DEC-035). A piece
  model built from mean chunk length still predicts 200 units, because the effect is
  a threshold on a per-query distribution, so a measured multiplier is the honest
  instrument and a modelled one would be false precision.
- **Prevention rule:** when a provider's billing unit has a capacity ("up to 100
  documents"), find what fills it before assuming your unit is theirs. Then check the
  first real run's actual against its estimate per run, not only against the
  three-run drift check, which is too coarse to catch a 17% error.
- **Added to preflight:** yes (item 37)

## MIS-029 — Called one run's number a ceiling, and the next run beat it
- **Date:** 2026-09-23
- **Severity:** Medium — a wrong claim reached EXPERIMENTS.md, the scorecard, the
  negative-results entry, NARRATIVE.md and an experiment file, and was described
  there as "the single most reusable thing the axis produced". Corrected in place
  within one run; no decision was taken on it.
- **What happened:** EXP-0024's strict recall@20 was 0.920 before reranking and
  0.920 after, p = 1.000. I wrote: *"The reranker only re-orders 50 candidate
  documents, so the recall of that candidate set is the most it can ever deliver…
  no reranker, however good, beats 0.920 here."* EXP-0025 scored **0.940** at
  recall@20 the same afternoon.
- **How it was caught:** reading EXP-0025's metrics against the claim before writing
  it up. It took one line of disbelief — 0.940 is not supposed to be possible.
- **Root cause:** the reasoning was correct and applied to the wrong number. A
  50-document candidate set does bound the reranker, but it bounds it at recall@**50**,
  not recall@**20**. A gold at dense rank 21–50 is inside the candidate set and can be
  promoted into the top 20 — EXP-0025 promoted eight. I had the right mechanism and
  never measured the quantity it actually implies. **Measuring it takes one query
  against data already in the store**, which is what makes this careless rather than
  unlucky: the control's recall at every depth was sitting in `run_questions` the
  whole time.
- **Impact:** the corrected number is better than the wrong one. The real ceiling is
  **strict recall@50 = 0.985** on the dense control, against which the best reranker
  delivered 0.730@5 — so the gold is in the candidate set 98.5% of the time and gets
  surfaced 73% of the time. That gap reframes Axis 5 from "reranking cannot help
  because the documents are not there" (what the wrong ceiling implied) to "the
  documents are there and two cross-encoders could not rank them" — the opposite
  conclusion, and the more interesting one.
- **Fix applied:** correction entries appended and `> **CORRECTED by MIS-029**` lines
  added directly beneath the original claims in `docs/experiments/EXP-0024.md`,
  `docs/EXPERIMENTS.md` (scorecard point 3 and the negative-results entry) and
  `docs/NARRATIVE.md`. The original numbers stay; only the conclusion is withdrawn.
  The measured depth curve is now recorded in the Axis 5 scorecard.
- **Prevention rule:** a ceiling, floor or bound is a **measurement**, not an
  inference from a mechanism. Before writing that something cannot be exceeded,
  compute the quantity that actually bounds it — and if that takes a query against
  the results store, run the query. A bound asserted from one run is a prediction
  wearing a fact's clothes, which is the thing this repository exists to not do.
- **Added to preflight:** yes (item 38)

## MIS-030 — The runner dirties the working tree, so the second run of any batch records git_dirty=1
- **Date:** 2026-09-23
- **Severity:** Low — no numbers affected, but it makes a preflight item unsatisfiable
  and so trains everyone to ignore a flag that matters.
- **What happened:** the Axis 5 batch launched from a clean tree. EXP-0025 ran first
  and, because it carried `--approve-cost`, appended its approval row to the
  cost-approvals log in `docs/DECISIONS.md` — a tracked file. EXP-0026 started
  seconds later, read git state, found the tree dirty and recorded `git_dirty=1`.
- **How it was caught:** EXP-0026's row showed `git_dirty=1` when nobody had touched
  anything, one run after MIS-027 established that a run in flight owns the tree.
- **Root cause:** the runner writes three machine-appended tables into
  `docs/DECISIONS.md` (promotions, cost approvals, test openings). That is the right
  place for them — the ledger should be reviewable in a diff — but it means **the act
  of running dirties the repository**, so MIS-027's rule cannot be honoured by any
  batch of two approved runs, however disciplined the operator.
- **Impact:** one row carries a flag that describes the runner's own bookkeeping
  rather than a code change. `git diff` over EXP-0026's window touches only
  `docs/DECISIONS.md`. EXP-0026 was VOID for an unrelated reason (MIS-031), so no
  result rests on it.
- **Fix applied:** none yet — this is recorded before it is fixed, deliberately, so
  the decision is made with the cost visible rather than patched over. Three options,
  none free: commit between runs in a batch (manual, and a commit per run contradicts
  one-commit-per-story); have the runner record git state *before* its own writes;
  or move the machine-appended tables out of a tracked file, which loses the diff.
- **Prevention rule:** when a tool records provenance about the repository, it must
  read that provenance **before** its own side effects, or it is measuring itself.
  Until that is fixed, `git_dirty=1` on the second or later run of a batch is expected
  and its cause must be stated on the run's row rather than assumed innocent.
- **Added to preflight:** yes (item 39)

## MIS-031 — Ran a batch without checking the account balance; the last run died on HTTP 402
- **Date:** 2026-09-23
- **Severity:** Low — nothing was billed for the failed run and no result was lost,
  but an experiment that was approved did not happen and the axis is incomplete.
- **What happened:** EXP-0026 (`qwen/qwen3-reranker-8b`, estimated $0.9168) died on
  its first rerank call: `HTTP 402 Insufficient credits`. The OpenRouter account ran
  out of credit partway through the Axis 5 batch, after EXP-0024 ($0.234) and
  EXP-0025 ($0.448).
- **How it was caught:** the provider said so, in a body the client preserved. 402 is
  correctly absent from the retry set — a credit exhaustion is not transient, and
  retrying it eight times with backoff would have burned four minutes to reach the
  same answer.
- **Root cause:** every cost control in this project is per-run. The $2 gate, the
  estimate, the approval, the running totals — all of them answer "can this run
  afford to start?" and none answers "does the account have money in it?". The
  running totals printed `$2.3151 over 33 runs` immediately before the failure, which
  is spend *we* recorded, not balance *remaining*.
- **Impact:** one approved experiment not run. Axis 5 has two rerankers measured and
  one owed. `cost_actual_usd` is NULL on the VOID row, correctly: the provider
  refused the request, so there is no usage to report.
- **Fix applied:** none in code yet. `GET /api/v1/credits` reports the balance and
  would let the pre-run estimate be checked against money that actually exists, which
  is a small change and a real improvement to the gate — raised with Krutik rather
  than built unasked, since it changes what halts a run.
- **Prevention rule:** before a batch, check the balance, not just the estimate. A
  gate that only compares a run against a threshold cannot tell you the account is
  empty, and the failure lands on whichever run is last in the queue — which is the
  one you were least likely to have already validated.
- **Added to preflight:** yes (item 40)

## MIS-032 — Estimated a cross-encoder's tokens as the sum of its documents; it bills (query, document) pairs
- **Date:** 2026-09-24
- **Severity:** Low — 32% over, inside the gate and inside the approved amount. It is
  logged at length because it is the third cost-model error in this axis and the
  three have the same shape.
- **What happened:** EXP-0026 (`qwen/qwen3-reranker-8b`, the one token-billed
  reranker) estimated $0.9168 and billed **$1.2103**. The estimator computed the
  candidates' own token count and stopped there.
- **How it was caught:** `cost_actual_usd` against `cost_estimate_usd` on the run row,
  per preflight 37. The three-run drift check still did not fire.
- **Root cause:** a cross-encoder does not read a list of documents; it scores
  **(query, document) pairs**, one forward pass each. So the query text and the
  model's prompt template are billed once **per document**, not once per call.
  Measured: **517.9 tokens per pair**, against candidates averaging 348 words
  (442 tokens) — about **76 tokens of per-pair overhead**, and at 58 candidates per
  query that is a third of the bill. Compounding it, the estimator used the
  corpus-wide mean chunk length (309 words) where actual candidates average 348,
  because longer articles produce more chunks and so are retrieved more often.
- **Impact:** $0.29 of unanticipated spend. No result affected.
- **Fix applied:** the token path now estimates
  `candidate_chunks x (candidate_words x 1.126 x 1.27 + 76)`, which reproduces
  6,050,240 of the 6,051,291 tokens actually billed — within 0.1%. Both constants are
  named for what they are, and the estimator's printed source says "a cross-encoder
  bills the query once PER DOCUMENT" so the next reader does not have to rediscover
  it. `tests/test_reranking.py` pins it against the run. **Calibrated on one run and
  labelled not validated out of sample** (DEC-035, OQ-036).
- **Prevention rule:** before estimating a hosted component, work out **what the unit
  of work actually is** — per call, per document, per pair, per search unit — and get
  it from one real response's `usage`, not from the shape of the request you sent.
  All three Axis 5 cost errors (MIS-025 free-looking prices, MIS-028 search units by
  count, this one) are the same mistake: assuming the provider bills the thing we
  happened to be counting.
- **Added to preflight:** yes (item 41)

## MIS-033 — Ran an axis without pre-registering the hypothesis
- **Date:** 2026-09-24
- **Severity:** Low — no number is affected; the calibration record is.
- **What happened:** EXP-0027 (MMR) ran with no `docs/HYPOTHESES.md` entry written
  beforehand. Axis 5's runs had H-017 and H-018 committed before them; Axis 6's did
  not. The expectation plainly existed — P2-13 prioritises MMR *because* "diversity
  directly serves multi-document coverage", DEC-061 chose this axis partly on that
  ground, and the configs were built around it — so there was something to write down
  and it was not written down.
- **How it was caught:** writing the experiment file and reaching for the hypothesis
  to resolve.
- **Root cause:** the sweep was free and quick, so it was launched as soon as the code
  passed its tests. The pre-registration step is the one thing in this workflow with
  no immediate payoff, which is exactly why it needs to be mechanical rather than
  remembered.
- **Impact:** the strongest result in Axis 6 — that a diversity technique inverts on
  this corpus because gold documents cluster — arrives with **no record of whether it
  was expected**. H-019 records the miss rather than back-filling a prediction, which
  would have been worse: a hypothesis written after the fact is not evidence of
  anything except a good memory.
- **Fix applied:** none in code. A test could assert that every `axis` config has a
  matching HYPOTHESES entry before it runs, and that is worth considering, but it is
  not written unasked.
- **Prevention rule:** the hypothesis entry is written and **committed** in the same
  action as the config, before the run — not before the writeup. A free run is the
  most likely one to skip it, because nothing forces a pause.
- **Added to preflight:** yes (item 42)

## MIS-034 — A probe on one prompt licensed a model for another, and one empty completion VOIDed a 100-question run
- **Date:** 2026-09-25
- **Severity:** High — VOIDed EXP-0029 attempt 1 after 221 of ~500 paid calls (~$0.009 spent, recoverable from cache)
- **What happened:** two distinct failures, and it is worth keeping them apart.

  **(a) The model was licensed on the wrong evidence.** DEC-064 chose
  `openai/gpt-oss-20b` off a 30-call probe that used the **`contextual_chunk`** prompt
  at `max_tokens=200`. It passed cleanly: 0/10 flagged, 54 output tokens per call, no
  reasoning. I then used the same model for the **`compress_context`** prompt without
  re-probing, and that prompt behaves completely differently on the same model.
  EXP-0029 died on call ~222 with `EmptyGenerationError`: `finish_reason='length'`,
  `completion_tokens=1000`, **`reasoning_tokens=1000`** — the entire budget spent
  reasoning before a single output token.

  **(b) A per-chunk provider failure killed the whole run.** My `ContextCompressor` let
  the exception propagate, so the runner did the right thing with the wrong input and
  marked the run VOID. One passage out of 500 that could not be shortened is not a
  failure of the run.
- **How it was caught:** the run's traceback. Then, digging: the same input **succeeds
  on a retry** — 123 reasoning tokens, 170 out — so the failure is not input-specific,
  it is **non-deterministic at temperature 0**. Reading the cache showed the real
  shape: of 221 successful calls, p50 output was 102 tokens, p95 576, and **one call
  reported 32,848 completion tokens for a 60-word answer** — ~32,788 of them reasoning,
  blowing straight through `max_tokens=1000`. And `reasoning_effort` does nothing here:
  `"minimal"` and `"low"` both produced exactly 123 reasoning tokens on the same input,
  so the parameter is not being honoured by this model.
- **Root cause:** I treated "model" as the unit of validation when the unit is
  **(model, prompt)**. A reasoning model's token behaviour is a property of the task it
  is given, not of the model alone. Preflight item 11 already says to check whether a
  new model spends completion tokens on reasoning before setting its budget — I checked
  it for the prefix prompt and carried the conclusion to a prompt I had not tested.
  Preflight item 15 already says to fail at the unit that failed; I wrote the compressor
  without applying it.
- **Impact:** EXP-0029 attempt 1 VOID. ~$0.009 of the ~$0.023 compression budget spent;
  **none of it wasted** — all 221 completions are in the generation cache and replay
  free, so the re-run resumes rather than restarts. That is the cache earning its keep
  (DEC-049), and it is the only reason this cost cents instead of the whole run.
- **Fix applied:**
  1. `ContextCompressor.compress` catches a failed call per chunk, keeps the
     **retrieved text uncompressed** (the control's behaviour), and records
     `chunks_call_failed`, `call_failure_rate` and the first 20 errors on the row. The
     failed chunk's full word count is still counted in `words_out`, so the reduction
     number cannot be flattered by a failure.
  2. `ContextualChunker._prefix_for` does the same: a failed prefix call returns `""`,
     the chunk indexes as the control's chunk, and `prefix_calls_failed` /
     `prefix_call_failure_rate` go on the row. Without this, one bad completion at call
     7,000 of 8,218 would have abandoned an index build already paid for.
  3. Three tests, including that the word accounting includes the failed chunk.
- **Prevention rules:**
  - **Probe every (model, prompt) pair, not every model.** A model that behaves on one
    prompt can spend 30,000 reasoning tokens on another. Read `reasoning_tokens` off a
    real response for the *actual* prompt before committing a loop to it.
  - **A per-unit provider failure is recorded per unit and the run continues.** Only a
    failure of the run itself is VOID. If a loop of N paid calls can be killed by call
    number k, the money for the first k−1 is at risk.
  - **`reasoning_effort` is a request, not a guarantee.** Assert the reasoning-token
    count you assumed; do not infer it from the parameter you sent.
- **Added to preflight:** yes — items 42, 43 and 44.
