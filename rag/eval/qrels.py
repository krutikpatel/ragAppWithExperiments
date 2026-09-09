"""Document-level qrels and runs — P0-05.

Emitted in the nested-dict form that both `ranx` (`Qrels.from_dict` /
`Run.from_dict`) and `pytrec_eval` accept:

    qrels = {question_id: {doc_id: 1}}
    run   = {question_id: {doc_id: score}}

Relevance is binary. WixQA marks a document as gold or not; there are no graded
judgments to invent, and inventing them would put unmeasured numbers into the
metrics. Metric computation itself is P0-06 and goes through `ranx`/`pytrec_eval`
rather than being hand-rolled here.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from rag.retrieval.base import RetrievalResult


def qrels_from_split(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Build binary document-level qrels from a split.

    Questions with no gold document (the unanswerable set) are omitted: a query
    with an empty relevant set is undefined for recall and nDCG, and `ranx` would
    otherwise average zeros into the retrieval metrics. Refusal behaviour on those
    questions is scored separately in P0-07.
    """
    qrels: dict[str, dict[str, int]] = {}
    for row in frame.itertuples():
        gold = list(row.gold_doc_ids)
        if not gold:
            continue
        qrels[row.question_id] = {doc_id: 1 for doc_id in gold}
    return qrels


def run_from_results(
    results: Iterable[RetrievalResult], *, rank_scores: bool = True
) -> dict[str, dict[str, float]]:
    """Build a run dict from pooled document rankings.

    By default the raw pooled scores are replaced with strictly decreasing
    rank-derived scores, `1 / (rank + 1)`.

    This is not cosmetic. Pooled scores tie often — with `max` pooling every
    document whose best chunk scored the same value ties exactly — and our pooling
    rule breaks those ties on the rank of the document's best chunk (see
    `rag/retrieval/pooling.py`). An IR library re-sorts by score and breaks ties by
    its own undocumented rule, so it would score a *different* ordering than the one
    the system actually returns and the one recorded in `run_questions`. A question
    could then show its gold document at rank 4 in the stored ranking and score zero
    recall@5. That is not a metric measuring the system; it is two orderings
    disagreeing. See MIS-003.

    Pass `rank_scores=False` only to inspect the raw pooled scores. Every
    rank-based metric here — recall, nDCG, reciprocal rank — depends on order
    alone, so the substitution cannot change a correctly-ordered result.
    """
    run: dict[str, dict[str, float]] = {}
    for result in results:
        if rank_scores:
            run[result.question_id] = {
                doc_id: 1.0 / (rank + 1) for rank, (doc_id, _) in enumerate(result.docs)
            }
        else:
            run[result.question_id] = {doc_id: float(score) for doc_id, score in result.docs}
    return run


def check_run_against_qrels(
    run: dict[str, dict[str, float]], qrels: dict[str, dict[str, int]]
) -> dict[str, Any]:
    """Report questions present in one side and not the other.

    A silently missing question is scored as a total miss by every IR library, so
    a shrinking run set reads as a quality drop. This makes that visible instead.
    """
    run_ids, qrel_ids = set(run), set(qrels)
    return {
        "n_qrels": len(qrel_ids),
        "n_run": len(run_ids),
        "missing_from_run": sorted(qrel_ids - run_ids),
        "unjudged_in_run": sorted(run_ids - qrel_ids),
        "aligned": run_ids == qrel_ids,
    }
