"""MeshGate example pack — "Zombie Cats": a cute-apocalypse location kit built entirely by script.

    blender -b -P sources/blender/make_pack_zombie_cats.py -- --out-dir samples/packs/zombie_cats [--no-export]

How real stylized packs are made, and what MeshGate checks:
  • one 256×256 palette texture and one PBR material (`zc_atlas`) for the whole pack — every face samples a
    flat colour cell, so each prop is one mesh and one draw call; glowing parts use `zc_glow` / `zc_lamp`;
  • every prop is its own asset (`zc_*.glb` + `.fbx`), origin on the ground, meters, ASCII names;
  • static props get collision proxies (UCX_ for Unreal, -convcolonly for Godot) via the MeshGate add-on code;
  • `zc_zombie_cat` is a rigged biped on the Unity Humanoid skeleton (+ tail bones) with `idle` and `shamble`;
  • `zc_diorama.glb` places everything on a small street — instanced tiles, fences and three cats.

Writes <out>/zombie_cats.blend and, unless --no-export, every asset through meshgate_blender.export (same code as the
add-on panel) with the validator; prints the in-Blender contract check for each asset.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import bpy
except ImportError:
    print("Run inside Blender: blender -b -P <this file> -- --out-dir samples/packs/zombie_cats")
    sys.exit(2)

import argparse
import json
import math
import os
import random
import tempfile

import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshgate_blender import checks, compat, export, tools  # noqa: E402

FPS = 30
CELLS = 8                 # palette: 8×8 colour cells
PALETTE = {               # name → (index, sRGB colour)
    "grass": (0, (0.36, 0.55, 0.28)), "grass_dead": (1, (0.56, 0.56, 0.30)), "dirt": (2, (0.42, 0.30, 0.20)),
    "asphalt": (3, (0.22, 0.22, 0.25)), "road_paint": (4, (0.95, 0.82, 0.32)), "wood": (5, (0.64, 0.46, 0.28)),
    "wood_dark": (6, (0.38, 0.25, 0.15)), "cardboard": (7, (0.74, 0.57, 0.36)), "stone": (8, (0.58, 0.58, 0.62)),
    "stone_dark": (9, (0.36, 0.36, 0.40)), "fur": (10, (0.55, 0.64, 0.52)), "fur_dark": (11, (0.36, 0.44, 0.35)),
    "pink": (12, (0.96, 0.60, 0.66)), "bone": (13, (0.93, 0.91, 0.83)), "black": (14, (0.07, 0.07, 0.09)),
    "metal": (15, (0.62, 0.64, 0.68)), "rust": (16, (0.56, 0.30, 0.18)), "yarn": (17, (0.88, 0.26, 0.32)),
    "goo": (18, (0.45, 0.96, 0.30)), "label": (19, (0.52, 0.36, 0.72)), "fish": (20, (0.40, 0.62, 0.88)),
    "lamp": (21, (1.00, 0.86, 0.42)), "bark": (22, (0.30, 0.22, 0.18)), "moss": (23, (0.30, 0.46, 0.25)),
    "bandage": (24, (0.91, 0.86, 0.76)), "tape": (25, (0.52, 0.40, 0.24)), "carpet": (26, (0.70, 0.45, 0.62)),
    "rope": (27, (0.80, 0.68, 0.48)), "muzzle": (28, (0.80, 0.84, 0.76)),
}
MATS: dict = {}
# Level of detail per quality tier: the budget is a target, not only a ceiling — build as much shape as the tier affords
# instead of decimating a single model. seg = factor for round segment counts (≥ 8), subdiv = added subdivision levels.
DETAILS = {
    "mobile-low":  {"seg": 0.5,  "subdiv": -1, "bevel": 1, "grid": 5},
    "mobile-mid":  {"seg": 1.0,  "subdiv": 0,  "bevel": 2, "grid": 9},
    "mobile-high": {"seg": 1.5,  "subdiv": 0,  "bevel": 2, "grid": 13},
    "pc":          {"seg": 2.0,  "subdiv": 1,  "bevel": 3, "grid": 17},
}
DETAIL = dict(DETAILS["pc"])


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="samples/packs/zombie_cats")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--seed", type=int, default=9)
    ap.add_argument("--detail", default="pc", choices=list(DETAILS), help="detail of the canonical files (default pc = full quality)")
    ap.add_argument("--tiers", default="mobile-low,mobile-mid,mobile-high",
                    help="also rebuild the pack at each tier's detail → zc_*.<tier>.glb, validated against the tier budget ('' = none)")
    return ap.parse_args(argv)


# ----------------------------------------------------------------------------
# palette + materials
# ----------------------------------------------------------------------------

def make_materials(tmp: str):
    size, cell = 256, 256 // CELLS
    img = np.ones((size, size, 4), dtype=np.float32)
    for _, (i, rgb) in PALETTE.items():
        cx, cy = i % CELLS, i // CELLS
        # Blender images are stored bottom-up: row 0 is the bottom of the texture
        y0 = cy * cell
        img[y0:y0 + cell, cx * cell:(cx + 1) * cell, :3] = rgb
    # subtle vertical gradient inside each cell: hand-painted feel, still flat at the UV point we sample
    ramp = np.linspace(0.92, 1.05, cell, dtype=np.float32)[:, None, None]
    for cy in range(CELLS):
        img[cy * cell:(cy + 1) * cell, :, :3] *= ramp
    img[..., :3] = np.clip(img[..., :3], 0, 1)
    image = bpy.data.images.new("zc_palette", size, size, alpha=True)
    image.pixels.foreach_set(img.ravel())
    image.filepath_raw = os.path.join(tmp, "zc_palette.png"); image.file_format = "PNG"; image.save(); image.pack()
    image.filepath_raw = "//textures/zc_palette.png"

    atlas = bpy.data.materials.new("zc_atlas"); atlas.use_nodes = True
    b = compat.principled(atlas)
    tex = atlas.node_tree.nodes.new("ShaderNodeTexImage"); tex.image = image; tex.interpolation = "Closest"
    atlas.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.82
    MATS["atlas"] = atlas

    for name, rgb, strength in (("zc_glow", (0.35, 1.0, 0.15), 1.8), ("zc_lamp", (1.0, 0.8, 0.35), 3.0)):   # stays coloured after tone mapping
        m = bpy.data.materials.new(name); m.use_nodes = True
        b = compat.principled(m)
        b.inputs["Base Color"].default_value = (*rgb, 1)
        compat.set_input(b, "Emission", (*rgb, 1))
        b.inputs["Emission Strength"].default_value = strength
        b.inputs["Roughness"].default_value = 0.4
        MATS[name.replace("zc_", "")] = m


def cell_uv(color: str) -> tuple[float, float]:
    i = PALETTE[color][0]
    return ((i % CELLS) + 0.5) / CELLS, ((i // CELLS) + 0.5) / CELLS


def paint(obj, color: str, material: str = "atlas") -> None:
    """Whole object → one palette cell (all UVs on the cell centre) and one material."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    u, v = cell_uv(color)
    for loop in me.uv_layers.active.data:
        loop.uv = (u, v)
    me.materials.clear()
    me.materials.append(MATS[material])


