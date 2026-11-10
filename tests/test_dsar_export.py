import datetime as dt
import io
import json
import zipfile

import pytest

from dsar_export import (
    REDACTED,
    DsarError,
    InMemorySource,
    SubjectQuery,
    due_date,
    export,
)


def _sample_source() -> InMemorySource:
    return InMemorySource(
        "crm",
        [
            {"email": "ana@example.com", "plan": "pro"},
            {"email": "bo@example.com", "plan": "free"},
        ],
        match_fields=["email"],
    )


def _fixed_clock() -> dt.datetime:
    return dt.datetime(2026, 11, 9, 12, 0, tzinfo=dt.timezone.utc)


def test_export_single_source() -> None:
    query = SubjectQuery({"email": "ANA@example.com "})
    source = _sample_source()
    result = export(
        query,
        [source],
        request_id="r-1",
        clock=_fixed_clock,
    )
    with zipfile.ZipFile(io.BytesIO(result.bundle)) as zf:
        assert zf.namelist() == ["README.txt", "data/crm.json", "manifest.json"]
        data = zf.read("data/crm.json")
        assert data == b'[\n  {\n    "email": "ana@example.com",\n    "plan": "pro"\n  }\n]\n'
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest == {
            "request_id": "r-1",
            "created_at": "2026-11-09T12:00:00Z",
            "complete": True,
            "sources": [
                {
                    "name": "crm",
                    "records": 1,
                    "file": "data/crm.json",
                    "sha256": "3d93f437ca9453f6b2e4b1895cf5f406a48f694106758c6f7c6e640e9f75d625",
                }
            ],
            "errors": [],
        }
        assert result.manifest == manifest
        assert result.complete is True
        infos = zf.infolist()
        assert [i.date_time for i in infos] == [(1980, 1, 1, 0, 0, 0)] * 3
        assert all(i.external_attr == 0o644 << 16 for i in infos)
        assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in infos)


def test_reproducible_bundle() -> None:
    query = SubjectQuery({"email": "ana@example.com"})
    source = _sample_source()
    result1 = export(query, [source], request_id="r-1", clock=_fixed_clock)
    result2 = export(query, [source], request_id="r-1", clock=_fixed_clock)
    assert result1.bundle == result2.bundle


def test_source_failure_discards_partial_records() -> None:
    class FailingSource:
        name = "billing"

        def find(self, query):
            yield {"email": "ana@example.com", "amount": 10}
            raise RuntimeError("db down")

    query = SubjectQuery({"email": "ana@example.com"})
    good_source = _sample_source()
    # A failing source records an error; export itself does not raise.
    result = export(
        query,
        [good_source, FailingSource()],
        request_id="r-2",
        clock=_fixed_clock,
    )
    assert result.complete is False
    assert result.manifest["errors"] == [{"source": "billing", "code": "source_failed"}]
    # Good source still exported
    with zipfile.ZipFile(io.BytesIO(result.bundle)) as zf:
        assert "data/crm.json" in zf.namelist()
        assert "data/billing.json" not in zf.namelist()
        # Ensure failure message not present anywhere
        bundle_bytes = result.bundle
        assert b"db down" not in bundle_bytes
        manifest = json.loads(zf.read("manifest.json"))
        assert any(s["name"] == "crm" for s in manifest["sources"])
        assert all(s["name"] != "billing" for s in manifest["sources"])


def test_redaction() -> None:
    source = InMemorySource(
        "crm",
        [
            {
                "email": "ana@example.com",
                "counterparty_email": "third@example.com",
                "plan": "pro",
            }
        ],
        match_fields=["email"],
        redact_fields=["counterparty_email"],
    )
    query = SubjectQuery({"email": "ana@example.com"})
    result = export(query, [source], request_id="r-3", clock=_fixed_clock)
    with zipfile.ZipFile(io.BytesIO(result.bundle)) as zf:
        data = json.loads(zf.read("data/crm.json"))
        record = data[0]
        assert record["counterparty_email"] == REDACTED
        assert record["email"] == "ana@example.com"
        assert record["plan"] == "pro"


def test_too_many_records() -> None:
    # Generate 100001 records
    records = [{"email": "ana@example.com", "i": i} for i in range(100001)]
    source = InMemorySource(
        "large",
        records,
        match_fields=["email"],
    )
    query = SubjectQuery({"email": "ana@example.com"})
    result = export(
        query,
        [source],
        request_id="r-4",
        clock=_fixed_clock,
        max_records_per_source=100000,
    )
    assert result.complete is False
    assert result.manifest["errors"] == [{"source": "large", "code": "too_many_records"}]
    # Only 100000 records exported
    with zipfile.ZipFile(io.BytesIO(result.bundle)) as zf:
        data = json.loads(zf.read("data/large.json"))
        assert len(data) == 100000


def test_bundle_too_large() -> None:
    query = SubjectQuery({"email": "ana@example.com"})
    source = _sample_source()
    with pytest.raises(DsarError) as exc_info:
        export(
            query,
            [source],
            request_id="r-5",
            clock=_fixed_clock,
            max_bundle_bytes=1,
        )
    assert exc_info.value.code == "bundle_too_large"


def test_invalid_query_empty() -> None:
    with pytest.raises(DsarError) as exc_info:
        SubjectQuery({})
    assert exc_info.value.code == "invalid_query"


def test_invalid_record_nan() -> None:
    with pytest.raises(DsarError) as exc_info:
        InMemorySource(
            "bad",
            [{"x": float("nan")}],
            match_fields=["x"],
        )
    assert exc_info.value.code == "invalid_record"


