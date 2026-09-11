"""Pre-run cost estimate for Tier 2 — P0-09.

Printed before a Tier 2 run starts, so the bill is a decision rather than a
discovery. Everything here is an **engineering estimate**, not a measurement, and
is labelled as such — the one kind of forward-looking number this project allows
(CLAUDE.md section 3).

Two things this gets right that the first version got wrong (OQ-018, MIS-008):

1. **Prices are per provider, not per model.** OpenRouter serves one model from many
   providers at prices spanning ~12x, and the judge is pinned to specific ones
   (DEC-032). The model-level price is DeepInfra's; the pinned config pays Cerebras'.
   Per-provider prices live at `/models/<id>/endpoints`, and that is what is read.

2. **Token volume is calibrated on a measured run, not a multiplier.** The old
   `x3.0 call allowance` under-reported judge output by 9x. Ragas emits a lot —
   statement lists, per-claim verdicts with reasons — and the calibration below is
   what one real question actually cost.
"""

from __future__ import annotations

from typing import Any

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{model}/endpoints"

# --- Calibration: measured on run_20260911_045508_9f7c, 5 real dev questions, ---
# --- top_k=5, chunk_size=512, judge openai/gpt-oss-120b pinned to Cerebras. ---
# All three Ragas metrics; 8 chat + 2 embedding calls per question. Embedding cost
# was below $0.00001 per question and is ignored.
CALIBRATION_RUN_ID = "run_20260911_045508_9f7c"
JUDGE_TOKENS_IN_PER_QUESTION = 11_164
JUDGE_TOKENS_OUT_PER_QUESTION = 5_575
CALIBRATION_CONTEXT_WORDS = 5 * 512
# Faithfulness re-sends the retrieved context, so judge input grows with context
# size; output does not, in any way this estimator can predict. Input is scaled
# linearly against the calibration context; output is held at the measured figure.

WORDS_TO_TOKENS = 1.27  # measured on this corpus, DEC-029
GENERATED_TOKENS_OUT_PER_QUESTION = 350  # measured 118-183 on smoke runs; padded


def fetch_model_prices(model_ids: list[str]) -> dict[str, dict[str, float]]:
    """Model-level list prices per million tokens. Empty dict if unreachable.

    These are what OpenRouter shows on the model card, and for a multi-provider
    model they are NOT what a pinned configuration pays. Use `fetch_provider_price`
    for anything with a provider order.
    """
    try:
        import httpx

        payload = httpx.get(OPENROUTER_MODELS_URL, timeout=15.0).json()["data"]
    except Exception:
        return {}
    prices: dict[str, dict[str, float]] = {}
    for model in payload:
        if model["id"] in model_ids:
            price = _parse_pricing(model.get("pricing", {}))
            if price:
                prices[model["id"]] = price
    return prices


def fetch_provider_price(model_id: str, provider_order: tuple[str, ...]) -> dict[str, Any]:
    """The price the first available pinned provider charges for this model.

    OpenRouter routes to the first provider in `order` that is up, so that is the
    provider whose price applies. Returns `provider: None` if none of the pinned
    providers serve the model, which the caller must treat as "unknown", not "free".
    """
    try:
        import httpx

        endpoints = httpx.get(
            OPENROUTER_ENDPOINTS_URL.format(model=model_id), timeout=15.0
        ).json()["data"]["endpoints"]
    except Exception:
        return {"provider": None, "reason": "endpoints API unreachable"}

    by_provider: dict[str, dict[str, float]] = {}
    for endpoint in endpoints:
        name = endpoint.get("provider_name")
        price = _parse_pricing(endpoint.get("pricing", {}))
        if name and price and name not in by_provider:
            by_provider[name] = price

    for provider in provider_order:
        if provider in by_provider:
            return {"provider": provider, **by_provider[provider]}
    return {
        "provider": None,
        "reason": f"none of {list(provider_order)} serve {model_id}",
        "available": sorted(by_provider),
    }


