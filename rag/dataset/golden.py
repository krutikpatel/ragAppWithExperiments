"""The golden CI slice — P3-03.

A fixed, expert-labelled question set for the Phase 3 gate, taken from WixQA's existing
verified pairs with zero manual labelling. Selection is scripted and seeded; nothing is
hand-picked by looking at pass/fail outcomes. The one stratum defined by an outcome —
questions the Phase 2 closing run answered WITHOUT the gold document in its context —
is defined that way by the story, is taken whole, and is the reason the faithfulness
eval exists (Phase 3 fact 2).

Strata are exclusive and assigned in this order:

  answered_without_gold  every such question in the Phase 2 closing dev Tier 2 run
  multi_doc              ≥ 2 gold documents, seeded sample
  single_doc             1 gold document, seeded sample
  unanswerable           from the authored refusal set, seeded, equal per `reason`

Sizes and seed are DEC-074. Any change is a new version (golden_v2), a DEC entry and
a baseline recompute — never an edit of v1.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pandas as pd

from rag.hashing import hash_records
from rag.paths import GOLDEN_DIR

VERSION = "golden_v1"
SEED = 20260928
# The Phase 2 closing dev Tier 2 run (EXP-0006 replicate audited in DEC-070): the
# source of the answered-without-gold stratum.
AWG_SOURCE_RUN = "run_20260913_205058_dc03"
N_MULTI = 20
N_SINGLE = 33
N_UNANSWERABLE_PER_REASON = 5
FIELDS = ["question_id", "question", "reference_answer", "article_ids", "stratum",
          "source_config", "n_gold_docs", "reason"]


def golden_path(version: str = VERSION) -> Path:
    return GOLDEN_DIR / f"{version}.jsonl"


def answered_without_gold(store: Any, run_id: str = AWG_SOURCE_RUN) -> list[str]:
    """Question ids whose gold was NOT in the generator's context and whose answer was
    not a refusal (refusals recounted under the current detector, MIS-038)."""
    from rag.eval.generation_metrics import is_refusal

    ids = []
    for qid, row in store.get_questions(run_id).items():
        metrics = json.loads(row["metrics_json"])
        if metrics.get("gold_in_context") == 0 and not is_refusal(row["generated_answer"] or ""):
            ids.append(qid)
    return sorted(ids)


def _sample(ids: list[str], n: int, rng: random.Random) -> list[str]:
    if n > len(ids):
        raise ValueError(f"asked for {n} from a pool of {len(ids)}")
    return sorted(rng.sample(sorted(ids), n))


def select_golden(dev: pd.DataFrame, unanswerable: pd.DataFrame, awg_ids: list[str],
                  *, seed: int = SEED) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    dev = dev.set_index("question_id")
    missing = sorted(set(awg_ids) - set(dev.index))
    if missing:
        raise ValueError(f"answered-without-gold ids not in dev: {missing[:3]}")
    n_gold = dev["n_gold_docs"].astype(int)
    rest = [q for q in dev.index if q not in set(awg_ids)]
    multi = _sample([q for q in rest if n_gold[q] >= 2], N_MULTI, rng)
    single = _sample([q for q in rest if n_gold[q] == 1], N_SINGLE, rng)

    rows = []
    for stratum, ids in (("answered_without_gold", sorted(awg_ids)), ("multi_doc", multi), ("single_doc", single)):
        for q in ids:
            r = dev.loc[q]
            rows.append({
                "question_id": q, "question": str(r["question"]), "reference_answer": str(r["answer"]),
                "article_ids": [str(x) for x in r["gold_doc_ids"]], "stratum": stratum,
                "source_config": str(r["source_config"]), "n_gold_docs": int(r["n_gold_docs"]), "reason": "",
            })
    for reason in sorted(unanswerable["reason"].unique()):
        pool = unanswerable[unanswerable["reason"] == reason]
        for q in _sample(list(pool["question_id"]), N_UNANSWERABLE_PER_REASON, rng):
            r = pool[pool["question_id"] == q].iloc[0]
            rows.append({
                "question_id": q, "question": str(r["question"]), "reference_answer": "",
                "article_ids": [], "stratum": "unanswerable", "source_config": "unanswerable",
                "n_gold_docs": 0, "reason": str(reason),
            })
    return rows


def golden_hash(rows: list[dict[str, Any]]) -> str:
    return hash_records(rows, sort_key="question_id", fields=FIELDS)


def write_golden(rows: list[dict[str, Any]], path: Path | None = None) -> Path:
    path = path or golden_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def load_golden(version: str = VERSION) -> list[dict[str, Any]]:
    return [json.loads(line) for line in golden_path(version).read_text().splitlines() if line]


def build_golden() -> list[dict[str, Any]]:
    """Re-derive the slice from the frozen splits and the results store."""
    from rag.dataset.loader import load_split
    from rag.runner.store import ResultsStore

    with ResultsStore() as store:
        awg = answered_without_gold(store)
    return select_golden(load_split("dev"), load_split("unanswerable"), awg)
