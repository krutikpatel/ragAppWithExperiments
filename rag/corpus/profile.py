"""Corpus profiling — P1-02.

A characterization of the frozen corpus, not an experiment: nothing here retrieves
or scores anything. It exists so that chunking results can be read against the
shape of the data rather than guessed at. Every number it emits is written to a
JSON artifact under `results/corpus_profile/` first; the markdown block that lands
in `docs/EXPERIMENTS.md` mirrors that artifact.

Two units appear throughout, and both are always labelled:

- **words** — whitespace tokens, the chunker's unit (DEC-005).
- **tokens** — `cl100k_base` BPE tokens, what a model sees (DEC-029: ~1.27 per word).

On "numbered step lists": the frozen `contents` field has had its list markers
stripped at extraction. A procedure in this corpus reads "To remove animation:\n
Click the element. Click the Animation icon. Click None." — no `1.`, `2.`, `3.`.
Only 21 of 6,221 articles carry a literal numbered line. So the profile reports the
literal count the story asks for *and* a heuristic "procedure block" count that
matches how procedures actually appear. The heuristic is defined in
`find_procedure_blocks` and recorded in DEC-039; its agreement with the source HTML
is untested (OQ-020).
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.hashing import canonical_json, short_id
from rag.paths import DOCS_DIR, RESULTS_DIR

# Bump when the heuristics or the emitted fields change. A new version appends a new
# block to EXPERIMENTS.md; it never rewrites an old one.
PROFILE_VERSION = "profile-v1"

BPE_ENCODING = "cl100k_base"

# Histogram bin edges in words. The last bin is open-ended.
HISTOGRAM_EDGES = [0, 100, 200, 300, 400, 500, 600, 800, 1000, 1500, 2000, 3000]

# A literal numbered line: "1. text" or "1) text" at the start of a line. The same
# pattern `rag/eval/steps.py` uses on reference answers.
_NUMBERED_LINE = re.compile(r"^[ \t]*\d+[.)]\s+\S", re.MULTILINE)

# Verbs that open a step in this corpus's procedures. Fixed and documented on
# purpose: the count depends on this list, so the list is part of the definition.
IMPERATIVE_VERBS = (
    "Click", "Select", "Go to", "Choose", "Enter", "Hover", "Tap", "Open", "Scroll",
    "Drag", "Type", "Add", "Set", "Toggle", "Navigate", "Check", "Uncheck", "Log in",
    "Sign in", "Press", "Copy", "Paste", "Upload", "Edit", "Publish", "Create",
    "Delete", "Remove", "Connect", "Save", "Fill", "Pick", "Switch", "Enable",
    "Disable", "Customize", "Adjust", "Confirm", "Review", "Download", "Install",
    "Refresh", "Search", "Find", "Locate", "Use", "Make sure", "Repeat", "Turn on",
    "Turn off", "Drag", "Drop", "Enter", "Choose", "Preview", "Start", "Stop",
)
_VERB_ALT = "|".join(re.escape(v) for v in IMPERATIVE_VERBS)
# One step: an imperative opening, then text up to a sentence terminator. A
# terminator only counts when followed by whitespace, an uppercase letter or the end
# of text, so "e.g. 3" does not end a step but "page.FAQs" does.
_STEP_SENTENCE = rf"(?:{_VERB_ALT})[^.!?\n]*?[.!?](?=\s|[A-Z]|$)"
# A block: a header sentence ending in ':' at the end of a line, then two or more
# step sentences. The header is the text since the previous sentence terminator or
# newline, not the whole line — articles here have a median of three newlines, so a
# line is often an entire section and would drag unrelated prose into the block.
_PROCEDURE_BLOCK = re.compile(
    rf"(?:(?<=[.!?\n])|^)[^\n.!?:]*:[ \t]*\n(?:\s*{_STEP_SENTENCE}){{2,}}",
    re.MULTILINE,
)
_STEP_ONLY = re.compile(_STEP_SENTENCE)


@dataclass(frozen=True)
class ProcedureBlock:
    """A procedure's span in whitespace-token positions, header included."""

    start_token: int
    end_token: int  # exclusive

    @property
    def n_tokens(self) -> int:
        return self.end_token - self.start_token


