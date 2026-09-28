"""P0-07 / P0-11 — prompts are versioned data, addressed by (id, version).

Only the generator prompt is ours now. Ragas owns the judge prompts and manages them
internally, so those are tracked by `metric_prompt_versions` fingerprints instead —
see `tests/test_eval_boundary.py`.
"""

from __future__ import annotations

import pytest

from rag.prompts import list_prompts, load_prompt

# Editing a prompt without bumping its version would silently change every future
# run while the results store still recorded the old ref. This pin makes that edit
# fail here instead of showing up as a mysterious metric shift weeks later.
PINNED_HASHES = {
    "answer@v1": "sha256:cb49635996bd8e0",
    # P1-05: frozen for the whole of Phase 1. An edit here is a v2 and a new control.
    "baseline_answer@v1": "sha256:a5e9b4d936151a8",
    # P2-10: the LLM-as-reranker's ordering prompt (Axis 5).
    "rerank_llm@v1": "sha256:c89fb05085e9b10",
    # P2-13 (Axis 6). `contextual_chunk` is prefixed onto every chunk *before
    # indexing*, so an edit here without a version bump would silently mean the index
    # on disk was built by a prompt no longer in the repo — the most expensive
    # version-skew in the project, at one LLM call per chunk to discover.
    "compress_context@v1": "sha256:f372591e7e06721",
    "contextual_chunk@v1": "sha256:b4f446a0b0ccec7",
    # P2-12 (Axis 4). Each is sent once per question, so an edit without a version
    # bump changes every future retrieval while the cache still replays the old one.
    "query_decompose@v1": "sha256:e7f2e681d94ad4d",
    "query_hyde@v1": "sha256:a49d4b8d2bec73e",
    "query_multi@v1": "sha256:cc5424b96c1dd02",
    "query_step_back@v1": "sha256:6d4745041ad8a64",
    # P2-14 (Axis 7). The two answer prompts are one-dimension variants of
    # baseline_answer@v1 — same task, format, language and URL rule — so that a delta
    # is attributable to the citation requirement and nothing else.
    "enforced_answer@v1": "sha256:55e7413b9f6f541",
    "groundedness_check@v1": "sha256:a46b489e756ab1b",
    "span_answer@v1": "sha256:9e410481d6645ba",
}


def test_every_prompt_content_hash_is_pinned():
    actual = {prompt.ref: prompt.content_hash[:22] for prompt in list_prompts()}
    assert actual == PINNED_HASHES, (
        "a prompt changed. Bump its version in prompts/*.yaml and update this pin — "
        "editing a prompt in place makes old and new runs incomparable."
    )


def test_prompt_ref_is_what_the_store_records():
    assert load_prompt("answer", "v1").ref == "answer@v1"


def test_unknown_version_is_rejected():
    with pytest.raises(KeyError, match="no version"):
        load_prompt("answer", "v99")


def test_missing_field_names_itself():
    with pytest.raises(KeyError, match="question"):
        load_prompt("answer", "v1").render(context="x")


def test_answer_prompt_asks_for_citations_and_refusal():
    """Citation precision and refusal metrics are only computable if it asks for them."""
    rendered = load_prompt("answer", "v1").render(context="CTX", question="Q")
    assert "CTX" in rendered and "Q" in rendered
    assert "[doc:<id>]" in rendered
    assert "do not guess" in rendered


# --- P1-05: the Phase 1 control prompt ----------------------------------------

def test_baseline_prompt_asks_for_steps_citations_and_no_urls():
    rendered = load_prompt("baseline_answer", "v1").render(context="CTX", question="Q")
    assert "numbered list of steps" in " ".join(rendered.split())
    assert "Answer in English" in rendered
    assert "[doc:<id>]" in rendered
    assert "Do not write any URL" in rendered
    assert "The provided articles do not cover this." in rendered


def test_baseline_prompt_refusal_phrase_is_what_the_detector_matches():
    """DEC-014's refusal detector is lexical; the prompt's fixed refusal phrase must
    be one it recognises, or every refusal would be scored as an answer."""
    from rag.eval.generation_metrics import is_refusal

    assert is_refusal("The provided articles do not cover this. Nothing mentions refunds.")


def test_run_config_default_prompt_is_the_phase_1_control():
    from rag.runner.config import RunConfig

    config = RunConfig(name="t")
    assert config.generator_prompt == "baseline_answer@v1"
    assert (config.generator_prompt_id, config.generator_prompt_version) == ("baseline_answer", "v1")
    load_prompt(config.generator_prompt_id, config.generator_prompt_version)


def test_url_detector_matches_links_not_domain_names():
    from rag.eval.generation_metrics import find_urls

    assert find_urls("Go to https://support.wix.com/en/article/x for details.") == ["https://support.wix.com/en/article/x"]
    # The trailing full stop is sentence punctuation, not part of the host. v1 swallowed
    # it; the MIS-039 fix stops at the last URL-ish character. No recorded number depends
    # on the matched STRING — `answers_with_url` is a count — so nothing in the ledger
    # moves, and this expectation was pinning a wart rather than a behaviour.
    assert find_urls("See www.wix.com/my-account.") == ["www.wix.com/my-account"]
    assert find_urls("Connect example.com in your Domains settings [doc:abc12345].") == []
    assert find_urls("") == [] and find_urls(None) == []


