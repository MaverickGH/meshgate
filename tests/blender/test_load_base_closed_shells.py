"""Closed clothing survives collapse, native validation and GLB/FBX export."""
import sys,tempfile,hashlib,math
from pathlib import Path
from collections import Counter
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sources/blender'))
from meshgate_blender.modeling import Kit
from meshgate_blender import export
root=Path(__file__).resolve().parents[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
mg=Kit(name='closed_collapse')
scope={};exec((root/'sources/generate/examples/cat_character_base_v14.py').read_text(),scope);scope['build'](mg)
obj=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
def check():
 roles=[x.value for x in obj.data.attributes['cat_cloth_role'].data]
 for role in (1,2,3,4):
  edges=Counter()
  for p in obj.data.polygons:
   if all(roles[i]==role for i in p.vertices):
    ids=list(p.vertices)
    for a,b in zip(ids,ids[1:]+ids[:1]):edges[tuple(sorted((a,b)))]+=1
  assert edges and all(count==2 for count in edges.values()),(role,'open or nonmanifold shell')
 assert obj.data.uv_layers and all(math.isfinite(c) for loop in obj.data.uv_layers.active.data for c in loop.uv)
def images():
 used={n.image for m in obj.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}
 assert len(used)==15 and all(i.packed_file for i in used)
 return sorted(hashlib.sha256(i.packed_file.data).hexdigest() for i in used)
check();hashes=images();mg._finalize();check()
shapes=[(k.name,[tuple(v.co) for v in k.data]) for k in obj.data.shape_keys.key_blocks]
assert len(shapes)==13
with tempfile.TemporaryDirectory() as tmp:
 export.FBX_TRIANGLES=True
 result=export.export_asset(bpy.context,str(Path(tmp)/'closed.glb'),fbx=True,validate=True,strict=True)
 assert result.ok,result.reports
 check()
 assert images()==hashes
 assert shapes==[(k.name,[tuple(v.co) for v in k.data]) for k in obj.data.shape_keys.key_blocks]
print('PASS: all four clothing shells closed after collapse, native validation and GLB/FBX export; UV, 15 packed textures and 12 morph targets preserved.')
