# ML-1 Source and Chunking Spike

| Field | Value |
|---|---|
| Task | ML-1 |
| Owner | AI/ML Engineer |
| Status | Approved |
| Started | 2026-09-27 |
| Finished | 2026-09-27 |
| Depends on | BA-2 (User stories), SWE-2 (AWS foundation) |
| Hands off to | ML-2 (Ingestion pipeline), SWE-4 (API contract) |

## Why This Comes First

Phase 1 promises an answer with the exact section behind it. That promise is
decided by the retrieval unit, not by the model. A chunk that spans two sections
cannot be cited, and a chunk that loses its paragraph path cannot be pinpointed.
So the chunk is designed and measured before any pipeline is built.

This task answers four questions and nothing else:

1. Can each source be fetched reliably, and under what licence?
2. What does the source format actually give us for citation?
3. What is the right chunk, and how big is it in practice?
4. What breaks, and how will the pipeline notice?

Running cost: nothing. Everything here runs locally against public endpoints.

## Verified Sources

Verified 27 September 2026 against live endpoints.

| Source | Endpoint | Format | Authority | Refresh | Verified |
|---|---|---|---|---|---|
| 31 CFR Chapter X | `ecfr.gov/api/versioner/v1/full/{date}/title-31.xml?subtitle=B&chapter=X&part={part}` | XML | Binding | Weekly | Fetched and parsed, 8 parts, 235 sections |
| 31 CFR bulk | `govinfo.gov/bulkdata/ECFR/title-31/ECFR-title31.xml` | XML | Binding | Weekly | 9.6 MB, last modified 11 Sep 2026 |
| FFIEC BSA/AML Manual | `bsaaml.ffiec.gov/manual/{Section}/{nn}`, PDFs at `/docs/manual/{nn}_{Section}/{nn}.pdf` | HTML, PDF | Guidance | Monthly | Listing and URL pattern confirmed. Not yet parsed |
| FinCEN advisories | `fincen.gov/resources/advisoriesbulletinsfact-sheets` | PDF | Guidance | Weekly | Listing confirmed. Not yet parsed |
| OFAC SDN | `sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML` | XML | Binding | Daily | Base path confirmed by OFAC. File not yet fetched |
| OFAC Consolidated | same base, `CONSOLIDATED.XML` | XML | Binding | Daily | As above |

All six are U.S. Government works with no copyright restriction; the eCFR XML
user guide states this for eCFR data directly.

**Not yet verified:** the OFAC export URLs. The base path and namespace come from
OFAC's own notice of 7 May 2024, but the files themselves have not been
downloaded. Treat those two rows as unconfirmed until ML-5 fetches them.

## Measured Result

From `python -m ml.spike.run_spike` over all eight BSA parts.

| Metric | Value |
|---|---|
| Token counter | tiktoken `cl100k_base` (exact) |
| eCFR issue date | 2026-09-10 |
| Parts | 1010, 1020, 1021, 1022, 1023, 1024, 1025, 1026 |
| Sections | 235 |
| Chunks | 417 |
| Chunks per section, max | 20 |
| Tokens: min / median / mean / max | 40 / 392 / 309 / 505 |
| Over budget (limit 512) | 0 |
| Chunks under 64 tokens | 62 |
| Body lines checked / not verbatim | 2389 / 0 |
| Chunks with split paragraphs | 0 |
| Chunks with unresolved labels | 1 |
| Paths impossible under the CFR cycle | 0 |
| Paragraphs with marker collisions | 574 |

Reading those numbers:

- **0 not verbatim of 2389** is the important one. Every line of every chunk
  appears character for character in its source section. The system quotes
  regulation, so this is the claim everything else rests on.
- **0 impossible paths** means all 417 pinpoints are shapes federal drafting can
  produce. See F8 for why this metric, and not the flag count, is the gate.
- **1 unresolved label** is honest residue: a path the rules inferred rather than
  derived. It is correct, but it was reached by falling back, so it carries a
  flag.
- **62 chunks under 64 tokens** is not a defect. Every one is a cross-reference
  stub ("Refer to § 1010.311 of this chapter") or `[Reserved]`. Part 1020 is
  largely pointers into Part 1010, which is why both must be ingested together.
