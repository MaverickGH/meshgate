"""Blender -b base.blend --python-exit-code 1 -P this.py -- base.glb"""
import sys
import math
import bpy
from mathutils import Vector
names=['head_width','head_depth','body_width','leg_length','paw_size','hand_size']
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.shape_keys]
assert meshes, 'No editor shapes in saved base'
for obj in meshes:
    keys=obj.data.shape_keys.key_blocks
    for name in names:
        assert name in keys and name+'_neg' in keys, name
    basis=keys[0]
    for key in keys[1:]:
        assert len(key.data)==len(basis.data)
        assert any((a.co-b.co).length>1e-5 for a,b in zip(key.data,basis.data)), key.name
        assert all(math.isfinite(c) for v in key.data for c in v.co)
    # Simultaneous positive and negative extremes: topology remains unchanged and finite.
    for sign in (1,-1):
        for name in names:
            keys[name].value=1 if sign>0 else 0
            keys[name+'_neg'].value=1 if sign<0 else 0
        bpy.context.view_layer.update()
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        assert len(mesh.vertices)==len(obj.data.vertices)
        assert all(math.isfinite(c) for v in mesh.vertices for c in v.co)
        evaluated.to_mesh_clear()
    for key in keys[1:]: key.value=0
    for a,b in zip(keys[0].data,obj.data.vertices): assert (a.co-b.co).length<1e-6
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=sys.argv[sys.argv.index('--')+1])
exported=set()
for obj in bpy.context.scene.objects:
    if obj.type=='MESH' and obj.data.shape_keys:
        exported.update(k.name for k in obj.data.shape_keys.key_blocks)
assert all(n in exported and n+'_neg' in exported for n in names), exported
print('Cat base verified: six two-sided exported morphs, nonzero deltas, finite combinations and neutral restoration.')
