"""Real Blender: edited live scene survives portable snapshot/reload, artist scene excluded."""
import sys,tempfile
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sources/blender'))
from meshgate_blender import live
from meshgate_blender.modeling import Kit
bpy.ops.wm.read_factory_settings(use_empty=True)
live._live_scene(clear=True)
bpy.ops.mesh.primitive_cube_add()
o=bpy.context.object;o.name='Edited';o.data.vertices[0].co.x-=.3
expected=[tuple(v.co) for v in o.data.vertices]
artist=bpy.data.scenes.new('Artist');unrelated=bpy.data.objects.new('Private object',bpy.data.meshes.new('Other'));artist.collection.objects.link(unrelated)
with tempfile.TemporaryDirectory() as tmp:
 image=bpy.data.images.new('reference',width=8,height=16)
 image.filepath_raw=str(Path(tmp)/'reference.png');image.file_format='PNG';image.save()
 ref=live.cmd_reference({'path':image.filepath_raw,'height':2,'view':'front'});assert ref['ok'],ref
 reference=bpy.data.objects[ref['object']];assert reference.hide_render and reference.data.packed_file
 assert abs(reference.empty_display_size-2)<1e-6
 p=Path(tmp)/'revision.blend'
 r=live.cmd_save_base({'path':str(p),'note':'manual edit'});assert r['ok'],r
 assert p.with_suffix('.json').exists()
 assert not live.cmd_save_base({'path':str(p)})['ok']
 with bpy.data.libraries.load(str(p)) as (source,target): assert 'Private object' not in source.objects
 bpy.ops.wm.read_factory_settings(use_empty=True)
 k=Kit(name='reload');obj=k.load_base(str(p))
 assert [tuple(v.co) for v in obj.data.vertices]==expected
 assert not live.cmd_save_base({'path':str(Path(tmp)/'empty.blend')})['ok']
print('PASS: edited mesh reloads unchanged, unrelated scene excluded, revisions cannot overwrite.')
live._live_scene(clear=True)
bpy.ops.mesh.primitive_cube_add();obj=bpy.context.object;obj.name='History'
origin=[tuple(v.co) for v in obj.data.vertices]
for _ in range(3):
 revision=live.cmd_mesh({'part':obj.name})['revision']
 assert live.cmd_edit({'part':obj.name,'revision':revision,'operation':'move','delta':[.1,0,0]})['ok']
for _ in range(3): assert live.cmd_edit_undo({})['ok']
assert all(abs(v.co.x-p[0])<1e-6 for v,p in zip(obj.data.vertices,origin))
print('PASS: three successive edits undo back to original geometry.')
