"""P0-09 / OQ-018 — the pre-run Tier 2 cost estimate."""

from __future__ import annotations

import pytest

from rag.runner import cost
from rag.runner.cost import estimate_tier2_cost, format_estimate


@pytest.fixture(autouse=True)
def offline_prices(monkeypatch):
    """Tests must not hit OpenRouter. Serve fixed prices instead."""
    monkeypatch.setattr(
        cost,
        "fetch_model_prices",
        lambda ids: {i: {"in": 0.05, "out": 0.40} for i in ids},
    )

    def provider_price(model_id, order):
        table = {"Cerebras": {"in": 0.35, "out": 0.75}, "Groq": {"in": 0.15, "out": 0.60}}
        for p in order:
            if p in table:
                return {"provider": p, **table[p]}
        return {"provider": None, "reason": "none pinned", "available": sorted(table)}

    monkeypatch.setattr(cost, "fetch_provider_price", provider_price)


def _estimate(**overrides):
    kwargs = dict(
        n_questions=100,
        context_words=2560,
        generator_model="openai/gpt-5-nano",
        judge_model="openai/gpt-oss-120b",
        judge_provider_order=("Cerebras", "Groq"),
    )
    kwargs.update(overrides)
    return estimate_tier2_cost(**kwargs)


def test_estimate_is_labelled_as_an_estimate():
    """Cost is the one forward-looking number allowed, and only when labelled."""
    estimate = _estimate()
    assert estimate["is_estimate"] is True
    assert "estimate, not a measurement" in format_estimate(estimate)


def test_judge_is_priced_at_the_pinned_provider_not_the_model():
    """MIS-008: the model-level price is not what a pinned configuration pays."""
    pinned = _estimate()
    assert pinned["judge_price_source"] == "provider Cerebras"
    assert pinned["judge_price_per_mtok"] == {"in": 0.35, "out": 0.75}

    unpinned = _estimate(judge_provider_order=())
    assert "model-level" in unpinned["judge_price_source"]
    assert pinned["judge_usd"] > unpinned["judge_usd"]


def test_first_available_pinned_provider_wins():
    estimate = _estimate(judge_provider_order=("Nowhere", "Groq", "Cerebras"))
    assert estimate["judge_price_source"] == "provider Groq"


def test_unknown_provider_is_unavailable_not_free():
    estimate = _estimate(judge_provider_order=("Nowhere",))
    assert "judge_usd" not in estimate
    assert "total_usd" not in estimate
    rendered = format_estimate(estimate)
    assert "UNAVAILABLE" in rendered and "Do not read 'unavailable' as 'free'" in rendered


def test_token_volume_is_calibrated_on_a_real_run():
    estimate = _estimate(n_questions=1, context_words=cost.CALIBRATION_CONTEXT_WORDS)
    assert estimate["judge_tokens_in"] == cost.JUDGE_TOKENS_IN_PER_QUESTION
    assert estimate["judge_tokens_out"] == cost.JUDGE_TOKENS_OUT_PER_QUESTION
    assert estimate["calibration_run_id"].startswith("run_")


def test_judge_input_scales_with_context_but_output_does_not():
    """Faithfulness re-sends the context; nothing about the output size follows it."""
    small, large = _estimate(context_words=1280), _estimate(context_words=5120)
    assert large["judge_tokens_in"] == pytest.approx(small["judge_tokens_in"] * 4)
    assert large["judge_tokens_out"] == small["judge_tokens_out"]


def test_cost_scales_with_question_count():
    small, large = _estimate(n_questions=10), _estimate(n_questions=100)
    assert large["judge_usd"] == pytest.approx(small["judge_usd"] * 10, rel=1e-3)
