"""Pipeline stages.

Three stages, each doing one thing so Step Functions can retry it alone:

  fetch      one part's XML from eCFR into raw storage
  transform  raw XML into validated chunk records
  finalize   the manifest, written last so `latest` never names a partial run

The gates in transform raise. ML-1 showed the parser can be confidently wrong,
and a wrong citation is worse than a missing one because it is quotable, so a
failed check stops the run rather than annotating it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..ingestion import ecfr
from ..ingestion.chunking import chunk_sections
from ..ingestion.tokens import TokenCounter, default_counter
from . import keys
from .records import Manifest, PartResult, chunk_record, sha256, to_jsonl
from .storage import Storage


class ValidationFailed(RuntimeError):
    """A gate rejected the output. The run stops here."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch(storage: Storage, source_id: str, part: str, as_of: str) -> dict:
    """Download one part unless it is already stored for this issue date."""
    key = keys.raw_key(source_id, as_of, part)
    if storage.exists(key):
        body = storage.get(key)
        cached = True
    else:
        body = ecfr.fetch_part(part, as_of)
        storage.put(key, body)
        cached = False
    return {
        "part": part,
        "as_of": as_of,
        "raw_key": key,
        "raw_sha256": sha256(body),
        "bytes": len(body),
        "cached": cached,
    }


def _check_paths(sections) -> None:
    bad = [
        f"{s.citation} {''.join('(' + x + ')' for x in p.path)}"
        for s in sections
        for p in s.paragraphs
        if p.path and not ecfr.path_follows_cycle(p.path)
    ]
    if bad:
        raise ValidationFailed(
            f"{len(bad)} paragraph paths are impossible under the CFR cycle, "
            f"first: {bad[:3]}"
        )


def _check_verbatim(sections, chunks) -> int:
    source = {s.citation: s.text for s in sections}
    checked = 0
    bad: list[str] = []
    for chunk in chunks:
        body = chunk.text.split("\n\n", 1)[-1]
        for line in body.splitlines():
            if not line.strip():
                continue
            checked += 1
            if line not in source.get(chunk.citation, ""):
                bad.append(f"{chunk.citation} {chunk.pinpoint}: {line[:80]}")
    if bad:
        raise ValidationFailed(
            f"{len(bad)} chunk lines are not verbatim in their source, "
            f"first: {bad[:3]}"
        )
    return checked


def transform(
    storage: Storage,
    source_id: str,
    part: str,
    as_of: str,
    run_id: str,
    max_tokens: int = 512,
    counter: TokenCounter | None = None,
) -> dict:
    """Parse one part, chunk it, check it, and store the records."""
    counter = counter or default_counter()
    raw = storage.get(keys.raw_key(source_id, as_of, part))
    sections = ecfr.parse_sections(raw)

    _check_paths(sections)
    chunks = chunk_sections(
        sections,
        counter,
        source_id=source_id,
        as_of=as_of,
        max_tokens=max_tokens,
    )
    lines_checked = _check_verbatim(sections, chunks)

    over = [c.chunk_id for c in chunks if c.token_count > max_tokens]
    if over:
        raise ValidationFailed(f"{len(over)} chunks exceed {max_tokens} tokens")

    body = to_jsonl([chunk_record(c, run_id) for c in chunks])
    key = keys.chunks_key(source_id, as_of, part)
    storage.put(key, body)

    return PartResult(
        part=part,
        raw_key=keys.raw_key(source_id, as_of, part),
        chunks_key=key,
        raw_sha256=sha256(raw),
        chunks_sha256=sha256(body),
        sections=len(sections),
        chunks=len(chunks),
        tokens_max=max(((c.token_count) for c in chunks), default=0),
        body_lines_checked=lines_checked,
        unresolved_labels=sum(1 for c in chunks if c.flags),
        marker_collisions=sum(
            1 for s in sections for p in s.paragraphs if p.collided
        ),
    ).as_dict()


def finalize(
    storage: Storage,
    source_id: str,
    as_of: str,
    run_id: str,
    parts: list[dict],
    started_at: str,
    token_counter: str,
    max_tokens: int = 512,
) -> dict:
    """Write the manifest, then move the `latest` pointer to it."""
    if not parts:
        raise ValidationFailed("no parts were ingested")

    manifest = Manifest(
        run_id=run_id,
        source_id=source_id,
        as_of=as_of,
        schema_version=keys.SCHEMA_VERSION,
        started_at=started_at,
        finished_at=now(),
        token_counter=token_counter,
        max_tokens=max_tokens,
        parts=sorted(parts, key=lambda p: p["part"]),
    )
    body = manifest.to_bytes()
    key = keys.manifest_key(source_id, as_of)
    storage.put(key, body)
    # Written second and only on success, so `latest` never names a partial run.
    storage.put(keys.latest_key(source_id), body)

    return {
        "manifest_key": key,
        "latest_key": keys.latest_key(source_id),
        "run_id": run_id,
        "as_of": as_of,
        **manifest.totals,
    }
