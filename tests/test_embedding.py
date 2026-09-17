"""P1-04 — prefixes are applied per family, the index key is the provenance tuple,
and the dense retriever is deterministic and cached."""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from rag.chunking.base import FixedTokenChunker
from rag.chunking.index_map import ChunkIndex
from rag.embedding.base import (
    Embedder,
    EmbedderConfig,
    SentenceTransformersEmbedder,
    infer_prefix_convention,
    resolve_prefix_convention,
)
from rag.retrieval.dense import DenseRetriever, index_key


class FakeEmbedder(Embedder):
    """Deterministic bag-of-words vectors; records what it was asked to embed."""

    name = "fake"

    def __init__(self, config: EmbedderConfig) -> None:
        super().__init__(config)
        self.calls: list[list[str]] = []

    def _embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        out = []
        for text in texts:
            vec = [0.0] * 32
            for token in text.lower().split():
                vec[int(hashlib.sha256(token.encode()).hexdigest(), 16) % 32] += 1.0
            out.append(vec)
        return out


# --- prefixes ------------------------------------------------------------------

@pytest.mark.parametrize(
    ("model_id", "family", "query_prefix", "passage_prefix"),
    [
        ("intfloat/e5-base-v2", "e5", "query: ", "passage: "),
        ("intfloat/multilingual-e5-large", "e5", "query: ", "passage: "),
        ("BAAI/bge-base-en-v1.5", "bge-en", "Represent this sentence for searching relevant passages: ", ""),
        ("BAAI/bge-m3", "none", "", ""),
        ("nomic-ai/nomic-embed-text-v1.5", "nomic", "search_query: ", "search_document: "),
        ("Qwen/Qwen3-Embedding-0.6B", "qwen3", "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: ", ""),
        ("qwen/qwen3-embedding-8b", "qwen3", "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: ", ""),
    ],
)
def test_prefix_is_applied_for_the_configured_family(model_id, family, query_prefix, passage_prefix):
    assert infer_prefix_convention(model_id) == family
    embedder = FakeEmbedder(EmbedderConfig(model=model_id))
    embedder.embed_texts(["how do I refund"], input_type="query")
    embedder.embed_texts(["Requesting a refund"], input_type="passage")
    assert embedder.calls[0] == [query_prefix + "how do I refund"]
    assert embedder.calls[1] == [passage_prefix + "Requesting a refund"]
    assert embedder.provenance()["prefix_convention"] == family


def test_unknown_family_is_refused_unless_convention_is_explicit():
    with pytest.raises(ValueError, match="no prefix convention known"):
        FakeEmbedder(EmbedderConfig(model="someone/mystery-embedder"))
    ok = FakeEmbedder(EmbedderConfig(model="someone/mystery-embedder", prefix_convention="none"))
    assert ok.prefix.name == "none"
    with pytest.raises(ValueError, match="unknown prefix_convention"):
        FakeEmbedder(EmbedderConfig(model="intfloat/e5-base-v2", prefix_convention="bogus"))


def test_input_type_is_required_and_validated():
    embedder = FakeEmbedder(EmbedderConfig(model="intfloat/e5-base-v2"))
    with pytest.raises(TypeError):
        embedder.embed_texts(["x"])  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="input_type"):
        embedder.embed_texts(["x"], input_type="document")  # type: ignore[arg-type]


def test_local_backend_requires_a_pinned_revision():
    with pytest.raises(ValueError, match="revision"):
        SentenceTransformersEmbedder(EmbedderConfig(model="intfloat/e5-base-v2"))


def test_hosted_backend_requires_a_provider_pin_and_checks_the_response():
    from rag.embedding.base import OpenRouterEmbedder

    with pytest.raises(ValueError, match="provider"):
        OpenRouterEmbedder(EmbedderConfig(model="qwen/qwen3-embedding-8b"))
    embedder = OpenRouterEmbedder(EmbedderConfig(model="qwen/qwen3-embedding-8b", provider="DeepInfra"))
    assert embedder.pinned_identity == "provider:DeepInfra"
    good = {"data": [{"index": 0, "embedding": [1.0]}], "provider": "DeepInfra",
            "usage": {"prompt_tokens": 7, "cost": 7e-8}}
    assert embedder._parse(good, 1, 1) == [[1.0]]
    assert embedder.usage.calls == 1 and embedder.usage.prompt_tokens == 7
    with pytest.raises(RuntimeError, match="not the pinned"):
        embedder._parse({**good, "provider": "Nebius"}, 1, 1)
    with pytest.raises(RuntimeError, match="1 vectors for 2"):
        embedder._parse(good, 2, 1)


def test_resolve_prefix_convention_explicit_wins():
    assert resolve_prefix_convention("intfloat/e5-base-v2", "none").name == "none"


# --- dense index ---------------------------------------------------------------

DOCS = [
    ("doc_refund", "Requesting a refund for a premium plan. Go to billing. Click request refund."),
    ("doc_menu", "Customizing your horizontal menu design. Click the menu. Click design."),
    ("doc_forum", "About Wix Forum. Guests can post if you allow it. Members can upload."),
]
CORPUS_HASH = "sha256:" + "a" * 64


