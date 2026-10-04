"""MeshGate — demo asset generator for an end-to-end pipeline check.

Builds a real game asset inside Blender, a "crate with a beacon": a hierarchy
of named objects, PBR materials with procedurally generated textures
(packed into the .blend), a hinged lid and a spinning beacon with two keyframe
animations. Everything follows the asset contract: meters, applied transforms, a meaningful
origin (bottom of the crate), Latin names without spaces.

Headless run:
    blender -b -P sources/blender/make_demo_scene.py -- --blend samples/meshgate_demo.blend

Then the regular pipeline:
    blender -b samples/meshgate_demo.blend -P sources/blender/export_meshgate.py -- --out samples/meshgate_demo.glb --validate
"""

import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import bpy
except ImportError:
    print("This script runs inside Blender: blender -b -P <this file> -- --blend out.blend")
    sys.exit(2)

import argparse
import math
import os
import tempfile

import numpy as np
from mathutils import Vector

# version compatibility (Blender 3.5 … 5.x) lives in the add-on package next to this script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshgate_blender import compat  # noqa: E402

TEX_SIZE = 1024
FPS = 30


# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------

def _args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser(description="MeshGate demo scene")
    ap.add_argument("--blend", required=True, help="where to save the .blend")
    ap.add_argument("--tex-size", type=int, default=TEX_SIZE, help="texture size (power of two)")
    return ap.parse_args(argv)


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = 90


