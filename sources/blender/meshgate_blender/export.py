"""Export by the asset contract — shared by the add-on panel and the headless CLI (export_meshgate.py).

Always writes the canonical `<name>.glb`. Engine targets add variants only when they need something the
canonical file must not contain:
  web     `<name>.draco.glb`   when Draco is enabled (Godot/Unreal cannot decode Draco)
  unity   `<name>.fbx`         clean FBX for the Unity editor / Humanoid; `<name>.unity.fbx` with `_LOD0.._LODn`
                               meshes when LODs exist (Unity builds a LODGroup from that naming)
  unreal  `<name>.fbx`         clean FBX; `<name>.unreal.fbx` with `UCX_<mesh>_NN` collision when proxies exist
  godot   `<name>.godot.glb`   with `<mesh>-convcolonly` collision nodes when proxies exist (Godot import hints)
Every written file goes through the bundled validator; the report comes back as dicts.
"""

from __future__ import annotations

import importlib.util
import os
from contextlib import contextmanager
from dataclasses import dataclass, field

import bpy

from . import compat
from .checks import export_objects, meshes

TARGETS = ("web", "unity", "godot", "unreal")


@dataclass
class ExportResult:
    files: list[str] = field(default_factory=list)
    reports: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.get("ok", False) for r in self.reports)


# ----------------------------------------------------------------------------
# validator (bundled copy in the add-on zip, or the repository's core/ when run from a checkout)
# ----------------------------------------------------------------------------

def _load_module(name: str):
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, "validator", f"{name}.py"),
                      os.path.join(here, "..", "..", "..", "core", f"{name}.py")):
        if os.path.isfile(candidate):
            spec = importlib.util.spec_from_file_location(f"meshgate_{name}", candidate)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def load_profiles() -> dict:
    mod = _load_module("validate_glb")
    return mod.load_profiles() if mod else {"order": [], "profiles": {}}


def validate_file(path: str, strict: bool = True, max_mb: float = 25.0, profile: str | None = None, kind: str = "asset") -> dict:
    from pathlib import Path
    p = Path(path)
    try:
        if p.suffix.lower() == ".fbx":
            mod = _load_module("validate_fbx")
            report = mod.inspect(p) if mod else {"errors": ["validator not bundled"], "warnings": [], "notes": []}
        else:
            mod = _load_module("validate_glb")
            if not mod:
                return {"file": p.name, "errors": ["validator not bundled"], "warnings": [], "notes": [], "ok": False}
            gltf, bin_chunk = mod.parse_glb(p)
            report = mod.inspect(gltf, bin_chunk, p, max_mb)
    except Exception as exc:  # noqa: BLE001 — a broken file is a report, not a crash
        return {"file": p.name, "errors": [str(exc)], "warnings": [], "notes": [], "ok": False}
    if profile and p.suffix.lower() != ".fbx":
        bud = mod.check_budget(report, profile, kind)
        report["budget"] = bud
        report["warnings"] += [f"{bud['label']} budget: {x['name']} {x['value']:g} > {x['limit']:g}" for x in bud["items"] if not x["ok"]]
    report["ok"] = not report["errors"] and not (strict and report["warnings"])
    report.setdefault("file", p.name)
    return report


# ----------------------------------------------------------------------------
# exporters
# ----------------------------------------------------------------------------

def _gltf(path: str, *, selection: bool, animations: bool, draco: bool, draco_level: int = 6, image_format: str = "AUTO",
          influences: int = 4) -> list[str]:
    kwargs, dropped = compat.operator_kwargs(
        bpy.ops.export_scene.gltf,
        filepath=path, export_format="GLB", export_yup=True, export_apply=True,
        export_materials="EXPORT", export_image_format=image_format,
        export_cameras=False, export_lights=False,
        export_animations=animations, export_nla_strips=True, export_optimize_animation_size=True,
        export_merge_animation="NLA_TRACK",   # 4.x+/5.x: one clip per NLA track name across objects (older: implied)
        export_texcoords=True, export_normals=True, export_skins=True, export_morph=True, export_extras=True,
        # morphs (character-creator sliders) touch a region each: sparse, without normals, they cost kilobytes
        export_morph_normal=False, export_try_sparse_sk=True, export_try_omit_sparse_sk=True,
        use_selection=selection, use_renderable=True, use_visible=False,
        export_draco_mesh_compression_enable=draco, export_draco_mesh_compression_level=draco_level,
        export_influence_nb=influences,
    )
    bpy.ops.export_scene.gltf(**kwargs)
    return dropped


