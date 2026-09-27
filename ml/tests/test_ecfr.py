"""Parser and label-resolution tests."""

from pathlib import Path

import pytest

from ml.ingestion.ecfr import parse_sections, resolve_labels

FIXTURE = Path(__file__).parent / "fixtures" / "ecfr_title31_sample.xml"


@pytest.fixture(scope="module")
def sections():
    return parse_sections(FIXTURE.read_bytes())


def test_finds_both_sections(sections):
    assert [s.section for s in sections] == ["9990.100", "9990.200"]


def test_citation_and_ancestors(sections):
    s = sections[0]
    assert s.citation == "31 CFR 9990.100"
    assert (s.title, s.subtitle, s.chapter, s.part, s.subpart) == (
        "31",
        "B",
        "X",
        "9990",
        "B",
    )


def test_heading_strips_the_section_number(sections):
    assert sections[0].heading == "Definitions for fixture purposes."


def test_amendment_note_captured(sections):
    assert sections[0].amendment_note.startswith("[80 FR 11111")


def test_lead_in_paragraph_has_no_marker(sections):
    first = sections[0].paragraphs[0]
    assert first.label == ""
    assert first.text.startswith("For purposes of this part")


def test_top_level_i_is_a_letter_not_a_roman_numeral(sections):
    """(i) after (h) is the ninth letter, so it stays at the top level."""
    labels = [p.path for p in sections[0].paragraphs if p.label]
    assert labels[-1] == ("i",)
    assert all(len(path) == 1 for path in labels)


def test_nested_paths(sections):
    paths = {p.label: p.path for p in sections[1].paragraphs if p.label}
    assert paths["1"] == ("a", "1")
    assert paths["i"] == ("a", "2", "i")
    assert paths["A"] == ("a", "2", "i", "A")
    assert paths["3"] == ("a", "3")
    assert paths["b"] == ("b",)


def test_unmarked_text_inherits_the_previous_path(sections):
    # Every paragraph after the first marker has a path.
    assert all(p.path for p in sections[1].paragraphs)


@pytest.mark.parametrize(
    "markers, expected",
    [
        (["a", "b", "c"], [("a",), ("b",), ("c",)]),
        (["a", "1", "2", "b"], [("a",), ("a", "1"), ("a", "2"), ("b",)]),
        (
            ["a", "1", "i", "ii", "2"],
            [("a",), ("a", "1"), ("a", "1", "i"), ("a", "1", "ii"), ("a", "2")],
        ),
        # (i) opens a roman level because (1) is already open above it.
        (["1", "i", "ii"], [("1",), ("1", "i"), ("1", "ii")]),
        # Deep close-out: (A)(B) then back to (2).
        (
            ["a", "1", "i", "A", "B", "2"],
            [
                ("a",),
                ("a", "1"),
                ("a", "1", "i"),
                ("a", "1", "i", "A"),
                ("a", "1", "i", "B"),
                ("a", "2"),
            ],
        ),
    ],
)
def test_resolve_labels(markers, expected):
    assert [path for path, _, _ in resolve_labels(markers)] == expected


def test_gap_is_marked_unresolved():
    # (c) straight after (a) cannot be a successor, so its path is a guess.
    _, unresolved, _ = resolve_labels(["a", "c"])[1]
    assert unresolved is True


def test_collision_resolved_by_context_is_not_unresolved():
    # (i) after (h) is the ninth letter: the marker collides, the rules cope.
    path, unresolved, collided = resolve_labels(list("abcdefghi"))[-1]
    assert path == ("i",)
    assert collided is True
    assert unresolved is False


def test_get_decompresses_gzip_and_passes_plain_through(monkeypatch):
    """eCFR requires Accept-Encoding, so responses arrive gzipped."""
    import gzip
    import io
    import urllib.request

    from ml.ingestion import ecfr

    sent = {}

    def fake_urlopen(req, timeout=0):
        sent["headers"] = req.headers
        return io.BytesIO(sent["body"])

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    sent["body"] = gzip.compress(b"<ECFR/>")
    assert ecfr._get("https://example.test", 1) == b"<ECFR/>"
    assert sent["headers"]["Accept-encoding"] == "gzip"

    sent["body"] = b"<ECFR/>"
    assert ecfr._get("https://example.test", 1) == b"<ECFR/>"


@pytest.mark.parametrize(
    "markers",
    [
        ["a", "ii", "b"],  # crashed: level kept kind "letter" while holding "ii"
        ["a", "1", "iii", "2"],
        ["A", "IV", "B"],
        ["1", "abc", "2"],
        ["a", "27", "b"],
        ["z", "aa", "1"],
        ["i", "v", "x", "a"],
    ],
)
def test_resolver_never_raises_on_odd_sequences(markers):
    out = resolve_labels(markers)
    assert len(out) == len(markers)
    assert all(path for path, _, _ in out)


