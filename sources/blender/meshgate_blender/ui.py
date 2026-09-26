"""MeshGate panel (3D View sidebar → MeshGate), operators, settings and the File → Export entry."""


import os

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup

from . import checks, export, tools

_ = bpy.app.translations.pgettext_iface


# ----------------------------------------------------------------------------
# settings stored on the scene
# ----------------------------------------------------------------------------

class MESHGATE_Issue(PropertyGroup):
    code: StringProperty()
    severity: StringProperty()
    text: StringProperty()
    fix: StringProperty()


class MESHGATE_ReportLine(PropertyGroup):
    text: StringProperty()


def _default_name(context) -> str:
    stem = bpy.path.display_name_from_filepath(bpy.data.filepath) if bpy.data.filepath else "asset"
    return checks.ascii_name(stem) or "asset"


class MESHGATE_Settings(PropertyGroup):
    target_web: BoolProperty(name="Web", default=True, description="Three.js / browser")
    target_unity: BoolProperty(name="Unity", default=False, description="Unity 6: GLB via glTFast, FBX for the editor and Humanoid")
    target_godot: BoolProperty(name="Godot", default=False, description="Godot 4: native glTF import")
    target_unreal: BoolProperty(name="Unreal", default=False, description="Unreal 5: Interchange (GLB) or FBX, UCX collision")
    out_dir: StringProperty(name="Folder", subtype="DIR_PATH", default="//export/", description="Where to write the files (// = next to the .blend)")
    asset_name: StringProperty(name="Name", default="", description="File name without extension; empty = .blend name")
    selection_only: BoolProperty(name="Selected only", default=False)
    animations: BoolProperty(name="Animations", default=True)
    fbx: BoolProperty(name="FBX too", default=False, description="Write <name>.fbx next to the GLB (always on for Unity/Unreal)")
    web_draco: BoolProperty(name="Draco for web", default=False, description="Extra <name>.draco.glb with compressed geometry (web only)")
    image_format: EnumProperty(name="Textures", items=[("AUTO", "As is", "Keep source format"), ("WEBP", "WebP", "Smaller, web + engines that read WebP"),
                                                      ("PNG", "PNG", "Lossless"), ("JPEG", "JPEG", "Small, lossy")], default="AUTO")
    tier_mobile_low: BoolProperty(name="Mobile low", default=False, description="<name>.mobile-low.glb: ≤ 8k tris, ≤ 512px textures, 2 influences, JPEG")
    tier_mobile_mid: BoolProperty(name="Mobile mid", default=False, description="<name>.mobile-mid.glb: ≤ 25k tris, ≤ 1024px textures, JPEG")
    tier_mobile_high: BoolProperty(name="Mobile high", default=False, description="<name>.mobile-high.glb: ≤ 60k tris, ≤ 2048px textures")
    collision_shape: EnumProperty(name="Collision", items=[("CONVEX", "Convex hull", ""), ("BOX", "Box", "")], default="CONVEX")
    issues: CollectionProperty(type=MESHGATE_Issue)
    issues_checked: BoolProperty(default=False)
    report: CollectionProperty(type=MESHGATE_ReportLine)
    last_glb: StringProperty(default="")
    show_report: BoolProperty(name="Report", default=True)

    def profiles(self) -> list[str]:
        return [p for p, on in (("mobile-low", self.tier_mobile_low), ("mobile-mid", self.tier_mobile_mid),
                                ("mobile-high", self.tier_mobile_high)) if on]

    def targets(self) -> list[str]:
        return [t for t in export.TARGETS if getattr(self, f"target_{t}")]

    def glb_path(self, context) -> str:
        name = checks.ascii_name(self.asset_name) if self.asset_name else _default_name(context)
        return os.path.join(bpy.path.abspath(self.out_dir or "//export/"), name + ".glb")


# ----------------------------------------------------------------------------
# operators
# ----------------------------------------------------------------------------

def _store_issues(context, issues):
    s = context.scene.meshgate
    s.issues.clear()
    for i in issues:
        item = s.issues.add()
        item.code, item.severity, item.text, item.fix = i.code, i.severity, i.label(), i.fix
    s.issues_checked = True


class MESHGATE_OT_check(Operator):
    bl_idname = "meshgate.check"
    bl_label = "Check"
    bl_description = "Check the scene against the MeshGate asset contract"
    bl_options = {"REGISTER"}

    def execute(self, context):
        s = context.scene.meshgate
        issues = checks.run_checks(context, s.selection_only, set(s.targets()))
        _store_issues(context, issues)
        errors = sum(i.severity == checks.ERROR for i in issues)
        warnings = sum(i.severity == checks.WARNING for i in issues)
        self.report({"ERROR" if errors else "WARNING" if warnings else "INFO"},
                    _("MeshGate: %d errors, %d warnings") % (errors, warnings) if issues else _("MeshGate: contract satisfied"))
        return {"FINISHED"}


