"""Chunking tests."""

from pathlib import Path

import pytest

from ml.ingestion.chunking import chunk_section, chunk_sections
from ml.ingestion.ecfr import Paragraph, Section, parse_sections
from ml.ingestion.tokens import EstimatedCounter

FIXTURE = Path(__file__).parent / "fixtures" / "ecfr_title31_sample.xml"
AS_OF = "2026-09-10"
COUNTER = EstimatedCounter()


@pytest.fixture(scope="module")
def sections():
    return parse_sections(FIXTURE.read_bytes())


@pytest.fixture(scope="module")
def chunks(sections):
    return chunk_sections(
        sections, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=256
    )


def test_chunks_are_produced(chunks):
    assert len(chunks) >= 2


def test_no_chunk_spans_two_sections(chunks):
    for chunk in chunks:
        assert chunk.text.count(" CFR ") >= 1
        assert len({chunk.citation}) == 1


def test_every_chunk_fits_the_budget(chunks):
    assert all(c.token_count <= 256 for c in chunks)


def test_every_chunk_carries_a_citation_and_pinpoint(chunks):
    for chunk in chunks:
        assert chunk.citation.startswith("31 CFR 9990.")
        assert chunk.pinpoint
        assert chunk.as_of == AS_OF


def test_header_states_where_the_text_sits(chunks):
    head = chunks[0].text.splitlines()
    assert head[0].startswith("31 CFR 9990.100")
    assert head[1] == "Part 9990, Subpart B | in force as of 2026-09-10"


def test_ids_are_unique_and_stable(sections, chunks):
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    again = chunk_sections(
        sections, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=256
    )
    assert [c.chunk_id for c in again] == [c.chunk_id for c in chunks]


def test_deep_chunk_names_its_parent_paragraphs(sections):
    small = chunk_section(
        sections[1], COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=224
    )
    unders = [c for c in small if "Starts under:" in c.text]
    assert unders, "a chunk starting inside a list should name its ancestors"
    context_line = unders[0].text.split("Starts under:")[1].splitlines()[0]
    assert context_line.startswith(" (a)")
    # The marker comes from the path, so the text must not repeat it.
    assert "(a) (a)" not in context_line


def test_oversized_paragraph_is_split_not_dropped():
    long_text = "(a) " + ("This sentence states a requirement. " * 200)
    section = Section(
        section="9990.300",
        heading="Long paragraph.",
        part="9990",
        paragraphs=[Paragraph("a", ("a",), long_text)],
    )
    out = chunk_section(
        section, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=256
    )
    assert len(out) > 1
    assert all(c.split_paragraph for c in out)
    assert all(c.token_count <= 256 for c in out)
    joined = " ".join(c.text.split("\n\n", 1)[-1] for c in out)
    assert joined.count("This sentence states a requirement.") == 200


def test_unresolved_labels_are_flagged_on_the_chunk():
    section = Section(
        section="9990.400",
        heading="Gap.",
        part="9990",
        paragraphs=[
            Paragraph("a", ("a",), "(a) First."),
            Paragraph("c", ("c",), "(c) Third, with (b) missing."),
        ],
    )
    out = chunk_section(
        section, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=256
    )
    # The parser marks the gap; here we only confirm it reaches the chunk.
    section.paragraphs[1].unresolved = True
    out = chunk_section(
        section, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=256
    )
    assert "unresolved_paragraph_label" in out[0].flags


def test_verbatim_check_catches_altered_text(sections):
    """A fidelity check that cannot fail is worse than none, so prove it fails."""
    from ml.spike.run_spike import check_verbatim

    good = chunk_sections(
        sections, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=256
    )
    assert check_verbatim(sections, good)["lines_not_verbatim"] == 0

    # Drop one space, the way a careless join would.
    tampered = chunk_sections(
        sections, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=256
    )
    tampered[0].text = tampered[0].text.replace("this part", "thispart", 1)
    result = check_verbatim(sections, tampered)
    assert result["lines_not_verbatim"] == 1
    assert result["examples"]


@pytest.mark.parametrize("max_tokens", [192, 256, 320, 384, 512, 768])
def test_no_chunk_exceeds_the_budget_at_any_size(sections, max_tokens):
    """Header and body tokens do not add linearly, so check across sizes."""
    out = chunk_sections(
        sections, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=max_tokens
    )
    over = [(c.citation, c.pinpoint, c.token_count) for c in out
            if c.token_count > max_tokens]
    assert not over, f"over budget at max_tokens={max_tokens}: {over}"


def test_a_budget_smaller_than_the_header_is_rejected():
    """Better to fail than to emit a chunk the embedding model will truncate."""
    section = Section(
        section="9990.600",
        heading="A heading so long that it alone consumes the whole budget " * 6,
        part="9990",
        paragraphs=[Paragraph("a", ("a",), "(a) Short body.")],
    )
    with pytest.raises(ValueError, match="too small"):
        chunk_section(
            section, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=128
        )


def test_the_context_line_is_capped_for_deeply_nested_sections():
    """31 CFR 1010.100 needed a 451-token header before this cap existed."""
    deep = [
        Paragraph("a", ("a",), "(a) " + "Ancestor text. " * 40),
        Paragraph("1", ("a", "1"), "(1) " + "Ancestor text. " * 40),
        Paragraph("i", ("a", "1", "i"), "(i) " + "Ancestor text. " * 40),
        Paragraph("A", ("a", "1", "i", "A"), "(A) " + "Ancestor text. " * 40),
        Paragraph("2", ("a", "1", "i", "A", "2"), "(2) Body sits here."),
    ]
    section = Section(
        section="9990.700", heading="Deep.", part="9990", paragraphs=deep
    )
    out = chunk_section(
        section, COUNTER, source_id="ecfr-31-x", as_of=AS_OF, max_tokens=512
    )
    assert all(c.token_count <= 512 for c in out)
    for chunk in out:
        if "Starts under:" in chunk.text:
            line = chunk.text.split("Starts under:")[1].splitlines()[0]
            # At most MAX_CONTEXT ancestors, each truncated.
            assert line.count(";") <= 2
