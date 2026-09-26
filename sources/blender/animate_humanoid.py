"""MeshGate — take any rigged humanoid (GLB/FBX) and prepare it according to the contract:
convert to meters with the origin at the feet, find Humanoid bones by name (Unity / Mixamo / Rigify / UE),
add demo animations `idle` and `wave` (if it has none of its own), push them into NLA and save a .blend.

    blender -b -P sources/blender/animate_humanoid.py -- --in avatar.glb --blend out.blend [--no-anim]
    blender -b out.blend -P sources/blender/export_meshgate.py -- --out avatar.glb --fbx --validate
"""

import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import bpy
except ImportError:
    print("This script runs inside Blender")
    sys.exit(2)

import argparse
import math
import os

from mathutils import Vector

# version compatibility (Blender 3.5 … 5.x) lives in the add-on package next to this script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshgate_blender import compat  # noqa: E402

# canonical Unity Humanoid → name variants (case-insensitive, a prefix like "mixamorig:" is stripped)
ALIASES = {
    "Hips": ["hips", "pelvis"],
    "Spine": ["spine", "spine1", "spine_01"],
    "Chest": ["chest", "spine2", "spine_02", "upperchest", "spine3"],
    "Neck": ["neck", "neck_01"],
    "Head": ["head"],
    "LeftShoulder": ["leftshoulder", "clavicle_l", "shoulder.l", "shoulder_l"],
    "LeftUpperArm": ["leftupperarm", "leftarm", "upperarm_l", "upper_arm.l"],
    "LeftLowerArm": ["leftlowerarm", "leftforearm", "lowerarm_l", "forearm.l"],
    "LeftHand": ["lefthand", "hand_l", "hand.l"],
    "RightShoulder": ["rightshoulder", "clavicle_r", "shoulder.r", "shoulder_r"],
    "RightUpperArm": ["rightupperarm", "rightarm", "upperarm_r", "upper_arm.r"],
    "RightLowerArm": ["rightlowerarm", "rightforearm", "lowerarm_r", "forearm.r"],
    "RightHand": ["righthand", "hand_r", "hand.r"],
    "LeftUpperLeg": ["leftupperleg", "leftupleg", "thigh_l", "thigh.l"],
    "LeftLowerLeg": ["leftlowerleg", "leftleg", "calf_l", "shin.l"],
    "LeftFoot": ["leftfoot", "foot_l", "foot.l"],
    "RightUpperLeg": ["rightupperleg", "rightupleg", "thigh_r", "thigh.r"],
    "RightLowerLeg": ["rightlowerleg", "rightleg", "calf_r", "shin.r"],
    "RightFoot": ["rightfoot", "foot_r", "foot.r"],
}


def _args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, help="character GLB/glTF/FBX")
    ap.add_argument("--blend", required=True)
    ap.add_argument("--no-anim", action="store_true", help="do not add idle/wave")
    ap.add_argument("--keep-anim", action="store_true", help="keep animations from the file (they are kept by default too)")
    return ap.parse_args(argv)


def import_file(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path, use_anim=True)
    else:
        raise SystemExit(f"unknown format: {ext}")


def find_humanoid(arm: bpy.types.Object) -> dict:
    names = {b.name: b.name for b in arm.data.bones}
    low = {n.split(":")[-1].lower(): n for n in names}
    found = {}
    for canon, variants in ALIASES.items():
        for v in [canon.lower()] + variants:
            if v in low:
                found[canon] = low[v]
                break
    return found


