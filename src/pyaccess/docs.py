"""Per-rule documentation for all PyAccess rules.

Each entry contains:
- code          : rule identifier (e.g. "PA001")
- title         : short human-readable name
- what          : one-line description of what is detected
- why           : rationale / why this matters
- example_bad   : offending code snippet
- example_good  : corrected version or escape hatch
- escape        : escape hatch syntax
- severity      : default severity level
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleDoc:
    code: str
    title: str
    what: str
    why: str
    example_bad: str
    example_good: str
    escape: str
    severity: str = "error"

    def render(self) -> str:
        """Return a human-readable multi-line description for terminal output."""
        lines = [
            f"{self.code}  {self.title}",
            f"{'─' * (len(self.code) + 2 + len(self.title))}",
            "",
            f"Severity : {self.severity}",
            "",
            "What     :",
            f"  {self.what}",
            "",
            "Why      :",
        ]
        for para in self.why.strip().splitlines():
            lines.append(f"  {para}" if para else "")
        lines += [
            "",
            "Example — violation:",
            *[f"  {ln}" for ln in self.example_bad.strip().splitlines()],
            "",
            "Example — fix / escape:",
            *[f"  {ln}" for ln in self.example_good.strip().splitlines()],
            "",
            "Escape hatch:",
            f"  {self.escape}",
            "",
        ]
        return "\n".join(lines)


_RULES: list[RuleDoc] = [
    # ------------------------------------------------------------------
    # Accessibility rules
    # ------------------------------------------------------------------
    RuleDoc(
        code="PA001",
        title="cross-package import of an @internal symbol",
        what=(
            "Importing a symbol marked @internal from a package other than the one "
            "that defines it."
        ),
        why=(
            "@internal means 'visible only within this package'. Importing it from "
            "another top-level package bypasses the intended API boundary and creates "
            "hidden coupling that breaks when the internal is refactored."
        ),
        example_bad="""\
# beta/user.py
from alpha.core import _helper   # @internal in alpha — violation

# alpha/core.py
from pyaccess import internal

@internal
def _helper(): ...
""",
        example_good="""\
# Option 1 — use a @public API surface instead:
# alpha/core.py
from pyaccess import public

@public
def helper(): ...

# beta/user.py
from alpha.core import helper   # OK

# Option 2 — suppress a single import with inline comment:
from alpha.core import _helper  # pyaccess: ignore[PA001]
""",
        escape="# pyaccess: ignore[PA001]  (trailing comment on the import line)",
        severity="error",
    ),
    RuleDoc(
        code="PA002",
        title="cross-module import of a @private symbol",
        what=(
            "Importing a symbol marked @private from any module other than its "
            "defining module."
        ),
        why=(
            "@private means 'visible only inside this module'. Unlike @internal (which "
            "is package-scoped), even a sibling module in the same package must not "
            "import it. Violations expose implementation details that have no stable "
            "contract."
        ),
        example_bad="""\
# alpha/utils.py
from alpha.core import _impl   # @private in alpha.core — violation

# alpha/core.py
from pyaccess import private

@private
def _impl(): ...
""",
        example_good="""\
# Promote to @internal if the sibling legitimately needs it:
from pyaccess import internal

@internal
def _impl(): ...

# Or suppress:
from alpha.core import _impl  # pyaccess: ignore[PA002]
""",
        escape="# pyaccess: ignore[PA002]  (trailing comment on the import line)",
        severity="error",
    ),
    RuleDoc(
        code="PA003",
        title="visibility annotation conflicts with naming convention",
        what=(
            "An explicit @public/@internal decorator disagrees with the leading-underscore "
            "naming convention."
        ),
        why=(
            "Python developers rely on the _underscore prefix as a 'non-public' signal "
            "long before annotations existed.  When decorator and name disagree it is "
            "almost always an oversight.\n"
            "\n"
            "Two sub-cases:\n"
            "  error   @public on an underscore-prefixed name (strong contradiction)\n"
            "  warning @internal on a non-underscore name (style nudge only)"
        ),
        example_bad="""\
from pyaccess import public, internal

@public          # ERROR: name says hidden, decorator says public
def _my_func(): ...

@internal        # WARNING: name reads like public API
def my_helper(): ...
""",
        example_good="""\
# Fix the name to match the intent:
@public
def my_func(): ...    # no underscore

@internal
def _my_helper(): ... # underscore matches internal

