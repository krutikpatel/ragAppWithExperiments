"""Pre-run cost estimate for Tier 2 — P0-09.

Printed before a Tier 2 run starts, so the bill is a decision rather than a
discovery. Everything here is an **engineering estimate**, not a measurement:
token counts are approximated from context sizes and Ragas's call pattern, and
prices are OpenRouter list prices fetched at call time.

Cost and latency estimates are the one kind of forward-looking number this project
allows (CLAUDE.md section 3), provided they are labelled as estimates. They are.
"""

from __future__ import annotations

from typing import Any

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Ragas faithfulness decomposes an answer into claims and verifies each one; answer
# correctness generates and classifies statements. Both are several calls per
# question, each re-sending the context. This multiplier is a rough allowance, not a
# measurement — the first real Tier 2 run replaces it with observed token counts.
RAGAS_CALL_MULTIPLIER = 3.0

WORDS_TO_TOKENS = 1.35


def fetch_prices(model_ids: list[str]) -> dict[str, dict[str, float]]:
    """OpenRouter list prices per million tokens. Empty dict if unreachable."""
    try:
        import httpx

        payload = httpx.get(OPENROUTER_MODELS_URL, timeout=15.0).json()["data"]
    except Exception:
        return {}
    prices = {}
    for model in payload:
        if model["id"] in model_ids:
            pricing = model.get("pricing", {})
            try:
                prices[model["id"]] = {
                    "in": float(pricing.get("prompt", 0)) * 1e6,
                    "out": float(pricing.get("completion", 0)) * 1e6,
                }
            except (TypeError, ValueError):
                continue
    return prices


def estimate_tier2_cost(
    *,
    n_questions: int,
    context_words: int,
    generator_model: str,
    judge_model: str,
    generated_words: int = 250,
) -> dict[str, Any]:
    """Estimate the token volume and dollar cost of a Tier 2 run."""
    context_tokens = context_words * WORDS_TO_TOKENS
    generated_tokens = generated_words * WORDS_TO_TOKENS

    gen_in = n_questions * (context_tokens + 200)
    gen_out = n_questions * generated_tokens
    judge_in = n_questions * (context_tokens + generated_tokens + 400) * RAGAS_CALL_MULTIPLIER
    judge_out = n_questions * 200 * RAGAS_CALL_MULTIPLIER

    prices = fetch_prices([generator_model, judge_model])
    estimate: dict[str, Any] = {
        "n_questions": n_questions,
        "generator_tokens_in": int(gen_in),
        "generator_tokens_out": int(gen_out),
        "judge_tokens_in": int(judge_in),
        "judge_tokens_out": int(judge_out),
        "ragas_call_multiplier": RAGAS_CALL_MULTIPLIER,
        "is_estimate": True,
    }
    if generator_model in prices and judge_model in prices:
        gen_price, judge_price = prices[generator_model], prices[judge_model]
        estimate["generator_usd"] = round(
            gen_in / 1e6 * gen_price["in"] + gen_out / 1e6 * gen_price["out"], 4
        )
        estimate["judge_usd"] = round(
            judge_in / 1e6 * judge_price["in"] + judge_out / 1e6 * judge_price["out"], 4
        )
        estimate["total_usd"] = round(estimate["generator_usd"] + estimate["judge_usd"], 4)
    else:
        estimate["prices_unavailable"] = True
    return estimate


def format_estimate(estimate: dict[str, Any]) -> str:
    lines = [
        "",
        "*** TIER 2 COST ESTIMATE (estimate, not a measurement) ***",
        f"    questions:      {estimate['n_questions']}",
        f"    generator:      {estimate['generator_tokens_in']:,} in / "
        f"{estimate['generator_tokens_out']:,} out",
        f"    judge (Ragas):  {estimate['judge_tokens_in']:,} in / "
        f"{estimate['judge_tokens_out']:,} out "
        f"(x{estimate['ragas_call_multiplier']} call allowance)",
    ]
    if "total_usd" in estimate:
        lines.append(
            f"    est. cost:      ${estimate['generator_usd']:.2f} generator + "
            f"${estimate['judge_usd']:.2f} judge = ${estimate['total_usd']:.2f}"
        )
    else:
        lines.append("    est. cost:      unavailable (could not fetch OpenRouter prices)")
    lines.append("")
    return "\n".join(lines)
