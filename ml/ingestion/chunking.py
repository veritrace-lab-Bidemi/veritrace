"""Section-aware chunking.

One section is the unit of citation, so chunks never cross a section boundary.
Inside a section, paragraphs are packed whole. A chunk carries a breadcrumb
header and, when it starts part-way down a list, the ancestor paragraphs it
sits under, so a retrieved chunk still says what it is about.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .ecfr import MARKER, Paragraph, Section
from .tokens import TokenCounter

SENTENCE = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")
CONTEXT_CHARS = 100

# The context line orients the reader; it is not a second copy of the section.
# Deeply nested sections such as 31 CFR 1010.100 have long ancestor chains, so
# the line is capped and the shallowest ancestors are dropped first, keeping the
# nearest parents, which carry the most meaning.
MAX_CONTEXT = 3
HEADER_TOKEN_SHARE = 0.25

# Tokens do not add linearly across a join: the boundary between the header and
# the body can merge or split one. Without slack a chunk lands a token or two
# over the limit and the embedding model truncates it silently.
JOIN_ALLOWANCE = 8


@dataclass
class Chunk:
    """One retrievable unit with everything needed to cite it."""

    chunk_id: str
    source_id: str
    citation: str
    pinpoint: str  # paragraph range inside the section
    heading: str
    part: str
    subpart: str
    authority: str
    as_of: str
    text: str
    token_count: int
    split_paragraph: bool = False  # a paragraph had to be divided
    flags: tuple[str, ...] = field(default_factory=tuple)


def _strip_marker(text: str) -> str:
    """Drop the leading (a) so the context line does not print it twice."""
    return MARKER.sub("", text, count=1)


def _fmt_path(path: tuple[str, ...]) -> str:
    return "".join(f"({p})" for p in path) if path else ""


def _pinpoint(paragraphs: list[Paragraph]) -> str:
    paths = [p.path for p in paragraphs if p.path]
    if not paths:
        return ""
    first, last = _fmt_path(paths[0]), _fmt_path(paths[-1])
    return first if first == last else f"{first} to {last}"


def _crumbs(context: list[Paragraph]) -> str:
    return "; ".join(
        f"{_fmt_path(p.path)} {_strip_marker(p.text)[:CONTEXT_CHARS].rstrip()}"
        for p in context
    )


def _header(
    section: Section,
    as_of: str,
    context: list[Paragraph],
    counter: TokenCounter | None = None,
    cap: int | None = None,
) -> str:
    lines = [f"{section.citation} {section.heading}".strip()]
    place = [f"Part {section.part}"] if section.part else []
    if section.subpart:
        place.append(f"Subpart {section.subpart}")
    place.append(f"in force as of {as_of}")
    lines.append(" | ".join([", ".join(place[:-1]), place[-1]]).lstrip(", "))

    kept = context[-MAX_CONTEXT:]
    # Drop the shallowest ancestors until the whole header fits the cap.
    while kept and counter and cap:
        if counter.count("\n".join(lines + [f"Starts under: {_crumbs(kept)}"])) <= cap:
            break
        kept = kept[1:]
    if kept:
        lines.append(f"Starts under: {_crumbs(kept)}")
    return "\n".join(lines)


def _ancestors(paragraphs: list[Paragraph], first: Paragraph) -> list[Paragraph]:
    """Paragraphs whose path is a proper prefix of the chunk's first paragraph."""
    out = []
    for p in paragraphs:
        if p is first:
            break
        if p.path and len(p.path) < len(first.path) and first.path[: len(p.path)] == p.path:
            out = [a for a in out if len(a.path) < len(p.path)] + [p]
    return out


def _split_long(text: str, budget: int, counter: TokenCounter) -> list[str]:
    """Divide one oversized paragraph on sentence boundaries."""
    sentences = SENTENCE.split(text)
    parts: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = current + [sentence]
        if counter.count(" ".join(candidate)) > budget and current:
            parts.append(" ".join(current))
            current = [sentence]
        else:
            current = candidate
    if current:
        parts.append(" ".join(current))
    return parts


