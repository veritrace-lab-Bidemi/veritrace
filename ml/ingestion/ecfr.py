"""Fetch and parse 31 CFR from eCFR XML.

Structure comes from the GPO eCFR XML User Guide: nested DIV1..DIV9 elements
carry TYPE (TITLE, SUBTITLE, CHAPTER, SUBCHAP, PART, SUBPART, SECTION) and N
(the number). HEAD holds the heading.

Paragraph nesting is not in the XML. Every paragraph is a flat <P> whose
numbering is hardcoded in the text, so the (a)(1)(i) hierarchy has to be
inferred from the leading marker. resolve_labels does that.
"""

from __future__ import annotations

import gzip
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

ECFR_FULL = "https://www.ecfr.gov/api/versioner/v1/full/{date}/title-{title}.xml"
ECFR_TITLES = "https://www.ecfr.gov/api/versioner/v1/titles.json"

# eCFR asks callers to identify themselves.
USER_AGENT = "veritrace-spike/0.1 (github.com/veritrace-lab-Bidemi/veritrace)"

# DIV TYPE value -> field name we keep for citations.
LEVELS = {
    "TITLE": "title",
    "SUBTITLE": "subtitle",
    "CHAPTER": "chapter",
    "SUBCHAP": "subchapter",
    "PART": "part",
    "SUBPART": "subpart",
    "SUBJGRP": "subjgrp",
}

# Paragraph-bearing elements. The user guide lists P plus close relatives.
PARA_TAGS = {"P", "PSPACE", "FP", "P-1", "P-2", "P-3"}

MARKER = re.compile(r"^\(([A-Za-z0-9]{1,5})\)\s*")

# A heading-style lead-in often runs into its first child inside one <P>:
#   "(b) Filing procedures—(1) What to file. A suspicious transaction ..."
# Splitting on a marker that follows an em dash recovers the swallowed marker.
# Only the em dash qualifies; a marker after a period is frequently an inline
# enumeration ("including: (1) name; (2) address") and must not be split.
LEADIN = re.compile(r"(?<=—)\s*(?=\([A-Za-z0-9]{1,5}\)\s)")

# A paragraph can also open with several markers run together, with no
# separator at all: "(5)(i) Customer notice." Both belong in the sequence, and
# the text belongs to the last one. Anchored at the start, so an inline
# enumeration later in the sentence is never touched.
# No space is allowed between markers in a run: a space means the run ended.
# That keeps "(d) (1) through (3) of this section" from reading as two markers.
ADJACENT = re.compile(r"^\(([A-Za-z0-9]{1,5})\)")

# The third shape: a short italic heading ends in a period and the first child
# follows in the same <P>: "(2) Special rules. (i) A bank is not required ..."
# Three guards keep prose intact: the paragraph must itself open with a marker,
# the heading must be short, and the following marker must be the first of a
# level. So "obtained: (1) name; (2) address" is untouched, both because a colon
# is not a period and because that text is not a heading.
HEADING = re.compile(r"^(.{1,120}?\.\s+)(?=\((?:1|i|A|a)\)\s)")

# A run can also be separated by a single space: "(D) (1) It provides ...".
# Allowed only for a first marker followed by capitalised text, which keeps
# "(d) (1) through (3) of this section" from reading as a run: a cross-reference
# continues in lower case, a real paragraph starts a new sentence.
SPACED = re.compile(r"^\s\((1|i|A|a)\)\s+(?=[A-Z(])")
ROMAN = re.compile(r"^(?:x{0,3})(?:ix|iv|v?i{0,3})$")

LOWER_ALPHA, ARABIC, LOWER_ROMAN, UPPER_ALPHA = "a", "1", "i", "A"


@dataclass
class Paragraph:
    """One paragraph with its inferred position in the (a)(1)(i) hierarchy."""

    label: str  # the marker alone, e.g. "2"
    path: tuple[str, ...]  # full path, e.g. ("a", "2", "i")
    text: str
    unresolved: bool = False  # no rule placed it; the path is a guess
    collided: bool = False  # marker fits two levels, context decided which


@dataclass
class Section:
    """One CFR section and its paragraphs."""

    section: str  # "1020.220"
    heading: str
    part: str
    subpart: str = ""
    subchapter: str = ""
    chapter: str = ""
    subtitle: str = ""
    title: str = "31"
    paragraphs: list[Paragraph] = field(default_factory=list)
    amendment_note: str = ""

    @property
    def citation(self) -> str:
        return f"{self.title} CFR {self.section}"

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)