def _parse_pricing(pricing: dict[str, Any]) -> dict[str, float] | None:
    try:
        return {
            "in": float(pricing.get("prompt", 0)) * 1e6,
            "out": float(pricing.get("completion", 0)) * 1e6,
        }
    except (TypeError, ValueError):
        return None


def estimate_tier2_cost(
    *,
    n_questions: int,
    context_words: int,
    generator_model: str,
    judge_model: str,
    judge_provider_order: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Estimate token volume and dollar cost of a Tier 2 run."""
    context_scale = context_words / CALIBRATION_CONTEXT_WORDS

    gen_in = n_questions * (context_words * WORDS_TO_TOKENS + 200)
    gen_out = n_questions * GENERATED_TOKENS_OUT_PER_QUESTION
    judge_in = n_questions * JUDGE_TOKENS_IN_PER_QUESTION * context_scale
    judge_out = n_questions * JUDGE_TOKENS_OUT_PER_QUESTION

    estimate: dict[str, Any] = {
        "n_questions": n_questions,
        "generator_tokens_in": int(gen_in),
        "generator_tokens_out": int(gen_out),
        "judge_tokens_in": int(judge_in),
        "judge_tokens_out": int(judge_out),
        "calibration_run_id": CALIBRATION_RUN_ID,
        "context_scale_vs_calibration": round(context_scale, 2),
        "is_estimate": True,
    }

    # Generator is not pinned, so the model-level price is the best available and
    # is the floor of what routing may charge.
    gen_price = fetch_model_prices([generator_model]).get(generator_model)
    if gen_price:
        estimate["generator_usd"] = round(
            gen_in / 1e6 * gen_price["in"] + gen_out / 1e6 * gen_price["out"], 4
        )
        estimate["generator_price_source"] = "model-level (unpinned; routing may charge more)"

    # Judge is pinned, so the price is the pinned provider's, and nothing else.
    if judge_provider_order:
        judge_price = fetch_provider_price(judge_model, judge_provider_order)
        if judge_price.get("provider"):
            estimate["judge_usd"] = round(
                judge_in / 1e6 * judge_price["in"] + judge_out / 1e6 * judge_price["out"], 4
            )
            estimate["judge_price_source"] = f"provider {judge_price['provider']}"
            estimate["judge_price_per_mtok"] = {"in": judge_price["in"], "out": judge_price["out"]}
        else:
            estimate["judge_price_unavailable"] = judge_price.get("reason", "unknown")
    else:
        judge_price = fetch_model_prices([judge_model]).get(judge_model)
        if judge_price:
            estimate["judge_usd"] = round(
                judge_in / 1e6 * judge_price["in"] + judge_out / 1e6 * judge_price["out"], 4
            )
            estimate["judge_price_source"] = "model-level (unpinned)"

    if "generator_usd" in estimate and "judge_usd" in estimate:
        estimate["total_usd"] = round(estimate["generator_usd"] + estimate["judge_usd"], 4)
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
        f"(calibrated on {estimate['calibration_run_id']}, "
        f"context x{estimate['context_scale_vs_calibration']})",
    ]
    if "total_usd" in estimate:
        price = estimate.get("judge_price_per_mtok", {})
        lines.append(
            f"    est. cost:      ${estimate['generator_usd']:.4f} generator + "
            f"${estimate['judge_usd']:.4f} judge = ${estimate['total_usd']:.4f}"
        )
        lines.append(f"    judge priced at {estimate.get('judge_price_source', '?')}"
                     + (f"  (${price['in']:.3f}/${price['out']:.3f} per Mtok)" if price else ""))
    else:
        reason = estimate.get("judge_price_unavailable", "could not fetch prices")
        lines.append(f"    est. cost:      UNAVAILABLE — {reason}")
        lines.append("    Do not read 'unavailable' as 'free'.")
    lines.append("")
    return "\n".join(lines)
