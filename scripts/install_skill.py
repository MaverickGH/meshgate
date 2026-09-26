#!/usr/bin/env python3
"""Install the MeshGate agent skill.

    python3 scripts/install_skill.py                  # Claude Code: ~/.claude/skills/meshgate
    python3 scripts/install_skill.py --codex          # Codex: $CODEX_HOME/skills/meshgate or ~/.codex/skills/meshgate
    python3 scripts/install_skill.py --dir /some/path # any skills directory

The skill is SKILL.md (+ SKILL.ru.md) and a pointer back to this repository, because the skill drives
meshgate.py, the Blender scripts and the engine projects that live here. Refuses to overwrite an
existing install unless --force is given.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--codex", action="store_true", help="install for Codex instead of Claude Code")
    ap.add_argument("--dir", help="skills directory to install into")
    ap.add_argument("--force", action="store_true", help="replace an existing install")
    args = ap.parse_args()

    if args.dir:
        base = Path(args.dir).expanduser()
    elif args.codex:
        base = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "skills"
    else:
        base = Path("~/.claude/skills").expanduser()
    dest = base / "meshgate"

    if dest.exists():
        if not args.force:
            print(f"✗ {dest} already exists — pass --force to replace it")
            return 1
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    note = (f"\n> Repository: `{ROOT}` — run every `meshgate.py` command from there "
            f"(`cd {ROOT}`). If it has moved, clone https://github.com/MaverickGH/meshgate and reinstall.\n")
    # insert the pointer right after the front matter
    parts = text.split("---", 2)
    text = f"---{parts[1]}---\n{note}{parts[2]}" if len(parts) == 3 else note + text
    (dest / "SKILL.md").write_text(text, encoding="utf-8")
    if (ROOT / "SKILL.ru.md").exists():
        shutil.copy2(ROOT / "SKILL.ru.md", dest / "SKILL.ru.md")
    print(f"✓ MeshGate skill installed → {dest}")
    print("  Start a new agent session so it picks the skill up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
