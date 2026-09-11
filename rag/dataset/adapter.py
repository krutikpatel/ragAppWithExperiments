"""DatasetAdapter — P0-11.

Maps a source benchmark onto the harness's internal row shape. The runner never
imports anything benchmark-specific: it reads frozen parquet splits through
`rag.dataset.loader`, and those splits are built by an adapter. Dropping in a second
benchmark means writing one adapter and freezing its splits — nothing in `rag/runner/`
changes. `tests/test_interfaces.py` asserts the runner has no WixQA import, direct or
transitive.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QARow:
    """One evaluation question in the harness's own shape."""

    question_id: str
    question: str
    answer: str
    gold_doc_ids: list[str]
    source_config: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def n_gold_docs(self) -> int:
        return len(self.gold_doc_ids)

    def as_record(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "answer": self.answer,
            "gold_doc_ids": list(self.gold_doc_ids),
            "source_config": self.source_config,
            "n_gold_docs": self.n_gold_docs,
        }


class DatasetAdapter(ABC):
    """Turns one source dataset into `QARow`s and one corpus into documents.

    Implementations own every benchmark-specific detail — field names, pinned
    revisions, licence — and expose none of it past this interface.
    """

    name: str

    @abstractmethod
    def source_configs(self) -> list[str]:
        """The question sets this adapter can load, by internal name."""

    @abstractmethod
    def load_questions(self, source_config: str) -> list[QARow]:
        """Load one question set, sorted by `question_id`."""

    @abstractmethod
    def provenance(self) -> dict[str, Any]:
        """Whatever pins this dataset: revision, snapshot date, licence, citation."""
