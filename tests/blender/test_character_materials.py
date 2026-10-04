"""Subtle character tiles stay deterministic, periodic and valid for PBR export."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sources/blender'))
from meshgate_blender import tiles
for pattern in ('fabric','leather'):
 a=tiles.draw(pattern,(.4,.3,.2),px=256,seed=4,rough=.9)
 b=tiles.draw(pattern,(.4,.3,.2),px=256,seed=4,rough=.9)
 for x,y in zip(a,b):
  assert np.array_equal(x,y)
  assert np.isfinite(x).all() and x.min()>=0 and x.max()<=1
 colour,height,rough,metal=a
 assert np.ptp(height)>0
 assert float(colour.max())<.45, 'Weave must not wash out the base colour'
 normal=tiles.normal_from_height(height,1)
 assert np.isfinite(normal).all()
 # Tile edges wrap: the seam gradient should remain comparable to ordinary neighbouring pixels.
 edge=np.abs(height[:,0]-height[:,-1]).mean()
 typical=np.abs(np.diff(height,axis=1)).mean()
 assert edge<=typical*4+.005,(pattern,edge,typical)
print('PASS: fabric/leather PBR maps, deterministic texture scale, bounded contrast and periodic seams.')
# Exported baked bases must not multiply their PBR textures by internal paint.
# Pass a generated cat GLB after -- to exercise the complete export path.
if '--' in sys.argv:
 import bpy
 asset=sys.argv[sys.argv.index('--')+1]
 bpy.ops.import_scene.gltf(filepath=asset)
 for material in bpy.data.materials:
  if material.use_nodes and material.name.endswith(('_bandana','_leather','_shirt_olive','_shorts_brown')):
   assert not any(n.type in {'VERTEX_COLOR','ATTRIBUTE'} for n in material.node_tree.nodes),material.name
   images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'basecolor' in n.image.name]
   assert images,material.name
   for image in images:
    pixels=np.array(image.pixels[:]).reshape(-1,4)
    assert pixels[:,:3].mean()>.1,(material.name,'black exported texture')
 print('PASS: exported fabric/leather colours are not multiplied by internal paint.')
