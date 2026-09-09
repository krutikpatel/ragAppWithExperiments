"""P0-07 / P0-11 — prompts are versioned data, addressed by (id, version)."""

from __future__ import annotations

import pytest

from rag.prompts import list_prompts, load_prompt

# Editing a prompt without bumping its version would silently change every future
# score while the results store still recorded the old ref. These hashes make that
# edit fail here instead of showing up as a mysterious metric shift weeks later.
PINNED_HASHES = {
    "answer@v1": "sha256:cb49635996bd8e0",
    "judge_answer_correctness@v1": "sha256:bc056a027ce3706",
    "judge_answer_relevance@v1": "sha256:0440f2fc2ebf474",
    "judge_faithfulness@v1": "sha256:47546bf4d8e3276",
}


def test_every_prompt_content_hash_is_pinned():
    actual = {prompt.ref: prompt.content_hash[:22] for prompt in list_prompts()}
    assert actual == PINNED_HASHES, (
        "a prompt changed. Bump its version in prompts/*.yaml and update this pin — "
        "editing a prompt in place makes old and new scores incomparable."
    )


def test_prompt_ref_is_what_the_store_records():
    assert load_prompt("judge_faithfulness", "v1").ref == "judge_faithfulness@v1"


def test_unknown_version_is_rejected():
    with pytest.raises(KeyError, match="no version"):
        load_prompt("judge_faithfulness", "v99")


def test_missing_field_names_itself():
    with pytest.raises(KeyError, match="context"):
        load_prompt("judge_faithfulness", "v1").render(answer="x")


def test_judge_prompts_render_with_their_fields():
    rendered = load_prompt("judge_faithfulness", "v1").render(context="CTX", answer="ANS")
    assert "CTX" in rendered and "ANS" in rendered
    # The JSON example must survive .format() unescaped.
    assert '"score"' in rendered
