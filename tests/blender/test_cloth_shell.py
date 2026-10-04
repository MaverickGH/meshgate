"""Real Blender check: curved concave clothing surface → closed thick shell."""
import sys
from pathlib import Path
import bmesh
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sources' / 'blender'))
from meshgate_blender.modeling import Kit
mg = Kit(colors='vertex')
color = mg.color('cloth', (.45, .52, .32))
# Curved three-column torso surface, with the centre of its lower hem missing.
vertices = [(x, .15*x*x + .02*z*z, z) for z in (0., .5, 1.) for x in (-.5, 0., .5)]
faces = [(0,1,4,3), (1,2,5,4), (3,4,7,6), (4,5,8,7)]
# Concave ragged hem: move its centre inwards rather than capping a planar polygon.
vertices[1] = (0, .02*.18*.18, .18)
for offset in (0, 1):
    obj = mg.mesh(vertices, faces, color, name='curved_cloth')
    original = [v.co.copy() for v in obj.data.vertices]
    mg.modify(obj, 'solidify', thickness=.02, offset=offset)
    bm = bmesh.new(); bm.from_mesh(obj.data)
    assert all(e.is_manifold for e in bm.edges), 'Hem/opening rims must close'
    assert bm.calc_volume(signed=True) > 0, 'Shell normals must face outward'
    assert obj.data.color_attributes.get('Col') is not None
    assert obj.data.uv_layers.active is not None
    assert len(obj.data.vertices) == 2*len(vertices)
    assert len(obj.data.polygons) == 16, 'Two skins plus eight boundary rims'
    if offset == 1:
        assert all(min((p-v.co).length for v in obj.data.vertices) < 1e-6 for p in original), 'Outward offset keeps authored inner surface'
    assert all(abs(d.color[3]-1) < 1e-6 for d in obj.data.color_attributes['Col'].data)
    bm.free()
print('cloth shell verified: concave curved hem, closed manifold, positive volume, vertex colors, UVs, outward offset.')
