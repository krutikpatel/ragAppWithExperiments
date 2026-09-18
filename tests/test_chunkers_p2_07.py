"""P2-07 — the four Axis 1 chunkers, the sentence splitter, the chunking profile,
the registry, and what the runner does with `context_text`."""

from __future__ import annotations

import pytest

from rag.chunking.base import (
    FixedTokenChunker,
    build_chunker,
    chunker_class,
    registered_chunkers,
)
from rag.chunking.index_map import ChunkIndex
from rag.chunking.parent_document import ParentDocumentChunker
from rag.chunking.profile import profile_chunks
from rag.chunking.semantic import SemanticChunker, breakpoints, group_sentences
from rag.chunking.sentence_window import SentenceWindowChunker
from rag.chunking.sentences import split_sentences
from rag.chunking.structure import StructureChunker, line_units
from rag.embedding.base import EmbedderConfig
from tests.test_embedding import FakeEmbedder

ARTICLE = (
    "Transferring Your Wix Domain Away from Wix\n"
    "You can transfer a domain purchased from Wix to another host. When you transfer, "
    "settings move too.Before you begin:We recommend keeping your domain with Wix.\n"
    "To transfer your domain:\n"
    "Click the Domains tab. Select your domain. Click Transfer away from Wix. Confirm the transfer.\n"
    "Your site is disconnected once the transfer completes."
)


# --- sentence splitter ------------------------------------------------------------

def test_splitter_breaks_on_newlines_spaces_and_glued_capitals():
    sentences = split_sentences(ARTICLE)
    assert sentences[0] == "Transferring Your Wix Domain Away from Wix"
    assert "When you transfer, settings move too." in sentences
    assert "Before you begin:We recommend keeping your domain with Wix." in sentences  # glued '.B'
    assert "To transfer your domain:" in sentences  # a ':'-line is its own sentence
    assert sentences[-1] == "Your site is disconnected once the transfer completes."
    assert split_sentences("   \n  ") == []


# --- registry -----------------------------------------------------------------------

def test_registry_lists_the_axis_1_chunkers_and_builds_by_name():
    assert {"fixed_token", "sentence_window", "parent_document", "semantic", "structure"} <= set(registered_chunkers())
    assert isinstance(build_chunker("fixed_token", chunk_size=600, overlap=100), FixedTokenChunker)
    assert isinstance(build_chunker("structure", max_words=600), StructureChunker)
    with pytest.raises(KeyError, match="unknown chunker"):
        build_chunker("headings")
    # Only the semantic chunker declares a pre-spend.
    assert chunker_class("fixed_token").embedding_params({"chunk_size": 600}) is None
    assert chunker_class("semantic").embedding_params(
        {"threshold_percentile": 95, "embedding_model": "m", "embedding_provider": "p"}
    ) == {"embedding_model": "m", "embedding_provider": "p"}


# --- sentence window ------------------------------------------------------------------

def test_sentence_window_indexes_one_sentence_and_contexts_the_window():
    chunks = SentenceWindowChunker(window=1).split("d", ARTICLE)
    sentences = split_sentences(ARTICLE)
    assert [c.text for c in chunks] == sentences
    assert chunks[0].context == " ".join(sentences[:2])
    assert chunks[3].context == " ".join(sentences[2:5])
    assert chunks[-1].context == " ".join(sentences[-2:])
    assert [c.ordinal for c in chunks] == list(range(len(sentences)))
    assert SentenceWindowChunker(window=0).split("d", ARTICLE)[2].context_text is None  # same as text


# --- parent document -----------------------------------------------------------------

def test_parent_document_children_index_and_parents_context():
    text = " ".join(f"w{i}" for i in range(1000))
    chunks = ParentDocumentChunker(parent_size=600, child_size=150).split("d", text)
    assert len(chunks) == 4 + 3  # 600 -> 4 children of 150; 400 -> 150,150,100
    assert all(len(c.text.split()) <= 150 for c in chunks)
    assert len(chunks[0].context.split()) == 600 and chunks[0].context == chunks[3].context
    assert len(chunks[4].context.split()) == 400 and chunks[4].context != chunks[0].context
    assert chunks[0].text == " ".join(chunks[0].context.split()[:150])
    with pytest.raises(ValueError):
        ParentDocumentChunker(parent_size=100, child_size=200)


# --- structure -----------------------------------------------------------------------

