"""MeshGate live link: an AI tool drives this Blender through the kit, seeing what it builds.

A small server on localhost (a random port and token, written to ~/.meshgate/blender_link.json) takes one JSON request
per line and answers with one JSON line. `meshgate.py mcp` turns these into MCP tools for Claude Code and other AI
clients. Requests:

    {"token": …, "cmd": "info"}                                  the live scene: objects, sizes, triangles
    {"token": …, "cmd": "run", "code": "def build(mg): …", "tier": "pc", "look": "none"}
                                                                   build kit code into the "MeshGate live" scene
    {"token": …, "cmd": "facts"}                                 measured facts: floating pieces, triangles per line…
    {"token": …, "cmd": "measure", "a": "line 9", "b": "line 15"} the gap between two parts (build lines or objects)
    {"token": …, "cmd": "render", "closeups": [...]}             a sheet of four views (+ close-ups), as a PNG path
    {"token": …, "cmd": "export", "path": "…/asset.glb"}         a checked GLB (+ FBX) by the MeshGate contract

Only kit code runs (the same guard rails as `meshgate.py gen`): no raw bpy, no files, no network. Builds go to their
own scene, so the artist's scene is never touched. In the open Blender the server runs beside the UI (requests are
handled on Blender's main thread by a timer); a background Blender serves with serve_forever().
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import math
import os
import queue
import random
import secrets
import socket
import subprocess
import tempfile
import threading
from pathlib import Path
from array import array

import bpy
import mathutils

from . import export, modeling

HERE = Path(__file__).resolve().parent
LIVE_SCENE = "MeshGate live"
_state: dict = {"server": None, "thread": None, "queue": None, "token": None, "port": None,
                "edit_undo": None, "edit_revision": 0}


def link_file() -> Path:
    base = os.environ.get("MESHGATE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".meshgate")
    return Path(base) / "blender_link.json"


def _safety():
    here = HERE / "kitlib" / "safety.py"
    src = here if here.exists() else HERE.parents[1] / "generate" / "safety.py"
    spec = importlib.util.spec_from_file_location("meshgate_live_safety", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _window():
    if bpy.app.background:   # a background Blender has a stand-in window; switching its scene crashes the exporter
        return None
    wm = bpy.context.window_manager
    return bpy.context.window or (wm.windows[0] if wm and len(wm.windows) else None)


def _live_scene(clear: bool) -> bpy.types.Scene:
    """The scene live builds go to. A background Blender is ours alone: its scene becomes the live one. In the open
    Blender a scene of its own, shown in the window — the artist's scene stays as it was."""
    win = _window()
    if win is None:
        scene = bpy.context.scene
        scene.name = LIVE_SCENE
    else:
        scene = bpy.data.scenes.get(LIVE_SCENE) or bpy.data.scenes.new(LIVE_SCENE)
        win.scene = scene
    if clear:
        for o in list(scene.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    return scene


def _in_scene(scene):
    """A context for the kit: the window showing the live scene, or (background) the scene itself."""
    win = _window()
    if win is not None:
        return bpy.context.temp_override(window=win, scene=scene, view_layer=scene.view_layers[0])
    return contextlib.nullcontext()   # background: the live scene is the current one; an override without a
    #                                   window crashes the glTF exporter (it sets context.window.scene)


def _scene_objects():
    scene = bpy.data.scenes.get(LIVE_SCENE) or bpy.context.scene
    return scene, [o for o in scene.objects if o.type in ("MESH", "ARMATURE", "EMPTY")]


# ---------------------------------------------------------------------------- commands (main thread)

def cmd_info(req: dict) -> dict:
    scene, objs = _scene_objects()
    scene.view_layers[0].update()
    out = []
    for o in objs:
        item = {"name": o.name, "type": o.type, "location": [round(x, 4) for x in o.matrix_world.translation]}
        if o.type == "MESH":
            item["revision"] = _revision(o) if scene.name == LIVE_SCENE else None
            item["vertices"] = len(o.data.vertices)
            pts = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
            item["size_m"] = [round(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in range(3)]
            item["tris"] = sum(len(p.vertices) - 2 for p in o.data.polygons)
            item["materials"] = [m.name for m in o.data.materials if m]
        out.append(item)
    return {"scene": scene.name, "objects": out, "tris": sum(i.get("tris", 0) for i in out)}


def cmd_run(req: dict) -> dict:
    code = str(req.get("code") or "")
    safety = _safety()
    problems = safety.check(code)
    if problems:
        return {"ok": False, "problems": [f"safety: {p}" for p in problems]}
    tier = req.get("tier") if req.get("tier") in modeling.TIERS else "pc"
    look = req.get("look") if req.get("look") in ("none", "faceted") else "none"
    _clear_edit_undo()
    scene = _live_scene(clear=True)
    with _in_scene(scene):
        budget = export.load_profiles()["profiles"][tier]["asset"]
        kit = modeling.Kit(tier, name=str(req.get("name") or "live"), max_materials=budget["max_materials"], finish=look,
                           max_tris=budget["max_tris"], params=req.get("params") or {},
                           max_texture=budget.get("max_texture"), max_texture_mb=budget.get("max_texture_mb"))
        g = safety.restricted_globals({"math": math, "random": random, "mathutils": mathutils})
        try:
            exec(compile(code, "<generated>", "exec"), g)  # noqa: S102 — passed safety.check above
            g["build"](kit)
            notes = kit._finalize()
        except Exception as exc:  # noqa: BLE001 — the error goes back to the AI
            import traceback
            frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<generated>"]
            where = f"line {frames[-1].lineno}: " if frames else ""
            return {"ok": False, "problems": [f"{where}{type(exc).__name__}: {exc}"]}
        facts = kit._facts()
    for obj in _scene_objects()[1]:
        if obj.type == "MESH":
            _revision(obj, force=True)   # vertex IDs from a previous build must never address this new mesh
    info = cmd_info({})
    return {"ok": True, "notes": notes, "facts": facts, "tris": info["tris"], "size_m": facts.get("size_m"),
            "params": kit._params, "budget_tris": budget["max_tris"]}


def cmd_facts(req: dict) -> dict:
    scene, _ = _scene_objects()
    with _in_scene(scene):
        kit = modeling.Kit.__new__(modeling.Kit)   # facts only: no palette, no scene reset
        kit._sources = {}
        return kit._facts()


def _vector(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 3 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError(f"{name} must be three finite numbers in world metres")
    return mathutils.Vector(value)


def _integer(value, name, lo, hi):
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise ValueError(f"{name} must be an integer from {lo} to {hi}")
    return value


def _mesh_stamp(obj):
    """Track base geometry and world placement, including edits made manually in Blender."""
    mesh = obj.data
    digest = hashlib.sha256()
    digest.update(array("d", [c for row in obj.matrix_world for c in row]).tobytes())
    for collection, key, width, kind in ((mesh.vertices, "co", 3, "f"), (mesh.edges, "vertices", 2, "I"),
                                         (mesh.loops, "vertex_index", 1, "I"), (mesh.polygons, "loop_total", 1, "I")):
        values = array(kind, [0])*(len(collection)*width)
        collection.foreach_get(key, values)
        digest.update(len(collection).to_bytes(8, "little"))
        digest.update(values.tobytes())
    source = mesh.attributes.get(modeling.SRC_ATTR)
    if source:
        values = array("i", [0])*len(source.data)
        source.data.foreach_get("value", values)
        digest.update(values.tobytes())
    return digest.hexdigest()


def _revision(obj, force=False):
    stamp = _mesh_stamp(obj)
    revision = int(obj.get("meshgate_edit_revision", 0))
    if force or obj.get("meshgate_edit_stamp") != stamp:
        revision = max(_state["edit_revision"], revision)+1
        _state["edit_revision"] = revision
        obj["meshgate_edit_revision"], obj["meshgate_edit_stamp"] = revision, stamp
    return revision


def _selection(req):
    """Resolve an object or build-line label, then intersect with a world-space region and vertex IDs."""
    scene, objs = _scene_objects()
    if scene.name != LIVE_SCENE:
        raise ValueError("build a MeshGate live scene before inspecting or editing its mesh")
    scene.view_layers[0].update()
    spec = str(req.get("part") or "").strip()
    words = spec.split()
    line = int(words[1]) if len(words) == 2 and words[0].lower() == "line" and words[1].isdigit() else None
    candidates = []
    for obj in objs:
        if obj.type != "MESH":
            continue
        attr = obj.data.attributes.get(modeling.SRC_ATTR)
        ids = {i for i, item in enumerate(attr.data) if item.value == line} if line is not None and attr else set()
        if line is None and obj.name == spec:
            ids = set(range(len(obj.data.vertices)))
        if ids:
            candidates.append((obj, ids))
    if len(candidates) != 1:
        raise ValueError(f"part '{spec}' matched {len(candidates)} meshes; use one exact object name or build line")
    obj, ids = candidates[0]
    if obj.mode != "OBJECT" or obj.data.shape_keys:
        raise ValueError("local edits require Object mode and a mesh without shape keys")
    if "vertices" in req:
        values = req["vertices"]
        if not isinstance(values, list) or not values:
            raise ValueError("vertices must be a nonempty list of mesh vertex IDs")
        explicit = {_integer(i, "vertex ID", 0, len(obj.data.vertices)-1) for i in values}
        if not explicit <= ids:
            raise ValueError("vertex IDs must belong to the selected part")
        ids &= explicit
    region = req.get("region")
    weights = {i: 1.0 for i in ids}
    if region is not None:
        if not isinstance(region, dict):
            raise ValueError("region must be a box {min,max} or sphere {center,radius}")
        if set(region) == {"min", "max"}:
            lo, hi = _vector(region["min"], "region min"), _vector(region["max"], "region max")
            if any(a > b for a, b in zip(lo, hi)):
                raise ValueError("region min must not exceed max")
            weights = {i: 1.0 for i in ids if all(a <= p <= b for a,p,b in
                       zip(lo, obj.matrix_world @ obj.data.vertices[i].co, hi))}
        elif set(region) <= {"center", "radius", "falloff"} and {"center", "radius"} <= set(region):
            center = _vector(region["center"], "region center")
            radius = region["radius"]
            if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not math.isfinite(radius) or radius <= 0:
                raise ValueError("region radius must be finite and positive")
            falloff = region.get("falloff", "smooth")
            if falloff not in ("smooth", "constant"):
                raise ValueError("region falloff must be smooth or constant")
            weights = {}
            for i in ids:
                distance = (obj.matrix_world @ obj.data.vertices[i].co - center).length
                if distance < radius:
                    t = 1 - distance/radius
                    weights[i] = t*t*(3-2*t) if falloff == "smooth" else 1.0
        else:
            raise ValueError("region must be a box {min,max} or sphere {center,radius,falloff?}")
    if not weights:
        raise ValueError("selection contains no vertices")
    return obj, weights


def _mesh_quality(obj):
    """Inspect the complete source mesh; selection/page cuts are not mesh boundaries."""
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        unseen = set(bm.verts)
        components = []
        while unseen:
            seed = unseen.pop()
            stack, count = [seed], 0
            while stack:
                vertex = stack.pop()
                count += 1
                for edge in vertex.link_edges:
                    other = edge.other_vert(vertex)
                    if other in unseen:
                        unseen.remove(other)
                        stack.append(other)
            components.append(count)
        issues = {
            "boundary_edges": [e.index for e in bm.edges if e.is_boundary],
            "nonmanifold_edges": [e.index for e in bm.edges if not e.is_manifold],
            "wire_edges": [e.index for e in bm.edges if e.is_wire],
            "loose_vertices": [v.index for v in bm.verts if not v.link_edges],
            "degenerate_faces": [f.index for f in bm.faces if f.calc_area() <= 1e-12],
        }
        positions = [obj.matrix_world @ v.co for v in bm.verts]
        return {"scope": "whole_object", "component_count": len(components),
                "component_vertex_counts": sorted(components, reverse=True)[:20],
                "bounds": {"min": [min(p[k] for p in positions) for k in range(3)],
                           "max": [max(p[k] for p in positions) for k in range(3)]},
                "counts": {name: len(ids) for name, ids in issues.items()},
                "samples": {name: ids[:20] for name, ids in issues.items()},
                "problem_edges": [{"id": i, "vertices": [v.index for v in bm.edges[i].verts]}
                                  for i in issues["nonmanifold_edges"][:20]]}
    finally:
        bm.free()


def cmd_mesh(req: dict) -> dict:
    obj, weights = _selection(req)
    offset = _integer(req.get("offset", 0), "offset", 0, len(weights))
    limit = _integer(req.get("limit", 200), "limit", 1, 500)
    ids = sorted(weights)[offset:offset+limit]
    normals = obj.matrix_world.inverted().transposed().to_3x3()
    page = set(ids)
    return {"ok": True, "part": obj.name, "revision": _revision(obj),
            "selected": len(weights), "vertex_count": len(obj.data.vertices), "face_count": len(obj.data.polygons),
            "quality": _mesh_quality(obj),
            "vertices": [{"id": i, "position": list(obj.matrix_world @ obj.data.vertices[i].co),
                          "normal": list((normals @ obj.data.vertices[i].normal).normalized()), "weight": weights[i]}
                         for i in ids],
            "faces": [{"id": p.index, "vertices": list(p.vertices),
                       "center": list(obj.matrix_world @ p.center),
                       "normal": list((normals @ p.normal).normalized()), "material": p.material_index}
                      for p in obj.data.polygons
                      if set(p.vertices) <= page],
            "next_offset": offset+len(ids) if offset+len(ids) < len(weights) else None}


def _clear_edit_undo():
    history = _state.pop("edit_history", [])
    previous = _state.get("edit_undo")
    if previous and not history:
        history = [previous]
    meshes = {item["before"] for item in history}
    for mesh in meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    _state["edit_undo"] = None


def cmd_edit(req: dict) -> dict:
    obj, weights = _selection(req)
    revision = _revision(obj)
    if _integer(req.get("revision"), "revision", 0, 2**31-1) != revision:
        raise ValueError("stale mesh revision; inspect the part with blender_mesh before editing")
    operation = req.get("operation")
    if operation in {"extrude", "inset", "bridge", "subdivide", "symmetrize"}:
        candidate, selected_faces = _topology(obj, weights, req)
        result = _commit_edit(obj, candidate, len(weights), operation)
        result.update(faces=selected_faces, vertex_count=len(candidate.vertices), face_count=len(candidate.polygons))
        return result
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if operation == "move":
        delta = _vector(req.get("delta"), "delta")
        for i, weight in weights.items():
            points[i] += delta*weight
    elif operation == "scale":
        factors = _vector(req.get("factors"), "factors")
        if any(v <= 0 for v in factors):
            raise ValueError("scale factors must be positive")
        pivot = _vector(req["pivot"], "pivot") if "pivot" in req else sum(
            (points[i] for i in weights), mathutils.Vector())/len(weights)
        for i, weight in weights.items():
            scaled = pivot + mathutils.Vector([(points[i][a]-pivot[a])*factors[a] for a in range(3)])
            points[i] = points[i].lerp(scaled, weight)
    elif operation == "smooth":
        strength = req.get("strength", .5)
        if isinstance(strength, bool) or not isinstance(strength, (int,float)) or not math.isfinite(strength) or not 0 < strength <= 1:
            raise ValueError("strength must be in (0,1]")
        iterations = _integer(req.get("iterations", 3), "iterations", 1, 30)
        links = {i: set() for i in weights}
        for edge in obj.data.edges:
            a,b = edge.vertices
            if a in links:
                links[a].add(b)
            if b in links:
                links[b].add(a)
        for _ in range(iterations):
            moves = {i: points[i].lerp(sum((points[j] for j in neighbours), mathutils.Vector())/len(neighbours),
                                      strength*weights[i]) for i, neighbours in links.items() if neighbours}
            for i, point in moves.items():
                points[i] = point
    else:
        raise ValueError("operation must be move, scale, smooth, extrude, inset, bridge, subdivide or symmetrize")
    inverse = obj.matrix_world.inverted()
    local = {i: inverse @ points[i] for i in weights}
    if any(not math.isfinite(c) for p in local.values() for c in p):
        raise ValueError("edit produced nonfinite coordinates")
    candidate = obj.data.copy()   # all work is validated before committing; instances keep their own geometry
    try:
        for i, point in local.items():
            candidate.vertices[i].co = point
        if candidate.has_custom_normals:
            candidate.normals_split_custom_set([(0,0,0)]*len(candidate.loops))
        candidate.update()
    except Exception:
        bpy.data.meshes.remove(candidate)
        raise
    return _commit_edit(obj, candidate, len(weights), operation)


def _commit_edit(obj, candidate, changed, operation):
    history = _state.setdefault("edit_history", [])
    before = obj.data
    obj.data = candidate
    revision = _revision(obj, force=True)
    _state["edit_undo"] = {"object": obj, "before": before, "after": candidate, "changed": changed,
                           "stamp": obj["meshgate_edit_stamp"]}
    history.append(_state["edit_undo"])
    if len(history) > 10:
        expired = history.pop(0)["before"]
        if expired.users == 0:
            bpy.data.meshes.remove(expired)
    return {"ok": True, "part": obj.name, "revision": revision, "changed": changed,
            "operation": operation, "undo_available": True}


def _topology(obj, weights, req):
    """Native BMesh operators on a private copy, in world metres. Commit only a valid result."""
    import bmesh
    bm = bmesh.new()
    candidate = None
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bmesh.ops.transform(bm, matrix=obj.matrix_world, verts=list(bm.verts))
        operation = req["operation"]
        if operation == "symmetrize":
            if len(weights) != len(bm.verts):
                raise ValueError("symmetrize requires the entire mesh object, without a region or vertex subset")
            keep = req.get("keep", "+x")
            if keep not in {"+x", "-x"}:
                raise ValueError("symmetrize keep must be +x or -x")
            plane = req.get("plane", 0.0)
            if isinstance(plane, bool) or not isinstance(plane, (int,float)) or not math.isfinite(plane):
                raise ValueError("symmetry plane must be finite world x in metres")
            for vert in bm.verts:
                vert.co.x -= plane
            bmesh.ops.symmetrize(bm, input=list(bm.verts)+list(bm.edges)+list(bm.faces),
                                 direction="X" if keep == "+x" else "-X", dist=1e-6)
            for vert in bm.verts:
                vert.co.x += plane
            selected = list(bm.faces)
        elif operation == "bridge":
            loops = req.get("loops")
            if not isinstance(loops, list) or len(loops) != 2 or any(not isinstance(loop, list) for loop in loops):
                raise ValueError("bridge requires two closed vertex-ID loops")
            if len(loops[0]) < 3 or len(loops[0]) != len(loops[1]):
                raise ValueError("bridge loops must have the same count of at least three vertices")
            edges, used = [], set()
            for loop in loops:
                ids = [_integer(i, "loop vertex", 0, len(bm.verts)-1) for i in loop]
                if len(set(ids)) != len(ids) or used.intersection(ids) or not set(ids) <= weights.keys():
                    raise ValueError("bridge loops must be disjoint, unique and inside the selected part")
                used.update(ids)
                for a,b in zip(ids, ids[1:]+ids[:1]):
                    edge = bm.edges.get((bm.verts[a],bm.verts[b]))
                    if edge is None or len(edge.link_faces) != 1:
                        raise ValueError("bridge needs existing boundary edges with exactly one adjacent face")
                    edges.append(edge)
            result = bmesh.ops.bridge_loops(bm, edges=edges, use_pairs=True)
            selected = result["faces"]
        else:
            ids = req.get("faces")
            if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
                raise ValueError("extrude/inset requires distinct face IDs from blender_mesh")
            selected = [bm.faces[_integer(i,"face ID",0,len(bm.faces)-1)] for i in ids]
            if any(not all(v.index in weights for v in face.verts) for face in selected):
                raise ValueError("faces must lie entirely inside the selected part/region")
            faces = set(selected)
            boundary = {edge for face in faces for edge in face.edges
                        if sum(f in faces for f in edge.link_faces) == 1}
            if not boundary and operation != "subdivide":
                raise ValueError("select a face region with a boundary, not the entire closed surface")
            if any(len(edge.link_faces) > 2 for face in faces for edge in face.edges):
                raise ValueError("face region contains nonmanifold edges")
            if operation == "subdivide":
                cuts = _integer(req.get("cuts", 1), "cuts", 1, 3)
                bmesh.ops.subdivide_edges(bm, edges=list({e for f in selected for e in f.edges}),
                                          cuts=cuts, use_grid_fill=True, smooth=0.0)
                selected = list(bm.faces)
            elif operation == "extrude":
                delta = _vector(req.get("delta"),"delta")
                if delta.length < 1e-9:
                    raise ValueError("extrusion delta must be nonzero")
                result = bmesh.ops.extrude_face_region(bm,geom=selected)
                raised = [v for v in result["geom"] if isinstance(v,bmesh.types.BMVert)]
                selected_new = [f for f in result["geom"] if isinstance(f,bmesh.types.BMFace)]
                bmesh.ops.translate(bm,verts=raised,vec=delta)
                remaining = [f for f in selected if f.is_valid]
                if remaining:
                    bmesh.ops.delete(bm,geom=remaining,context="FACES_ONLY")
                selected = selected_new
            else:
                thickness = req.get("thickness")
                if isinstance(thickness,bool) or not isinstance(thickness,(int,float)) or not math.isfinite(thickness) or thickness <= 0:
                    raise ValueError("inset thickness must be finite and positive in metres")
                directions = {face: [(loop.link_loop_next.vert.co-loop.vert.co).copy()
                                     for loop in face.loops] for face in selected}
                bmesh.ops.inset_region(bm,faces=selected,thickness=thickness,depth=0,
                                      use_even_offset=True,use_boundary=True,use_relative_offset=False)
                if any((loop.link_loop_next.vert.co-loop.vert.co).dot(direction) <= 1e-12
                       for face in selected for loop,direction in zip(face.loops,directions[face])):
                    raise ValueError("inset overlaps or reverses the region; reduce thickness")
        bm.normal_update()
        if not selected or any(not math.isfinite(c) for v in bm.verts for c in v.co):
            raise ValueError("operation did not produce finite geometry")
        if any(face.calc_area() < 1e-12 for face in bm.faces):
            raise ValueError("operation produced degenerate faces; reduce the amount or change the region")
        if any(len(edge.link_faces) > 2 for edge in bm.edges):
            raise ValueError("operation produced nonmanifold edges")
        bm.faces.index_update()
        selected_ids = [f.index for f in selected if f.is_valid]
        bmesh.ops.transform(bm,matrix=obj.matrix_world.inverted(),verts=list(bm.verts))
        candidate = obj.data.copy()
        bm.to_mesh(candidate)
        if candidate.has_custom_normals:
            candidate.normals_split_custom_set([(0,0,0)]*len(candidate.loops))
        candidate.update()
        return candidate, selected_ids
    except Exception:
        if candidate is not None:
            bpy.data.meshes.remove(candidate)
        raise
    finally:
        bm.free()


def cmd_edit_undo(req: dict) -> dict:
    _scene_objects()[0].view_layers[0].update()
    previous = _state.get("edit_undo")
    if previous is None:
        raise ValueError("no local edit to undo")
    obj = previous["object"]
    if obj.data is not previous["after"] or _mesh_stamp(obj) != previous["stamp"]:
        raise ValueError("mesh was replaced outside the edit tool; undo is no longer applicable")
    after = obj.data
    obj.data = previous["before"]
    revision = _revision(obj, force=True)
    history = _state.get("edit_history", [])
    if history:
        history.pop()
    _state["edit_undo"] = history[-1] if history else None
    if after.users == 0:
        bpy.data.meshes.remove(after)
    return {"ok": True, "part": obj.name, "revision": revision, "changed": previous["changed"]}


def _part(spec: str, objs):
    """One part in world space as (vertices, faces): an object by name, or "line N" — what line N of the build code
    made (the pieces are merged into one mesh at the end; the line labels stay)."""
    spec = spec.strip()
    words = spec.split()
    line = int(words[-1]) if len(words) == 2 and words[0].lower() == "line" and words[1].isdigit() else None
    verts, faces = [], []
    for o in objs:
        if o.type != "MESH" or (line is None and o.name != spec):
            continue
        me, base = o.data, len(verts)
        keep = None
        if line is not None:
            src = me.attributes.get(modeling.SRC_ATTR)
            if src is None:
                continue
            keep = {k for k, d in enumerate(src.data) if d.value == line}
        verts += [tuple(o.matrix_world @ v.co) for v in me.vertices]
        faces += [tuple(base + k for k in p.vertices) for p in me.polygons
                  if keep is None or all(k in keep for k in p.vertices)]
    return verts, faces


def cmd_measure(req: dict) -> dict:
    from mathutils.bvhtree import BVHTree
    scene, objs = _scene_objects()
    a, b = str(req.get("a") or ""), str(req.get("b") or "")
    (va, fa), (vb, fb) = _part(a, objs), _part(b, objs)
    if not fa or not fb:
        names = sorted(o.name for o in objs if o.type == "MESH")
        return {"ok": False, "problems": [f"nothing found for '{a if not fa else b}' — give an object name "
                                          f"({', '.join(names)[:300]}) or \"line N\" of the build code"]}
    ta, tb = BVHTree.FromPolygons(va, fa), BVHTree.FromPolygons(vb, fb)
    overlap = bool(ta.overlap(tb))

    def nearest(vs, fs, other):   # closest a vertex of one part comes to the other's surface
        pts = sorted({k for f in fs for k in f})
        return min((other.find_nearest(mathutils.Vector(vs[k]))[3] or 0.0) for k in pts[::max(1, len(pts) // 3000)])
    gap = 0.0 if overlap else min(nearest(va, fa, tb), nearest(vb, fb, ta))
    return {"ok": True, "gap_m": round(gap, 5), "overlap": overlap, "touching": overlap or gap < 0.003}


def cmd_render(req: dict) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="meshgate-live-"))
    glb = tmp / "live.glb"
    scene, objs = _scene_objects()
    with _in_scene(scene):
        export._gltf(str(glb), selection=False, animations=False, draco=False)
    out = tmp / "views.png"
    script = HERE / "kitlib" / "render_views.py"
    if not script.exists():
        script = HERE.parents[1] / "generate" / "render_views.py"
    subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "-P", str(script), "--", str(glb), str(out),
                    str(int(req.get("px") or 1024)), str(int(req.get("samples") or 24)), json.dumps(req["reference"]) if isinstance(req.get("reference"), dict) else str(req.get("reference") or ""),
                    json.dumps(req.get("closeups") or [])], capture_output=True, timeout=900)
    return {"ok": out.exists(), "image": str(out) if out.exists() else None}


def cmd_reference(req: dict) -> dict:
    """Place a packed reference image in the live scene at a measured size."""
    scene = bpy.data.scenes.get(LIVE_SCENE)
    path = Path(str(req.get("path") or "")).expanduser().resolve()
    view = str(req.get("view") or "front")
    height = float(req.get("height") or 1)
    if not scene or not path.is_file() or view not in {"front", "side", "back"} or not math.isfinite(height) or height <= 0:
        return {"ok": False, "problems": ["live scene, image path, front/side/back and positive height required"]}
    image = bpy.data.images.load(str(path), check_existing=True)
    image.pack()
    obj = bpy.data.objects.new("Reference_" + view, None)
    scene.collection.objects.link(obj)
    obj.empty_display_type = "IMAGE"
    obj.data = image
    obj.empty_display_size = height * max(image.size) / image.size[1]
    obj.empty_image_depth = "BACK"
    obj.color[3] = .35
    obj.location = (0, .5, height/2) if view != "side" else (-.5,0,height/2)
    obj.rotation_euler = (math.pi/2,0,0) if view == "front" else (math.pi/2,0,math.pi) if view == "back" else (math.pi/2,0,math.pi/2)
    obj.hide_render = True
    obj["meshgate_reference"] = True
    return {"ok": True, "object": obj.name, "height_m": height, "view": view}


def cmd_save_base(req: dict) -> dict:
    """Freeze only the live scene into a new portable base; never overwrite an existing revision."""
    scene = bpy.data.scenes.get(LIVE_SCENE)
    path = Path(str(req.get("path") or "")).expanduser().resolve()
    if not scene or not any(o.type == "MESH" for o in scene.objects):
        return {"ok": False, "problems": ["build a live mesh scene before saving a base"]}
    if path.suffix.lower() != ".blend" or path.exists() or path.with_suffix(".json").exists():
        return {"ok": False, "problems": ["choose a new .blend path for this revision"]}
    images = {n.image for o in scene.objects if o.type == "MESH" for material in o.data.materials
              if material and material.use_nodes for n in material.node_tree.nodes
              if n.type == "TEX_IMAGE" and n.image}
    for image in images:
        if not image.packed_file:
            if image.source == "FILE" and not Path(bpy.path.abspath(image.filepath)).is_file():
                return {"ok": False, "problems": ["missing texture: " + image.filepath]}
            image.pack()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reserve exclusively: a repeated request cannot silently replace an artist's base.
    with path.open("xb"):
        pass
    try:
        bpy.data.libraries.write(str(path), {scene}, path_remap="RELATIVE", fake_user=True, compress=True)
        metadata = {"asset": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source": "MeshGate live", "objects": [o.name for o in scene.objects],
                    "textures": "packed", "note": str(req.get("note") or "")}
        path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"ok": True, "path": str(path), "metadata": metadata}


def cmd_export(req: dict) -> dict:
    path = str(req.get("path") or "")
    if not path.lower().endswith(".glb"):
        return {"ok": False, "problems": ["give a path ending in .glb"]}
    scene, objs = _scene_objects()
    with _in_scene(scene):
        res = export.export_asset(bpy.context, path, targets=["web", "unity", "godot", "unreal"], fbx=True, validate=True)
    return {"ok": res.ok, "files": res.files, "summary": export.summary_lines(res)}


COMMANDS = {"info": cmd_info, "run": cmd_run, "facts": cmd_facts, "measure": cmd_measure, "render": cmd_render,
            "reference": cmd_reference, "save_base": cmd_save_base, "export": cmd_export, "mesh": cmd_mesh, "edit": cmd_edit, "edit_undo": cmd_edit_undo}


def handle(req: dict) -> dict:
    if req.get("token") != _state["token"]:
        return {"ok": False, "problems": ["wrong token"]}
    fn = COMMANDS.get(str(req.get("cmd")))
    if fn is None:
        return {"ok": False, "problems": [f"unknown command — use {', '.join(COMMANDS)}"]}
    try:
        return fn(req)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "problems": [f"{type(exc).__name__}: {exc}"]}


