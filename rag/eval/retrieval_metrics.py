"""Retrieval metrics — P0-06.

Everything is computed at document level, through `ranx`, over binary qrels. The
only arithmetic done here is applying definitions that `ranx` does not ship as
named metrics; no recall, nDCG or reciprocal rank is hand-rolled.

Two definitions need saying out loud, because the words are used loosely elsewhere:

**Strict recall@k** — the fraction of questions where *all* gold documents appear
in the top k. This is the headline. 79 of the 400 human-grounded questions need two
or three documents, and a system that reliably finds one of two looks healthy under
any other definition while being unable to answer the question.

**Loose recall@k** — the fraction where *any* gold document appears. `ranx` calls
this `hit_rate`.

`ranx`'s own `recall@k` is neither: it is the mean per-question fraction of gold
documents found. It is used here only as the input to strict recall, which is the
count of questions whose fraction reached 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ranx import Qrels, Run, evaluate

K_VALUES = (1, 3, 5, 10, 20)
NDCG_K = 10


@dataclass(frozen=True)
class RetrievalMetrics:
    aggregate: dict[str, float]
    per_question: dict[str, dict[str, float]]
    n_questions: int
    n_single_gold: int
    notes: dict[str, Any] = field(default_factory=dict)


def _ordered_question_ids(qrels: Qrels) -> list[str]:
    """The question order `ranx` uses for per-query result arrays.

    `ranx` sorts query ids internally, so a per-query array is NOT in the order the
    input dict was built. Reading the order back off the object rather than assuming
    it is what keeps per-question rows attached to the right question;
    `tests/test_retrieval_metrics.py` pins this so a `ranx` upgrade that changes it
    fails loudly instead of silently misattributing every per-question score.
    """
    return list(qrels.qrels.keys())


def _per_query(qrels: Qrels, run: Run, metric: str) -> dict[str, float]:
    scores = evaluate(qrels, run, metric, return_mean=False)
    return dict(zip(_ordered_question_ids(qrels), (float(s) for s in scores), strict=True))


def evaluate_retrieval(
    qrels_dict: dict[str, dict[str, int]],
    run_dict: dict[str, dict[str, float]],
    *,
    k_values: tuple[int, ...] = K_VALUES,
    ndcg_k: int = NDCG_K,
) -> RetrievalMetrics:
    """Compute document-level retrieval metrics and their per-question values."""
    if not qrels_dict:
        raise ValueError("no qrels: nothing to score")

    missing = sorted(set(qrels_dict) - set(run_dict))
    if missing:
        raise ValueError(
            f"{len(missing)} judged questions are absent from the run "
            f"(first: {missing[:3]}). Every IR library scores a missing question as "
            "a total miss, so this would read as a quality drop. Fix the run."
        )

    qrels = Qrels(dict(qrels_dict))
    run = Run({qid: run_dict[qid] for qid in qrels_dict})

    per_question: dict[str, dict[str, float]] = {qid: {} for qid in qrels_dict}
    aggregate: dict[str, float] = {}

    for k in k_values:
        fraction_found = _per_query(qrels, run, f"recall@{k}")
        hit = _per_question_hit(qrels, run, k)
        for qid in per_question:
            per_question[qid][f"strict_recall@{k}"] = float(fraction_found[qid] >= 1.0)
            per_question[qid][f"loose_recall@{k}"] = hit[qid]
        aggregate[f"strict_recall@{k}"] = _mean(
            per_question, f"strict_recall@{k}"
        )
        aggregate[f"loose_recall@{k}"] = _mean(per_question, f"loose_recall@{k}")

    ndcg = _per_query(qrels, run, f"ndcg@{ndcg_k}")
    for qid, value in ndcg.items():
        per_question[qid][f"ndcg@{ndcg_k}"] = value
    aggregate[f"ndcg@{ndcg_k}"] = _mean(per_question, f"ndcg@{ndcg_k}")

    mrr_value, rr_per_question, n_single = mrr_single_gold(qrels_dict, run_dict)
    for qid, value in rr_per_question.items():
        per_question[qid]["reciprocal_rank"] = value
    if mrr_value is not None:
        aggregate["mrr_single_gold"] = mrr_value
    aggregate["mrr_single_gold_n"] = float(n_single)

    return RetrievalMetrics(
        aggregate=aggregate,
        per_question=per_question,
        n_questions=len(qrels_dict),
        n_single_gold=n_single,
        notes={
            "k_values": list(k_values),
            "relevance": "binary",
            "granularity": "document",
            "mrr_scope": "single-gold-doc subset only",
        },
    )


def _per_question_hit(qrels: Qrels, run: Run, k: int) -> dict[str, float]:
    return _per_query(qrels, run, f"hit_rate@{k}")


def _mean(per_question: dict[str, dict[str, float]], metric: str) -> float:
    values = [row[metric] for row in per_question.values()]
    return sum(values) / len(values)


def mrr_single_gold(
    qrels_dict: dict[str, dict[str, int]], run_dict: dict[str, dict[str, float]]
) -> tuple[float | None, dict[str, float], int]:
    """MRR over the single-gold-document subset only.

    Reciprocal rank asks "where is *the* answer". With two or three gold documents
    there is no single answer to locate, and averaging over a mixed population
    produces a number whose meaning depends on the multi-doc proportion of the
    split rather than on the retriever. So the subset is explicit, its size is
    reported alongside, and the full-set version is refused outright.
    """
    single = {qid: rel for qid, rel in qrels_dict.items() if len(rel) == 1}
    if not single:
        return None, {}, 0

    qrels = Qrels(dict(single))
    run = Run({qid: run_dict[qid] for qid in single})
    per_question = _per_query(qrels, run, "mrr")
    mean = sum(per_question.values()) / len(per_question)
    return mean, per_question, len(single)


def refuse_full_set_mrr(qrels_dict: dict[str, dict[str, int]]) -> None:
    """Raise if asked for MRR over a set containing multi-gold questions."""
    multi = [qid for qid, rel in qrels_dict.items() if len(rel) > 1]
    if multi:
        raise ValueError(
            f"MRR is not meaningful over this set: {len(multi)} of {len(qrels_dict)} "
            "questions have more than one gold document. Use mrr_single_gold, which "
            "reports the subset size alongside the value."
        )