def test_leadin_split_recovers_a_swallowed_marker():
    """eCFR puts a lead-in and its first child in one <P>, joined by an em dash."""
    from ml.ingestion.ecfr import LEADIN

    text = "(b) Filing procedures—(1) What to file. A report shall be filed."
    assert LEADIN.split(text) == [
        "(b) Filing procedures—",
        "(1) What to file. A report shall be filed.",
    ]


def test_leadin_split_leaves_inline_enumerations_alone():
    """A marker after a period or colon is usually prose, not a new paragraph."""
    from ml.ingestion.ecfr import LEADIN

    text = "The CIP must specify the information obtained: (1) name; (2) address."
    assert LEADIN.split(text) == [text]


def test_fallback_descends_on_a_different_kind_and_keeps_ancestors():
    # (a) then (2): the (1) was swallowed by a merged lead-in. Keep the (a).
    assert [p for p, _, _ in resolve_labels(["a", "2"])] == [("a",), ("a", "2")]


def test_fallback_stays_on_the_same_kind():
    # (a) then (c): a gap between siblings, not a deeper level.
    assert [p for p, _, _ in resolve_labels(["a", "c"])] == [("a",), ("c",)]


def test_real_1020_220_sequence_resolves_without_guesses():
    """Federal drafting cycles (a)(1)(i)(A)(1)(i), so kinds recur at depth.

    Marker sequence taken from 31 CFR 1020.220 as published.
    """
    seq = ["a", "1", "2", "i", "A", "1", "2", "3", "i", "ii", "4", "i", "ii",
           "B", "C", "ii", "A", "1", "2", "B", "1", "2", "C", "iii"]
    out = resolve_labels(seq)
    paths = [p for p, _, _ in out]

    assert not any(u for _, u, _ in out), "no marker should need the fallback"
    assert paths[4] == ("a", "2", "i", "A")
    assert paths[5] == ("a", "2", "i", "A", "1")
    assert paths[10] == ("a", "2", "i", "A", "4")
    assert paths[13] == ("a", "2", "i", "B")
    assert paths[15] == ("a", "2", "ii")
    assert paths[-1] == ("a", "2", "iii")


def test_a_level_cannot_repeat_its_immediate_parent_kind():
    # (1) directly inside (1) is not a thing; it stays a sibling.
    assert [p for p, _, _ in resolve_labels(["a", "1", "2"])] == [
        ("a",),
        ("a", "1"),
        ("a", "2"),
    ]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("(a) Foo bar", ["a"]),
        ("(5)(i) Customer notice.", ["5", "i"]),          # seen in 1020.220
        ("(a)(1)(i) Deep opener", ["a", "1", "i"]),
        ("(d) (1) through (3) of this section", ["d"]),   # a space ends the run
        ("(b) [Reserved]", ["b"]),
        ("Plain lead-in text", []),
    ],
)
def test_leading_markers(text, expected):
    from ml.ingestion.ecfr import leading_markers

    assert leading_markers(text) == expected


def test_marker_run_places_the_text_at_the_deepest_marker():
    """"(5)(i) ..." must yield (a)(5)(i), not (a)(5)."""
    from ml.ingestion.ecfr import parse_sections

    xml = b"""<ECFR><DIV1 N="1" TYPE="TITLE"><HEAD>Title 31\xe2\x80\x94Money</HEAD>
      <DIV5 N="9990" TYPE="PART"><HEAD>PART 9990</HEAD>
      <DIV8 N="&#167; 9990.500" TYPE="SECTION"><HEAD>&#167; 9990.500   Runs.</HEAD>
        <P>(a) First.</P>
        <P>(5)(i) Customer notice. Body text here.</P>
        <P>(ii) Adequate notice. More body text.</P>
      </DIV8></DIV5></DIV1></ECFR>"""

    paras = parse_sections(xml)[0].paragraphs
    assert paras[1].path == ("a", "5", "i")
    assert paras[1].label == "i"
    assert paras[2].path == ("a", "5", "ii")
    assert not paras[2].unresolved


@pytest.mark.parametrize(
    "text, expected",
    [
        # Heading ending in a period, then the first child. Seen in 1020.315.
        (
            "(2) Special rules. (i) A bank is not required to file.",
            ["(2) Special rules.", "(i) A bank is not required to file."],
        ),
        ("(a) General. (1) Every bank shall file.",
         ["(a) General.", "(1) Every bank shall file."]),
        # Em dash form.
        ("(b) Filing procedures—(1) What to file.",
         ["(b) Filing procedures—", "(1) What to file."]),
        # Must NOT split: a colon, and an enumeration inside prose.
        ("(A) In general. The CIP must specify what is obtained: (1) name; (2) address.",
         ["(A) In general. The CIP must specify what is obtained: (1) name; (2) address."]),
        # Must NOT split: the paragraph does not open with a marker.
        ("The bank must retain the record. (1) applies only to intermediaries.",
         ["The bank must retain the record. (1) applies only to intermediaries."]),
        # Must NOT split: (2) is not the first marker of a level.
        ("(a) This applies to banks. (2) Later text.",
         ["(a) This applies to banks. (2) Later text."]),
        # Must NOT split: a run already consumed both markers.
        ("(5)(i) Customer notice. Body text follows.",
         ["(5)(i) Customer notice. Body text follows."]),
        ("(1) The name and address of the beneficiary;",
         ["(1) The name and address of the beneficiary;"]),
    ],
)
def test_split_leadins(text, expected):
    from ml.ingestion.ecfr import split_leadins

    assert split_leadins(text) == expected


