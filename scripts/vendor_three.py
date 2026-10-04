#!/usr/bin/env python3
"""Copy the three.js files the MeshGate viewer imports into apps/studio/ui/vendor/three, so Studio works offline.

    python3 scripts/vendor_three.py [--version 0.169.0]

Follows the viewer's imports recursively (three/addons/... and their relative imports) and downloads each module once
from jsDelivr. The Studio server serves /three/... from this folder and falls back to the CDN for anything missing.
The desktop build runs this before bundling. Pure stdlib.
"""

import argparse
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "targets" / "web" / "meshgate-viewer.js"
OUT = ROOT / "apps" / "studio" / "ui" / "vendor" / "three"
IMPORT_RE = re.compile(r"""(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\s*['"]([^'"]+)['"]""")


def specifiers(text: str):
    for m in IMPORT_RE.finditer(text):
        yield m.group(1) or m.group(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="0.169.0")
    args = ap.parse_args()
    cdn = f"https://cdn.jsdelivr.net/npm/three@{args.version}/"
    todo, seen = ["build/three.module.js"], set()
    for spec in specifiers(VIEWER.read_text(encoding="utf-8")):
        if spec.startswith("three/addons/"):
            todo.append("examples/jsm/" + spec[len("three/addons/"):])
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen.add(rel)
        dest = OUT / rel
        if not dest.exists():
            with urllib.request.urlopen(cdn + rel, timeout=60) as r:
                data = r.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        text = dest.read_text(encoding="utf-8", errors="replace")
        base = rel.rsplit("/", 1)[0]
        for spec in specifiers(text):
            if spec == "three":
                continue
            if spec.startswith("three/addons/"):
                todo.append("examples/jsm/" + spec[len("three/addons/"):])
            elif spec.startswith("."):
                parts = (base + "/" + spec).split("/")
                norm = []
                for p in parts:
                    if p == "..":
                        norm.pop()
                    elif p not in (".", ""):
                        norm.append(p)
                todo.append("/".join(norm))
    (OUT / "VERSION").write_text(args.version + "\n")
    size = sum(f.stat().st_size for f in OUT.rglob("*.js"))
    print(f"three.js {args.version}: {len(seen)} modules, {size / 1e6:.1f} MB → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
