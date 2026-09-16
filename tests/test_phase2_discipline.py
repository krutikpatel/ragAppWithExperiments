"""P2-04 split policy, P2-05 promoted pointer, P2-06 cost gate — and the DECISIONS.md
log appender they share."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag.runner import cost
from rag.runner.config import AXES, EvalTier, RunConfig, load_config_file
from rag.runner.cost import CostGateError, estimate_index_cost, estimate_run_cost
from rag.runner.decision_log import append_row, section_rows
from rag.runner.promoted import (
    PROMOTED_PATH,
    check_split_policy,
    config_diff,
    decision_splits,
    load_promoted,
    resolve_run_ref,
)
from rag.runner.store import ResultsStore
from tests.test_cost import TABLE


# --- config: axis ---------------------------------------------------------------

def test_axis_is_validated_and_not_part_of_the_hash():
    base = RunConfig(name="x")
    assert base.with_(axis="chunking").config_hash == base.config_hash
    with pytest.raises(ValueError, match="unknown axis"):
        RunConfig(name="x", axis="vibes")
    assert "retrieval_method" in AXES


# --- P2-04: split policy ---------------------------------------------------------

def test_axis_3_is_refused_on_dev_large_without_the_flag():
    config = RunConfig(name="x", axis="retrieval_method", split="dev_large")
    with pytest.raises(PermissionError, match="dev. ONLY"):
        check_split_policy(config, allow_leaky_split=False)
    allowed = check_split_policy(config, allow_leaky_split=True)
    assert allowed["leakage_affected"] is True and "LEAKAGE-AFFECTED" in allowed["note"]


def test_judged_decisions_are_refused_on_dev_large():
    config = RunConfig(
        name="x", axis="generation", split="dev_large", eval_tier=EvalTier.TIER_2,
        generator_model="openai/gpt-5-nano", judge_model="openai/gpt-oss-120b",
    )
    with pytest.raises(PermissionError, match="dev. subsample only"):
        check_split_policy(config, allow_leaky_split=False)


def test_retrieval_axes_may_use_dev_large_and_dev_needs_nothing():
    assert check_split_policy(RunConfig(name="x", axis="chunking", split="dev_large"), allow_leaky_split=False) == {
        "leakage_affected": False, "note": None,
    }
    assert check_split_policy(RunConfig(name="x", axis="retrieval_method", split="dev"), allow_leaky_split=False)["leakage_affected"] is False


def test_decision_splits_follow_p2_04():
    for axis in ("chunking", "embedding", "reranking", "assembly"):
        assert decision_splits(axis) == {"decide": "dev_large", "confirm": "dev"}
    for axis in ("retrieval_method", "query_transform", "generation", "agentic"):
        assert decision_splits(axis) == {"decide": "dev", "confirm": "dev"}


# --- P2-05: promoted.yaml ---------------------------------------------------------

def test_promoted_starts_as_the_dense_control():
    assert PROMOTED_PATH.exists()
    assert load_promoted().config_hash == load_config_file("configs/baseline_dense.yaml").config_hash


def test_config_diff_names_the_dimension_changed():
    promoted = load_promoted()
    one = config_diff(promoted.with_(retriever="bm25", retriever_params={}, split="dev_large", name="n"), promoted)
    assert one["dimensions"] == ["retrieval"] and one["one_dimension"]
    assert set(one["changed"]) == {"retriever", "retriever_params"}, "split and name are run settings, not dimensions"
    two = config_diff(promoted.with_(top_k=10, chunker_params={"chunk_size": 300, "overlap": 0}), promoted)
    assert two["dimensions"] == ["assembly", "chunking"] and not two["one_dimension"]


def _row_of(run_id: str, config, **overrides) -> dict:
    from tests.test_runner import _row

    return _row(
        run_id, config_hash=config.config_hash, config_json=json.dumps(config.as_dict()),
        split=config.split, eval_tier=config.eval_tier.value, retriever=config.retriever, **overrides,
    )


def test_promoted_ref_resolves_to_the_newest_run_on_the_same_split(tmp_path):
    promoted = load_promoted()
    other = promoted.with_(retriever="bm25", retriever_params={})
    with ResultsStore(tmp_path / "runs.sqlite") as store:
        store.start_run(_row_of("run_1", promoted))
        store.start_run(_row_of("run_2", promoted))
        store.start_run(_row_of("run_3", promoted.with_(split="dev_large")))
        store.start_run(_row_of("run_x", other))
        store.start_run(_row_of("run_y", other.with_(split="dev_large")))
        for run_id in ("run_1", "run_2", "run_3", "run_x", "run_y"):
            store.finish_run(run_id, status="VALID", n_questions=1)
        assert resolve_run_ref("promoted", store=store, like_run="run_x") == "run_2"
        assert resolve_run_ref("promoted", store=store, like_run="run_y") == "run_3"
        assert resolve_run_ref("run_x", store=store) == "run_x"
        store.start_run(_row_of("run_u", other.with_(split="unanswerable")))
        with pytest.raises(KeyError, match="no VALID run of the promoted config"):
            resolve_run_ref("promoted", store=store, like_run="run_u")


def test_tier1_identity_ignores_tier2_only_defaults():
    """DEC-042 changed `generator_prompt`'s default after EXP-0005 ran; the dense
    control's Tier 1 runs must still be found as runs of promoted.yaml."""
    promoted = load_promoted()
    old_default = promoted.with_(generator_prompt="answer@v1")
    assert old_default.config_hash != promoted.config_hash
    assert old_default.identity_hash == promoted.identity_hash
    assert promoted.with_(top_k=6).identity_hash != promoted.identity_hash
    tier2 = promoted.with_(eval_tier=EvalTier.TIER_2, generator_model="a/b", judge_model="c/d")
    assert tier2.with_(generator_prompt="answer@v1").identity_hash != tier2.identity_hash


