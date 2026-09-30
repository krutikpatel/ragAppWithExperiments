"""Bounded retries for the small OpenRouter GETs (P3-14, DEC-098).

The request-path calls — chat, embeddings, rerank, the judge — each carry their own
timeout and retry policy, tuned to their failure history (MIS-010, MIS-014, MIS-024).
This is the same policy for the read-only listing calls the cost estimator and the
pricing refresh make: a timeout on every attempt, transient failures (network errors,
408/425/429/5xx) retried with exponential backoff, anything else raised at once.
`tests/test_resilience_p3_14.py` fails if an OpenRouter call site appears anywhere
without one of these policies.
"""

from __future__ import annotations

import time
from typing import Any

RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def get_json(url: str, *, timeout: float = 20.0, attempts: int = 4, backoff_s: float = 2.0) -> Any:
    """GET `url` and return its JSON; up to `attempts` tries, `backoff_s` doubling between."""
    import httpx

    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except httpx.TransportError as exc:
            last = exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in RETRY_STATUS:
                raise
            last = exc
        if attempt < attempts:
            time.sleep(backoff_s * (2 ** (attempt - 1)))
    raise RuntimeError(f"GET {url}: {attempts} attempts failed; last error {type(last).__name__}: {last}") from last
