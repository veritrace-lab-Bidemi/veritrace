"""Lambda entry point.

One function, four actions, dispatched by the state machine. Keeping them in
one deployment package means one build and one set of permissions; Step
Functions still retries each action independently.
"""

from __future__ import annotations

import os
import uuid

from ..ingestion.ecfr import latest_issue_date
from ..ingestion.sources import BSA_PARTS
from ..ingestion.tokens import default_counter
from . import stages
from .storage import S3Storage


def _storage() -> S3Storage:
    return S3Storage(os.environ["DATA_BUCKET"])


def handler(event: dict, context=None) -> dict:
    action = event["action"]

    if action == "resolve":
        # Pin the issue date once, so every part in this run is the same vintage.
        as_of = event.get("as_of") or latest_issue_date()
        return {
            "run_id": event.get("run_id") or str(uuid.uuid4()),
            "source_id": event.get("source_id", "ecfr-31-x"),
            "as_of": as_of,
            "parts": event.get("parts") or list(BSA_PARTS),
            "started_at": stages.now(),
            "token_counter": default_counter().name,
            "max_tokens": int(event.get("max_tokens", 512)),
        }

    if action == "fetch":
        return stages.fetch(
            _storage(), event["source_id"], event["part"], event["as_of"]
        )

    if action == "transform":
        return stages.transform(
            _storage(),
            event["source_id"],
            event["part"],
            event["as_of"],
            event["run_id"],
            max_tokens=int(event.get("max_tokens", 512)),
        )

    if action == "finalize":
        return stages.finalize(
            _storage(),
            event["source_id"],
            event["as_of"],
            event["run_id"],
            event["parts"],
            event["started_at"],
            event["token_counter"],
            max_tokens=int(event.get("max_tokens", 512)),
        )

    raise ValueError(f"unknown action: {action}")
