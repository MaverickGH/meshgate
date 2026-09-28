"""The Zombie Cats diorama: every asset of the pack on a small street (8 × 8 m), as linked duplicates, with all clips.

    blender -b --factory-startup -P sources/blender/make_zombie_cats_diorama.py -- --blends DIR --out DIR
            [--tiers mobile-low,mobile-mid,mobile-high,pc] [--result diorama.json]

--blends holds <asset>.blend files written by `meshgate.py gen` (sources/generate/make_zombie_cats_pack.py makes
them). Writes <out>/zc_diorama.glb and zc_diorama.<tier>.glb within each tier's scene budget, and a JSON result.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import math
import os

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshgate_blender import export  # noqa: E402

ASSETS = ["zc_ground_tile", "zc_road_tile", "zc_fence_broken", "zc_tombstone_cat", "zc_dead_tree", "zc_cardboard_barricade",
          "zc_toxic_can", "zc_street_lamp", "zc_bones_pile", "zc_scratch_post_ruin", "zc_zombie_cat"]


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blends", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tiers", default="mobile-low,mobile-mid,mobile-high,pc")
    ap.add_argument("--result")
    return ap.parse_args(argv)


def load(blends: str) -> dict:
    """Each asset's objects (collision proxies left out) in a collection of its own. Returns name → top objects."""
    tops = {}
    for name in ASSETS:
        path = os.path.join(blends, f"{name}.blend")
        with bpy.data.libraries.load(path) as (src, dst):
            dst.objects = list(src.objects)
        coll = bpy.data.collections.new(f"src_{name}")
        bpy.context.scene.collection.children.link(coll)
        objs = [o for o in dst.objects if o is not None and not o.get("meshgate_collision_for")]
        for o in objs:
            coll.objects.link(o)
        tops[name] = [o for o in objs if o.parent not in objs]
    return tops


def build(tops: dict):
    dio = bpy.data.collections.new("zc_diorama")
    bpy.context.scene.collection.children.link(dio)
    root = bpy.data.objects.new("zc_diorama", None)
    dio.objects.link(root)

    def place(asset, loc, rot_z=0.0, name=None):
        src = []
        todo = list(tops[asset])
        while todo:
            o = todo.pop()
            src.append(o)
            todo += [c for c in o.children if not c.get("meshgate_collision_for")]
        mapping = {}
        for o in src:
            c = o.copy()   # linked duplicate: shares mesh, armature and actions (NLA tracks = the clips)
            dio.objects.link(c)
            mapping[o] = c
        for o, c in mapping.items():
            if o.parent in mapping:
                c.parent = mapping[o.parent]
                c.matrix_parent_inverse = o.matrix_parent_inverse.copy()   # assigning .parent resets it
            for m in c.modifiers:
                if m.type == "ARMATURE" and m.object in mapping:
                    m.object = mapping[m.object]
        for o in tops[asset]:
            t = mapping[o]
            t.parent = root
            t.location = Vector(loc) + o.location
            t.rotation_euler.z += rot_z
            if name:
                t.name = name
        return mapping

    for ix in range(4):
        for iy in range(4):
            place("zc_road_tile" if iy == 1 else "zc_ground_tile", (-3 + ix * 2, -3 + iy * 2, 0), name=f"tile_{ix}_{iy}")
    for i, x in enumerate((-3, -1, 1, 3)):
        place("zc_fence_broken", (x, 3.9, 0), name=f"fence_n_{i}")
        if i != 2:
            place("zc_fence_broken", (x, -3.9, 0), math.pi, name=f"fence_s_{i}")
    for i, y in enumerate((1, 3)):
        place("zc_fence_broken", (-3.9, y, 0), math.pi / 2, name=f"fence_w_{i}")
    place("zc_street_lamp", (-2.2, -1.1, 0), 0.0, "lamp_0")
    place("zc_street_lamp", (2.4, -2.9, 0), math.pi, "lamp_1")
    place("zc_dead_tree", (-2.5, 2.6, 0), 0.4, "tree_0")
    place("zc_tombstone_cat", (0.6, 3.0, 0), 0.1, "tomb_0")
    place("zc_tombstone_cat", (1.6, 2.7, 0), -0.2, "tomb_1")
    place("zc_tombstone_cat", (2.6, 3.1, 0), 0.25, "tomb_2")
    place("zc_cardboard_barricade", (1.8, -3.1, 0), 0.2, "barricade_0")
    place("zc_toxic_can", (-0.6, 1.6, 0), 0.0, "can_0")
    place("zc_bones_pile", (0.3, 1.3, 0), 0.0, "bones_0")
    place("zc_scratch_post_ruin", (-1.8, 0.9, 0), 0.6, "post_0")
    place("zc_zombie_cat", (-0.3, -1.0, 0), 0.3, "cat_0")
    place("zc_zombie_cat", (1.0, -0.6, 0), -0.4, "cat_1")
    place("zc_zombie_cat", (0.4, 2.2, 0), math.pi, "cat_2")
    return dio, root


def select(coll):
    for o in bpy.context.view_layer.objects:
        o.select_set(o.name in coll.objects)


def main():
    a = _args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tops = load(a.blends)
    dio, root = build(tops)
    bpy.context.view_layer.update()
    profiles = export.load_profiles()["profiles"]
    result = {"ok": True, "tiers": {}, "problems": []}
    select(dio)
    glb = os.path.join(a.out, "zc_diorama.glb")
    res = export.export_asset(bpy.context, glb, selection=True, targets=[], fbx=False, validate=True, strict=True)
    rep = res.reports[0] if res.reports else {}
    if not rep.get("ok", False):
        result["ok"] = False
        result["problems"] += rep.get("errors", []) + rep.get("warnings", [])
    for tier in [t for t in a.tiers.split(",") if t and t != "pc"]:
        path = os.path.join(a.out, f"zc_diorama.{tier}.glb")
        budget = {**profiles[tier]["asset"], "max_tris": profiles[tier]["scene"]["max_tris"]}   # a scene, not one asset
        select(dio)
        objs = export.export_objects(bpy.context, True)
        notes = []
        fmt = budget.get("image_format", "AUTO")
        with export._tier(bpy.context, objs, budget, notes):
            export._gltf(path, selection=True, animations=True, draco=False, image_format=fmt,
                         influences=budget["max_influences"])
        v = export.validate_file(path, profile=tier, kind="scene")
        within = bool(v.get("budget", {}).get("ok"))
        result["ok"] &= bool(v.get("ok")) and within
        if not within:
            result["problems"].append(f"{tier}: {v.get('budget')}")
        result["tiers"][tier] = {"file": os.path.basename(path), "tris": v.get("triangles"), "within_budget": within}
        print(f"DIORAMA {tier} {v.get('triangles')} tris, {v.get('draw_calls')} draw calls, within {within}")
    if a.result:
        with open(a.result, "w", encoding="utf-8") as f:
            json.dump(result, f)
    print("DIORAMA", json.dumps(result)[:500])


if __name__ == "__main__":
    main()
