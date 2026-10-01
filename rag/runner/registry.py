"""Component registry — the seam that keeps the runner free of technique code.

The runner names a retriever; it does not import one. Adding a technique in a later
phase means registering it here, not editing `run.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_RETRIEVERS: dict[str, Callable[..., Any]] = {}
_RERANKERS: dict[str, Callable[..., Any]] = {}
_BUILTINS_LOADED = False


def _ensure_builtins() -> None:
    """Import the modules that register built-in retrievers.

    Lazily, and from here rather than as a side effect of importing the runner:
    otherwise the registry is empty for anything that does not happen to import
    `rag.runner.run` first, and `build_retriever` fails with "unknown retriever" for
    a retriever that exists.
    """
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    _BUILTINS_LOADED = True
    import rag.reranking.llm  # noqa: F401
    import rag.reranking.mmr  # noqa: F401
    import rag.reranking.toy  # noqa: F401
    import rag.reranking.openrouter  # noqa: F401
    import rag.reranking.typesafe  # noqa: F401
    import rag.retrieval.bm25  # noqa: F401
    import rag.retrieval.dense  # noqa: F401
    import rag.retrieval.hybrid  # noqa: F401
    import rag.retrieval.toy  # noqa: F401


def register_retriever(name: str) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        if name in _RETRIEVERS:
            raise ValueError(f"retriever {name!r} is already registered")
        _RETRIEVERS[name] = cls
        return cls

    return decorator


def build_retriever(name: str, **kwargs: Any) -> Any:
    _ensure_builtins()
    if name not in _RETRIEVERS:
        raise KeyError(f"unknown retriever {name!r}; registered: {sorted(_RETRIEVERS)}")
    return _RETRIEVERS[name](**kwargs)


def retriever_class(name: str) -> type:
    """The registered class, for questions that must be answered before the
    retriever is built — what it would embed, and so what it would cost (P2-06)."""
    _ensure_builtins()
    if name not in _RETRIEVERS:
        raise KeyError(f"unknown retriever {name!r}; registered: {sorted(_RETRIEVERS)}")
    return _RETRIEVERS[name]


def registered_retrievers() -> list[str]:
    _ensure_builtins()
    return sorted(_RETRIEVERS)


# --- rerankers (P2-10) --------------------------------------------------------
#
# Same seam, same reason: the runner names a reranker, it does not import one.


def register_reranker(name: str) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        if name in _RERANKERS:
            raise ValueError(f"reranker {name!r} is already registered")
        _RERANKERS[name] = cls
        return cls

    return decorator


def build_reranker(name: str, **kwargs: Any) -> Any:
    _ensure_builtins()
    if name not in _RERANKERS:
        raise KeyError(f"unknown reranker {name!r}; registered: {sorted(_RERANKERS)}")
    return _RERANKERS[name](**kwargs)


def reranker_class(name: str) -> type:
    """The registered class, for what must be known before the reranker exists:
    what it would bill per query, and so what the run would cost (P2-06)."""
    _ensure_builtins()
    if name not in _RERANKERS:
        raise KeyError(f"unknown reranker {name!r}; registered: {sorted(_RERANKERS)}")
    return _RERANKERS[name]


def registered_rerankers() -> list[str]:
    _ensure_builtins()
    return sorted(_RERANKERS)
