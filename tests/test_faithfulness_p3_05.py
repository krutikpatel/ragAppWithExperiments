"""P3-05 — offline faithfulness evaluation. No model calls: Ragas runs on a fake LLM,
and the pipeline's judge is an injected function."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from rag.eval.faithfulness import (
    AnswerInput,
    JudgeCache,
    aggregate,
    attribute,
    citation_integrity,
    evaluate,
    rebuild_contexts,
    report_markdown,
)
from rag.eval.judge import ClaimJudgment, ClaimVerdict, FaithfulnessClaims

REFUSAL = "I'm sorry, the provided articles do not cover this."


from ragas.llms.base import InstructorBaseRagasLLM  # noqa: E402 — tests may import Ragas; rag/ may not


class FakeLLM(InstructorBaseRagasLLM):
    """A real subclass of Ragas's instructor LLM base, so the metric accepts it; returns
    canned structured output by type instead of calling a model."""

    def __init__(self, statements, verdicts):
        self.statements, self.verdicts = statements, verdicts

    def generate(self, prompt, model_cls):
        raise NotImplementedError

    async def agenerate(self, prompt, model_cls):
        if model_cls.__name__ == "StatementGeneratorOutput":
            return model_cls(statements=self.statements)
        return model_cls(statements=[{"statement": s, "reason": "r", "verdict": v}
                                     for s, v in zip(self.statements, self.verdicts)])


@pytest.mark.parametrize("verdicts", [[1, 1, 1], [1, 0, 1], [0, 0, 0]])
def test_claim_level_score_is_identical_to_ragas_ascore(verdicts):
    """The claims path calls Ragas's own steps in `ascore`'s order, so the number must match."""
    from ragas.metrics.collections import Faithfulness

    llm = FakeLLM(["a", "b", "c"], verdicts)
    metric = Faithfulness(llm=llm)
    item = {"question": "q", "answer": "an answer", "contexts": ["ctx one", "ctx two"]}
    expected = asyncio.run(metric.ascore(user_input="q", response="an answer", retrieved_contexts=item["contexts"])).value
    got = asyncio.run(FaithfulnessClaims._one(metric, item))
    assert got.score == pytest.approx(expected)
    assert [c.supported for c in got.claims] == [bool(v) for v in verdicts]


def _item(qid, answer, *, gold=("g1",), cited=(), gic=1.0, contexts=("--- ARTICLE [doc:g1] ---\nclick settings then save",)):
    return AnswerInput(question_id=qid, question=f"Q {qid}", answer=answer, gold_doc_ids=list(gold),
                       cited_doc_ids=list(cited), context_chunk_ids=[f"c{i}" for i in range(len(contexts))],
                       context_doc_ids=["g1"], contexts=list(contexts), gold_in_context=gic)


def _judge(scores):
    calls = []

    def score_fn(items):
        calls.append(len(items))
        out = []
        for it in items:
            s = scores[it["question"]]
            if s is None:
                out.append(ClaimJudgment(score=None, error="boom"))
            else:
                claims = (ClaimVerdict("click settings", True, "ok"),) + (
                    (ClaimVerdict("the moon is cheese", False, "not in context"),) if s < 1 else ())
                out.append(ClaimJudgment(score=s, claims=claims))
        return out

    score_fn.calls = calls
    return score_fn


def test_refusals_are_not_judged_failures_are_none_and_every_rate_is_right(tmp_path):
    inputs = [
        _item("a", "1. Click settings. 2. Save. [doc:g1]", cited=["g1"]),
        _item("b", "Click settings; the moon is cheese. [doc:zz]", cited=["zz"], gic=0.0),
        _item("c", REFUSAL),
        _item("d", "Something. [doc:g1]", cited=["g1"], gold=("g1", "g2")),
        _item("u1", "Here is how to do it in Squarespace.", gold=(), gic=None),
        _item("u2", REFUSAL, gold=(), gic=None),
    ]
    fn = _judge({"Q a": 1.0, "Q b": 0.5, "Q d": None, "Q u1": 1.0})
    rows = evaluate(inputs, None, JudgeCache(tmp_path / "c.sqlite"), identity="j", prompt_version="v", score_fn=fn)
    by = {r["question_id"]: r for r in rows}
    assert by["c"]["faithfulness"] is None and by["c"]["refused"] and by["c"]["n_claims"] == 0
    assert by["d"]["faithfulness"] is None and by["d"]["unsupported"] is None, "a failure is not a verdict"
    assert by["b"]["unsupported"] is True and by["b"]["invented_citations"] == ["zz"]
    m = aggregate(rows)
    assert m["all"]["n_judged"] == 3 and m["all"]["judge_failures"] == 1
    assert m["all"]["mean_faithfulness"] == round((1.0 + 0.5 + 1.0) / 3, 4)
    assert m["all"]["unsupported_answer_rate"] == round(1 / 3, 4)
    assert m["answerable"]["refusal_rate"] == 0.25
    assert m["unanswerable"]["false_answer_rate"] == 0.5
    assert m["all"]["citation_integrity"] == 0.75 and m["all"]["invented_citations"] == 1
    assert m["gold_not_in_context"]["n"] == 1 and m["gold_docs:multi"]["n"] == 1


def test_an_unchanged_answer_is_never_re_judged_and_a_failure_is_not_cached(tmp_path):
    cache = JudgeCache(tmp_path / "c.sqlite")
    inputs = [_item("a", "Click settings. [doc:g1]"), _item("d", "Other. [doc:g1]")]
    fn = _judge({"Q a": 1.0, "Q d": None})
    evaluate(inputs, None, cache, identity="j", prompt_version="v", score_fn=fn)
    fn2 = _judge({"Q a": 0.0, "Q d": 1.0})
    rows = evaluate(inputs, None, cache, identity="j", prompt_version="v", score_fn=fn2)
    assert fn2.calls == [1], "only the failed one is re-judged"
    assert {r["question_id"]: r["faithfulness"] for r in rows} == {"a": 1.0, "d": 1.0}
    assert cache.hits == 1
    # A different judge identity or an edited answer misses.
    fn3 = _judge({"Q a": 0.5, "Q d": 0.5})
    evaluate(inputs, None, cache, identity="another judge", prompt_version="v", score_fn=fn3)
    assert fn3.calls == [2]


def test_attribution_points_at_the_chunk_sharing_the_claim_words():
    chunk, share = attribute("Click Settings then Save the page",
                             ["c0", "c1"], ["pricing plans and billing", "open settings and click save"])
    assert chunk == "c1" and share > 0.5
    assert attribute("", ["c0"], ["x"]) == (None, 0.0)


def test_citation_integrity_is_about_documents_in_the_assembled_context():
    assert citation_integrity(["a"], ["a", "b"]) == (True, [])
    assert citation_integrity([], ["a"]) == (True, [])
    assert citation_integrity(["a", "z"], ["a"]) == (False, ["z"])


def test_rebuilt_context_is_the_assemblers_and_respects_the_budget():
    text = {"c1": "one two three", "c2": "four five", "c3": "six seven eight nine"}
    docs = {"c1": "d1", "c2": "d2", "c3": "d3"}
    parts, kept, doc_ids = rebuild_contexts(["c1", "c2", "c3"], docs, text, max_tokens=6, order="rank")
    assert kept == ["c1", "c2"] and doc_ids == ["d1", "d2"], "c3 does not fit the 6-word budget"
    assert parts[0] == "--- ARTICLE [doc:d1] ---\none two three"


def test_the_report_lists_lowest_first_with_verdicts():
    rows = evaluate([_item("a", "x"), _item("b", "y")], None, None, identity="j", prompt_version="v",
                    score_fn=_judge({"Q a": 1.0, "Q b": 0.5}))
    md = report_markdown("src", "run_x", rows, aggregate(rows), n=1)
    assert "`b` — faithfulness 0.500" in md and "`a` —" not in md
    assert "**UNSUPPORTED**" in md and "heuristic" in md


@pytest.mark.skipif(not Path("data/frozen/corpus.parquet").exists(), reason="frozen corpus not built")
def test_the_phase_2_dev_run_rebuilds_for_every_answer():
    """The assertion inside rebuild_contexts runs for all 100 stored answers."""
    from rag.eval.faithfulness import load_run
    from rag.runner.store import ResultsStore

    with ResultsStore() as store:
        if store.get_run("run_20260913_205058_dc03") is None:
            pytest.skip("results store without the Phase 2 dev run")
        _, inputs = load_run("run_20260913_205058_dc03", store)
    assert len(inputs) == 100 and all(len(i.contexts) == 5 for i in inputs)
    assert sum(1 for i in inputs if i.refused) == 8