@dataclass(frozen=True)
class ChunkSpan:
    start_token: int
    end_token: int  # exclusive


def token_offsets(text: str) -> list[tuple[int, int]]:
    """Character spans of every whitespace token, in `str.split()` order.

    `str.split()` splits on Unicode whitespace; so does `\\S+` under `re` for str
    patterns. The equality is asserted rather than assumed because the corpus
    contains U+00A0 and U+FEFF, and the two definitions disagreeing would silently
    misplace every boundary.
    """
    spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if len(spans) != len(text.split()):
        raise ValueError("regex tokenization disagrees with str.split(); profile cannot map offsets")
    return spans


def chunk_spans(n_tokens: int, chunk_size: int, overlap: int) -> list[ChunkSpan]:
    """The token spans `FixedTokenChunker` would produce, without building chunks.

    Mirrors the loop in `rag.chunking.base.FixedTokenChunker.split` exactly,
    including its early stop once a window reaches the end of the document.
    """
    if n_tokens == 0:
        return []
    stride = chunk_size - overlap
    spans: list[ChunkSpan] = []
    for start in range(0, n_tokens, stride):
        spans.append(ChunkSpan(start, min(start + chunk_size, n_tokens)))
        if start + chunk_size >= n_tokens:
            break
    return spans


def find_procedure_blocks(text: str) -> list[ProcedureBlock]:
    """Procedure blocks in a document, as whitespace-token spans.

    Definition (DEC-039): a line ending in ':' followed by at least two consecutive
    sentences that each open with a verb from `IMPERATIVE_VERBS`. The header line is
    part of the block, because a boundary between "To do X:" and its steps separates
    the steps from their purpose. The block ends at the first sentence that does not
    open with a listed verb.
    """
    offsets = token_offsets(text)
    if not offsets:
        return []
    starts = [s for s, _ in offsets]
    blocks: list[ProcedureBlock] = []
    for match in _PROCEDURE_BLOCK.finditer(text):
        first_char = match.start()
        # Skip leading whitespace so the header's first token is located, not the
        # token before it.
        while first_char < match.end() and text[first_char].isspace():
            first_char += 1
        last_char = match.end() - 1
        start_token = bisect_right(starts, first_char) - 1
        end_token = bisect_right(starts, last_char)
        if start_token < 0 or end_token <= start_token:
            continue
        blocks.append(ProcedureBlock(start_token, end_token))
    return blocks


def is_cut(block: ProcedureBlock, spans: list[ChunkSpan]) -> bool:
    """True when no single chunk contains the whole block.

    With overlap, a block that straddles a stride boundary may still sit entirely
    inside one of the two chunks that share the overlap; that is not a cut. A block
    longer than `chunk_size` is always cut.
    """
    return not any(s.start_token <= block.start_token and block.end_token <= s.end_token for s in spans)


def count_numbered_lines(text: str) -> int:
    return len(_NUMBERED_LINE.findall(text))


