"""Run configuration — P0-09 / P0-10.

Frozen, hashable, and the single input to a run: `run(config) -> row in the results
store`. `config_hash` covers everything that can change a number, so two runs with
the same hash should produce the same metrics, and a differing hash is the first
thing to look at when they do not.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any

from rag.hashing import canonical_json, short_id
from rag.retrieval.pooling import DEFAULT_POOLING, POOLING_RULES


class EvalTier(str, Enum):
    """P0-09. Tier 1 is the default because it is the one you can afford to repeat.

    TIER_1  retrieval metrics only. Zero LLM calls, zero cost.
    TIER_2  Tier 1 plus generation and judge metrics. Promoted configs only.
    """

    TIER_1 = "tier1"
    TIER_2 = "tier2"

    @property
    def uses_llm(self) -> bool:
        return self is EvalTier.TIER_2


@dataclass(frozen=True)
class RunConfig:
    """Everything that determines a run's numbers."""

    name: str
    split: str = "dev"
    eval_tier: EvalTier = EvalTier.TIER_1

    retriever: str = "bm25"
    retriever_params: dict[str, Any] = field(default_factory=dict)
    chunker: str = "fixed_token"
    chunker_params: dict[str, Any] = field(default_factory=lambda: {"chunk_size": 512, "overlap": 0})
    # How many chunks are ranked for *scoring*. Metrics are reported at k up to 20
    # documents, and you cannot measure recall@20 having retrieved 5 — the number
    # would silently be recall@5 wearing a different label. Depth is therefore
    # separate from `top_k`, which is how many chunks reach the generator's context.
    retrieval_depth: int = 100
    top_k: int = 5
    doc_pooling: str = DEFAULT_POOLING

    # Tier 2 only. Empty by default: model choice is Krutik's call, not a default
    # this file gets to make. See CLAUDE.md section 10.
    generator_model: str = ""
    generator_prompt: str = "answer@v1"
    generator_max_tokens: int = 2000
    generator_reasoning_effort: str = "minimal"
    judge_model: str = ""
    judge_temperature: float = 0.0
    judge_max_tokens: int = 4096
    # Ragas AnswerRelevancy needs an embedding model. OpenRouter supplies them, so
    # this is empty only because the model is unchosen — not because it is unavailable
    # (DEC-026 corrects DEC-022). Empty means answer_relevance is recorded as skipped.
    judge_embedding_model: str = ""
    context_max_tokens: int = 6000

    # Tier 2 is expensive per question — Ragas faithfulness decomposes an answer into
    # claims and verifies each one, several LLM calls per metric. So Tier 2 scores a
    # fixed subsample by default; the same questions every run, so results stay
    # comparable. Tier 1 is free and always runs the whole split.
    eval_subsample_size: int = 100
    eval_subsample_seed: int = 7
    full_eval: bool = False

    seed: int = 1
    # Set only by a harness smoke test. Runs carrying it are marked in the store and
    # must never be written into docs/EXPERIMENTS.md as an experiment.
    harness_smoke_test: bool = False

    def __post_init__(self) -> None:
        if self.doc_pooling not in POOLING_RULES:
            raise ValueError(f"unknown doc_pooling {self.doc_pooling!r}; known: {POOLING_RULES}")
        if self.top_k < 1:
            raise ValueError("top_k must be at least 1")
        if self.retrieval_depth < self.top_k:
            raise ValueError(
                f"retrieval_depth ({self.retrieval_depth}) must be at least top_k "
                f"({self.top_k}): the context cannot hold chunks that were never ranked"
            )
        if self.eval_tier.uses_llm and not self.harness_smoke_test:
            missing = [
                name
                for name, value in (
                    ("generator_model", self.generator_model),
                    ("judge_model", self.judge_model),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"Tier 2 needs {' and '.join(missing)}. Model choice is a decision "
                    "for Krutik with a DEC entry, not a default — see CLAUDE.md "
                    "section 10."
                )
            # P0-07: a judge from the generator's own family grades its own lineage.
            # The bias is real and unmeasured, so it is refused rather than noted.
            if self.generator_family == self.judge_family:
                raise ValueError(
                    f"judge and generator are both from the {self.judge_family!r} "
                    "family. Same-family judging carries self-preference bias; P0-07 "
                    "requires different families. Pick a judge from another provider."
                )
        if self.eval_subsample_size < 1:
            raise ValueError("eval_subsample_size must be at least 1")

    @property
    def generator_family(self) -> str:
        from rag.eval.judge import model_family

        return model_family(self.generator_model)

    @property
    def judge_family(self) -> str:
        from rag.eval.judge import model_family

        return model_family(self.judge_model)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["eval_tier"] = self.eval_tier.value
        return data

    @property
    def config_hash(self) -> str:
        """Stable over field order; changes when anything that moves a number moves.

        `name` is excluded: renaming a run does not change its numbers, and two runs
        of the same configuration should collide here on purpose.
        """
        payload = {k: v for k, v in self.as_dict().items() if k != "name"}
        return short_id(canonical_json(payload), length=16)

    def with_(self, **changes: Any) -> RunConfig:
        return replace(self, **changes)


def load_config_file(path: str | Any) -> RunConfig:
    """Load a `RunConfig` from a YAML file. Unknown keys are an error, not a shrug.

    A typo in a config field would otherwise be silently ignored and the run would
    record settings nobody chose.
    """
    from pathlib import Path

    import yaml

    document = yaml.safe_load(Path(path).read_text()) or {}
    known = set(RunConfig.__dataclass_fields__)
    unknown = sorted(set(document) - known)
    if unknown:
        raise ValueError(f"unknown config keys {unknown}; known keys: {sorted(known)}")
    if "eval_tier" in document:
        document["eval_tier"] = EvalTier(document["eval_tier"])
    return RunConfig(**document)
