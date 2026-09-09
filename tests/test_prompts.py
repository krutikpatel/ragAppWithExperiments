"""P0-07 / P0-11 — prompts are versioned data, addressed by (id, version).

Only the generator prompt is ours now. Ragas owns the judge prompts and manages them
internally, so those are tracked by `metric_prompt_versions` fingerprints instead —
see `tests/test_eval_boundary.py`.
"""

from __future__ import annotations

import pytest

from rag.prompts import list_prompts, load_prompt

# Editing a prompt without bumping its version would silently change every future
# run while the results store still recorded the old ref. This pin makes that edit
# fail here instead of showing up as a mysterious metric shift weeks later.
PINNED_HASHES = {
    "answer@v1": "sha256:cb49635996bd8e0",
}


def test_every_prompt_content_hash_is_pinned():
    actual = {prompt.ref: prompt.content_hash[:22] for prompt in list_prompts()}
    assert actual == PINNED_HASHES, (
        "a prompt changed. Bump its version in prompts/*.yaml and update this pin — "
        "editing a prompt in place makes old and new runs incomparable."
    )


def test_prompt_ref_is_what_the_store_records():
    assert load_prompt("answer", "v1").ref == "answer@v1"


def test_unknown_version_is_rejected():
    with pytest.raises(KeyError, match="no version"):
        load_prompt("answer", "v99")


def test_missing_field_names_itself():
    with pytest.raises(KeyError, match="question"):
        load_prompt("answer", "v1").render(context="x")


def test_answer_prompt_asks_for_citations_and_refusal():
    """Citation precision and refusal metrics are only computable if it asks for them."""
    rendered = load_prompt("answer", "v1").render(context="CTX", question="Q")
    assert "CTX" in rendered and "Q" in rendered
    assert "[doc:<id>]" in rendered
    assert "do not guess" in rendered