@pytest.mark.parametrize(
    "path, valid",
    [
        (("a",), True),
        (("a", "2"), True),
        (("a", "2", "i"), True),
        (("a", "2", "i", "A"), True),
        (("a", "2", "i", "A", "1"), True),
        (("a", "2", "i", "A", "1", "i"), True),
        (("h", "2"), True),
        (("a", "1", "F", "3", "ii"), False),  # skips the roman level
        (("g", "ii", "2"), False),            # roman directly under a letter
        (("c", "2", "B", "ii"), False),       # roman inside a capital
        (("a", "b"), False),                  # two letter levels in a row
    ],
)
def test_path_follows_cycle(path, valid):
    """Federal drafting cycles letter, number, roman, capital, number, roman."""
    from ml.ingestion.ecfr import path_follows_cycle

    assert path_follows_cycle(path) is valid


def test_letter_sequence_continues_past_z_by_doubling():
    """31 CFR 1010.100 defines terms through (ff), not stopping at (z)."""
    from ml.ingestion.ecfr import _alpha_index, _alpha_marker

    assert _alpha_index("z") == 25
    assert _alpha_marker(26) == "aa"
    assert _alpha_marker(_alpha_index("aa") + 1) == "bb"
    assert _alpha_marker(_alpha_index("z") + 1) == "aa"
    assert _alpha_index("iv") is None  # mixed letters are not a doubled marker


def test_definitions_run_stays_at_the_top_level():
    """(aa) after (z) is a sibling, not a child. This mangled 1010.100 before."""
    seq = [chr(ord("a") + i) for i in range(26)] + ["aa", "bb", "cc", "dd", "ee", "ff"]
    out = resolve_labels(seq)

    assert not any(u for _, u, _ in out)
    assert all(len(p) == 1 for p, _, _ in out)
    assert [p[0] for p, _, _ in out] == seq


def test_doubled_letter_nested_under_a_letter_is_impossible():
    from ml.ingestion.ecfr import path_follows_cycle

    assert path_follows_cycle(("dd",)) is True
    assert path_follows_cycle(("cc", "dd")) is False


@pytest.mark.parametrize(
    "text, expected",
    [
        # 31 CFR 1010.100(ff)(4)(iii)(D): a space separates the run.
        ("(D) (1) It provides prepaid access solely to:", ["D", "1"]),
        # A cross-reference continues in lower case, so it is not a run.
        ("(d) (1) through (3) of this section are reserved", ["d"]),
        ("(d) (1) and (2) of this paragraph apply", ["d"]),
        # A spaced run is only allowed for a first marker.
        ("(D) (2) Not a first marker", ["D"]),
        ("(5)(i) Customer notice.", ["5", "i"]),
    ],
)
def test_spaced_marker_runs(text, expected):
    from ml.ingestion.ecfr import leading_markers

    assert leading_markers(text) == expected


def test_long_heading_still_splits():
    """31 CFR 1010.653(b)(2) has a 65-character heading; the old cap was 60."""
    from ml.ingestion.ecfr import split_leadins

    text = (
        "(2) Due diligence of correspondent accounts to prohibit indirect use. "
        "(i) A covered financial institution shall establish a due diligence program."
    )
    assert split_leadins(text) == [
        "(2) Due diligence of correspondent accounts to prohibit indirect use.",
        "(i) A covered financial institution shall establish a due diligence program.",
    ]


@pytest.mark.parametrize(
    "markers, expected",
    [
        # 31 CFR 1020.315: (h)(1), (h)(2), then (i) Revocation is a new paragraph.
        (["h", "1", "2", "i", "1", "2"],
         [("h",), ("h", "1"), ("h", "2"), ("i",), ("i", "1"), ("i", "2")]),
        # The same (i) after (h)(1), but followed by (ii): a roman list.
        (["h", "1", "i", "ii", "iii"],
         [("h",), ("h", "1"), ("h", "1", "i"), ("h", "1", "ii"), ("h", "1", "iii")]),
        # A letter run continuing past (i).
        (["h", "1", "i", "j"], [("h",), ("h", "1"), ("i",), ("j",)]),
        # No ancestor letter to continue, so the roman reading stands.
        (["a", "1", "i", "ii"],
         [("a",), ("a", "1"), ("a", "1", "i"), ("a", "1", "ii")]),
    ],
)
def test_lookahead_decides_letter_versus_roman(markers, expected):
    """(i) is the ninth letter or the first roman; only what follows tells."""
    assert [p for p, _, _ in resolve_labels(markers)] == expected
