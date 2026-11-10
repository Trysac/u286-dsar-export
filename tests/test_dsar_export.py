"""Behavior tests for the public API of dsar_export."""

from __future__ import annotations

import pytest

import dsar_export


def test_normalize_trims_and_lowercases() -> None:
    assert dsar_export.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        dsar_export.normalize(value)


def test_version_is_semver() -> None:
    parts = dsar_export.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
