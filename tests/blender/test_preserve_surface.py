"""Real Blender regression: clothing must not punch holes into anatomical skin."""
import sys
from pathlib import Path
import bpy, bmesh
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sources' / 'blender'))
from meshgate_blender.modeling import Kit, PRESERVE_ATTR

def scene(protect):
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    mg = Kit(colors='vertex', name='protected_body')
    skin = mg.color('skin',(.7,.6,.5)); cloth = mg.color('cloth',(.2,.3,.1))
    # Body continues above/below the enclosing garment. Its middle rings are inside it.
    body = mg.loft_path([(0,0,z,.1,.07) for z in (0,.2,.3,.4,.5,.7)], skin, sides=12)
    if protect:
        mg.preserve_surface(body)
    nbody = len(body.data.polygons)
    garment = mg.part('cube',cloth,loc=(0,0,.35),scale=(.3,.25,.32))
    # Spare internal accessory should still be deleted, demonstrating selective cleanup.
    internal = mg.part('cube',cloth,loc=(0,0,.35),scale=(.025,.025,.025))
    obj = mg.join('body_with_clothing',[garment,body,internal])
    return mg,obj,nbody

mg,control,nbody = scene(False)
before = len(control.data.polygons)
removed = mg._cull_hidden(control)
assert removed > 6, 'Fixture must actually reproduce anatomical face deletion'
mg,obj,nbody = scene(True)
assert sum(item.value for item in obj.data.attributes[PRESERVE_ATTR].data) == nbody
copy = mg.copy(obj)
assert sum(item.value for item in copy.data.attributes[PRESERVE_ATTR].data) == nbody
mg._forget(copy)
notes = mg._finalize_rest([])
marker = obj.data.attributes[PRESERVE_ATTR]
assert sum(item.value for item in marker.data) == nbody
# Marked skin must still form one manifold positive-volume island after real finalization.
bm = bmesh.new(); bm.from_mesh(obj.data)
layer = bm.faces.layers.int.get(PRESERVE_ATTR)
skin_faces = {f for f in bm.faces if f[layer]}
assert len(skin_faces) == nbody
assert all(sum(g in skin_faces for g in e.link_faces)==2 for f in skin_faces for e in f.edges)
seen = set(); stack = [next(iter(skin_faces))]
while stack:
    f = stack.pop()
    if f in seen: continue
    seen.add(f)
    stack.extend(g for e in f.edges for g in e.link_faces if g in skin_faces and g not in seen)
assert seen == skin_faces
bm.free()
assert any('removed 6 hidden faces' in note for note in notes), notes
assert obj.data.uv_layers.active and obj.data.color_attributes['Col']
print('preserve_surface verified: control reproduces holes, joined/copied face protection, finalize keeps connected closed skin, accessory culling/UV/colour remain.')
