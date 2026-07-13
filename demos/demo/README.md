# demo

A single, self-contained project that exercises **every PyAccess rule** in
one place, with explanations inline as code comments (each offending line
carries a `# PAxxx -- why` comment, cross-referenced to the rule's
implementation under `src/pyaccess/rules/`).

## Layout

| Path | What it shows |
|---|---|
| `pyproject.toml` | `[tool.pyaccess]` config: `default_visibility`, `roots`, `disabled_rules`. |
| `core_pkg/api.py` | Declares `@public`, `@internal` and `@private` symbols — the source of truth for the two static visibility rules. |
| `core_pkg/sibling.py` | Same-package use of `@internal` symbols: **legal**, no diagnostics. |
| `core_pkg/naming_mismatches.py` | **`PA003`**: `@public`/`@internal` (decorator or `Annotated[T, Public/Internal]`) vs. leading-underscore naming. |
| `consumer_pkg/cross_package.py` | Cross-package use of the same symbols: **`PA001`** and **`PA002`** both fire here. |
| `dynamic_pkg/unresolved_attrs.py` | **`PA010`** (non-literal `getattr`/`setattr`/...), **`PA011`** (`eval`/`exec`/`compile`), **`PA012`** (non-literal `import_module`/`__import__`). |
| `dynamic_pkg/hooks.py` | **`PA013`** (module-level `__getattr__`), **`PA014`** (explicit metaclass). |
| `dynamic_pkg/mutation.py` | **`PA015`** (`__dict__` mutation), **`PA018`** (`globals()`/`locals()`/`vars()` mutation). |
| `dynamic_pkg/introspection.py` | **`PA016`** (frame introspection), **`PA017`** (monkey-patching an imported name). |
| `dynamic_pkg/escape_hatches.py` | The inline-comment and `@dynamic`-decorator suppression mechanisms. |
| `dynamic_pkg/module_marker.py` | The whole-module `# pyaccess: dynamic-module` suppression mechanism. |

## Configuration (`pyproject.toml`)

```toml
[tool.pyaccess]
default_visibility = "public"                         # symbols without a decorator are public by default
roots = ["core_pkg", "consumer_pkg", "dynamic_pkg"]    # explicit top-level package boundaries
# disabled_rules = ["PA014"]                            # rule codes to skip project-wide
```

`roots` matters most for ambiguous layouts (e.g. a `src/` directory scanned
from the repo root, where the first dotted segment alone can't tell packages
apart) — here it's a no-op since each package is already its own top-level
name, but the syntax is the same. `disabled_rules` turns off a rule code for
the whole project; it's commented out above so the demo's expected output
below stays accurate — uncomment it to see `PA014` disappear.

## Rule reference

Rules `PA001`/`PA002` need the whole-project import graph (cross-file);
`PA003` and `PA010`-`PA018` are local to a single file's AST. See
`src/pyaccess/rules/access.py`, `src/pyaccess/rules/private.py`,
`src/pyaccess/rules/naming.py` and `src/pyaccess/rules/dynamic.py` for the
authoritative implementation and docstrings behind every code below.

| Code | Meaning |
|---|---|
| `PA001` | Cross-package import of a symbol marked `@internal`. |
| `PA002` | Cross-module import of a symbol marked `@private` (stricter than `PA001`: scoped to the *module*, not the *package*). |
| `PA003` | `@public`/`@internal` annotation disagrees with leading-underscore naming (error for `@public _foo`, warning for `@internal foo`). |
| `PA010` | `getattr`/`setattr`/`hasattr`/`delattr` called with a non-literal attribute name. |
| `PA011` | `eval` / `exec` / `compile` — executes code the linter cannot see through. |
| `PA012` | `importlib.import_module` / `__import__` called with a non-literal module name. |
| `PA013` | Module-level `__getattr__` / `__getattribute__` intercepting attribute access. |
| `PA014` | A class declares an explicit custom `metaclass=...`. |
| `PA015` | Direct `__dict__` mutation (subscript write, `.update()`/`.pop()`/..., or wholesale reassignment). |
| `PA016` | Call-stack frame introspection (`inspect.currentframe`/`stack`/`trace`, `sys._getframe`). |
| `PA017` | Monkey-patching an attribute of an already-imported name. |
| `PA018` | `globals()`/`locals()`/`vars()` used for a *write* (mutator call, subscript assignment, or `del`). |

Every `PA01x` diagnostic can be silenced with one of three dynamic-rule
escape hatches (see `dynamic_pkg/escape_hatches.py` and
`dynamic_pkg/module_marker.py`):

1. An inline trailing comment: `# pyaccess: allow-dynamic`.
2. A `@dynamic` (or `@dynamic(reason="...")`) decorator on the enclosing
   function/class.
3. A module-level marker comment near the top of the file:
   `# pyaccess: dynamic-module`.

**Any** diagnostic, from any rule (`PA001`/`PA002`/`PA003`/`PA01x`), can also
be silenced with the generic inline suppression comment — see
`core_pkg/api.py`'s `helper`/`InternalRegistry` and
`core_pkg/naming_mismatches.py`'s `deliberately_unprefixed` for examples:

```python
@internal  # pyaccess: ignore[PA003]
def helper(): ...

@internal  # pyaccess: ignore   (bare form: silences every code on this line)
def other(): ...
```

## Running it

From the repository root:

```bash
pyaccess check demos/demo
# or, without installing the console script:
python -m pyaccess.cli check demos/demo
python -m pyaccess.cli check --format json demos/demo
```

Expected: one `PA001` and one `PA002` from `consumer_pkg/cross_package.py`,
two `PA003` (one error, one warning) from `core_pkg/naming_mismatches.py`'s
decorators plus two more from its `Annotated[...]` attributes, and one
instance each of `PA010`-`PA018` from the corresponding `dynamic_pkg/*.py`
files, but **nothing** from `core_pkg/sibling.py`,
`dynamic_pkg/escape_hatches.py`, `dynamic_pkg/module_marker.py`, or the
inline-suppressed lines in `core_pkg/api.py` and
`core_pkg/naming_mismatches.py` — those are the "this is fine"
counter-examples.

## Live underlining in an editor

See the main repository README for `pyaccess-lsp` setup instructions (works
with any LSP-capable editor, e.g. via the LSP4IJ plugin in PyCharm, or
natively in VS Code / Neovim). Point the language server at this single
`demos/demo` folder.