def _get(url: str, timeout: int) -> bytes:
    """GET with compression. eCFR answers 406 without an Accept-Encoding that
    permits it, and urllib does not decompress on its own."""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def latest_issue_date(title: str = "31") -> str:
    """Date eCFR last issued this title. Use it so fetches are reproducible."""
    import json

    data = json.loads(_get(ECFR_TITLES, 60))
    for t in data["titles"]:
        if str(t["number"]) == title:
            return t["latest_issue_date"]
    raise KeyError(f"title {title} not in titles.json")


def part_url(
    part: str, date: str, chapter: str = "X", subtitle: str = "B", title: str = "31"
) -> str:
    """eCFR needs the full ancestor chain, not just the part."""
    query = urllib.parse.urlencode(
        {"subtitle": subtitle, "chapter": chapter, "part": part}
    )
    return f"{ECFR_FULL.format(date=date, title=title)}?{query}"


def fetch_part(part: str, date: str, **kw) -> bytes:
    """Download one part's XML."""
    return _get(part_url(part, date, **kw), 180)


def _alpha_index(marker: str) -> int | None:
    """Position in the letter sequence a, b ... z, aa, bb ... zz, aaa ...

    31 CFR 1010.100 runs to (ff), so the sequence continues past (z) by doubling
    the letter rather than counting in base 26.
    """
    if not marker.isalpha() or len(set(marker.lower())) != 1:
        return None
    return (len(marker) - 1) * 26 + (ord(marker[0].lower()) - ord("a"))


def _alpha_marker(index: int, upper: bool = False) -> str:
    repeats, letter = divmod(index, 26)
    marker = chr(ord("a") + letter) * (repeats + 1)
    return marker.upper() if upper else marker


def _classify(marker: str) -> set[str]:
    """Which hierarchy levels a marker could belong to."""
    if marker.isdigit():
        return {ARABIC}
    if marker.isupper():
        return {UPPER_ALPHA}
    kinds = set()
    if _alpha_index(marker) is not None:
        kinds.add(LOWER_ALPHA)
    if marker and ROMAN.match(marker):
        kinds.add(LOWER_ROMAN)
    return kinds or {LOWER_ALPHA}


ROMAN_ORDER = (
    "i ii iii iv v vi vii viii ix x xi xii xiii xiv xv xvi xvii xviii xix xx "
    "xxi xxii xxiii xxiv xxv xxvi xxvii xxviii xxix xxx"
).split()


def _successor(kind: str, previous: str) -> str:
    """Marker that should follow `previous` at this level.

    Returns "" when `previous` is not a valid marker for `kind`. That happens
    after a fallback, and an empty answer simply means no rule matches rather
    than an error.
    """
    if kind == ARABIC:
        return str(int(previous) + 1) if previous.isdigit() else ""
    if kind in (LOWER_ALPHA, UPPER_ALPHA):
        index = _alpha_index(previous)
        return "" if index is None else _alpha_marker(index + 1, kind == UPPER_ALPHA)
    if previous not in ROMAN_ORDER:
        return ""
    i = ROMAN_ORDER.index(previous)
    return ROMAN_ORDER[i + 1] if i + 1 < len(ROMAN_ORDER) else ""


def _is_first(kind: str, marker: str) -> bool:
    return marker == {ARABIC: "1", LOWER_ALPHA: "a", LOWER_ROMAN: "i", UPPER_ALPHA: "A"}[kind]


def _ancestor_successor(
    stack: list[tuple[str, str]], marker: str, kinds: set[str]
) -> int | None:
    """Depth of the nearest ancestor level this marker continues, if any."""
    for depth in range(len(stack) - 2, -1, -1):
        kind, previous = stack[depth]
        if kind in kinds and marker == _successor(kind, previous):
            return depth
    return None


