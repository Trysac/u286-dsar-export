# Architecture

## Purpose

`trysac-dsar-export` is a small, dependency-free Python library: Assemble a data subject access request export from pluggable data sources: matched records, third-party redaction, a byte-reproducible ZIP with a SHA-256 manifest

## Shape

```text
caller code --> dsar_export (public API in __init__.py)
                    |
                    +-- pure functions, no I/O, no global state
```

- **Public API**: the names listed in `__all__` of `src/dsar_export/__init__.py`. Anything else is
  internal and may change without a major version.
- **Errors**: invalid input raises `DsarError` with a `code` attribute (`invalid_query`,
  `invalid_source`, `invalid_record`, `invalid_clock`, `bundle_too_large`); messages are short and
  never contain identifiers or record values. Per-source failures are reported in
  `ExportResult.manifest['errors']` instead of being raised; the library never prints or exits.
- **Side effects**: none. If a feature needs I/O, isolate it in its own module behind a small
  interface and record the choice in an ADR.

## Quality contract

`scripts/check.py` is the single definition of the gates; `fabrica.json` tells the factory and CI
how to run it. See [TESTING.md](TESTING.md).

## Decisions

Architecture decisions are recorded in [decisions/](decisions/) as numbered ADRs.
