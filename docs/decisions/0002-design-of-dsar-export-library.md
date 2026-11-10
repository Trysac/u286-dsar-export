# Design of dsar-export library

Status: accepted (generated, pending human review)

## Context

Need a reusable library to assemble GDPR data subject access request exports from multiple systems with reproducibility, redaction, and failure reporting.

## Decision

Implement a standard-library-only package with a Protocol for sources, an in-memory reference source, and a deterministic ZIP builder with SHA-256 manifest.

## Consequences

No external dependencies keep installation simple and secure. The library is auditable and testable. Custom sources must implement the DataSource protocol and handle their own redaction if needed.
