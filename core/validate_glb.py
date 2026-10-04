#!/usr/bin/env python3
"""MeshGate — GLB validator against the "asset contract".

Checks that a .glb is valid binary glTF 2.0 and that its contents
follow the contract (see docs/asset-contract.md): a scene and meshes exist,
dimensions look like meters, transforms are applied, geometry has UVs and normals,
materials are PBR, textures are powers of two, names are Latin with no spaces.
Prints a report (or JSON for CI).

Pure stdlib — no dependencies. Usage:
    python3 core/validate_glb.py path/to/asset.glb [--max-mb 25] [--strict] [--json]
Exit code: 0 — valid, 1 — contract errors (with --strict, warnings too), 2 — not glTF 2.0 / corrupt file.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any

_GLB_MAGIC = 0x46546C67  # 'glTF' little-endian
_CHUNK_JSON = 0x4E4F534A  # 'JSON'
_CHUNK_BIN = 0x004E4942   # 'BIN\0'

# Extensions understood by all our targets (Three.js, glTFast, Godot, Unreal Interchange).
_SAFE_EXTENSIONS = {
    "KHR_materials_emissive_strength", "KHR_texture_transform", "KHR_mesh_quantization",
    "KHR_materials_unlit", "KHR_materials_clearcoat", "KHR_materials_transmission",
    "KHR_materials_ior", "KHR_materials_specular", "KHR_materials_volume",
    "KHR_lights_punctual", "KHR_draco_mesh_compression", "KHR_texture_basisu",
    "EXT_meshopt_compression",
}
# Extensions with per-target caveats.
_EXT_NOTES = {
    "KHR_draco_mesh_compression": "Draco: supported by Three.js/glTFast/Godot; not by Unreal Interchange (needs glTFRuntime or an uncompressed variant)",
    "KHR_texture_basisu": "KTX2/Basis: supported by Three.js and glTFast, Godot 4 — yes, Unreal — needs checking",
    "EXT_meshopt_compression": "meshopt: Three.js — yes, glTFast — yes, Godot/Unreal — no",
    "KHR_materials_pbrSpecularGlossiness": "legacy spec/gloss — convert to metallic/roughness",
}

_MIN_DIM_M = 0.01     # under 1 cm — looks like wrong units (mm → m)
_MAX_DIM_M = 100.0    # over 100 m — looks like cm instead of m, or a scene rather than an asset


class GlbError(Exception):
    """The file is not valid binary glTF 2.0."""


# ----------------------------------------------------------------------------
# Container parsing
# ----------------------------------------------------------------------------

def parse_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    """Parse a GLB: return (glTF JSON, BIN chunk)."""
    data = path.read_bytes()
    if len(data) < 12:
        raise GlbError("file is shorter than 12 bytes — not a GLB")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != _GLB_MAGIC:
        raise GlbError("no 'glTF' signature — not a GLB (maybe .gltf or a different format)")
    if version != 2:
        raise GlbError(f"container version {version}, only glTF 2.0 is supported")
    if length != len(data):
        raise GlbError(f"header says length {length}, on disk {len(data)} — file is truncated or corrupt")

    gltf: dict[str, Any] | None = None
    bin_chunk = b""
    offset = 12
    while offset + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_len]
        if chunk_type == _CHUNK_JSON:
            gltf = json.loads(chunk.decode("utf-8"))
        elif chunk_type == _CHUNK_BIN:
            bin_chunk = chunk
        offset += chunk_len
    if gltf is None:
        raise GlbError("JSON chunk with the scene description not found")
    return gltf, bin_chunk


def image_size(blob: bytes) -> tuple[int, int] | None:
    """PNG/JPEG/WebP size from the header, without decoding."""
    if blob[:8] == b"\x89PNG\r\n\x1a\n" and len(blob) >= 24:
        w, h = struct.unpack_from(">II", blob, 16)
        return w, h
    if blob[:2] == b"\xff\xd8":  # JPEG: look for the SOF marker
        i = 2
        while i + 9 < len(blob):
            if blob[i] != 0xFF:
                i += 1
                continue
            marker = blob[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg_len = struct.unpack_from(">H", blob, i + 2)[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack_from(">HH", blob, i + 5)
                return w, h
            i += 2 + seg_len
        return None
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP" and len(blob) >= 30:
        fmt = blob[12:16]
        if fmt == b"VP8 ":
            w, h = struct.unpack_from("<HH", blob, 26)
            return w & 0x3FFF, h & 0x3FFF
        if fmt == b"VP8L":
            b0, b1, b2, b3 = blob[21:25]
            return 1 + (((b1 & 0x3F) << 8) | b0), 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        if fmt == b"VP8X":
            w = 1 + int.from_bytes(blob[24:27], "little")
            h = 1 + int.from_bytes(blob[27:30], "little")
            return w, h
    return None


def _node_matrix(n: dict[str, Any]) -> list[list[float]]:
    """Local 4×4 node matrix (row-major) from matrix or T·R·S."""
    if "matrix" in n:
        m = n["matrix"]  # column-major in glTF
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    t = n.get("translation", [0, 0, 0])
    x, y, z, w = n.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = n.get("scale", [1, 1, 1])
    rot = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    sc = (sx, sy, sz)
    return [[rot[r][c] * sc[c] for c in range(3)] + [t[r]] for r in range(3)] + [[0, 0, 0, 1]]


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def _transform_point(m: list[list[float]], p: list[float]) -> list[float]:
    return [m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3] for r in range(3)]


def world_bounds(gltf: dict[str, Any], bin_chunk: bytes = b"") -> tuple[list[float], list[float]] | None:
    """World AABB of the default scene: min/max of POSITION accessors, passed through the node hierarchy.

    Skinned meshes follow the glTF spec: the mesh node's own transform is ignored, vertices are placed by
    the skin — in bind pose that is global(joint) · inverseBindMatrix(joint), the same for every joint, so
    the first joint is enough.
    """
    nodes = gltf.get("nodes") or []
    meshes = gltf.get("meshes") or []
    accessors = gltf.get("accessors") or []
    scenes = gltf.get("scenes") or []
    if not scenes:
        return None
    roots = scenes[gltf.get("scene", 0)].get("nodes") or []
    identity = [[float(r == c) for c in range(4)] for r in range(4)]

    # pass 1: global matrix of every node reachable from the scene
    world_of: dict[int, list[list[float]]] = {}
    stack = [(i, identity) for i in roots]
    while stack:
        idx, parent = stack.pop()
        if idx in world_of or idx >= len(nodes):
            continue
        world_of[idx] = _mat_mul(parent, _node_matrix(nodes[idx]))
        stack.extend((c, world_of[idx]) for c in nodes[idx].get("children") or [])

    def skin_matrix(skin_index: int) -> list[list[float]] | None:
        skins = gltf.get("skins") or []
        if skin_index >= len(skins):
            return None
        skin = skins[skin_index]
        joints = skin.get("joints") or []
        if not joints or joints[0] not in world_of:
            return None
        ibm = identity
        if "inverseBindMatrices" in skin and bin_chunk:
            data = read_accessor(gltf, bin_chunk, skin["inverseBindMatrices"])
            if data:
                m = data[0]  # column-major
                ibm = [[m[c * 4 + r] for c in range(4)] for r in range(4)]
        return _mat_mul(world_of[joints[0]], ibm)

    bb_min = [math.inf] * 3
    bb_max = [-math.inf] * 3
    for idx, world in world_of.items():
        n = nodes[idx]
        if "mesh" not in n or n["mesh"] >= len(meshes):
            continue
        if "skin" in n:
            world = skin_matrix(n["skin"]) or world
        for p in meshes[n["mesh"]].get("primitives") or []:
            ai = (p.get("attributes") or {}).get("POSITION")
            if ai is None or ai >= len(accessors):
                continue
            acc = accessors[ai]
            if "min" not in acc or "max" not in acc:
                continue
            lo, hi = acc["min"], acc["max"]
            for corner in ((lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (lo[0], hi[1], lo[2]), (hi[0], hi[1], lo[2]),
                           (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (lo[0], hi[1], hi[2]), (hi[0], hi[1], hi[2])):
                wp = _transform_point(world, list(corner))
                for i in range(3):
                    bb_min[i] = min(bb_min[i], wp[i])
                    bb_max[i] = max(bb_max[i], wp[i])
    if not all(math.isfinite(v) for v in bb_min + bb_max):
        return None
    return bb_min, bb_max


_CTYPE = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

HUMANOID_BONES = [
    "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head",
    "LeftShoulder", "LeftUpperArm", "LeftLowerArm", "LeftHand",
    "RightShoulder", "RightUpperArm", "RightLowerArm", "RightHand",
    "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes",
    "RightUpperLeg", "RightLowerLeg", "RightFoot", "RightToes",
]
# alternative names (Mixamo / Rigify / UE Mannequin) → canonical Unity Humanoid
_BONE_ALIASES = {
    "pelvis": "Hips", "hips": "Hips", "spine": "Spine", "spine1": "Spine", "spine2": "Chest", "spine_02": "Chest", "chest": "Chest",
    "neck": "Neck", "neck_01": "Neck", "head": "Head",
    "leftshoulder": "LeftShoulder", "clavicle_l": "LeftShoulder", "shoulder.l": "LeftShoulder",
    "leftarm": "LeftUpperArm", "upperarm_l": "LeftUpperArm", "upper_arm.l": "LeftUpperArm",
    "leftforearm": "LeftLowerArm", "lowerarm_l": "LeftLowerArm", "forearm.l": "LeftLowerArm",
    "lefthand": "LeftHand", "hand_l": "LeftHand", "hand.l": "LeftHand",
    "rightshoulder": "RightShoulder", "clavicle_r": "RightShoulder", "shoulder.r": "RightShoulder",
    "rightarm": "RightUpperArm", "upperarm_r": "RightUpperArm", "upper_arm.r": "RightUpperArm",
    "rightforearm": "RightLowerArm", "lowerarm_r": "RightLowerArm", "forearm.r": "RightLowerArm",
    "righthand": "RightHand", "hand_r": "RightHand", "hand.r": "RightHand",
    "leftupleg": "LeftUpperLeg", "thigh_l": "LeftUpperLeg", "thigh.l": "LeftUpperLeg",
    "leftleg": "LeftLowerLeg", "calf_l": "LeftLowerLeg", "shin.l": "LeftLowerLeg",
    "leftfoot": "LeftFoot", "foot_l": "LeftFoot", "foot.l": "LeftFoot",
    "lefttoebase": "LeftToes", "ball_l": "LeftToes", "toe.l": "LeftToes",
    "rightupleg": "RightUpperLeg", "thigh_r": "RightUpperLeg", "thigh.r": "RightUpperLeg",
    "rightleg": "RightLowerLeg", "calf_r": "RightLowerLeg", "shin.r": "RightLowerLeg",
    "rightfoot": "RightFoot", "foot_r": "RightFoot", "foot.r": "RightFoot",
    "righttoebase": "RightToes", "ball_r": "RightToes", "toe.r": "RightToes",
}


def _canon_bone(name: str) -> str | None:
    n = name.split(":")[-1].lower()  # mixamorig:Hips → hips
    if n in _BONE_ALIASES:
        return _BONE_ALIASES[n]
    for h in HUMANOID_BONES:
        if n == h.lower():
            return h
    return None


def read_accessor(gltf: dict[str, Any], bin_chunk: bytes, index: int) -> list[tuple] | None:
    """Read an accessor from BIN as a list of tuples (no sparse). None if the data is not in the GLB."""
    acc = gltf["accessors"][index]
    if "bufferView" not in acc or "sparse" in acc:
        return None
    bv = gltf["bufferViews"][acc["bufferView"]]
    fmt, size = _CTYPE[acc["componentType"]]
    n = _NCOMP[acc["type"]]
    stride = bv.get("byteStride") or size * n
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    out = []
    for i in range(acc["count"]):
        off = base + i * stride
        out.append(struct.unpack_from("<" + fmt * n, bin_chunk, off))
    if acc.get("normalized"):
        scale = {5121: 255.0, 5123: 65535.0}.get(acc["componentType"], 1.0)
        out = [tuple(v / scale for v in t) for t in out]
    return out


def inspect_skins(gltf: dict[str, Any], bin_chunk: bytes, warnings: list[str], notes: list[str]) -> dict[str, Any]:
    skins = gltf.get("skins") or []
    nodes = gltf.get("nodes") or []
    accessors = gltf.get("accessors") or []
    info: dict[str, Any] = {"count": len(skins), "joints": 0, "max_skin_joints": 0, "max_influences": 0,
                            "humanoid": None, "missing_humanoid": [], "bad_weights": 0}
    if not skins:
        return info
    joint_names = []
    for s in skins:
        info["joints"] += len(s.get("joints") or [])
        info["max_skin_joints"] = max(info["max_skin_joints"], len(s.get("joints") or []))
        joint_names += [nodes[j].get("name") or f"node#{j}" for j in s.get("joints") or [] if j < len(nodes)]
        if "inverseBindMatrices" not in s:
            warnings.append(f"skin {s.get('name') or '?'} has no inverseBindMatrices — most engines won't be able to use it")
    # weights: sums must be ≈1, at most 4 influences per slot
    bad = 0; zero = 0; checked = 0
    for m in gltf.get("meshes") or []:
        for p in m.get("primitives") or []:
            attrs = p.get("attributes") or {}
            if "JOINTS_0" not in attrs and "WEIGHTS_0" not in attrs:
                continue
            if "JOINTS_0" not in attrs or "WEIGHTS_0" not in attrs:
                warnings.append(f"mesh {m.get('name')}: only one of JOINTS_0/WEIGHTS_0 present — incomplete skin")
                continue
            if "WEIGHTS_1" in attrs:
                notes.append(f"mesh {m.get('name')}: more than 4 influences per vertex (WEIGHTS_1) — Unity/Godot truncate to 4")
            w = read_accessor(gltf, bin_chunk, attrs["WEIGHTS_0"])
            if w is None:
                continue
            w1 = read_accessor(gltf, bin_chunk, attrs["WEIGHTS_1"]) if "WEIGHTS_1" in attrs else None
            for vi, t in enumerate(w):
                checked += 1
                sm = sum(t) + (sum(w1[vi]) if w1 else 0.0)
                infl = sum(1 for x in t if x > 1e-4) + (sum(1 for x in w1[vi] if x > 1e-4) if w1 else 0)
                if infl > info["max_influences"]:
                    info["max_influences"] = infl
                if sm < 1e-6:
                    zero += 1
                elif abs(sm - 1.0) > 0.02:
                    bad += 1
    if zero:
        warnings.append(f"{zero} vertices without weights (sum 0) — they will stay in place when animated in the engine")
    if bad:
        warnings.append(f"{bad} of {checked} vertices have unnormalized weights (sum ≠ 1) — Unity normalizes, Three.js does not: artifacts possible")
    info["bad_weights"] = bad + zero
    # Humanoid coverage
    canon = {c for c in (_canon_bone(n) for n in joint_names) if c}
    missing = [b for b in HUMANOID_BONES if b not in canon]
    required = [b for b in missing if b not in ("LeftToes", "RightToes", "Chest", "UpperChest", "LeftShoulder", "RightShoulder", "Neck")]
    info["humanoid"] = not required
    info["missing_humanoid"] = missing
    if not required:
        notes.append("skeleton is Humanoid-compatible (Unity Humanoid / UE Mannequin): all required bones found" + (f"; optional bones missing: {', '.join(missing)}" if missing else ""))
    elif len(canon) >= 5:
        warnings.append(f"skeleton looks humanoid but is missing bones: {', '.join(required)} — Unity Humanoid won't build an avatar")
    else:
        notes.append("skeleton is not humanoid (Generic) — Unity Humanoid/UE Mannequin require retargeting")
    return info


def _is_pow2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _bad_name(name: str) -> bool:
    return not name or not all(c.isascii() and (c.isalnum() or c in "_-.") for c in name)


# ----------------------------------------------------------------------------
# Contract check
# ----------------------------------------------------------------------------

def inspect(gltf: dict[str, Any], bin_chunk: bytes, path: Path, max_mb: float) -> dict[str, Any]:
    """Collect facts about the asset plus lists of errors/warnings."""
    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    asset = gltf.get("asset") or {}
    if str(asset.get("version")) != "2.0":
        errors.append(f"asset.version = {asset.get('version')!r}, expected '2.0'")

    scenes = gltf.get("scenes") or []
    if not scenes:
        errors.append("no scenes at all (scenes is empty)")
    elif "scene" not in gltf:
        warnings.append("no default scene set ('scene' field) — the runtime may not know what to load")

    meshes = gltf.get("meshes") or []
    if not meshes:
        errors.append("no meshes — the asset has nothing to show")
    accessors = gltf.get("accessors") or []
    nodes = gltf.get("nodes") or []
    materials = gltf.get("materials") or []
    images = gltf.get("images") or []
    buffer_views = gltf.get("bufferViews") or []
    exts = gltf.get("extensionsUsed") or []
    draco = "KHR_draco_mesh_compression" in exts

    # --- geometry: primitives, triangles, UVs, normals, dimensions ---
    prim_count = 0
    triangles = 0
    no_uv: list[str] = []
    no_normal: list[str] = []
    non_tri: list[str] = []
    missing_minmax = False
    mesh_tris = [0] * len(meshes)
    for mi, m in enumerate(meshes):
        mname = m.get("name") or f"mesh#{mi}"
        for p in m.get("primitives") or []:
            prim_count += 1
            attrs = p.get("attributes") or {}
            mode = p.get("mode", 4)
            if mode != 4:
                non_tri.append(mname)
            if "TEXCOORD_0" not in attrs:
                no_uv.append(mname)
            if "NORMAL" not in attrs:
                no_normal.append(mname)
            pos = accessors[attrs["POSITION"]] if "POSITION" in attrs and attrs["POSITION"] < len(accessors) else None
            if pos and ("min" not in pos or "max" not in pos):
                missing_minmax = True
            if "indices" in p and p["indices"] < len(accessors):
                mesh_tris[mi] += accessors[p["indices"]].get("count", 0) // 3
            elif pos:
                mesh_tris[mi] += pos.get("count", 0) // 3
    # triangles drawn: a mesh counts once per node showing it (instances), and per GPU instance
    # (EXT_mesh_gpu_instancing); the file stores each mesh once (unique_triangles)
    uses = [0] * len(meshes)
    for n in nodes:
        mi = n.get("mesh")
        if isinstance(mi, int) and 0 <= mi < len(meshes):
            inst = ((n.get("extensions") or {}).get("EXT_mesh_gpu_instancing") or {}).get("attributes") or {}
            acc = next(iter(inst.values()), None)
            uses[mi] += accessors[acc].get("count", 1) if isinstance(acc, int) and acc < len(accessors) else 1
    triangles = sum(t * u for t, u in zip(mesh_tris, uses))
    unique_triangles = sum(mesh_tris)
    instanced = sum(1 for u in uses if u > 1)
    if instanced:
        notes.append(f"{instanced} mesh{'es' if instanced > 1 else ''} shared by several placements (instances): "
                     f"{unique_triangles:,} triangles stored, {triangles:,} drawn")

    dims = None
    bounds = world_bounds(gltf, bin_chunk)
    if bounds:
        bb_min, bb_max = bounds
        dims = [bb_max[i] - bb_min[i] for i in range(3)]
        longest = max(dims)
        if longest < _MIN_DIM_M:
            warnings.append(f"dimensions {_fmt_dims(dims)} m — asset is under 1 cm: units are probably not meters (mm?)")
        elif longest > _MAX_DIM_M:
            warnings.append(f"dimensions {_fmt_dims(dims)} m — over 100 m: units are probably cm instead of meters, or this is a scene rather than an asset")
        if bb_min[1] < -0.25 * max(longest, 1e-6):
            notes.append(f"asset bottom is {-bb_min[1]:.2f} m below the origin — for objects standing on the floor the contract recommends the origin at the base")
    if missing_minmax or (bounds is None and meshes):
        warnings.append("POSITION accessors have no min/max — dimensions cannot be checked (violates the glTF spec)")

    if no_uv:
        warnings.append(f"no UVs (TEXCOORD_0) on meshes: {_short(no_uv)} — textures and lightmaps won't map in the engine")
    if no_normal:
        warnings.append(f"no normals on meshes: {_short(no_normal)} — the runtime will compute flat ones, lighting will look faceted")
    if non_tri:
        warnings.append(f"non-triangle primitives (mode≠4) on meshes: {_short(non_tri)} — Unity/Unreal won't import them")

    # --- nodes: names, unapplied transforms ---
    unnamed = sum(1 for n in nodes if not n.get("name"))
    if unnamed:
        warnings.append(f"{unnamed} of {len(nodes)} nodes are unnamed — names are needed to address objects at runtime")
    bad_names = [n["name"] for n in nodes if n.get("name") and _bad_name(n["name"])]
    if bad_names:
        warnings.append(f"node names with spaces/non-Latin characters: {_short(bad_names)} — awkward to reference from code")
    scaled = [n.get("name") or f"node#{i}" for i, n in enumerate(nodes)
              if "mesh" in n and any(abs(s - 1.0) > 1e-4 for s in n.get("scale", [1, 1, 1]))]
    if scaled:
        warnings.append(f"scale ≠ 1 on meshes: {_short(scaled)} — the contract requires applied transforms (apply scale)")
    matrices = [n.get("name") or f"node#{i}" for i, n in enumerate(nodes) if "matrix" in n]
    if matrices:
        notes.append(f"nodes with matrix instead of TRS: {_short(matrices)} — animations can't target such nodes")

    # --- materials ---
    if not materials:
        warnings.append("no materials — the engine will apply its default gray")
    else:
        legacy = [m.get("name") or f"mat#{i}" for i, m in enumerate(materials)
                  if "pbrMetallicRoughness" not in m and "KHR_materials_unlit" not in (m.get("extensions") or {})]
        if legacy:
            warnings.append(f"materials without PBR (pbrMetallicRoughness): {_short(legacy)} — the contract requires PBR")
        bad_mat = [m["name"] for m in materials if m.get("name") and _bad_name(m["name"])]
        if bad_mat:
            warnings.append(f"material names with spaces/non-Latin characters: {_short(bad_mat)}")

    # --- textures ---
    tex_info: list[dict[str, Any]] = []
    for i, img in enumerate(images):
        entry: dict[str, Any] = {"name": img.get("name") or f"image#{i}", "mime": img.get("mimeType")}
        if "uri" in img:
            entry["external"] = img["uri"]
            warnings.append(f"texture {entry['name']} is external ({img['uri']}) — pack it into the GLB, otherwise the asset is not self-contained")
        elif "bufferView" in img and img["bufferView"] < len(buffer_views):
            bv = buffer_views[img["bufferView"]]
            blob = bin_chunk[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]
            entry["bytes"] = bv["byteLength"]
            size = image_size(blob)
            if size:
                entry["size"] = list(size)
                if not (_is_pow2(size[0]) and _is_pow2(size[1])):
                    warnings.append(f"texture {entry['name']} {size[0]}×{size[1]} — not a power of two (worse mipmaps/compression in engines)")
                if max(size) > 4096:
                    warnings.append(f"texture {entry['name']} {size[0]}×{size[1]} — larger than 4096, excessive for web and mobile")
        tex_info.append(entry)

    # --- extensions ---
    for e in exts:
        if e in _EXT_NOTES:
            notes.append(_EXT_NOTES[e])
        elif e not in _SAFE_EXTENSIONS:
            warnings.append(f"extension {e} — not all targets understand it, test it in the engines")
    required = gltf.get("extensionsRequired") or []
    for e in required:
        if e != "KHR_draco_mesh_compression" and e not in _SAFE_EXTENSIONS:
            errors.append(f"required extension {e} — the file won't load without it, and support is not guaranteed")

    skin_info = inspect_skins(gltf, bin_chunk, warnings, notes)

    animations = gltf.get("animations") or []
    anim_names = [a.get("name") or f"anim#{i}" for i, a in enumerate(animations)]
    if animations and any(not a.get("name") for a in animations):
        warnings.append("some animations are unnamed — code will have to select them by index")

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        warnings.append(f"size {size_mb:.1f} MB exceeds the contract limit of {max_mb:.0f} MB — optimize geometry/textures")

    return {
        "file": path.name,
        "size_mb": round(size_mb, 3),
        "bin_kb": round(len(bin_chunk) / 1024),
        "scenes": len(scenes), "nodes": len(nodes), "meshes": len(meshes), "primitives": prim_count,
        "triangles": triangles, "unique_triangles": unique_triangles, "instanced_meshes": instanced, "dims_m": [round(d, 4) for d in dims] if dims else None,
        "bounds_min_m": [round(v, 4) for v in bounds[0]] if bounds else None,
        "materials": len(materials), "textures": len(gltf.get("textures") or []), "images": tex_info,
        "animations": anim_names, "skins": skin_info["count"], "joints": skin_info["joints"],
        "humanoid": skin_info["humanoid"], "missing_humanoid": skin_info["missing_humanoid"],
        "max_skin_joints": skin_info["max_skin_joints"], "max_influences": skin_info["max_influences"],
        "draw_calls": _draw_calls(gltf), "max_texture": max((max(t["size"]) for t in tex_info if t.get("size")), default=0),
        "texture_mb": round(sum(t["size"][0] * t["size"][1] * 4 * 4 / 3 for t in tex_info if t.get("size")) / (1024 * 1024), 3),
        "draco": draco, "extensions": exts,
        "errors": errors, "warnings": warnings, "notes": notes,
    }


def _draw_calls(gltf: dict[str, Any]) -> int:
    """Approximate draw calls: every node that instances a mesh draws each of its primitives."""
    meshes = gltf.get("meshes") or []
    return sum(len(meshes[n["mesh"]].get("primitives") or []) for n in gltf.get("nodes") or []
               if "mesh" in n and n["mesh"] < len(meshes))


def load_profiles() -> dict[str, Any]:
    """core/profiles.json (next to this file; the Blender add-on bundles a copy next to its validator copy)."""
    path = Path(__file__).with_name("profiles.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"order": [], "profiles": {}}


def check_budget(r: dict[str, Any], profile: str, kind: str = "asset", profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare a report with a tier's budget. kind: 'asset' (one exported file) or 'scene' (a level / diorama)."""
    profiles = profiles or load_profiles()
    spec = profiles["profiles"][profile]
    b = spec[kind]
    items = [("tris", r["triangles"], b["max_tris"])]
    if kind == "asset":
        items += [("texture size", r["max_texture"], b["max_texture"]), ("texture memory, MB", r["texture_mb"], b["max_texture_mb"]),
                  ("materials", r["materials"], b["max_materials"]), ("bones per skin", r["max_skin_joints"], b["max_bones"]),
                  ("influences per vertex", r["max_influences"], b["max_influences"]), ("file, MB", r["size_mb"], b["max_file_mb"])]
    else:
        items += [("draw calls", r["draw_calls"], b["max_draw_calls"])]
    rows = [{"name": n, "value": v, "limit": lim, "ok": v <= lim} for n, v, lim in items]
    return {"profile": profile, "label": spec["label"], "kind": kind, "ok": all(x["ok"] for x in rows), "items": rows}


