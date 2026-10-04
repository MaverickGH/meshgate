#!/usr/bin/env python3
"""MeshGate example pack "Zombie Cats" (samples/packs/zombie_cats) — the stylized kit models, as the engines use them.

    python3 sources/generate/make_zombie_cats_pack.py [--out samples/packs/zombie_cats] [--blender PATH] [--tiers …]

Every asset is built by `meshgate.py gen` from the stylized kit code in examples/zombie_cats/stylized (the same models
as the styles lineup, docs/img/zc-styles-lineup.jpg): all quality tiers, collision proxies for the static props, FBX
and the engine variants. Then Blender lays them out on a small street (sources/blender/make_zombie_cats_diorama.py):
zc_diorama.glb with every clip, and its tier files within each tier's scene budget. index.json has the shape the web
viewer, Unity, Godot and Unreal tests read.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = HERE / "examples" / "zombie_cats"
# asset → (collision for the static props, title)
ASSETS = {
    "zc_ground_tile": (None, "Ground tile (paw prints)"),
    "zc_road_tile": (None, "Road tile (fish marks)"),
    "zc_fence_broken": ("box", "Broken fence (cat-ear pickets)"),
    "zc_tombstone_cat": ("convex", "Cat tombstone"),
    "zc_dead_tree": ("convex", "Dead tree + yarn"),
    "zc_cardboard_barricade": ("box", "Box barricade (hiding cat)"),
    "zc_toxic_can": ("convex", "Toxic cat food can"),
    "zc_street_lamp": ("convex", "Fish street lamp"),
    "zc_bones_pile": (None, "Fish bones"),
    "zc_scratch_post_ruin": ("convex", "Ruined scratching post"),
    "zc_zombie_cat": (None, "Zombie cat (Humanoid, idle/shamble)"),
}
TIERS = "mobile-low,mobile-mid,mobile-high,pc"


def validate(path: Path, *extra) -> dict:
    out = subprocess.run([sys.executable, str(ROOT / "core" / "validate_glb.py"), str(path), "--json", *extra],
                         capture_output=True, text=True).stdout
    rep = json.loads(out)
    return rep[0] if isinstance(rep, list) else rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "samples" / "packs" / "zombie_cats"))
    ap.add_argument("--blender")
    ap.add_argument("--tiers", default=TIERS, help="quality tiers to build (pc is the canonical file)")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    sizes = {f"zc_{k}": v[0] for k, v in json.loads((SRC / "assets.json").read_text(encoding="utf-8")).items()}
    sys.path.insert(0, str(ROOT))
    import meshgate
    blender = args.blender or meshgate.find_blender()
    if not blender:
        print("MeshGate pack: Blender not found (--blender or MESHGATE_BLENDER)")
        return 2
    for old in list(out.glob("*.glb")) + list(out.glob("*.fbx")) + list(out.glob("*.blend*")) + list(out.glob("index.json")):
        old.unlink()   # the READMEs stay
    index, ok = [], True
    with tempfile.TemporaryDirectory() as tmp:
        blends = Path(tmp) / "blends"
        blends.mkdir()
        for name, (collision, title) in ASSETS.items():
            work = Path(tmp) / name
            cmd = [sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(SRC / "stylized" / f"{name[3:]}.py"),
                   "--name", name, "--style", "stylized", "--size", str(sizes[name]), "--tiers", args.tiers,
                   "--collision", collision or "none", "--blender", blender, "--no-preview", "--out-dir", str(work)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            try:
                g = json.loads((work / "gen.json").read_text(encoding="utf-8"))
            except OSError:
                print(f"  ✗ {name}: no result\n{(r.stdout + r.stderr)[-1500:]}")
                ok = False
                continue
            rep = g["report"]
            ok &= bool(rep.get("ok"))
            for f in rep.get("files", []):
                shutil.copyfile(work / f, out / f)
            if rep.get("blend"):
                shutil.copyfile(work / rep["blend"], blends / f"{name}.blend")
            canon = rep["tiers"][rep["canonical"]]
            v = validate(out / f"{name}.glb")
            index.append({
                "file": f"{name}.glb", "title": title, "kind": "asset", "made_with": "kit, stylized",
                "fbx": f"{name}.fbx" if f"{name}.fbx" in rep["files"] else None,
                "tris": canon["tris"], "clips": sorted(v.get("animations", [])), "dims_m": v.get("dims_m"),
                "bones": v.get("joints", 0),
                "variants": [f for f in rep["files"] if f != f"{name}.glb" and ".mobile-" not in f],
                "tiers": {t: {"file": e["file"], "tris": e["tris"], "within_budget": e["within_budget"]}
                          for t, e in rep["tiers"].items() if t != rep["canonical"]},
            })
            tiers = ", ".join(f"{t} {e['tris']:,}" for t, e in rep["tiers"].items())
            print(f"  {'✓' if rep.get('ok') else '✗'} {name:24} {tiers}" + ("" if rep.get("ok") else
                  "\n      " + "; ".join(rep.get("problems", []))[:600]))
        # the diorama: every asset on a small street, as linked duplicates, with all their clips
        res = Path(tmp) / "diorama.json"
        r = subprocess.run([blender, "-b", "--factory-startup", "-P", str(ROOT / "sources" / "blender" / "make_zombie_cats_diorama.py"),
                            "--", "--blends", str(blends), "--out", str(out), "--tiers", args.tiers, "--result", str(res)],
                           capture_output=True, text=True)
        try:
            dio = json.loads(res.read_text(encoding="utf-8"))
        except OSError:
            print("  ✗ zc_diorama: no result\n" + (r.stdout + r.stderr)[-2000:])
            return 1
        ok &= dio["ok"]
        v = validate(out / "zc_diorama.glb")
        index.append({"file": "zc_diorama.glb", "title": "Diorama: zombie cat street", "kind": "scene", "fbx": None,
                      "tris": v.get("triangles"), "clips": sorted(v.get("animations", [])), "dims_m": v.get("dims_m"),
                      "bones": v.get("joints", 0), "variants": [], "tiers": dio["tiers"]})
        print(f"  {'✓' if dio['ok'] else '✗'} {'zc_diorama':24} " + ", ".join(f"{t} {e['tris']:,}" for t, e in dio["tiers"].items())
              + f", pc {v.get('triangles', 0):,}; clips {sorted(v.get('animations', []))}" + ("" if dio["ok"] else f"\n      {dio.get('problems')}"))
    (out / "index.json").write_text(json.dumps({"pack": "zombie_cats", "title": "Zombie Cats", "canonical_detail": "pc",
                                                "assets": index}, indent=2) + "\n", encoding="utf-8")
    size = sum(f.stat().st_size for f in out.iterdir() if f.is_file()) / 2 ** 20
    print(f"Result: {len(index)} assets in {out} ({size:.1f} MB) — "
          + ("every asset satisfies the contract and its tier budgets." if ok else "some assets have issues."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
