"""P0-07 — the generation metrics that need no LLM call."""

from __future__ import annotations

import pytest

from rag.eval.generation_metrics import citation_scores, deterministic_metrics, is_refusal, refusal_summary
from rag.eval.steps import extract_steps, step_coverage
from rag.generation.base import extract_citations

REFERENCE = """To add a member area:
1. Go to your site dashboard.
2. Click Add Apps in the left menu.
3. Search for Members Area and click Add.
4. Publish your site.
"""


def test_citation_precision_and_recall():
    scores = citation_scores(["dA", "dB"], ["dA", "dC"])
    assert scores.precision == pytest.approx(0.5)
    assert scores.recall == pytest.approx(0.5)


def test_citing_nothing_gives_no_precision_rather_than_zero():
    """Declining to cite is not the same as citing wrongly."""
    scores = citation_scores([], ["dA"])
    assert scores.precision is None
    assert scores.recall == 0.0
    assert scores.cited_nothing is True


def test_duplicate_citations_do_not_inflate_the_denominator():
    assert citation_scores(["dA", "dA"], ["dA"]).precision == pytest.approx(1.0)


def test_citations_are_extracted_in_first_mention_order():
    assert extract_citations("x [doc:aabbccdd] y [doc:11223344] z [doc:aabbccdd]") == [
        "aabbccdd",
        "11223344",
    ]


def test_step_extraction_reads_numbered_lists_only():
    steps = extract_steps(REFERENCE)
    assert len(steps) == 4
    assert steps[0].startswith("Go to your site dashboard")
    # Bullets are unordered facts in this corpus, not steps.
    assert extract_steps("- first thing\n- second thing") == []


def test_step_coverage_counts_present_steps():
    generated = """1. Go to your site dashboard.
2. Click Add Apps in the left menu.
3. Publish your site.
"""
    result = step_coverage(REFERENCE, generated)
    assert result.applicable is True
    assert result.n_reference_steps == 4
    assert result.coverage == pytest.approx(0.75)
    assert result.order_preserved is True


def test_step_coverage_detects_reordering():
    reordered = """1. Publish your site.
2. Go to your site dashboard.
3. Click Add Apps in the left menu.
4. Search for Members Area and click Add.
"""
    result = step_coverage(REFERENCE, reordered)
    assert result.coverage == pytest.approx(1.0)
    assert result.order_preserved is False


def test_step_coverage_is_none_for_prose_answers():
    """Most WixQA answers are prose. Scoring them zero would poison the mean."""
    result = step_coverage("Payouts are held when verification is incomplete.", "Anything.")
    assert result.applicable is False
    assert result.coverage is None and result.order_preserved is None


def test_refusal_detection():
    assert is_refusal("The provided context does not contain this information.")
    assert is_refusal("I don't have enough information to answer that.")
    assert is_refusal("Could you clarify which site you mean?")
    assert not is_refusal("Go to Settings and click Save.")


def test_refusal_and_false_refusal_are_separate_metrics():
    unanswerable = deterministic_metrics(
        generated_answer="The articles do not cover this.",
        reference_answer="",
        cited_doc_ids=[],
        gold_doc_ids=[],
    )
    assert unanswerable["correct_refusal"] == 1.0
    assert unanswerable["false_refusal"] is None

    answerable = deterministic_metrics(
        generated_answer="The articles do not cover this.",
        reference_answer=REFERENCE,
        cited_doc_ids=[],
        gold_doc_ids=["dA"],
    )
    assert answerable["false_refusal"] == 1.0
    assert answerable["correct_refusal"] is None


def test_refusal_summary_reports_both_rates_with_counts():
    per_question = {
        "u1": {"correct_refusal": 1.0, "false_refusal": None},
        "u2": {"correct_refusal": 0.0, "false_refusal": None},
        "a1": {"correct_refusal": None, "false_refusal": 0.0},
    }
    summary = refusal_summary(per_question)
    assert summary["refusal_rate"] == pytest.approx(0.5)
    assert summary["refusal_rate_n"] == 2
    assert summary["false_refusal_rate"] == 0.0
    assert summary["false_refusal_rate_n"] == 1
    assert summary["refusal_detector"]