def paint_faces(obj, pick) -> None:
    """Per-face colour: pick(face_index, face_center) → palette name."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    for poly in me.polygons:
        u, v = cell_uv(pick(poly.index, poly.center))
        for li in poly.loop_indices:
            uv[li].uv = (u, v)
    me.materials.clear()
    me.materials.append(MATS["atlas"])


# ----------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"; s.unit_settings.scale_length = 1.0
    s.render.fps = FPS; s.frame_start, s.frame_end = 1, 60
    s.cursor.location = (0, 0, 0)


def _apply_mods(obj):
    ctx = bpy.context
    for m in list(obj.modifiers):
        with ctx.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
            bpy.ops.object.modifier_apply(modifier=m.name)


def part(kind: str, color: str, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), smooth=True, subdiv=0, bevel=0.0,
         material="atlas", taper=None, **kw):
    """One coloured piece: primitive → transform applied → optional bevel/subdivision applied → painted."""
    def seg(n):
        return max(6, round(n * DETAIL["seg"])) if isinstance(n, int) and n >= 8 else n
    for key in ("segments", "ring_count", "vertices", "major_segments", "minor_segments"):
        if key in kw:
            kw[key] = seg(kw[key])
    if subdiv:
        subdiv = max(0, subdiv + DETAIL["subdiv"])
    op = {"cube": bpy.ops.mesh.primitive_cube_add, "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
          "ico": bpy.ops.mesh.primitive_ico_sphere_add, "cyl": bpy.ops.mesh.primitive_cylinder_add,
          "cone": bpy.ops.mesh.primitive_cone_add, "torus": bpy.ops.mesh.primitive_torus_add,
          "plane": bpy.ops.mesh.primitive_plane_add, "grid": bpy.ops.mesh.primitive_grid_add}[kind]
    defaults = {"cube": {"size": 1.0}, "sphere": {"segments": seg(16), "ring_count": seg(10), "radius": 0.5},
                "ico": {"subdivisions": 1, "radius": 0.5}, "cyl": {"vertices": seg(12), "radius": 0.5, "depth": 1.0},
                "cone": {"vertices": seg(12), "radius1": 0.5, "radius2": 0.0, "depth": 1.0}}.get(kind, {})
    op(location=(0, 0, 0), rotation=(0, 0, 0), **{**defaults, **kw})
    obj = bpy.context.active_object
    if taper is not None:  # scale top ring (z > 0) by taper factor
        for v in obj.data.vertices:
            if v.co.z > 0:
                v.co.x *= taper; v.co.y *= taper
    obj.scale = scale
    obj.rotation_euler = rot
    obj.location = loc
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if bevel:
        m = obj.modifiers.new("bevel", "BEVEL"); m.width = bevel; m.segments = DETAIL["bevel"]; m.limit_method = "ANGLE"
    if subdiv:
        m = obj.modifiers.new("subsurf", "SUBSURF"); m.levels = subdiv; m.render_levels = subdiv
    _apply_mods(obj)
    for p in obj.data.polygons:
        p.use_smooth = smooth
    paint(obj, color, material)
    return obj


def join(name: str, parts: list, parent=None):
    """Join parts into one mesh named `name`, origin at the world origin (the asset's ground point)."""
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name; obj.data.name = name
    loc = obj.matrix_world.translation.copy()
    obj.location = (0, 0, 0)
    for v in obj.data.vertices:
        v.co += loc
    if parent is not None:
        obj.parent = parent
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=loc)
    e = bpy.context.active_object; e.name = name
    if parent is not None:
        e.parent = parent
    return e


def keyframes(obj, clip: str, keys, path="rotation_euler", interpolation="BEZIER"):
    obj.animation_data_create()
    obj.animation_data.action = bpy.data.actions.new(clip)
    obj.rotation_mode = "XYZ"
    for frame, value in keys:
        setattr(obj, path, value); obj.keyframe_insert(path, frame=frame)
    compat.set_interpolation(obj.animation_data.action, interpolation, "EASE_IN_OUT" if interpolation == "BEZIER" else None)
    compat.push_to_nla(obj, clip)


def collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    layer_coll = bpy.context.view_layer.layer_collection.children[name]
    bpy.context.view_layer.active_layer_collection = layer_coll
    return coll


# ----------------------------------------------------------------------------
# assets
# ----------------------------------------------------------------------------

def ground_tile(rng):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=DETAIL["grid"], y_subdivisions=DETAIL["grid"], size=2.0, location=(0, 0, 0))
    g = bpy.context.active_object
    for v in g.data.vertices:
        edge = max(abs(v.co.x), abs(v.co.y)) > 0.99
        v.co.z = 0.0 if edge else rng.uniform(0.0, 0.035)   # borders flat so tiles line up
    noise = {i: rng.random() for i in range(len(g.data.polygons))}
    paint_faces(g, lambda i, c: "grass" if noise[i] < 0.62 else ("grass_dead" if noise[i] < 0.86 else "dirt"))
    for p in g.data.polygons:
        p.use_smooth = False
    parts = [g]
    for _ in range(3):  # paw prints: pad + 4 toes
        x, y = rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7)
        parts.append(part("cyl", "dirt", (x, y, 0.036), (0.09, 0.075, 0.006), vertices=10, smooth=False))
        for dx, dy in ((-0.06, 0.07), (-0.02, 0.1), (0.02, 0.1), (0.06, 0.07)):
            parts.append(part("cyl", "dirt", (x + dx, y + dy, 0.036), (0.035, 0.035, 0.006), vertices=8, smooth=False))
    return join("zc_ground_tile", parts)


def road_tile(rng):
    parts = [part("cube", "asphalt", (0, 0, 0.025), (2.0, 2.0, 0.05), smooth=False)]
    for x in (-0.6, 0.4):  # fish-shaped lane marks along X
        parts.append(part("sphere", "road_paint", (x, 0, 0.052), (0.34, 0.12, 0.008), segments=12, ring_count=6))
        parts.append(part("cone", "road_paint", (x - 0.24, 0, 0.052), (0.12, 0.16, 0.008), rot=(0, math.pi / 2, 0), vertices=3, smooth=False))
    for _ in range(4):  # cracks
        parts.append(part("cube", "black", (rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), 0.051),
                          (rng.uniform(0.2, 0.5), 0.02, 0.004), rot=(0, 0, rng.uniform(0, math.pi)), smooth=False))
    return join("zc_road_tile", parts)


def fence(rng):
    parts = []
    for x in (-0.95, 0.95):
        parts.append(part("cube", "wood_dark", (x, 0, 0.55), (0.1, 0.1, 1.1), bevel=0.01, smooth=False))
    for z in (0.35, 0.8):
        parts.append(part("cube", "wood_dark", (0, 0, z), (1.9, 0.05, 0.08), bevel=0.01, smooth=False))
    for i, x in enumerate((-0.6, -0.3, 0.0, 0.3, 0.6)):
        if i == 3:  # broken picket lying on the ground
            parts.append(part("cube", "wood", (0.35, 0.35, 0.04), (0.14, 0.72, 0.03), rot=(0, 0, 0.5), bevel=0.01, smooth=False))
            parts.append(part("cube", "wood", (x, 0.04, 0.3), (0.14, 0.03, 0.5), rot=(0.25, 0, 0), bevel=0.01, smooth=False))
            continue
        h = 0.95 + rng.uniform(-0.05, 0.05)
        parts.append(part("cube", "wood", (x, 0.04, h / 2), (0.14, 0.03, h), bevel=0.01, smooth=False))
        for ex in (-0.045, 0.045):  # cat ears on top of every picket
            parts.append(part("cone", "wood", (x + ex, 0.04, h + 0.05), (0.045, 0.02, 0.1), vertices=4, smooth=False))
    for dx in (-0.08, 0.0, 0.08):  # fish bone decoration nailed to a post
        parts.append(part("cyl", "bone", (0.95 + dx * 0.3, -0.07, 0.9 + dx), (0.01, 0.01, 0.12), rot=(0, 0, 0), vertices=6))
    return join("zc_fence_broken", parts)


def tombstone(rng):
    parts = [part("cube", "stone_dark", (0, 0, 0.06), (0.7, 0.4, 0.12), bevel=0.02, smooth=False)]
    parts.append(part("cube", "stone", (0, 0, 0.5), (0.5, 0.14, 0.8), bevel=0.04, subdiv=1, smooth=True))
    for x in (-0.15, 0.15):
        parts.append(part("cone", "stone", (x, 0, 0.98), (0.12, 0.06, 0.2), vertices=4, rot=(0, 0, math.pi / 4), smooth=False))
    parts.append(part("cyl", "stone_dark", (0, -0.075, 0.5), (0.09, 0.075, 0.02), rot=(math.pi / 2, 0, 0), vertices=12))
    for dx, dz in ((-0.07, 0.09), (-0.025, 0.12), (0.025, 0.12), (0.07, 0.09)):
        parts.append(part("cyl", "stone_dark", (dx, -0.075, 0.5 + dz), (0.03, 0.03, 0.02), rot=(math.pi / 2, 0, 0), vertices=8))
    for _ in range(3):
        parts.append(part("ico", "moss", (rng.uniform(-0.28, 0.28), rng.uniform(-0.18, 0.18), 0.12), (0.12, 0.1, 0.05), subdivisions=1))
    return join("zc_tombstone_cat", parts)


