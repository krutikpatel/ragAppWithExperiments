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
