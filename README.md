# PyAccess

Strict accessibility linter for Python: enforce `@public` / `@internal` / `@private`
declarations across a project, the way C#, Java, TypeScript or Rust do natively.

This repository currently hosts a Phase 1 POC that demonstrates the core idea:

> Detect a cross-package import of a symbol marked `@internal`.

## Quickstart

```bash
pip install -e .[dev]
pytest
pyaccess check path/to/project
```

## Visibility markers

```python
from pyaccess import public, internal, private

@public
def api_function(): ...

@internal
def helper(): ...     # only callable from within the same package

@private
def _secret(): ...    # only callable from within the same module
```

The decorators are pure runtime identities. All enforcement is static.

