"""Blender regression: collapsed faces disappear without changing valid details/attributes."""
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sources' / 'blender'))
from meshgate_blender.modeling import Kit, PRESERVE_ATTR
from meshgate_blender.live import _mesh_quality

mesh = bpy.data.meshes.new('collapsed_fixture')
mesh.from_pydata([(0,0,0),(1,0,0),(2,0,0),(0,1,0),
                  (0,0,1),(1e-7,0,1),(0,1e-7,1),(10,0,0),(11,0,0)],
                 [(7,8)], [(0,1,2),(0,1,3),(4,5,6)])
obj = bpy.data.objects.new('collapsed_fixture', mesh)
bpy.context.collection.objects.link(obj)
marker = mesh.attributes.new(PRESERVE_ATTR,'INT','FACE')
for item in marker.data: item.value = 1
colour = mesh.color_attributes.new('paint','FLOAT_COLOR','POINT')
for i,item in enumerate(colour.data): item.color = (i / 10, .2, .3, 1)
uv = mesh.uv_layers.new(name='UVMap')
for item in uv.data: item.uv = (.2,.4)
assert Kit._drop_zero_area(obj) == 1
assert len(mesh.polygons) == 2
assert all(item.value == 1 for item in mesh.attributes[PRESERVE_ATTR].data)
assert all(abs(item.uv.x-.2)<1e-6 and abs(item.uv.y-.4)<1e-6 for item in mesh.uv_layers['UVMap'].data)
assert sorted(round(item.color[0],4) for item in mesh.color_attributes['paint'].data) == [0,.1,.3,.4,.5,.6,.7,.8]
assert _mesh_quality(obj)['counts']['wire_edges'] == 1, 'Unrelated wire geometry must survive'
assert min(p.area for p in mesh.polygons) > 0, 'Tiny nonzero triangle must survive'
assert Kit._drop_zero_area(obj) == 0
obj.shape_key_add(name='Basis')
assert Kit._drop_zero_area(obj) == 0
print('Zero-area cleanup: exact collapsed face removed; protected skin, tiny triangle, UV/paint, unrelated wire and shape keys preserved.')