def _percentiles(values: list[int]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    n = len(ordered)

    def pct(p: float) -> float:
        # Nearest-rank, so every reported percentile is a value that occurs.
        rank = max(1, int(round(p / 100 * n)))
        return float(ordered[min(rank, n) - 1])

    return {
        "n": n,
        "min": float(ordered[0]),
        "p25": pct(25),
        "median": pct(50),
        "p75": pct(75),
        "p90": pct(90),
        "p95": pct(95),
        "max": float(ordered[-1]),
        "mean": round(sum(ordered) / n, 1),
        "total": float(sum(ordered)),
    }


def _histogram(values: list[int], edges: list[int]) -> list[dict[str, Any]]:
    bins: list[dict[str, Any]] = []
    for lo, hi in zip(edges, edges[1:] + [None], strict=True):
        count = sum(1 for v in values if v >= lo and (hi is None or v < hi))
        bins.append({"lo": lo, "hi": hi, "count": count, "fraction": round(count / len(values), 4) if values else 0.0})
    return bins


@dataclass(frozen=True)
class ChunkConfigProfile:
    chunk_size: int
    overlap: int
    n_chunks: int
    fits_in_one_chunk: int
    fits_in_one_chunk_fraction: float
    procedure_blocks_cut: int
    procedure_blocks_cut_fraction: float
    procedure_blocks_longer_than_chunk: int
    # A block no longer than the overlap can never be cut: whichever stride boundary
    # it straddles, one of the two chunks sharing the overlap holds all of it. This
    # count says how many blocks are even eligible to be cut under this config.
    procedure_blocks_longer_than_overlap: int
    articles_with_cut_block: int
    articles_with_cut_block_fraction: float


def _profile_group(
    rows: list[dict[str, Any]], chunk_configs: list[tuple[int, int]]
) -> dict[str, Any]:
    """Profile one group of documents (the whole corpus, or one article_type)."""
    n = len(rows)
    words = [r["n_words"] for r in rows]
    tokens = [r["n_tokens"] for r in rows]
    with_numbered = sum(1 for r in rows if r["n_numbered_lines"] >= 1)
    with_numbered_list = sum(1 for r in rows if r["n_numbered_lines"] >= 2)
    with_blocks = sum(1 for r in rows if r["blocks"])
    n_blocks = sum(len(r["blocks"]) for r in rows)
    block_lengths = [b.n_tokens for r in rows for b in r["blocks"]]

    per_config: list[dict[str, Any]] = []
    for chunk_size, overlap in chunk_configs:
        n_chunks = 0
        fits = 0
        cut = 0
        too_long = 0
        longer_than_overlap = 0
        articles_cut = 0
        for r in rows:
            spans = chunk_spans(r["n_words"], chunk_size, overlap)
            n_chunks += len(spans)
            if r["n_words"] <= chunk_size:
                fits += 1
            any_cut = False
            for b in r["blocks"]:
                if b.n_tokens > chunk_size:
                    too_long += 1
                if b.n_tokens > overlap:
                    longer_than_overlap += 1
                if is_cut(b, spans):
                    cut += 1
                    any_cut = True
            if any_cut:
                articles_cut += 1
        per_config.append(
            asdict(
                ChunkConfigProfile(
                    chunk_size=chunk_size,
                    overlap=overlap,
                    n_chunks=n_chunks,
                    fits_in_one_chunk=fits,
                    fits_in_one_chunk_fraction=round(fits / n, 4) if n else 0.0,
                    procedure_blocks_cut=cut,
                    procedure_blocks_cut_fraction=round(cut / n_blocks, 4) if n_blocks else 0.0,
                    procedure_blocks_longer_than_chunk=too_long,
                    procedure_blocks_longer_than_overlap=longer_than_overlap,
                    articles_with_cut_block=articles_cut,
                    articles_with_cut_block_fraction=round(articles_cut / n, 4) if n else 0.0,
                )
            )
        )

    return {
        "n_articles": n,
        "length_words": _percentiles(words),
        "length_tokens": _percentiles(tokens),
        "tokens_per_word": round(sum(tokens) / sum(words), 3) if sum(words) else None,
        "histogram_words": _histogram(words, HISTOGRAM_EDGES),
        "numbered_lines": {
            "articles_with_any_numbered_line": with_numbered,
            "fraction_any": round(with_numbered / n, 4) if n else 0.0,
            "articles_with_numbered_list_2plus": with_numbered_list,
            "fraction_2plus": round(with_numbered_list / n, 4) if n else 0.0,
        },
        "procedure_blocks": {
            "articles_with_block": with_blocks,
            "fraction": round(with_blocks / n, 4) if n else 0.0,
            "n_blocks": n_blocks,
            "block_length_words": _percentiles(block_lengths),
        },
        "chunk_configs": per_config,
    }


def profile_corpus(chunk_configs: list[tuple[int, int]] | None = None) -> dict[str, Any]:
    """Compute the profile over the frozen corpus. Pure: writes nothing."""
    import tiktoken

    from rag.corpus.loader import load_corpus

    chunk_configs = chunk_configs or [(600, 100), (600, 0), (512, 0)]
    corpus = load_corpus()
    encoding = tiktoken.get_encoding(BPE_ENCODING)

    rows: list[dict[str, Any]] = []
    for doc_id, text, article_type in zip(
        corpus.frame["id"], corpus.frame["indexed_text"], corpus.frame["article_type"], strict=True
    ):
        rows.append(
            {
                "doc_id": doc_id,
                "article_type": article_type,
                "n_words": len(text.split()),
                "n_tokens": len(encoding.encode(text, disallowed_special=())),
                "n_numbered_lines": count_numbered_lines(text),
                "blocks": find_procedure_blocks(text),
            }
        )

    by_type: dict[str, Any] = {}
    for article_type in sorted({r["article_type"] for r in rows}):
        by_type[article_type] = _profile_group([r for r in rows if r["article_type"] == article_type], chunk_configs)

    return {
        "profile_version": PROFILE_VERSION,
        "corpus_hash": corpus.corpus_hash,
        "normalization_version": corpus.normalization_version,
        "hf_revision": corpus.hf_revision,
        "bpe_encoding": BPE_ENCODING,
        "chunk_unit": "whitespace words (DEC-005)",
        "imperative_verbs": list(IMPERATIVE_VERBS),
        "histogram_edges_words": HISTOGRAM_EDGES,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "all": _profile_group(rows, chunk_configs),
        "by_article_type": by_type,
    }


# --- artifact and markdown ----------------------------------------------------

PROFILE_DIR = RESULTS_DIR / "corpus_profile"
DOC_START = "<!-- corpus-profile:{key} start -->"
DOC_END = "<!-- corpus-profile:{key} end -->"


def profile_key(profile: dict[str, Any]) -> str:
    """Identity of a profile: corpus, normalization, heuristics version."""
    return short_id(profile["corpus_hash"], profile["normalization_version"], profile["profile_version"], length=12)


def write_profile_artifact(profile: dict[str, Any]) -> Path:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILE_DIR / f"{profile_key(profile)}.json"
    path.write_text(json.dumps(profile, indent=2) + "\n")
    return path


def _fmt_pct(stats: dict[str, float]) -> str:
    return " | ".join(f"{int(stats[k]):,}" for k in ("min", "p25", "median", "p75", "p90", "p95", "max"))


def _bar(fraction: float, width: int = 40) -> str:
    return "█" * int(round(fraction * width))


def render_markdown(profile: dict[str, Any], artifact_path: Path) -> str:
    """The characterization block for docs/EXPERIMENTS.md. Mirrors the artifact."""
    key = profile_key(profile)
    a = profile["all"]
    types = profile["by_article_type"]
    lines: list[str] = []
    lines.append(DOC_START.format(key=key))
    lines.append(f"## Corpus profile — characterization, not an experiment ({profile['profile_version']})")
    lines.append("")
    lines.append(
        f"Written by `rag corpus profile` from `{artifact_path.relative_to(RESULTS_DIR.parent)}`. "
        f"Corpus `{profile['corpus_hash'][:19]}…`, `{profile['normalization_version']}`, "
        f"{a['n_articles']:,} articles. Two units, always labelled: **words** are whitespace "
        f"tokens, the chunker's unit (DEC-005); **tokens** are `{profile['bpe_encoding']}` BPE "
        f"tokens, {a['tokens_per_word']} per word on this corpus."
    )
    lines.append("")
    lines.append("### Article length")
    lines.append("")
    lines.append("| Unit | min | p25 | median | p75 | p90 | p95 | max | mean |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    lines.append(f"| words | {_fmt_pct(a['length_words'])} | {a['length_words']['mean']} |")
    lines.append(f"| tokens | {_fmt_pct(a['length_tokens'])} | {a['length_tokens']['mean']} |")
    lines.append("")
    lines.append("Histogram, in words:")
    lines.append("")
    lines.append("```")
    for b in a["histogram_words"]:
        label = f"{b['lo']:>5}–{b['hi'] - 1:<5}" if b["hi"] is not None else f"{b['lo']:>5}+     "
        lines.append(f"{label} {b['count']:>5} {b['fraction']:6.1%} {_bar(b['fraction'])}")
    lines.append("```")
    lines.append("")
    lines.append("### Fit in one chunk, and procedure boundaries")
    lines.append("")
    lines.append(
        "A **procedure block** is a heuristic (DEC-039): a line ending in `:` followed by two or "
        "more sentences that open with an imperative verb from a fixed list. It exists because "
        "the frozen text has no list markers — the source's numbered lists arrive as "
        "\"To do X:\\nClick A. Click B.\" — so the literal numbered-line count the story asks "
        "for is also reported, and is tiny. A block is **cut** when no single chunk contains "
        "all of it, header included; with overlap, straddling a stride boundary is not a cut "
        "if one of the two overlapping chunks still holds the whole block."
    )
    lines.append("")
    nl = a["numbered_lines"]
    pb = a["procedure_blocks"]
    lines.append(
        f"- Articles with a literal numbered line (`1.` / `1)`): **{nl['articles_with_any_numbered_line']}** "
        f"({nl['fraction_any']:.1%}); with two or more: {nl['articles_with_numbered_list_2plus']} "
        f"({nl['fraction_2plus']:.1%})."
    )
    bl = pb["block_length_words"]
    block_lengths = (
        f"median {int(bl['median'])} words, p90 {int(bl['p90'])}, max {int(bl['max'])}" if bl else "no blocks"
    )
    lines.append(
        f"- Articles with at least one procedure block: **{pb['articles_with_block']:,}** "
        f"({pb['fraction']:.1%}); {pb['n_blocks']:,} blocks in total, {block_lengths}."
    )
    lines.append("")
    lines.append("| Chunk config (words) | chunks | articles that fit in one chunk | procedure blocks cut | blocks longer than the overlap (eligible to be cut) | blocks longer than a chunk | articles with a cut block |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in a["chunk_configs"]:
        lines.append(
            f"| {c['chunk_size']}/{c['overlap']} | {c['n_chunks']:,} | {c['fits_in_one_chunk']:,} "
            f"({c['fits_in_one_chunk_fraction']:.1%}) | {c['procedure_blocks_cut']:,} "
            f"({c['procedure_blocks_cut_fraction']:.1%}) | {c['procedure_blocks_longer_than_overlap']:,} | "
            f"{c['procedure_blocks_longer_than_chunk']} | "
            f"{c['articles_with_cut_block']:,} ({c['articles_with_cut_block_fraction']:.1%}) |"
        )
    lines.append("")
    lines.append(
        "A block no longer than the overlap cannot be cut: whichever stride boundary it "
        "straddles, one of the two chunks that share the overlap holds all of it. The "
        "\"eligible\" column is therefore the ceiling on the cut count for that config."
    )
    lines.append("")
    lines.append("### By article type")
    lines.append("")
    lines.append("| Type | n | words median | words p90 | words max | tokens median | literal numbered line | procedure block | blocks | block words median / max |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for name, t in types.items():
        bl = t["procedure_blocks"]["block_length_words"]
        lines.append(
            f"| {name} | {t['n_articles']:,} | {int(t['length_words']['median'])} | "
            f"{int(t['length_words']['p90'])} | {int(t['length_words']['max']):,} | "
            f"{int(t['length_tokens']['median'])} | "
            f"{t['numbered_lines']['articles_with_any_numbered_line']} ({t['numbered_lines']['fraction_any']:.1%}) | "
            f"{t['procedure_blocks']['articles_with_block']:,} ({t['procedure_blocks']['fraction']:.1%}) | "
            f"{t['procedure_blocks']['n_blocks']:,} | "
            f"{int(bl['median']) if bl else '—'} / {int(bl['max']) if bl else '—'} |"
        )
    lines.append("")
    lines.append("| Type | chunk config | chunks | fit in one chunk | blocks cut | articles with a cut block |")
    lines.append("|---|---|---|---|---|---|")
    for name, t in types.items():
        for c in t["chunk_configs"]:
            lines.append(
                f"| {name} | {c['chunk_size']}/{c['overlap']} | {c['n_chunks']:,} | "
                f"{c['fits_in_one_chunk']:,} ({c['fits_in_one_chunk_fraction']:.1%}) | "
                f"{c['procedure_blocks_cut']} ({c['procedure_blocks_cut_fraction']:.1%}) | "
                f"{c['articles_with_cut_block']} ({c['articles_with_cut_block_fraction']:.1%}) |"
            )
    lines.append("")
    lines.append(DOC_END.format(key=key))
    return "\n".join(lines) + "\n"


def write_profile_docs(profile: dict[str, Any], artifact_path: Path, docs_path: Path | None = None) -> str:
    """Append the block to docs/EXPERIMENTS.md, append-only.

    Same key already present and identical: no-op. Present and different: refuse —
    bump `PROFILE_VERSION` so the new block lands beside the old one rather than
    over it. Returns one of "appended", "unchanged".
    """
    docs_path = docs_path or DOCS_DIR / "EXPERIMENTS.md"
    block = render_markdown(profile, artifact_path)
    key = profile_key(profile)
    existing = docs_path.read_text()
    start, end = DOC_START.format(key=key), DOC_END.format(key=key)
    if start in existing:
        current = existing[existing.index(start) : existing.index(end) + len(end)] + "\n"
        if current == block:
            return "unchanged"
        raise RuntimeError(
            f"a corpus profile block with key {key} already exists in {docs_path.name} and "
            "differs from this output. The file is append-only: bump PROFILE_VERSION so the "
            "new block is appended alongside the old one."
        )
    separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    docs_path.write_text(existing + separator + block)
    return "appended"


def profile_summary_lines(profile: dict[str, Any]) -> list[str]:
    """A short stdout summary; the markdown is the full report."""
    a = profile["all"]
    out = [
        f"articles: {a['n_articles']:,}   words median {int(a['length_words']['median'])}, "
        f"p90 {int(a['length_words']['p90'])}, max {int(a['length_words']['max'])}   "
        f"tokens/word {a['tokens_per_word']}",
        f"procedure blocks: {a['procedure_blocks']['n_blocks']:,} in "
        f"{a['procedure_blocks']['articles_with_block']:,} articles ({a['procedure_blocks']['fraction']:.1%}); "
        f"literal numbered lines in {a['numbered_lines']['articles_with_any_numbered_line']} articles",
    ]
    for c in a["chunk_configs"]:
        out.append(
            f"  {c['chunk_size']}/{c['overlap']}: {c['n_chunks']:,} chunks, "
            f"{c['fits_in_one_chunk_fraction']:.1%} of articles fit in one chunk, "
            f"{c['procedure_blocks_cut']:,} blocks cut ({c['procedure_blocks_cut_fraction']:.1%})"
        )
    return out


def profile_hash(profile: dict[str, Any]) -> str:
    """Hash of the numbers only — `computed_at` excluded — so re-runs can be compared."""
    payload = {k: v for k, v in profile.items() if k != "computed_at"}
    return short_id(canonical_json(payload))
