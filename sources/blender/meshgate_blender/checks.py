"""Asset contract checks that run inside Blender, before export — each with an optional automatic fix.

The GLB validator (core/validate_glb.py) sees only the exported file. These rules see the scene, so
they can point at the object to change and fix it in place: apply scale, transliterate names, unwrap,
pack and resize textures, put the asset on the ground, rename a Mixamo/Rigify/UE skeleton to Unity
Humanoid, normalize weights, push loose actions into NLA strips.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import bpy
from mathutils import Vector

from . import compat

ERROR, WARNING, INFO = "ERROR", "WARNING", "INFO"

HUMANOID = [
    "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head",
    "LeftShoulder", "LeftUpperArm", "LeftLowerArm", "LeftHand",
    "RightShoulder", "RightUpperArm", "RightLowerArm", "RightHand",
    "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes",
    "RightUpperLeg", "RightLowerLeg", "RightFoot", "RightToes",
]
HUMANOID_REQUIRED = [b for b in HUMANOID if b not in ("Chest", "UpperChest", "Neck", "LeftShoulder", "RightShoulder", "LeftToes", "RightToes")]
BONE_ALIASES = {  # lower-case name without "mixamorig:" style prefix → Unity Humanoid
    "hips": "Hips", "pelvis": "Hips", "chest": "Chest", "upperchest": "UpperChest", "upper_chest": "UpperChest",
    "neck": "Neck", "neck_01": "Neck", "head": "Head",
    "leftshoulder": "LeftShoulder", "clavicle_l": "LeftShoulder", "shoulder.l": "LeftShoulder", "shoulder_l": "LeftShoulder",
    "leftarm": "LeftUpperArm", "leftupperarm": "LeftUpperArm", "upperarm_l": "LeftUpperArm", "upper_arm.l": "LeftUpperArm",
    "leftforearm": "LeftLowerArm", "leftlowerarm": "LeftLowerArm", "lowerarm_l": "LeftLowerArm", "forearm.l": "LeftLowerArm",
    "lefthand": "LeftHand", "hand_l": "LeftHand", "hand.l": "LeftHand",
    "rightshoulder": "RightShoulder", "clavicle_r": "RightShoulder", "shoulder.r": "RightShoulder", "shoulder_r": "RightShoulder",
    "rightarm": "RightUpperArm", "rightupperarm": "RightUpperArm", "upperarm_r": "RightUpperArm", "upper_arm.r": "RightUpperArm",
    "rightforearm": "RightLowerArm", "rightlowerarm": "RightLowerArm", "lowerarm_r": "RightLowerArm", "forearm.r": "RightLowerArm",
    "righthand": "RightHand", "hand_r": "RightHand", "hand.r": "RightHand",
    "leftupleg": "LeftUpperLeg", "leftupperleg": "LeftUpperLeg", "thigh_l": "LeftUpperLeg", "thigh.l": "LeftUpperLeg",
    "leftleg": "LeftLowerLeg", "leftlowerleg": "LeftLowerLeg", "calf_l": "LeftLowerLeg", "shin.l": "LeftLowerLeg",
    "leftfoot": "LeftFoot", "foot_l": "LeftFoot", "foot.l": "LeftFoot",
    "lefttoebase": "LeftToes", "lefttoes": "LeftToes", "ball_l": "LeftToes", "toe.l": "LeftToes",
    "rightupleg": "RightUpperLeg", "rightupperleg": "RightUpperLeg", "thigh_r": "RightUpperLeg", "thigh.r": "RightUpperLeg",
    "rightleg": "RightLowerLeg", "rightlowerleg": "RightLowerLeg", "calf_r": "RightLowerLeg", "shin.r": "RightLowerLeg",
    "rightfoot": "RightFoot", "foot_r": "RightFoot", "foot.r": "RightFoot",
    "righttoebase": "RightToes", "righttoes": "RightToes", "ball_r": "RightToes", "toe.r": "RightToes",
}
# Spine chains (Mixamo Spine/Spine1/Spine2, UE spine_01…, Rigify spine/spine.001…) are mapped by order in
# humanoid_map(): first → Spine, second → Chest, third → UpperChest; further ones stay as they are.
_SPINE = re.compile(r"^spine(?:[_.]?0*(\d+))?$")

_NAME_OK = re.compile(r"^[A-Za-z0-9_.\-]+$")
_TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g",
})


@dataclass
class Issue:
    code: str
    severity: str
    message: str
    fix: str = ""                      # fix id, empty = manual
    objects: list[str] = field(default_factory=list)

    def label(self) -> str:
        names = ", ".join(self.objects[:4]) + (f" (+{len(self.objects) - 4})" if len(self.objects) > 4 else "")
        return f"{self.message}" + (f": {names}" if names else "")


# ----------------------------------------------------------------------------
# scope
# ----------------------------------------------------------------------------

# largest texture the contract accepts; a master build beyond the PC tier (--texture 8k) raises it for its run
MAX_TEXTURE = 4096

def export_objects(context, selection_only: bool = False) -> list[bpy.types.Object]:
    """Objects the exporter will write: renderable meshes, armatures and empties (and their children)."""
    pool = context.selected_objects if selection_only else context.scene.objects
    return [o for o in pool if o.type in {"MESH", "ARMATURE", "EMPTY"} and not o.hide_render
            and not o.get("meshgate_collision_for") and not o.get("meshgate_lod_of")]


def meshes(objs) -> list[bpy.types.Object]:
    return [o for o in objs if o.type == "MESH"]


def world_bounds(objs) -> tuple[Vector, Vector] | None:
    lo = Vector((math.inf,) * 3); hi = Vector((-math.inf,) * 3)
    found = False
    for o in meshes(objs):
        for corner in o.bound_box:
            p = o.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
            found = True
    return (lo, hi) if found else None


def ascii_name(name: str) -> str:
    out = name.lower().translate(_TRANSLIT) if any(ord(c) > 127 for c in name) else name
    out = re.sub(r"[^A-Za-z0-9_.\-]+", "_", out).strip("_")
    return out or "unnamed"


def _pow2(n: int) -> bool:
    return n > 0 and n & (n - 1) == 0


def _images(objs) -> list[bpy.types.Image]:
    seen = []
    for o in meshes(objs):
        for slot in o.material_slots:
            m = slot.material
            if m and m.use_nodes and m.node_tree:
                for n in m.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image and n.image not in seen:
                        seen.append(n.image)
    return seen


def humanoid_map(arm: bpy.types.Object) -> dict[str, str]:
    """bone name → Unity Humanoid name for bones that are recognised (already-canonical ones map to themselves)."""
    names = [b.name for b in arm.data.bones]
    low = {n.split(":")[-1].lower(): n for n in names}
    mapping: dict[str, str] = {}
    spine = sorted(((int(m.group(1) or 0), key) for key in low if (m := _SPINE.match(key))), key=lambda t: t[0])
    has_chest = any(BONE_ALIASES.get(k) == "Chest" for k in low)
    chain = ["Spine"] + ([] if has_chest else ["Chest", "UpperChest"])
    for (_, key), canon in zip(spine, chain):
        mapping[low[key]] = canon
    for key, original in low.items():
        canon = BONE_ALIASES.get(key)
        if canon is None and key in {h.lower() for h in HUMANOID}:
            canon = next(h for h in HUMANOID if h.lower() == key)
        if canon and original not in mapping and canon not in mapping.values():
            mapping[original] = canon
    return mapping


# ----------------------------------------------------------------------------
# rules
# ----------------------------------------------------------------------------

def run_checks(context, selection_only: bool = False, targets: set[str] | None = None) -> list[Issue]:
    targets = targets or set()
    scene = context.scene
    objs = export_objects(context, selection_only)
    issues: list[Issue] = []

    if not objs or not meshes(objs):
        issues.append(Issue("EMPTY", ERROR, "Nothing to export: no visible, renderable meshes"))
        return issues

    us = scene.unit_settings
    if us.system != "METRIC" or abs(us.scale_length - 1.0) > 1e-6:
        issues.append(Issue("UNITS", WARNING, "Scene units are not meters (Metric, unit scale 1.0)", "units"))

    bounds = world_bounds(objs)
    if bounds:
        lo, hi = bounds
        size = hi - lo
        longest = max(size)
        if longest < 0.01:
            issues.append(Issue("SIZE_SMALL", WARNING, f"Asset is {longest * 100:.2f} cm long — probably millimeters; scale it to real size"))
        elif longest > 100:
            issues.append(Issue("SIZE_LARGE", WARNING, f"Asset is {longest:.0f} m long — probably centimeters, or a whole scene"))
        if abs(lo.z) > 0.02 * max(longest, 0.01) and lo.z < 0.5 * size.z:
            issues.append(Issue("GROUND", INFO, f"Lowest point is at Z = {lo.z:.3f} m — floor props should stand on Z = 0", "ground"))

    scaled = [o.name for o in meshes(objs) if any(abs(s - 1) > 1e-4 for s in o.scale) and not compat.animates(o, "scale")]
    if scaled:
        issues.append(Issue("SCALE", WARNING, "Unapplied scale", "apply_scale", scaled))
    negative = [o.name for o in meshes(objs) if o.scale.x * o.scale.y * o.scale.z < 0]
    if negative:
        issues.append(Issue("NEG_SCALE", WARNING, "Negative scale flips normals in engines", "apply_scale", negative))

    bad_names = [o.name for o in objs if not _NAME_OK.match(o.name)]
    mats = {s.material for o in meshes(objs) for s in o.material_slots if s.material}
    bad_names += [f"material {m.name}" for m in mats if not _NAME_OK.match(m.name)]
    bad_names += [f"bone {b.name}" for o in objs if o.type == "ARMATURE" for b in o.data.bones if not _NAME_OK.match(b.name)]
    if bad_names:
        issues.append(Issue("NAMES", WARNING, "Names with spaces or non-Latin characters", "names", bad_names))

    no_uv = [o.name for o in meshes(objs) if not o.data.uv_layers]
    if no_uv:
        issues.append(Issue("NO_UV", WARNING, "Meshes without UVs", "unwrap", no_uv))

    no_mat = [o.name for o in meshes(objs) if not any(s.material for s in o.material_slots)]
    if no_mat:
        issues.append(Issue("NO_MATERIAL", WARNING, "Meshes without a material (engines show default grey)", "default_material", no_mat))
    non_pbr = [m.name for m in mats if not compat.principled(m)]
    if non_pbr:
        issues.append(Issue("NON_PBR", WARNING, "Materials without Principled BSDF — bake them to textures first", "", non_pbr))

    images = _images(objs)
    missing = [i.name for i in images if not i.packed_file and i.source == "FILE" and not i.has_data and not _file_exists(i)]
    if missing:
        issues.append(Issue("MISSING_TEX", ERROR, "Texture files not found", "", missing))
    unpacked = [i.name for i in images if not i.packed_file and i.source == "FILE" and i.name not in missing]
    if unpacked:
        issues.append(Issue("UNPACKED", INFO, "Textures are external files — packing keeps the .blend self-contained", "pack"))
    npot = [f"{i.name} {i.size[0]}×{i.size[1]}" for i in images if i.size[0] and (not _pow2(i.size[0]) or not _pow2(i.size[1]))]
    if npot:
        issues.append(Issue("NPOT", WARNING, "Textures not power of two", "pow2", npot))
    huge = [f"{i.name} {i.size[0]}×{i.size[1]}" for i in images if max(i.size) > MAX_TEXTURE]
    if huge:
        issues.append(Issue("HUGE_TEX", WARNING, f"Textures larger than {MAX_TEXTURE}", "pow2", huge))

    for arm in [o for o in objs if o.type == "ARMATURE"]:
        mapping = humanoid_map(arm)
        canon = set(mapping.values())
        if len(canon) >= 8:  # looks like a humanoid
            renames = {k: v for k, v in mapping.items() if k != v}
            missing_req = [b for b in HUMANOID_REQUIRED if b not in canon]
            if renames:
                issues.append(Issue("BONE_NAMES", WARNING, f"{arm.name}: {len(renames)} bones can be renamed to Unity Humanoid (Mixamo/Rigify/UE names found)",
                                    "humanoid", [arm.name]))
            if missing_req:
                issues.append(Issue("HUMANOID_MISSING", WARNING, f"{arm.name}: missing Humanoid bones: {', '.join(missing_req)}", "", [arm.name]))
        skinned = [o for o in meshes(objs) if any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]
        unweighted = []
        for o in skinned:
            group_ids = {g.index for g in o.vertex_groups if g.name in arm.data.bones}
            if any(not any(g.group in group_ids and g.weight > 0 for g in v.groups) for v in o.data.vertices):
                unweighted.append(o.name)
        if unweighted:
            issues.append(Issue("WEIGHTS", WARNING, "Skinned meshes with unweighted vertices (they stay behind when animated)", "weights", unweighted))

    loose = [o.name for o in objs if o.animation_data and o.animation_data.action
             and o.animation_data.nla_tracks and len(o.animation_data.nla_tracks) > 0]
    if loose:
        issues.append(Issue("LOOSE_ACTION", INFO, "Active actions next to NLA clips — push them to NLA so every clip keeps its name", "nla", loose))

    hidden = [o.name for o in context.scene.objects if o.type == "MESH" and o.hide_render and o.visible_get()
              and not o.get("meshgate_collision_for") and not o.get("meshgate_lod_of")]
    if hidden:
        issues.append(Issue("HIDDEN_RENDER", INFO, "Visible but disabled for render — will not be exported", "", hidden))

    return issues


def _file_exists(image: bpy.types.Image) -> bool:
    import os
    try:
        return os.path.isfile(bpy.path.abspath(image.filepath))
    except Exception:  # noqa: BLE001
        return False


# ----------------------------------------------------------------------------
# fixes
# ----------------------------------------------------------------------------

def _select_only(context, objs):
    for o in context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    if objs:
        context.view_layer.objects.active = objs[0]


def fix_units(context, objs):
    us = context.scene.unit_settings
    us.system = "METRIC"; us.scale_length = 1.0
    return "units set to meters"


def fix_apply_scale(context, objs):
    todo = [o for o in meshes(objs) if (any(abs(s - 1) > 1e-4 for s in o.scale) or o.scale.x * o.scale.y * o.scale.z < 0)
            and not compat.animates(o, "scale")]
    single = [o for o in todo if o.data.users == 1]
    shared = [o for o in todo if o.data.users > 1]
    for o in shared:  # make mesh data single-user so scale can be applied
        o.data = o.data.copy()
        single.append(o)
    if not single:
        return "nothing to apply"
    _select_only(context, single)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for o in single:  # negative scale leaves normals inverted
        if o.data.polygons:
            _select_only(context, [o])
            bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode="OBJECT")
    return f"scale applied on {len(single)} objects"


def fix_names(context, objs):
    n = 0
    for o in objs:
        if not _NAME_OK.match(o.name):
            o.name = ascii_name(o.name); n += 1
    for o in meshes(objs):
        for s in o.material_slots:
            if s.material and not _NAME_OK.match(s.material.name):
                s.material.name = ascii_name(s.material.name); n += 1
    for o in objs:
        if o.type == "ARMATURE":
            taken = {b.name for b in o.data.bones}
            for b in o.data.bones:
                if _NAME_OK.match(b.name):
                    continue
                new = ascii_name(b.name.split(":")[-1])   # "mixamorig:LeftArm" → "LeftArm"
                if new in taken:
                    new = ascii_name(b.name)
                taken.discard(b.name); taken.add(new)
                b.name = new; n += 1
    for a in bpy.data.actions:
        if not _NAME_OK.match(a.name):
            a.name = ascii_name(a.name); n += 1
    return f"{n} names fixed"


def fix_unwrap(context, objs):
    todo = [o for o in meshes(objs) if not o.data.uv_layers]
    for o in todo:
        _select_only(context, [o])
        bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
        bpy.ops.mesh.select_all(action="DESELECT"); bpy.ops.object.mode_set(mode="OBJECT")
    return f"unwrapped {len(todo)} meshes"


def fix_default_material(context, objs):
    mat = bpy.data.materials.get("default_pbr") or bpy.data.materials.new("default_pbr")
    mat.use_nodes = True
    n = 0
    for o in meshes(objs):
        if not any(s.material for s in o.material_slots):
            o.data.materials.append(mat); n += 1
    return f"default_pbr assigned to {n} meshes"


def fix_pack(context, objs):
    n = 0
    for img in _images(objs):
        if not img.packed_file and img.source == "FILE" and _file_exists(img):
            img.pack(); n += 1
    return f"packed {n} textures"


def fix_pow2(context, objs):
    n = 0
    for img in _images(objs):
        w, h = img.size
        if not w:
            continue
        nw = min(MAX_TEXTURE, 1 << max(0, round(math.log2(w))))
        nh = min(MAX_TEXTURE, 1 << max(0, round(math.log2(h))))
        if (nw, nh) != (w, h):
            img.scale(nw, nh)
            if img.packed_file or img.source == "GENERATED":
                img.pack()
            n += 1
    return f"resized {n} textures"


def fix_ground(context, objs):
    bounds = world_bounds(objs)
    if not bounds:
        return "no meshes"
    dz = -bounds[0].z
    roots = [o for o in objs if o.parent is None or o.parent not in objs]
    for o in roots:
        o.location.z += dz
    return f"moved {len(roots)} root objects by {dz:+.3f} m"


def fix_humanoid(context, objs):
    n = 0
    for arm in [o for o in objs if o.type == "ARMATURE"]:
        mapping = humanoid_map(arm)
        for old, new in mapping.items():
            if old != new and old in arm.data.bones and new not in arm.data.bones:
                arm.data.bones[old].name = new   # Blender renames vertex groups and F-curve paths too
                n += 1
    return f"{n} bones renamed to Unity Humanoid"


def fix_weights(context, objs):
    n = 0
    for arm in [o for o in objs if o.type == "ARMATURE"]:
        bone_heads = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones if b.use_deform}
        for o in [m for m in meshes(objs) if any(md.type == "ARMATURE" and md.object == arm for md in m.modifiers)]:
            groups = {g.name: g for g in o.vertex_groups}
            ids = {g.index for g in o.vertex_groups if g.name in bone_heads}
            for v in o.data.vertices:
                if any(g.group in ids and g.weight > 0 for g in v.groups):
                    continue
                p = o.matrix_world @ v.co
                nearest = min(bone_heads, key=lambda b: (bone_heads[b] - p).length)
                g = groups.get(nearest) or o.vertex_groups.new(name=nearest)
                groups[nearest] = g
                g.add([v.index], 1.0, "REPLACE"); n += 1
            _select_only(context, [o])
            bpy.ops.object.vertex_group_limit_total(group_select_mode="BONE_DEFORM", limit=4)
            bpy.ops.object.vertex_group_normalize_all(group_select_mode="BONE_DEFORM", lock_active=False)
    return f"{n} stray vertices weighted, weights limited to 4 and normalized"


def fix_nla(context, objs):
    n = 0
    for o in objs:
        if o.animation_data and o.animation_data.action:
            compat.push_to_nla(o); n += 1
    return f"{n} actions pushed to NLA"


FIXES = {
    "units": fix_units, "apply_scale": fix_apply_scale, "names": fix_names, "unwrap": fix_unwrap,
    "default_material": fix_default_material, "pack": fix_pack, "pow2": fix_pow2, "ground": fix_ground,
    "humanoid": fix_humanoid, "weights": fix_weights, "nla": fix_nla,
}
# order matters: rename bones before weights, apply scale before grounding
FIX_ORDER = ["units", "names", "humanoid", "apply_scale", "unwrap", "default_material", "pack", "pow2", "weights", "nla", "ground"]


def apply_fix(context, fix_id: str, selection_only: bool = False) -> str:
    if context.object and context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    try:
        return FIXES[fix_id](context, export_objects(context, selection_only))
    finally:
        for o in context.view_layer.objects:
            o.select_set(o in selected)
        context.view_layer.objects.active = active


def fix_all(context, selection_only: bool = False) -> list[str]:
    wanted = {i.fix for i in run_checks(context, selection_only) if i.fix}
    return [f"{fid}: {apply_fix(context, fid, selection_only)}" for fid in FIX_ORDER if fid in wanted]