- **574 marker collisions** of roughly 2400 paragraphs. A marker that could sit
  at two levels is the normal case in this corpus, not an edge case.

## Findings

**F1. eCFR structure is usable for citation, with one trap.** Levels are nested
`DIV1` to `DIV9` carrying `TYPE` (TITLE, SUBTITLE, CHAPTER, SUBCHAP, PART,
SUBPART, SECTION) and `N`, each followed by `HEAD`. The trap: on `DIV1`, `N` is
the *volume* number, not the title number. Read naively it yields "1 CFR" for
everything in title 31. The parser takes the title from `HEAD` instead.

**F2. eCFR returns the requested slice as the root element.** A fetch of
`?part=1020` arrives with `DIV5 TYPE="PART"` as the root, so a walker that only
reads levels from children loses the part number from every citation beneath it.
The root's own level has to seed the context.

**F3. Every level carries a `hierarchy_metadata` attribute** holding a JSON
object with an authoritative citation string, for example
`{"citation":"31 CFR Part 1020"}`. ML-2 should prefer this over assembling
citations by hand. Not yet used.

**F4. The full endpoint refuses uncompressed requests.** Without an
`Accept-Encoding` permitting compression it answers `406 Not Acceptable` with
`supportCode 11`, whatever the `Accept` header says. `urllib` sends no such
header and does not decompress. The failure reads like content negotiation, so it
sends you looking in the wrong place; the response body says the real reason.
Ingestion in Lambda needs the same treatment.

**F5. Paragraph nesting is not in the XML.** Every paragraph is a flat `<P>` with
its `(a)`, `(1)`, `(i)` marker hardcoded in the text. GPO's user guide states the
indentation "is not deducible from the XML syntax alone". Pinpoint citation
therefore depends on inferring hierarchy from the markers, which is the whole
difficulty of this task.

**F6. eCFR merges a lead-in with its first child in three distinct shapes.** All
three swallow a marker, and a swallowed marker orphans every marker below it:

| Shape | Example | Rule |
|---|---|---|
| Em dash | `(b) Filing procedures—(1) What to file.` | Split on a marker after an em dash |
| Run together | `(5)(i) Customer notice.` | Consume a run of adjacent markers |
| Heading and period | `(2) Due diligence ... indirect use. (i) A covered ...` | Split when a short heading ends in a period |

The third needs guards, or prose is destroyed: the paragraph must itself open
with a marker, the heading must be under 120 characters, and the next marker must
be the first of its level. That keeps `obtained: (1) name; (2) address` intact.
A space-separated run (`(D) (1) It provides ...`) is allowed only when the
following text is capitalised, which distinguishes it from the cross-reference
`(d) (1) through (3) of this section`.

**F7. The letter sequence continues past (z) by doubling.** 31 CFR 1010.100
defines terms through `(ff)`, and elsewhere reaches `(kkk)`. A single-letter
successor treats `(aa)` as unplaceable and nests every later definition under the
previous one. This was the single largest defect found: 145 paragraphs in the
most-retrieved section in the corpus carried wrong citations.

**F8. The flag count is not a correctness metric.** F7 was invisible to
`chunks_with_unresolved_labels`, which sat at 12 while 145 paragraphs were
confidently wrong, because the resolver had no reason to doubt itself. A flag only
catches failures the rules notice. What caught it was a different question: not
"was the resolver unsure?" but "is this output structurally possible?"

`path_follows_cycle` encodes the federal drafting cycle — letter, number, roman,
capital, then number, roman again — and rejects a path that cannot exist, such as
`(a)(1)(F)(3)(ii)`, which skips the roman level. Ambiguous markers may take
either kind, so every assignment is tried before a path is called impossible.

**ML-2 must run this as a hard gate, not a statistic.** No chunk with an
impossible pinpoint should reach the index. A wrong citation is worse than a
missing one, because it is quotable.

**F9. The `(i)` ambiguity needs lookahead, and both readings occur.** `(i)` is
both the ninth letter and the first roman numeral. After `(h)(1)`, an `(i)` may
open a roman list under `(h)(1)` or start a new paragraph `(i)`. 31 CFR 1020.315
does the latter: `(h)(1)`, `(h)(2)`, then `(i) Revocation`. Nothing in the marker
decides it; the *next* marker does. Only a roman successor (`(ii)`) implies a
list, so without one the letter sequence continues. Both readings are tested.