@pytest.mark.skipif(not Path("results/runs.sqlite").exists(), reason="no results store on this machine")
def test_promoted_resolves_to_exp_0005_in_the_real_store():
    with ResultsStore() as store:
        if store.get_run("run_20260912_222538_b1dc") is None:
            pytest.skip("EXP-0005 not in this store")
        row = store.latest_run_of(load_promoted(), split="dev")
    assert row is not None and row["name"].startswith("EXP-0005")


def _promotion_fixture(tmp_path, *, large_delta: float, dev_delta: float):
    """A store with a promoted-config baseline and a candidate on dev_large and dev,
    where the candidate wins `large_delta` of 100 questions on dev_large and
    `dev_delta` of 40 on dev (negative: loses)."""
    from tests.test_compare import _question, _row as _crow

    promoted = load_promoted()
    candidate = tmp_path / "cand.yaml"
    candidate.write_text(PROMOTED_PATH.read_text().replace("top_k: 5", "top_k: 7").replace("name: promoted", "name: cand"))
    cand_hash = load_config_file(candidate).config_hash
    store = ResultsStore(tmp_path / "runs.sqlite")
    for split, n, delta in (("dev_large", 100, large_delta), ("dev", 40, dev_delta)):
        a, b = f"a_{split}", f"b_{split}"
        cand = load_config_file(candidate)
        store.start_run(_crow(a, config_hash=promoted.config_hash, split=split, retriever="dense",
                              config_json=json.dumps(promoted.with_(split=split).as_dict()), eval_tier="tier1"))
        store.start_run(_crow(b, config_hash=cand_hash, split=split, retriever="dense",
                              config_json=json.dumps(cand.with_(split=split).as_dict()), eval_tier="tier1"))
        flips = int(abs(delta) * n)
        rows_a, rows_b = [], []
        for i in range(n):
            base_hit = float(i % 2 == 0)
            cand_hit = base_hit
            if i < flips:
                cand_hit = 1.0 if delta > 0 else 0.0
                base_hit = 0.0 if delta > 0 else 1.0
            rows_a.append(_question(a, f"q{i}", {"strict_recall@5": base_hit}))
            rows_b.append(_question(b, f"q{i}", {"strict_recall@5": cand_hit}))
        store.add_questions(rows_a)
        store.add_questions(rows_b)
        store.finish_run(a, status="VALID", metrics={"strict_recall@5": 0.5}, n_questions=n)
        store.finish_run(b, status="VALID", metrics={"strict_recall@5": 0.5 + delta}, n_questions=n)
    return store, candidate


def test_promotion_requires_dev_large_significance_and_dev_agreement(tmp_path, monkeypatch):
    from rag.runner import promoted as promoted_mod
    from rag.runner.compare import compare_runs

    slices = {"all": [f"q{i}" for i in range(100)]}
    monkeypatch.setattr("rag.runner.compare._slices_from_split", lambda split, ids: slices)

    store, candidate = _promotion_fixture(tmp_path, large_delta=0.2, dev_delta=-0.1)
    monkeypatch.setattr(promoted_mod, "PROMOTED_PATH", tmp_path / "promoted.yaml")
    result = promoted_mod.promote(
        candidate, axis="assembly", decide=("a_dev_large", "b_dev_large"), confirm=("a_dev", "b_dev"),
        metric="strict_recall@5", reason="test", store=store, git_sha="abc1234", dry_run=True,
    )
    assert result["verdicts"]["decide"]["p_value"] < 0.05
    assert any("DISAGREE" in p for p in result["problems"]), "dev_large and dev disagree: not promoted, a finding"
    assert result["promoted"] is False

    with pytest.raises(ValueError, match="pass --decide"):
        promoted_mod.promote(candidate, axis="assembly", decide=None, confirm=("a_dev", "b_dev"),
                             metric="strict_recall@5", reason="t", store=store, git_sha="abc", dry_run=True)
    store.close()


