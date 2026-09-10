"""P0-07 / P0-11 — Ragas stays behind the Judge interface.

Ragas has drifted from a RAG-eval library toward a general LLM-app eval product with
its own dataset and experiment abstractions. Adopting those would fork the Phase 0
results store and break `rag diff`. Confining the import to one module means a Ragas
major-version change, or a swap to another judge library, is a one-file change.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {REPO_ROOT / "rag" / "eval" / "judge.py"}


def _python_files() -> list[Path]:
    return [
        path
        for path in (REPO_ROOT / "rag").rglob("*.py")
        if "__pycache__" not in path.parts
    ]


# Matches `import ragas...` and `from ragas... import ...`. Mentions of the word in
# comments, and provenance column names like `ragas_version`, are not imports and
# are allowed anywhere.
_RAGAS_IMPORT = re.compile(r"^\s*(?:import\s+ragas|from\s+ragas[\w.]*\s+import)", re.MULTILINE)


def test_ragas_is_imported_only_by_the_judge_module():
    offenders = [
        path.relative_to(REPO_ROOT)
        for path in _python_files()
        if path not in ALLOWED and _RAGAS_IMPORT.search(path.read_text())
    ]
    assert not offenders, (
        f"Ragas referenced outside rag/eval/judge.py: {offenders}. "
        "Route it through the Judge interface instead."
    )


def test_ragas_dataset_and_experiment_abstractions_are_not_used():
    """We call metrics and write scores to our own store. Nothing more."""
    source = (REPO_ROOT / "rag" / "eval" / "judge.py").read_text()
    for forbidden in ("EvaluationDataset", "ragas.dataset_schema", "from ragas import evaluate"):
        assert forbidden not in source, (
            f"{forbidden} adopts Ragas's dataset/experiment layer, which duplicates "
            "the Phase 0 results store"
        )


def test_judge_records_the_provenance_the_store_needs():
    from rag.eval.judge import JudgeConfig, judge_provenance

    provenance = judge_provenance(JudgeConfig(model="anthropic/claude-sonnet-5"))
    for field in (
        "judge_model",
        "judge_family",
        "judge_temperature",
        "ragas_version",
        "metric_prompt_versions",
        "answer_correctness_weights",
    ):
        assert field in provenance, field


def test_metric_fingerprint_changes_when_ragas_metric_code_changes():
    """The fingerprint is what catches a silent prompt revision on upgrade."""
    from rag.eval.judge import metric_fingerprint

    faithfulness = metric_fingerprint("ragas.metrics.collections.faithfulness")
    correctness = metric_fingerprint("ragas.metrics.collections.answer_correctness")
    assert faithfulness.startswith("sha256:")
    assert faithfulness != correctness


def test_answer_relevance_is_skipped_without_an_embedding_model():
    """OpenRouter serves no embeddings, so this criterion cannot run yet (DEC-022)."""
    from rag.eval.judge import CRITERIA, JudgeConfig

    config = JudgeConfig(model="anthropic/claude-sonnet-5")
    assert "answer_relevance" in CRITERIA
    assert "answer_relevance" not in config.criteria
    assert config.skipped_criteria == ("answer_relevance",)


def test_judge_family_is_derived_from_the_model_id():
    from rag.eval.judge import model_family

    assert model_family("openai/gpt-5-nano") == "openai"
    assert model_family("anthropic/claude-sonnet-5") == "anthropic"


def test_answer_relevance_is_available_once_an_embedding_model_is_set():
    """DEC-026: it is gated on configuration, not on OpenRouter's capabilities."""
    from rag.eval.judge import CRITERIA, JudgeConfig

    configured = JudgeConfig(
        model="deepseek/deepseek-v3.2", embedding_model="baai/bge-m3"
    )
    assert configured.criteria == CRITERIA
    assert configured.skipped_criteria == ()


def test_embeddings_backend_is_wired_rather_than_stubbed():
    """MIS-005 regression: `_embeddings` used to raise on a false premise."""
    import inspect

    from rag.eval.judge import RagasJudge

    source = inspect.getsource(RagasJudge._embeddings)
    assert "NotImplementedError" not in source
    assert "OpenAIEmbeddings" in source