# FBX topology: True triangulates for engines (--topology tri), False keeps quads (--topology quad), None leaves the
# exporter's default (n-gons as they are). GLB is always triangles: glTF stores nothing else.
FBX_TRIANGLES: bool | None = None


def _fbx(path: str, *, objects: list[bpy.types.Object], animations: bool) -> list[str]:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objects:
        o.select_set(True)
    kwargs, dropped = compat.operator_kwargs(
        bpy.ops.export_scene.fbx,
        filepath=path, use_selection=True, object_types={"EMPTY", "ARMATURE", "MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y",
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_tspace=True, colors_type="NONE",
        add_leaf_bones=False, bake_anim=animations, bake_anim_use_nla_strips=True, bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, path_mode="COPY", embed_textures=True,
        **({} if FBX_TRIANGLES is None else {"use_triangles": FBX_TRIANGLES}),
    )
    bpy.ops.export_scene.fbx(**kwargs)
    return dropped


# ----------------------------------------------------------------------------
# target variants: temporary renames + unhiding of proxies, always restored
# ----------------------------------------------------------------------------

def collision_proxies(scene) -> list[bpy.types.Object]:
    return [o for o in scene.objects if o.type == "MESH" and o.get("meshgate_collision_for")]


def lod_meshes(scene) -> list[bpy.types.Object]:
    return [o for o in scene.objects if o.type == "MESH" and o.get("meshgate_lod_of")]


@contextmanager
def _variant(renames: dict, reveal: list):
    """Temporarily rename objects (two-phase to avoid name clashes) and enable proxies for render/export."""
    original = {o: o.name for o in renames}
    hidden = {o: (o.hide_render, o.hide_viewport, o.hide_get()) for o in reveal}
    try:
        for o in renames:
            o.name = f"__mg_tmp_{id(o)}"
        for o, new in renames.items():
            o.name = new
        for o in reveal:
            o.hide_render = False; o.hide_viewport = False; o.hide_set(False)
        yield
    finally:
        for o in renames:
            o.name = f"__mg_tmp_{id(o)}"
        for o, old in original.items():
            o.name = old
        for o, (hr, hv, h) in hidden.items():
            o.hide_render = hr; o.hide_viewport = hv; o.hide_set(h)


# ----------------------------------------------------------------------------
# quality tiers: temporary decimation + texture downscale, always restored
# ----------------------------------------------------------------------------

def evaluated_tris(context, objs) -> int:
    dg = context.evaluated_depsgraph_get()
    total = 0
    for o in meshes(objs):
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        total += len(me.loop_triangles)
        ev.to_mesh_clear()
    return total


def _has_alpha(objs) -> bool:
    return any(compat.uses_alpha(slot.material) for o in meshes(objs) for slot in o.material_slots)


@contextmanager
def _tier(context, objs, budget: dict, notes: list):
    """Bring the selection within a tier's asset budget for one export: DECIMATE modifiers first in the stack
    (so skinning still applies after), downscaled copies of oversized textures swapped into the materials."""
    added, swapped, copies = [], [], []
    # instances (objects sharing one mesh) get one decimated mesh they all share, so the file still stores it once;
    # a modifier on each would give every copy a mesh of its own
    shared: dict = {}
    for o in meshes(objs):
        if o.data.users > 1:
            shared.setdefault(o.data, []).append(o)
    ratios = {me: 1.0 for me in shared}
    made: dict = {}
    try:
        limit = budget["max_tris"]
        for _ in range(4):   # small meshes are left alone, so tighten the big ones until the budget holds
            tris = evaluated_tris(context, objs)
            if tris <= limit:
                break
            ratio = max(0.02, limit * 0.92 / tris)
            for me, users in shared.items():
                if me.shape_keys or len(me.polygons) < 48:
                    continue
                ratios[me] = max(0.01, ratios[me] * ratio)
                low = _decimated(context, me, ratios[me])
                for o in users:
                    o.data = low
                if me in made:
                    bpy.data.meshes.remove(made[me])
                made[me] = low
            for o in meshes(objs):
                if o.data.shape_keys or len(o.data.polygons) < 48 or any(o in u for u in shared.values()):
                    continue
                mod = o.modifiers.get("meshgate_tier")
                if mod is None:
                    mod = o.modifiers.new("meshgate_tier", "DECIMATE")
                    mod.decimate_type = "COLLAPSE"
                    mod.ratio = 1.0
                    added.append((o, mod.name))
                    with context.temp_override(object=o, active_object=o, selected_objects=[o]):
                        bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
                mod.ratio = max(0.01, mod.ratio * ratio)
        final = evaluated_tris(context, objs)
        if added:
            notes.append(f"decimated to {final:,} tris (budget {limit:,})")

        cap = budget["max_texture"]
        mats = {s.material for o in meshes(objs) for s in o.material_slots if s.material and s.material.use_nodes}
        remap = {}
        for m in mats:
            for n in m.node_tree.nodes:
                img = getattr(n, "image", None) if n.type == "TEX_IMAGE" else None
                if not img or not img.size[0] or max(img.size) <= cap:
                    continue
                if img not in remap:
                    k = cap / max(img.size)
                    cp = img.copy()
                    cp.name = f"{img.name}_{cap}"
                    cp.scale(max(1, int(img.size[0] * k)), max(1, int(img.size[1] * k)))
                    cp.pack()   # repack the new pixels, so the exporter does not reuse the original bytes
                    remap[img] = cp
                    copies.append(cp)
                swapped.append((n, img))
                n.image = remap[img]
        if remap:
            notes.append(f"{len(remap)} textures downscaled to ≤ {cap}px")
        yield
    finally:
        for n, img in swapped:
            n.image = img
        for cp in copies:
            bpy.data.images.remove(cp)
        for o, name in added:
            mod = o.modifiers.get(name)
            if mod:
                o.modifiers.remove(mod)
        for me, users in shared.items():
            for o in users:
                o.data = me
            if me in made:
                bpy.data.meshes.remove(made[me])


def _decimated(context, me, ratio: float):
    """A decimated copy of a mesh (collapse, as the tier modifier does), made once for all the objects sharing it."""
    tmp = bpy.data.objects.new("meshgate_tier_tmp", me)
    context.scene.collection.objects.link(tmp)
    mod = tmp.modifiers.new("meshgate_tier", "DECIMATE")
    mod.decimate_type, mod.ratio = "COLLAPSE", ratio
    try:
        dg = context.evaluated_depsgraph_get()
        low = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    finally:
        bpy.data.objects.remove(tmp)
    low.name = f"{me.name}_tier"
    low.validate(clean_customdata=False)   # the evaluated copy can keep stale loop data (glTF export in 3.5 fails on it)
    return low


def apply_mesh_scale(context, objs) -> int:
    """Contract: scale 1 on meshes. Applies to single-user meshes whose scale is not animated."""
    todo = [o for o in meshes(objs) if o.data.users == 1 and any(abs(s - 1) > 1e-6 for s in o.scale)
            and not compat.animates(o, "scale")]
    if not todo:
        return 0
    for o in context.view_layer.objects:
        o.select_set(False)
    for o in todo:
        o.select_set(True)
    context.view_layer.objects.active = todo[0]
    try:
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    except RuntimeError as exc:
        print(f"MeshGate: could not apply scale: {exc}")
        return 0
    return len(todo)


def export_tier(context, path: str, profile: str, *, objs=None, selection: bool = False, animations: bool = True,
                notes: list | None = None, image_format: str | None = None, max_tris: int | None = None) -> list[str]:
    """One GLB within a quality tier's asset budget: decimation and texture downscale as a safety net (reverted after),
    JPEG textures where the tier asks for them and nothing needs alpha, the tier's bone-influence limit."""
    budget = dict(load_profiles()["profiles"][profile]["asset"])
    if max_tris:   # your own limit, below the tier's
        budget["max_tris"] = min(budget["max_tris"], int(max_tris))
    objs = objs if objs is not None else export_objects(context, selection)
    fmt = image_format or budget.get("image_format", "AUTO")
    if fmt == "JPEG" and _has_alpha(objs):
        fmt = "AUTO"   # JPEG would drop the alpha channel
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with _tier(context, objs, budget, notes if notes is not None else []):
        return _gltf(path, selection=selection, animations=animations, draco=False, image_format=fmt,
                     influences=budget["max_influences"])


def export_asset(context, out_glb: str, *, targets=(), fbx: bool = False, draco: bool = False, web_draco: bool = False,
                 selection: bool = False, animations: bool = True, image_format: str = "AUTO",
                 apply_scale: bool = True, validate: bool = True, strict: bool = True, profiles=()) -> ExportResult:
    """Export `out_glb` (+ variants for `targets`). `draco` compresses the canonical file itself (CLI flag);
    `web_draco` writes an extra `<name>.draco.glb` for the web target."""
    result = ExportResult()
    targets = [t for t in targets if t in TARGETS]
    out_glb = os.path.abspath(bpy.path.abspath(out_glb))
    base, _ = os.path.splitext(out_glb)
    os.makedirs(os.path.dirname(out_glb), exist_ok=True)
    if context.object and context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    scene = context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    objs = export_objects(context, selection)
    if apply_scale:
        n = apply_mesh_scale(context, objs)
        if n:
            result.notes.append(f"applied scale on {n} objects")

    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    tier_of: dict = {}

    def add(path, dropped):
        result.files.append(path)
        if dropped:
            result.notes.append(f"{os.path.basename(path)}: exporter options not in Blender {bpy.app.version_string}: {', '.join(dropped)}")

    try:
        # canonical GLB (selection is restored between exports; glTF honours use_selection itself)
        add(out_glb, _gltf(out_glb, selection=selection, animations=animations, draco=draco, image_format=image_format))

        if web_draco and "web" in targets and not draco:
            p = base + ".draco.glb"
            add(p, _gltf(p, selection=selection, animations=animations, draco=True, image_format=image_format))

        if fbx or "unity" in targets or "unreal" in targets:
            p = base + ".fbx"
            add(p, _fbx(p, objects=objs, animations=animations))

        proxies = [o for o in collision_proxies(scene) if o.get("meshgate_collision_for") in {x.name for x in objs}]
        lods = [o for o in lod_meshes(scene) if o.get("meshgate_lod_of") in {x.name for x in objs}]

        if "unity" in targets and lods:
            renames = {}
            for o in lods:
                src = scene.objects.get(o["meshgate_lod_of"])
                renames[o] = f"{o['meshgate_lod_of']}_LOD{int(o.get('meshgate_lod_level', 1))}"
                if src is not None:
                    renames[src] = f"{src.name}_LOD0"
            p = base + ".unity.fbx"
            with _variant(renames, lods):
                add(p, _fbx(p, objects=objs + lods, animations=animations))

        if "unreal" in targets and proxies:
            counters: dict[str, int] = {}
            renames = {}
            for o in proxies:
                owner = o["meshgate_collision_for"]
                i = counters.get(owner, 0); counters[owner] = i + 1
                renames[o] = f"UCX_{owner}_{i:02d}"
            p = base + ".unreal.fbx"
            with _variant(renames, proxies):
                add(p, _fbx(p, objects=objs + proxies, animations=animations))

        # quality tiers: <name>.<tier>.glb within the tier's asset budget ("pc" is the canonical file itself)
        table = load_profiles()
        for prof in [p for p in profiles if p in table.get("profiles", {}) and p != "pc"]:
            path = f"{base}.{prof}.glb"
            tier_notes: list = []
            add(path, export_tier(context, path, prof, objs=objs, selection=selection, animations=animations, notes=tier_notes))
            result.notes += [f"{os.path.basename(path)}: {n}" for n in tier_notes]
            tier_of[path] = prof

        if "godot" in targets and proxies:
            renames = {o: f"{o['meshgate_collision_for']}_col{i}-convcolonly" for i, o in enumerate(proxies)}
            p = base + ".godot.glb"
            with _variant(renames, proxies):
                if selection:   # selection export: the proxies must be selected too (restored in finally)
                    for o in proxies:
                        o.select_set(True)
                add(p, _gltf(p, selection=selection, animations=animations, draco=False, image_format=image_format))
    finally:
        for o in context.view_layer.objects:
            o.select_set(o in selected)
        context.view_layer.objects.active = active

    if validate:
        for path in result.files:
            report = validate_file(path, strict=strict, profile=tier_of.get(path))
            # variants carry proxies/LOD meshes on purpose — their extra names are not contract issues
            result.reports.append(report)
    return result


def summary_lines(result: ExportResult, compact: bool = False) -> list[str]:
    """Human report. compact=True (panel): name on its own line, details below, exporter notes left out."""
    lines = []
    for r in result.reports:
        mark = "✓" if r.get("ok") else ("✗" if r.get("errors") else "⚠")
        size = f"{r['size_mb']:.2f} MB" if "size_mb" in r else ""
        extra = ""
        if "triangles" in r:
            extra = f"{r['triangles']:,} tris, {len(r.get('animations', []))} anims" + (f", {r['joints']} bones" if r.get("joints") else "")
            if r.get("budget"):
                extra += f" · {r['budget']['label']} budget {'ok' if r['budget']['ok'] else 'EXCEEDED'}"
        elif "polygons" in r:
            extra = f"{r['polygons']:,} polys, takes: {', '.join(r.get('animations', [])) or '—'}"
        if compact:
            lines.append(f"{mark} {r.get('file')}")
            lines.append(f"   {size} · {extra}".rstrip(" ·"))
        else:
            lines.append(f"{mark} {r.get('file')}  {size}  {extra}".rstrip())
        lines += [f"    ✗ {e}" for e in r.get("errors", [])]
        lines += [f"    ⚠ {w}" for w in r.get("warnings", [])]
    if not compact:
        lines += [f"· {n}" for n in result.notes]
    return lines