# ---------------------------------------------------------------------------- the server

def _accept_loop(srv: socket.socket, q: "queue.Queue"):
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        threading.Thread(target=_client, args=(conn, q), daemon=True).start()


def _client(conn: socket.socket, q: "queue.Queue"):
    with conn:
        buf = b""
        while True:
            try:
                chunk = conn.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    req = json.loads(line)
                except ValueError:
                    conn.sendall(b'{"ok": false, "problems": ["send one JSON object per line"]}\n')
                    continue
                done = threading.Event()
                box: dict = {}
                q.put((req, box, done))   # Blender's data is only touched on its main thread
                done.wait()
                conn.sendall((json.dumps(box.get("reply", {}), default=str) + "\n").encode())


def _drain(q) -> None:
    while True:
        try:
            req, box, done = q.get_nowait()
        except queue.Empty:
            return
        box["reply"] = handle(req)
        done.set()


def start(port: int = 0) -> dict:
    """Start the live link (once); returns {port, token} and writes them to ~/.meshgate/blender_link.json."""
    if _state["server"]:
        return {"port": _state["port"], "token": _state["token"]}
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(4)
    q: queue.Queue = queue.Queue()
    _state.update(server=srv, queue=q, token=secrets.token_urlsafe(24), port=srv.getsockname()[1])
    _state["thread"] = threading.Thread(target=_accept_loop, args=(srv, q), daemon=True)
    _state["thread"].start()
    path = link_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"port": _state["port"], "token": _state["token"], "pid": os.getpid(),
                                "blender": bpy.app.version_string}), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    if not bpy.app.background:
        bpy.app.timers.register(_tick, persistent=True)
    return {"port": _state["port"], "token": _state["token"]}


def _tick():
    if not _state["server"]:
        return None
    _drain(_state["queue"])
    return 0.1


def serve_forever() -> None:
    """Background Blender: keep answering until stopped (Ctrl-C or the process ends)."""
    import time
    start()
    print(f"MeshGate live link on 127.0.0.1:{_state['port']} (token in {link_file()})", flush=True)
    while _state["server"]:
        _drain(_state["queue"])
        time.sleep(0.05)


def stop() -> None:
    srv = _state.get("server")
    if srv:
        try:
            srv.close()
        except OSError:
            pass
    _state.update(server=None, queue=None, token=None, port=None)
    try:
        if json.loads(link_file().read_text()).get("pid") == os.getpid():
            link_file().unlink()
    except (OSError, ValueError):
        pass


def running() -> bool:
    return bool(_state["server"])
