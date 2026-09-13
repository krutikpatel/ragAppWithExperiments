"""P1-06 — citations are doc ids; title, URL and the exact chunk come from the store."""

from __future__ import annotations

import pandas as pd

from rag.citations import format_report, render_citations
from rag.corpus.loader import FrozenCorpus
from rag.eval.generation_metrics import citation_scores
from rag.generation.base import extract_citations
from rag.retrieval.base import ScoredChunk

CORPUS = FrozenCorpus(
    frame=pd.DataFrame(
        [
            {"id": "a" * 64, "url": "https://support.wix.com/en/article/a", "title": "Article A", "contents": "", "article_type": "article", "indexed_text": ""},
            {"id": "b" * 64, "url": "https://support.wix.com/en/article/b", "title": "Article B", "contents": "", "article_type": "article", "indexed_text": ""},
        ]
    ),
    meta={"corpus_hash": "x", "normalization_version": "norm-v1", "hf_revision": "y"},
)
CHUNKS = [ScoredChunk("c1", "a" * 64, 0.9), ScoredChunk("c2", "b" * 64, 0.8)]
TEXT = {"c1": "Go to Settings. Click Save.", "c2": "Open the dashboard."}


def test_citations_resolve_to_title_url_and_exact_chunk():
    answer = f"1. Go to Settings. [doc:{'a' * 64}]\n2. Click Save. [doc:{'a' * 64}]"
    cited = extract_citations(answer)
    rendered = render_citations(cited, CHUNKS, TEXT, CORPUS)
    assert [c.doc_id for c in rendered] == ["a" * 64, "b" * 64]
    first = rendered[0]
    assert (first.title, first.url, first.chunk_text, first.cited, first.in_context) == (
        "Article A", "https://support.wix.com/en/article/a", "Go to Settings. Click Save.", True, True
    )
    assert rendered[1].cited is False and rendered[1].in_context is True
    report = format_report("q", answer, rendered)
    assert "[1] Article A" in report and "https://support.wix.com/en/article/a" in report
    assert "| Go to Settings. Click Save." in report
    assert "Retrieved but not cited:" in report and "Article B" in report


def test_invented_citation_is_shown_and_flagged():
    rendered = render_citations(["f" * 64], CHUNKS, TEXT, CORPUS)
    ghost = rendered[0]
    assert ghost.cited and not ghost.in_context and ghost.title is None and ghost.chunk_text is None
    assert "CITED BUT NOT RETRIEVED" in format_report("q", "[doc:ffff]", rendered)


def test_citation_precision_needs_no_llm_and_matches_the_rendered_ids():
    """The same ids that render the source block score citation precision/recall."""
    cited = extract_citations(f"x [doc:{'a' * 64}] y [doc:{'b' * 64}]")
    scores = citation_scores(cited, gold_doc_ids=["a" * 64])
    assert (scores.precision, scores.recall, scores.n_cited) == (0.5, 1.0, 2)


def test_spaced_and_capitalised_citations_are_parsed():
    """MIS-016 / DEC-043: `[doc: id]` with a space was dropped by citation-v1 — 4 to 13
    citations per 100 answers. citation-v2 accepts whitespace and case."""
    from rag.generation.base import CITATION_PARSER_VERSION

    assert CITATION_PARSER_VERSION == "citation-v2"
    a = "a" * 64
    assert extract_citations(f"[doc: {a}]") == [a]
    assert extract_citations(f"[ doc:{a} ]") == [a]
    assert extract_citations(f"[Doc: {a}]") == [a]
    assert extract_citations(f"[doc:{a}] and again [doc: {a}]") == [a]
    # Not a citation: wrong keyword, or a non-hex id.
    assert extract_citations("[document: abcdef12] [doc: xyz]") == []
