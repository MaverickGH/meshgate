"""MeshGate Kit inside Blender: build `build(mg)` code into a scene, and bring free library models in.

Sidebar (N) → MeshGate → Kit. The same kit, guard rails and library as `meshgate.py gen`, so what an artist or an AI
builds here matches what the pipeline builds. For scripting in Blender's Python console or Text Editor:

    from meshgate_blender import kit_ui          # (the add-on's package name may be "meshgate" when installed)
    mg = kit_ui.live_kit("pc")                   # the kit on the current scene, nothing is cleared
    body = mg.blob([{"ball": (0, 0, 0.3), "r": 0.2}], mg.color("fur", "#7b8a6c", material="fur"))
    kit_ui.live_palette(mg)                      # write the palette textures so the colours show
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import bpy
import mathutils
from bpy.props import CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList

from . import export, finish, modeling

HERE = Path(__file__).resolve().parent
TIERS = [(t, t, "") for t in reversed(modeling.TIERS)]
FINISHES = [("none", "Palette", "Flat palette colours (stylized)"), ("faceted", "Low-poly", "Flat shading, fewer segments"),
            ("weathered", "Realistic", "Baked PBR with wear and material looks"), ("clean", "Clean PBR", "Exact colours, baked PBR")]
LICENSES = [("cc0,by", "CC0 + CC-BY", "Commercial use and changes allowed (credit CC-BY authors)"),
            ("cc0", "CC0 only", "No credit needed"),
            ("cc0,by,by-sa", "+ CC-BY-SA", "Your changed model must be CC-BY-SA too")]


def kitlib() -> Path:
    """The library, keys and guard-rail modules: bundled in the add-on zip, or the repository's sources/generate."""
    bundled = HERE / "kitlib"
    return bundled if bundled.exists() else HERE.parents[1] / "generate"


