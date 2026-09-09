"""Text normalization — P0-02.

One rule, one version string. The indexed text is derived from the stored text;
the stored text is never modified, because citation display needs the original.

`norm-v1`
    Markdown links `[anchor](target)` collapse to `anchor` in indexed text.
    Everything else is passed through byte-for-byte.

Bumping this version is the only sanctioned way to change indexing behaviour, and
the runner records it on every run. See docs/DECISIONS.md DEC-002.
"""

from __future__ import annotations

import re

NORMALIZATION_VERSION = "norm-v1"

# [anchor](target) — target may not contain a closing paren, which is true of every
# link in this corpus. Nested-paren targets are left alone rather than mangled.
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^()\s]*)\)")


def normalize_for_index(text: str, *, version: str = NORMALIZATION_VERSION) -> str:
    """Return the text as it should be embedded / indexed.

    Bare URLs are deliberately kept: they are exact terms a user may search for,
    and dropping them would remove signal the baseline can legitimately use.
    """
    if version != NORMALIZATION_VERSION:
        raise ValueError(
            f"unknown normalization_version {version!r}; "
            f"this build implements {NORMALIZATION_VERSION!r}"
        )
    return _MD_LINK.sub(r"\1", text)
