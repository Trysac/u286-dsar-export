# dsar-export

[![PyPI version](https://img.shields.io/pypi/v/trysac-dsar-export)](https://pypi.org/project/trysac-dsar-export/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-dsar-export)](LICENSE)
[![CI](https://github.com/Trysac/u286-dsar-export/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u286-dsar-export/actions/workflows/ci.yml)

Assemble a data subject access request export from pluggable data sources: matched records, third-party redaction, a byte-reproducible ZIP with a SHA-256 manifest

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-dsar-export
# or
uv add trysac-dsar-export
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import dsar_export

# normalize() trims surrounding whitespace and lower-cases the text.
print(dsar_export.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    dsar_export.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
