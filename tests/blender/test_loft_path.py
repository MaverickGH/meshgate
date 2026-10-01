"""Run with Blender -b --factory-startup -P tests/blender/test_loft_path.py."""
import math
import sys
from pathlib import Path
import bmesh
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sources' / 'blender'))
from meshgate_blender.modeling import Kit, ModelError
mg = Kit(colors='vertex')
fur = mg.color('fur', (0.6, 0.5, 0.4))
cloth = mg.color('cloth', (0.3, 0.4, 0.2))
sections = [(0,0,0,.08,.04), (.12,0,.2,.10,.035), (.2,.04,.4,.04,.025)]
obj = mg.loft_path(sections, fur, sides=12, axis=(1,0,0), bands=[cloth]+[fur]*11)
bm = bmesh.new(); bm.from_mesh(obj.data)
assert all(e.is_manifold for e in bm.edges), 'Closed anatomical loft must be watertight'
assert bm.calc_volume() > 0, 'Outward winding required for reliable boolean union'
bm.free()
assert len(obj.data.vertices) == 36
assert obj.data.uv_layers.active and obj.data.color_attributes['Col']
for i, row in enumerate(sections):
    center = Vector(row[:3])
    widths = [(obj.data.vertices[i*12+k].co-center).length for k in (0,6)]
    depths = [(obj.data.vertices[i*12+k].co-center).length for k in (3,9)]
    assert all(abs(v-row[3]) < 1e-6 for v in widths)
    assert all(abs(v-row[4]) < 1e-6 for v in depths)
# Along Z this matches horizontal loft, with explicit width/depth orientation.
zloft = mg.loft_path([(0,0,0,.1,.05),(0,0,.3,.07,.035)], fur, sides=8, axis=(1,0,0))
assert abs(zloft.data.vertices[0].co.y) < 1e-6
assert abs(zloft.data.vertices[0].co.x-.1) < 1e-6
polygon = mg.loft_path([(0,0,0,.1,.05),(0,0,.3,.07,.035)], fur,
                       outline=[(-1,-1),(1,-1),(1,1),(-1,1)], smooth=False)
assert len(polygon.data.vertices) == 8 and all(not p.use_smooth for p in polygon.data.polygons)
# Exact boolean joins the new primitive to existing anatomy without remeshing its profile.
attachment = mg.part('sphere', fur, loc=(0,0,-.02), scale=(.16,.12,.12), smooth=True)
joined = mg.union([zloft,attachment], surface='boolean')
bm = bmesh.new(); bm.from_mesh(joined.data)
assert all(e.is_manifold for e in bm.edges) and bm.calc_volume() > 0
bm.free()
# Transport remains stable where the old projected tube normal would collapse.
bend = mg.loft_path([(0,0,0,.02,.01),(0,0,.1,.02,.01),(.1,0,.1,.02,.01),(.1,0,0,.02,.01)], fur)
assert all(math.isfinite(v) for vertex in bend.data.vertices for v in vertex.co)
open_cuff = mg.loft_path([(0,0,0,.1,.05),(0,0,.3,.07,.035)], cloth, sides=8, cap=False)
bm = bmesh.new(); bm.from_mesh(open_cuff.data)
assert sum(e.is_boundary for e in bm.edges) == 16
bm.free()
rounded = mg.loft_path(sections, fur, subdiv=1)
assert len(rounded.data.vertices) > len(obj.data.vertices)
for kwargs in ({'axis':(0,0,1)}, {'sides':2}, {'outline':[(0,0),(0,1),(1,0)]}, {'bands':[fur]}):
    try:
        mg.loft_path([(0,0,0,.1,.05),(0,0,.3,.07,.035)], fur, **kwargs)
    except ModelError:
        pass
    else:
        raise AssertionError(kwargs)
for rows in ([(0,0,0,.1,.05),(0,0,0,.1,.05)], [(0,0,0,.1,.05),(0,0,.1,.1,.05),(0,0,0,.1,.05)]):
    try:
        mg.loft_path(rows, fur)
    except ModelError:
        pass
    else:
        raise AssertionError(rows)
print('loft_path verified: manifold positive volume, elliptical sections, bent frame, UV/colour, open cuffs, subdivision and invalid paths.')