def fits(r: dict[str, Any], kind: str = "asset", profiles: dict[str, Any] | None = None) -> list[str]:
    profiles = profiles or load_profiles()
    return [p for p in profiles["order"] if check_budget(r, p, kind, profiles)["ok"]]


def _fmt_dims(d: list[float]) -> str:
    return "×".join(f"{v:.3g}" for v in d)


def _short(items: list[str], n: int = 5) -> str:
    return ", ".join(items[:n]) + (f" (+{len(items) - n})" if len(items) > n else "")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def validate(path: Path, max_mb: float, strict: bool = False, as_json: bool = False,
             profiles: list[str] | None = None, kind: str = "asset") -> int:
    """Validate an asset against the contract. Prints a report, returns the exit code."""
    try:
        gltf, bin_chunk = parse_glb(path)
    except (GlbError, json.JSONDecodeError, OSError) as exc:
        if as_json:
            print(json.dumps({"file": path.name, "errors": [str(exc)], "fatal": True}, ensure_ascii=False))
        else:
            print(f"✗ {path.name}: {exc}")
        return 2

    r = inspect(gltf, bin_chunk, path, max_mb)
    table = load_profiles()
    r["fits"] = fits(r, kind, table)
    r["budgets"] = [check_budget(r, p, kind, table) for p in (profiles or [])]
    for bud in r["budgets"]:
        for x in bud["items"]:
            if not x["ok"]:
                r["warnings"].append(f"{bud['label']} budget: {x['name']} {x['value']:g} > {x['limit']:g}")
    failed = bool(r["errors"]) or (strict and bool(r["warnings"]))
    r["ok"] = not failed

    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1 if failed else 0

    print(f"— MeshGate validate: {r['file']} —")
    print(f"  size:        {r['size_mb']:.2f} MB (BIN {r['bin_kb']} KB)")
    print(f"  scenes:      {r['scenes']}   nodes: {r['nodes']}   meshes: {r['meshes']}   primitives: {r['primitives']}   triangles: {r['triangles']:,}")
    print(f"  dimensions:  {_fmt_dims(r['dims_m']) + ' m (X×Y×Z, Y up)' if r['dims_m'] else '—'}")
    print(f"  materials:   {r['materials']}   textures: {r['textures']}   animations: {len(r['animations'])}"
          + (f" ({', '.join(r['animations'])})" if r["animations"] else "") + f"   skins: {r['skins']}"
          + (f" ({r['joints']} bones, Humanoid: {'yes' if r['humanoid'] else 'no'})" if r["skins"] else ""))
    for t in r["images"]:
        size = f"{t['size'][0]}×{t['size'][1]}" if t.get("size") else "?"
        print(f"    · {t['name']}: {size}, {t.get('mime') or '?'}, {t.get('bytes', 0) / 1024:.0f} KB")
    print(f"  Draco compression: {'yes' if r['draco'] else 'no'}   extensions: {', '.join(r['extensions']) or '—'}")
    print(f"  performance: {r['draw_calls']} draw calls, textures {r['texture_mb']:g} MB (max {r['max_texture'] or '—'}px)"
          + (f", ≤{r['max_influences']} influences/vertex, {r['max_skin_joints']} bones/skin" if r["skins"] else "")
          + f"   fits: {', '.join(r['fits']) or 'none of the tiers'}")
    for bud in r["budgets"]:
        cells = "  ".join(f"{'✓' if x['ok'] else '✗'} {x['name']} {x['value']:g}/{x['limit']:g}" for x in bud["items"])
        print(f"  {bud['label']:18} {cells}")
    for n in r["notes"]:
        print(f"  · {n}")
    for w in r["warnings"]:
        print(f"  ⚠ {w}")
    for e in r["errors"]:
        print(f"  ✗ {e}")
    if r["errors"]:
        print("Result: does NOT comply with the contract.")
    elif failed:
        print("Result: valid glTF 2.0, but there are warnings (--strict).")
    else:
        print("Result: valid glTF 2.0, contract satisfied." + (" (with warnings)" if r["warnings"] else ""))
    return 1 if failed else 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):   # Windows consoles and pipes default to cp1252; MeshGate prints ✓ and —
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="MeshGate — GLB validator against the asset contract.")
    ap.add_argument("glb", type=Path, nargs="+", help="path to .glb (several allowed)")
    ap.add_argument("--max-mb", type=float, default=25.0, help="size limit in MB (default 25)")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors (for CI)")
    ap.add_argument("--json", action="store_true", help="JSON report")
    ap.add_argument("--profile", default="", help="check against quality tier budgets: mobile-low, mobile-mid, mobile-high, pc, "
                                                   "a comma list, or 'all' (core/profiles.json); exceeding a budget is a warning")
    ap.add_argument("--scene", action="store_true", help="use the tier's scene budget (whole level) instead of the per-asset one")
    args = ap.parse_args()
    order = load_profiles()["order"]
    chosen = order if args.profile == "all" else [p.strip() for p in args.profile.split(",") if p.strip()]
    unknown = [p for p in chosen if p not in order]
    if unknown:
        ap.error(f"unknown profile(s) {unknown}; known: {', '.join(order)}")
    worst = 0
    for i, path in enumerate(args.glb):
        if i and not args.json:
            print()
        if not path.is_file():
            print(json.dumps({"file": str(path), "errors": ["file not found"], "fatal": True}, ensure_ascii=False)
                  if args.json else f"✗ file not found: {path}")
            worst = max(worst, 2)
            continue
        worst = max(worst, validate(path, args.max_mb, args.strict, args.json, chosen, "scene" if args.scene else "asset"))
    return worst


if __name__ == "__main__":
    sys.exit(main())
