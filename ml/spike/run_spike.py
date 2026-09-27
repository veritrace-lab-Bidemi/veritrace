"""ML-1 spike: fetch 31 CFR Chapter X, parse it, chunk it, report the numbers.

  python -m ml.spike.run_spike                 # live fetch, all BSA parts
  python -m ml.spike.run_spike --parts 1020    # one part
  python -m ml.spike.run_spike --offline       # the test fixture, no network

Writes chunks.jsonl and stats.json so the numbers can be checked, not trusted.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict
from pathlib import Path

from ml.ingestion import ecfr
from ml.ingestion.chunking import chunk_sections
from ml.ingestion.sources import BSA_PARTS
from ml.ingestion.tokens import default_counter

FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/ecfr_title31_sample.xml"


def load(args) -> tuple[list, str]:
    """Return parsed sections and the date the text is current as of."""
    if args.offline:
        return ecfr.parse_sections(FIXTURE.read_bytes()), "fixture"

    date = args.date or ecfr.latest_issue_date()
    cache = Path(args.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    sections = []
    for part in args.parts:
        path = cache / f"title31-part{part}-{date}.xml"
        if not path.exists():
            print(f"fetching part {part} ...", flush=True)
            path.write_bytes(ecfr.fetch_part(part, date))
        sections.extend(ecfr.parse_sections(path.read_bytes()))
    return sections, date


def check_verbatim(sections, chunks) -> dict:
    """Every line of chunk body text must appear in its source section exactly.

    The system quotes regulation, so a chunk that paraphrases or drops a
    character is worse than a chunk that is missing. This proves it does not
    happen rather than assuming it.
    """
    source = {s.citation: s.text for s in sections}
    checked = bad = 0
    examples: list[str] = []
    for chunk in chunks:
        body = chunk.text.split("\n\n", 1)[-1]
        for line in body.splitlines():
            if not line.strip():
                continue
            checked += 1
            if line not in source.get(chunk.citation, ""):
                bad += 1
                if len(examples) < 3:
                    examples.append(f"{chunk.citation} {chunk.pinpoint}: {line[:90]}")
    return {"lines_checked": checked, "lines_not_verbatim": bad, "examples": examples}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="eCFR issue date, default the latest")
    p.add_argument("--parts", nargs="+", default=list(BSA_PARTS))
    p.add_argument("--cache-dir", default="data/raw/ecfr")
    p.add_argument("--out-dir", default="data/spike")
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--offline", action="store_true")
    args = p.parse_args()

    counter = default_counter()
    sections, date = load(args)
    chunks = chunk_sections(
        sections,
        counter,
        source_id="ecfr-31-x",
        as_of=date,
        max_tokens=args.max_tokens,
    )

    verbatim = check_verbatim(sections, chunks)
    impossible = [
        (s.citation, p.path, p.text[:70])
        for s in sections
        for p in s.paragraphs
        if p.path and not ecfr.path_follows_cycle(p.path)
    ]
    sizes = [c.token_count for c in chunks]
    per_section = [len([c for c in chunks if c.citation == s.citation]) for s in sections]
    flagged = [c for c in chunks if c.flags]
    split = [c for c in chunks if c.split_paragraph]

    stats = {
        "token_counter": counter.name,
        "as_of": date,
        "parts": args.parts if not args.offline else ["fixture"],
        "max_tokens": args.max_tokens,
        "sections": len(sections),
        "chunks": len(chunks),
        "chunks_per_section_max": max(per_section, default=0),
        "tokens_min": min(sizes, default=0),
        "tokens_median": round(statistics.median(sizes)) if sizes else 0,
        "tokens_mean": round(statistics.fmean(sizes)) if sizes else 0,
        "tokens_max": max(sizes, default=0),
        "over_budget": sum(1 for s in sizes if s > args.max_tokens),
        "under_64_tokens": sum(1 for s in sizes if s < 64),
        "body_lines_checked": verbatim["lines_checked"],
        "body_lines_not_verbatim": verbatim["lines_not_verbatim"],
        "chunks_with_split_paragraphs": len(split),
        "chunks_with_unresolved_labels": len(flagged),
        "paths_impossible_under_cfr_cycle": len(impossible),
        "paragraphs_with_marker_collisions": sum(
            1 for s in sections for p in s.paragraphs if p.collided
        ),
    }

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "chunks.jsonl").open("w") as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk)) + "\n")
    (out / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")

    width = max(len(k) for k in stats)
    for key, value in stats.items():
        print(f"{key:<{width}}  {value}")
    for example in verbatim["examples"]:
        print(f"  not verbatim: {example}")
    for citation, path, text in impossible[:10]:
        pinpoint = "".join(f"({x})" for x in path)
        print(f"  impossible path: {citation} {pinpoint}  {text}")
    print(f"\nwrote {out/'chunks.jsonl'} and {out/'stats.json'}")


if __name__ == "__main__":
    main()
