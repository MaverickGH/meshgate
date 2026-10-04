"""MeshGate — demo character generator: a rigged humanoid "hero" for checking the skeleton and UV unwrap.

Builds a low-poly mannequin in Blender (1.75 m, T-pose), a skeleton with Unity Humanoid
bone names (Hips, Spine, Chest, Neck, Head, Left/RightShoulder, Left/RightUpperArm …), auto-weights
by nearest bone with smoothing at the joints, a UV unwrap (Smart UV Project), three PBR materials
with a procedural suit texture and two bone animations: `idle` (breathing/swaying) and `wave`
(waves the right hand). Everything follows the contract: meters, origin at the feet, Latin names.

Headless run:
    blender -b -P sources/blender/make_demo_character.py -- --blend samples/meshgate_hero.blend
    blender -b samples/meshgate_hero.blend -P sources/blender/export_meshgate.py -- --out samples/meshgate_hero.glb --fbx --validate
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

FPS = 30
TEX = 1024

# ----------------------------------------------------------------------------
# Skeleton: Unity Humanoid names; the character faces -Y (Blender front), left arm along +X.
# (head, tail) in meters, Z up.
# ----------------------------------------------------------------------------
BONES = {
    "Hips":          ((0, 0, 0.95), (0, 0, 1.05), None),  # noqa
    "Spine":         ((0, 0, 1.05), (0, 0, 1.20), "Hips"),
    "Chest":         ((0, 0, 1.20), (0, 0, 1.42), "Spine"),
    "Neck":          ((0, 0, 1.42), (0, 0, 1.52), "Chest"),
    "Head":          ((0, 0, 1.52), (0, 0, 1.75), "Neck"),
    "LeftShoulder":  ((0.05, 0, 1.40), (0.17, 0, 1.40), "Chest"),
    "LeftUpperArm":  ((0.17, 0, 1.40), (0.45, 0, 1.40), "LeftShoulder"),
    "LeftLowerArm":  ((0.45, 0, 1.40), (0.70, 0, 1.40), "LeftUpperArm"),
    "LeftHand":      ((0.70, 0, 1.40), (0.82, 0, 1.40), "LeftLowerArm"),
    "RightShoulder": ((-0.05, 0, 1.40), (-0.17, 0, 1.40), "Chest"),
    "RightUpperArm": ((-0.17, 0, 1.40), (-0.45, 0, 1.40), "RightShoulder"),
    "RightLowerArm": ((-0.45, 0, 1.40), (-0.70, 0, 1.40), "RightUpperArm"),
    "RightHand":     ((-0.70, 0, 1.40), (-0.82, 0, 1.40), "RightLowerArm"),
    "LeftUpperLeg":  ((0.10, 0, 0.92), (0.10, 0, 0.50), "Hips"),
    "LeftLowerLeg":  ((0.10, 0, 0.50), (0.10, 0, 0.08), "LeftUpperLeg"),
    "LeftFoot":      ((0.10, 0, 0.08), (0.10, -0.12, 0.02), "LeftLowerLeg"),
    "LeftToes":      ((0.10, -0.12, 0.02), (0.10, -0.20, 0.02), "LeftFoot"),
    "RightUpperLeg": ((-0.10, 0, 0.92), (-0.10, 0, 0.50), "Hips"),
    "RightLowerLeg": ((-0.10, 0, 0.50), (-0.10, 0, 0.08), "RightUpperLeg"),
    "RightFoot":     ((-0.10, 0, 0.08), (-0.10, -0.12, 0.02), "RightLowerLeg"),
    "RightToes":     ((-0.10, -0.12, 0.02), (-0.10, -0.20, 0.02), "RightFoot"),
}


def _args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser(description="MeshGate demo character")
    ap.add_argument("--blend", required=True)
    ap.add_argument("--tex-size", type=int, default=TEX)
    return ap.parse_args(argv)


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, 60


# ----------------------------------------------------------------------------
# Texture and materials
# ----------------------------------------------------------------------------

def _noise(size: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    grid = rng.random((cells + 1, cells + 1))
    xs = np.linspace(0, cells, size, endpoint=False)
    x0 = np.floor(xs).astype(int); fx = xs - x0; x1 = np.minimum(x0 + 1, cells)
    a = grid[x0[:, None], x0[None, :]] * (1 - fx[:, None]) + grid[x1[:, None], x0[None, :]] * fx[:, None]
    b = grid[x0[:, None], x1[None, :]] * (1 - fx[:, None]) + grid[x1[:, None], x1[None, :]] * fx[:, None]
    return a * (1 - fx[None, :]) + b * fx[None, :]


def make_image(name: str, rgba: np.ndarray, tmpdir: str, is_data: bool) -> bpy.types.Image:
    h, w, _ = rgba.shape
    img = bpy.data.images.new(name, width=w, height=h, alpha=True)
    img.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    img.filepath_raw = os.path.join(tmpdir, f"{name}.png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    img.filepath_raw = f"//textures/{name}.png"
    return img


def make_suit_texture(size: int, tmpdir: str) -> bpy.types.Image:
    """Suit: dark blue fabric with orange panel seams and a grid — it reveals the UV unwrap quality."""
    rng = np.random.default_rng(3)
    y = np.arange(size)[:, None]; x = np.arange(size)[None, :]
    base = np.array([0.10, 0.16, 0.32])
    cloth = 0.85 + 0.3 * _noise(size, 128, rng)
    color = base[None, None, :] * cloth[:, :, None]
    cell = size // 8
    seam = ((x % cell) < 6) | ((y % cell) < 6)
    color[seam] = np.array([0.95, 0.45, 0.10])
    fine = ((x % (cell // 4)) < 1) | ((y % (cell // 4)) < 1)
    color[fine & ~seam] *= 0.75
    rgba = np.concatenate([np.clip(color, 0, 1), np.ones((size, size, 1))], axis=2)
    return make_image("hero_suit_albedo", rgba, tmpdir, False)


def make_materials(suit_tex: bpy.types.Image) -> dict:
    def principled(name):
        m = bpy.data.materials.new(name); m.use_nodes = True
        return m, m.node_tree.nodes["Principled BSDF"]
    mats = {}
    suit, b = principled("hero_suit")
    tex = suit.node_tree.nodes.new("ShaderNodeTexImage"); tex.image = suit_tex; tex.location = (-400, 200)
    suit.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7
    mats["hero_suit"] = suit
    skin, b = principled("hero_skin")
    b.inputs["Base Color"].default_value = (0.85, 0.62, 0.48, 1); b.inputs["Roughness"].default_value = 0.55
    mats["hero_skin"] = skin
    boots, b = principled("hero_boots")
    b.inputs["Base Color"].default_value = (0.12, 0.10, 0.09, 1); b.inputs["Roughness"].default_value = 0.4
    mats["hero_boots"] = boots
    return mats


# ----------------------------------------------------------------------------
# Body: primitives overlapping at the joints → voxel remesh (single smooth shell) →
# smoothing → decimation → per-zone materials → UV unwrap. Result: a smooth mannequin.
# ----------------------------------------------------------------------------

def _prim(op, name, location, scale=(1, 1, 1), rotation=(0, 0, 0), **kw):
    op(location=location, rotation=rotation, **kw)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return o


def build_body(mats: dict) -> bpy.types.Object:
    cube, cyl, sph = bpy.ops.mesh.primitive_cube_add, bpy.ops.mesh.primitive_cylinder_add, bpy.ops.mesh.primitive_uv_sphere_add
    P = []
    # head, neck, torso
    P.append(_prim(sph, "skull", (0, 0.005, 1.64), (0.98, 1.08, 1.12), radius=0.10, segments=24, ring_count=16))
    P.append(_prim(sph, "jaw", (0, -0.03, 1.575), (1.0, 0.95, 0.8), radius=0.075, segments=20, ring_count=12))
    P.append(_prim(sph, "nose", (0, -0.105, 1.61), (0.7, 1.3, 1.0), radius=0.022, segments=12, ring_count=8))
    P.append(_prim(cyl, "neck", (0, 0.01, 1.48), (1, 1, 1), radius=0.05, depth=0.14, vertices=16))
    P.append(_prim(sph, "chest", (0, 0.0, 1.30), (1.75, 1.0, 1.25), radius=0.11, segments=24, ring_count=16))
    P.append(_prim(sph, "belly", (0, 0.01, 1.12), (1.45, 0.95, 1.1), radius=0.11, segments=24, ring_count=16))
    P.append(_prim(sph, "pelvis", (0, 0.0, 0.96), (1.6, 1.0, 0.9), radius=0.11, segments=24, ring_count=16))
    for sx in (1, -1):
        P.append(_prim(sph, "deltoid", (sx * 0.165, 0, 1.40), (1, 1, 1), radius=0.07, segments=16, ring_count=12))
        P.append(_prim(cyl, "upperarm", (sx * 0.31, 0, 1.40), (1, 1, 1), rotation=(0, math.pi / 2, 0), radius=0.052, depth=0.30, vertices=16))
        P.append(_prim(sph, "elbow", (sx * 0.45, 0, 1.40), (1, 1, 1), radius=0.05, segments=16, ring_count=12))
        P.append(_prim(cyl, "forearm", (sx * 0.575, 0, 1.40), (1, 1, 1), rotation=(0, math.pi / 2, 0), radius=0.044, depth=0.26, vertices=16))
        P.append(_prim(sph, "wrist", (sx * 0.70, 0, 1.40), (1, 1, 1), radius=0.04, segments=12, ring_count=8))
        P.append(_prim(sph, "hand", (sx * 0.765, 0, 1.40), (1.5, 0.55, 1.0), radius=0.05, segments=16, ring_count=12))
        P.append(_prim(sph, "hip", (sx * 0.10, 0, 0.92), (1, 1, 1), radius=0.085, segments=16, ring_count=12))
        P.append(_prim(cyl, "thigh", (sx * 0.105, 0, 0.71), (1, 1, 1), radius=0.08, depth=0.44, vertices=16))
        P.append(_prim(sph, "knee", (sx * 0.11, 0, 0.50), (1, 1, 1), radius=0.065, segments=16, ring_count=12))
        P.append(_prim(cyl, "shin", (sx * 0.11, 0.005, 0.29), (1, 1, 1), radius=0.058, depth=0.42, vertices=16))
        P.append(_prim(sph, "ankle", (sx * 0.11, 0.0, 0.09), (1, 1, 1), radius=0.05, segments=12, ring_count=8))
        P.append(_prim(cube, "foot", (sx * 0.11, -0.06, 0.045), (0.11, 0.27, 0.09), size=1.0))
    bpy.ops.object.select_all(action="DESELECT")
    for o in P:
        o.select_set(True)
    bpy.context.view_layer.objects.active = P[0]
    bpy.ops.object.join()
    body = bpy.context.active_object
    body.name = "hero_body"; body.data.name = "hero_body"
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

    # single shell: voxel remesh fuses the overlapping primitives
    rm = body.modifiers.new("remesh", "REMESH"); rm.mode = "VOXEL"; rm.voxel_size = 0.012; rm.use_smooth_shade = True
    bpy.ops.object.modifier_apply(modifier="remesh")
    sm = body.modifiers.new("smooth", "SMOOTH"); sm.factor = 0.6; sm.iterations = 6
    bpy.ops.object.modifier_apply(modifier="smooth")
    dec = body.modifiers.new("decimate", "DECIMATE"); dec.ratio = 0.08
    bpy.ops.object.modifier_apply(modifier="decimate")
    for p in body.data.polygons:
        p.use_smooth = True

    # per-zone materials: head/neck/hands — skin, feet — boots, the rest — suit
    for m in (mats["hero_suit"], mats["hero_skin"], mats["hero_boots"]):
        body.data.materials.append(m)
    for poly in body.data.polygons:
        c = poly.center
        if c.z > 1.445 or (abs(c.x) > 0.715 and c.z > 1.30):
            poly.material_index = 1
        elif c.z < 0.115:
            poly.material_index = 2
        else:
            poly.material_index = 0

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.015, scale_to_bounds=False)
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    return body


# ----------------------------------------------------------------------------
# Skeleton and weights
# ----------------------------------------------------------------------------

def build_armature() -> bpy.types.Object:
    arm_data = bpy.data.armatures.new("hero_rig")
    arm = bpy.data.objects.new("hero_rig", arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = {}
    for name, (head, tail, parent) in BONES.items():
        b = arm_data.edit_bones.new(name)
        b.head, b.tail = Vector(head), Vector(tail)
        ebones[name] = b
    for name, (_, _, parent) in BONES.items():
        if parent:
            ebones[name].parent = ebones[parent]
            ebones[name].use_connect = (ebones[parent].tail - ebones[name].head).length < 1e-6
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def _seg_dist(p: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length


def skin(body: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Weights by nearest bone; a smooth blend where two bones meet."""
    groups = {name: body.vertex_groups.new(name=name) for name in BONES}
    segs = {name: (Vector(h), Vector(t)) for name, (h, t, _) in BONES.items()}
    blend = 0.06
    for v in body.data.vertices:
        p = body.matrix_world @ v.co
        d = sorted(((_seg_dist(p, *segs[n]), n) for n in segs), key=lambda x: x[0])
        (d1, n1), (d2, n2) = d[0], d[1]
        # within `blend` of the second-nearest bone: split the weight linearly (0.5/0.5 at equal distance)
        if d2 - d1 < blend:
            w1 = 0.5 + 0.5 * (d2 - d1) / blend
            groups[n1].add([v.index], w1, "REPLACE")
            groups[n2].add([v.index], 1.0 - w1, "REPLACE")
        else:
            groups[n1].add([v.index], 1.0, "REPLACE")
    mod = body.modifiers.new("rig", "ARMATURE")
    mod.object = arm
    body.parent = arm