**F10. FinCEN offers no feed or API.** Advisories are an HTML table linking to
PDFs under `fincen.gov/system/files/`. ML-2 needs a crawl plus PDF extraction,
which is the slowest and most brittle of the four sources. Budget for it.

**F11. OFAC changed its XML namespace on 7 May 2024,** from
`http://tempuri.org/sdnList.xsd` to
`https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML`.
A parser copied from an older example silently matches nothing. This affects ML-5
rather than ML-2, since screening is deterministic and not retrieval.

## Chunking Decisions

| Decision | Choice | Why |
|---|---|---|
| Boundary | Never cross a section | The section is the unit of citation |
| Packing | Whole paragraphs, greedy | Splitting mid-paragraph cuts a requirement from its condition |
| Oversized paragraph | Split on sentence boundaries, flag the chunk | Rare, and dropping text is worse than splitting it |
| Size | 512 tokens | Fits Cohere Embed's 512 limit, keeping both embedding models available |
| Header | Citation, part, subpart, in-force date on every chunk | A retrieved chunk must say what it is without its neighbours |
| Ancestors | Name the parent paragraphs when a chunk starts inside a list | Otherwise "(3) Recordkeeping" arrives with nothing to attach to |
| Header cap | 3 ancestors, 100 characters each, 25% of the budget | 31 CFR 1010.100 produced a 451-token header before this cap |
| Join allowance | 8 tokens | Header and body tokens do not add linearly across the boundary |
| Too-small budget | Raise, do not truncate | A silently truncated chunk loses text the citation claims to contain |
| Small tail | Merge into the previous chunk when it fits | A 20-token orphan retrieves badly and dilutes the index |
| Identity | `sha256(source, citation, index)[:16]` | Stable across runs, so re-ingestion replaces rather than duplicates |

Every chunk carries `chunk_id`, `source_id`, `citation`, `pinpoint`, `heading`,
`part`, `subpart`, `authority`, `as_of`, `token_count`, and flags for split
paragraphs and unresolved labels.

`as_of` matters more than it looks. BA-2 records that the 2026 AML program rule
is proposed rather than in force, so an answer must state the date its source was
current. The field is set from the eCFR issue date, not the run date.

## Steps

### 1. Start the task

```bash
cd ~/projects/veritrace
git checkout main && git pull
git checkout -b ml/ml-1-data-spike
unzip -o ~/Downloads/veritrace-ml-1.zip
```

The archive has no top-level folder, so it unpacks into the repo root. Set
**Started** in this file and the tracker.