def test_structure_binds_header_lines_and_never_cuts_a_short_procedure():
    units = line_units(ARTICLE)
    assert units[2].startswith("To transfer your domain:\nClick the Domains tab.")
    chunks = StructureChunker(max_words=20).split("d", ARTICLE)
    assert all(len(c.text.split()) <= 20 or "\n" not in c.text for c in chunks)
    joined = [c.text for c in chunks]
    assert any("To transfer your domain:\nClick the Domains tab." in t for t in joined)
    # Every line boundary in the output is a line boundary in the input.
    assert " ".join(" ".join(t.split()) for t in joined) == " ".join(ARTICLE.split())


def test_structure_cuts_an_oversized_line_at_max_words():
    text = "Title\n" + " ".join(f"w{i}" for i in range(50))
    chunks = StructureChunker(max_words=20).split("d", text)
    assert [len(c.text.split()) for c in chunks] == [1, 20, 20, 10]


# --- semantic -------------------------------------------------------------------------

def test_breakpoints_use_the_documents_own_percentile():
    assert breakpoints([0.1, 0.9, 0.1, 0.2], percentile=75) == [1]
    assert breakpoints([0.5], percentile=95) == []
    assert group_sentences(["a", "b", "c", "d"], [1]) == [["a", "b"], ["c", "d"]]
    assert group_sentences(["a", "b"], []) == [["a", "b"]]


def test_semantic_chunker_embeds_once_caches_distances_and_records_spend(tmp_path):
    embedder = FakeEmbedder(EmbedderConfig(model="intfloat/e5-base-v2", revision="r1"))
    docs = [("d1", ARTICLE), ("d2", "One sentence only."), ("d3", "Two sentences. Here they are.")]
    chunker = SemanticChunker(threshold_percentile=50, max_words=600, embedder=embedder, cache_dir=tmp_path)
    chunks = chunker.split_corpus(docs)
    assert {c.doc_id for c in chunks} == {"d1", "d2", "d3"}
    assert sum(1 for c in chunks if c.doc_id == "d2") == 1 and sum(1 for c in chunks if c.doc_id == "d3") == 1
    assert sum(1 for c in chunks if c.doc_id == "d1") > 1  # the article was cut somewhere
    # Sentence-based chunkers put a space at glued boundaries ("too.Before"), so
    # compare with all whitespace removed: nothing else is lost or added.
    assert "".join("".join(c.text.split()) for c in chunks if c.doc_id == "d1") == "".join(ARTICLE.split())
    embedded = sum(len(call) for call in embedder.calls)
    assert embedded == len(split_sentences(ARTICLE))  # d2/d3 have < 3 sentences: no cut possible, nothing embedded
    assert chunker.cache_path.exists()
    prov = chunker.provenance()
    assert prov["sentences_embedded"] == embedded and prov["cache_hits"] == 0

    # Second chunker on the same cache: identical chunks, no embedding calls.
    embedder2 = FakeEmbedder(EmbedderConfig(model="intfloat/e5-base-v2", revision="r1"))
    again = SemanticChunker(threshold_percentile=50, max_words=600, embedder=embedder2, cache_dir=tmp_path)
    assert again.split_corpus(docs) == chunks
    assert embedder2.calls == [] and again.provenance()["cache_hits"] == 1

    # The embedder is part of the identity; the threshold too.
    other = SemanticChunker(threshold_percentile=95, max_words=600, embedder=embedder2, cache_dir=tmp_path)
    assert other.chunker_id != chunker.chunker_id
    assert "embedding_model" in chunker.params and "pinned_identity" in chunker.params


# --- profile -------------------------------------------------------------------------

def test_profile_counts_cut_procedure_blocks_for_any_chunker():
    docs = {"d": ARTICLE}
    whole = profile_chunks(FixedTokenChunker(chunk_size=600, overlap=0).split_corpus(list(docs.items())), docs)
    assert whole["n_chunks"] == 1 and whole["docs_in_one_chunk"] == 1
    assert whole["procedure_blocks"] == 1 and whole["procedure_blocks_cut"] == 0
    # A 10-word fixed chunker slices through the 4-step procedure; the structure
    # chunker at the same budget keeps the block whole by binding it to its header.
    small = profile_chunks(FixedTokenChunker(chunk_size=12, overlap=0).split_corpus(list(docs.items())), docs)
    assert small["procedure_blocks_cut"] == 1 and small["docs_with_cut_block"] == 1
    kept = profile_chunks(StructureChunker(max_words=25).split_corpus(list(docs.items())), docs)
    assert kept["procedure_blocks_cut"] == 0
    assert kept["context_words_per_chunk_mean"] == kept["words_per_chunk_mean"]