def normalize(arm: bpy.types.Object, meshes: list) -> None:
    """Contract: meters, origin at the feet, applied scale on the armature and meshes."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in [arm] + meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    # if the asset is in centimeters (height > 20 "meters") — scale it down
    zs = [ (o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box ]
    height = max(zs) - min(zs)
    if height > 20:
        for o in [arm] + meshes:
            if o.parent is None:
                o.scale *= 0.01
        bpy.context.view_layer.update()
        zs = [ (o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box ]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # bottom at z=0
    dz = -min(zs)
    for o in [arm] + meshes:
        if o.parent is None:
            o.location.z += dz


def _raise_axis(arm, bone):
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


def _push_to_nla(obj):
    ad = obj.animation_data
    action = ad.action
    track = ad.nla_tracks.new(); track.name = action.name
    strip = track.strips.new(action.name, int(action.frame_range[0]), action); strip.name = action.name
    ad.action = None


def _key(pb, frame, rot=None, loc=None):
    if rot is not None:
        pb.rotation_euler = rot; pb.keyframe_insert("rotation_euler", frame=frame)
    if loc is not None:
        pb.location = loc; pb.keyframe_insert("location", frame=frame)


def add_demo_animations(arm: bpy.types.Object, bones: dict) -> list:
    need = ["Hips", "Chest", "LeftUpperArm", "RightUpperArm", "RightLowerArm"]
    if not all(b in bones for b in need):
        print("MeshGate: missing bones for demo animations:", [b for b in need if b not in bones])
        return []
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    up_axis, up_sign = _raise_axis(arm, bones["RightUpperArm"])
    fwd_axis, fwd_sign = _raise_axis(arm, bones["RightLowerArm"])
    chest_axis, chest_sign = _raise_axis(arm, bones["Chest"])  # "up" for the chest ≈ backward/forward tilt
    def r(axis, sign, deg):
        v = [0.0, 0.0, 0.0]; v[axis] = sign * math.radians(deg); return v
    arm.animation_data_create()
    made = []

    arm.animation_data.action = bpy.data.actions.new("idle")
    hips, chest = arm.pose.bones[bones["Hips"]], arm.pose.bones[bones["Chest"]]
    for frame, k in ((1, 0.0), (30, 1.0), (60, 0.0)):
        _key(hips, frame, loc=(0, 0.01 * k, 0))
        _key(chest, frame, rot=r(chest_axis, chest_sign, -2.0 * k))
        for side, sgn in (("LeftUpperArm", 1), ("RightUpperArm", -1)):
            _key(arm.pose.bones[bones[side]], frame, rot=r(up_axis, up_sign * sgn, -3.0 * k))
    for fc in compat.fcurves(arm.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"; kp.easing = "EASE_IN_OUT"
    _push_to_nla(arm); made.append("idle")

    arm.animation_data.action = bpy.data.actions.new("wave")
    ua, la = arm.pose.bones[bones["RightUpperArm"]], arm.pose.bones[bones["RightLowerArm"]]
    _key(ua, 1, rot=r(up_axis, up_sign, 0)); _key(ua, 15, rot=r(up_axis, up_sign, 75)); _key(ua, 50, rot=r(up_axis, up_sign, 75)); _key(ua, 60, rot=r(up_axis, up_sign, 0))
    _key(la, 1, rot=r(fwd_axis, fwd_sign, 0)); _key(la, 15, rot=r(fwd_axis, fwd_sign, 40))
    for i, frame in enumerate(range(22, 50, 7)):
        _key(la, frame, rot=r(fwd_axis, fwd_sign, 40 + (25 if i % 2 == 0 else -25)))
    _key(la, 50, rot=r(fwd_axis, fwd_sign, 40)); _key(la, 60, rot=r(fwd_axis, fwd_sign, 0))
    for fc in compat.fcurves(arm.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"; kp.easing = "EASE_IN_OUT"
    _push_to_nla(arm); made.append("wave")
    bpy.ops.object.mode_set(mode="OBJECT")
    return made


def main():
    args = _args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"; scene.unit_settings.scale_length = 1.0
    scene.render.fps = 30; scene.frame_start, scene.frame_end = 1, 60
    import_file(os.path.abspath(args.src))

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not arms:
        raise SystemExit("MeshGate: no armature in the file — this is not a rigged character")
    arm = arms[0]
    # push existing imported animations into NLA so the exporters don't lose them
    existing = []
    if arm.animation_data and arm.animation_data.action:
        existing.append(arm.animation_data.action.name); _push_to_nla(arm)
    for a in bpy.data.actions:
        if a.name not in existing and arm.animation_data and not any(s.action == a for t in arm.animation_data.nla_tracks for s in t.strips):
            arm.animation_data.action = a; _push_to_nla(arm); existing.append(a.name)

    normalize(arm, meshes)
    bones = find_humanoid(arm)
    missing = [b for b in ALIASES if b not in bones]
    print(f"MeshGate: {len(arm.data.bones)} bones, Humanoid found {len(bones)}/{len(ALIASES)}" + (f", missing: {missing}" if missing else ""))
    made = [] if args.no_anim else add_demo_animations(arm, bones)

    # contract names: Latin, no spaces
    for o in [arm] + meshes:
        o.name = o.name.replace(" ", "_")
    if not arm.parent and arm.name != "meshgate_avatar":
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
        root = bpy.context.active_object; root.name = "meshgate_avatar"
        arm.parent = root
        for m in meshes:
            if m.parent is None:
                m.parent = root

    out = os.path.abspath(args.blend)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    zs = [(o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box]
    print(f"MeshGate: character prepared -> {out} (height {max(zs) - min(zs):.2f} m, {len(meshes)} meshes, "
          f"animations: {', '.join(existing + made) or 'none'}, UV: {'yes' if all(m.data.uv_layers for m in meshes) else 'NO'})")


if __name__ == "__main__":
    main()
