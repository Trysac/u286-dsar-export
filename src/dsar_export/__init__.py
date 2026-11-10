"""Data Subject Access Request (DSAR) export assembly.

Collect matched records from pluggable data sources, redact third-party
fields, and produce a byte-reproducible ZIP bundle containing a SHA-256
manifest for auditing.
"""

from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import io
import json
import logging
import math
import re
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Protocol, runtime_checkable

__all__ = [
    "REDACTED",
    "DataSource",
    "DsarError",
    "ExportResult",
    "InMemorySource",
    "SubjectQuery",
    "due_date",
    "export",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

REDACTED = "[redacted: third party]"


class DsarError(Exception):
    """Base error for the dsar_export library."""

    def __init__(
        self,
        code: Literal[
            "invalid_query",
            "invalid_source",
            "invalid_record",
            "invalid_clock",
            "bundle_too_large",
        ],
        message: str | None = None,
    ) -> None:
        super().__init__(message if message is not None else code)
        self.code = code


@dataclass(frozen=True)
class SubjectQuery:
    """Immutable query identifying a data subject.

    ``identifiers`` is a mapping of field names to string values.
    The key ``'email'`` (if present) has its value normalized with
    ``strip().lower()``; all other values are normalized with ``strip()``.
    """

    identifiers: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.identifiers, Mapping):
            raise DsarError("invalid_query", "identifiers must be a mapping")
        normalized: dict[str, str] = {}
        for key, value in self.identifiers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise DsarError("invalid_query", "identifiers must be strings")
            if not re.fullmatch(r"[a-z_]{1,32}", key):
                raise DsarError(
                    "invalid_query",
                    "identifier keys must match ^[a-z_]{1,32}$",
                )
            normalized_value = value.strip().lower() if key == "email" else value.strip()
            if not 1 <= len(normalized_value) <= 256:
                raise DsarError(
                    "invalid_query",
                    "identifier values must be 1-256 characters after normalization",
                )
            normalized[key] = normalized_value
        if not 1 <= len(normalized) <= 10:
            raise DsarError("invalid_query", "query must contain 1-10 identifiers")
        object.__setattr__(self, "identifiers", MappingProxyType(normalized))


@runtime_checkable
class DataSource(Protocol):
    """Protocol for a data source that can find records for a subject."""

    name: str

    def find(self, query: SubjectQuery) -> Iterable[Mapping[str, object]]:
        """Yield records matching the query."""
        ...


class InMemorySource:
    """A source that holds records in memory.

    Records are matched against the query: a record matches when any field
    listed in ``match_fields`` equals the corresponding normalized identifier
    value from ``query``.  Fields listed in ``redact_fields`` are replaced
    with :data:`REDACTED` in the yielded records.
    """

    def __init__(
        self,
        name: str,
        records: Sequence[Mapping[str, object]],
        *,
        match_fields: Sequence[str],
        redact_fields: Sequence[str] = (),
    ) -> None:
        self.name = name
        self._match_fields = tuple(match_fields)
        self._redact_fields = tuple(redact_fields)
        materialized_records: list[Mapping[str, object]] = []
        for record in records:
            if not isinstance(record, Mapping):
                raise DsarError("invalid_record", "record must be a mapping")
            copy = dict(record)
            _validate_record(copy)
            materialized_records.append(copy)
        self._records = tuple(materialized_records)

    def find(self, query: SubjectQuery) -> Iterable[Mapping[str, object]]:
        """Yield records that match any of the configured match fields."""
        for record in self._records:
            for match_field in self._match_fields:
                if (
                    match_field in query.identifiers
                    and record.get(match_field) == query.identifiers[match_field]
                ):
                    yield _redact_record(record, self._redact_fields)
                    break


@dataclass(frozen=True)
class ExportResult:
    """Result of an export: the ZIP bundle and its manifest."""

    bundle: bytes
    manifest: dict[str, object]
    complete: bool


def _validate_record(record: object) -> None:
    """Validate a single record yielded by a data source."""
    if not isinstance(record, Mapping):
        raise DsarError("invalid_record", "record must be a mapping")
    for key, value in record.items():
        if not isinstance(key, str):
            raise DsarError("invalid_record", "record keys must be strings")
        _validate_json_value(value, depth=0)


def _validate_json_value(value: object, depth: int) -> None:
    if depth > 32:
        raise DsarError("invalid_record", "record nesting exceeds depth limit of 32")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DsarError("invalid_record", "float values must be finite")
        return
    if isinstance(value, (dt.datetime, dt.date)):
        return
    if isinstance(value, Mapping):
        for k, v in value.items():
            if not isinstance(k, str):
                raise DsarError("invalid_record", "record keys must be strings")
            _validate_json_value(v, depth + 1)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_json_value(item, depth + 1)
        return
    raise DsarError("invalid_record", f"unsupported record value type: {type(value).__name__}")


