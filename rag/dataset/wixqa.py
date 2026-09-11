"""Loading the WixQA question-answer configs from the pinned revision.

Only split construction reads this. Once splits are frozen, evaluation reads
parquet artifacts, never HuggingFace.
"""

from __future__ import annotations

from typing import Any

from rag.corpus.freeze import HF_DATASET, HF_REVISION, KB_SNAPSHOT_DATE
from rag.dataset.adapter import DatasetAdapter, QARow
from rag.hashing import short_id

QA_CONFIGS = {
    "expertwritten": "wixqa_expertwritten",
    "simulated": "wixqa_simulated",
    "synthetic": "wixqa_synthetic",
}


def question_id(source_config: str, question: str, gold_doc_ids: list[str]) -> str:
    """Stable id for a question, independent of row order or split membership."""
    return short_id(source_config, question, "|".join(sorted(gold_doc_ids)))


def load_qa_config(source_config: str) -> list[dict[str, Any]]:
    """Load one QA config into internal row dicts, sorted by question_id."""
    from datasets import load_dataset

    hf_config = QA_CONFIGS[source_config]
    dataset = load_dataset(HF_DATASET, hf_config, revision=HF_REVISION, split="train")

    rows: list[dict[str, Any]] = []
    for row in dataset:
        gold = list(row["article_ids"])
        rows.append(
            {
                "question_id": question_id(source_config, row["question"], gold),
                "question": row["question"],
                "answer": row["answer"],
                "gold_doc_ids": gold,
                "source_config": source_config,
                "n_gold_docs": len(gold),
            }
        )
    rows.sort(key=lambda r: r["question_id"])
    return rows


class WixQAAdapter(DatasetAdapter):
    """The WixQA benchmark (Wix.com AI Research, arXiv:2505.08643, MIT)."""

    name = "wixqa"

    def source_configs(self) -> list[str]:
        return list(QA_CONFIGS)

    def load_questions(self, source_config: str) -> list[QARow]:
        return [
            QARow(
                question_id=row["question_id"],
                question=row["question"],
                answer=row["answer"],
                gold_doc_ids=list(row["gold_doc_ids"]),
                source_config=row["source_config"],
                metadata={"hf_config": QA_CONFIGS[source_config]},
            )
            for row in load_qa_config(source_config)
        ]

    def provenance(self) -> dict[str, Any]:
        return {
            "hf_dataset": HF_DATASET,
            "hf_revision": HF_REVISION,
            "kb_snapshot_date": KB_SNAPSHOT_DATE,
            "license": "MIT",
            "citation": "Cohen et al. (2025), WixQA, arXiv:2505.08643",
        }