# Or suppress:
@public
def _my_func(): ...   # pyaccess: ignore[PA003]
""",
        escape="# pyaccess: ignore[PA003]  (trailing comment on the decorator line)",
        severity="error",  # sub-case for @public/_name; warning for the other sub-case
    ),
    # ------------------------------------------------------------------
    # Dynamic construct rules
    # ------------------------------------------------------------------
    RuleDoc(
        code="PA010",
        title="dynamic attribute access via getattr/setattr/hasattr/delattr",
        what=(
            "A call to getattr/setattr/hasattr/delattr where the attribute name is not "
            "a string literal — pyaccess cannot statically resolve which symbol is accessed."
        ),
        why=(
            "Non-literal attribute names defeat all static visibility analysis. "
            "PyAccess cannot know at analysis time which @internal or @private symbol "
            "the runtime will access, so the access escapes enforcement entirely."
        ),
        example_bad="""\
attr = "helper"
value = getattr(obj, attr)   # PA010: name is not a literal
""",
        example_good="""\
# Use a literal name:
value = getattr(obj, "helper")   # OK — literal, resolvable

# Or suppress if the dynamic access is intentional:
value = getattr(obj, attr)  # pyaccess: allow-dynamic

# Or annotate the function:
from pyaccess import dynamic

@dynamic(reason="plugin dispatch requires runtime attribute lookup")
def load_plugin(obj, name):
    return getattr(obj, name)
""",
        escape=(
            "# pyaccess: allow-dynamic          (inline, single line)\n"
            "  @dynamic(reason='...')           (function/class scope)\n"
            "  # pyaccess: dynamic-module       (whole file, near top)"
        ),
        severity="error",
    ),
    RuleDoc(
        code="PA011",
        title="use of eval / exec / compile",
        what="A call to eval(), exec(), or compile() with a dynamic string argument.",
        why=(
            "eval/exec/compile execute arbitrary code at runtime. Any symbol referenced "
            "inside the evaluated string is invisible to static analysis — visibility "
            "enforcement is completely bypassed for the executed code."
        ),
        example_bad="""\
eval("some_internal_func()")  # PA011
exec(user_code)               # PA011
""",
        example_good="""\
# Refactor to avoid dynamic execution, or suppress if unavoidable:
eval("some_internal_func()")  # pyaccess: allow-dynamic
""",
        escape=(
            "# pyaccess: allow-dynamic  |  @dynamic(reason='...')  |  # pyaccess: dynamic-module"
        ),
        severity="error",
    ),
    RuleDoc(
        code="PA012",
        title="dynamic import via importlib or __import__",
        what=(
            "A call to importlib.import_module() or __import__() with a non-literal "
            "module name."
        ),
        why=(
            "Dynamic imports load modules whose name is unknown at analysis time. "
            "PyAccess cannot build the import graph for dynamically loaded modules, "
            "so @internal/@private constraints on their symbols go unenforced."
        ),
        example_bad="""\
import importlib
mod = importlib.import_module(plugin_name)  # PA012
""",
        example_good="""\
# Use a literal:
mod = importlib.import_module("mypackage.plugin")  # OK

# Or suppress:
mod = importlib.import_module(plugin_name)  # pyaccess: allow-dynamic
""",
        escape=(
            "# pyaccess: allow-dynamic  |  @dynamic(reason='...')  |  # pyaccess: dynamic-module"
        ),
        severity="error",
    ),
    RuleDoc(
        code="PA013",
        title="module-level __getattr__ or __getattribute__",
        what=(
            "A module defines __getattr__ or __getattribute__ at module scope, enabling "
            "dynamic attribute resolution for the module itself."
        ),
        why=(
            "Module-level __getattr__ (PEP 562) intercepts attribute lookups on the "
            "module object. Any symbol the function returns is invisible to static "
            "analysis — importers can access anything, bypassing @internal/@private."
        ),
        example_bad="""\
# mypackage/mod.py
def __getattr__(name):           # PA013
    return _registry[name]
""",
        example_good="""\
# Expose only what you intend explicitly; use a dispatch dict with @public:
_registry = {"helper": _helper}

def get(name: str):              # explicit, analysable
    return _registry[name]

# Or suppress if the lazy-loading pattern is intentional:
def __getattr__(name):  # pyaccess: allow-dynamic
    return _registry[name]
""",
        escape=(
            "# pyaccess: allow-dynamic  |  @dynamic(reason='...')  |  # pyaccess: dynamic-module"
        ),
        severity="error",
    ),
    RuleDoc(
        code="PA014",
        title="explicit custom metaclass",
        what="A class declares an explicit metaclass= argument (other than type).",
        why=(
            "Custom metaclasses can redefine attribute creation, __getattr__, and "
            "class construction at runtime. They make static analysis of the class' "
            "members unreliable — added or transformed attributes are invisible."
        ),
        example_bad="""\
class MyMeta(type):
    def __new__(mcs, name, bases, ns): ...

class MyClass(metaclass=MyMeta):  # PA014
    pass
""",
        example_good="""\
# Prefer __init_subclass__, __class_getitem__, or descriptors for most needs.

