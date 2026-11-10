# Security notes

## Threat model

`trysac-dsar-export` is a library. `export` assembles the ZIP in memory from caller-provided sources; it performs no network or filesystem I/O. The threat model is limited to what the code enforces.

### Defended

- Invalid queries are rejected before export: 1–10 identifiers, keys matching `^[a-z_]{1,32}$`, values 1–256 characters after normalization; failures raise `DsarError` with code `invalid_query`.
- Source names must match `^[a-z0-9_-]{1,64}$` and be unique; failures raise `DsarError` with code `invalid_source`.
- Records are validated before entering the bundle: JSON-compatible values only, string keys, finite floats, and nesting no deeper than 32; failures raise `DsarError` with code `invalid_record`.
- The clock must return a timezone-aware `datetime`; naive values raise `DsarError` with code `invalid_clock`.
- A source that raises an exception is recorded as `source_failed`, its partial records are discarded, and other sources continue. Exception text is never placed in the manifest or bundle.
- Exceeding `max_records_per_source` records `too_many_records`, truncates that source's records, and sets `complete` to `False`.
- Exceeding `max_bundle_bytes` raises `DsarError` with code `bundle_too_large`.
- `InMemorySource` replaces fields named in `redact_fields` with `REDACTED = "[redacted: third party]"`.
- Data files are checksummed with SHA-256 in `manifest.json`.
- The code uses no `eval`, `exec`, or deserialization of untrusted data.
- Progress events created by the library contain source names, record counts, and completion state; they do not contain identifiers or record values.

### Not defended

- The ZIP bundle is not encrypted. Confidentiality in transit and at rest is the caller's responsibility; deliver it over an authenticated channel.
- Identity verification of the requester is not performed.
- Redaction covers only fields declared to `InMemorySource` (or handled by a custom source). A source may return third-party data in undeclared fields.
- Real database connectors, authentication to upstream systems, and rate limiting are not provided.
- Deletion requests and deadline extensions are not handled.
- `request_id` is not validated and is copied into `manifest.json`; callers must not put sensitive data there.
- The `on_event` callback is caller-supplied and is not sanitized by the library; it must not emit identifiers or record values.

## Publishing

Publishing mechanics are outside the library code in this repository. The package is distributed as `trysac-dsar-export`; no release credentials are part of the code.
