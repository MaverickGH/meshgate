"""A loaded finalized base must not receive another coplanar-face displacement."""
import sys,tempfile
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sources/blender'))
from meshgate_blender.modeling import Kit
bpy.ops.wm.read_factory_settings(use_empty=True)
mg=Kit(name='saved_geometry');colour=mg.color('test','#aaaaaa')
a=mg.part('cube',colour,scale=(1,1,1),exact=True)
b=mg.part('cube',colour,loc=(0,0,.4),scale=(.2,.2,.2),exact=True)
obj=mg.join('coplanar_fixture',[a,b])
probe=mg.copy(obj)
assert mg._unfight(probe)>0,'fixture must exercise coplanar correction'
mg.discard(probe)
original=[tuple(v.co) for v in obj.data.vertices]
with tempfile.TemporaryDirectory() as tmp:
 path=str(Path(tmp)/'saved.blend')
 bpy.ops.wm.save_as_mainfile(filepath=path)
 bpy.ops.wm.read_factory_settings(use_empty=True)
 reused=Kit(name='reused').load_base(path)
 assert Kit._unfight(reused)==0
 assert original==[tuple(v.co) for v in reused.data.vertices]
print('PASS: existing coplanar surfaces remain exact when a saved base is loaded.')
