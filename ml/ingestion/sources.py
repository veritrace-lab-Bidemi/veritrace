"""Registry of approved knowledge sources.

Every chunk Veritrace retrieves traces back to one entry here. Adding a source
means adding a row, not changing pipeline code.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    """One approved source of regulatory text."""

    id: str
    name: str
    publisher: str
    url: str
    fmt: str  # xml, pdf, html, csv
    authority: str  # binding, guidance, reference
    refresh: str  # how often the pipeline should re-fetch
    license: str
    notes: str = ""
    parts: tuple[str, ...] = field(default_factory=tuple)


# 31 CFR Chapter X parts that carry the BSA rules Phase 1 answers from.
BSA_PARTS = ("1010", "1020", "1021", "1022", "1023", "1024", "1025", "1026")

SOURCES: tuple[Source, ...] = (
    Source(
        id="ecfr-31-x",
        name="31 CFR Chapter X, Financial Crimes Enforcement Network",
        publisher="Office of the Federal Register",
        url="https://www.ecfr.gov/api/versioner/v1/full/{date}/title-31.xml?chapter=X&part={part}",
        fmt="xml",
        authority="binding",
        refresh="weekly",
        license="US Government work, not subject to copyright",
        notes="Bulk alternative: https://www.govinfo.gov/bulkdata/ECFR/title-31/ECFR-title31.xml",
        parts=BSA_PARTS,
    ),
    Source(
        id="ffiec-bsa-manual",
        name="FFIEC BSA/AML Examination Manual",
        publisher="Federal Financial Institutions Examination Council",
        url="https://bsaaml.ffiec.gov/manual",
        fmt="html",
        authority="guidance",
        refresh="monthly",
        license="US Government work, not subject to copyright",
        notes="Per-section PDFs at /docs/manual/{nn}_{Section}/{nn}.pdf; HTML at /manual/{Section}/{nn}",
    ),
    Source(
        id="fincen-advisories",
        name="FinCEN advisories, alerts and fact sheets",
        publisher="FinCEN",
        url="https://www.fincen.gov/resources/advisoriesbulletinsfact-sheets",
        fmt="pdf",
        authority="guidance",
        refresh="weekly",
        license="US Government work, not subject to copyright",
        notes="No feed or API. Listing page must be crawled for advisory links.",
    ),
    Source(
        id="ofac-sdn",
        name="OFAC Specially Designated Nationals list",
        publisher="Office of Foreign Assets Control",
        url="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML",
        fmt="xml",
        authority="binding",
        refresh="daily",
        license="US Government work, not subject to copyright",
        notes="Screening data, not retrieval text. Consumed by the deterministic screening step.",
    ),
    Source(
        id="ofac-consolidated",
        name="OFAC Consolidated (non-SDN) sanctions list",
        publisher="Office of Foreign Assets Control",
        url="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONSOLIDATED.XML",
        fmt="xml",
        authority="binding",
        refresh="daily",
        license="US Government work, not subject to copyright",
        notes="Screening data, not retrieval text.",
    ),
)

BY_ID = {s.id: s for s in SOURCES}


def retrieval_sources() -> tuple[Source, ...]:
    """Sources whose text is chunked and embedded. Excludes screening lists."""
    return tuple(s for s in SOURCES if not s.id.startswith("ofac-"))
