"""Concave triangulation checks in real Blender."""
import sys
from pathlib import Path
from mathutils import Vector, Matrix
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'sources'/'blender'))
from meshgate_blender.modeling import Kit, ModelError
mg = Kit(colors='vertex')
# Notched L: a centre fan would cross the inward corner.
loop = [(0,0,0),(3,0,0),(3,1,0),(1,1,0),(1,3,0),(0,3,0)]
rotation = Matrix.Rotation(.73,4,'X') @ Matrix.Rotation(.41,4,'Z')
for reverse in (False,True):
    vertices = [rotation @ Vector(p) + Vector((.3,-.8,.4)) for p in (loop[::-1] if reverse else loop)]
    faces = mg.triangulate_polygon(vertices)
    assert len(faces) == 4
    boundary_normal = sum((a.cross(b) for a,b in zip(vertices,vertices[1:]+vertices[:1])), Vector())
    area = 0
    for face in faces:
        a,b,c = (vertices[i] for i in face)
        cross = (b-a).cross(c-a)
        assert cross.dot(boundary_normal) > 0, 'Triangle winding must follow boundary'
        area += cross.length/2
    assert abs(area-5) < 1e-5, 'Concave area must be conserved without overlapped fan triangles'
    obj = mg.mesh(vertices, faces, mg.color('shape'+str(reverse),(.5,.4,.3)))
    assert len(obj.data.polygons) == 4
for vertices in ([(0,0,0),(1,0,0)], [(0,0,0),(1,0,0),(2,0,0)],
                 [(0,0,0),(1,0,0),(1,0,0)], [(0,0,0),(1,0,0),(0,float('nan'),0)]):
    try: mg.triangulate_polygon(vertices)
    except ModelError: pass
    else: raise AssertionError(vertices)
print('triangulate_polygon verified: concave area conservation, winding in rotated 3D/reversed loops, mesh compatibility and invalid boundaries.')
