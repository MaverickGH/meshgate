#!/usr/bin/env python3
"""Check the MeshGate Unreal plugin against the Python API that Unreal itself generates — without Unreal.

    python3 tests/unreal/check_api.py [--versions 5.4,5.5,5.6] [--download]

Unreal writes its whole Python API as a stub (`unreal.py`, Intermediate/PythonStub). The public
`unreal-stub` package (https://pypi.org/project/unreal-stub/, GitHub DocDooom/unreal-stub) ships those
stubs for UE 5.4, 5.5 and 5.6. This script indexes them (cached in ~/.cache/meshgate/unreal/) and walks
the plugin's Python with `ast`:

  • unreal.X                       X must exist (in every version, unless guarded by hasattr(unreal, "X"))
  • unreal.Class.member            member must exist on the class or its bases
  • unreal.Class(kw=…)             keyword must be a parameter of the constructor
  • obj.set/get_editor_property("p")  p must be an editor property of some class
  • _set(obj, "a", v, "b")         at least one of a/b must exist in each version (names that moved)
  • obj.attr                       attr must exist somewhere in the API (catches typos in property chains)

It cannot prove behaviour — only that every name we touch exists in the engine versions we claim.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "targets" / "unreal" / "MeshGate" / "Content" / "Python"
CACHE = Path(os.path.expanduser("~/.cache/meshgate/unreal"))
PACKAGE_VERSION = {"5.4": "0.1", "5.5": "0.2.1", "5.6": "0.3"}   # unreal-stub release → engine version of its stub
_EDITOR_PROP = re.compile(r"-\s+``(\w+)``\s+\(")
# attribute names that belong to Python objects we use, not to Unreal
PY_ATTRS = {
    "append", "extend", "split", "lower", "upper", "startswith", "endswith", "join", "get", "items", "keys", "values",
    "stdout", "stderr", "returncode", "path", "environ", "isfile", "isdir", "abspath", "dirname", "basename", "exists",
    "argv", "executable", "run", "add_argument", "parse_args", "replace", "strip", "format", "level", "samples",
}


# ----------------------------------------------------------------------------
# stubs
# ----------------------------------------------------------------------------

def stub_path(version: str, download: bool) -> Path | None:
    p = CACHE / f"unreal-{version}.py"
    if p.exists():
        return p
    if not download:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"downloading UE {version} stub (unreal-stub {PACKAGE_VERSION[version]} from PyPI) …", flush=True)
    meta = json.loads(urllib.request.urlopen("https://pypi.org/pypi/unreal-stub/json", timeout=60).read())
    wheel = next(f["url"] for f in meta["releases"][PACKAGE_VERSION[version]] if f["filename"].endswith(".whl"))
    data = urllib.request.urlopen(wheel, timeout=300).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.endswith("unreal.py") or n.endswith("unreal/__init__.pyi") or n.endswith("unreal.pyi"))
        p.write_bytes(z.read(name))
    return p


def _params(sig: str) -> list[str]:
    """Parameter names from 'self, a: T = [..], b: U = x) -> R:' — split on top-level commas."""
    out, depth, cur, quote = [], 0, "", None
    for ch in sig:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                out.append(cur)
                break
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(cur); cur = ""
            continue
        cur += ch
    names = [re.match(r"\s*\**(\w+)", part).group(1) for part in out if re.match(r"\s*\**(\w+)", part)]
    return [n for n in names if n != "self"]


def index(version: str, download: bool) -> dict | None:
    cached = CACHE / f"index-{version}.json"
    src = stub_path(version, download)
    if src is None:
        return None
    if cached.exists() and cached.stat().st_mtime >= src.stat().st_mtime:
        return json.loads(cached.read_text())
    print(f"indexing UE {version} stub ({src.stat().st_size / 1e6:.0f} MB) …", flush=True)
    # line-based: the stub is machine-written and regular, but some default values nest too deep for ast
    module, classes = set(), {}
    current = None
    re_class = re.compile(r"^class (\w+)\((.*?)\):")
    re_def = re.compile(r"^def (\w+)\(")
    re_mdef = re.compile(r"^    def (\w+)\((.*)")
    re_attr = re.compile(r"^    (\w+)\s*:\s*[\w\[\], .]+\s*(?:=|#|$)")   # 5.6: "X: T = ... #: 0"; 5.4/5.5: "X: T #: 0"
    re_var = re.compile(r"^(\w+)\s*[:=]")
    for line in src.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line or line[0] == "#":
            continue
        if line[0] not in " \t":
            m = re_class.match(line)
            if m:
                current = {"bases": [b.strip().split(".")[-1] for b in m.group(2).split(",") if b.strip()],
                           "members": set(), "init": [], "editor": set()}
                classes[m.group(1)] = current
                module.add(m.group(1))
                continue
            current = None
            m = re_def.match(line) or re_var.match(line)
            if m:
                module.add(m.group(1))
            continue
        if current is None:
            continue
        m = re_mdef.match(line)
        if m:
            current["members"].add(m.group(1))
            if m.group(1) == "__init__":
                current["init"] = _params(m.group(2))
            continue
        m = re_attr.match(line)
        if m:
            current["members"].add(m.group(1))
            continue
        for name in _EDITOR_PROP.findall(line):
            current["editor"].add(name)
            current["members"].add(name)
    for c in classes.values():
        c["members"] = sorted(c["members"]); c["editor"] = sorted(c["editor"])
    data = {"module": sorted(module), "classes": classes}
    cached.write_text(json.dumps(data))
    return data


class Api:
    def __init__(self, version: str, data: dict):
        self.version = version
        self.module = set(data["module"])
        self.classes = data["classes"]
        self.all_members = set()
        self.editor_props = set()
        for c in self.classes.values():
            self.all_members.update(c["members"])
            self.editor_props.update(c["editor"])

    def members(self, cls: str) -> set:
        out, todo, seen = set(), [cls], set()
        while todo:
            c = todo.pop()
            if c in seen or c not in self.classes:
                continue
            seen.add(c)
            out.update(self.classes[c]["members"])
            todo.extend(self.classes[c]["bases"])
        return out

    def init_params(self, cls: str) -> list | None:
        todo, seen = [cls], set()
        while todo:
            c = todo.pop(0)
            if c in seen or c not in self.classes:
                continue
            seen.add(c)
            if self.classes[c]["init"]:
                return self.classes[c]["init"]
            todo.extend(self.classes[c]["bases"])
        return None


# ----------------------------------------------------------------------------
# plugin scan
# ----------------------------------------------------------------------------

def _unreal_chain(node) -> list[str] | None:
    """unreal.A.B.c → ['A', 'B', 'c']"""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name) and node.id == "unreal":
        return list(reversed(parts))
    return None


def scan(path: Path, apis: list[Api]) -> list[str]:
    tree = ast.parse(path.read_text())
    problems: list[str] = []
    guarded_module = {n.args[1].value for n in ast.walk(tree)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "hasattr"
                      and len(n.args) == 2 and isinstance(n.args[0], ast.Name) and n.args[0].id == "unreal"
                      and isinstance(n.args[1], ast.Constant)}
    own_names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}

    def where(node):
        return f"{path.name}:{node.lineno}"

    for node in ast.walk(tree):
        # unreal.X / unreal.Class.member
        if isinstance(node, ast.Attribute):
            chain = _unreal_chain(node)
            if chain and (not isinstance(getattr(node, "_parent", None), ast.Attribute)):
                head = chain[0]
                present = [a.version for a in apis if head in a.module]
                if not present:
                    problems.append(f"{where(node)}: unreal.{head} does not exist in UE {', '.join(a.version for a in apis)}")
                elif len(present) < len(apis) and head not in guarded_module:
                    problems.append(f"{where(node)}: unreal.{head} only in UE {', '.join(present)} — guard with hasattr(unreal, '{head}')")
                if len(chain) >= 2 and present:
                    for a in apis:
                        if head in a.module and head in a.classes and chain[1] not in a.members(head):
                            problems.append(f"{where(node)}: unreal.{head}.{chain[1]} missing in UE {a.version}")
        # constructor keywords
        if isinstance(node, ast.Call):
            chain = _unreal_chain(node.func)
            if chain and len(chain) == 1 and node.keywords:
                for a in apis:
                    params = a.init_params(chain[0])
                    if params is None:
                        continue
                    for kw in node.keywords:
                        if kw.arg and kw.arg not in params:
                            problems.append(f"{where(node)}: unreal.{chain[0]}({kw.arg}=…) — UE {a.version} parameters are {params}")
            # set/get_editor_property("name")
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("set_editor_property", "get_editor_property") \
                    and node.args and isinstance(node.args[0], ast.Constant):
                prop = node.args[0].value
                missing = [a.version for a in apis if prop not in a.editor_props and prop not in a.all_members]
                if missing:
                    problems.append(f"{where(node)}: editor property '{prop}' unknown in UE {', '.join(missing)}")
            # _set(obj, "a", v, "b", …): one of the names must exist in each version
            if isinstance(node.func, ast.Name) and node.func.id == "_set" and len(node.args) >= 3:
                names = [a.value for i, a in enumerate(node.args) if i in (1,) or i >= 3 if isinstance(a, ast.Constant)]
                for a in apis:
                    if not any(n in a.all_members for n in names):
                        problems.append(f"{where(node)}: none of {names} exists in UE {a.version}")
        # obj.attr on non-unreal receivers: must exist somewhere in the API
        if isinstance(node, ast.Attribute) and _unreal_chain(node) is None:
            recv = node.value
            base = recv
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name) and base.id in {"os", "sys", "subprocess", "argparse", "ap", "args", "p", "raw", "json"}:
                continue
            if isinstance(base, ast.Constant) or node.attr in PY_ATTRS or node.attr in own_names:
                continue
            missing = [a.version for a in apis if node.attr not in a.all_members]
            if len(missing) == len(apis):
                problems.append(f"{where(node)}: .{node.attr} is not a member of any Unreal class")
    return sorted(set(problems))


def _link_parents(tree):
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versions", default="5.4,5.5,5.6")
    ap.add_argument("--download", action="store_true", help="download missing stubs (~25 MB each)")
    args = ap.parse_args()
    apis = []
    for v in args.versions.split(","):
        data = index(v.strip(), args.download)
        if data is None:
            print(f"· UE {v}: no stub in {CACHE} (run with --download)")
            continue
        apis.append(Api(v.strip(), data))
    if not apis:
        print("✗ no Unreal stubs available")
        return 2
    # parent links for the chain check
    orig_parse = ast.parse

    def parse_with_parents(src, *a, **kw):
        t = orig_parse(src, *a, **kw)
        _link_parents(t)
        return t
    ast.parse = parse_with_parents
    total = 0
    for path in sorted(PLUGIN.glob("*.py")):
        problems = scan(path, apis)
        total += len(problems)
        print(f"{'✓' if not problems else '✗'} {path.name}: checked against UE {', '.join(a.version for a in apis)}"
              + (f" — {len(problems)} problems" if problems else ""))
        for pr in problems:
            print(f"    ✗ {pr}")
    print("Result: " + ("every Unreal name the plugin uses exists." if total == 0 else f"{total} problems."))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
