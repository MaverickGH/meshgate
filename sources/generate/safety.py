"""Guard rails for AI-written build code — run before the code reaches Blender, and again inside the runner.

This is not a sandbox: Blender's Python cannot be sandboxed. It narrows what a generated `build(mg)` may touch to the
modeling kit plus math, random and mathutils, so a confused or prompt-injected model cannot reach files, processes,
the network or bpy by accident. The runner adds a restricted builtins table, --factory-startup, no auto-run of
scripts and a timeout. Review code from models you do not trust before running it.

    python3 sources/generate/safety.py generated.py     # prints problems, exit 1 if any
"""

from __future__ import annotations

import ast
import sys

MAX_CODE_BYTES = 80_000
ALLOWED_MODULES = {"math", "random", "mathutils"}
# names a build script never needs and that open doors out of the kit
DENIED_NAMES = {
    "bpy", "bmesh", "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib", "builtins", "io", "ctypes",
    "eval", "exec", "compile", "open", "input", "breakpoint", "globals", "locals", "vars", "getattr", "setattr",
    "delattr", "type", "object", "super", "memoryview", "exit", "quit", "help", "dir", "classmethod", "staticmethod",
    "property", "__import__",
}
# attributes that write files, run code or reach the application from any Blender object
DENIED_ATTRS = {
    "ops", "app", "utils", "handlers", "context", "save", "save_render", "save_as_mainfile", "filepath", "filepath_raw",
    "write", "as_module", "driver_add", "driver_remove", "drivers", "expression", "texts", "libraries", "load",
    "unpack", "reload", "scripts", "system", "path", "preferences", "window_manager", "rng_state", "getstate",
    "setstate", "f_globals", "f_locals", "gi_frame", "tb_frame",
}
DENIED_NODES = (ast.ClassDef, ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith,
                ast.With)


def check(code: str) -> list[str]:
    """Problems that stop the code from running, each with a line number. Empty list = allowed."""
    if len(code.encode()) > MAX_CODE_BYTES:
        return [f"code is {len(code.encode()) // 1000} KB, the limit is {MAX_CODE_BYTES // 1000} KB"]
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"line {exc.lineno}: syntax error: {exc.msg}"]
    problems = []

    def bad(node, msg):
        problems.append(f"line {getattr(node, 'lineno', '?')}: {msg}")

    for node in ast.walk(tree):
        if isinstance(node, DENIED_NODES):
            bad(node, f"'{type(node).__name__}' is not allowed in build code")
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_MODULES:
                    bad(node, f"import {a.name} — only {', '.join(sorted(ALLOWED_MODULES))} may be imported")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_MODULES or node.level:
                bad(node, f"from {node.module} import … — only {', '.join(sorted(ALLOWED_MODULES))} may be imported")
            elif any(a.name == "*" for a in node.names):
                bad(node, "star imports are not allowed")
        elif isinstance(node, ast.Name):
            if node.id in DENIED_NAMES:
                bad(node, f"'{node.id}' is not available — build with the mg kit only")
            elif node.id.startswith("_") and node.id != "_":   # a bare _ (for _ in range(n)) reaches nothing
                bad(node, f"names starting with '_' are not allowed ({node.id})")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                bad(node, f"attributes starting with '_' are not allowed (.{node.attr})")
            elif node.attr in DENIED_ATTRS:
                bad(node, f".{node.attr} is not allowed in build code")
        elif isinstance(node, (ast.FunctionDef, ast.Lambda)):
            name = getattr(node, "name", "")
            if name.startswith("_"):
                bad(node, f"function names starting with '_' are not allowed ({name})")
            args = node.args
            for a in args.posonlyargs + args.args + args.kwonlyargs + [x for x in (args.vararg, args.kwarg) if x]:
                if a.arg.startswith("_") and a.arg != "_":
                    bad(node, f"argument names starting with '_' are not allowed ({a.arg})")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value and "{" in node.value:
            bad(node, "format strings with dunder fields are not allowed")
    builds = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build"]
    if not builds:
        problems.append("the code must define `def build(mg):` at the top level")
    elif len(builds[0].args.args) != 1:
        problems.append("build must take exactly one argument: def build(mg)")
    return problems


SAFE_BUILTINS = {name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name) for name in (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "int", "isinstance", "len", "list",
    "map", "max", "min", "pow", "print", "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip",
    "ValueError", "Exception", "ZeroDivisionError", "IndexError", "KeyError", "True", "False", "None")}


def restricted_globals(modules: dict) -> dict:
    """Globals for exec(): safe builtins plus an __import__ that only hands out the allowed, pre-imported modules."""
    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".")[0]
        if root not in ALLOWED_MODULES or level:
            raise ImportError(f"import {name} is not allowed in build code")
        return modules[root] if not fromlist or "." not in name else modules[name]
    builtins = dict(SAFE_BUILTINS)
    builtins["__import__"] = guarded_import
    return {"__builtins__": builtins, "__name__": "meshgate_generated", **modules}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    found = check(open(sys.argv[1], encoding="utf-8").read())
    for p in found:
        print("✗ " + p)
    print("Result: " + ("allowed." if not found else f"{len(found)} problems."))
    sys.exit(1 if found else 0)
