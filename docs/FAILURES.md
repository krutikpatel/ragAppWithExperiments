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

- **EXP-0006** (dense control, Tier 2): **30 of 33** questions with a gold document missing
  from context were answered, 3 refused (detector v2; v1 counted 31 / 2).
- **EXP-0001 Tier 2** (BM25, Phase 0): 58 of 60.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0006 | "Im encountering an error with Wix Payments regarding region or currency." | *Troubleshooting Issues for Accepting Payments* + *About Wix Payments*: the currency/country list | A five-step currency-settings procedure citing all five retrieved articles; one of two gold docs in context | — |
| EXP-0006 | "Hoe can I restore the selection of projects for my Wix collection?" | *Restoring Collections with Backups* + *Restoring a Deleted Collection* | Portfolio-project guidance from the wrong product; one of two gold docs in context, cited | — |

### F2 — Answered an unanswerable question, with citations
No article in the corpus can answer the question; the retriever still returns five plausible
ones and the generator treats their presence as the answer. Stage: `generation` (no
refusal logic). Concentrated in **underspecified** questions.

- **EXP-0007**: 12 of 45 answered (hand count = detector v2); **10 of 15 underspecified**,
  2 of 15 post-snapshot, 0 of 15 other-platform. All 12 cited an article.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0007 | "How do I get it approved?" | Refusal / ask what "it" is | A numbered procedure for approving Online Programs members, cited | — |
| EXP-0007 | "Why was my account charged?" | Refusal / ask which charge | "Your charge is most likely from a renewal…", cited | — |
| EXP-0007 | "Which Wix Bookings features shipped after December 2024?" | Refusal: corpus snapshot is 2024-12-02 | A named feature asserted as post-December-2024, cited to an undated article | — |

### F3 — Refused with the answer in context
The gold article was retrieved (and sometimes cited); the generator declined because the
article did not match the question's wording closely enough. Stage: `generation`.

- **EXP-0006**: 2 of 67 questions with all gold in context (detector v2; the third under v1
  was a refusal phrase followed by a procedure, now counted as a hedged answer).

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

- **EXP-0007**: 7 of 33 refusals missed (21%) by detector v1. **Fixed by DEC-045**
  (`refusal-lexical-v2`): 0 of 33 missed on the same answers. v1 had also missed
  13–18 refusals per Phase 0 run through a curly-apostrophe defect.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0007 | "How do I set up abandoned cart emails in Shopify?" | Counted as refusal | "The provided articles cover Wix Stores abandoned cart emails, not Shopify…" — counted as an answer | DEC-045 |
| EXP-0007 | "How much does it cost?" | Counted as refusal | "…do not specify a general cost. Pricing information is not covered." + five citations — counted as an answer | DEC-045 |

### F7 — Prompt text echoed into the answer
The answer contains the prompt's own instruction verbatim. Stage: `generation`; fix belongs
to prompt `v2` (DEC-042 freezes `v1`).

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0007 | "How do I restore a deleted page in Squarespace?" | "The provided articles do not cover this. [what is missing]" | "…do not cover this. **Then, in one sentence, say what is missing:** They do not include…" | — |

---

### F8 — Gold is a "Request:" article; the retriever returns the how-to for the nearest existing feature
Synthetic `dev_large` questions of the form "Can I do X?" whose gold document is a
feature-request article (*Wix Editor Request: Uploading XML Files*). The control ranks
the how-to for the closest *existing* feature first (*Uploading Documents (.pdf, .doc…)*)
and the request article 6th–50th. Stage: `retrieval`; arguably `label` — which of the
two an assistant should surface is not something the label decides. 69 questions in
the control; every Axis 2 candidate without an answer-oriented query prefix fixes ~66
of them, and the control without its prefix fixes 53 (EXP-0012). Only exists on
`dev_large`: `dev` has no feature-request gold documents.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0008 | "Can I upload XML files in the Wix Editor?" | *Wix Editor Request: Uploading XML Files* | rank 29; top-1 *Uploading Documents (.pdf, .doc, .xls…)* | EXP-0009/0010/0011 (all), EXP-0012 (prefix off) |
| EXP-0008 | "Can I receive form submission notifications in Wix Inbox using Wix Forms?" | *Wix Forms Request: Receiving Form Submission Notifications…* | rank 50; top-1 *Choosing Who Gets Notified About Form Submissions* | same |
| EXP-0008 | "Can I customize email receipts in Wix Stores POS?" | *Wix Stores POS Request: Customizing Email Receipts* | rank 10; top-1 *Wix Mobile POS: Customizing Receipts* | same |

