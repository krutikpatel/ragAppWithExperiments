"""P2-14 — Axis 7: the abstention trade-off curve.

The curve is the deliverable, so these tests are about the two definitions that make it
mean anything: a false refusal is only counted where the gold document actually reached
the generator (MIS-012), and the refusal is recounted with the CURRENT detector rather
than read from a stored flag (MIS-037).
"""

from __future__ import annotations

import json

import pytest

from rag.eval.abstention import Point, format_curve, free_lunch, question_signals, sweep


def row(top1, answer, gold_in_context):
    return {
        "scores": json.dumps([top1, top1 - 0.05]),
        "generated_answer": answer,
        "metrics_json": json.dumps({"gold_in_context": gold_in_context}),
    }


ANSWER = "1. Open Settings. 2. Click Save. [doc:abc12345]"
REFUSAL = "The provided articles do not cover this."


def test_false_refusal_is_counted_only_where_the_gold_reached_the_generator():
    """MIS-012: refusing when retrieval failed is correct behaviour. Counting it as a
    false refusal would punish the system for the one thing it got right."""
    dev = {
        "a": row(0.90, ANSWER, 1.0),      # answerable, answered
        "b": row(0.60, REFUSAL, 1.0),     # answerable, refused -> a FALSE refusal
        "c": row(0.60, REFUSAL, 0.0),     # gold never arrived -> correct refusal
        "d": row(0.60, ANSWER, 0.0),      # gold never arrived, answered anyway
    }
    unans = {"u": row(0.50, ANSWER, None)}
    point = sweep(dev, unans, [0.0])[0]
    assert point.n_answerable == 2, "only questions with gold in context are answerable"
    assert point.false_refusal_rate == pytest.approx(0.5)   # b of {a, b}
    assert point.dev_answered_rate == pytest.approx(0.5)    # a and d of four


def test_the_threshold_composes_with_the_generators_own_refusal():
    """At threshold T the system answers only when top1 >= T AND the generator chose to
    answer. A question the generator already refused cannot become a false answer."""
    unans = {
        "high_answered": row(0.90, ANSWER, None),   # a false answer until T > 0.90
        "high_refused": row(0.90, REFUSAL, None),   # never a false answer
        "low_answered": row(0.40, ANSWER, None),    # a false answer until T > 0.40
    }
    dev = {"a": row(0.95, ANSWER, 1.0)}
    at_zero, at_half, at_top = sweep(dev, unans, [0.0, 0.5, 0.95])
    assert at_zero.false_answer_rate == pytest.approx(2 / 3)
    assert at_half.false_answer_rate == pytest.approx(1 / 3)
    assert at_top.false_answer_rate == 0.0


def test_refusal_is_recounted_with_the_current_detector_not_the_stored_flag():
    """MIS-037: a stored flag carries whichever detector produced it, and a fixed
    detector leaves the ledger stale. The curve recomputes from the answer text."""
    curly = "The provided articles don’t cover this."   # v1 missed this apostrophe
    rows = {"a": {"scores": json.dumps([0.8]), "generated_answer": curly,
                  "metrics_json": json.dumps({"refused": 0.0, "gold_in_context": 1.0})}}
    signals = question_signals(rows)
    assert signals[0]["refused"] is True, "recount must not trust the stale stored flag"


def test_questions_without_scores_are_skipped_not_counted_as_zero():
    rows = {"a": {"scores": "[]", "generated_answer": ANSWER,
                  "metrics_json": "{}"},
            "b": row(0.7, ANSWER, 1.0)}
    assert len(question_signals(rows)) == 1


def test_sweep_refuses_input_it_cannot_score():
    with pytest.raises(ValueError, match="per-question scores"):
        sweep({}, {"u": row(0.5, ANSWER, None)}, [0.0])
    with pytest.raises(ValueError, match="gold document in context"):
        sweep({"a": row(0.9, ANSWER, 0.0)}, {"u": row(0.5, ANSWER, None)}, [0.0])


def test_free_lunch_finds_the_highest_threshold_that_costs_nothing():
    """The one part of a trade-off curve that is not a trade. It must return None when
    there is none, never a threshold that quietly costs refusals."""
    base = Point(0.0, 0.30, 0.05, 0.90, 40, 60)
    free = Point(0.5, 0.20, 0.05, 0.90, 40, 60)     # fewer false answers, same refusals
    higher = Point(0.6, 0.10, 0.09, 0.80, 40, 60)   # cheaper answers, costs refusals
    assert free_lunch([base, free, higher]) is free
    assert free_lunch([base, higher]) is None
    assert free_lunch([]) is None
    # A threshold that cuts nothing is not a free lunch either.
    same = Point(0.5, 0.30, 0.05, 0.90, 40, 60)
    assert free_lunch([base, same]) is None