def test_generator_retries_transient_failures_and_counts_attempts(monkeypatch):
    """MIS-010: one timeout in 100 calls must not void a run, and retries are visible."""
    import httpx

    from rag.generation.base import Completion, GeneratorConfig, OpenRouterGenerator

    gen = OpenRouterGenerator(GeneratorConfig(model="x/y", max_attempts=3, backoff_s=0.0))
    calls = {"n": 0}

    def flaky(prompt):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ReadTimeout("slow")
        return Completion(text="ok [doc:abcdef12]", tokens_in=1, tokens_out=1,
                          reasoning_tokens=0, finish_reason="stop")

    monkeypatch.setattr(gen, "_complete_once", flaky)
    monkeypatch.setattr("rag.prompts.load_prompt", lambda i, v: type("P", (), {
        "ref": "answer@v1", "render": staticmethod(lambda **k: "p")})())
    answer = gen.generate("q", "ctx")
    assert answer.meta["attempts"] == 3
    assert answer.cited_doc_ids == ["abcdef12"]


def test_generator_does_not_retry_non_transient_errors(monkeypatch):
    import httpx

    from rag.generation.base import GeneratorConfig, OpenRouterGenerator

    gen = OpenRouterGenerator(GeneratorConfig(model="x/y", max_attempts=3, backoff_s=0.0))
    resp = httpx.Response(401, request=httpx.Request("POST", "https://x"))

    def unauthorized(prompt):
        raise httpx.HTTPStatusError("nope", request=resp.request, response=resp)

    monkeypatch.setattr(gen, "_complete_once", unauthorized)
    with pytest.raises(httpx.HTTPStatusError):
        gen._complete("p")


def test_no_gold_gives_no_recall_rather_than_zero():
    """Unanswerable questions have nothing to recall (DEC-044, MIS-002)."""
    scores = citation_scores(["dA"], [])
    assert scores.recall is None
    assert scores.precision == 0.0  # it cited something, and nothing was right
    assert citation_scores([], []).recall is None


# --- DEC-045: refusal-lexical-v2 ------------------------------------------------

def test_refusal_detector_version_is_v3():
    from rag.eval.generation_metrics import REFUSAL_DETECTOR_VERSION

    assert REFUSAL_DETECTOR_VERSION == "refusal-lexical-v3"


def test_curly_apostrophes_are_normalised():
    from rag.eval.generation_metrics import is_refusal

    assert is_refusal("I don’t have enough information in the provided articles to answer.")
    assert is_refusal("I can’t find any article that covers this.")


def test_paraphrased_refusals_are_detected():
    from rag.eval.generation_metrics import is_refusal

    for text in (
        "Creating a CMS collection in Webflow is not covered by the Wix Help Center articles provided.",
        "The provided articles cover Members Area features. They do not cover adding a members-only area to Webflow.",
        "The provided articles do not specify a general cost. Pricing information is not covered.",
        "The articles cover abandoned cart emails in Wix, not Shopify. To proceed I would need Wix-specific guidance.",
        "I'm not seeing any article in the provided set that covers changing the preview picture.",
        "None of the articles here describe resetting a Gmail password.",
    ):
        assert is_refusal(text), text


def test_a_caveat_after_a_procedure_is_an_answer_not_a_refusal():
    from rag.eval.generation_metrics import is_refusal

    hedged = (
        "To update the og:image for your site:\n\n1. Open your site's settings.\n2. Click Website "
        "settings.\n3. Upload the image.\n\nThe articles do not provide a general timeline for when "
        "the change appears on social platforms."
    )
    assert not is_refusal(hedged)
    late = "Here is what to do. " * 20 + "The provided articles do not cover the rest."
    assert not is_refusal(late)  # phrase outside the opening window
    assert is_refusal("The provided articles do not cover this. Missing: any 2025 pricing changes.")


def test_detector_matches_the_hand_labelled_unanswerable_answers():
    """45 answers of EXP-0007, labelled by reading each one (data/authored). The
    detector must agree with every label; a phrase-list change that breaks one is a
    visible decision, not a silent metric shift."""
    import yaml

    from rag.eval.generation_metrics import is_refusal
    from rag.paths import DATA_DIR

    rows = yaml.safe_load((DATA_DIR / "authored" / "refusal_labels_v1.yaml").read_text())["rows"]
    assert len(rows) == 45
    disagreements = [r["question"] for r in rows if is_refusal(r["answer"]) != r["refused"]]
    assert disagreements == [], disagreements
