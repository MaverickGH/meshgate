#!/usr/bin/env python3
"""Unreal pack import without Unreal: meshgate_import.import_pack runs against a stand-in `unreal` module and must pick
an existing file for every asset of every pack and tier — the tier GLB when asked, UCX_ collision FBX for static
props, the canonical GLB otherwise, Skeletal Mesh for rigged assets.

    python3 tests/unreal/test_pack_import.py
"""
import sys
import types
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
calls = []
fake = types.ModuleType("unreal")
fake.log = fake.log_warning = fake.log_error = lambda *a, **k: None
sys.modules["unreal"] = fake
sys.path.insert(0, str(ROOT / "targets" / "unreal" / "MeshGate" / "Content" / "Python"))
import meshgate_import as mi  # noqa: E402

mi.import_file = lambda src, dest, skeletal=False: calls.append((src, dest, skeletal)) or [dest]
mi._message = lambda *a, **k: None
FAILS = []


def step(name, ok, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


import json  # noqa: E402
for pack in sorted((ROOT / "samples" / "packs").iterdir()):
    index = json.loads((pack / "index.json").read_text())
    for profile in (None, "mobile-low", "mobile-mid", "mobile-high", "pc"):
        calls.clear()
        mi.import_pack(str(pack), profile=profile)
        missing = [c[0] for c in calls if not Path(c[0]).is_file()]
        step(f"{pack.name} / {profile or 'default'}: every asset imported from an existing file",
             len(calls) == len(index["assets"]) and not missing, f"{len(calls)}/{len(index['assets'])} {missing[:2]}")
        if profile in ("mobile-low", "mobile-mid", "mobile-high"):
            step(f"{pack.name} / {profile}: tier variants used", all(f".{profile}.glb" in c[0] for c in calls))
    calls.clear()
    mi.import_pack(str(pack))
    for c in calls:
        name = Path(c[0]).name.split(".")[0]
        entry = next(a for a in index["assets"] if a["file"].startswith(name + "."))
        if int(entry.get("bones") or 0) > 0:
            step(f"{name}: rigged → Skeletal Mesh from the canonical GLB", c[2] and c[0].endswith(f"{name}.glb"))
        elif (pack / f"{name}.unreal.fbx").is_file():
            step(f"{name}: static with collision → .unreal.fbx (UCX_)", c[0].endswith(".unreal.fbx") and not c[2])
print("Result: " + ("pack import picks the right files." if not FAILS else f"{len(FAILS)} failed."))
sys.exit(1 if FAILS else 0)
