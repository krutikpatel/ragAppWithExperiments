# Failures

A taxonomy of queries the system answers badly, built from the worst-scoring questions of
each evaluation run. Categories emerge from the data; none was written before a run showed
it. Every entry names the run it was read from, what was expected, what came back, and which
stage failed. "Fixed by" stays empty until a later `VALID` experiment changes the outcome
on that question.

Judged scores are not used to pick or explain entries (DEC-037: 12% of per-question judged
scores move by a quarter point on identical input). Entries come from deterministic metrics
and from reading the answer.

Stages: `retrieval` (gold not in context) · `generation` (gold in context, answer wrong or
withheld) · `format` (answer content plausible, scoring failed on shape) · `metric` (the
measurement is wrong, not the system).

---

## Categories

### F1 — Answered on a retrieval miss
The gold article was not retrieved; the generator answered from whatever five articles it
was given, with citations. The most common failure by count. Stage: `retrieval`, made
invisible by `generation`.

- **EXP-0006** (dense control, Tier 2): **31 of 33** questions with a gold document missing
  from context were answered, 2 refused.
- **EXP-0001 Tier 2** (BM25, Phase 0): 58 of 60.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0006 | "Im encountering an error with Wix Payments regarding region or currency." | *Troubleshooting Issues for Accepting Payments* + *About Wix Payments*: the currency/country list | A five-step currency-settings procedure citing all five retrieved articles; one of two gold docs in context | — |
| EXP-0006 | "Hoe can I restore the selection of projects for my Wix collection?" | *Restoring Collections with Backups* + *Restoring a Deleted Collection* | Portfolio-project guidance from the wrong product; one of two gold docs in context, cited | — |

### F2 — Answered an unanswerable question, with citations
No article in the corpus can answer the question; the retriever still returns five plausible
ones and the generator treats their presence as the answer. Stage: `generation` (no
refusal logic). Concentrated in **underspecified** questions.

- **EXP-0007**: 12 of 45 answered (hand count); **10 of 15 underspecified**, 2 of 15
  post-snapshot, 0 of 15 other-platform. 11 of the 12 cited an article.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0007 | "How do I get it approved?" | Refusal / ask what "it" is | A numbered procedure for approving Online Programs members, cited | — |
| EXP-0007 | "Why was my account charged?" | Refusal / ask which charge | "Your charge is most likely from a renewal…", cited | — |
| EXP-0007 | "Which Wix Bookings features shipped after December 2024?" | Refusal: corpus snapshot is 2024-12-02 | A named feature asserted as post-December-2024, cited to an undated article | — |

### F3 — Refused with the answer in context
The gold article was retrieved (and sometimes cited); the generator declined because the
article did not match the question's wording closely enough. Stage: `generation`.

- **EXP-0006**: 3 of 67 questions with all gold in context.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0006 | "…adjusting the page height in the Wix Editor for a page without a footer." | Steps from *Changing the Length of Your Page* (in context, cited) | "The provided articles do not cover this exact issue", then a paraphrase of what the article says | — |
| EXP-0006 | "…refund policy for canceling my Premium Light account." | 14-day money-back guarantee from *Requesting a Refund for a Premium or Studio Plan* (rank 2) | Refusal: articles do not name "Premium Light" | — |
| EXP-0006 | "…my documents arent being accepted." (Wix Payments verification) | Document requirements from *Guidelines for Uploading Documentation* (in context) | Refusal: no "troubleshooting steps for rejected uploads" | — |

### F4 — Cited the neighbour, not the gold
Gold in context; the generator cited a topically-adjacent retrieved article instead (or as
well). Citation precision drops; the answer text is often fine. Stage: `generation`, and
arguably `metric` — the reference's choice of article is one of several that say the same
thing.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0006 | "I want to know more about the 'Right Click Protect App'…" | *Protecting Your Site's Content* (rank 5) | Cited *Adding and Setting Up the Right Click Protect App* (rank 2); precision 0 | — |
| EXP-0006 | "Im interested in finding a Wix Partner to help redesign…" | *Hiring a Wix Professional* (rank 3) | Cited three other retrieved articles; precision 0 | — |
| EXP-0005 (dense, Tier 1) | "…add a full PDF to my portfolio site" | *PDF Viewer App* — BM25 rank 1 | Dense rank 9; one of nine questions where dense lost to an exact term | — |

### F5 — Step coverage zero on a plausible procedure
Gold in context, answer is a numbered procedure, coverage 0.0. Two sub-shapes: the reference's
steps are nested under headings the matcher does not see, or the reference is prose and its
`n_reference_steps` came from an unrelated list. Stage: `format` / `metric` (OQ-007).

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0006 | "…set up all available POS solutions in the UK" | "Step 1 \| Download the Wix app…" per provider | A list keyed by provider with steps nested beneath; matcher found none | — |
| EXP-0006 | "…updating a PDF on my website using the dashboard CMS…" | Prose about syncing sandbox to live | A six-step sandbox-sync procedure, cited correctly; coverage 0.0 against a non-procedural reference | — |

### F6 — Detector misses a refusal
The generator refused in its own words and the lexical detector counted it as an answer.
Stage: `metric`. Tracked as OQ-008.

- **EXP-0007**: 7 of 33 refusals missed (21%). **EXP-0006**: not swept by hand.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0007 | "How do I set up abandoned cart emails in Shopify?" | Counted as refusal | "The provided articles cover Wix Stores abandoned cart emails, not Shopify…" — counted as an answer | — |
| EXP-0007 | "How much does it cost?" | Counted as refusal | "…do not specify a general cost. Pricing information is not covered." + five citations — counted as an answer | — |

### F7 — Prompt text echoed into the answer
The answer contains the prompt's own instruction verbatim. Stage: `generation`; fix belongs
to prompt `v2` (DEC-042 freezes `v1`).

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0007 | "How do I restore a deleted page in Squarespace?" | "The provided articles do not cover this. [what is missing]" | "…do not cover this. **Then, in one sentence, say what is missing:** They do not include…" | — |

---

## Counts by run

| Run | F1 answered on miss | F2 answered unanswerable | F3 refused with gold | F4 neighbour cited | F5 step cov 0 with gold | F6 detector miss | F7 prompt echo |
|---|---|---|---|---|---|---|---|
| EXP-0006 (dev sub100) | 31 / 33 | — | 3 / 67 | not swept | 7 / 21 (2 read) | not swept | 0 |
| EXP-0007 (unanswerable) | — | 12 / 45 | — | — | — | 7 / 33 | 2 / 45 |

"Not swept" means the category was found by reading a sample, not counted over the run.
