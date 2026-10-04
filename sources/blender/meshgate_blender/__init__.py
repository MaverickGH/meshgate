"""MeshGate for Blender — check, fix and export assets for the web, Unity, Godot and Unreal.

Legacy add-on (Blender 3.5–4.1: Edit → Preferences → Add-ons → Install…) and extension
(Blender 4.2+: drag the zip into Blender or Get Extensions → Install from Disk) from the same code.
"""

bl_info = {
    "name": "MeshGate",
    "author": "MeshGate contributors",
    "version": (0, 5, 0),
    "blender": (3, 5, 0),
    "location": "3D View → Sidebar (N) → MeshGate; File → Export → MeshGate",
    "description": "Check a scene against the MeshGate asset contract, fix it, export a validated GLB (+FBX) for web, Unity, Godot and Unreal",
    "doc_url": "https://github.com/MaverickGH/meshgate",
    "tracker_url": "https://github.com/MaverickGH/meshgate/issues",
    "category": "Import-Export",
}

import bpy

from . import kit_ui, translations, ui


def register():
    for cls in ui.CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.meshgate = bpy.props.PointerProperty(type=ui.MESHGATE_Settings)
    kit_ui.register()
    bpy.types.TOPBAR_MT_file_export.append(ui.menu_export)
    bpy.app.translations.register(__name__, translations.DICT)


def unregister():
    from . import tools
    tools.stop_preview()
    bpy.app.translations.unregister(__name__)
    bpy.types.TOPBAR_MT_file_export.remove(ui.menu_export)
    kit_ui.unregister()
    del bpy.types.Scene.meshgate
    for cls in reversed(ui.CLASSES):
        bpy.utils.unregister_class(cls)
