"""P1-02 — corpus profiling: lengths, one-chunk fit, and mid-procedure boundaries."""

from __future__ import annotations

import pytest

from rag.chunking.base import FixedTokenChunker
from rag.corpus.profile import (
    ProcedureBlock,
    _percentiles,
    chunk_spans,
    count_numbered_lines,
    find_procedure_blocks,
    is_cut,
    token_offsets,
    write_profile_docs,
)

# How a procedure actually appears in the frozen text: header line ending in ':',
# then step sentences with their list markers stripped.
PROCEDURE = (
    "Animation effects are fun. You can manage them.To remove animation:\n"
    "Click the element. Click the\xa0Animation\xa0icon\xa0. Click\xa0None\xa0.Note:If you remove "
    "an animation, customizations are lost."
)


def test_token_offsets_agree_with_str_split_on_unicode_whitespace():
    text = "a\xa0b  c\n\td ﻿e"
    spans = token_offsets(text)
    assert [text[s:e] for s, e in spans] == text.split()


def test_chunk_spans_mirror_the_chunker():
    text = " ".join(f"w{i}" for i in range(1234))
    for size, overlap in ((600, 100), (512, 0), (5, 2), (2000, 0)):
        chunks = FixedTokenChunker(chunk_size=size, overlap=overlap).split("d", text)
        spans = chunk_spans(1234, size, overlap)
        assert len(spans) == len(chunks)
        assert [s.end_token - s.start_token for s in spans] == [len(c.text.split()) for c in chunks]
    assert chunk_spans(0, 600, 100) == []


def test_procedure_block_is_detected_and_spans_header_through_last_step():
    blocks = find_procedure_blocks(PROCEDURE)
    assert len(blocks) == 1
    tokens = PROCEDURE.split()
    span = tokens[blocks[0].start_token : blocks[0].end_token]
    # Starts at the header sentence, not the start of the line.
    assert span[0] == "them.To"
    assert span[1:4] == ["remove", "animation:", "Click"]
    # Ends at the last step's terminator; the "Note:" prose after it is not a step.
    # (\xa0 is whitespace, so "None" and ".Note:If" are separate tokens.)
    assert span[-2:] == ["None", ".Note:If"]


def test_a_lone_step_is_not_a_procedure():
    assert find_procedure_blocks("To do it:\nClick here. Then a sentence.") == []
    assert find_procedure_blocks("Just prose. Click here. Click there.") == []


def test_literal_numbered_lines_are_counted_separately():
    assert count_numbered_lines(PROCEDURE) == 0
    assert count_numbered_lines("Steps:\n1. Click A\n2. Click B\n3) Click C") == 3


def test_cut_detection_with_and_without_overlap():
    block = ProcedureBlock(start_token=95, end_token=110)
    # No overlap: stride boundary at 100 splits it.
    assert is_cut(block, chunk_spans(300, 100, 0))
    # Overlap of 20: chunk 0 = [0, 100), chunk 1 = [80, 180) holds all of it.
    assert not is_cut(block, chunk_spans(300, 100, 20))
    # Longer than a chunk: always cut.
    assert is_cut(ProcedureBlock(0, 150), chunk_spans(300, 100, 50))
    # Entirely inside the last, short chunk.
    assert not is_cut(ProcedureBlock(280, 295), chunk_spans(300, 100, 0))


def test_block_shorter_than_overlap_is_never_cut():
    """The property behind the 600/100 profile's zero: overlap >= block length."""
    for start in range(0, 700):
        block = ProcedureBlock(start, start + 100)
        assert not is_cut(block, chunk_spans(800, 600, 100)), start


def test_percentiles_are_nearest_rank():
    stats = _percentiles(list(range(1, 101)))
    assert (stats["min"], stats["p25"], stats["median"], stats["p90"], stats["max"]) == (1, 25, 50, 90, 100)
    assert _percentiles([]) == {}


def _fake_profile(version: str = "profile-test") -> dict:
    cfg = {
        "chunk_size": 600, "overlap": 100, "n_chunks": 1, "fits_in_one_chunk": 1,
        "fits_in_one_chunk_fraction": 1.0, "procedure_blocks_cut": 0,
        "procedure_blocks_cut_fraction": 0.0, "procedure_blocks_longer_than_chunk": 0,
        "procedure_blocks_longer_than_overlap": 0, "articles_with_cut_block": 0,
        "articles_with_cut_block_fraction": 0.0,
    }
    group = {
        "n_articles": 1,
        "length_words": _percentiles([10]), "length_tokens": _percentiles([13]),
        "tokens_per_word": 1.3,
        "histogram_words": [{"lo": 0, "hi": None, "count": 1, "fraction": 1.0}],
        "numbered_lines": {"articles_with_any_numbered_line": 0, "fraction_any": 0.0,
                           "articles_with_numbered_list_2plus": 0, "fraction_2plus": 0.0},
        "procedure_blocks": {"articles_with_block": 0, "fraction": 0.0, "n_blocks": 0,
                             "block_length_words": {}},
        "chunk_configs": [cfg],
    }
    return {
        "profile_version": version, "corpus_hash": "sha256:" + "0" * 64,
        "normalization_version": "norm-v1", "hf_revision": "x", "bpe_encoding": "cl100k_base",
        "chunk_unit": "words", "imperative_verbs": [], "histogram_edges_words": [0],
        "computed_at": "now", "all": group, "by_article_type": {"article": group},
    }


def test_docs_block_is_append_only(tmp_path):
    from rag.paths import RESULTS_DIR

    docs = tmp_path / "EXPERIMENTS.md"
    docs.write_text("# Experiments\n\n| existing | row |\n")
    artifact = RESULTS_DIR / "corpus_profile" / "fake.json"
    profile = _fake_profile()

    assert write_profile_docs(profile, artifact, docs) == "appended"
    first = docs.read_text()
    assert first.startswith("# Experiments\n\n| existing | row |\n")
    assert "corpus-profile:" in first
    # Same profile again: nothing changes.
    assert write_profile_docs(profile, artifact, docs) == "unchanged"
    assert docs.read_text() == first
    # Same key, different numbers: refused rather than rewritten.
    changed = _fake_profile()
    changed["all"]["n_articles"] = 2
    with pytest.raises(RuntimeError, match="append-only"):
        write_profile_docs(changed, artifact, docs)
    assert docs.read_text() == first
    # A version bump appends a second block and keeps the first.
    assert write_profile_docs(_fake_profile("profile-test2"), artifact, docs) == "appended"
    assert docs.read_text().startswith(first)