def _value_noise(size: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth noise [0..1] via bilinear interpolation of a random grid."""
    grid = rng.random((cells + 1, cells + 1))
    xs = np.linspace(0, cells, size, endpoint=False)
    x0 = np.floor(xs).astype(int)
    fx = xs - x0
    x1 = np.minimum(x0 + 1, cells)
    rows = grid[x0[:, None], x0[None, :]] * (1 - fx[:, None]) + grid[x1[:, None], x0[None, :]] * fx[:, None]
    rows2 = grid[x0[:, None], x1[None, :]] * (1 - fx[:, None]) + grid[x1[:, None], x1[None, :]] * fx[:, None]
    return rows * (1 - fx[None, :]) + rows2 * fx[None, :]


def _make_image(name: str, rgba: np.ndarray, tmpdir: str, is_data: bool) -> bpy.types.Image:
    """Create an image from an (h, w, 4) float32 [0..1] array, save it as PNG and pack it into the .blend."""
    h, w, _ = rgba.shape
    img = bpy.data.images.new(name, width=w, height=h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    img.filepath_raw = os.path.join(tmpdir, f"{name}.png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    img.filepath_raw = f"//textures/{name}.png"  # packed; exporters need a pseudo-path to tell files apart (FBX)
    return img


def make_textures(size: int, tmpdir: str) -> tuple[bpy.types.Image, bpy.types.Image]:
    """Procedural planks: albedo (sRGB) and a roughness map (Non-Color)."""
    rng = np.random.default_rng(7)
    planks = 6
    y = np.arange(size)[:, None].repeat(size, axis=1)
    x = np.arange(size)[None, :].repeat(size, axis=0)
    plank_id = (y * planks) // size
    # each plank gets its own base tone
    tones = rng.uniform(0.75, 1.15, planks)
    base = np.array([0.55, 0.36, 0.20])  # warm wood
    grain = _value_noise(size, 96, rng) * 0.25 + _value_noise(size, 12, rng) * 0.35
    # grain along X: stretch the noise horizontally
    stretched = _value_noise(size, 48, rng)[:, (np.arange(size) // 8)]  # stretch along X ×8
    fibers = 0.85 + 0.3 * stretched
    color = base[None, None, :] * tones[plank_id][:, :, None] * (0.8 + grain)[:, :, None] * fibers[:, :, None]
    # dark gaps between planks
    edge = ((y * planks) % size) < size * 0.015
    color[edge] *= 0.35
    # nails at the plank corners
    for p in range(planks):
        cy = int((p + 0.5) * size / planks)
        for cx in (int(size * 0.06), int(size * 0.94)):
            rr = (x - cx) ** 2 + (y - cy) ** 2
            color[rr < (size * 0.008) ** 2] = np.array([0.32, 0.32, 0.34])
    albedo = np.concatenate([np.clip(color, 0, 1), np.ones((size, size, 1))], axis=2)

    rough = 0.62 + 0.3 * _value_noise(size, 40, rng) - 0.15 * stretched
    rough[edge] = 0.95
    rough = np.clip(rough, 0.3, 1.0)
    rough_rgba = np.stack([rough, rough, rough, np.ones_like(rough)], axis=2)
    return _make_image("wood_planks_albedo", albedo, tmpdir, False), _make_image("wood_planks_rough", rough_rgba, tmpdir, True)


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------

def _principled(name: str) -> tuple[bpy.types.Material, bpy.types.ShaderNode]:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    return mat, bsdf


def make_materials(albedo: bpy.types.Image, rough: bpy.types.Image) -> dict[str, bpy.types.Material]:
    mats: dict[str, bpy.types.Material] = {}

    wood, bsdf = _principled("wood_planks")
    nt = wood.node_tree
    tex_a = nt.nodes.new("ShaderNodeTexImage"); tex_a.image = albedo; tex_a.location = (-500, 200)
    tex_r = nt.nodes.new("ShaderNodeTexImage"); tex_r.image = rough; tex_r.location = (-500, -150)
    nt.links.new(tex_a.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex_r.outputs["Color"], bsdf.inputs["Roughness"])
    bsdf.inputs["Metallic"].default_value = 0.0
    mats["wood_planks"] = wood

    metal, bsdf = _principled("metal_dark")
    bsdf.inputs["Base Color"].default_value = (0.32, 0.33, 0.36, 1.0)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.38
    mats["metal_dark"] = metal

    beacon, bsdf = _principled("beacon_emissive")
    bsdf.inputs["Base Color"].default_value = (0.05, 0.9, 1.0, 1.0)
    compat.socket(bsdf, "Emission").default_value = (0.1, 0.85, 1.0, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 4.0
    bsdf.inputs["Roughness"].default_value = 0.2
    mats["beacon_emissive"] = beacon

    glass, bsdf = _principled("beacon_glass")
    bsdf.inputs["Base Color"].default_value = (0.8, 0.95, 1.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Alpha"].default_value = 0.22
    compat.set_blend(glass, "BLEND")
    mats["beacon_glass"] = glass
    return mats


# ----------------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------------

def _obj_from_active(name: str, mat: bpy.types.Material, parent=None) -> bpy.types.Object:
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
    return obj


def _shift_mesh(obj: bpy.types.Object, offset: Vector) -> None:
    """Shift vertices so the object origin ends up at the desired point (hinge, bottom)."""
    for v in obj.data.vertices:
        v.co += offset


def _bevel(obj: bpy.types.Object, width: float, segments: int = 2) -> None:
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"


def _smooth(obj: bpy.types.Object) -> None:
    for p in obj.data.polygons:
        p.use_smooth = True


def _box(name, size, location, mat, parent=None, bevel=0.0) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = _obj_from_active(name, mat, parent)
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)  # contract: scale = 1
    if bevel:
        _bevel(obj, bevel)
    return obj


def build_asset(mats: dict[str, bpy.types.Material]) -> bpy.types.Object:
    W, D, H = 0.80, 0.50, 0.45      # crate: width (x), depth (y), height (z) in meters
    LID_H = 0.10
    wall = 0.03

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    root = bpy.context.active_object
    root.name = "meshgate_demo"

    # Body: origin at the bottom center (the asset stands on the floor).
    body = _box("crate_body", (W, D, H), (0, 0, 0), mats["wood_planks"], root, bevel=0.012)
    _shift_mesh(body, Vector((0, 0, H / 2)))
    # cavity on top (the crate interior) — via boolean with an inner cube
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, H / 2 + wall))
    cutter = bpy.context.active_object
    cutter.scale = (W - 2 * wall, D - 2 * wall, H)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    boolean = body.modifiers.new("hollow", "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.object = cutter
    cutter.hide_render = True          # the exporter skips non-renderable objects (use_renderable)
    cutter.display_type = "WIRE"        # can't use hide_viewport: it would drop the boolean operand from the depsgraph
    cutter.name = "_cutter"

    # Metal corners/bands of the body.
    for i, sx in enumerate((-1, 1)):
        band = _box(f"band_{'l' if sx < 0 else 'r'}", (0.05, D + 0.012, H + 0.004), (sx * (W / 2 - 0.10), 0, H / 2), mats["metal_dark"], body, bevel=0.004)
    for i, sx in enumerate((-1, 1)):
        for j, sy in enumerate((-1, 1)):
            _box(f"corner_{i}{j}", (0.06, 0.06, H + 0.004), (sx * (W / 2 - 0.028), sy * (D / 2 - 0.028), H / 2), mats["metal_dark"], body, bevel=0.004)

    # Handles — tori on the sides.
    for sx, suffix in ((-1, "l"), (1, "r")):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.05, minor_radius=0.008, major_segments=32, minor_segments=12,
                                         location=(sx * (W / 2 + 0.008), 0, H * 0.6), rotation=(0, math.pi / 2, 0))
        handle = _obj_from_active(f"handle_{suffix}", mats["metal_dark"], body)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        _smooth(handle)

    # Lid: origin at the rear hinge (y = -D/2, z = H) so the rotation animation is physically correct.
    lid = _box("crate_lid", (W + 0.02, D + 0.02, LID_H), (0, 0, H), mats["wood_planks"], body, bevel=0.012)
    _shift_mesh(lid, Vector((0, D / 2, LID_H / 2)))
    lid.location = (0, -D / 2, H)
    lid_band = _box("lid_band", (W + 0.03, 0.05, LID_H + 0.006), (0, 0, 0), mats["metal_dark"], lid, bevel=0.004)
    _shift_mesh(lid_band, Vector((0, D / 2, LID_H / 2)))
    # hinges
    for sx, suffix in ((-1, "l"), (1, "r")):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.014, depth=0.08, vertices=16,
                                            location=(sx * (W / 2 - 0.12), -D / 2, H), rotation=(0, math.pi / 2, 0))
        hinge = _obj_from_active(f"hinge_{suffix}", mats["metal_dark"], body)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        _smooth(hinge)

    # Beacon on the lid: post + glowing ring (spins) + glass dome.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.06, vertices=24, location=(0, 0, 0))
    post = _obj_from_active("beacon_post", mats["metal_dark"], lid)
    _shift_mesh(post, Vector((0, 0, 0.03)))
    post.location = (0, D / 2, LID_H)  # relative to the lid origin
    _smooth(post)

    bpy.ops.mesh.primitive_torus_add(major_radius=0.045, minor_radius=0.010, major_segments=48, minor_segments=16, location=(0, 0, 0))
    ring = _obj_from_active("beacon_ring", mats["beacon_emissive"], post)
    ring.location = (0, 0, 0.085)
    _smooth(ring)
    # a "notch" on the ring — a secondary mesh so the rotation is visible
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    notch = _obj_from_active("beacon_notch", mats["metal_dark"], ring)
    notch.scale = (0.02, 0.03, 0.026)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    notch.location = (0.045, 0, 0)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, segments=32, ring_count=16, location=(0, 0, 0))
    dome = _obj_from_active("beacon_dome", mats["beacon_glass"], post)
    dome.location = (0, 0, 0.085)
    _smooth(dome)

    return root


# ----------------------------------------------------------------------------
# Animations
# ----------------------------------------------------------------------------

def _action(obj: bpy.types.Object, name: str) -> None:
    obj.animation_data_create()
    obj.animation_data.action = bpy.data.actions.new(name)


def _push_to_nla(obj: bpy.types.Object) -> None:
    """Move the action into an NLA strip of the same name: both the glTF and FBX exporters turn a strip
    into a separate named animation (a "take" in FBX) instead of a single shared "Scene"."""
    ad = obj.animation_data
    action = ad.action
    track = ad.nla_tracks.new()
    track.name = action.name
    strip = track.strips.new(action.name, int(action.frame_range[0]), action)
    strip.name = action.name
    ad.action = None


def animate(root: bpy.types.Object) -> None:
    objs = {o.name: o for o in bpy.data.objects}
    lid = objs["crate_lid"]
    ring = objs["beacon_ring"]

    # lid_open: the lid opens 100° over 1.5 s (frames 1..45), then closes (46..90).
    _action(lid, "lid_open")
    lid.rotation_mode = "XYZ"
    for frame, angle in ((1, 0.0), (45, math.radians(100)), (90, 0.0)):  # +X: lid up
        lid.rotation_euler = (angle, 0, 0)
        lid.keyframe_insert("rotation_euler", frame=frame)
    for fc in compat.fcurves(lid.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.easing = "EASE_IN_OUT"

    # beacon_spin: the ring makes a full turn in 3 s (linear, looped by the runtime).
    _action(ring, "beacon_spin")
    ring.rotation_mode = "XYZ"
    for frame, angle in ((1, 0.0), (90, math.tau)):
        ring.rotation_euler = (0, 0, angle)
        ring.keyframe_insert("rotation_euler", frame=frame)
    for fc in compat.fcurves(ring.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

    _push_to_nla(lid)
    _push_to_nla(ring)


# ----------------------------------------------------------------------------

def main() -> None:
    args = _args()
    reset_scene()
    with tempfile.TemporaryDirectory() as tmp:
        albedo, rough = make_textures(args.tex_size, tmp)
        mats = make_materials(albedo, rough)
        root = build_asset(mats)
        animate(root)
        out = os.path.abspath(args.blend)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
    print(f"MeshGate: demo scene saved -> {out} ({len(meshes)} meshes, {len(bpy.data.actions)} animations, textures {args.tex_size}px)")


if __name__ == "__main__":
    main()