def test_the_curve_is_monotone_in_the_direction_it_claims():
    """Raising the threshold can only remove answers, so false answers cannot rise and
    false refusals cannot fall. If this ever breaks, the sweep is wrong, not the data."""
    dev = {f"d{i}": row(0.50 + i * 0.02, ANSWER, 1.0) for i in range(20)}
    unans = {f"u{i}": row(0.45 + i * 0.02, ANSWER, None) for i in range(20)}
    points = sweep(dev, unans, [round(0.40 + i * 0.05, 3) for i in range(10)])
    fa = [p.false_answer_rate for p in points]
    fr = [p.false_refusal_rate for p in points]
    assert fa == sorted(fa, reverse=True), "false answers must be non-increasing"
    assert fr == sorted(fr), "false refusals must be non-decreasing"


def test_format_curve_states_the_detector_and_the_sample_sizes():
    """A curve without its n is a picture, not a measurement."""
    text = format_curve(sweep({"a": row(0.9, ANSWER, 1.0)},
                              {"u": row(0.5, ANSWER, None)}, [0.0, 0.7]))
    assert "refusal-lexical-v3" in text
    assert "n = 1 unanswerable, 1 answerable" in text


def test_curve_on_the_recorded_runs_reproduces_the_reported_operating_point():
    """The EXP-0038 numbers, asserted against the store. Skips where the runs are absent."""
    from rag.runner.store import DEFAULT_DB, ResultsStore

    if not DEFAULT_DB.exists():
        pytest.skip("no results store on this machine")
    with ResultsStore() as store:
        dev = store.get_questions("run_20260913_205058_dc03")
        unans = store.get_questions("run_20260913_060733_6a9b")
    if not dev or not unans:
        pytest.skip("the Phase 1 Tier 2 control runs are not in this store")

    points = sweep(dev, unans, [0.0, 0.575, 0.625, 0.750])
    base, knee, mid, zero = points
    assert base.false_answer_rate == pytest.approx(0.2667, abs=1e-3), (
        "the Phase 1 baseline false-answer rate is 0.2667 under refusal-lexical-v2 "
        "(MIS-037 corrects the 0.4222 in EXP-0007's row)"
    )
    assert knee.false_answer_rate == pytest.approx(0.1333, abs=1e-3)
    assert knee.false_refusal_rate == pytest.approx(base.false_refusal_rate, abs=1e-6)
    assert zero.false_answer_rate == 0.0 and zero.false_refusal_rate > 0.5
    assert free_lunch(points) is knee


# --- the groundedness self-check ------------------------------------------------

from rag.generation.base import Completion  # noqa: E402
from rag.generation.cache import GenerationCache  # noqa: E402
from rag.generation.grounding import REFUSAL_TEXT, GroundednessCheck, parse_verdict  # noqa: E402
from rag.generation.pipeline_llm import PipelineLLM  # noqa: E402


def checker(tmp_path, text, name="c"):
    calls = []

    def backend(prompt_text: str) -> Completion:
        calls.append(prompt_text)
        return Completion(text=text, tokens_in=8, tokens_out=1, reasoning_tokens=0,
                          finish_reason="stop")

    cache = GenerationCache(tmp_path / f"{name}.sqlite")
    return GroundednessCheck(PipelineLLM("m/x", cache=cache, backend=backend)), calls, cache


def test_unsupported_is_checked_before_supported():
    """UNSUPPORTED contains SUPPORTED as a substring. Testing for SUPPORTED first would
    read every rejection as an approval and make the technique silently do nothing."""
    assert parse_verdict("UNSUPPORTED") is False
    assert parse_verdict("SUPPORTED") is True
    assert parse_verdict("  unsupported  ") is False
    assert parse_verdict("Verdict: SUPPORTED") is True
    assert parse_verdict("maybe") is None
    assert parse_verdict("") is None and parse_verdict(None) is None


def test_a_rejected_answer_becomes_the_standard_refusal(tmp_path):
    """The replacement must be byte-identical to the refusal the prompts ask for, or the
    detector will not count this technique's refusals as refusals at all."""
    from rag.eval.generation_metrics import is_refusal

    check, calls, cache = checker(tmp_path, "UNSUPPORTED")
    with cache:
        kept, record = check.check(question_id="q1", question="Q", context="CTX",
                                   answer=ANSWER)
    assert kept == REFUSAL_TEXT and is_refusal(kept)
    assert record == {"grounding_checked": 1.0, "grounding_rejected": 1.0}
    assert len(calls) == 1
    assert check.provenance()["rejection_rate"] == 1.0


def test_a_refusal_is_never_sent_to_the_checker(tmp_path):
    """A checker asked to approve 'the articles do not cover this' would manufacture
    false refusals out of correct behaviour — and it costs a call to find out."""
    check, calls, cache = checker(tmp_path, "UNSUPPORTED")
    with cache:
        kept, record = check.check(question_id="q1", question="Q", context="CTX",
                                   answer=REFUSAL)
    assert kept == REFUSAL, "a refusal must pass through untouched"
    assert calls == [], "and must not cost a call"
    assert check.stats["refusals_skipped"] == 1
    assert record["grounding_checked"] == 0.0


