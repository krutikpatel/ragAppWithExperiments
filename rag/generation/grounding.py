"""Groundedness self-check — P2-14, Axis 7.

After the answer is written it is shown back to a model together with the articles it
was written from, and asked whether every step is supported. An answer judged
unsupported is replaced by the system's standard refusal.

This is the only technique in Axis 7 that costs a second LLM call per query, so P2-14
requires three numbers alongside whatever it fixes: its added latency, its cost, and its
own false-refusal contribution — how many answers it rejected that were actually fine.
All three are recorded here rather than inferred later.

Two design choices worth stating:

- **A refusal is always supported.** The check is never asked to approve the system's own
  refusals, because a checker that rejects "the articles do not cover this" manufactures
  false refusals out of correct behaviour. It is short-circuited without a call, which
  also means refusals cost nothing to check.
- **An unparseable verdict keeps the answer.** The check can only ever *remove* an
  answer, so when it fails or returns something that is neither word, the safe direction
  is to leave the answer alone and count the failure. Refusing on a broken check would
  let a provider outage look like a grounding finding (MIS-034, preflight 43).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from rag.eval.generation_metrics import is_refusal
from rag.prompts import load_prompt

if TYPE_CHECKING:
    from rag.generation.pipeline_llm import PipelineLLM

PROMPT_ID = "groundedness_check"
PROMPT_VERSION = "v1"

# What replaces an answer the check rejects. Byte-identical to the refusal the prompts
# ask for, so the refusal detector treats it exactly like a model-written refusal —
# otherwise this technique's refusals would not be counted as refusals at all.
REFUSAL_TEXT = "The provided articles do not cover this."

SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"


def parse_verdict(output: str) -> bool | None:
    """True = supported, False = unsupported, None = unparseable.

    Checks UNSUPPORTED first: it contains SUPPORTED as a substring, so testing for
    SUPPORTED first would read every rejection as an approval — a bug that would make
    the technique silently do nothing and look like a null result.
    """
    text = (output or "").strip().upper()
    if not text:
        return None
    if UNSUPPORTED in text:
        return False
    if SUPPORTED in text:
        return True
    return None


class GroundednessCheck:
    """Rejects answers the model judges unsupported by their own context."""

    name = "self_check"

    def __init__(self, llm: PipelineLLM) -> None:
        self.llm = llm
        self.prompt = load_prompt(PROMPT_ID, PROMPT_VERSION)
        self.stats = {
            "answers_seen": 0,
            "refusals_skipped": 0,
            "checked": 0,
            "rejected": 0,
            "unparseable": 0,
            "call_failed": 0,
            "check_seconds": 0.0,
        }
        self.failures: list[dict[str, str]] = []

    def check(self, *, question_id: str, question: str, context: str, answer: str) -> tuple[str, dict[str, Any]]:
        """Returns the answer to keep and a per-question record."""
        self.stats["answers_seen"] += 1
        if is_refusal(answer):
            # Never ask the checker to approve a refusal (see module docstring).
            self.stats["refusals_skipped"] += 1
            return answer, {"grounding_checked": 0.0, "grounding_rejected": 0.0}

        rendered = self.prompt.render(context=context, question=question, answer=answer)
        started = time.perf_counter()
        try:
            output = self.llm.complete(
                question_id=f"ground:{question_id}",
                prompt_id=PROMPT_ID,
                prompt_version=PROMPT_VERSION,
                prompt_text=rendered,
            )
        except Exception as exc:  # noqa: BLE001 - counted, not swallowed
            self.stats["call_failed"] += 1
            self.stats["check_seconds"] += time.perf_counter() - started
            if len(self.failures) < 20:
                self.failures.append(
                    {"question_id": question_id, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
                )
            return answer, {"grounding_checked": 0.0, "grounding_rejected": 0.0,
                            "grounding_call_failed": 1.0}
        self.stats["check_seconds"] += time.perf_counter() - started
        self.stats["checked"] += 1

        verdict = parse_verdict(output)
        if verdict is None:
            self.stats["unparseable"] += 1
            return answer, {"grounding_checked": 1.0, "grounding_rejected": 0.0,
                            "grounding_unparseable": 1.0}
        if verdict:
            return answer, {"grounding_checked": 1.0, "grounding_rejected": 0.0}
        self.stats["rejected"] += 1
        return REFUSAL_TEXT, {"grounding_checked": 1.0, "grounding_rejected": 1.0}

    def provenance(self) -> dict[str, Any]:
        seen, checked = self.stats["answers_seen"], self.stats["checked"]
        return {
            "grounding_check": self.name,
            "prompt": f"{PROMPT_ID}@{PROMPT_VERSION}",
            "prompt_hash": self.prompt.content_hash,
            # Of the answers it actually judged — refusals are excluded because they
            # were never at risk of rejection.
            "rejection_rate": round(self.stats["rejected"] / checked, 4) if checked else None,
            "mean_check_ms": round(1000 * self.stats["check_seconds"] / seen, 1) if seen else None,
            "failures": self.failures,
            "llm": self.llm.stats(),
            **self.stats,
        }