class MESHGATE_OT_fix(Operator):
    bl_idname = "meshgate.fix"
    bl_label = "Fix"
    bl_description = "Apply the automatic fix for this issue"
    bl_options = {"REGISTER", "UNDO"}
    fix: StringProperty()

    def execute(self, context):
        s = context.scene.meshgate
        msg = checks.apply_fix(context, self.fix, s.selection_only)
        self.report({"INFO"}, f"MeshGate: {msg}")
        bpy.ops.meshgate.check()
        return {"FINISHED"}


class MESHGATE_OT_fix_all(Operator):
    bl_idname = "meshgate.fix_all"
    bl_label = "Fix all"
    bl_description = "Apply every automatic fix (undo with Ctrl+Z)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.meshgate
        done = checks.fix_all(context, s.selection_only)
        self.report({"INFO"}, "MeshGate: " + ("; ".join(done) if done else _("nothing to fix")))
        bpy.ops.meshgate.check()
        return {"FINISHED"}


class MESHGATE_OT_export(Operator):
    bl_idname = "meshgate.export"
    bl_label = "Export"
    bl_description = "Export the canonical GLB and the files the selected engines need, then validate them"
    bl_options = {"REGISTER"}

    def execute(self, context):
        s = context.scene.meshgate
        if not bpy.data.filepath and s.out_dir.startswith("//"):
            self.report({"ERROR"}, _("Save the .blend first, or choose an absolute export folder"))
            return {"CANCELLED"}
        path = s.glb_path(context)
        result = export.export_asset(context, path, targets=s.targets(), fbx=s.fbx, web_draco=s.web_draco,
                                     selection=s.selection_only, animations=s.animations, image_format=s.image_format,
                                     profiles=s.profiles())
        s.report.clear()
        for line in export.summary_lines(result, compact=True):
            s.report.add().text = line
        for note in result.notes:
            print(f"MeshGate: {note}")
        s.last_glb = path
        s.show_report = True
        level = {"INFO"} if result.ok else {"WARNING"}
        self.report(level, _("MeshGate: %d files written to %s") % (len(result.files), os.path.dirname(path)))
        return {"FINISHED"}


class MESHGATE_OT_preview(Operator):
    bl_idname = "meshgate.preview"
    bl_label = "Preview in browser"
    bl_description = "Open the last exported GLB in the MeshGate web viewer (served from Blender on localhost)"

    @classmethod
    def poll(cls, context):
        return bool(context.scene.meshgate.last_glb) and os.path.isfile(context.scene.meshgate.last_glb)

    def execute(self, context):
        try:
            url = tools.preview(context.scene.meshgate.last_glb)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"MeshGate: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, url)
        return {"FINISHED"}


class MESHGATE_OT_open_folder(Operator):
    bl_idname = "meshgate.open_folder"
    bl_label = "Open folder"
    bl_description = "Open the export folder"

    def execute(self, context):
        folder = bpy.path.abspath(context.scene.meshgate.out_dir or "//export/")
        os.makedirs(folder, exist_ok=True)
        bpy.ops.wm.path_open(filepath=folder)
        return {"FINISHED"}


class MESHGATE_OT_add_collision(Operator):
    bl_idname = "meshgate.add_collision"
    bl_label = "Add collision"
    bl_description = "Create a hidden collision proxy for each selected mesh (UCX_ for Unreal, -convcolonly for Godot)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(o.type == "MESH" for o in context.selected_objects)

    def execute(self, context):
        made = tools.add_collision(context, context.selected_objects, context.scene.meshgate.collision_shape)
        self.report({"INFO"}, _("MeshGate: %d collision proxies") % len(made))
        return {"FINISHED"}


class MESHGATE_OT_make_lods(Operator):
    bl_idname = "meshgate.make_lods"
    bl_label = "Make LODs"
    bl_description = "Create hidden decimated copies _LOD1 (50%) and _LOD2 (25%) for each selected mesh (Unity LODGroup)"
    bl_options = {"REGISTER", "UNDO"}
    ratio1: bpy.props.FloatProperty(name="LOD1", default=0.5, min=0.01, max=1.0)
    ratio2: bpy.props.FloatProperty(name="LOD2", default=0.25, min=0.01, max=1.0)

    @classmethod
    def poll(cls, context):
        return any(o.type == "MESH" for o in context.selected_objects)

    def execute(self, context):
        made = tools.make_lods(context, list(context.selected_objects), (self.ratio1, self.ratio2))
        self.report({"INFO"}, _("MeshGate: %d LOD meshes") % len(made))
        return {"FINISHED"}


