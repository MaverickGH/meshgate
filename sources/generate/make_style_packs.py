#!/usr/bin/env python3
"""Zombie Cats in three styles — the same eleven assets as stylized, low-poly and realistic kit models.

    python3 sources/generate/make_style_packs.py [--styles stylized,lowpoly,realistic] [--out out/packs] [--blender PATH]

The build code in examples/zombie_cats/<style>/ was written by an AI (Claude Code) from one description per asset
(examples/zombie_cats/assets.json) and a render of the hand-built Zombie Cats asset as its reference picture, one run
per style. This script only rebuilds that code — no AI — with the style's finish: low-poly is faceted, realistic gets
weathered textures. The packs go to out/packs/zombie_cats_<style> (not committed: the realistic textures alone are
tens of megabytes); docs/img/zc-styles-lineup.jpg shows them side by side. Assets listed in planned.json are not
built yet (organic shapes that need a picture → 3D generator); the pack's index.json lists them under "planned".
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
SRC = HERE / "examples" / "zombie_cats"
STYLES = ["stylized", "lowpoly", "realistic"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--styles", default=",".join(STYLES))
    ap.add_argument("--out", default=str(ROOT / "out" / "packs"))
    ap.add_argument("--blender")
    args = ap.parse_args()
    assets = json.loads((SRC / "assets.json").read_text(encoding="utf-8"))
    planned = json.loads((SRC / "planned.json").read_text(encoding="utf-8"))
    extra = ["--blender", args.blender] if args.blender else []
    ok = True
    for style in args.styles.split(","):
        out = Path(args.out).resolve() / f"zombie_cats_{style}"
        out.mkdir(parents=True, exist_ok=True)
        index = []
        with tempfile.TemporaryDirectory() as tmp:
            for asset, (size, description) in assets.items():
                if asset in planned.get(style, {}):
                    print(f"  · {style:9} {asset:20} planned: {planned[style][asset]}")
                    continue
                name = f"zc_{asset}"
                code = SRC / style / f"{asset}.py"
                work = Path(tmp) / name
                r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(code), "--name", name,
                                    "--style", style, "--size", str(size), "--out-dir", str(work), *extra],
                                   capture_output=True, text=True)
                try:
                    g = json.loads((work / "gen.json").read_text(encoding="utf-8"))
                except OSError:
                    print(f"  ✗ {style}/{asset}: no result\n{(r.stdout + r.stderr)[-1200:]}")
                    ok = False
                    continue
                rep = g["report"]
                ok &= bool(rep.get("ok"))
                for f in rep.get("files", []) + ([rep["preview"]] if rep.get("preview") else []):
                    shutil.copyfile(work / f, out / f)
                canon = rep["tiers"][rep["canonical"]]
                index.append({"file": f"{name}.glb", "title": description.split(":")[0].split(",")[0], "kind": "asset",
                              "made_with": f"kit, {style}, finish {g.get('finish')}", "tris": canon["tris"],
                              "dims_m": canon.get("dims_m"), "clips": canon.get("clips", []), "bones": 0,
                              "fbx": f"{name}.fbx" if f"{name}.fbx" in rep["files"] else None,
                              "variants": [f for f in rep["files"] if f != f"{name}.glb" and ".mobile-" not in f],
                              "tiers": {t: {"file": e["file"], "tris": e["tris"], "within_budget": e["within_budget"]}
                                        for t, e in rep["tiers"].items() if t != rep["canonical"]}})
                tiers = ", ".join(f"{t} {e['tris']:,}" for t, e in rep["tiers"].items())
                print(f"  {'✓' if rep.get('ok') else '✗'} {style:9} {asset:20} {tiers}")
        (out / "index.json").write_text(json.dumps({"pack": f"zombie_cats_{style}", "title": f"Zombie Cats — {style}",
                                                    "canonical_detail": "pc", "assets": index,
                                                    "planned": [{"file": f"zc_{a}.glb", "why": why}
                                                                for a, why in planned.get(style, {}).items()]},
                                                   indent=2) + "\n")
    print("Result: " + ("every style pack built." if ok else "some assets failed."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