### 2. Set up the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements.txt
```

On a python.org build for macOS, HTTPS fails with `unable to get local issuer
certificate` until the bundled certificates are installed:

```bash
/Applications/Python\ 3.14/Install\ Certificates.command
```

### 3. Run the tests

```bash
python -m pytest ml/tests -q
```

Expect **86 passed**. These run against a schema-faithful fixture, not real
regulatory text, so they prove the parser and chunker without treating invented
text as a source.

Confirm the token counter is exact:

```bash
python -c "from ml.ingestion.tokens import default_counter; print(default_counter().name)"
```

`tiktoken cl100k_base` means exact counts. `estimated (chars/4)` means tiktoken
could not reach its vocabulary; fix that before trusting any size number, since
chunk budgets are the one thing an estimate should not decide.

### 4. Fetch the real thing

```bash
python -m ml.spike.run_spike --parts 1020
```

Caches XML under `data/raw/ecfr/`, writes `data/spike/chunks.jsonl` and
`data/spike/stats.json`. `data/` is ignored by Git.

**Verify a citation by hand.** This is the step that matters, because everything
downstream inherits it:

```bash
python -c "
import json
c=[json.loads(l) for l in open('data/spike/chunks.jsonl')]
x=[i for i in c if i['citation']=='31 CFR 1020.220'][0]
print(x['citation'], x['pinpoint'], x['token_count']); print(x['text'][:400])"
```

Open the section on eCFR and confirm the text sits at the paragraphs its
`pinpoint` names, and that the header reads `Part 1020, Subpart B`. If they
disagree, stop: the citation promise is broken and ML-2 must not be built on it.

This check found two defects the statistics could not see, an empty part number
and a paragraph path off by a level. Do not skip it.

### 5. Run the full corpus

```bash
python -m ml.spike.run_spike
```

Three numbers decide whether the design holds:

| Number | Act if |
|---|---|
| `paths_impossible_under_cfr_cycle` | Not 0. A pinpoint names a paragraph that cannot exist. It prints examples |
| `body_lines_not_verbatim` | Not 0. Chunk text no longer matches its source |
| `over_budget` | Not 0. Embedding will truncate those chunks |

`chunks_with_unresolved_labels` is informational, not a gate: see F8.
`paragraphs_with_marker_collisions` is expected to be large and is reported only
so the unresolved count can be read against it.

### 6. Record the run

Fill the **Measured Result** table above from this run, so the next chunking
change has something to be compared against.

### 7. Close ML-1

Set **Status** to `Approved` and fill in **Finished**. Commit, open a pull
request, watch both checks pass, merge, and mark ML-1 Finished and Synced in the
tracker.

## What ML-2 Inherits

| Item | State |
|---|---|
| Source registry | `ml/ingestion/sources.py`. Adding a source is a row, not a code change |
| eCFR fetcher | Done. Handles compression and the ancestor chain |
| eCFR parser | Done, 86 tests. Handles all three merge shapes, doubled letters and the `(i)` ambiguity |
| Chunker | Done. Bounded headers, enforced budgets |
| Path validator | Done. **Promote to a hard gate in the pipeline** |
| Verbatim check | Done in the spike. **Promote to a pipeline assertion** |
| Token counting | Pluggable. Swap in a Bedrock-exact counter when ML-3 fixes the embedding model |
| `hierarchy_metadata` | Not used. Prefer it over hand-assembled citations (F3) |
| FFIEC extraction | Not started. HTML or PDF, decided in ML-2 |
| FinCEN extraction | Not started. Crawl plus PDF extraction. The brittle one |
| OFAC parsing | Not started. Belongs to screening, not retrieval. Mind the 2024 namespace |

## Open Questions for ML-2

1. Does the FFIEC manual parse better from HTML or from the per-section PDFs?
   The HTML has structure; the PDFs are the citable artefact.
2. Does an advisory chunk at 512 tokens, or does its narrative structure want
   something larger with the section header repeated?
3. Do FFIEC and FinCEN share the eCFR chunk shape, or does each source need its
   own `pinpoint` scheme? The SWE-4 metadata contract depends on the answer.
4. Part 1020 is mostly cross-reference stubs into Part 1010. Should a stub chunk
   be indexed at all, resolved to its target at ingestion, or followed at query
   time?

## What This Task Taught

Worth carrying into ML-2, because it cost the most time here.

The parser reported itself 94% healthy while 145 citations in the corpus's most
important section were wrong. Self-reported uncertainty measures what the code
knows it does not know, which is not the same as correctness, and confident
errors are the dangerous kind. A validator built from the domain's own published
rules found them in one pass.

Build the validator before tuning the parser, not after. Every defect after that
point was found by asking the data one question rather than by guessing at the
next plausible shape.

## Sources

- [eCFR API and data](https://www.ecfr.gov/developers/documentation/api/v1)
- [GPO eCFR XML User Guide](https://github.com/usgpo/bulk-data/blob/main/ECFR-XML-User-Guide.md)
- [govinfo eCFR bulk data, title 31](https://www.govinfo.gov/bulkdata/ECFR/title-31)
- [Document Drafting Handbook](https://www.archives.gov/files/federal-register/write/handbook/ddh.pdf)
- [1 CFR Part 21, Preparation of Documents Subject to Codification](https://www.ecfr.gov/current/title-1/chapter-I/subchapter-E/part-21)
- [FFIEC BSA/AML Examination Manual](https://bsaaml.ffiec.gov/manual)
- [FinCEN advisories, bulletins and fact sheets](https://www.fincen.gov/resources/advisoriesbulletinsfact-sheets)
- [OFAC Sanctions List Service](https://ofac.treasury.gov/sanctions-list-service)
- [OFAC namespace change, 7 May 2024](https://ofac.treasury.gov/recent-actions/20240507_44)