# ----------------------------------------------------------------------------
# panel
# ----------------------------------------------------------------------------

_ICONS = {checks.ERROR: "ERROR", checks.WARNING: "ERROR", checks.INFO: "INFO"}


def _wrap(layout, text: str, width_px: int, icon: str = "NONE") -> None:
    """Labels do not wrap in Blender — split text to the panel width (about 7 px per character at 1× UI scale)."""
    import textwrap
    scale = bpy.context.preferences.system.ui_scale if bpy.context.preferences else 1.0
    chars = max(18, int((width_px - 50) / (7 * scale)))
    col = layout.column(align=True)
    for i, line in enumerate(textwrap.wrap(text, chars) or [""]):
        col.label(text=line, icon=icon if i == 0 else "BLANK1")


class MESHGATE_PT_main(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MeshGate"
    bl_label = "MeshGate"

    def draw(self, context):
        s = context.scene.meshgate
        layout = self.layout

        box = layout.box()
        box.label(text="Targets", icon="EXPORT")
        row = box.row(align=True)
        for t in ("web", "unity", "godot", "unreal"):
            row.prop(s, f"target_{t}", toggle=True)
        box.prop(s, "out_dir")
        box.prop(s, "asset_name", text="Name")
        if not s.asset_name:
            box.label(text=f"→ {_default_name(context)}.glb", icon="FILE_BLANK")
        col = box.column(align=True)
        col.prop(s, "selection_only")
        col.prop(s, "animations")
        col.prop(s, "fbx")
        sub = col.row()
        sub.enabled = s.target_web
        sub.prop(s, "web_draco")
        box.prop(s, "image_format")

        box = layout.box()
        box.label(text="Quality tiers", icon="PREFERENCES")
        row = box.row(align=True)
        row.prop(s, "tier_mobile_low", toggle=True, text="Low")
        row.prop(s, "tier_mobile_mid", toggle=True, text="Mid")
        row.prop(s, "tier_mobile_high", toggle=True, text="High")
        box.label(text="PC = the canonical GLB (full quality)", icon="DESKTOP")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator("meshgate.check", icon="CHECKMARK")
        row.operator("meshgate.fix_all", icon="MODIFIER")
        row = col.row(align=True)
        row.scale_y = 1.5
        row.operator("meshgate.export", icon="EXPORT")

        if s.issues_checked:
            box = layout.box()
            if not s.issues:
                box.label(text="Contract satisfied", icon="CHECKMARK")
            width = context.region.width if context.region else 300
            for item in s.issues:
                row = box.row(align=False)
                _wrap(row, item.text, width - (30 if item.fix else 0), _ICONS.get(item.severity, "DOT"))
                if item.fix:
                    op = row.operator("meshgate.fix", text="", icon="MODIFIER")
                    op.fix = item.fix

        if s.report:
            box = layout.box()
            row = box.row()
            row.prop(s, "show_report", icon="TRIA_DOWN" if s.show_report else "TRIA_RIGHT", emboss=False)
            if s.show_report:
                width = context.region.width if context.region else 300
                for line in s.report:
                    _wrap(box, line.text, width)
            row = box.row(align=True)
            row.operator("meshgate.preview", icon="WORLD")
            row.operator("meshgate.open_folder", icon="FILE_FOLDER")


class MESHGATE_PT_engine(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MeshGate"
    bl_label = "Engine extras"
    bl_parent_id = "MESHGATE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.meshgate
        layout = self.layout
        row = layout.row(align=True)
        row.prop(s, "collision_shape", text="")
        row.operator("meshgate.add_collision", icon="MESH_ICOSPHERE")
        layout.operator("meshgate.make_lods", icon="MOD_DECIM")
        n_col = len(export.collision_proxies(context.scene))
        n_lod = len(export.lod_meshes(context.scene))
        layout.label(text=_("%d collision proxies, %d LOD meshes in the scene") % (n_col, n_lod), icon="INFO")


def menu_export(self, context):
    self.layout.operator("meshgate.export", text="MeshGate (.glb for web/Unity/Godot/Unreal)")


CLASSES = (
    MESHGATE_Issue, MESHGATE_ReportLine, MESHGATE_Settings,
    MESHGATE_OT_check, MESHGATE_OT_fix, MESHGATE_OT_fix_all, MESHGATE_OT_export, MESHGATE_OT_preview,
    MESHGATE_OT_open_folder, MESHGATE_OT_add_collision, MESHGATE_OT_make_lods,
    MESHGATE_PT_main, MESHGATE_PT_engine,
)