# --- index map: context_text round-trips ---------------------------------------------

def test_index_map_round_trips_context_text(tmp_path):
    chunker = SentenceWindowChunker(window=1)
    chunks = chunker.split_corpus([("d", ARTICLE), ("e", "Just one.")])
    index = ChunkIndex(chunks=chunks, chunker_id=chunker.chunker_id, chunker_params=chunker.params,
                       corpus_hash="sha256:" + "c" * 64, normalization_version="norm-v1")
    index.save(tmp_path)
    loaded = ChunkIndex.load(tmp_path)
    assert loaded.chunks == chunks
    assert loaded.context_text == index.context_text and loaded.chunk_text == index.chunk_text
    assert loaded.context_text[chunks[0].chunk_id] != loaded.chunk_text[chunks[0].chunk_id]
    one = [c for c in loaded.chunks if c.doc_id == "e"][0]
    assert one.context_text is None and one.context == one.text


# --- runner ---------------------------------------------------------------------------

import json
from pathlib import Path

from rag.runner.config import load_config_file
from rag.runner.store import ResultsStore

CORPUS_READY = Path("data/frozen/corpus.parquet").exists() and Path("data/frozen/dev.parquet").exists()


@pytest.mark.skipif(not CORPUS_READY, reason="frozen corpus not built")
def test_runner_builds_the_named_chunker_and_records_its_profile(tmp_path):
    """`config.chunker` is read (it was hard-coded to fixed_token before P2-07), and
    the run row carries the chunking profile the story asks for."""
    from rag.runner.run import run
    from tests.test_phase2_discipline import TABLE

    config = load_config_file("configs/smoke_toy.yaml").with_(chunker="structure", chunker_params={"max_words": 600})
    with ResultsStore(tmp_path / "runs.sqlite") as store:
        row = run(config, store=store, pricing=TABLE)
    assert row["chunker_id"].startswith("structure-")
    meta = json.loads(row["chunker_meta"])
    assert meta["chunker"] == "structure" and meta["params"]["max_words"] == 600
    profile = meta["profile"]
    assert profile["n_documents"] == 6221 and profile["n_chunks"] > 6221
    assert profile["procedure_blocks"] > 0 and 0 <= profile["procedure_blocks_cut"] <= profile["procedure_blocks"]
    assert json.loads(row["metrics_json"])["chunking_profile"] == profile


@pytest.mark.skipif(not CORPUS_READY, reason="frozen corpus not built")
def test_semantic_pre_spend_is_estimated_and_gated_before_any_embedding(tmp_path, monkeypatch):
    """The semantic chunker embeds the whole corpus before a chunk exists. The gate
    must fire on that estimate before the embedder is called, not after."""
    from rag.runner import cost, run as run_mod
    from rag.runner.cost import CostGateError
    from rag.runner.run import run
    from tests.test_phase2_discipline import TABLE

    calls: list[int] = []

    class Boom(FakeEmbedder):
        def _embed(self, texts):
            calls.append(len(texts))
            raise AssertionError("embedded before the gate")

    monkeypatch.setattr(run_mod, "COST_GATE_USD", 0.0)
    monkeypatch.setattr(cost, "COST_GATE_USD", 0.0)
    from rag.chunking import semantic as semantic_mod

    monkeypatch.setattr(semantic_mod, "build_embedder", lambda backend, cfg: Boom(cfg))
    config = load_config_file("configs/smoke_toy.yaml").with_(
        chunker="semantic",
        chunker_params={
            "threshold_percentile": 95, "max_words": 600,
            "embedding_model": "qwen/qwen3-embedding-8b", "embedding_provider": "DeepInfra",
            "cache_dir": str(tmp_path / "cold"),
        },
    )
    with ResultsStore(tmp_path / "runs.sqlite") as store:
        with pytest.raises(CostGateError, match="has not started"):
            run(config, store=store, pricing=TABLE)
        assert store.list_runs() == []
    assert calls == [], "the gate fired after the corpus was embedded"
    estimate = run(config, store=None, pricing=TABLE, estimate_only=True)
    assert estimate["index"]["chunker_embedding_usd"] > 0
    assert estimate["index"]["chunker_source"].startswith("semantic:")