def resolve_labels(markers: list[str]) -> list[tuple[tuple[str, ...], bool, bool]]:
    """Turn a flat marker sequence into paths.

    Rules, applied in order:
      1. Continues the current level if it is that level's next marker.
      2. Opens a deeper level if it is a first marker (1, a, i or A).
      3. Closes back to an ancestor whose next marker it is.
      4. Otherwise stays at the current level and is marked unresolved.

    Returns (path, unresolved, collided) per marker. "(i)" collides: ninth
    lowercase letter or first roman numeral. A collision resolved by rules 1 to
    3 is reliable; only rule 4 means the path is a guess.
    """
    stack: list[tuple[str, str]] = []  # (kind, last marker at that level)
    out: list[tuple[tuple[str, ...], bool, bool]] = []

    for index, marker in enumerate(markers):
        following = markers[index + 1] if index + 1 < len(markers) else None
        kinds = _classify(marker)
        placed = False
        collided = len(kinds) > 1
        unresolved = False

        # 1. sibling at the current level
        if stack:
            kind, previous = stack[-1]
            if kind in kinds and marker == _successor(kind, previous):
                stack[-1] = (kind, marker)
                placed = True

        # 1b. A colliding marker such as (i) may continue an ancestor letter
        #     sequence -- 31 CFR 1020.315 runs (h) then (i) Revocation -- or open
        #     a roman list. Only a roman successor next implies a list, so
        #     without one, closing back to the letter level wins. Checked before
        #     rule 2, which would otherwise always descend.
        if not placed and collided:
            depth = _ancestor_successor(stack, marker, kinds)
            if depth is not None and following != _successor(LOWER_ROMAN, marker):
                kind = stack[depth][0]
                del stack[depth + 1 :]
                stack[depth] = (kind, marker)
                placed = True

        # 2. first marker of a deeper level. Federal drafting cycles through
        #    (a)(1)(i)(A)(1)(i), so arabic and roman levels legitimately recur
        #    at depth. The only bar is repeating the immediate parent's kind.
        if not placed:
            for kind in (ARABIC, LOWER_ROMAN, UPPER_ALPHA, LOWER_ALPHA):
                if kind in kinds and _is_first(kind, marker):
                    if not stack or kind != stack[-1][0]:
                        stack.append((kind, marker))
                        placed = True
                        break

        # 3. back out to an ancestor this marker continues
        if not placed:
            depth = _ancestor_successor(stack, marker, kinds)
            if depth is not None:
                kind = stack[depth][0]
                del stack[depth + 1 :]
                stack[depth] = (kind, marker)
                placed = True

        # 4. no rule fits. A marker of a different kind than the current level
        #    means a deeper level whose first markers are missing, so descend
        #    and keep the ancestors. The same kind means a gap between
        #    siblings, so stay. Either way the path is a guess.
        if not placed:
            kind = next(iter(kinds))
            if stack and kind not in {k for k, _ in stack}:
                stack.append((kind, marker))
            elif stack:
                stack[-1] = (kind, marker)
            else:
                stack.append((kind, marker))
            unresolved = True

        out.append((tuple(m for _, m in stack), unresolved, collided))

    return out


def _title_number(el: ET.Element) -> str:
    head = el.find("HEAD")
    if head is None:
        return ""
    m = re.search(r"Title\s+(\d+[A-Z]?)", _element_text(head))
    return m.group(1) if m else ""


def leading_markers(text: str) -> list[str]:
    """Every marker a paragraph opens with, in order.

    "(a) Foo"      -> ["a"]
    "(5)(i) Foo"   -> ["5", "i"]
    "(a)(1)(i) Foo"-> ["a", "1", "i"]
    "Plain text"   -> []
    """
    return _split_markers(text)[0]


def _split_markers(text: str) -> tuple[list[str], str]:
    """The opening marker run and the text after it."""
    markers: list[str] = []
    rest = text
    while True:
        m = ADJACENT.match(rest)
        if not m and markers:
            m = SPACED.match(rest)
        if not m:
            break
        markers.append(m.group(1))
        rest = rest[m.end() :]
    return markers, rest.lstrip()


def split_leadins(text: str) -> list[str]:
    """Break one <P> into the paragraphs it actually contains.

    eCFR merges a lead-in with its first child in two ways, both handled here:
    an em dash ("(b) Filing procedures—(1) What to file") and a short heading
    ending in a period ("(2) Special rules. (i) A bank is not required").
    """
    out: list[str] = []
    for part in LEADIN.split(text):
        markers, rest = _split_markers(part)
        m = HEADING.match(rest) if markers else None
        if m:
            cut = len(part) - len(rest) + m.end()
            out.append(part[:cut].rstrip())
            out.append(part[cut:])
        else:
            out.append(part)
    return [p for p in out if p.strip()]


