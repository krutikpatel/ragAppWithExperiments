"""Versioned prompts, addressed by (id, version) — P0-07 / P0-11.

Prompts are data, not code. They live in `prompts/*.yaml` and are loaded by id and
version so a run can record exactly which text produced its scores. A prompt edited
without a version bump would silently change every future judge score while looking
identical in the results store, so `content_hash` is recorded too and
`tests/test_prompts.py` pins it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import yaml

from rag.hashing import hash_text
from rag.paths import PROMPTS_DIR


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    description: str
    template: str
    content_hash: str

    @property
    def ref(self) -> str:
        """What goes in the results store: `judge_faithfulness@v1`."""
        return f"{self.id}@{self.version}"

    def render(self, **fields: object) -> str:
        try:
            return self.template.format(**fields)
        except KeyError as exc:
            raise KeyError(f"prompt {self.ref} needs field {exc} which was not supplied") from None


@lru_cache(maxsize=None)
def load_prompt(prompt_id: str, version: str) -> Prompt:
    path = PROMPTS_DIR / f"{prompt_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no prompt file for {prompt_id!r} at {path}")
    document = yaml.safe_load(path.read_text())
    versions = document["versions"]
    if version not in versions:
        raise KeyError(
            f"prompt {prompt_id!r} has no version {version!r}; available: {sorted(versions)}"
        )
    entry = versions[version]
    return Prompt(
        id=prompt_id,
        version=version,
        description=entry.get("description", ""),
        template=entry["template"],
        content_hash=hash_text(entry["template"]),
    )


def list_prompts() -> list[Prompt]:
    prompts = []
    for path in sorted(PROMPTS_DIR.glob("*.yaml")):
        document = yaml.safe_load(path.read_text())
        for version in document["versions"]:
            prompts.append(load_prompt(path.stem, version))
    return prompts