def dead_tree(rng):
    root = empty("zc_dead_tree")
    parts = [part("cone", "bark", (0, 0, 1.2), (0.28, 0.28, 2.4), radius1=0.5, radius2=0.18, vertices=9, smooth=False)]
    for ang, z, l in ((0.3, 1.6, 1.0), (2.4, 2.0, 0.8), (4.3, 1.3, 0.9)):
        d = Vector((math.cos(ang), math.sin(ang), 0.7)).normalized()
        c = Vector((0, 0, z)) + d * (l / 2)
        parts.append(part("cone", "bark", tuple(c), (0.08, 0.08, l), radius1=0.5, radius2=0.15, vertices=6,
                          rot=d.to_track_quat("Z", "Y").to_euler(), smooth=False))
    for ang in (0.0, 2.1, 4.2):
        parts.append(part("cone", "bark", (math.cos(ang) * 0.25, math.sin(ang) * 0.25, 0.08), (0.12, 0.35, 0.16),
                          rot=(0, 0, ang), vertices=5, smooth=False))
    trunk = join("tree_trunk", parts, root)
    d = Vector((math.cos(0.3), math.sin(0.3), 0.7)).normalized()
    tip = Vector((0, 0, 1.6)) + d * 0.85
    pivot = empty("yarn_pivot", tuple(tip), root)
    string = part("cyl", "yarn", (tip.x, tip.y, tip.z - 0.3), (0.008, 0.008, 0.6), vertices=6)
    ball = part("sphere", "yarn", (tip.x, tip.y, tip.z - 0.68), (0.16, 0.16, 0.16), segments=12, ring_count=8)
    yarn = join("yarn_ball", [string, ball])
    yarn.parent = pivot
    yarn.matrix_parent_inverse = pivot.matrix_world.inverted()
    keyframes(pivot, "yarn_swing", [(1, (0.25, 0, 0)), (30, (-0.25, 0, 0)), (60, (0.25, 0, 0))])
    return root, trunk


def barricade(rng):
    parts = []
    boxes = [((-0.45, 0, 0.25), (0.6, 0.55, 0.5)), ((0.2, 0.05, 0.3), (0.7, 0.6, 0.6)), ((0.8, -0.05, 0.2), (0.45, 0.5, 0.4)),
             ((-0.2, 0.0, 0.78), (0.55, 0.5, 0.45)), ((0.45, 0.05, 0.85), (0.4, 0.45, 0.5))]
    for i, (loc, size) in enumerate(boxes):
        rot = (0, 0, rng.uniform(-0.15, 0.15))
        parts.append(part("cube", "cardboard", loc, size, rot=rot, bevel=0.015, smooth=False))
        parts.append(part("cube", "tape", (loc[0], loc[1], loc[2] + size[2] / 2), (size[0] * 1.01, 0.08, 0.01), rot=rot, smooth=False))
    # a zombie cat hiding in the top box: ears + glowing eyes
    for x in (0.36, 0.54):
        parts.append(part("cone", "fur", (x, 0.02, 1.16), (0.07, 0.05, 0.14), vertices=4, smooth=False))
    for x in (0.4, 0.5):
        parts.append(part("sphere", "goo", (x, -0.2, 1.06), (0.035, 0.02, 0.035), material="glow", segments=8, ring_count=6))
    return join("zc_cardboard_barricade", parts)


def toxic_can(rng):
    root = empty("zc_toxic_can")
    parts = [part("cyl", "metal", (0, 0, 0.35), (0.5, 0.5, 0.7), vertices=16, bevel=0.01)]
    parts.append(part("cyl", "label", (0, 0, 0.35), (0.51, 0.51, 0.42), vertices=16))
    parts.append(part("sphere", "fish", (0, -0.255, 0.36), (0.16, 0.02, 0.08), segments=12, ring_count=6))
    parts.append(part("cone", "fish", (0.13, -0.255, 0.36), (0.06, 0.02, 0.08), rot=(0, math.pi / 2, 0), vertices=3, smooth=False))
    parts.append(part("cyl", "metal", (0.18, 0.1, 0.78), (0.5, 0.5, 0.02), rot=(0.9, 0.3, 0), vertices=16, smooth=False))
    parts.append(part("cyl", "goo", (0, 0, 0.705), (0.46, 0.46, 0.02), vertices=16, material="glow"))
    body = join("can_body", parts, root)
    puddle = [part("sphere", "goo", (rng.uniform(-0.45, 0.45), rng.uniform(-0.45, 0.45), 0.0), (0.35, 0.25, 0.04),
                   material="glow", segments=10, ring_count=6) for _ in range(4)]
    join("goo_puddle", puddle, root)
    for i, (x, y) in enumerate(((0.1, 0.05), (-0.12, 0.1), (0.02, -0.14))):
        b = part("sphere", "goo", (0, 0, 0), (0.07, 0.07, 0.07), material="glow", segments=8, ring_count=6)
        b.name = b.data.name = f"bubble_{i}"
        b.parent = root
        b.location = (x, y, 0.72)
        keyframes(b, "bubbles", [(1 + i * 10, (x, y, 0.72)), (31 + i * 10, (x, y, 1.1)), (32 + i * 10, (x, y, 0.72))],
                  path="location", interpolation="LINEAR")
    return root, body


