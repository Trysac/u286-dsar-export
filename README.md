# dsar-export

[![CI](https://github.com/Trysac/u286-dsar-export/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u286-dsar-export/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/trysac-dsar-export.svg)](https://pypi.org/project/trysac-dsar-export/)
[![Python versions](https://img.shields.io/pypi/pyversions/trysac-dsar-export.svg)](https://pypi.org/project/trysac-dsar-export/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Assemble a data subject access request (DSAR) export from pluggable data sources.

- Collect matched records from multiple systems through one interface.
- Redact third-party data in fields declared by the source.
- Produce a byte-reproducible ZIP bundle with a SHA-256 manifest.
- Record source failures as manifest error codes instead of silently skipping them.

## Installation

```bash
pip install trysac-dsar-export
```

## Usage

```python
from datetime import datetime, timezone
from dsar_export import InMemorySource, SubjectQuery, export

query = SubjectQuery({"email": "ana@example.com"})
source = InMemorySource(
    "crm", [{"email": "ana@example.com", "plan": "pro"}], match_fields=["email"]
)
result = export(
    query,
    [source],
    request_id="r-1",
    clock=lambda: datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc),
)
# result.bundle holds the ZIP bytes.
```

The ZIP contains `README.txt`, `data/<source>.json` for each successfully exported source, and `manifest.json`. Entry names are sorted, timestamps are fixed at `(1980, 1, 1, 0, 0, 0)`, and compression is `ZIP_DEFLATED`.

## API Reference

### `SubjectQuery`

Frozen dataclass holding a subject's identifiers as a mapping of field names to strings. Validation rules:

- 1–10 identifiers.
- Keys match `^[a-z_]{1,32}$`.
- Values are 1–256 characters after normalization.
- The `email` key is normalized with `strip().lower()`; other values with `strip()`.
- Invalid input raises `DsarError` with code `invalid_query`.

### `DataSource` (Protocol)

Runtime-checkable protocol for a source with `name: str` and `find(query: SubjectQuery) -> Iterable[Mapping[str, object]]`.

### `InMemorySource`

```python
InMemorySource(name, records, *, match_fields, redact_fields=())
```

Records are validated on construction. A record matches when any field named in `match_fields` equals the corresponding normalized identifier in the query. Fields named in `redact_fields` are replaced with `REDACTED = "[redacted: third party]"`. Source names must match `^[a-z0-9_-]{1,64}$` and be unique; invalid names raise `DsarError` with code `invalid_source`.

### `export`

```python
export(query, sources, *, request_id, clock, max_records_per_source=100_000, max_bundle_bytes=104_857_600, on_event=None)
```

Returns `ExportResult(bundle: bytes, manifest: dict[str, object], complete: bool)`.

- `request_id` is an arbitrary string and is not validated.
- `clock` must return a timezone-aware `datetime`; a naive value raises `DsarError` with code `invalid_clock`. The manifest stores `created_at` in UTC as `%Y-%m-%dT%H:%M:%SZ`.
- `max_records_per_source` limits records per source. Exceeding it records `too_many_records`, truncates that source's records, and sets `complete` to `False`.
- `max_bundle_bytes` raises `DsarError` with code `bundle_too_large` when the assembled ZIP exceeds it.
- `on_event` receives dict events such as `source_done` and `export_done`; events created by the library contain source names, counts and completion state, never identifiers or record values.
- A source that raises an exception is recorded as `source_failed`; its partial records are discarded and other sources continue. Per-source errors appear in `manifest["errors"]` and are not raised. The manifest never stores exception text.

Records may contain `None`, `str`, `bool`, `int`, finite `float`, lists, and mappings with string keys; `datetime` and `date` values are converted with `isoformat()`. Other types, non-string keys, non-finite floats, or nesting deeper than 32 raise `DsarError` with code `invalid_record`.

`DsarError` carries a `code` attribute with one of: `invalid_query`, `invalid_source`, `invalid_record`, `invalid_clock`, `bundle_too_large`.

### `due_date`

Returns the one-month deadline according to EDPB Guidelines 01/2022: the same calendar day of the next month, or the last day of that month when it has fewer days.

## Why not ad hoc scripts

Ad hoc queries do not provide one auditable flow: this library records source failures explicitly, redacts declared third-party fields through the source interface, and emits checksummed, byte-reproducible output. It does not replace identity verification or legal review.

## Security Considerations

- The bundle is not encrypted; deliver it over an authenticated channel.
- Identity verification of the requester is out of scope.
- See [docs/SECURITY.md](docs/SECURITY.md) for the threat model.

## License

MIT
