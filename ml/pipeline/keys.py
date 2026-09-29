"""S3 key layout.

Every key carries the source and the issue date the text was current as of, so
two ingestions of different vintages coexist and a rebuild can name exactly
which one to load. Nothing is overwritten in place.

  raw/        ecfr-31-x/2026-09-10/part-1020.xml
  chunks/     ecfr-31-x/2026-09-10/part-1020.jsonl
  manifests/  ecfr-31-x/2026-09-10/manifest.json
  manifests/  ecfr-31-x/latest.json
"""

SCHEMA_VERSION = 1


def raw_key(source_id: str, as_of: str, part: str) -> str:
    return f"raw/{source_id}/{as_of}/part-{part}.xml"


def chunks_key(source_id: str, as_of: str, part: str) -> str:
    return f"chunks/{source_id}/{as_of}/part-{part}.jsonl"


def manifest_key(source_id: str, as_of: str) -> str:
    return f"manifests/{source_id}/{as_of}/manifest.json"


def latest_key(source_id: str) -> str:
    """Pointer to the newest complete run. Written last, so it never names a
    partial ingestion."""
    return f"manifests/{source_id}/latest.json"