def test_custom_source_invalid_record() -> None:
    class BadSource:
        name = "bad"

        def find(self, query):
            yield {"x": float("nan")}

    query = SubjectQuery({"email": "ana@example.com"})
    with pytest.raises(DsarError) as exc_info:
        export(query, [BadSource()], request_id="r-13", clock=_fixed_clock)
    assert exc_info.value.code == "invalid_record"


def test_invalid_clock_naive() -> None:
    query = SubjectQuery({"email": "ana@example.com"})
    source = _sample_source()
    with pytest.raises(DsarError) as exc_info:
        export(
            query,
            [source],
            request_id="r-6",
            clock=lambda: dt.datetime(2026, 11, 9, 12, 0),
        )
    assert exc_info.value.code == "invalid_clock"


def test_due_date() -> None:
    assert due_date(dt.date(2026, 1, 31)) == dt.date(2026, 2, 28)
    assert due_date(dt.date(2026, 11, 9)) == dt.date(2026, 12, 9)
    assert due_date(dt.date(2028, 1, 31)) == dt.date(2028, 2, 29)
    assert due_date(dt.date(2026, 12, 31)) == dt.date(2027, 1, 31)


def test_events_no_identifiers() -> None:
    events: list[dict[str, object]] = []
    query = SubjectQuery({"email": "ana@example.com"})
    source = _sample_source()
    export(
        query,
        [source],
        request_id="r-7",
        clock=_fixed_clock,
        on_event=events.append,
    )
    assert events == [
        {"event": "source_done", "source": "crm", "records": 1},
        {"event": "export_done", "complete": True},
    ]
    for event in events:
        event_str = str(event)
        assert "ana@example.com" not in event_str
        assert "pro" not in event_str


def test_no_records_complete_true() -> None:
    query = SubjectQuery({"email": "nobody@example.com"})
    source = _sample_source()
    result = export(query, [source], request_id="r-8", clock=_fixed_clock)
    assert result.complete is True
    with zipfile.ZipFile(io.BytesIO(result.bundle)) as zf:
        data = json.loads(zf.read("data/crm.json"))
        assert data == []
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["complete"] is True
        assert manifest["sources"][0]["records"] == 0


def test_unicode_values() -> None:
    query = SubjectQuery({"email": "üser@example.com"})
    source = InMemorySource(
        "unicode",
        [{"email": "üser@example.com", "name": "Ünïcode Nàme"}],
        match_fields=["email"],
    )
    result = export(query, [source], request_id="r-9", clock=_fixed_clock)
    with zipfile.ZipFile(io.BytesIO(result.bundle)) as zf:
        data = json.loads(zf.read("data/unicode.json"))
        assert data[0]["name"] == "Ünïcode Nàme"
        # ensure ensure_ascii=False wrote raw UTF-8 rather than \u escape sequences
        raw = zf.read("data/unicode.json")
        assert "Ünïcode Nàme".encode() in raw
        assert b"\\u00dc" not in raw


def test_datetime_conversion() -> None:
    query = SubjectQuery({"email": "ana@example.com"})
    source = InMemorySource(
        "dates",
        [
            {
                "email": "ana@example.com",
                "created": dt.datetime(2025, 1, 1, 12, 30, tzinfo=dt.timezone.utc),
                "birthday": dt.date(1990, 5, 20),
            }
        ],
        match_fields=["email"],
    )
    result = export(query, [source], request_id="r-10", clock=_fixed_clock)
    with zipfile.ZipFile(io.BytesIO(result.bundle)) as zf:
        data = json.loads(zf.read("data/dates.json"))
        assert data[0]["created"] == "2025-01-01T12:30:00+00:00"
        assert data[0]["birthday"] == "1990-05-20"


def test_source_name_validation() -> None:
    query = SubjectQuery({"email": "ana@example.com"})
    bad_source = InMemorySource(
        "Invalid Name",
        [],
        match_fields=["email"],
    )
    with pytest.raises(DsarError) as exc_info:
        export(query, [bad_source], request_id="r-11", clock=_fixed_clock)
    assert exc_info.value.code == "invalid_source"


def test_duplicate_source_names() -> None:
    query = SubjectQuery({"email": "ana@example.com"})
    source1 = InMemorySource("same", [], match_fields=["email"])
    source2 = InMemorySource("same", [], match_fields=["email"])
    with pytest.raises(DsarError) as exc_info:
        export(query, [source1, source2], request_id="r-12", clock=_fixed_clock)
    assert exc_info.value.code == "invalid_source"


def test_one_shot_source_iterable_is_materialised() -> None:
    query = SubjectQuery({"email": "ana@example.com"})

    def source_gen():
        yield _sample_source()

    result = export(query, source_gen(), request_id="r-14", clock=_fixed_clock)
    assert result.complete is True
    assert [s["name"] for s in result.manifest["sources"]] == ["crm"]
    with zipfile.ZipFile(io.BytesIO(result.bundle)) as zf:
        assert zf.namelist() == ["README.txt", "data/crm.json", "manifest.json"]
        assert json.loads(zf.read("data/crm.json"))[0]["plan"] == "pro"


def test_empty_sources_invalid() -> None:
    query = SubjectQuery({"email": "ana@example.com"})
    with pytest.raises(DsarError) as exc_info:
        export(query, [], request_id="r-15", clock=_fixed_clock)
    assert exc_info.value.code == "invalid_source"