def test_promotion_advances_the_pointer_and_logs_it(tmp_path, monkeypatch):
    from rag.runner import decision_log, promoted as promoted_mod

    slices = {"all": [f"q{i}" for i in range(100)]}
    monkeypatch.setattr("rag.runner.compare._slices_from_split", lambda split, ids: slices)
    store, candidate = _promotion_fixture(tmp_path, large_delta=0.2, dev_delta=0.1)

    pointer = tmp_path / "promoted.yaml"
    pointer.write_text(PROMOTED_PATH.read_text())
    log = tmp_path / "DECISIONS.md"
    log.write_text(
        "## Promotion log\n\n| # | Date |\n|---|---|\n" + promoted_mod.PROMOTION_EMPTY_ROW + "\n\n## Next section\n\n| a | b |\n"
    )
    monkeypatch.setattr(promoted_mod, "PROMOTED_PATH", pointer)
    monkeypatch.setattr(decision_log, "DECISIONS_PATH", log)

    result = promoted_mod.promote(
        candidate, axis="assembly", decide=("a_dev_large", "b_dev_large"), confirm=("a_dev", "b_dev"),
        metric="strict_recall@5", reason="test win", store=store, git_sha="abc1234",
    )
    assert result["problems"] == [] and result["promoted"] is True and result["log_row"] == 1
    assert load_config_file(pointer).config_hash == load_config_file(candidate).config_hash
    assert "PROMOTED on" in pointer.read_text()
    rows = section_rows(log.read_text(), "## Promotion log")
    assert len(rows) == 1 and "assembly" in rows[0] and "p=" in rows[0]
    assert "| a | b |" in log.read_text(), "the next section is untouched"
    store.close()


def test_promotion_refuses_a_run_that_is_not_the_candidate(tmp_path, monkeypatch):
    from rag.runner import promoted as promoted_mod

    monkeypatch.setattr("rag.runner.compare._slices_from_split", lambda split, ids: {"all": []})
    store, candidate = _promotion_fixture(tmp_path, large_delta=0.2, dev_delta=0.1)
    result = promoted_mod.promote(
        candidate, axis="retrieval_method", decide=None, confirm=("b_dev", "a_dev"),  # swapped
        metric="strict_recall@5", reason="t", store=store, git_sha="abc", dry_run=True,
    )
    assert any("not a run of the current promoted config" in p for p in result["problems"])
    store.close()


# --- P2-06: cost gate -------------------------------------------------------------

def test_index_build_dominates_when_the_index_is_not_cached():
    params = {"embedding_backend": "openrouter", "embedding_model": "qwen/qwen3-embedding-8b", "embedding_provider": "DeepInfra"}
    cold = estimate_index_cost(retriever="dense", retriever_params=params, corpus_words=2_250_000,
                               index_exists=False, n_questions=200, pricing=TABLE)
    warm = estimate_index_cost(retriever="dense", retriever_params=params, corpus_words=2_250_000,
                               index_exists=True, n_questions=200, pricing=TABLE)
    assert cold["index_usd"] == pytest.approx(2_250_000 * 1.27 / 1e6 * 0.01, abs=1e-4)
    assert warm["index_usd"] == 0.0 and warm["query_usd"] == cold["query_usd"] > 0
    bm25 = estimate_index_cost(retriever="bm25", retriever_params={}, corpus_words=1, index_exists=False,
                               n_questions=1, pricing=TABLE)
    assert bm25["index_usd"] == 0.0


def test_unpriced_embedding_model_is_unavailable_and_gated():
    params = {"embedding_model": "new/model", "embedding_provider": "Somewhere"}
    index = estimate_index_cost(retriever="dense", retriever_params=params, corpus_words=100,
                                index_exists=False, n_questions=1, pricing=TABLE)
    assert "price_unavailable" in index
    run = estimate_run_cost(tier2=None, index=index)
    assert run["over_gate"] is True and run["total_usd"] == 0.0, "unknown is gated, not free"