CYCLE = {
    LOWER_ALPHA: ARABIC,
    ARABIC: LOWER_ROMAN,
    LOWER_ROMAN: UPPER_ALPHA,
    UPPER_ALPHA: ARABIC,
}


def path_follows_cycle(path: tuple[str, ...]) -> bool:
    """Whether a path is a shape federal drafting can actually produce.

    Levels cycle letter, number, roman, capital, then number, roman, capital
    again. A path like (a)(1)(F)(3)(ii) skips the roman level and so cannot
    exist, which makes it detectably wrong rather than merely uncertain.
    Ambiguous markers may take either kind, so every assignment is tried.
    """

    def walk(i: int, previous: str | None) -> bool:
        if i == len(path):
            return True
        for kind in _classify(path[i]):
            if previous is None or CYCLE[previous] == kind:
                if walk(i + 1, kind):
                    return True
        return False

    return walk(0, None)


def _element_text(el: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def parse_sections(xml_bytes: bytes) -> list[Section]:
    """Walk the DIV tree and return every section it contains."""
    root = ET.fromstring(xml_bytes)
    sections: list[Section] = []

    def walk(el: ET.Element, ctx: dict[str, str]) -> None:
        for child in el:
            if not child.tag.startswith("DIV"):
                continue
            kind = (child.get("TYPE") or "").strip()
            number = (child.get("N") or "").strip()
            if kind == "TITLE":
                # On DIV1, N is the volume number. The title number is in HEAD.
                number = _title_number(child) or number
            if kind == "SECTION":
                sections.append(_build_section(child, ctx, number))
                continue
            if kind in LEVELS:
                walk(child, {**ctx, LEVELS[kind]: number})
            else:
                walk(child, ctx)

    # eCFR returns the requested slice as the root element, so a fetch of
    # ?part=1020 arrives with DIV5 PART as the root. Its own level has to seed
    # the context or the part number is lost from every citation below it.
    ctx: dict[str, str] = {}
    kind = (root.get("TYPE") or "").strip()
    if kind == "SECTION":
        return [_build_section(root, {}, root.get("N", ""))]
    if kind in LEVELS:
        number = (
            _title_number(root) if kind == "TITLE" else (root.get("N") or "").strip()
        )
        ctx[LEVELS[kind]] = number

    walk(root, ctx)
    return sections


def _build_section(el: ET.Element, ctx: dict[str, str], number: str) -> Section:
    heading_el = el.find("HEAD")
    heading = _element_text(heading_el) if heading_el is not None else ""
    # HEAD repeats the number: "§ 1020.220   Customer identification ..."
    heading = re.sub(r"^§+\s*[\d.]+\s*", "", heading).strip()

    section_num = number.replace("§", "").strip()

    raw: list[str] = []
    note = ""
    for child in el:
        if child.tag in PARA_TAGS:
            text = _element_text(child)
            if text:
                raw.extend(split_leadins(text))
        elif child.tag == "CITA":
            note = _element_text(child)

    runs = [leading_markers(t) for t in raw]
    resolved = resolve_labels([m for run in runs for m in run])

    paragraphs: list[Paragraph] = []
    cursor = 0
    last_path: tuple[str, ...] = ()
    for text, run in zip(raw, runs):
        if not run:
            # Unmarked text inherits the path of whatever came before it.
            paragraphs.append(Paragraph("", last_path, text))
            continue
        # The text belongs to the deepest marker in the run; the earlier ones
        # only exist to place it, so their uncertainty carries over to it.
        placed = resolved[cursor : cursor + len(run)]
        cursor += len(run)
        path = placed[-1][0]
        last_path = path
        paragraphs.append(
            Paragraph(
                run[-1],
                path,
                text,
                any(u for _, u, _ in placed),
                any(c for _, _, c in placed),
            )
        )

    return Section(
        section=section_num,
        heading=heading,
        part=ctx.get("part", ""),
        subpart=ctx.get("subpart", ""),
        subchapter=ctx.get("subchapter", ""),
        chapter=ctx.get("chapter", ""),
        subtitle=ctx.get("subtitle", ""),
        title=ctx.get("title", "31"),
        paragraphs=paragraphs,
        amendment_note=note,
    )