def chunk_section(
    section: Section,
    counter: TokenCounter,
    source_id: str,
    as_of: str,
    authority: str = "binding",
    max_tokens: int = 512,
    min_tokens: int = 64,
) -> list[Chunk]:
    """Pack one section's paragraphs into chunks of at most max_tokens."""
    chunks: list[Chunk] = []
    batch: list[Paragraph] = []
    split_flag = False
    header_cap = int(max_tokens * HEADER_TOKEN_SHARE)

    def emit() -> None:
        nonlocal batch, split_flag
        if not batch:
            return
        context = _ancestors(section.paragraphs, batch[0])
        header = _header(section, as_of, context, counter, header_cap)
        body = "\n".join(p.text for p in batch)
        text = f"{header}\n\n{body}"
        flags = tuple(
            sorted({"unresolved_paragraph_label" for p in batch if p.unresolved})
        )
        chunks.append(
            Chunk(
                chunk_id=_chunk_id(source_id, section.citation, len(chunks)),
                source_id=source_id,
                citation=section.citation,
                pinpoint=_pinpoint(batch),
                heading=section.heading,
                part=section.part,
                subpart=section.subpart,
                authority=authority,
                as_of=as_of,
                text=text,
                token_count=counter.count(text),
                split_paragraph=split_flag,
                flags=flags,
            )
        )
        batch = []
        split_flag = False

    def budget_for(first: Paragraph) -> int:
        """Body budget for a chunk starting at this paragraph.

        The header grows with ancestor depth, so it is measured per chunk. A
        single section-wide reserve would shrink every chunk to suit its
        deepest paragraph and split text that would otherwise fit.
        """
        context = _ancestors(section.paragraphs, first)
        header = counter.count(
            _header(section, as_of, context, counter, header_cap)
        )
        budget = max_tokens - header - JOIN_ALLOWANCE
        if budget < min_tokens:
            raise ValueError(
                f"max_tokens={max_tokens} is too small for {section.citation}: "
                f"its header needs {header} tokens, leaving {budget} for text, "
                f"below min_tokens={min_tokens}"
            )
        return budget

    for para in section.paragraphs:
        size = counter.count(para.text)
        budget = budget_for(batch[0] if batch else para)
        if size > budget_for(para):
            emit()
            budget = budget_for(para)
            for piece in _split_long(para.text, budget, counter):
                batch = [
                    Paragraph(para.label, para.path, piece, para.unresolved, para.collided)
                ]
                split_flag = True
                emit()
            continue
        running = counter.count("\n".join(p.text for p in batch + [para]))
        if batch and running > budget:
            emit()
        batch.append(para)
    emit()

    return _merge_tail(chunks, counter, max_tokens, min_tokens)


def _merge_tail(
    chunks: list[Chunk], counter: TokenCounter, max_tokens: int, min_tokens: int
) -> list[Chunk]:
    """Fold a too-small final chunk into the one before it when it fits."""
    if len(chunks) < 2 or chunks[-1].token_count >= min_tokens:
        return chunks
    last, previous = chunks.pop(), chunks[-1]
    body = last.text.split("\n\n", 1)[-1]
    merged = f"{previous.text}\n{body}"
    if counter.count(merged) <= max_tokens:
        previous.text = merged
        previous.token_count = counter.count(merged)
        previous.pinpoint = _merge_pinpoints(previous.pinpoint, last.pinpoint)
        previous.flags = tuple(sorted(set(previous.flags) | set(last.flags)))
    else:
        chunks.append(last)
    return chunks


def _merge_pinpoints(first: str, second: str) -> str:
    start = first.split(" to ")[0]
    end = second.split(" to ")[-1]
    return start if start == end else f"{start} to {end}"


def _chunk_id(source_id: str, citation: str, index: int) -> str:
    key = f"{source_id}|{citation}|{index}".encode()
    return hashlib.sha256(key).hexdigest()[:16]


def chunk_sections(sections: list[Section], counter: TokenCounter, **kw) -> list[Chunk]:
    out: list[Chunk] = []
    for section in sections:
        out.extend(chunk_section(section, counter, **kw))
    return out
