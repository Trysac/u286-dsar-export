# Testing

## Running

```sh
pytest tests/test_dsar_export.py
```

## Policy

Tests exercise the public API through `dsar_export` and assert observable results: ZIP entry names and bytes, manifest values, raised `DsarError` codes, and progress events. They use synthetic in-memory records and a fixed timezone-aware clock; no network or external services are involved.

## Tiers

The suite is a single test module. The repository listing contains no separate conformance tier, external tool download, or `conftest.py` fixture file.

## Layout

`tests/test_dsar_export.py` covers:

- `test_export_single_source` — a single `InMemorySource` produces `README.txt`, `data/crm.json`, and `manifest.json`; asserts the exact JSON bytes for `data/crm.json` and the expected manifest values.
- `test_reproducible_bundle` — two exports with the same inputs and clock return identical `result.bundle` bytes.
- `test_source_failure_discards_partial_records` — a source raising `RuntimeError("db down")` sets `complete=False`, records `source_failed`, keeps other sources, and does not include the exception text or a partial file in the bundle.
- `test_redaction` — `redact_fields=["counterparty_email"]` replaces that value with `[redacted: third party]` and leaves other fields unchanged.
- `test_too_many_records` — exceeding `max_records_per_source` records `too_many_records` and sets `complete=False`.
- `test_bundle_too_large` — a bundle above `max_bundle_bytes` raises `DsarError` with code `bundle_too_large`.
- `test_invalid_query_empty` — `SubjectQuery({})` raises `DsarError` with code `invalid_query`.
- `test_invalid_record_nan` — a record containing `float("nan")` raises `DsarError` with code `invalid_record`.
- `test_custom_source_invalid_record` — a custom `DataSource` yielding an invalid record raises `DsarError` with code `invalid_record`.
- `test_invalid_clock_naive` — a clock returning a naive `datetime` raises `DsarError` with code `invalid_clock`.
