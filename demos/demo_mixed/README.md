# demo_mixed

A realistic mini-project mixing **legal** and **illegal** access patterns:

* `engine/` is the library, with both public and internal symbols and a
  module-private helper.
* `engine/extras.py` legitimately consumes internal symbols from
  `engine.core` (same package → OK).
* `webapp/` is the consumer, which gets caught crossing package boundaries
  into `engine`'s internals.

Expected diagnostics: at least one `PA001` *and* one `PA002`.

Try the live workflow:
1. Open `webapp/handlers.py` — three lines should be underlined.
2. Replace `engine.core.helper` with `engine.core.public_entry` —
   one underline disappears.
3. Remove `@private` from `engine.core._secret` — the PA002 underline disappears.