# Or suppress if the metaclass is unavoidable (e.g. ABCMeta):
class MyABC(metaclass=ABCMeta):  # pyaccess: allow-dynamic
    pass
""",
        escape=(
            "# pyaccess: allow-dynamic  |  @dynamic(reason='...')  |  # pyaccess: dynamic-module"
        ),
        severity="error",
    ),
    RuleDoc(
        code="PA015",
        title="direct __dict__ mutation",
        what=(
            "A call that mutates an object's __dict__ directly "
            "(e.g. obj.__dict__['key'] = val, obj.__dict__.update(...))."
        ),
        why=(
            "__dict__ mutation bypasses the normal attribute-setting protocol and is "
            "invisible to static analysis. It can add or overwrite any symbol, including "
            "@private ones, without any visibility check."
        ),
        example_bad="""\
obj.__dict__["_secret"] = value   # PA015
obj.__dict__.update(kwargs)       # PA015
""",
        example_good="""\
# Use normal assignment; if the attribute is dynamic use setattr with a literal:
obj._secret = value               # analysable
setattr(obj, "_secret", value)    # OK — literal name

# Or suppress:
obj.__dict__["_secret"] = value   # pyaccess: allow-dynamic
""",
        escape=(
            "# pyaccess: allow-dynamic  |  @dynamic(reason='...')  |  # pyaccess: dynamic-module"
        ),
        severity="error",
    ),
    RuleDoc(
        code="PA016",
        title="frame introspection",
        what=(
            "A call to inspect.currentframe(), inspect.stack(), inspect.trace(), or "
            "sys._getframe()."
        ),
        why=(
            "Frame introspection reads the call stack at runtime and can access local "
            "variables, globals, and closures of any caller — including @private symbols. "
            "It also makes code fragile to inlining, tail-call optimisation, and other "
            "future Python optimisations."
        ),
        example_bad="""\
import inspect
frame = inspect.currentframe()   # PA016
caller_locals = frame.f_locals
""",
        example_good="""\
# Pass needed values explicitly instead of reading the caller's frame.

# Or suppress:
frame = inspect.currentframe()  # pyaccess: allow-dynamic
""",
        escape=(
            "# pyaccess: allow-dynamic  |  @dynamic(reason='...')  |  # pyaccess: dynamic-module"
        ),
        severity="error",
    ),
    RuleDoc(
        code="PA017",
        title="monkey-patching an attribute of an imported name",
        what=(
            "Assigning to an attribute of a name that was imported from another module "
            "(e.g. other_module.func = replacement)."
        ),
        why=(
            "Monkey-patching modifies a symbol in another module after import. "
            "It is invisible to static analysis — any code that later uses "
            "other_module.func will execute the patched version without the patching "
            "being visible at the call site. It also bypasses @private/@internal "
            "constraints."
        ),
        example_bad="""\
import alpha.core
alpha.core.helper = lambda: None  # PA017 — monkey-patching
""",
        example_good="""\
# Prefer dependency injection or adapter patterns instead of patching.
# In tests, use pytest monkeypatch or unittest.mock.patch:
def test_something(monkeypatch):
    monkeypatch.setattr(alpha.core, "helper", lambda: None)  # pyaccess: allow-dynamic
""",
        escape=(
            "# pyaccess: allow-dynamic  |  @dynamic(reason='...')  |  # pyaccess: dynamic-module"
        ),
        severity="warning",
    ),
    RuleDoc(
        code="PA018",
        title="write via globals() / locals() / vars()",
        what=(
            "A call to globals(), locals(), or vars() whose return value is used for a "
            "write operation (e.g. globals()['x'] = val, globals().update(...))."
        ),
        why=(
            "Writing through the globals/locals/vars namespace bypasses normal assignment "
            "and is invisible to static analysis. It can silently create or overwrite "
            "any name, including @private ones."
        ),
        example_bad="""\
globals()["_secret"] = value      # PA018
globals().update({"key": val})    # PA018
""",
        example_good="""\
# Use normal assignment:
_secret = value                   # analysable

# Or suppress:
globals()["_secret"] = value      # pyaccess: allow-dynamic
""",
        escape=(
            "# pyaccess: allow-dynamic  |  @dynamic(reason='...')  |  # pyaccess: dynamic-module"
        ),
        severity="error",
    ),
]

# Index by code for O(1) lookup.
_BY_CODE: dict[str, RuleDoc] = {r.code: r for r in _RULES}

ALL_RULES: list[RuleDoc] = _RULES


def get_rule(code: str) -> RuleDoc | None:
    """Return the :class:`RuleDoc` for *code*, or ``None`` if not found."""
    return _BY_CODE.get(code.upper())


def list_rules() -> list[RuleDoc]:
    """Return all rule docs, ordered by code."""
    return list(_RULES)