def _json_ready(value: object) -> object:
    """Convert datetime/date to ISO strings, recursively."""
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {k: _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _redact_record(record: Mapping[str, object], redact_fields: Sequence[str]) -> dict[str, object]:
    """Return a new dict with the given fields replaced by REDACTED."""
    new_record = dict(record)
    for redact_field in redact_fields:
        new_record[redact_field] = REDACTED
    return new_record


def export(
    query: SubjectQuery,
    sources: Sequence[DataSource],
    *,
    request_id: str,
    clock: Callable[[], dt.datetime],
    max_records_per_source: int = 100_000,
    max_bundle_bytes: int = 104_857_600,
    on_event: Callable[[dict[str, object]], None] | None = None,
) -> ExportResult:
    """Run the export and build the reproducible bundle.

    Args:
        query: The already-validated ``SubjectQuery``.
        sources: Sequence of data sources to query.
        request_id: Arbitrary string identifying the request (no validation).
        clock: Callable returning a timezone-aware UTC ``datetime``.
        max_records_per_source: Maximum records to export per source.
        max_bundle_bytes: Maximum allowed size of the ZIP bundle.
        on_event: Optional callback receiving progress events.  Events are
            dicts with string keys and JSON-serialisable values.  They must
            never contain identifiers or record values.

    Returns:
        ``ExportResult`` with the bundle bytes and manifest.

    Raises:
        DsarError: If any validation fails or the bundle is too large.
    """
    if not isinstance(query, SubjectQuery):
        raise DsarError("invalid_query", "query must be a SubjectQuery")

    # Materialise the sources once so one-shot iterables cannot silently
    # produce an empty export that is reported as complete.
    source_list = list(sources)
    if not source_list:
        raise DsarError("invalid_source", "at least one source is required")

    # Validate sources
    source_names: set[str] = set()
    for source in source_list:
        name = source.name
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_-]{1,64}", name):
            raise DsarError(
                "invalid_source",
                "source name must match ^[a-z0-9_-]{1,64}$ and be unique",
            )
        if name in source_names:
            raise DsarError("invalid_source", "duplicate source name")
        source_names.add(name)

    # Get current timestamp
    now_dt = clock()
    if not isinstance(now_dt, dt.datetime):
        raise DsarError("invalid_clock", "clock must return a datetime")
    if now_dt.tzinfo is None or now_dt.utcoffset() is None:
        raise DsarError("invalid_clock", "clock must return a timezone-aware datetime")
    created_at = now_dt.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    successful_sources: list[tuple[str, list[Mapping[str, object]]]] = []
    errors: list[dict[str, str]] = []
    complete = True

    for source in source_list:
        records: list[Mapping[str, object]] = []
        source_failed = False
        try:
            iterator = iter(source.find(query))
            while True:
                try:
                    record = next(iterator)
                except StopIteration:
                    break
                _validate_record(record)
                records.append(record)
                if len(records) > max_records_per_source:
                    complete = False
                    errors.append({"source": source.name, "code": "too_many_records"})
                    records = records[:max_records_per_source]
                    break
        except DsarError:
            raise
        except Exception:
            source_failed = True
            complete = False
            errors.append({"source": source.name, "code": "source_failed"})
            records = []  # discard partial records
        if not source_failed:
            successful_sources.append((source.name, records))
            if on_event:
                on_event(
                    {
                        "event": "source_done",
                        "source": source.name,
                        "records": len(records),
                    }
                )

    # Sort successful sources by name
    successful_sources.sort(key=lambda x: x[0])

    # Generate file contents
    manifest_sources: list[dict[str, object]] = []
    data_files: dict[str, bytes] = {}
    for name, records in successful_sources:
        json_content = (
            json.dumps(
                [_json_ready(r) for r in records],
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        data_bytes = json_content.encode("utf-8")
        sha256 = hashlib.sha256(data_bytes).hexdigest()
        file_name = f"data/{name}.json"
        data_files[file_name] = data_bytes
        manifest_sources.append(
            {
                "name": name,
                "records": len(records),
                "file": file_name,
                "sha256": sha256,
            }
        )

    # Build README.txt
    readme_lines = [
        "Data Subject Access Request export",
        "",
        "This bundle contains records matching the request.",
        "",
        "Sources included:",
    ]
    for src in manifest_sources:
        readme_lines.append(f"- {src['name']}: {src['records']} record(s)")
    readme_lines.append("")
    readme_lines.append("Please handle this information securely.")
    readme_bytes = ("\n".join(readme_lines) + "\n").encode("utf-8")

    # Build manifest
    errors.sort(key=lambda x: x["source"])
    manifest: dict[str, object] = {
        "request_id": request_id,
        "created_at": created_at,
        "complete": complete,
        "sources": manifest_sources,
        "errors": errors,
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")

    # Assemble entries
    entries: list[tuple[str, bytes]] = [
        ("README.txt", readme_bytes),
        *data_files.items(),
        ("manifest.json", manifest_bytes),
    ]
    entries.sort(key=lambda x: x[0])

    # Build ZIP with deterministic metadata
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, content in entries:
            info = zipfile.ZipInfo(arcname)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, content)
    bundle_bytes = zip_buffer.getvalue()

    if len(bundle_bytes) > max_bundle_bytes:
        raise DsarError("bundle_too_large", "resulting bundle exceeds size limit")

    if on_event:
        on_event({"event": "export_done", "complete": complete})

    return ExportResult(bundle=bundle_bytes, manifest=manifest, complete=complete)


def due_date(received: dt.date) -> dt.date:
    """Return the one-month deadline as per EDPB Guidelines 01/2022.

    The date is the same calendar day of the next month, or the last day of
    that month if it has fewer days.
    """
    if not isinstance(received, dt.date):
        raise TypeError("received must be a date")
    year = received.year
    month = received.month + 1
    if month == 13:
        year += 1
        month = 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(received.day, last_day)
    return dt.date(year, month, day)
