"""P0-05 — every chunk carries its document, and the mapping round-trips."""

from __future__ import annotations

import pytest

from rag.chunking.base import FixedTokenChunker
from rag.chunking.index_map import ChunkIndex

DOCS = [("doc_A", " ".join(f"a{i}" for i in range(1100))), ("doc_B", "short document")]


def test_every_chunk_carries_its_doc_id():
    chunks = FixedTokenChunker(chunk_size=512).split_corpus(DOCS)
    assert {c.doc_id for c in chunks} == {"doc_A", "doc_B"}
    assert all(c.chunk_id for c in chunks)


def test_chunk_ids_are_unique_and_opaque():
    chunks = FixedTokenChunker(chunk_size=512).split_corpus(DOCS)
    ids = [c.chunk_id for c in chunks]
    assert len(set(ids)) == len(ids)
    # Opaque on purpose: doc_id must come from the mapping, not from parsing.
    assert all(c.doc_id not in c.chunk_id for c in chunks)


def test_chunking_is_deterministic():
    first = FixedTokenChunker(chunk_size=512).split_corpus(DOCS)
    second = FixedTokenChunker(chunk_size=512).split_corpus(DOCS)
    assert first == second


def test_chunker_id_tracks_params():
    assert FixedTokenChunker(512).chunker_id != FixedTokenChunker(256).chunker_id
    assert FixedTokenChunker(512, 0).chunker_id == FixedTokenChunker(512, 0).chunker_id


def test_fixed_size_and_overlap():
    chunker = FixedTokenChunker(chunk_size=512, overlap=64)
    chunks = chunker.split("doc_A", DOCS[0][1])
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    assert all(len(c.text.split()) <= 512 for c in chunks)
    first, second = chunks[0].text.split(), chunks[1].text.split()
    assert first[-64:] == second[:64]


def test_empty_document_yields_no_chunks():
    assert FixedTokenChunker().split("doc_empty", "   ") == []


def test_invalid_params_rejected():
    with pytest.raises(ValueError):
        FixedTokenChunker(chunk_size=0)
    with pytest.raises(ValueError):
        FixedTokenChunker(chunk_size=128, overlap=128)


def test_index_map_round_trips(tmp_path):
    chunker = FixedTokenChunker(chunk_size=512)
    index = ChunkIndex(
        chunks=chunker.split_corpus(DOCS),
        chunker_id=chunker.chunker_id,
        chunker_params=chunker.params,
        corpus_hash="sha256:test",
        normalization_version="norm-v1",
    )
    index.save(tmp_path / "index")
    reloaded = ChunkIndex.load(tmp_path / "index")

    assert reloaded.chunks == index.chunks
    assert reloaded.chunk_to_doc == index.chunk_to_doc
    assert reloaded.corpus_hash == "sha256:test"
    assert reloaded.chunker_id == chunker.chunker_id
