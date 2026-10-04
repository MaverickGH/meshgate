import bpy,bmesh,sys,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sources/blender'))
from meshgate_blender.modeling import Kit

def inside(tree,point):
 votes=0
 for direction in [( .312,.553,.772),(-.674,.259,.691),(.233,-.781,.579)]:
  ray=Vector(direction).normalized();start=Vector(point);count=0
  for _ in range(64):
   hit=tree.ray_cast(start,ray)
   if hit[0] is None:break
   count+=1;start=hit[0]+ray*1e-5
  else:raise AssertionError('ray did not exit closed surface')
  votes+=count%2
 return votes>=2

def tree_of(mesh):return BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons])
if '--self-test' in sys.argv:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1)
 tree=tree_of(bpy.context.object.data)
 assert inside(tree,(0,0,0)) and not inside(tree,(1.5,0,0))
 bpy.ops.mesh.primitive_torus_add(major_radius=1.2,minor_radius=.3)
 tree=tree_of(bpy.context.object.data)
 assert not inside(tree,(0,0,0)) and inside(tree,(1.2,0,0)) and not inside(tree,(0,0,1))
 print('PASS: sphere interior/exterior and torus concave hole tested independently of normals.')
else:
 base=Path(__file__).resolve().parents[2]/'samples/bases/cat_scout_v10.blend'
 if not base.is_file():   # a working base kept on the author's disk, not in the repository
  print('SKIP: samples/bases/cat_scout_v10.blend is not here'); raise SystemExit(0)
 bpy.ops.wm.open_mainfile(filepath=str(base))
 original=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
 links=[set() for _ in original.data.vertices]
 for e in original.data.edges:
  a,b=e.vertices;links[a].add(b);links[b].add(a)
 remaining=set(range(len(links)));groups=[]
 while remaining:
  g=set();stack=[min(remaining)]
  while stack:
   i=stack.pop()
   if i not in g:g.add(i);stack.extend(links[i]-g)
  remaining-=g;groups.append(g)
 skin=max(groups,key=len);ids=sorted(skin);mapping={old:new for new,old in enumerate(ids)}
 points=[tuple(original.data.vertices[i].co) for i in ids]
 faces=[tuple(mapping[i] for i in p.vertices) for p in original.data.polygons if p.vertices[0] in skin]
 bpy.ops.wm.read_factory_settings(use_empty=True)
 mg=Kit(name='probe');grey=mg.color('skin','#aaaaaa');olive=mg.color('cloth','#737859');brown=mg.color('shorts','#604b40')
 body=mg.mesh(points,faces,grey,name='body',smooth=True)
 shirt=mg.garment(body,olive,above=.294,below=.505,gap=.009,thickness=.004,refine=1,open_front=.075,regions=[((-.15,-.11,.29),(.15,.11,.505)),((.13,-.11,.390),(.24,.11,.505)),((-.24,-.11,.390),(-.13,.11,.505))])
 pants=mg.garment(body,brown,above=.160,below=.309,gap=.003,thickness=.002,refine=1,regions=[((-.172,-.13,.15),(.172,.13,.32))])
 tree=tree_of(body.data)
 result={}
 for label,o in [('shirt',shirt),('pants',pants)]:
  bm=bmesh.new();bm.from_mesh(o.data)
  assert all(e.is_manifold for e in bm.edges),(label,'open shell')
  bm.free()
  points=[v.co for v in o.data.vertices]+[p.center for p in o.data.polygons]
  bad=[p for p in points if inside(tree,p) and tree.find_nearest(p)[3]>.001]
  result[label]={'vertices':len(o.data.vertices),'faces':len(o.data.polygons),'penetrating_samples':len(bad)}
  assert not bad,(label,len(bad))
 print('PASS: real concave skin fit has no penetrating vertices or face centres.')
