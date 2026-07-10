# demo_pa002_private

Demonstrates **PA002 — cross-module import of a symbol marked `@private`**.

* `mypkg/secrets.py` declares a `@private` function `_token`.
* `mypkg/secrets.py` itself can use `_token` freely.
* `mypkg/other.py` imports `_token` from a *different* module — PyAccess
  flags this with `PA002` even though both modules live in the same package.