# ----------------------------------------------------------------------------
# Bone animations
# ----------------------------------------------------------------------------

def _push_to_nla(obj: bpy.types.Object) -> None:
    ad = obj.animation_data
    action = ad.action
    track = ad.nla_tracks.new(); track.name = action.name
    strip = track.strips.new(action.name, int(action.frame_range[0]), action); strip.name = action.name
    ad.action = None


def _key(pb, frame, rot=None, loc=None):
    if rot is not None:
        pb.rotation_euler = rot
        pb.keyframe_insert("rotation_euler", frame=frame)
    if loc is not None:
        pb.location = loc
        pb.keyframe_insert("location", frame=frame)


def _raise_axis(arm: bpy.types.Object, bone: str) -> tuple[int, float]:
    """Find the local axis and sign whose rotation raises the bone upward (tail Z increases)."""
    pb = arm.pose.bones[bone]
    best = None
    for axis in range(3):
        for sign in (1.0, -1.0):
            rot = [0.0, 0.0, 0.0]; rot[axis] = sign * math.radians(60)
            pb.rotation_mode = "XYZ"; pb.rotation_euler = rot
            bpy.context.view_layer.update()
            z = (arm.matrix_world @ pb.tail).z
            if best is None or z > best[0]:
                best = (z, axis, sign)
    pb.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    return best[1], best[2]