def street_lamp(rng):
    root = empty("zc_street_lamp")
    parts = [part("cyl", "metal", (0, 0, 0.08), (0.36, 0.36, 0.16), vertices=10, bevel=0.01)]
    parts.append(part("cyl", "metal", (0, 0, 1.55), (0.09, 0.09, 3.0), vertices=8))
    parts.append(part("cyl", "rust", (0, 0, 0.9), (0.1, 0.1, 0.2), vertices=8))
    parts.append(part("cyl", "metal", (0.35, 0, 3.02), (0.06, 0.06, 0.8), rot=(0, math.pi / 2 - 0.3, 0), vertices=8))
    pole = join("lamp_pole", parts, root)
    pivot = empty("lamp_pivot", (0.72, 0, 3.05), root)
    fish = [part("sphere", "fish", (0.72, 0, 2.86), (0.42, 0.2, 0.2), segments=14, ring_count=8),
            part("cone", "fish", (1.0, 0, 2.86), (0.16, 0.05, 0.2), rot=(0, math.pi / 2, 0), vertices=3, smooth=False),
            part("sphere", "lamp", (0.72, 0, 2.78), (0.3, 0.14, 0.08), material="lamp", segments=12, ring_count=6),
            part("sphere", "black", (0.58, -0.09, 2.9), (0.04, 0.02, 0.04), segments=8, ring_count=6),
            part("cyl", "metal", (0.72, 0, 2.99), (0.02, 0.02, 0.14), vertices=6)]
    head = join("lamp_head", fish)
    head.parent = pivot
    head.matrix_parent_inverse = pivot.matrix_world.inverted()
    keyframes(pivot, "swing", [(1, (0.12, 0, 0)), (30, (-0.12, 0, 0)), (60, (0.12, 0, 0))])
    return root, pole


def bones_pile(rng):
    parts = []
    for k in range(3):
        cx, cy, ang = rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), rng.uniform(0, math.pi)
        d = Vector((math.cos(ang), math.sin(ang), 0))
        parts.append(part("cyl", "bone", (cx, cy, 0.03), (0.02, 0.02, 0.4), rot=(0, math.pi / 2, ang), vertices=6))
        parts.append(part("cone", "bone", tuple(Vector((cx, cy, 0.04)) + d * 0.24), (0.08, 0.05, 0.12),
                          rot=(0, math.pi / 2, ang), vertices=6))
        for t in (-0.12, -0.04, 0.04, 0.12):
            p = Vector((cx, cy, 0.03)) + d * t
            parts.append(part("cyl", "bone", tuple(p), (0.008, 0.008, 0.14), rot=(0, math.pi / 2, ang + math.pi / 2), vertices=5))
    return join("zc_bones_pile", parts)


def scratch_post(rng):
    parts = [part("cube", "carpet", (0, 0, 0.04), (0.6, 0.6, 0.08), bevel=0.02, smooth=False)]
    parts.append(part("cyl", "rope", (0, 0, 0.5), (0.18, 0.18, 0.9), vertices=10))
    for z in np.linspace(0.12, 0.9, 8):
        parts.append(part("torus", "rope", (0, 0, float(z)), (1, 1, 1), major_radius=0.095, minor_radius=0.012,
                          major_segments=12, minor_segments=5))
    parts.append(part("cube", "carpet", (0.12, 0.05, 0.98), (0.45, 0.45, 0.06), rot=(0.35, -0.2, 0.2), bevel=0.02, smooth=False))
    parts.append(part("cube", "carpet", (-0.45, 0.25, 0.06), (0.4, 0.4, 0.06), rot=(0.1, 0.25, 0.4), bevel=0.02, smooth=False))
    return join("zc_scratch_post_ruin", parts)


# ----------------------------------------------------------------------------
# zombie cat: biped on the Unity Humanoid skeleton (+ tail), idle + shamble
# ----------------------------------------------------------------------------

CAT_BONES = {  # chibi proportions, height ≈ 1.0 m, faces -Y, left hand +X
    "Hips": ((0, 0, 0.42), (0, 0, 0.48), None), "Spine": ((0, 0, 0.48), (0, 0, 0.56), "Hips"),
    "Chest": ((0, 0, 0.56), (0, 0, 0.64), "Spine"), "Neck": ((0, 0, 0.64), (0, 0, 0.68), "Chest"),
    "Head": ((0, 0, 0.68), (0, 0, 0.98), "Neck"),
    "LeftShoulder": ((0.03, 0, 0.62), (0.1, 0, 0.62), "Chest"), "LeftUpperArm": ((0.1, 0, 0.62), (0.22, 0, 0.62), "LeftShoulder"),
    "LeftLowerArm": ((0.22, 0, 0.62), (0.33, 0, 0.62), "LeftUpperArm"), "LeftHand": ((0.33, 0, 0.62), (0.39, 0, 0.62), "LeftLowerArm"),
    "RightShoulder": ((-0.03, 0, 0.62), (-0.1, 0, 0.62), "Chest"), "RightUpperArm": ((-0.1, 0, 0.62), (-0.22, 0, 0.62), "RightShoulder"),
    "RightLowerArm": ((-0.22, 0, 0.62), (-0.33, 0, 0.62), "RightUpperArm"), "RightHand": ((-0.33, 0, 0.62), (-0.39, 0, 0.62), "RightLowerArm"),
    "LeftUpperLeg": ((0.07, 0, 0.42), (0.07, 0, 0.24), "Hips"), "LeftLowerLeg": ((0.07, 0, 0.24), (0.07, 0, 0.06), "LeftUpperLeg"),
    "LeftFoot": ((0.07, 0, 0.06), (0.07, -0.08, 0.02), "LeftLowerLeg"), "LeftToes": ((0.07, -0.08, 0.02), (0.07, -0.12, 0.02), "LeftFoot"),
    "RightUpperLeg": ((-0.07, 0, 0.42), (-0.07, 0, 0.24), "Hips"), "RightLowerLeg": ((-0.07, 0, 0.24), (-0.07, 0, 0.06), "RightUpperLeg"),
    "RightFoot": ((-0.07, 0, 0.06), (-0.07, -0.08, 0.02), "RightLowerLeg"), "RightToes": ((-0.07, -0.08, 0.02), (-0.07, -0.12, 0.02), "RightFoot"),
    "Tail1": ((0, 0.08, 0.44), (0, 0.18, 0.46), "Hips"), "Tail2": ((0, 0.18, 0.46), (0, 0.26, 0.56), "Tail1"),
    "Tail3": ((0, 0.26, 0.56), (0, 0.28, 0.68), "Tail2"),
}


