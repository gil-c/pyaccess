"""PA010 / PA011 / PA012 — dynamic attribute access, code execution, dynamic imports.

Unlike PA001/PA002, these rules don't need the whole-project import graph:
each file is parsed once and walked for a fixed list of "escape the static
analysis" patterns (see ``src/pyaccess/rules/dynamic.py``).
"""
import importlib


def read_literal(obj: object) -> object:
    return getattr(obj, "value")  # OK -- literal attribute name, statically resolvable


def read_dynamic(obj: object, attr_name: str) -> object:
    return getattr(obj, attr_name)  # PA010 -- non-literal name defeats static analysis


def run_code(expression: str) -> object:
    return eval(expression)  # PA011 -- eval()/exec()/compile() run code the linter can't see through


def load_literal_module():
    return importlib.import_module("json")  # OK -- literal target, resolvable


def load_dynamic_module(module_name: str):
    return importlib.import_module(module_name)  # PA012 -- non-literal target, can't be resolved statically
