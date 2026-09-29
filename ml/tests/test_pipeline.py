"""Pipeline tests. No AWS: the stages take a Storage, so the filesystem stands in."""

import json
from pathlib import Path

import pytest

from ml.ingestion import ecfr
from ml.pipeline import keys, stages
from ml.pipeline.records import from_jsonl
from ml.pipeline.storage import LocalStorage

FIXTURE = Path(__file__).parent / "fixtures" / "ecfr_title31_sample.xml"
SOURCE, PART, AS_OF, RUN = "ecfr-31-x", "9990", "2026-09-10", "run-1"


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


@pytest.fixture
def stub_fetch(monkeypatch):
    calls = []

    def fake(part, date, **kw):
        calls.append((part, date))
        return FIXTURE.read_bytes()

    monkeypatch.setattr(ecfr, "fetch_part", fake)
    return calls


def test_fetch_stores_the_raw_xml(storage, stub_fetch):
    out = stages.fetch(storage, SOURCE, PART, AS_OF)
    assert out["raw_key"] == f"raw/{SOURCE}/{AS_OF}/part-{PART}.xml"
    assert out["cached"] is False
    assert storage.exists(out["raw_key"])
    assert len(out["raw_sha256"]) == 64


def test_fetch_is_skipped_when_already_stored(storage, stub_fetch):
    stages.fetch(storage, SOURCE, PART, AS_OF)
    again = stages.fetch(storage, SOURCE, PART, AS_OF)
    assert again["cached"] is True
    assert len(stub_fetch) == 1, "a cached part must not be downloaded twice"


def test_transform_writes_records_with_everything_needed_to_cite(storage, stub_fetch):
    stages.fetch(storage, SOURCE, PART, AS_OF)
    out = stages.transform(storage, SOURCE, PART, AS_OF, RUN)

    assert out["chunks"] > 0
    records = from_jsonl(storage.get(out["chunks_key"]))
    assert len(records) == out["chunks"]

    first = records[0]
    for required in (
        "schema_version", "chunk_id", "source_id", "citation", "pinpoint",
        "as_of", "text", "token_count", "text_sha256", "run_id",
    ):
        assert required in first, f"missing {required}"
    assert first["as_of"] == AS_OF
    assert first["run_id"] == RUN
    assert first["citation"].startswith("31 CFR ")


def test_finalize_writes_a_manifest_and_moves_latest(storage, stub_fetch):
    stages.fetch(storage, SOURCE, PART, AS_OF)
    part = stages.transform(storage, SOURCE, PART, AS_OF, RUN)
    out = stages.finalize(
        storage, SOURCE, AS_OF, RUN, [part], "2026-09-10T00:00:00+00:00", "test-counter"
    )

    manifest = json.loads(storage.get(keys.manifest_key(SOURCE, AS_OF)))
    assert manifest["run_id"] == RUN
    assert manifest["totals"]["chunks"] == part["chunks"]
    assert manifest["parts"][0]["chunks_sha256"] == part["chunks_sha256"]

    # latest must be byte-identical to the manifest it points at
    assert storage.get(keys.latest_key(SOURCE)) == storage.get(
        keys.manifest_key(SOURCE, AS_OF)
    )
    assert out["chunks"] == part["chunks"]


def test_finalize_refuses_an_empty_run(storage):
    with pytest.raises(stages.ValidationFailed, match="no parts"):
        stages.finalize(storage, SOURCE, AS_OF, RUN, [], "t", "c")


def test_impossible_path_stops_the_run(storage, monkeypatch, stub_fetch):
    """A citation that cannot exist must fail the run, not be flagged and kept."""
    stages.fetch(storage, SOURCE, PART, AS_OF)
    monkeypatch.setattr(ecfr, "path_follows_cycle", lambda path: False)
    with pytest.raises(stages.ValidationFailed, match="impossible"):
        stages.transform(storage, SOURCE, PART, AS_OF, RUN)


def test_non_verbatim_text_stops_the_run(storage, monkeypatch, stub_fetch):
    """If chunk text drifts from its source, the run fails rather than indexing it."""
    stages.fetch(storage, SOURCE, PART, AS_OF)

    real = stages._check_verbatim

    def tampered(sections, chunks):
        for chunk in chunks:
            chunk.text = chunk.text.replace("this part", "thispart", 1)
        return real(sections, chunks)

    monkeypatch.setattr(stages, "_check_verbatim", tampered)
    with pytest.raises(stages.ValidationFailed, match="not verbatim"):
        stages.transform(storage, SOURCE, PART, AS_OF, RUN)


def test_records_are_stable_across_runs(storage, stub_fetch):
    """Re-ingesting the same vintage replaces rather than duplicates."""
    stages.fetch(storage, SOURCE, PART, AS_OF)
    first = stages.transform(storage, SOURCE, PART, AS_OF, "run-1")
    second = stages.transform(storage, SOURCE, PART, AS_OF, "run-2")

    a = [r["chunk_id"] for r in from_jsonl(storage.get(first["chunks_key"]))]
    b = [r["chunk_id"] for r in from_jsonl(storage.get(second["chunks_key"]))]
    assert a == b
    assert first["chunks_key"] == second["chunks_key"]
