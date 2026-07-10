# PyAccess Demos

A collection of **standalone mini-projects** designed to be opened in PyCharm
so you can **see PyAccess in action live**, with red squiggles under the
offending lines as you type.

## What's here

Each subdirectory is a complete, self-contained Python project. Open the
`demos/` folder as your PyCharm workspace (or each subfolder individually if
you prefer).

| Project | Purpose | Expected diagnostics |
|---|---|---|
| `demo_pa001_internal/` | Cross-package import of `@internal` | `PA001` × 2 |
| `demo_pa002_private/`  | Cross-module import of `@private`  | `PA002` × 1 |
| `demo_all_clean/`      | Conformant project, nothing flagged | none |
| `demo_mixed/`          | Realistic project mixing legal & illegal accesses | `PA001`, `PA002` |

The `.editorconfig` and `pyproject.toml` files inside each demo mirror what
a real consumer of PyAccess would have, so what you see locally matches what
a downstream user would see.

---

## How to get live underlining in PyCharm

PyCharm itself does not ship a generic LSP client, but a free JetBrains
plugin called **LSP4IJ** (developed by Red Hat) gives PyCharm Community /
Pro the ability to talk to any Language Server. We use it to plug PyAccess in.

### 1. Install the LSP4IJ plugin

`Settings → Plugins → Marketplace → search "LSP4IJ" → Install → Restart`.

### 2. Declare PyAccess as a language server

`Settings → Languages & Frameworks → Language Servers → "+"`

* **Name:** `pyaccess`
* **Command:** absolute path to your `pyaccess-lsp` binary, for instance:
  * Windows: `D:\Dev\pyaccess\venv\Scripts\pyaccess-lsp.exe`
  * macOS / Linux: `/path/to/venv/bin/pyaccess-lsp`
* **Mappings tab:** add a mapping
  * **Language:** `Python`
  * **File name pattern:** `*.py`

Save. PyCharm will start the server in the background.

### 3. Open one of the demo folders

Open e.g. `demos/demo_pa001_internal/` as a PyCharm project. The illegal
imports in `consumer_pkg/use_internal.py` should now be **underlined in red**
within a second or two of opening the file.

### 4. Edit & verify live updates

Open `core_pkg/api.py` and remove the `@internal` decorator from `helper`.
The diagnostic in `use_internal.py` should disappear within ~500 ms after
your save (and immediately on text change if your LSP4IJ "trigger" is set
to `On document change`, which is the default).

---

## Fallback: PyCharm File Watcher

If you cannot (or do not want to) install LSP4IJ, you can still get
**non-inline** feedback by configuring a File Watcher that runs
`pyaccess check --format text <demo_dir>` on save and surfaces the output
in the Run tool window. See `docs/file_watcher.md` (TODO).

---

## Running from the CLI

From the repository root:

```powershell
# Show diagnostics in human-friendly form
python -m pyaccess.cli check demos/demo_pa001_internal

# JSON form (for tools / scripts)
python -m pyaccess.cli check --format json demos/demo_mixed
```

