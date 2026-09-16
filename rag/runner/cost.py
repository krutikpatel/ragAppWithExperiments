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

P2-06 (DEC-050) moves the prices out of the live API and into `configs/pricing.yaml`,
a dated table refreshed by `rag pricing refresh` from the same two endpoints. The
estimate is then reproducible and offline, and the `pricing_version` it used is
recorded on the run row. It also adds the cost that actually dominates this
project — embedding the whole corpus for a new index — and the $2 gate.
"""


from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.paths import CONFIGS_DIR

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{model}/endpoints"
PRICING_PATH = CONFIGS_DIR / "pricing.yaml"
# P2-06: any single run estimated above this halts for explicit approval.
COST_GATE_USD = 2.0
# Query tokens per question for Tier 1 dense retrieval: measured mean question
# length on dev is ~12 words; the qwen3 instruct prefix adds ~30 tokens.
QUERY_TOKENS_PER_QUESTION = 50

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
            "in": round(float(pricing.get("prompt", 0)) * 1e6, 6),
            "out": round(float(pricing.get("completion", 0)) * 1e6, 6),
        }
    except (TypeError, ValueError):
        return None


@dataclass
class PricingTable:
    """`configs/pricing.yaml`: $ per million tokens, per model, per provider.

    `chat[model]["_model"]` is the model-level (unpinned) price; `chat[model][provider]`
    the pinned one. Embedding models are priced on input only. A missing entry is
    "unknown", which the estimator reports as UNAVAILABLE — never as free.
    """

    pricing_version: str
    chat: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    embeddings: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    source: str = ""
    path: Path | None = None

    @classmethod
    def load(cls, path: Path = PRICING_PATH) -> PricingTable:
        import yaml

        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. Run `rag pricing refresh` to build it from OpenRouter; "
                "the estimator does not guess prices."
            )
        doc = yaml.safe_load(path.read_text()) or {}
        return cls(
            pricing_version=str(doc.get("pricing_version", "")),
            chat=doc.get("chat", {}) or {},
            embeddings=doc.get("embeddings", {}) or {},
            source=doc.get("source", ""),
            path=path,
        )

    def price(self, kind: str, model: str, provider: str | None = None) -> dict[str, float] | None:
        table = self.chat if kind == "chat" else self.embeddings
        entry = table.get(model) or {}
        return entry.get(provider or "_model")

    def pinned_price(self, kind: str, model: str, provider_order: tuple[str, ...]) -> dict[str, Any]:
        """First pinned provider with a recorded price — the one routing pays."""
        entry = (self.chat if kind == "chat" else self.embeddings).get(model) or {}
        for provider in provider_order:
            if provider in entry:
                return {"provider": provider, **entry[provider]}
        return {
            "provider": None,
            "reason": f"none of {list(provider_order)} priced for {model} in pricing {self.pricing_version}",
            "available": sorted(p for p in entry if p != "_model"),
        }

    def save(self, path: Path | None = None) -> Path:
        import yaml

        path = path or self.path or PRICING_PATH
        header = (
            "# Prices in USD per million tokens, per model, per provider. `_model` is the\n"
            "# model-level (unpinned) price; a named provider is what a pinned config pays\n"
            "# (DEC-032/034: the two differ ~12x for the judge). Written by `rag pricing\n"
            "# refresh` from OpenRouter's /models and /models/<id>/endpoints; edit the model\n"
            "# list by hand, never the numbers. The estimator records pricing_version on\n"
            "# every run (P2-06, DEC-050).\n"
        )
        body = yaml.safe_dump(
            {
                "pricing_version": self.pricing_version,
                "source": self.source,
                "chat": self.chat,
                "embeddings": self.embeddings,
            },
            sort_keys=False,
        )
        path.write_text(header + body)
        return path


def refresh_pricing(path: Path = PRICING_PATH) -> PricingTable:
    """Re-fetch every model already listed in the table and stamp today's date.

    The model list is curated by hand (a model enters the table when a DEC entry
    chooses it); the numbers never are.
    """
    current = PricingTable.load(path) if path.exists() else PricingTable(pricing_version="")
    chat: dict[str, dict[str, dict[str, float]]] = {}
    for model in current.chat:
        chat[model] = _fetch_all_prices(model)
    embeddings: dict[str, dict[str, dict[str, float]]] = {}
    for model in current.embeddings:
        embeddings[model] = {k: {"in": v["in"]} for k, v in _fetch_all_prices(model).items()}
    fresh = PricingTable(
        pricing_version=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        chat=chat,
        embeddings=embeddings,
        source="OpenRouter /api/v1/models (model-level) and /api/v1/models/<id>/endpoints (per provider)",
        path=path,
    )
    fresh.save(path)
    return fresh


def _fetch_all_prices(model: str) -> dict[str, dict[str, float]]:
    """`_model` plus every provider serving `model`, from the two endpoints."""
    import httpx

    out: dict[str, dict[str, float]] = {}
    model_level = fetch_model_prices([model]).get(model)
    if model_level:
        out["_model"] = model_level
    endpoints = httpx.get(OPENROUTER_ENDPOINTS_URL.format(model=model), timeout=20.0).json()["data"]["endpoints"]
    for endpoint in endpoints:
        name = endpoint.get("provider_name")
        price = _parse_pricing(endpoint.get("pricing", {}))
        if name and price and name not in out:
            out[name] = price
    if "_model" not in out and out:
        # Embedding models are absent from /models (CLAUDE.md §10); take the cheapest
        # provider as the model-level reference so an unpinned estimate has a floor.
        out["_model"] = min((v for k, v in out.items()), key=lambda v: v["in"])
    return out


def estimate_tier2_cost(
    *,
    n_questions: int,
    context_words: int,
    generator_model: str,
    judge_model: str,
    judge_provider_order: tuple[str, ...] = (),
    n_judged: int | None = None,
    pricing: PricingTable | None = None,
) -> dict[str, Any]:
    """Estimate token volume and dollar cost of a Tier 2 run."""
    pricing = pricing or PricingTable.load()
    context_scale = context_words / CALIBRATION_CONTEXT_WORDS

    gen_in = n_questions * (context_words * WORDS_TO_TOKENS + 200)
    gen_out = n_questions * GENERATED_TOKENS_OUT_PER_QUESTION
    # Questions without a reference answer are not judged (DEC-044); the
    # unanswerable split has none, so its judge cost is zero, not 45 questions' worth.
    n_judged = n_questions if n_judged is None else n_judged
    judge_in = n_judged * JUDGE_TOKENS_IN_PER_QUESTION * context_scale
    judge_out = n_judged * JUDGE_TOKENS_OUT_PER_QUESTION

    estimate: dict[str, Any] = {
        "n_questions": n_questions,
        "n_judged": n_judged,
        "generator_tokens_in": int(gen_in),
        "generator_tokens_out": int(gen_out),
        "judge_tokens_in": int(judge_in),
        "judge_tokens_out": int(judge_out),
        "calibration_run_id": CALIBRATION_RUN_ID,
        "context_scale_vs_calibration": round(context_scale, 2),
        "pricing_version": pricing.pricing_version,
        "is_estimate": True,
    }

    # Generator is not pinned, so the model-level price is the best available and
    # is the floor of what routing may charge.
    gen_price = pricing.price("chat", generator_model)
    if gen_price:
        estimate["generator_usd"] = round(
            gen_in / 1e6 * gen_price["in"] + gen_out / 1e6 * gen_price["out"], 4
        )
        estimate["generator_price_source"] = "model-level (unpinned; routing may charge more)"

    # Judge is pinned, so the price is the pinned provider's, and nothing else.
    if judge_provider_order:
        judge_price = pricing.pinned_price("chat", judge_model, judge_provider_order)
        if judge_price.get("provider"):
            estimate["judge_usd"] = round(
                judge_in / 1e6 * judge_price["in"] + judge_out / 1e6 * judge_price["out"], 4
            )
            estimate["judge_price_source"] = f"provider {judge_price['provider']}"
            estimate["judge_price_per_mtok"] = {"in": judge_price["in"], "out": judge_price["out"]}
        else:
            estimate["judge_price_unavailable"] = judge_price.get("reason", "unknown")
    else:
        judge_price = pricing.price("chat", judge_model)
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


# --- P2-06: the whole-run estimate, the gate, and actuals ---------------------------

def estimate_index_cost(
    *,
    retriever: str,
    retriever_params: dict[str, Any],
    corpus_words: int,
    index_exists: bool,
    n_questions: int,
    pricing: PricingTable,
) -> dict[str, Any]:
    """What a dense retriever will spend: the full-corpus embedding if the index is
    not cached (the dominant cost in this project, P2-06), plus the query vectors.
    Zero for in-process retrievers."""
    if retriever != "dense" or retriever_params.get("embedding_backend", "openrouter") != "openrouter":
        return {"index_usd": 0.0, "query_usd": 0.0, "index_exists": True, "source": "in-process retriever"}
    model = retriever_params.get("embedding_model", "")
    provider = retriever_params.get("embedding_provider", "")
    price = pricing.pinned_price("embeddings", model, (provider,)) if provider else {"provider": None}
    if not price.get("provider"):
        price = {"provider": None, **(pricing.price("embeddings", model) or {})}
    estimate: dict[str, Any] = {
        "embedding_model": model,
        "embedding_provider": provider,
        "index_exists": index_exists,
        "corpus_tokens": int(corpus_words * WORDS_TO_TOKENS),
        "query_tokens": n_questions * QUERY_TOKENS_PER_QUESTION,
    }
    if "in" not in price:
        estimate["price_unavailable"] = f"{model} ({provider or 'unpinned'}) not in pricing {pricing.pricing_version}"
        return estimate
    per_tok = price["in"] / 1e6
    estimate["index_usd"] = 0.0 if index_exists else round(estimate["corpus_tokens"] * per_tok, 4)
    estimate["query_usd"] = round(estimate["query_tokens"] * per_tok, 6)
    estimate["source"] = (
        f"embeddings at ${price['in']:.3f}/Mtok ({price.get('provider') or 'model-level'}); "
        + ("index cached, build cost 0" if index_exists else "index NOT cached — full corpus embed")
    )
    return estimate


def estimate_run_cost(
    *,
    tier2: dict[str, Any] | None,
    index: dict[str, Any],
    pipeline_llm_usd: float = 0.0,
) -> dict[str, Any]:
    """Total pre-run estimate with the breakdown of what drives it."""
    parts: dict[str, float] = {}
    unavailable: list[str] = []
    if "index_usd" in index:
        parts["index_build"] = index["index_usd"]
        parts["query_embeddings"] = index["query_usd"]
    elif "price_unavailable" in index:
        unavailable.append(index["price_unavailable"])
    if tier2:
        if "total_usd" in tier2:
            parts["generator"] = tier2["generator_usd"]
            parts["judge"] = tier2["judge_usd"]
        else:
            unavailable.append(tier2.get("judge_price_unavailable", "generator or judge price unavailable"))
    if pipeline_llm_usd:
        parts["pipeline_llm"] = pipeline_llm_usd
    total = round(sum(parts.values()), 4)
    driver = max(parts, key=parts.get) if parts else None
    return {
        "total_usd": total,
        "parts_usd": parts,
        "driver": driver,
        "unavailable": unavailable,
        "gate_usd": COST_GATE_USD,
        "over_gate": total > COST_GATE_USD or bool(unavailable),
        "is_estimate": True,
    }


class CostGateError(RuntimeError):
    """Estimated cost is above the gate and no approval was given. The run does not
    start; nothing is written to the results store."""


def format_run_estimate(estimate: dict[str, Any], *, pricing_version: str) -> str:
    lines = ["", f"*** RUN COST ESTIMATE (estimate, not a measurement; pricing {pricing_version}) ***"]
    for name, usd in estimate["parts_usd"].items():
        marker = "  <- drives the estimate" if name == estimate["driver"] and usd > 0 else ""
        lines.append(f"    {name:<18} ${usd:.4f}{marker}")
    for reason in estimate["unavailable"]:
        lines.append(f"    UNAVAILABLE: {reason} — not read as free")
    lines.append(f"    total              ${estimate['total_usd']:.4f}   (gate ${estimate['gate_usd']:.2f})")
    lines.append("")
    return "\n".join(lines)


def actual_run_cost(
    *,
    retriever_meta: dict[str, Any],
    generator_tokens_in: int,
    generator_tokens_out: int,
    generator_model: str,
    judge_estimate_usd: float | None,
    pipeline_llm_stats: dict[str, Any] | None,
    pricing: PricingTable,
) -> dict[str, Any]:
    """What the run spent, from provider-reported usage where it exists.

    Embedding cost is exact (provider-reported, split into the build and the
    queries). Generator cost is exact tokens at the table price. The judge's is the
    pre-run estimate: Ragas does not surface token usage (P0-09). The label says
    which parts are measured.
    """
    parts: dict[str, float] = {}
    measured: list[str] = []
    estimated: list[str] = []
    embedder = (retriever_meta.get("embedder_now") or {}).get("usage") or {}
    if embedder:
        total = float(embedder.get("cost_usd", 0.0))
        build = 0.0 if retriever_meta.get("cache_hit") else float(
            ((retriever_meta.get("embedder") or {}).get("usage") or {}).get("cost_usd", 0.0)
        )
        parts["index_build"] = round(build, 6)
        parts["query_embeddings"] = round(max(total - build, 0.0), 6)
        measured += ["index_build", "query_embeddings"]
    if generator_tokens_in or generator_tokens_out:
        price = pricing.price("chat", generator_model)
        if price:
            parts["generator"] = round(
                generator_tokens_in / 1e6 * price["in"] + generator_tokens_out / 1e6 * price["out"], 5
            )
            measured.append("generator")
    if judge_estimate_usd is not None:
        parts["judge"] = judge_estimate_usd
        estimated.append("judge")
    if pipeline_llm_stats:
        price = pricing.price("chat", pipeline_llm_stats.get("model", ""))
        if price:
            parts["pipeline_llm"] = round(
                pipeline_llm_stats.get("tokens_in", 0) / 1e6 * price["in"]
                + pipeline_llm_stats.get("tokens_out", 0) / 1e6 * price["out"], 5
            )
            measured.append("pipeline_llm")
    return {
        "total_usd": round(sum(parts.values()), 5),
        "parts_usd": parts,
        "measured": measured,
        "estimated": estimated,
        "source": (
            "exact" if not estimated
            else f"exact for {measured or 'nothing'}; pre-run estimate for {estimated}"
        ),
    }
