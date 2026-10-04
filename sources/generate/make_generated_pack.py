#!/usr/bin/env python3
"""MeshGate example pack "Generated" — assets made by `meshgate.py gen`, so the engine checks cover generation too.

    python3 sources/generate/make_generated_pack.py [--out samples/packs/generated] [--live-triposr] [--blender PATH]

Five assets come from kit code in sources/generate/examples (written by AI models from the MeshGate prompt: from text,
and one from a picture); one comes from a picture through TripoSR. The TripoSR output is committed
(examples/hydrant_triposr_raw.glb), so the pack rebuilds on any machine; --live-triposr regenerates it from
examples/hydrant_picture.png first. Writes index.json in the same shape as the Zombie Cats pack, which the web viewer,
Unity, Godot and Unreal tests read.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EX = HERE / "examples"
# name → (title, how it is made, gen arguments)
ASSETS = {
    "gen_windmill": ("Windmill — kit code from text", "kit, text",
                     ["--code", str(EX / "windmill.py")]),
    "gen_street_lamp": ("Street lamp — kit code from text", "kit, text",
                        ["--code", str(EX / "street_lamp.py"), "--style", "realistic", "--texture", "1k"]),
    "gen_fire_hydrant": ("Fire hydrant — kit code", "kit, hand-written example",
                         ["--code", str(EX / "fire_hydrant.py"), "--collision", "convex"]),
    "gen_treasure_chest": ("Treasure chest — kit code, opening lid", "kit, hand-written example",
                           ["--code", str(EX / "treasure_chest.py"), "--collision", "box"]),
    "gen_toxic_can": ("Toxic can — kit code from a picture", "kit, picture",
                      ["--code", str(EX / "toxic_can.py"), "--image", str(EX / "toxic_can_picture.png")]),
    "gen_hydrant_photo": ("Hydrant — TripoSR from a picture", "mesh, TripoSR",
                          ["--mesh", str(EX / "hydrant_triposr_raw.glb"), "--image", str(EX / "hydrant_picture.png"),
                           "--size", "0.8", "--targets", "web,godot", "--collision", "convex"]),
    "gen_toxic_can_vertex": ("Toxic can — kit code, vertex colours, no textures", "kit, vertex colours",
                             ["--code", str(EX / "toxic_can.py"), "--colors", "vertex"]),
    "gen_forest_glade": ("Forest glade — kit code, instanced trees and fence", "kit, instances",
                         ["--code", str(EX / "forest_glade.py")]),
    "gen_hydrant_lowpoly": ("Hydrant — TripoSR, own limits 300–3,000 tris, vertex colours", "mesh, vertex colours, own limits",
                            ["--mesh", str(EX / "hydrant_triposr_raw.glb"), "--image", str(EX / "hydrant_picture.png"),
                             "--size", "0.8", "--tris", "low=300,mid=800,high=1500,pc=3000", "--colors", "vertex",
                             "--targets", "web"]),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "samples" / "packs" / "generated"))
    ap.add_argument("--blender")
    ap.add_argument("--live-triposr", action="store_true", help="regenerate the TripoSR mesh from the picture first")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    extra = ["--blender", args.blender] if args.blender else []
    if args.live_triposr:
        sys.path.insert(0, str(HERE))
        from mesh import triposr
        with tempfile.TemporaryDirectory() as tmp:
            raw = triposr.generate(image=str(EX / "hydrant_picture.png"), prompt=None, out_dir=Path(tmp))
            shutil.copyfile(raw, EX / "hydrant_triposr_raw.glb")
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("*.glb")) + list(out.glob("*.fbx")) + list(out.glob("index.json")):   # README stays
        old.unlink()
    index, ok = [], True
    with tempfile.TemporaryDirectory() as tmp:
        for name, (title, how, gen_args) in ASSETS.items():
            work = Path(tmp) / name
            cmd = [sys.executable, str(ROOT / "meshgate.py"), "gen", *gen_args, "--name", name, "--no-preview",
                   "--out-dir", str(work), *extra]
            r = subprocess.run(cmd, capture_output=True, text=True)
            try:
                g = json.loads((work / "gen.json").read_text())
            except OSError:
                print(f"  ✗ {name}: no result\n{(r.stdout + r.stderr)[-1500:]}")
                ok = False
                continue
            rep = g["report"]
            if not rep.get("ok"):
                ok = False
                print(f"  ✗ {name}: " + "; ".join(rep.get("problems", []))[:800])
            for f in rep.get("files", []):
                shutil.copyfile(work / f, out / f)
            canon = rep["tiers"][rep["canonical"]]
            index.append({
                "file": f"{name}.glb", "title": title, "kind": "asset", "made_with": how, "colors": g.get("colors", "texture"),
                "caps": g.get("caps") or None,
                "fbx": f"{name}.fbx" if f"{name}.fbx" in rep["files"] else None,
                "tris": canon["tris"], "clips": canon.get("clips", []), "dims_m": canon.get("dims_m"), "bones": 0,
                "variants": [f for f in rep["files"] if f != f"{name}.glb" and ".mobile-" not in f],
                "tiers": {t: {"file": e["file"], "tris": e["tris"], "within_budget": e["within_budget"]}
                          for t, e in rep["tiers"].items() if t != rep["canonical"]},
            })
            tiers = ", ".join(f"{t} {e['tris']:,}" for t, e in rep["tiers"].items())
            print(f"  {'✓' if rep.get('ok') else '✗'} {name:20} {how:26} {tiers}")
    # sizes as engines see them (glTF: x, y-up, z), straight from the validator — the same as the Zombie Cats index
    for a in index:
        rep = json.loads(subprocess.run([sys.executable, str(ROOT / "core" / "validate_glb.py"), str(out / a["file"]), "--json"],
                                        capture_output=True, text=True).stdout)
        rep = rep[0] if isinstance(rep, list) else rep
        a["dims_m"], a["bones"] = rep.get("dims_m"), rep.get("joints", 0)
    (out / "index.json").write_text(json.dumps({"pack": "generated", "title": "Generated with meshgate.py gen",
                                                "canonical_detail": "pc", "assets": index}, indent=2) + "\n")
    top = ROOT / "samples" / "index.json"
    meta = json.loads(top.read_text())
    if not any(p.get("path") == "packs/generated" for p in meta.get("packs", [])):
        meta.setdefault("packs", []).append({"title": "Generated pack (meshgate.py gen)", "path": "packs/generated"})
        top.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    size = sum(f.stat().st_size for f in out.iterdir()) / 2 ** 20
    print(f"Result: {len(index)} generated assets in {out.relative_to(ROOT)} ({size:.1f} MB)"
          + ("" if ok else " — some had problems"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
