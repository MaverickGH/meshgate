"""Direct state checks: Blender -b --factory-startup -P tests/blender/test_live_edit.py."""
import sys
from pathlib import Path
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sources'/'blender'))
from meshgate_blender import live

live._state['token']='test'
def call(cmd, **args):
    return live.handle({'token':'test','cmd':cmd,**args})

# No editing or metadata writes in the user's scene when no live scene exists.
cube=bpy.data.objects['Cube']
assert call('info')['objects']
assert 'meshgate_edit_stamp' not in cube
assert not call('edit',part='Cube',revision=0,operation='move',delta=[1,0,0])['ok']

live._live_scene(clear=True)
bpy.ops.mesh.primitive_cube_add(location=(.2,.1,.3))
head=bpy.context.object
head.name='Head'
source=head.data.attributes.new('mg_src','INT','POINT')
for item in source.data:
    item.value=9
uv=[tuple(item.uv) for item in head.data.uv_layers.active.data]
scene=bpy.data.scenes.new('Artist')
other=head.copy()
scene.collection.objects.link(other)
other.name='Artist_head'
other_points=[tuple(v.co) for v in other.data.vertices]
assert not call('mesh',part=other.name)['ok']

initial=call('mesh',part='Head')
assert initial['ok']
edit=call('edit',part='Head',revision=initial['revision'],operation='move',delta=[.03,0,0])
assert edit['ok'],edit
assert [tuple(item.uv) for item in head.data.uv_layers.active.data]==uv
assert [item.value for item in head.data.attributes['mg_src'].data]==[9]*8
assert [tuple(v.co) for v in other.data.vertices]==other_points

# A manual edit invalidates the revision and protects it from our older undo.
head.data.vertices[0].co.x+=.1
head.data.update()
manual=[tuple(v.co) for v in head.data.vertices]
rejected=call('edit',part='Head',revision=edit['revision'],operation='move',delta=[1,0,0])
assert not rejected['ok'] and 'stale' in rejected['problems'][0],rejected
assert [tuple(v.co) for v in head.data.vertices]==manual
assert not call('edit_undo')['ok']
assert [tuple(v.co) for v in head.data.vertices]==manual

fresh=call('mesh',part='Head')
assert fresh['revision']>edit['revision']
# World transforms also invalidate a selection inspected earlier.
head.location.y+=.02
rejected=call('edit',part='Head',revision=fresh['revision'],operation='move',delta=[1,0,0])
assert not rejected['ok']
new=call('mesh',part='Head')
edit=call('edit',part='Head',revision=new['revision'],operation='move',delta=[.01,0,0])
assert edit['ok'],edit
assert call('edit_undo')['ok']
assert [tuple(v.co) for v in head.data.vertices]==manual
assert [tuple(v.co) for v in other.data.vertices]==other_points
print('Live state checks passed: manual changes, foreign scene, shared data, attributes and undo.')