def animate(arm: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    up_axis, up_sign = _raise_axis(arm, "RightUpperArm")
    fwd_axis, fwd_sign = _raise_axis(arm, "RightLowerArm")

    # idle: breathing — hips slightly up/down, chest slightly forward/back, arms sway
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions.new("idle")
    hips, chest = arm.pose.bones["Hips"], arm.pose.bones["Chest"]
    for frame, k in ((1, 0.0), (30, 1.0), (60, 0.0)):
        _key(hips, frame, loc=(0, 0.012 * k, 0))          # bone-local Y = along the bone (up)
        _key(chest, frame, rot=(math.radians(2.0 * k), 0, 0))
        for side, sgn in (("Left", 1), ("Right", -1)):
            rot = [0.0, 0.0, 0.0]; rot[up_axis] = up_sign * sgn * -math.radians(4.0 * k)
            _key(arm.pose.bones[f"{side}UpperArm"], frame, rot=rot)
    for fc in compat.fcurves(arm.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"; kp.easing = "EASE_IN_OUT"
    _push_to_nla(arm)

    # wave: right arm rises (frames 1–15), forearm waves (15–50), arm lowers (50–60)
    arm.animation_data.action = bpy.data.actions.new("wave")
    ua, la = arm.pose.bones["RightUpperArm"], arm.pose.bones["RightLowerArm"]
    def r(axis, sign, deg):
        v = [0.0, 0.0, 0.0]; v[axis] = sign * math.radians(deg); return v
    _key(ua, 1, rot=r(up_axis, up_sign, 0)); _key(ua, 15, rot=r(up_axis, up_sign, 75)); _key(ua, 50, rot=r(up_axis, up_sign, 75)); _key(ua, 60, rot=r(up_axis, up_sign, 0))
    _key(la, 1, rot=r(fwd_axis, fwd_sign, 0)); _key(la, 15, rot=r(fwd_axis, fwd_sign, 40))
    for i, frame in enumerate(range(22, 50, 7)):
        _key(la, frame, rot=r(fwd_axis, fwd_sign, 40 + (25 if i % 2 == 0 else -25)))
    _key(la, 50, rot=r(fwd_axis, fwd_sign, 40)); _key(la, 60, rot=r(fwd_axis, fwd_sign, 0))
    for fc in compat.fcurves(arm.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"; kp.easing = "EASE_IN_OUT"
    _push_to_nla(arm)
    bpy.ops.object.mode_set(mode="OBJECT")


# ----------------------------------------------------------------------------

def main() -> None:
    args = _args()
    reset_scene()
    with tempfile.TemporaryDirectory() as tmp:
        mats = make_materials(make_suit_texture(args.tex_size, tmp))
        body = build_body(mats)
        arm = build_armature()
        skin(body, arm)
        animate(arm)
        # root empty so there is a single parent in the engine
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
        root = bpy.context.active_object
        root.name = "meshgate_hero"
        arm.parent = root
        out = os.path.abspath(args.blend)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print(f"MeshGate: character saved -> {out} ({len(body.data.vertices)} vertices, {len(BONES)} bones, "
          f"{len(bpy.data.actions)} animations, UV: {'yes' if body.data.uv_layers else 'no'})")


if __name__ == "__main__":
    main()
