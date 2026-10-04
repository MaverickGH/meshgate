"""Blender -b --factory-startup -P tests/blender/test_live_quality.py."""
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sources' / 'blender'))
from meshgate_blender import live

live._state['token'] = 'test'
live._live_scene(clear=True)
bpy.ops.mesh.primitive_cube_add(location=(2, 3, 4))
cube = bpy.context.object
cube.name = 'Closed'
result = live.handle({'token': 'test', 'cmd': 'mesh', 'part': 'Closed', 'limit': 1})
assert result['ok'], result
quality = result['quality']
assert quality['scope'] == 'whole_object'
assert quality['component_count'] == 1
assert quality['component_vertex_counts'] == [8]
assert all(count == 0 for count in quality['counts'].values()), quality
assert quality['bounds'] == {'min': [1, 2, 3], 'max': [3, 4, 5]}

# An open triangle, a zero-area triangle, a wire, and an isolated vertex.
mesh = bpy.data.meshes.new('Broken')
mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0),
                 (3,0,0),(4,0,0),(5,0,0),
                 (7,0,0),(8,0,0),(10,0,0)], [(6,7)], [(0,1,2),(3,4,5)])
obj = bpy.data.objects.new('Broken', mesh)
bpy.context.scene.collection.objects.link(obj)
result = live.handle({'token': 'test', 'cmd': 'mesh', 'part': 'Broken', 'vertices': [0]})
assert result['ok'], result
quality = result['quality']
assert quality['component_count'] == 4, quality
assert quality['component_vertex_counts'] == [3, 3, 2, 1]
assert quality['counts'] == {'boundary_edges': 6, 'nonmanifold_edges': 7,
                            'wire_edges': 1, 'loose_vertices': 1, 'degenerate_faces': 1}, quality
assert quality['samples']['loose_vertices'] == [8]
assert quality['samples']['degenerate_faces'] == [1]
print('Live quality passed: closed mesh, disconnected pieces, open edges, wire, loose vertex and degenerate face.')
