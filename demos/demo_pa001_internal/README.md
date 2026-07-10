# demo_pa001_internal

Demonstrates **PA001 — cross-package import of a symbol marked `@internal`**.

* `core_pkg/api.py` declares one `@public` and one `@internal` symbol.
* `core_pkg/sibling.py` imports the internal symbol from the *same* package —
  this is **allowed** (no diagnostic).
* `consumer_pkg/use_internal.py` imports the internal symbol from *another*
  top-level package — PyAccess flags this with `PA001`.

Try this:
1. Open `consumer_pkg/use_internal.py`. The two illegal imports should be
   underlined.
2. Change `@internal` to `@public` in `core_pkg/api.py`. The squiggles
   should vanish almost immediately.

