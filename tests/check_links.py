#!/usr/bin/env python3
"""Every relative link and image in the repository's Markdown points at a file that exists, every #section link points
at a heading that exists (GitHub's anchor rules), and every English page has its Russian copy (and back). Pure stdlib.

    python3 tests/check_links.py
"""
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"node_modules", "target", "Library", ".git", "out", "dist", "runtime", "vendor", "samples/_local"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def pages():
    for p in ROOT.rglob("*.md"):
        if any(part.startswith("._") for part in p.relative_to(ROOT).parts):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(part in SKIP for part in p.relative_to(ROOT).parts) or rel.startswith("samples/_local") or "/.godot/" in rel:
            continue
        if rel.startswith(("targets/godot/MeshGateDemo/samples/", ".planning/", ".claude/", "sources/generate/prompts/")):
            continue
        yield p


def anchors(path: Path) -> set:
    """GitHub's heading anchors: lower case, punctuation dropped (letters of any script kept), spaces to hyphens."""
    out, seen = set(), {}
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    for m in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, flags=re.M):
        heading = re.sub(r"`|\*\*|\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1))
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    return out


def main() -> int:
    bad, pairs = [], []
    for page in pages():
        text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
        for m in LINK.finditer(text):
            target, _, anchor = m.group(1).partition("#")
            if re.match(r"^[a-z]+:", target):
                continue
            dest = (page.parent / target).resolve() if target else page
            if target and not dest.exists():
                bad.append(f"{page.relative_to(ROOT)}: {m.group(1)}")
            elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                bad.append(f"{page.relative_to(ROOT)}: {m.group(1)} (no such section)")
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
