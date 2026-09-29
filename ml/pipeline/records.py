"""On-disk record shapes.

The chunk record is the contract between ingestion and everything downstream:
the index in ML-3, the retriever in ML-4, the API in SWE-4. Changing a field
means bumping SCHEMA_VERSION, because a stale index cannot be read otherwise.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from ..ingestion.chunking import Chunk
from .keys import SCHEMA_VERSION


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chunk_record(chunk: Chunk, run_id: str) -> dict:
    """One retrievable unit, with everything needed to cite and to rebuild."""
    return {
        "schema_version": SCHEMA_VERSION,
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "citation": chunk.citation,
        "pinpoint": chunk.pinpoint,
        "heading": chunk.heading,
        "part": chunk.part,
        "subpart": chunk.subpart,
        "authority": chunk.authority,
        "as_of": chunk.as_of,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "split_paragraph": chunk.split_paragraph,
        "flags": list(chunk.flags),
        "text_sha256": sha256(chunk.text.encode()),
        "run_id": run_id,
    }


def to_jsonl(records: list[dict]) -> bytes:
    return ("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n").encode()


def from_jsonl(body: bytes) -> list[dict]:
    return [json.loads(line) for line in body.decode().splitlines() if line.strip()]


@dataclass
class PartResult:
    """What one part contributed, and the proof it was checked."""

    part: str
    raw_key: str
    chunks_key: str
    raw_sha256: str
    chunks_sha256: str
    sections: int
    chunks: int
    tokens_max: int
    body_lines_checked: int
    unresolved_labels: int
    marker_collisions: int

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Manifest:
    """A complete, loadable ingestion. Written only after every gate passed."""

    run_id: str
    source_id: str
    as_of: str
    schema_version: int
    started_at: str
    finished_at: str
    token_counter: str
    max_tokens: int
    parts: list[dict] = field(default_factory=list)

    @property
    def totals(self) -> dict:
        return {
            "sections": sum(p["sections"] for p in self.parts),
            "chunks": sum(p["chunks"] for p in self.parts),
            "body_lines_checked": sum(p["body_lines_checked"] for p in self.parts),
            "unresolved_labels": sum(p["unresolved_labels"] for p in self.parts),
            "marker_collisions": sum(p["marker_collisions"] for p in self.parts),
        }

    def to_bytes(self) -> bytes:
        payload = {
            "run_id": self.run_id,
            "source_id": self.source_id,
            "as_of": self.as_of,
            "schema_version": self.schema_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "token_counter": self.token_counter,
            "max_tokens": self.max_tokens,
            "totals": self.totals,
            "parts": self.parts,
        }
        return (json.dumps(payload, indent=2) + "\n").encode()
