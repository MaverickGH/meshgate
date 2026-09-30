"""Morph targets for customising a model the way a game's character creator does — a wider head, bigger ears, longer
legs, a rounder belly — as shape keys that go into the GLB and FBX (glTF morph targets, Unity and Godot blend shapes,
Unreal morph targets). Studio moves them with sliders at once; a game can move them at run time.

A morph is a deformation of space, not of one mesh: every vertex inside its region moves by the same rule, so the
same morph fits every quality tier, every LOD and the ink outline, whatever their triangles are. A spec:

    {"name": "ear_size", "at": [x, y, z], "radius": 0.2, "scale": [1.3, 1.3, 1.3], "move": [0, 0, 0.02],
     "inflate": 0.0, "above": None, "below": None, "blend": 0.04, "boxes": [[lo, hi], …], "margin": 0.03,
     "stretch": [z0, z1, dz], "mirror": True, "two_sided": True, "value": 0.0}

At full weight a vertex p goes to at + scale·(p − at) + move, plus inflate away from `at`; its weight fades from 1
inside half the radius to 0 at the radius, from 0 at `above` to 1 a `blend` higher (and the other way for `below`),
and to 0 a `margin` outside the `boxes` (the pieces the morph is meant for). `mirror` adds the same on the other side
(x → −x). A two-sided morph also gets "<name>_neg": the opposite change (scale → 1/scale, move and inflate negated).
Pure bpy/mathutils.
"""
from __future__ import annotations

import json

from mathutils import Vector

NEG = "_neg"


def _smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _weight(spec: dict, p: Vector, at: Vector) -> float:
    w = 1.0
    r = spec.get("radius")
    if r:
        w *= _smooth((1 - (p - at).length / r) / 0.5)
        if w <= 0:
            return 0.0
    blend = max(float(spec.get("blend") or 0.04), 1e-4)
    if spec.get("above") is not None:
        w *= _smooth((p.z - spec["above"]) / blend)
    if spec.get("below") is not None:
        w *= _smooth((spec["below"] - p.z) / blend)
    boxes = spec.get("boxes")
    if boxes and w > 0:
        margin = max(float(spec.get("margin") or 0.03), 1e-4)
        out = min(max(max(lo[k] - p[k], 0.0, p[k] - hi[k]) for k in range(3)) for lo, hi in boxes)
        w *= _smooth(1 - out / margin)
    return w


def _delta(spec: dict, p: Vector, n: Vector, sign: float, mirror_x: bool) -> Vector:
    at = Vector(spec["at"])
    move = Vector(spec.get("move") or (0, 0, 0))
    if mirror_x:
        at.x, move.x = -at.x, -move.x
        spec = dict(spec, boxes=[[(-hi[0], lo[1], lo[2]), (-lo[0], hi[1], hi[2])] for lo, hi in spec.get("boxes") or []])
    w = _weight(spec, p, at)
    if w <= 0:
        return Vector()
    s = spec.get("scale", 1.0)
    s = Vector((s, s, s) if isinstance(s, (int, float)) else s)
    inflate = float(spec.get("inflate") or 0.0)
    if sign < 0:
        s = Vector([1 / max(c, 1e-3) for c in s])
        move, inflate = -move, -inflate
    target = at + Vector([c * k for c, k in zip(p - at, s)]) + move
    out = p - at   # inflate pushes away from the morph's centre: the inside-out ink hull moves with the skin under it
    out = out.normalized() if out.length > 1e-9 else n
    d = (target - p) * w + out * (inflate * w)
    if spec.get("stretch"):   # the part between two heights grows by dz; everything above it rises by as much
        z0, z1, dz = (float(c) for c in spec["stretch"])
        t = min(1.0, max(0.0, (p.z - z0) / max(z1 - z0, 1e-6)))
        d.z += (dz if sign > 0 else -dz) * t * w
    return d