def test_recorded_generated_answers_contain_no_urls():
    """P1-05's acceptance test on real model output: every stored answer produced
    with baseline_answer@v1 is URL-free. Skips when no such run exists yet."""
    import json

    from rag.runner.store import DEFAULT_DB, ResultsStore

    if not DEFAULT_DB.exists():
        pytest.skip("no results store on this machine")
    from rag.eval.generation_metrics import find_urls

    with ResultsStore() as store:
        runs = [
            r for r in store.list_runs(200)
            if r["status"] == "VALID" and not r["harness_smoke_test"]
            and json.loads(r["prompt_versions"] or "{}").get("answer") == "baseline_answer@v1"
        ]
        if not runs:
            pytest.skip("no VALID run with baseline_answer@v1 recorded yet")
        # DEC-086: P1-05 forbids links the generator WRITES — "a generated one can only
        # be stale or invented". A URL quoted verbatim from one of the answer's own
        # context articles is neither, so it is checked against that text; anything
        # else — invented, altered, or from outside the context — still fails.
        from rag.corpus.loader import load_corpus

        texts = dict(zip(load_corpus().frame["id"], load_corpus().frame["contents"]))
        offenders = []
        for run in runs:
            top_k = json.loads(run["config_json"] or "{}").get("top_k", 5)
            for qid, row in store.get_questions(run["run_id"]).items():
                urls = find_urls(row["generated_answer"]) if row["generated_answer"] else []
                if not urls:
                    continue
                context = " ".join(texts.get(d, "") for d in json.loads(row["retrieved_doc_ids"] or "[]")[:top_k])
                invented = [u for u in urls if u.rstrip(".,") not in context]
                if invented:
                    offenders.append((run["run_id"], qid, invented))
    assert offenders == [], f"URL-shaped strings in raw model output: {offenders[:5]}"


# --- P2-10: the LLM-as-reranker prompt ----------------------------------------

def test_rerank_prompt_asks_for_an_ordering_of_every_candidate():
    """The parser tolerates prose (MIS-016), but the prompt still has to ask for the
    thing the parser reads: bare numbers, each candidate once."""
    rendered = load_prompt("rerank_llm", "v1").render(question="Q", candidates="[1] A\n\n[2] B", n=2)
    flat = " ".join(rendered.split())
    assert "[1] A" in rendered and "Q" in rendered
    assert "Each number appears exactly once" in flat
    assert "Output ONLY the numbers, best first" in flat
    assert "all 2 of them" in flat


# --- P2-13: the Axis 6 prompts -------------------------------------------------

def test_contextual_chunk_prompt_asks_for_the_statement_alone():
    """The caller concatenates the output in front of the chunk verbatim, so any
    preamble the model adds gets indexed as if it were article text."""
    rendered = load_prompt("contextual_chunk", "v1").render(
        document="DOC", chunk="CHUNK", max_words=60
    )
    flat = " ".join(rendered.split())
    assert "DOC" in rendered and "CHUNK" in rendered
    assert "at most 60 words" in flat
    assert "Answer with the statement only" in flat


def test_compress_context_prompt_forbids_rewriting_and_names_the_empty_marker():
    """Extractive only: a rewritten chunk would mean faithfulness was scored against
    text retrieval never returned. The empty marker has to be the one the caller
    matches, or a chunk with nothing relevant would be kept in full."""
    from rag.assembly import EMPTY_MARKER

    rendered = load_prompt("compress_context", "v1").render(
        question="Q", passage="P", empty_marker=EMPTY_MARKER
    )
    flat = " ".join(rendered.split())
    assert "Q" in rendered and "P" in rendered
    assert "word for word" in flat
    assert "Do not rewrite" in flat
    assert f"output exactly: {EMPTY_MARKER}" in flat


def test_url_detector_does_not_flag_a_bare_scheme():
    """MIS-039: a scheme with no host is not a link. An answer correctly instructing a
    user to 'replace http:// with https://' was flagged as containing a URL — found on
    the test split, after it was opened, and fixed as a measurement bug rather than a
    change to anything the system does."""
    from rag.eval.generation_metrics import find_urls

    assert find_urls("edit the code to remove http:// and replace it with https://, then Publish.") == []
    assert find_urls("ensure any code uses HTTPS (not HTTP)") == []
    # And it still catches what it exists to catch.
    assert find_urls("Go to https://support.wix.com/en/article/x") == ["https://support.wix.com/en/article/x"]
    assert find_urls("See www.wix.com/my-account.") == ["www.wix.com/my-account"]


def test_every_doc_marker_is_either_parsed_or_flagged_malformed_on_stored_output():
    """MIS-045 / preflight 49: `citation-v3` silently skips a `[doc:` marker it cannot
    parse. The P3-09 detector must account for every one the parser does not, on every
    stored answer — no marker may be neither."""
    import re

    from rag.eval.generation_metrics import malformed_citation_markers
    from rag.runner.store import DEFAULT_DB, ResultsStore

    if not DEFAULT_DB.exists():
        pytest.skip("no results store on this machine")
    parsed = re.compile(r"\[\s*doc\s*:\s*[0-9a-f]{8,64}\s*(?:[|#][^\]]*)?\]", re.IGNORECASE)
    with ResultsStore() as store:
        answers = [a for (a,) in store.conn.execute(
            "SELECT generated_answer FROM run_questions WHERE generated_answer IS NOT NULL")]
    gaps = [a[:80] for a in answers
            if len(re.findall(r"\[\s*doc\s*:", a, re.IGNORECASE))
            != len(parsed.findall(a)) + len(malformed_citation_markers(a))]
    assert gaps == []
    assert malformed_citation_markers("[doc:" + "a" * 66 + "] and [doc: ADI: A Payment Form]") == [
        "a" * 66, "ADI: A Payment Form"]
    assert malformed_citation_markers("[doc:" + "b" * 64 + "] [doc: " + "c" * 64 + " | a quote]") == []
