"""Run the pipeline locally, against the filesystem instead of S3.

Same stages, same gates, same output shape as the Lambda. Running this first
proves the logic before any AWS resource exists, and it is the fastest way to
tell a pipeline problem apart from a permissions problem.

  python -m ml.pipeline.local_run --parts 1020
  python -m ml.pipeline.local_run --out data/local
"""

from __future__ import annotations

import argparse
import json
import uuid

from ..ingestion.ecfr import latest_issue_date
from ..ingestion.sources import BSA_PARTS
from ..ingestion.tokens import default_counter
from . import keys, stages
from .storage import LocalStorage


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--parts", nargs="+", default=list(BSA_PARTS))
    p.add_argument("--source-id", default="ecfr-31-x")
    p.add_argument("--as-of", help="eCFR issue date, default the latest")
    p.add_argument("--out", default="data/local")
    p.add_argument("--max-tokens", type=int, default=512)
    args = p.parse_args()

    storage = LocalStorage(args.out)
    counter = default_counter()
    as_of = args.as_of or latest_issue_date()
    run_id = str(uuid.uuid4())
    started = stages.now()

    print(f"run {run_id}  as of {as_of}  counter {counter.name}")

    results = []
    for part in args.parts:
        fetched = stages.fetch(storage, args.source_id, part, as_of)
        state = "cached" if fetched["cached"] else f"{fetched['bytes']:,} bytes"
        result = stages.transform(
            storage,
            args.source_id,
            part,
            as_of,
            run_id,
            max_tokens=args.max_tokens,
            counter=counter,
        )
        results.append(result)
        print(
            f"  part {part}: {state}, {result['sections']} sections, "
            f"{result['chunks']} chunks, max {result['tokens_max']} tokens"
        )

    out = stages.finalize(
        storage,
        args.source_id,
        as_of,
        run_id,
        results,
        started,
        counter.name,
        max_tokens=args.max_tokens,
    )
    print(json.dumps(out, indent=2))
    print(f"\nmanifest: {args.out}/{keys.manifest_key(args.source_id, as_of)}")


if __name__ == "__main__":
    main()
