"""Blender script: a stand-in for neural-generator output — one dense, vertex-coloured mesh in arbitrary units,
leaning 20° like a photo taken from above, with a few floating specks. refine.py must stand it up, scale it, clean it,
fit every tier and bake the colour.

    blender -b --factory-startup -P tests/generate/make_raw_mesh.py -- out.glb
"""
import math
import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import bpy

sys.path.insert(0, "sources/blender")
from meshgate_blender import compat  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
parts = []
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.8, depth=0.3, location=(0, 0, 0.15)); parts.append(bpy.context.active_object)
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.55, depth=3.0, location=(0, 0, 1.6)); parts.append(bpy.context.active_object)
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=0.55, location=(0, 0, 3.1)); parts.append(bpy.context.active_object)
for o in parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = parts[1]
bpy.ops.object.join()
o = bpy.context.active_object
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.subdivide(number_cuts=3)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.03, location=(1.6, 0.4, 2.0))   # a floating speck
speck = bpy.context.active_object
speck.select_set(True); o.select_set(True); bpy.context.view_layer.objects.active = o
bpy.ops.object.join()
o.rotation_euler = (math.radians(20), 0, 0)
o.scale = (23, 23, 23)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = o.data
attr = me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
for i, v in enumerate(me.vertices):
    attr.data[i].color = (0.8, 0.12, 0.1, 1.0) if v.co.z > 10 else (0.15, 0.2, 0.75, 1.0)
kw, _ = compat.operator_kwargs(bpy.ops.export_scene.gltf, filepath=sys.argv[-1], export_format="GLB", export_colors=True,
                               export_vertex_color="ACTIVE", export_materials="NONE")
bpy.ops.export_scene.gltf(**kw)
print("MESHGATE_RAW", len(me.polygons))