def _index(chunk_size: int = 600) -> tuple[ChunkIndex, dict[str, str]]:
    chunker = FixedTokenChunker(chunk_size=chunk_size, overlap=0)
    chunks = chunker.split_corpus(DOCS)
    index = ChunkIndex(
        chunks=chunks, chunker_id=chunker.chunker_id, chunker_params=chunker.params,
        corpus_hash=CORPUS_HASH, normalization_version="norm-v1",
    )
    return index, {c.chunk_id: c.text for c in chunks}


def _retriever(tmp_path, embedder=None, **kw) -> DenseRetriever:
    index, text = _index(kw.pop("chunk_size", 600))
    embedder = embedder or FakeEmbedder(EmbedderConfig(model="intfloat/e5-base-v2", revision="abc123"))
    return DenseRetriever(
        index.chunk_to_doc, text, index=index, embedder=embedder,
        index_dir=tmp_path / "idx", **kw,
    )


def test_index_key_is_a_function_of_the_provenance_tuple_only():
    base = dict(
        corpus_hash=CORPUS_HASH, normalization_version="norm-v1", chunker_id="fixed_token-x",
        model_id="intfloat/e5-base-v2", revision="abc", prefix_convention="e5",
    )
    assert index_key(**base) == index_key(**base)
    for field, value in (
        ("corpus_hash", "sha256:" + "b" * 64), ("normalization_version", "norm-v2"),
        ("chunker_id", "fixed_token-y"), ("model_id", "BAAI/bge-base-en-v1.5"),
        ("revision", "def"), ("prefix_convention", "none"),
    ):
        assert index_key(**{**base, field: value}) != index_key(**base), field
    # P2-08 run 5: a truncated output is a different index; unset leaves old keys alone.
    assert index_key(**base, dimensions=None) == index_key(**base)
    assert index_key(**base, dimensions=1024) != index_key(**base)


def test_dimensions_are_requested_and_asserted():
    """P2-08 run 5: `dimensions` goes into the request, and a provider that ignores it
    is caught at the response rather than scored as a truncated index."""
    from rag.embedding.base import OpenRouterEmbedder

    embedder = OpenRouterEmbedder(
        EmbedderConfig(model="qwen/qwen3-embedding-8b", provider="DeepInfra", dimensions=2)
    )
    assert embedder.provenance()["dimensions"] == 2
    good = {"data": [{"index": 0, "embedding": [1.0, 0.0]}], "provider": "DeepInfra", "usage": {}}
    assert embedder._parse(good, 1, 1) == [[1.0, 0.0]]
    native = {"data": [{"index": 0, "embedding": [1.0, 0.0, 0.0, 0.0]}], "provider": "DeepInfra", "usage": {}}
    with pytest.raises(RuntimeError, match="not honoured"):
        embedder._parse(native, 1, 1)


def test_index_builds_once_and_is_reused_from_cache(tmp_path):
    first = _retriever(tmp_path)
    assert first.provenance()["cache_hit"] is False
    assert first.provenance()["n_vectors"] == 3
    assert first.provenance()["build_seconds"] >= 0
    assert first.provenance()["size_bytes"] == 3 * 32 * 4
    assert (tmp_path / "idx" / "vectors.npy").exists()
    # Passages were embedded with the passage prefix, once each.
    assert all(t.startswith("passage: ") for t in first.embedder.calls[0])

    second = _retriever(tmp_path)
    assert second.provenance()["cache_hit"] is True
    assert second.embedder.calls == []  # nothing re-embedded
    assert np.array_equal(first.vectors, second.vectors)


def test_search_is_deterministic_and_uses_the_query_prefix(tmp_path):
    retriever = _retriever(tmp_path)
    ranked = retriever.search("how do I request a refund for my plan", top_k=3)
    assert retriever.embedder.calls[-1][0].startswith("query: ")
    assert [retriever.chunk_to_doc[cid] for cid, _ in ranked][0] == "doc_refund"
    assert ranked == retriever.search("how do I request a refund for my plan", top_k=3)
    assert all(-1.0 - 1e-6 <= s <= 1.0 + 1e-6 for _, s in ranked)
    assert all(not math.isnan(s) for _, s in ranked)
    assert retriever.search("   ", top_k=3) == []


def test_retrieve_returns_distinct_documents_from_dense_ranking(tmp_path):
    retriever = _retriever(tmp_path, chunk_size=4)  # many chunks per document
    result = retriever.retrieve("q", "click the menu design", top_k=20, k_docs=3, candidate_pool=20)
    assert len(result.context.doc_ids) == len(set(result.context.doc_ids))
    assert result.context.collapse_ratio is not None and result.context.collapse_ratio >= 1.0


def test_dense_retriever_refuses_to_build_without_provenance(tmp_path):
    index, text = _index()
    with pytest.raises(ValueError, match="provenance"):
        DenseRetriever(index.chunk_to_doc, text, embedder=FakeEmbedder(EmbedderConfig(model="intfloat/e5-base-v2")))