def test_gate_threshold_and_driver():
    over = estimate_run_cost(tier2={"total_usd": 1.5, "generator_usd": 0.1, "judge_usd": 1.4},
                             index={"index_usd": 0.9, "query_usd": 0.0})
    assert over["total_usd"] == 2.4 and over["over_gate"] and over["driver"] == "judge"
    under = estimate_run_cost(tier2=None, index={"index_usd": 0.0, "query_usd": 0.0001})
    assert under["over_gate"] is False


CORPUS_READY = Path("data/frozen/corpus.parquet").exists() and Path("data/frozen/dev.parquet").exists()


@pytest.mark.skipif(not CORPUS_READY, reason="frozen corpus not built")
def test_runner_halts_above_the_gate_without_starting_a_run(tmp_path, monkeypatch):
    """P2-06: the runner prints the estimate and exits; it does not prompt, does not
    proceed on a default, and records nothing."""
    from rag.runner import run as run_mod
    from rag.runner.run import run

    monkeypatch.setattr(run_mod, "COST_GATE_USD", 0.0)
    monkeypatch.setattr(cost, "COST_GATE_USD", 0.0)
    monkeypatch.setattr(run_mod, "estimate_index_cost", lambda **kw: {"index_usd": 0.5, "query_usd": 0.0, "index_exists": False, "source": "faked"})
    config = load_config_file("configs/smoke_toy.yaml")
    with ResultsStore(tmp_path / "runs.sqlite") as store:
        with pytest.raises(CostGateError, match="has not started"):
            run(config, store=store, pricing=TABLE)
        assert store.list_runs() == []


@pytest.mark.skipif(not CORPUS_READY, reason="frozen corpus not built")
def test_runner_records_estimate_actual_axis_and_promoted_diff(tmp_path, monkeypatch):
    from rag.runner import decision_log, run as run_mod
    from rag.runner.cost_approvals import EMPTY_ROW, LOG_HEADING
    from rag.runner.run import run
    from rag.generation.cache import GenerationCache

    log = tmp_path / "DECISIONS.md"
    log.write_text(f"{LOG_HEADING}\n\n| # |\n|---|\n{EMPTY_ROW}\n\n## After\n")
    monkeypatch.setattr(decision_log, "DECISIONS_PATH", log)
    monkeypatch.setattr(run_mod, "estimate_index_cost", lambda **kw: {"index_usd": 3.0, "query_usd": 0.0, "index_exists": False, "source": "faked"})

    config = load_config_file("configs/smoke_toy.yaml").with_(axis="assembly", top_k=7)
    with ResultsStore(tmp_path / "runs.sqlite") as store, GenerationCache(tmp_path / "g.sqlite") as cache:
        with pytest.raises(CostGateError):
            run(config, store=store, pricing=TABLE, generation_cache=cache)
        with pytest.warns(UserWarning, match="one dimension") as caught:
            row = run(config, store=store, pricing=TABLE, generation_cache=cache, approve_cost="DEC-TEST")
    assert row["axis"] == "assembly" and row["cost_approval"] == "DEC-TEST"
    assert row["cost_estimate_usd"] == 3.0 and row["pricing_version"] == TABLE.pricing_version
    assert row["cost_actual_usd"] == 0.0, "a toy run spends nothing, and that is measured"
    diff = json.loads(row["vs_promoted_json"])
    assert diff["one_dimension"] is False and "retrieval" in diff["dimensions"] and "assembly" in diff["dimensions"]
    assert row["promoted_config_hash"] == load_promoted().config_hash
    assert row["leakage_affected"] == 0
    assert len(section_rows(log.read_text(), LOG_HEADING)) == 1
    assert "DEC-TEST" in log.read_text()


# --- the shared DECISIONS.md log appender (MIS-018) -------------------------------

def test_log_sections_end_at_the_next_heading(tmp_path, monkeypatch):
    from rag.runner import decision_log

    path = tmp_path / "D.md"
    path.write_text(
        "## Test-split openings log\n\nintro\n\n| # | Date |\n|---|---|\n| _(none)_ | — |\n\n"
        "## DEC-046\n\n| metric | run 1 |\n|---|---|\n| faithfulness | 0.883 |\n| relevance | 0.79 |\n"
    )
    assert section_rows(path.read_text(), "## Test-split openings log") == []
    n = append_row("## Test-split openings log", "| 1 | 2026-09-15 |", placeholder="| _(none)_ | — |", path=path)
    assert n == 1
    text = path.read_text()
    assert "| _(none)_" not in text and "| faithfulness | 0.883 |" in text
    assert text.index("| 1 | 2026-09-15 |") < text.index("## DEC-046")
    n = append_row("## Test-split openings log", "| 2 | 2026-09-16 |", placeholder="| _(none)_ | — |", path=path)
    assert n == 2
