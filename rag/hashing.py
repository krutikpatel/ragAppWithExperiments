"""Stable content hashing.

Parquet bytes are not reproducible across writer versions, so every hash in this
project is computed over a canonical serialization of the *rows*, never over the
file on disk. Two runs that materialize the same records produce the same hash
regardless of how the file was written.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def hash_records(
    records: Iterable[Mapping[str, Any]],
    *,
    sort_key: str,
    fields: list[str],
) -> str:
    """Hash records sorted by `sort_key`, keeping only `fields`, in that field order.

    Restricting to an explicit field list means adding a derived column later does
    not silently change the hash of an unchanged corpus. Adding a *source* field
    should change it, and does, because the field list is part of the recipe.
    """
    digest = hashlib.sha256()
    rows = sorted(records, key=lambda r: r[sort_key])
    for row in rows:
        payload = [row[field] for field in fields]
        digest.update(canonical_json(payload).encode("utf-8"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_id(*parts: str, length: int = 16) -> str:
    """Deterministic short identifier over the given parts."""
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]
