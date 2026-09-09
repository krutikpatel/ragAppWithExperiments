"""P0-09 — the pre-run Tier 2 cost estimate."""

from __future__ import annotations

from rag.runner.cost import estimate_tier2_cost, format_estimate


def _estimate(**overrides):
    kwargs = dict(
        n_questions=100,
        context_words=2560,
        generator_model="openai/gpt-5-nano",
        judge_model="anthropic/claude-sonnet-5",
    )
    kwargs.update(overrides)
    return estimate_tier2_cost(**kwargs)


def test_estimate_is_labelled_as_an_estimate():
    """Cost is the one forward-looking number allowed, and only when labelled."""
    estimate = _estimate()
    assert estimate["is_estimate"] is True
    assert "estimate, not a measurement" in format_estimate(estimate)


def test_judge_volume_accounts_for_ragas_multiple_calls():
    estimate = _estimate()
    assert estimate["ragas_call_multiplier"] > 1
    assert estimate["judge_tokens_in"] > estimate["generator_tokens_in"]


def test_cost_scales_with_question_count():
    small, large = _estimate(n_questions=10), _estimate(n_questions=100)
    assert large["judge_tokens_in"] == small["judge_tokens_in"] * 10


def test_missing_prices_degrade_without_failing():
    estimate = _estimate(judge_model="not/a-real-model")
    assert estimate.get("prices_unavailable") is True
    assert "unavailable" in format_estimate(estimate)
