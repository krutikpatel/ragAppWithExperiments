"""P0-01 / P0-02 — the frozen corpus and its normalization rule."""

from __future__ import annotations

import pytest

from rag.corpus.freeze import HF_REVISION, KB_SNAPSHOT_DATE, compute_corpus_hash
from rag.corpus.loader import load_corpus, verify_corpus
from rag.corpus.normalize import NORMALIZATION_VERSION, normalize_for_index


def test_revision_is_pinned_to_a_commit_not_a_branch():
    assert len(HF_REVISION) == 40 and HF_REVISION.isalnum()
    assert HF_REVISION not in {"main", "master"}


def test_markdown_link_targets_are_stripped_from_indexed_text():
    text = "See [the billing article](https://support.wix.com/en/article/billing) for more."
    assert normalize_for_index(text) == "See the billing article for more."


def test_bare_urls_are_kept():
    text = "Go to https://support.wix.com/en/article/billing"
    assert normalize_for_index(text) == text


def test_unknown_normalization_version_is_rejected():
    with pytest.raises(ValueError, match="unknown normalization_version"):
        normalize_for_index("text", version="norm-v99")


def test_hash_is_order_independent():
    records = [
        {"id": "b", "url": "u2", "title": "t2", "contents": "c2", "article_type": "article"},
        {"id": "a", "url": "u1", "title": "t1", "contents": "c1", "article_type": "article"},
    ]
    assert compute_corpus_hash(records) == compute_corpus_hash(list(reversed(records)))


def test_hash_changes_when_source_text_changes():
    base = [{"id": "a", "url": "u", "title": "t", "contents": "c", "article_type": "article"}]
    edited = [dict(base[0], contents="c!")]
    assert compute_corpus_hash(base) != compute_corpus_hash(edited)


# --- these require `rag corpus freeze` to have been run -----------------------

frozen = pytest.mark.skipif(
    not __import__("rag.paths", fromlist=["CORPUS_PARQUET"]).CORPUS_PARQUET.exists(),
    reason="frozen corpus not materialized; run `rag corpus freeze`",
)


@frozen
def test_materialized_hash_matches_metadata():
    assert verify_corpus()["match"] is True


@frozen
def test_metadata_records_provenance():
    meta = load_corpus().meta
    assert meta["hf_revision"] == HF_REVISION
    assert meta["kb_snapshot_date"] == KB_SNAPSHOT_DATE
    assert meta["normalization_version"] == NORMALIZATION_VERSION


@frozen
def test_indexed_text_is_derived_from_stored_contents():
    frame = load_corpus().frame.head(200)
    for row in frame.itertuples():
        assert row.indexed_text == normalize_for_index(row.contents)
