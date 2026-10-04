#!/usr/bin/env python3
"""Every data-i18n label in the Studio page has a plain string in both languages (not an object, not missing).

    python3 tests/studio/test_ui_strings.py
"""
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
html = (ROOT / "apps" / "studio" / "ui" / "index.html").read_text(encoding="utf-8")
js = (ROOT / "apps" / "studio" / "ui" / "studio.js").read_text(encoding="utf-8")
keys = set(re.findall(r'data-i18n(?:-placeholder)?="([a-z_]+)"', html))
start = js.index("const STRINGS = {")
en = js[js.index("en: {", start):js.index("ru: {", start)]
ru = js[js.index("ru: {", start):js.index("\n};", start)]
fails = []
for lang, block in (("en", en), ("ru", ru)):
    for k in sorted(keys):
        found = re.findall(rf'[\s,{{]{k}: (["`{{\[])', block)   # a repeated key: the last one wins in JavaScript
        if not found:
            fails.append(f"{lang}: '{k}' is missing")
        elif found[-1] not in '"`':
            fails.append(f"{lang}: '{k}' is not a string (the page would show [object Object])")
for f in fails:
    print(f"  ✗ {f}")
print("Result: " + (f"{len(keys)} labels have strings in both languages." if not fails else f"{len(fails)} problems."))
sys.exit(1 if fails else 0)