def apply(obj, specs: list, spend: dict | None = None) -> int:
    """Add the morphs as shape keys on a mesh object (world-space specs); keeps them on the object for its LODs.
    Returns how many keys it added (a morph whose region misses the object adds none). spend = {"left": bytes,
    "sparse": bool, "dropped": set()} keeps the file within a tier's budget: a key that would cost more than is
    left is not made (a morph target stores every vertex it moves, or every vertex when the exporter cannot write
    sparse ones), and its morph is listed as dropped."""
    if obj.type != "MESH" or not specs or not obj.data.vertices or obj.data.users > 1:
        return 0
    me = obj.data
    mw = obj.matrix_world
    rot = mw.to_3x3()
    inv = rot.inverted()
    pts = [mw @ v.co for v in me.vertices]
    nrm = [(rot @ v.normal).normalized() for v in me.vertices]
    made, kept = 0, []
    per_vertex = len(me.loops) / max(len(me.vertices), 1)   # a flat-shaded GLB splits vertices per face
    for spec in specs:
        if spend is not None and spec["name"] in spend["dropped"]:
            continue
        halves = []   # both halves of a slider, or neither
        for sign in ((1.0, -1.0) if spec.get("two_sided", True) else (1.0,)):
            deltas = []
            for p, n in zip(pts, nrm):
                d = _delta(spec, p, n, sign, False)
                if spec.get("mirror"):
                    d += _delta(spec, p, n, sign, True)
                deltas.append(d)
            moved = sum(1 for d in deltas if d.length >= 1e-5)
            if moved:
                halves.append((sign, deltas, moved))
        if not halves:
            continue
        if spend is not None:
            cost = sum((m * 16 if spend["sparse"] else len(d) * 12) * per_vertex for _, d, m in halves)
            if cost > spend["left"]:
                spend["dropped"].add(spec["name"])
                continue
            spend["left"] -= cost
        kept.append(spec)
        for sign, deltas, _ in halves:
            if me.shape_keys is None:
                obj.shape_key_add(name="Basis", from_mix=False)
            key = obj.shape_key_add(name=spec["name"] + ("" if sign > 0 else NEG), from_mix=False)
            for kp, v, d in zip(key.data, me.vertices, deltas):
                kp.co = v.co + inv @ d
            value = float(spec.get("value") or 0.0)
            key.value = max(0.0, value if sign > 0 else -value)
            made += 1
    if made:
        old = json.loads(obj.get("meshgate_morphs") or "[]")
        obj["meshgate_morphs"] = json.dumps(old + [k for k in kept if k["name"] not in {o["name"] for o in old}])
    return made


def reapply(obj) -> int:
    """The morphs of the mesh it was made from, on a copy with other triangles (an LOD): its shape keys are cleared
    first (a decimated copy cannot keep them) and rebuilt from the specs."""
    specs = obj.get("meshgate_morphs")
    if not specs:
        return 0
    if obj.data.shape_keys:
        obj.shape_key_clear()
    return apply(obj, json.loads(specs))


def strip(obj) -> None:
    """Remove shape keys before a modifier is applied (decimation cannot apply to a mesh with shape keys)."""
    if obj.type == "MESH" and obj.data.shape_keys:
        obj.shape_key_clear()


def deform(obj, specs: list) -> int:
    """Move a mesh's vertices for good by the specs (a fit, not a slider): the full change of each, summed.
    Returns how many vertices moved."""
    if obj.type != "MESH" or not specs or not obj.data.vertices or obj.data.shape_keys:
        return 0
    mw = obj.matrix_world
    rot = mw.to_3x3()
    inv = rot.inverted()
    moved = 0
    for v in obj.data.vertices:
        p = mw @ v.co
        n = (rot @ v.normal).normalized()
        d = Vector()
        for spec in specs:
            d += _delta(spec, p, n, 1.0, False)
        if d.length >= 1e-6:
            v.co = v.co + inv @ d
            moved += 1
    if moved:
        obj.data.update()
    return moved
