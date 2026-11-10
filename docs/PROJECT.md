# Project record

## Objective

Provide a stdlib-only Python library that assembles a DSAR export from pluggable data sources: collect matched records, allow a source to redact declared third-party fields, and build a byte-reproducible ZIP bundle with a SHA-256 manifest.

## Scope

In scope:

- The public API in `src/dsar_export/__init__.py`: `SubjectQuery`, `DataSource`, `InMemorySource`, `export`, `ExportResult`, `due_date`, `REDACTED`, and `DsarError`.
- Validation of identifiers, source names, records, clocks, and bundle size with `DsarError` codes.
- Explicit per-source failure reporting in `manifest["errors"]` with codes `source_failed` and `too_many_records`.
- Deterministic ZIP entries `README.txt`, `data/<source>.json`, and `manifest.json`, with SHA-256 checksums for data files.
- The one-month deadline calculation in `due_date` following EDPB Guidelines 01/2022.

Out of scope:

- Identity verification of the requester.
- Connectors to real databases or external services.
- Deletion requests.
- Encryption of the bundle; it must be delivered over an authenticated channel.
- Deadline extensions.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created for the dsar-export utility. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 1010281 / 78939 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.0990 |

## Factory run u286 (measured from API usage)

| Date (UTC) | Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|---|
| 2026-11-10 | generation | deepseek-v4-pro | yes | 1930 | 15740 | 0 | 3200 | 0.0325 |
| 2026-11-10 | fix-1 | deepseek-flash | no | 14622 | 12456 | 0 | 179712 | 0.0102 |
| 2026-11-10 | audit | deepseek-flash | no | 19737 | 22711 | 0 | 319232 | 0.0175 |
| 2026-11-10 | fix-2 | deepseek-flash | no | 8539 | 2934 | 0 | 83584 | 0.0033 |
| 2026-11-10 | threat-model | deepseek-flash | no | 18879 | 16220 | 0 | 195456 | 0.0132 |
| 2026-11-10 | fix-3 | deepseek-flash | no | 7526 | 1528 | 0 | 52992 | 0.0022 |
| 2026-11-10 | docs | deepseek-flash | no | 104616 | 7350 | 0 | 256 | 0.0201 |

Total: $0.0990. Prices: deepseek line, as measured by its adapter. Providers serve the current version of each model id, so the date tells which version answered; versions, launch stages and price sources per line are in the factory's model register (docs/MODELS.md).
