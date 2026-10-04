"""Blender --factory-startup -b -P this.py: selected fitted shell and safe replacement."""
import sys
from pathlib import Path
import bpy,bmesh
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sources/blender'))
from meshgate_blender.modeling import Kit,ModelError
bpy.ops.wm.read_factory_settings(use_empty=True)
mg=Kit(name='regions')
fur=mg.color('skin','#cccccc');cloth=mg.color('cloth','#778866')
body=mg.part('cube',fur,scale=(1,1,1),exact=True)
before=[tuple(v.co) for v in body.data.vertices]
shell=mg.garment(body,cloth,gap=.01,thickness=.004,regions=[((-.51,-.51,-.51),(.51,-.49,.51))])
assert all(x.value==1 for x in shell.data.attributes['mg_preserve_surface'].data), 'cloth wall protection missing'
assert len(shell.data.vertices)==8 and len(shell.data.polygons)==6
assert all(v.co.y<-.5 for v in shell.data.vertices)
bm=bmesh.new();bm.from_mesh(shell.data);assert all(e.is_manifold for e in bm.edges);bm.free()
assert before==[tuple(v.co) for v in body.data.vertices]
for regions in [[],[((1,0,0),(0,1,1))],[((0,0,0),(float('nan'),1,1))]]:
 try:mg.garment(body,cloth,regions=regions)
 except ModelError:pass
 else:raise AssertionError('bad regions accepted')
for refine in (-1, 3, 1.5):
 try:mg.garment(body,cloth,refine=refine)
 except ModelError:pass
 else:raise AssertionError('bad refinement accepted')
name=shell.name;data=shell.data.name;mg.discard(shell)
assert name not in bpy.data.objects and data not in bpy.data.meshes
print('PASS: selected thick hollow shell, closed rims, unchanged body, bad bounds rejected and replacement removed.')