### F9 — Terse or indirect user phrasing; gold slips from rank 3–5 to 6–15
Short `dev` questions that name the goal but not the feature (*"i wish to cancel a
plan"*, *"a button that people can click and it will reveal info"*). The control has
the gold just inside the top five; any perturbation of the query side — removing the
instruct prefix (EXP-0012, −0.122 on short questions), a smaller model (EXP-0010,
−0.230 on short), truncation (EXP-0013, −0.054 on short) — pushes it just outside.
Stage: `retrieval`. The most fragile slice on `dev`, and the one where the query
instruction earns its keep.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0012 | "i wish to cancel a plan" | *Canceling a Wix Premium or Studio Plan* (control rank 3) | rank 11 without the prefix | keeping the prefix |
| EXP-0012 | "I want to use a button that people can click and it will reveal info…" | *Adding and Setting Up Collapsible Text* (rank 5) | rank 15 | keeping the prefix |
| EXP-0010 | "How to make the published changes draft?" | *Saving, Previewing and Publishing Your Site* (rank 5) | rank 48 under bge-m3 | — |
| EXP-0013 | "How do I get notified of purchases" | gold at rank 4 | rank 11 at 1024-d | — |

### F10 — Exact-term query; dense has the gold at rank 6–33 while BM25 has it at 1–5
The nine questions BM25 won in Phase 1 (H-001), seen again from the fusion side. The
query carries a product term or a phrase the gold article's title repeats nearly
verbatim (*PDF*, *header … scrolling*, *login … website designer*); dense places the
article inside its top 100 but below five near-paraphrases, and BM25 places it first
or second. Stage: `retrieval` (ranking, not recall — the gold is in the candidate
pool). Every hybrid setting in Axis 3 recovered some of these (3 at α=0.8, 7 at
α=0.6, 9 under RRF) and nothing recovers them without paying elsewhere (EXP-0014–0018).
Under the promoted dense control they remain misses.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0005 (control) | "I want to know how to add a full PDF to my portfolio site" | gold at BM25 rank 1 | dense rank 9 | hybrid at any α (EXP-0018: rank 1) — not promoted |
| EXP-0005 (control) | "I want to change the header background to black when scrolling in Wix Editor." | BM25 rank 1 | dense rank 8 | hybrid α=0.8: rank 2 — not promoted |
| EXP-0005 (control) | "do I have to give my login to a website designer to work on my site" | BM25 rank 2 | dense rank 33 | RRF: rank 4 (EXP-0014); α=0.8: still a miss |
| EXP-0005 (control) | "I need help with setting up two different emails on my website…" | BM25 rank 2 | dense rank 19 | α=0.6: rank 4; α=0.8: still a miss |

### F11 — Consensus fusion demotes a gold document the lexical half never returned
A failure of the **rejected** hybrid configurations, recorded because it is the
mechanism behind the axis's negatives and would recur in any deployment that fuses by
rank. Under RRF (EXP-0014) and weighted fusion at α ≤ 0.4 (EXP-0015/0016), a document
dense ranks first can score below any document both lists agree on, because the
missing list contributes nothing. 22 of RRF's 38 lost questions had the gold absent
from BM25's top 100; the other 16 had it at BM25 rank 16–65. Stage: `retrieval`
(fusion). At α=0.6 the same documents land at fused rank 6–10 (EXP-0017); at α=0.8
they stay in the top five except for four rank-5 → rank-6 cases (EXP-0018).

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0014 (RRF) | "how to add more static pages to a Wix website" | gold at dense rank 1; BM25 absent | RRF rank 20 | α=0.8 (rank stays 1); i.e. not fusing by rank |
| EXP-0014 (RRF) | "how can I find my domain information purchased from Wix" | dense 1; BM25 absent | RRF rank 36 | α=0.8 |
| EXP-0014 (RRF) | "What should I do if I'm having issues making a payment for a Wix service?" | dense 1; BM25 absent | RRF rank 29 | α=0.8 |
| EXP-0017 (α=0.6) | "Im interested in finding a Wix Partner to help redesign and update my existing website." | dense 3; BM25 absent | fused rank 6 | α=0.8 |
| EXP-0018 (α=0.8) | "How to make the published changes draft?" | dense 5; BM25 65 | fused rank 6 | — (also F9) |

### F12 — Gold article's evidence split across chunks; its best piece loses to another article's best
A failure of the **rejected** Axis 1 chunkers, recorded because the mechanism explains
the whole axis. Document score is the max over the article's chunks (DEC-040 pooling),
so cutting an article into three or thirty pieces makes every piece weaker while rival
articles keep one strong piece. The candidate pool then holds several chunks of the
gold article — the retriever "sees" it — and still ranks it below five other documents.
Stage: `retrieval` (pooling/granularity interaction). Worse the finer the chunks:
mean indexed length 309 words → 0.720 strict recall@5, 124 → 0.695, 123 → 0.675,
12 → 0.530 on `dev`.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0021 (semantic) | "How do I remove the ribbon from one plan on the plan card list?" | golds at control ranks 1, 3 | ranks 1, 7 — with 7 and 4 chunks of the two golds in the 50-chunk pool | the control's coarse chunks |
| EXP-0020 (parent-doc) | "Is domain privacy included in the price of purchasing the domain…" | control rank 1 | rank 8, with 5 children of the gold in the pool | the control |
| EXP-0019 (sentence-window) | "I need to know how to prevent an item in my CMS collection from being published" | control rank 4 | rank 70; **0** gold sentences in the pool | the control |
| EXP-0019 (sentence-window) | "How to make the published changes draft?" | control rank 5 | absent from the top 100 | the control |

### F13 — Rank-5 gold slips to rank 6 on a pure re-embed (the floor)
Not a technique failure: the measured cost of embedding the same text again on a hosted
provider. Two questions of 200, both single-gold, both exactly on the boundary
(EXP-0023). Stage: `retrieval`. Recorded so that no future axis attributes two flips to
a technique.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0023 | "how to see my website ip address" | rank 5 under `be04` | rank 6 after re-embedding the identical corpus | — (irreducible; ~1 point of strict recall@5) |
| EXP-0023 | "how to cancel a payment for a Wix Premium plan" | rank 5 | rank 6 | — |

### F14 — Cross-encoder confidently demotes a gold the dense retriever had at rank 1–5
The reranker's losses are not near-misses. On 28 questions of 200 the gold left the
top 5 entirely, typically by 6 to 16 places, and three of the six read by hand started
at **rank 1**. These are well-formed questions the dense retriever had already
answered; reading the question against the passage produced a confident wrong call.
Stage: `reranking`. The mirror image (F15) is the same mechanism getting it right.

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0024 | "how to add more static pages to a Wix website" | rank 1 | rank 8 | — |
| EXP-0024 | "Is domain privacy included in the price of purchasing the domain and the yearly charge?" | rank 1 | rank 7 | — |
| EXP-0024 | "How can I add a personalized name to my automated emails? I was advised to use dynamic values for this." | rank 1 | rank 7 | — |
| EXP-0024 | "How to make the published changes draft?" | rank 5 | rank 20 | — |
| EXP-0024 | "How can I offer free shipping for a sample option of a product while the main product does not have free shipping?" | rank 5 | rank 21 | — |
| EXP-0024 | "Im encountering an issue with my payment settings… payouts are on hold." (2 golds) | ranks 2, 3 | ranks 2, 15 | — |

### F15 — Loosely-phrased question; dense buries the gold and the cross-encoder rescues it
The counterpart to F14 and the only thing in Axis 5 that clearly worked. Golds sitting
at rank 6 to 33 under dense retrieval came back to rank 1 or 2. The 17 gains skew
towards typos, non-English phrasing and complaints-rather-than-questions — the cases
where comparing two independently-made vectors does badly. Whether that pattern is
real or a story fitted to 45 questions is OQ-037; the `source:expertwritten` vs
`source:simulated` slices do not separate, which argues against it.
Stage: `retrieval` (recovered at `reranking`).

| Run | Question | Expected | Got | Fixed by |
|---|---|---|---|---|
| EXP-0024 | "do I have to give my login to a website designer to work on my site" | rank 33 under dense | rank 2 | reranking (EXP-0024) |
| EXP-0024 | "i cant create a new gallery in my website. it only refers to portfolio templates" | rank 24 | rank 1 | reranking (EXP-0024) |
| EXP-0024 | "Hoe can I restore the selection of projects for my Wix collection?" (2 golds) | ranks 6, 20 | ranks 1, 2 | reranking (EXP-0024) |
| EXP-0024 | "I am trying to cancel my Premium subscription within the 14-day period, but I cant find the cancel feature." | rank 6 | rank 1 | reranking (EXP-0024) |

## Counts by run

| Run | F1 answered on miss | F2 answered unanswerable | F3 refused with gold | F4 neighbour cited | F5 step cov 0 with gold | F6 detector miss | F7 prompt echo |
|---|---|---|---|---|---|---|---|
| EXP-0006 (dev sub100) | 30 / 33 | — | 2 / 67 | not swept | 7 / 21 (2 read) | not swept | 0 |
| EXP-0007 (unanswerable) | — | 12 / 45 | — | — | — | 7 / 33 (v1) → 0 (v2) | 2 / 45 |

Retrieval-only categories (F8–F11) are counted from `rag diff` flips, not sampled:

| Run | F10 exact-term, BM25 rank ≤5 / dense 6–33 | F11 gold demoted by fusion (lost vs dense) |
|---|---|---|
| EXP-0014 (RRF) | 9 recovered of 9 | 38 (22 with gold absent from BM25's top 100) |
| EXP-0016 (α=0.4) | — (14 gained, not read one by one) | 40 |
| EXP-0017 (α=0.6) | 7 recovered | 16 (8 absent from BM25) |

Axis 5 (EXP-0024), counted from `rag compare` flips on strict recall@5, `dev` n=200:

| Run | F14 gold demoted out of top 5 | F15 buried gold rescued into top 5 | net |
|---|---|---|---|
| EXP-0024 (cohere/rerank-v3.5, 50 → 5) | 28 | 17 | −11 (Δ −0.055, p = 0.139) |

Counted across all 160 single-gold questions rather than only the top-5 boundary, the
two categories are near-symmetric: the gold moved up a rank band for **40** questions
and down for **39**. F14 and F15 are the same mechanism, and on this corpus it is a
coin flip that costs $0.00117 and 900 ms per query to toss.
| EXP-0018 (α=0.8) | 3 recovered | 4 (all rank 5 → 6) |

Axis 1 (chunking), same method:

| Run | F10 exact-term questions recovered | F12 gold diluted across chunks (lost vs control) |
|---|---|---|
| EXP-0020 (parent-document) | 4 of the 12 gains | 17 |
| EXP-0021 (semantic) | 4 of the 6 gains | 15 |
| EXP-0022 (structure) | 3 of the 6 gains | 17 |
| EXP-0019 (sentence-window) | 6 of the 10 gains | 48 (21 past rank 10; 1 out of the top 100) |
| EXP-0023 (control re-embed) | — | 2 (F13, the floor) |

"Not swept" means the category was found by reading a sample, not counted over the run.
