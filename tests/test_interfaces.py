"""P0-11 — the interfaces exist, and the runner knows nothing about WixQA."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _transitive_imports(module: str, seen: set[str] | None = None) -> set[str]:
    """Follow `rag.*` imports from a module's source, recursively."""
    seen = seen if seen is not None else set()
    if module in seen or not module.startswith("rag"):
        return seen
    seen.add(module)
    path = REPO_ROOT / (module.replace(".", "/") + ".py")
    if not path.exists():
        path = REPO_ROOT / module.replace(".", "/") / "__init__.py"
    if not path.exists():
        return seen
    for name in _imports_of(path):
        _transitive_imports(name, seen)
    return seen


def test_runner_has_no_wixqa_import_direct_or_transitive():
    """Dropping in a second benchmark must touch nothing under rag/runner/."""
    for path in (REPO_ROOT / "rag" / "runner").glob("*.py"):
        module = "rag.runner." + path.stem
        reached = _transitive_imports(module)
        assert "rag.dataset.wixqa" not in reached, (
            f"{module} reaches rag.dataset.wixqa via {sorted(m for m in reached if 'dataset' in m)}"
        )


def test_dataset_adapter_has_a_concrete_implementation():
    from rag.dataset.adapter import DatasetAdapter
    from rag.dataset.wixqa import WixQAAdapter

    adapter = WixQAAdapter()
    assert isinstance(adapter, DatasetAdapter)
    assert adapter.source_configs() == ["expertwritten", "simulated", "synthetic"]
    assert adapter.provenance()["hf_revision"]


def test_every_required_interface_exists_with_an_implementation():
    from rag.assembly import ConcatAssembler, ContextAssembler
    from rag.chunking.base import Chunker, FixedTokenChunker
    from rag.embedding.base import Embedder, OpenRouterEmbedder
    from rag.eval.judge import Judge, RagasJudge
    from rag.generation.base import Generator, OpenRouterGenerator
    from rag.retrieval.base import Retriever
    from rag.retrieval.bm25 import BM25Retriever

    for interface, impl in (
        (Chunker, FixedTokenChunker),
        (Embedder, OpenRouterEmbedder),
        (Retriever, BM25Retriever),
        (ContextAssembler, ConcatAssembler),
        (Generator, OpenRouterGenerator),
        (Judge, RagasJudge),
    ):
        assert inspect.isabstract(interface), f"{interface.__name__} should be abstract"
        assert issubclass(impl, interface)
        assert not inspect.isabstract(impl), f"{impl.__name__} should be concrete"


def test_reranker_is_interface_only_in_phase_0():
    """A reranker is technique work. None may exist without a story and a decision."""
    import rag.reranking.base as base
    from rag.reranking.base import Reranker

    assert inspect.isabstract(Reranker)
    concrete = [
        obj for _, obj in inspect.getmembers(base, inspect.isclass)
        if issubclass(obj, Reranker) and obj is not Reranker and not inspect.isabstract(obj)
    ]
    assert concrete == [], f"Phase 0 must ship no reranker implementation: {concrete}"


def test_judge_takes_the_p0_11_signature():
    from rag.eval.judge import Judge

    params = inspect.signature(Judge.score).parameters
    assert {"question", "answer", "contexts", "reference"} <= set(params)


def test_embedder_refuses_to_run_without_a_model():
    from rag.embedding.base import EmbedderConfig, OpenRouterEmbedder

    with pytest.raises(ValueError, match="no embedding model"):
        OpenRouterEmbedder(EmbedderConfig(model=""))
