"""Exercise local topology operations inside real Blender."""
import sys
from pathlib import Path
import bpy, bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sources'/'blender'))
from meshgate_blender import live
live._state['token']='test'
def call(cmd,**args):
    return live.handle({'token':'test','cmd':cmd,**args})
def edit(obj,operation,**args):
    result=call('edit',part=obj.name,revision=call('mesh',part=obj.name)['revision'],operation=operation,**args)
    assert result['ok'],result
    return result
def closed(obj):
    bm=bmesh.new(); bm.from_mesh(obj.data)
    assert all(len(e.link_faces)==2 for e in bm.edges)
    assert bm.calc_volume()>0
    bm.free()
live._live_scene(clear=True)
bpy.ops.mesh.primitive_cube_add()
obj=bpy.context.object; obj.name='Head'; obj.scale=(1,.5,1.5)
source=obj.data.attributes.new('mg_src','INT','POINT')
for item in source.data: item.value=9
original=obj.data
other=obj.copy(); bpy.context.collection.objects.link(other)
other.name='Shared'
face=max(obj.data.polygons,key=lambda p:p.normal.z).index
result=edit(obj,'inset',faces=[face],thickness=.2)
closed(obj)
assert len(obj.data.polygons)==10
assert other.data==original
assert set(i.value for i in obj.data.attributes['mg_src'].data)=={9}
assert obj.data.uv_layers.active
inset=obj.data
result=edit(obj,'extrude',faces=result['faces'],delta=[0,0,.3])
closed(obj)
assert len(obj.data.polygons)==14
assert len(result['faces'])==1
assert set(i.value for i in obj.data.attributes['mg_src'].data)=={9}
assert call('edit_undo')['ok']
assert obj.data==inset
before=obj.data
bad=call('edit',part=obj.name,revision=call('mesh',part=obj.name)['revision'],operation='extrude',faces=[0],delta=[0,0,0])
assert not bad['ok'] and obj.data==before
bad=call('edit',part=obj.name,revision=call('mesh',part=obj.name)['revision'],operation='inset',faces=[face],thickness=100)
assert not bad['ok'] and obj.data==before
# Two disjoint caps have boundary rings; bridging forms a closed prism.
mesh=bpy.data.meshes.new('Caps')
mesh.from_pydata([(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)],[],[(3,2,1,0),(4,5,6,7)])
bridge=bpy.data.objects.new('Bridge',mesh); bpy.context.collection.objects.link(bridge)
result=edit(bridge,'bridge',loops=[[0,1,2,3],[4,5,6,7]])
closed(bridge)
assert len(bridge.data.polygons)==6 and len(result['faces'])==4
assert call('edit_undo')['ok'] and bridge.data==mesh
bad=call('edit',part=obj.name,revision=call('mesh',part=obj.name)['revision'],operation='bridge',loops=[[0,1,2,3],[4,5,6,7]])
assert not bad['ok']
print('Topology checks passed: inset, extrude, bridge, manifold volume, labels, UV, instances and undo.')

# Local subdivision adds control points without rounding the silhouette.
before=obj.data
result=edit(obj,'subdivide',faces=[0],cuts=1)
closed(obj)
assert len(obj.data.vertices)>len(before.vertices)
assert call('edit_undo')['ok'] and obj.data==before
# World-space symmetry on a translated and nonuniformly scaled object.
obj.location.x=.4
obj.data.vertices[0].co.x-=.15
bpy.context.view_layer.update()
positive=[tuple(obj.matrix_world @ v.co) for v in obj.data.vertices if (obj.matrix_world @ v.co).x>.4]
result=edit(obj,'symmetrize',keep='+x',plane=.4)
closed(obj)
points=[obj.matrix_world @ v.co for v in obj.data.vertices]
assert all(any((q-Vector(p)).length<1e-5 for q in points) for p in positive)
for p in points:
    assert any(abs(q.x-(.8-p.x))<1e-5 and abs(q.y-p.y)<1e-5 and abs(q.z-p.z)<1e-5 for q in points)
assert call('edit_undo')['ok']
bad=call('edit',part=obj.name,revision=call('mesh',part=obj.name)['revision'],operation='symmetrize',vertices=[0],keep='+x')
assert not bad['ok']
print('Subdivision and world-plane symmetry checks passed.')