def _safety():
    spec = importlib.util.spec_from_file_location("meshgate_kit_safety", kitlib() / "safety.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _library(*args: str, timeout: int = 900) -> dict | list:
    """Run the library CLI in Blender's own Python, isolated from other add-ons; returns its JSON."""
    r = subprocess.run([sys.executable, str(kitlib() / "library.py"), *args, "--json"], capture_output=True, text=True,
                       timeout=timeout)
    out = r.stdout.strip()
    if r.returncode or not out.startswith(("{", "[")):
        raise RuntimeError((out or r.stderr).strip().splitlines()[-1] if (out or r.stderr).strip() else "library failed")
    return json.loads(out)


def live_kit(tier: str = "pc", finish_: str = "none", name: str = "asset") -> modeling.Kit:
    """The kit on the current scene (nothing is cleared) — for the Python console, scripts and AI tools in Blender."""
    return modeling.Kit(tier, name=name, finish=finish_)


def live_palette(mg: modeling.Kit) -> None:
    """Write the palette textures of a live kit so its colours show in the viewport."""
    mg._make_palette()


# ---------------------------------------------------------------------------- settings

class MESHGATE_KitResult(PropertyGroup):
    uid: StringProperty()
    title: StringProperty()
    author: StringProperty()
    license_name: StringProperty()
    faces: IntProperty()
    mirror: bpy.props.BoolProperty()


class MESHGATE_KitSettings(PropertyGroup):
    code: StringProperty(name="Code", subtype="FILE_PATH", description="A .py file that defines build(mg)")
    name: StringProperty(name="Name", default="asset")
    tier: EnumProperty(name="Tier", items=TIERS, default="pc")
    finish: EnumProperty(name="Look", items=FINISHES, default="none")
    query: StringProperty(name="Search", description="What to look for (a plain noun works best: cat, stump, skull)")
    category: bpy.props.BoolProperty(name="Objaverse category", description="Hand-labelled categories; every hit is free",
                                      default=False)
    licenses: EnumProperty(name="Licences", items=LICENSES, default="cc0,by")
    size: FloatProperty(name="Size", default=1.0, min=0.01, soft_max=20.0, unit="LENGTH",
                        description="Largest dimension of the imported model")
    results: CollectionProperty(type=MESHGATE_KitResult)
    index: IntProperty()
    status: StringProperty()


# ---------------------------------------------------------------------------- operators

class MESHGATE_OT_kit_build(Operator):
    bl_idname = "meshgate.kit_build"
    bl_label = "Build"
    bl_description = "Run the build(mg) code into a new scene at the chosen tier and look (same guard rails as the pipeline)"

    def execute(self, context):
        s = context.scene.meshgate_kit
        path = bpy.path.abspath(s.code)
        if not os.path.isfile(path):
            self.report({"ERROR"}, "Choose a .py file that defines build(mg)")
            return {"CANCELLED"}
        code = open(path, encoding="utf-8").read()
        safety = _safety()
        problems = safety.check(code)
        if problems:
            self.report({"ERROR"}, "Build code refused: " + "; ".join(problems[:3]))
            return {"CANCELLED"}
        name = modeling.Kit._ascii(s.name or Path(path).stem).lower()
        tier, look = s.tier, s.finish
        if context.window:   # the artist keeps their scene: each build gets its own
            scene = bpy.data.scenes.new(f"MeshGate {name} {tier}")
            context.window.scene = scene
            scene.meshgate_kit.code, scene.meshgate_kit.name = s.code, s.name
            scene.meshgate_kit.tier, scene.meshgate_kit.finish = tier, look
        else:                # no window (background Blender, scripts, tests): build into the current scene
            scene = context.scene
        try:
            budget = export.load_profiles()["profiles"][tier]["asset"]
            kit = modeling.Kit(tier, name=name, max_materials=budget["max_materials"], finish=look,
                               max_texture=budget.get("max_texture"), max_texture_mb=budget.get("max_texture_mb"))
            g = safety.restricted_globals({"math": math, "random": random, "mathutils": mathutils})
            exec(compile(code, path, "exec"), g)  # noqa: S102 — passed safety.check above
            g["build"](kit)
            notes = kit._finalize()
            if look in ("weathered", "clean"):
                notes += finish.weathered(bpy.context, budget, tier, bpy.app.tempdir, name, clean=look == "clean")
        except Exception as exc:  # noqa: BLE001 — show the build error to the artist
            self.report({"ERROR"}, f"build(mg) failed: {exc}")
            return {"CANCELLED"}
        tris = sum(len(p.vertices) - 2 for o in scene.objects if o.type == "MESH" for p in o.data.polygons)
        scene.meshgate_kit.status = f"{name}: {tris:,} triangles at {tier}" + (f" — {notes[-1]}" if notes else "")
        self.report({"INFO"}, scene.meshgate_kit.status)
        return {"FINISHED"}


class MESHGATE_OT_kit_search(Operator):
    bl_idname = "meshgate.kit_search"
    bl_label = "Search"
    bl_description = "Find free models you may change and use commercially (CC0 / CC-BY) on Sketchfab and Objaverse"

    def execute(self, context):
        s = context.scene.meshgate_kit
        if not s.query.strip():
            self.report({"ERROR"}, "Type what to look for")
            return {"CANCELLED"}
        args = ["search", s.query, "--license", s.licenses, "--count", "20"] + (["--category"] if s.category else [])
        try:
            found = _library(*args, timeout=300)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        s.results.clear()
        for r in found if isinstance(found, list) else []:
            item = s.results.add()
            item.uid, item.title, item.author = r["uid"], r["name"][:60], r.get("author") or ""
            item.license_name, item.faces, item.mirror = r.get("license_name", ""), r.get("faces") or 0, bool(r.get("mirror"))
        s.status = f"{len(s.results)} models"
        return {"FINISHED"}


class MESHGATE_OT_kit_import(Operator):
    bl_idname = "meshgate.kit_import"
    bl_label = "Download and import"
    bl_description = "Download the chosen model with its credit and bring it in at the 3D cursor, in its rest pose and at the chosen size"

    def execute(self, context):
        s = context.scene.meshgate_kit
        if not (0 <= s.index < len(s.results)):
            self.report({"ERROR"}, "Pick a model in the list")
            return {"CANCELLED"}
        uid = s.results[s.index].uid
        try:
            got = _library("get", uid, "--license", s.licenses)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        objs = import_model(context, got["file"], s.size, context.scene.cursor.location)
        for o in objs:
            o["meshgate_credit"] = got["line"]
        s.status = got["line"]
        self.report({"INFO"}, f"Imported — credit: {got['line']}")
        return {"FINISHED"}


def import_model(context, path: str, size: float, at) -> list:
    """Import a model file into the scene: rest pose, scaled so its largest side is `size`, standing on `at`."""
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise RuntimeError(f"{ext} files are not supported")
    new = [o for o in bpy.data.objects if o not in before]
    for arm in [o for o in new if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    context.view_layer.update()
    tops = [o for o in new if o.parent not in new]
    pts = [o.matrix_world @ mathutils.Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    if pts:
        lo = mathutils.Vector([min(p[i] for p in pts) for i in range(3)])
        hi = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
        k = size / max(max(hi - lo), 1e-6)
        base = mathutils.Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        m = mathutils.Matrix.Translation(mathutils.Vector(at)) @ mathutils.Matrix.Scale(k, 4) @ mathutils.Matrix.Translation(-base)
        for o in tops:
            o.matrix_world = m @ o.matrix_world
    return new


# ---------------------------------------------------------------------------- UI

class MESHGATE_OT_live_link(Operator):
    bl_idname = "meshgate.live_link"
    bl_label = "Connect AI"
    bl_description = ("Let an AI tool (Claude Code, Codex, Cursor… through `meshgate.py mcp`) build kit code in this "
                      "Blender and see the result. Builds go to a scene of their own; only kit code runs")

    def execute(self, context):
        from . import live
        s = context.scene.meshgate_kit
        if live.running():
            live.stop()
            s.status = "AI link off."
        else:
            info = live.start()
            s.status = (f"AI link on (port {info['port']}). In a terminal: claude mcp add meshgate -- python3 "
                        "meshgate.py mcp — builds show in the “MeshGate live” scene.")
        return {"FINISHED"}


class MESHGATE_UL_kit_results(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.title, icon="MESH_MONKEY")
        row.label(text=f"{item.license_name} · {item.faces:,}" + (" · free" if item.mirror else ""))


class MESHGATE_PT_kit(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MeshGate"
    bl_label = "Kit"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.meshgate_kit
        col = self.layout.column()
        box = col.box()
        box.label(text="Build from code", icon="SCRIPT")
        box.prop(s, "code", text="")
        row = box.row(align=True)
        row.prop(s, "name", text="")
        row.prop(s, "tier", text="")
        box.prop(s, "finish", expand=True)
        box.operator("meshgate.kit_build", icon="PLAY")
        box = col.box()
        box.label(text="Free models (CC0 / CC-BY)", icon="WORLD")
        row = box.row(align=True)
        row.prop(s, "query", text="")
        row.operator("meshgate.kit_search", text="", icon="VIEWZOOM")
        row = box.row(align=True)
        row.prop(s, "category", toggle=True)
        row.prop(s, "licenses", text="")
        box.template_list("MESHGATE_UL_kit_results", "", s, "results", s, "index", rows=4)
        row = box.row(align=True)
        row.prop(s, "size")
        row.operator("meshgate.kit_import", icon="IMPORT")
        box = col.box()
        box.label(text="AI link", icon="LINKED")
        from . import live
        on = live.running()
        box.operator("meshgate.live_link", text="Disconnect AI" if on else "Connect AI", icon="CANCEL" if on else "PLUGIN",
                     depress=on)
        if s.status:
            for line in _wrap(s.status, 44)[:5]:
                col.label(text=line)


def _wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return out + ([line] if line else [])


CLASSES = (MESHGATE_KitResult, MESHGATE_KitSettings, MESHGATE_OT_kit_build, MESHGATE_OT_kit_search, MESHGATE_OT_kit_import,
           MESHGATE_OT_live_link, MESHGATE_UL_kit_results, MESHGATE_PT_kit)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.meshgate_kit = bpy.props.PointerProperty(type=MESHGATE_KitSettings)


def unregister():
    from . import live
    live.stop()
    del bpy.types.Scene.meshgate_kit
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