def _seg(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length


def zombie_cat(rng):
    root = empty("zc_zombie_cat")
    P = []
    # head (big, chibi), ears, muzzle, nose, glowing eyes, stitches
    P.append(part("sphere", "fur", (0, 0, 0.83), (0.34, 0.3, 0.28), segments=18, ring_count=12, subdiv=1))
    for sx in (1, -1):
        P.append(part("cone", "fur", (sx * 0.1, 0.02, 1.0), (0.09, 0.06, 0.13), rot=(0, sx * -0.3, 0), vertices=6))
        P.append(part("cone", "pink", (sx * 0.1, 0.0, 0.99), (0.05, 0.03, 0.08), rot=(0, sx * -0.3, 0), vertices=6))
        P.append(part("sphere", "goo", (sx * 0.075, -0.135, 0.86), (0.05, 0.03, 0.055), material="glow", segments=10, ring_count=6))
        for k in range(3):  # whiskers
            P.append(part("cyl", "black", (sx * 0.12, -0.14, 0.77 + (k - 1) * 0.015), (0.003, 0.003, 0.1), rot=(0, math.pi / 2 + sx * (k - 1) * 0.2, 0), vertices=4))
    P.append(part("sphere", "muzzle", (0, -0.13, 0.77), (0.13, 0.07, 0.08), segments=12, ring_count=8))
    P.append(part("sphere", "pink", (0, -0.165, 0.8), (0.03, 0.02, 0.022), segments=8, ring_count=6))
    for dx in (-0.06, -0.02, 0.02, 0.06):  # stitches across the forehead
        P.append(part("cube", "black", (dx + 0.04, -0.13, 0.94), (0.008, 0.01, 0.05), smooth=False))
    P.append(part("cube", "black", (0.04, -0.13, 0.94), (0.14, 0.01, 0.008), smooth=False))
    # body
    P.append(part("sphere", "fur", (0, 0, 0.53), (0.26, 0.22, 0.3), segments=14, ring_count=10, subdiv=1))
    P.append(part("sphere", "muzzle", (0, -0.075, 0.52), (0.15, 0.08, 0.18), segments=12, ring_count=8))
    P.append(part("cube", "black", (-0.05, -0.105, 0.55), (0.008, 0.01, 0.12), rot=(0, 0.3, 0), smooth=False))
    for sx in (1, -1):
        # arms (T-pose), paws, bandage on the right arm
        P.append(part("cyl", "fur", (sx * 0.22, 0, 0.62), (0.075, 0.075, 0.26), rot=(0, math.pi / 2, 0), vertices=10, subdiv=1))
        P.append(part("sphere", "muzzle", (sx * 0.37, 0, 0.62), (0.07, 0.065, 0.06), segments=10, ring_count=6))
        if sx < 0:
            P.append(part("cyl", "bandage", (sx * 0.26, 0, 0.62), (0.085, 0.085, 0.06), rot=(0, math.pi / 2, 0), vertices=10))
        # legs, feet
        P.append(part("cyl", "fur_dark", (sx * 0.07, 0, 0.26), (0.095, 0.095, 0.46), vertices=10, subdiv=1))   # reaches into the body
        P.append(part("sphere", "muzzle", (sx * 0.07, -0.04, 0.045), (0.09, 0.13, 0.06), segments=10, ring_count=6))
    # tail (3 segments following the tail bones)
    for a, b in (("Tail1", 0), ("Tail2", 0), ("Tail3", 0)):
        h, t, _ = CAT_BONES[a]
        h, t = Vector(h), Vector(t)
        d = t - h
        P.append(part("cyl", "fur_dark" if a == "Tail3" else "fur", tuple((h + t) / 2), (0.05, 0.05, d.length + 0.03),
                      rot=d.to_track_quat("Z", "Y").to_euler(), vertices=8))
    body = join("zombie_cat_body", P)

    arm_data = bpy.data.armatures.new("zombie_cat_rig")
    arm = bpy.data.objects.new("zombie_cat_rig", arm_data)
    bpy.context.collection.objects.link(arm)
    arm.parent = root
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    for n, (h, t, _) in CAT_BONES.items():
        b = arm_data.edit_bones.new(n); b.head, b.tail = Vector(h), Vector(t); eb[n] = b
    for n, (_, _, parent) in CAT_BONES.items():
        if parent:
            eb[n].parent = eb[parent]
    bpy.ops.object.mode_set(mode="OBJECT")

    groups = {n: body.vertex_groups.new(name=n) for n in CAT_BONES}
    segs = {n: (Vector(h), Vector(t)) for n, (h, t, _) in CAT_BONES.items()}
    for v in body.data.vertices:
        p = v.co
        if p.z > 0.68:   # the whole head follows the Head bone (rigid, cartoon-style)
            groups["Head"].add([v.index], 1.0, "REPLACE"); continue
        d = sorted(((_seg(p, *segs[n]), n) for n in segs), key=lambda x: x[0])
        (d1, n1), (d2, n2) = d[0], d[1]
        if d2 - d1 < 0.03:
            w = 0.5 + 0.5 * (d2 - d1) / 0.03
            groups[n1].add([v.index], w, "REPLACE"); groups[n2].add([v.index], 1 - w, "REPLACE")
        else:
            groups[n1].add([v.index], 1.0, "REPLACE")
    mod = body.modifiers.new("rig", "ARMATURE"); mod.object = arm
    body.parent = arm

    # animations on bones
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"

    def axis_towards(bone, direction, deg=60):
        """Local axis + sign whose rotation moves the bone's tail most along `direction` (world)."""
        pb = arm.pose.bones[bone]
        base = (arm.matrix_world @ pb.tail).copy()
        best = None
        for axis in range(3):
            for sign in (1.0, -1.0):
                r = [0.0, 0.0, 0.0]; r[axis] = sign * math.radians(deg)
                pb.rotation_euler = r; bpy.context.view_layer.update()
                gain = ((arm.matrix_world @ pb.tail) - base).dot(Vector(direction))
                if best is None or gain > best[0]:
                    best = (gain, axis, sign)
        pb.rotation_euler = (0, 0, 0); bpy.context.view_layer.update()
        return best[1], best[2]

    def rot(axis_sign, deg):
        r = [0.0, 0.0, 0.0]; r[axis_sign[0]] = axis_sign[1] * math.radians(deg); return tuple(r)

    fwd = (0, -1, 0)
    arms_fwd = {s: axis_towards(f"{s}UpperArm", fwd) for s in ("Left", "Right")}
    legs_fwd = {s: axis_towards(f"{s}UpperLeg", fwd) for s in ("Left", "Right")}
    arms_down = {s: axis_towards(f"{s}UpperArm", (0, 0, -1)) for s in ("Left", "Right")}
    head_tilt = axis_towards("Head", (1, 0, 0), 20)
    tail_side = axis_towards("Tail2", (1, 0, 0), 30)
    chest_fwd = axis_towards("Chest", fwd, 20)
    pbs = arm.pose.bones

    def clip(name, frames, pose_at):
        arm.animation_data_create()
        arm.animation_data.action = bpy.data.actions.new(name)
        for f in frames:
            for bone, value in pose_at(f).items():
                pbs[bone].rotation_euler = value
                pbs[bone].keyframe_insert("rotation_euler", frame=f)
        compat.set_interpolation(arm.animation_data.action, "BEZIER", "EASE_IN_OUT")
        compat.push_to_nla(arm, name)

    def idle(f):
        k = math.sin((f - 1) / 60 * math.tau)
        return {"Head": rot(head_tilt, 8 * k), "Tail2": rot(tail_side, 25 * k), "Tail3": rot(tail_side, 30 * k),
                "Chest": rot(chest_fwd, 3 * k),
                "LeftUpperArm": rot(arms_down[("Left")], 55 + 4 * k), "RightUpperArm": rot(arms_down["Right"], 55 - 4 * k)}

    def shamble(f):
        k = math.sin((f - 1) / 60 * math.tau)
        return {"LeftUpperArm": rot(arms_fwd["Left"], 80 + 6 * k), "RightUpperArm": rot(arms_fwd["Right"], 80 - 6 * k),
                "LeftUpperLeg": rot(legs_fwd["Left"], 22 * k), "RightUpperLeg": rot(legs_fwd["Right"], -22 * k),
                "Chest": rot(chest_fwd, 10 + 4 * abs(k)), "Head": rot(head_tilt, 12 * k),
                "Tail2": rot(tail_side, 20 * k), "Tail3": rot(tail_side, -25 * k)}

    clip("idle", [1, 16, 31, 46, 61], idle)
    clip("shamble", [1, 16, 31, 46, 61], shamble)
    bpy.ops.object.mode_set(mode="OBJECT")
    return root, body


# ----------------------------------------------------------------------------
# pack + diorama
# ----------------------------------------------------------------------------

STATIC_COLLISION = {"zc_fence_broken": "BOX", "zc_tombstone_cat": "CONVEX", "zc_cardboard_barricade": "BOX",
                    "zc_scratch_post_ruin": "CONVEX", "tree_trunk": "CONVEX", "lamp_pole": "CONVEX", "can_body": "CONVEX"}
TITLES = {
    "zc_ground_tile": "Ground tile (paw prints)", "zc_road_tile": "Road tile (fish marks)", "zc_fence_broken": "Broken fence (cat-ear pickets)",
    "zc_tombstone_cat": "Cat tombstone", "zc_dead_tree": "Dead tree + yarn", "zc_cardboard_barricade": "Box barricade (hiding cat)",
    "zc_toxic_can": "Toxic cat food can", "zc_street_lamp": "Fish street lamp", "zc_bones_pile": "Fish bones",
    "zc_scratch_post_ruin": "Ruined scratching post", "zc_zombie_cat": "Zombie cat (Humanoid, idle/shamble)", "zc_diorama": "Diorama: zombie cat street",
}


def build_pack(rng) -> dict:
    """Each asset in its own collection at the origin. Returns name → collection."""
    colls = {}
    for name, fn in (("zc_ground_tile", ground_tile), ("zc_road_tile", road_tile), ("zc_fence_broken", fence),
                     ("zc_tombstone_cat", tombstone), ("zc_dead_tree", dead_tree), ("zc_cardboard_barricade", barricade),
                     ("zc_toxic_can", toxic_can), ("zc_street_lamp", street_lamp), ("zc_bones_pile", bones_pile),
                     ("zc_scratch_post_ruin", scratch_post), ("zc_zombie_cat", zombie_cat)):
        colls[name] = collection(name)
        fn(rng)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection
    for obj in list(bpy.context.scene.objects):
        shape = STATIC_COLLISION.get(obj.name)
        if shape:
            tools.add_collision(bpy.context, [obj], shape)
    return colls


def build_diorama(colls: dict):
    """Linked duplicates of the pack on a 4×4-tile street (8 × 8 m): road across the middle, fences, props, cats."""
    dio = collection("zc_diorama")
    root = empty("zc_diorama")

    def place(asset, loc, rot_z=0.0, name=None):
        src_objs = [o for o in colls[asset].objects if not o.get("meshgate_collision_for")]
        mapping = {}
        for o in src_objs:
            c = o.copy()   # linked duplicate: shares mesh/armature data and actions
            dio.objects.link(c)
            mapping[o] = c
        for o, c in mapping.items():
            c.parent = mapping.get(o.parent)
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()   # assigning .parent resets it in Blender
            for m in c.modifiers:
                if m.type == "ARMATURE" and m.object in mapping:
                    m.object = mapping[m.object]
        top = [c for o, c in mapping.items() if o.parent not in mapping]
        for t in top:
            t.parent = root
            t.location = Vector(loc) + t.location
            t.rotation_euler.z += rot_z
            if name:
                t.name = name
        return top

    k = 0
    for ix in range(4):
        for iy in range(4):
            x, y = -3 + ix * 2, -3 + iy * 2
            place("zc_road_tile" if iy == 1 else "zc_ground_tile", (x, y, 0), name=f"tile_{ix}_{iy}")
            k += 1
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
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection
    return dio


def select_collection(coll):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in coll.all_objects:
        if not o.get("meshgate_collision_for"):
            o.select_set(True)


def build(detail: str, seed: int, tmp: str):
    """Fresh scene at the given detail: palette, every asset, collision proxies, diorama."""
    DETAIL.clear(); DETAIL.update(DETAILS[detail])
    reset()
    make_materials(tmp)
    colls = build_pack(random.Random(seed))
    dio = build_diorama(colls)
    return colls, dio


def export_all(colls, dio, out: str, suffix: str = "", profile: str | None = None, engine_variants: bool = True):
    """Export every asset (+ diorama) with the in-Blender check; suffix/profile for quality-tier variants."""
    rows, ok = [], True
    for name, coll in list(colls.items()) + [("zc_diorama", dio)]:
        select_collection(coll)
        issues = [i for i in checks.run_checks(bpy.context, selection_only=True) if i.severity != checks.INFO]
        is_dio = name == "zc_diorama"
        glb = os.path.join(out, f"{name}{suffix}.glb")
        res = export.export_asset(bpy.context, glb, selection=True,
                                  targets=[] if (is_dio or not engine_variants) else ["unity", "godot", "unreal"],
                                  fbx=engine_variants and not is_dio)
        rep = res.reports[0]
        if profile:
            rep = export.validate_file(glb, profile=profile, kind="scene" if is_dio else "asset")
        good = rep.get("ok", False) and all(r.get("ok") for r in res.reports[1:]) and not issues
        ok &= good
        budget = rep.get("budget")
        print(f"  {'✓' if good else '✗'} {name + suffix:36} {rep.get('triangles', 0):>7,} tris  {len(rep.get('animations', []))} clips  "
              f"{rep.get('joints', 0):>2} bones" + (f"  {budget['label']}: {'within budget' if budget['ok'] else 'OVER BUDGET'}" if budget else ""))
        for i in issues:
            print(f"      ⚠ [{i.code}] {i.label()}")
        for w in rep.get("warnings", []):
            print(f"      ⚠ {w}")
        rows.append((name, rep, [os.path.basename(f) for f in res.files[1:]]))
    return rows, ok


def main():
    args = _args()
    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)
    tiers = [t.strip() for t in args.tiers.split(",") if t.strip() and t.strip() != args.detail]
    with tempfile.TemporaryDirectory() as tmp:
        colls, dio = build(args.detail, args.seed, tmp)
        blend = os.path.join(out, "zombie_cats.blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
        print(f"MeshGate pack: {blend} — {len(colls)} assets + diorama, detail {args.detail}, {len(bpy.data.materials)} materials, "
              f"{len(bpy.data.actions)} actions, palette 256² ({len(PALETTE)} colours)")
        if args.no_export:
            return 0
        rows, ok = export_all(colls, dio, out)
        index = {name: {"file": f"{name}.glb", "title": TITLES[name], "kind": "scene" if name == "zc_diorama" else "asset",
                        "fbx": None if name == "zc_diorama" else f"{name}.fbx",
                        "tris": rep.get("triangles"), "clips": rep.get("animations", []), "dims_m": rep.get("dims_m"),
                        "bones": rep.get("joints", 0), "variants": variants, "tiers": {}}
                 for name, rep, variants in rows}
        for tier in tiers:
            print(f"— tier {tier} (detail {DETAILS[tier]}) —")
            colls, dio = build(tier, args.seed, tmp)
            tier_rows, tier_ok = export_all(colls, dio, out, suffix=f".{tier}", profile=tier, engine_variants=False)
            ok &= tier_ok
            for name, rep, _ in tier_rows:
                index[name]["tiers"][tier] = {"file": f"{name}.{tier}.glb", "tris": rep.get("triangles"),
                                              "within_budget": bool(rep.get("budget", {}).get("ok"))}
    json.dump({"pack": "zombie_cats", "title": "Zombie Cats", "canonical_detail": args.detail, "assets": list(index.values())},
              open(os.path.join(out, "index.json"), "w"), indent=2)
    print("Result: " + ("every asset satisfies the contract and its tier budgets." if ok else "some assets have issues."))
    return 0 if ok else 1


if __name__ == "__main__":
    code = main()
    if code:
        sys.exit(code)
