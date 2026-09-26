#!/usr/bin/env python3
"""Every relative link and image in the repository's Markdown points at a file that exists, and every English page has
its Russian copy (and back). Pure stdlib.

    python3 tests/check_links.py
"""
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"node_modules", "target", "Library", ".git", "out", "vendor", "samples/_local"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def pages():
    for p in ROOT.rglob("*.md"):
        rel = p.relative_to(ROOT).as_posix()
        if any(part in SKIP for part in p.relative_to(ROOT).parts) or rel.startswith("samples/_local") or "/.godot/" in rel:
            continue
        if rel.startswith(("targets/godot/MeshGateDemo/samples/", ".planning/", ".claude/", "sources/generate/prompts/")):
            continue
        yield p


def main() -> int:
    bad, pairs = [], []
    for page in pages():
        text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
        for m in LINK.finditer(text):
            target = m.group(1).split("#")[0]
            if not target or re.match(r"^[a-z]+:", target):
                continue
            if not (page.parent / target).resolve().exists():
                bad.append(f"{page.relative_to(ROOT)}: {m.group(1)}")
        name = page.name
        if name.endswith(".ru.md"):
            twin = page.with_name(name[:-6] + ".md")
        else:
            twin = page.with_name(name[:-3] + ".ru.md")
        if page.parent == ROOT and name in ("SKILL.md", "SKILL.ru.md", "CLAUDE.md", "ONBOARDING.md"):
            pass
        if not twin.exists() and name not in ("CLAUDE.md", "ONBOARDING.md") and "LICENSE" not in name:
            pairs.append(f"{page.relative_to(ROOT)} has no {twin.name}")
    for b in bad:
        print(f"  ✗ broken link {b}")
    for p in pairs:
        print(f"  ✗ {p}")
    count = sum(1 for _ in pages())
    print("Result: " + (f"{count} pages, every link resolves and every page has its translation." if not bad and not pairs
                        else f"{len(bad)} broken links, {len(pairs)} missing translations."))
    return 1 if bad or pairs else 0


if __name__ == "__main__":
    sys.exit(main())
