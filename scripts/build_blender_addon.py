#!/usr/bin/env python3
"""Build the MeshGate Blender add-on zip.

    python3 scripts/build_blender_addon.py            # → dist/meshgate-blender-<version>.zip

One zip for every supported Blender:
  • Blender 3.5–4.1: Edit → Preferences → Add-ons → Install… (legacy add-on, uses bl_info)
  • Blender 4.2+:    drag the zip into Blender, or Get Extensions → ⌄ → Install from Disk (uses blender_manifest.toml)
The validator (core/validate_*.py) and the web viewer (targets/web) are bundled, so the add-on works
without a checkout of the repository.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "blender" / "meshgate_blender"


def version() -> str:
    m = re.search(r'^version = "([^"]+)"', (SRC / "blender_manifest.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def build(out_dir: Path) -> Path:
    ver = version()
    bl = re.search(r'"version": \((\d+), (\d+), (\d+)\)', (SRC / "__init__.py").read_text(encoding="utf-8"))
    if bl and ".".join(bl.groups()) != ver:
        sys.exit(f"✗ version mismatch: blender_manifest.toml {ver} vs bl_info {'.'.join(bl.groups())}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"meshgate-blender-{ver}.zip"
    files = {}
    for p in sorted(SRC.rglob("*")):
        if (p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
                and not any(part.startswith("._") for part in p.relative_to(SRC).parts)):
            files[p.relative_to(SRC).as_posix()] = p
    for name in ("validate_glb.py", "validate_fbx.py", "profiles.json"):
        files[f"validator/{name}"] = ROOT / "core" / name
    for name in ("index.html", "app.js", "meshgate-viewer.js"):
        files[f"viewer/{name}"] = ROOT / "targets" / "web" / name
    # the Kit panel: guard rails for build code, the free-model library and its helpers (run in Blender's Python)
    gen = ROOT / "sources" / "generate"
    for arc, src in (("kitlib/safety.py", gen / "safety.py"), ("kitlib/library.py", gen / "library.py"),
                     ("kitlib/keys.py", gen / "keys.py"), ("kitlib/net.py", gen / "mesh" / "net.py"),
                     ("kitlib/render_views.py", gen / "render_views.py")):   # the AI link's rendered views
        files[arc] = src
    files["LICENSE"] = ROOT / "LICENSE"
    # one top-level folder: the legacy installer (3.5–4.1) needs it, and Blender 4.2+ accepts a manifest inside it
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in files.items():
            z.write(src, f"meshgate/{arc}")
    return out


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(ROOT / "dist"))
    args = ap.parse_args()
    out = build(Path(args.out_dir))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    print(f"✓ {out}  ({out.stat().st_size / 1024:.0f} KB, {len(names)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