def test_a_failed_or_unparseable_check_keeps_the_answer(tmp_path):
    """The check can only REMOVE an answer, so the safe direction on failure is to leave
    it alone and count it. Refusing on a broken check would let a provider outage look
    like a grounding finding."""
    def exploding(prompt_text: str) -> Completion:
        raise RuntimeError("provider said no")

    with GenerationCache(tmp_path / "a.sqlite") as cache:
        check = GroundednessCheck(PipelineLLM("m/x", cache=cache, backend=exploding))
        kept, record = check.check(question_id="q1", question="Q", context="C", answer=ANSWER)
    assert kept == ANSWER and record["grounding_call_failed"] == 1.0
    assert check.stats["call_failed"] == 1 and check.stats["rejected"] == 0
    assert "provider said no" in check.provenance()["failures"][0]["error"]

    check2, _, cache2 = checker(tmp_path, "I am not sure", name="b")
    with cache2:
        kept2, record2 = check2.check(question_id="q1", question="Q", context="C", answer=ANSWER)
    assert kept2 == ANSWER and record2["grounding_unparseable"] == 1.0
    assert check2.stats["rejected"] == 0


def test_rejection_rate_excludes_refusals_it_never_judged(tmp_path):
    """Refusals were never at risk of rejection, so counting them in the denominator
    would understate how often the check fires."""
    check, _, cache = checker(tmp_path, "UNSUPPORTED")
    with cache:
        for i in range(3):
            check.check(question_id=f"r{i}", question="Q", context="C", answer=REFUSAL)
        check.check(question_id="a1", question="Q", context="C", answer=ANSWER)
    prov = check.provenance()
    assert prov["answers_seen"] == 4 and prov["refusals_skipped"] == 3
    assert prov["checked"] == 1 and prov["rejected"] == 1
    assert prov["rejection_rate"] == 1.0, "1 of 1 judged, not 1 of 4 seen"
    assert prov["mean_check_ms"] is not None


def test_config_refuses_the_check_at_tier_1_and_rejects_unknown_names():
    from rag.runner.config import EvalTier, RunConfig

    with pytest.raises(ValueError, match="nothing for it to do at Tier 1"):
        RunConfig(name="t", grounding_check="self_check")
    with pytest.raises(ValueError, match="unknown grounding_check"):
        RunConfig(name="t", grounding_check="vibes", eval_tier=EvalTier.TIER_2,
                  generator_model="openai/gpt-5-nano", skip_judge=True)


def test_grounding_check_moved_no_historical_hash():
    from rag.runner.promoted import load_promoted

    assert load_promoted().config_hash == "7c99bc8e9a88e878"


def test_span_support_is_a_dimension_of_generation_not_retrieval():
    from rag.runner.config import RunConfig
    from rag.runner.promoted import DIMENSIONS

    assert "grounding_check" in DIMENSIONS["generation"]
    assert "grounding_check" not in RunConfig.TIER1_FIELDS


# --- MIS-038: the detector was prompt-dependent ---------------------------------

def test_a_refusal_written_as_a_numbered_step_is_a_refusal():
    """MIS-038. v2 required NO numbered steps, a rule calibrated on a prompt whose
    refusals are bare sentences. Axis 7's prompts demand numbered steps, so the model
    writes '1. The provided articles do not cover this.' and v2 scored it as an ANSWER
    — which would have read as 'citation enforcement makes the system answer more'."""
    from rag.eval.generation_metrics import REFUSAL_DETECTOR_VERSION, is_refusal

    assert REFUSAL_DETECTOR_VERSION == "refusal-lexical-v3"
    assert is_refusal("1. The provided articles do not cover this.")
    assert is_refusal("1) The provided articles do not cover this. [doc:abc12345|quote]")
    assert is_refusal("- The provided articles do not cover this.")
    assert is_refusal("The provided articles do not cover this.")


def test_a_hedged_procedure_is_still_not_a_refusal():
    """The distinction v2 existed to draw, kept. A caveat after a real procedure is a
    hedged answer; scoring it as a refusal would make every careful answer a refusal."""
    from rag.eval.generation_metrics import is_refusal

    hedged = (
        "1. Open Settings. [doc:abc12345]\n"
        "2. Click Domains. [doc:abc12345]\n"
        "3. Click Save. [doc:abc12345]\n"
        "Note: the provided articles do not give a timeline for propagation."
    )
    assert not is_refusal(hedged)


def test_v3_agrees_with_the_hand_labels_it_inherited():
    """DEC-045's 45 hand-labelled answers. A detector change that moved these would be
    changing the definition, not fixing a bug."""
    import yaml

    from rag.eval.generation_metrics import is_refusal
    from rag.paths import REPO_ROOT

    path = REPO_ROOT / "data" / "authored" / "refusal_labels_v1.yaml"
    if not path.exists():
        pytest.skip("hand-labelled refusal set not present")
    rows = yaml.safe_load(path.read_text())["rows"]
    wrong = [r for r in rows if is_refusal(r["answer"]) != bool(r["refused"])]
    assert wrong == [], f"v3 disagrees with {len(wrong)} hand labels: {wrong[:2]}"
