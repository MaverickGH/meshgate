"""Finalized PBR base → reduced geometry → native morphs without repainting."""
import sys
import tempfile
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'sources' / 'blender'))
from meshgate_blender.modeling import Kit, ModelError
base = Path(__file__).resolve().parents[2] / 'out/gen/cat_head_study/cat_head_study.blend'
bpy.ops.wm.read_factory_settings(use_empty=True)
mg = Kit(name='base_test')
obj = mg.load_base(str(base), ratio=.12)
assert obj.data.uv_layers.active is not None
images = {n.image for material in obj.data.materials if material and material.use_nodes
          for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}
assert images, 'Baked PBR texture images must survive import'
assert all(image.packed_file for image in images), 'Base must remain portable'
checksums = {image: (tuple(image.size), tuple(image.pixels[:24])) for image in images}
count = len(obj.data.vertices)
mg.morph('head_width', at=(0,0,.74), radius=.3, scale=(1.15,1,1))
mg.morph('ears', at=(.17,0,.78), radius=.2, scale=1.1, above=.79, mirror=True)
notes = mg._finalize()
assert len(obj.data.vertices) == count, 'Morph creation must not change topology'
assert obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) == 5
assert obj.data.uv_layers.active is not None
assert all((tuple(image.size), tuple(image.pixels[:24])) == checksums[image] for image in images)
assert bpy.context.scene['mg_base_materials']
print('load_base verified:', len(obj.data.polygons), 'faces;', len(images), 'packed PBR images; two native morphs; UV/images unchanged after finalize.')
for path, ratio in [('missing.blend',1), (str(base),0)]:
    try: mg.load_base(path,ratio=ratio)
    except ModelError: pass
    else: raise AssertionError('Invalid base input accepted')

# Reusing a previously morphed saved base must restore Basis and replace old metadata.
with tempfile.TemporaryDirectory() as tmp:
    path = str(Path(tmp) / 'with_morphs.blend')
    basis = [tuple(v.co) for v in obj.data.shape_keys.key_blocks[0].data]
    obj.data.shape_keys.key_blocks[1].value = .8
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    again = Kit(name='again')
    reused = again.load_base(path)
    assert not reused.data.shape_keys and 'meshgate_morphs' not in reused
    assert all((v.co-Vector(p)).length < 1e-6 for v,p in zip(reused.data.vertices,basis))
print('Saved morph base resets to Basis, with old keys/metadata removed.')
