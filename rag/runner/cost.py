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

import math

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

# Rerank calibration, from EXP-0024 (run_20260923_052941_4ada, 200 dev questions,
# 50 candidate documents, fixed-600/100 chunks). The first estimate assumed Cohere's
# "one query, up to 100 documents" search unit and was **17% low**: 200 units
# estimated, **234 billed**.
#
# Why, measured: `rerank_candidates` counts documents, but a document contributes
# every chunk of it the retriever ranked — 58.4 candidate *chunks* per 50 documents.
# Cohere then splits each into ~500-token pieces, and 44% of candidate chunks exceed
# that (candidates average 348 words against the corpus-wide 309 — longer articles
# have more chunks and so more chances to be retrieved). Most queries land near 84
# billable pieces, under the 100-per-unit line; the ~34 whose candidates skew long
# cross it and bill twice.
#
# That is a threshold on a per-query distribution, which no mean-based model
# reproduces — a piece model built from the mean still predicts 200. So the
# multiplier is simply what was billed: 234 / 200. It is calibrated on ONE run and
# has NOT been validated out of sample; the next rerank run is the validation, and
# until then this is an estimate with a known provenance, not a law (DEC-035).
RERANK_CALIBRATION_RUN_ID = "run_20260923_052941_4ada"
RERANK_UNITS_PER_QUERY = 1.17
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
    # Rerank models are billed in the provider's own unit (Cohere's search unit,
    # Fireworks' token) and the numbers are MEASURED from `usage.cost`, never
    # fetched: OpenRouter lists every rerank model at 0 while the calls bill real
    # money (MIS-025). `refresh_pricing` copies this block through untouched.
    rerank: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    rerank_source: str = ""
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
            rerank=doc.get("rerank", {}) or {},
            rerank_source=doc.get("rerank_source", ""),
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

    def rerank_price(self, model: str, provider: str) -> dict[str, Any] | None:
        """The measured billing rule for one pinned rerank model, or None."""
        return (self.rerank.get(model) or {}).get(provider)

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
                "rerank_source": self.rerank_source,
                "chat": self.chat,
                "embeddings": self.embeddings,
                "rerank": self.rerank,
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
        # Copied through, never re-fetched: the listing would overwrite measured
        # prices with the zeros it reports for rerank models (MIS-025).
        rerank=current.rerank,
        rerank_source=current.rerank_source,
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
    retriever_params: dict[str, Any] | None,
    corpus_words: int,
    index_exists: bool,
    n_questions: int,
    pricing: PricingTable,
) -> dict[str, Any]:
    """What a retriever's embedder will spend: the full-corpus embedding if the index
    is not cached (the dominant cost in this project, P2-06), plus the query vectors.
    `retriever_params` is what `Retriever.embedding_params` returned — None for an
    in-process retriever, the `dense` block for a hybrid — so a retriever is costed
    by what it embeds, not by its name."""
    if not retriever_params or retriever_params.get("embedding_backend", "openrouter") != "openrouter":
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


def estimate_rerank_cost(
    *,
    reranker: str,
    estimate_params: dict[str, Any] | None,
    n_questions: int,
    candidate_docs: int,
    candidate_words: int,
    pricing: PricingTable,
) -> dict[str, Any]:
    """What a reranker will bill for a whole run, before it starts (P2-06).

    Reranking is charged **per query**, not per corpus, so unlike an index build it
    scales with the split: the same configuration is $0.20 on `dev` and $6.22 on
    `dev_large`. `candidate_words` is the mean words per candidate chunk, measured
    from the chunk index rather than assumed.

    Cohere bills a search unit per query (documents beyond `docs_per_unit` add
    another); Fireworks bills tokens. Both rates are measured, not listed (MIS-025).
    An LLM reranker is priced from the chat table like any other in-pipeline call.
    """
    if not reranker or not estimate_params:
        return {"rerank_usd": 0.0, "source": "no reranker"}
    model = estimate_params.get("model", "")
    kind = estimate_params.get("kind")
    estimate: dict[str, Any] = {"reranker": reranker, "model": model, "n_questions": n_questions,
                               "candidate_docs": candidate_docs}
    if kind == "chat":
        price = pricing.price("chat", model)
        if not price:
            estimate["price_unavailable"] = f"{model} not in chat pricing {pricing.pricing_version}"
            return estimate
        words = estimate_params.get("candidate_words") or candidate_words
        tokens_in = int(n_questions * candidate_docs * words * WORDS_TO_TOKENS)
        # The model answers with a list of numbers: a few tokens per candidate.
        tokens_out = n_questions * max(4 * candidate_docs, 32)
        estimate["rerank_usd"] = round(tokens_in / 1e6 * price["in"] + tokens_out / 1e6 * price["out"], 4)
        estimate["source"] = (
            f"LLM reranker: {tokens_in:,} in / {tokens_out:,} out at "
            f"${price['in']}/${price['out']} per Mtok"
        )
        return estimate
    provider = estimate_params.get("provider", "")
    rule = pricing.rerank_price(model, provider)
    if not rule:
        estimate["price_unavailable"] = (
            f"{model} ({provider or 'unpinned'}) not in the measured rerank table "
            f"({pricing.pricing_version}). OpenRouter lists rerank models at $0 and bills "
            "real money, so an absent entry is unknown, never free (MIS-025)."
        )
        return estimate
    if rule.get("unit") == "search_unit":
        # Units track candidate *length*, not candidate count, and the relationship is
        # a per-query threshold. The multiplier is measured, not modelled — see above.
        units_per_query = float(rule.get("units_per_query", RERANK_UNITS_PER_QUERY))
        units = math.ceil(n_questions * units_per_query * candidate_docs / 50)
        estimate["rerank_usd"] = round(units * float(rule["usd_per_unit"]), 4)
        estimate["search_units"] = units
        estimate["source"] = (
            f"measured ${rule['usd_per_unit']}/search unit x {units:,} units "
            f"({units_per_query} units/query at 50 candidate docs, calibrated on "
            f"{RERANK_CALIBRATION_RUN_ID}, NOT yet validated out of sample)"
        )
        return estimate
    tokens = int(n_questions * candidate_docs * RERANK_UNITS_PER_QUERY * candidate_words * WORDS_TO_TOKENS)
    estimate["rerank_usd"] = round(tokens / 1e6 * float(rule["usd_per_mtok"]), 4)
    estimate["tokens"] = tokens
    estimate["source"] = f"measured ${rule['usd_per_mtok']}/Mtok x {tokens:,} tokens"
    return estimate


def estimate_run_cost(
    *,
    tier2: dict[str, Any] | None,
    index: dict[str, Any],
    pipeline_llm_usd: float = 0.0,
    rerank: dict[str, Any] | None = None,
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
    if rerank:
        if "rerank_usd" in rerank:
            parts["rerank"] = rerank["rerank_usd"]
        elif "price_unavailable" in rerank:
            unavailable.append(rerank["price_unavailable"])
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
    reranker_meta: dict[str, Any] | None = None,
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
    rerank_usage = (reranker_meta or {}).get("usage") or {}
    if rerank_usage.get("cost_usd"):
        # Provider-reported, straight off `usage.cost`; no table is consulted
        # because no table is trustworthy for rerank models (MIS-025).
        parts["rerank"] = round(float(rerank_usage["cost_usd"]), 6)
        measured.append("rerank")
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
