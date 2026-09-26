"""Render the original MeshGate cinematic README hero with Blender 3.5+.

blender -b -t 6 --python scripts/render_readme_hero.py -- --preview
blender -b -t 6 --python scripts/render_readme_hero.py
ffmpeg -framerate 16 -i out/hero-frames/frame-%03d.png -filter_complex '[0:v] split [a][b];[a] palettegen=max_colors=192:stats_mode=diff [p];[b][p] paletteuse=dither=bayer:bayer_scale=3' -loop 0 docs/img/meshgate-hero-v3.gif
"""
import bpy
import math
import random
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out' / 'hero-frames'
PREVIEW = '--preview' in sys.argv
COUNT = 48
TAU = math.tau

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.taa_render_samples = 64
scene.eevee.use_gtao = True
scene.eevee.gtao_distance = 3
scene.eevee.gtao_factor = 1.3
scene.eevee.use_bloom = True
scene.eevee.bloom_intensity = .035
scene.eevee.bloom_radius = 5
scene.render.resolution_x = 1400
scene.render.resolution_y = 560
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = .35
scene.world.color = (.007, .011, .015)


def mat(name, color, metal=0, rough=.4, glow=None, power=0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = rough
    if glow:
        bsdf.inputs['Emission'].default_value = (*glow, 1)
        bsdf.inputs['Emission Strength'].default_value = power
    return material


graphite = mat('Satin black titanium', (.028, .047, .055), .94, .27)
black = mat('Obsidian', (.009, .017, .022), .6, .32)
silver = mat('Titanium glints', (.34, .49, .52), .85, .21)
bright = mat('Polished edge', (.68, .85, .86), .78, .16)
teal = mat('Portal photon', (.01, .65, .6), .25, .14, (.0, .95, .82), 5)
teal_soft = mat('Quiet cyan', (.02, .23, .24), .5, .26, (.02, .65, .65), .7)
orange = mat('Amber facets', (.78, .22, .055), .58, .24, (1, .2, .01), 1.35)
gold = mat('Copper metal', (.45, .17, .055), .86, .25)
floor_mat = mat('Studio floor', (.015, .024, .03), .46, .31)
back = mat('Backdrop', (.006, .012, .017), .03, .86)


def beam(name, a, b, width, depth, material, bevel=.02):
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(a+b)/2)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (width, depth, (b-a).length)
    obj.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler()
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('Cut corner', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    obj.data.use_auto_smooth = True
    obj.data.materials.append(material)
    return obj


def ring(name, points, y, width, depth, material, bevel=.025):
    return [beam(f'{name} {i:02d}', (a[0],y,a[1]), (b[0],y,b[1]), width,depth,material,bevel)
            for i,(a,b) in enumerate(zip(points, points[1:]))]

# The icon's open, six-sided gate: nested architectural layers, separated in depth.
gate_start = set(bpy.context.scene.objects)
gate = [(-2.36,-1.38),(-2.36,1.11),(-1.60,1.88),(.21,1.88),(.98,1.11),(.98,-1.38)]
ring('Structural gate',gate,.15,.30,.52,black,.065)
ring('Machined face',gate,-.18,.245,.115,graphite,.027)
ring('Outer chamfer',gate,-.252,.035,.025,silver,.009)
inner = [(-2.07,-1.32),(-2.07,1.0),(-1.46,1.60),(.07,1.60),(.67,1.0),(.67,-1.32)]
ring('Luminous inner gate',inner,-.285,.08,.045,teal,.018)
ring('Photon core',inner,-.322,.017,.022,bright,.005)
# Broken exterior armor plates add the designed, constructed rhythm of the reference.
for i,(a,b) in enumerate(zip(gate,gate[1:])):
    for j in range(12):
        u0,u1=(j+.065)/12,(j+.91)/12
        p0=(a[0]*(1-u0)+b[0]*u0,-.31,a[1]*(1-u0)+b[1]*u0)
        p1=(a[0]*(1-u1)+b[0]*u1,-.31,a[1]*(1-u1)+b[1]*u1)
        beam(f'Gate armor {i:02d}-{j:02d}',p0,p1,.168,.075,
             silver if (i*12+j)%17==0 else graphite,.012)

# Turn the entire portal toward the stream. The near jamb now makes the exit
# legible in depth instead of looking like fragments appearing beside a flat icon.
gate_root = bpy.data.objects.new('Angled portal assembly', None)
scene.collection.objects.link(gate_root)
gate_root.location = (-.7, 0, 0)
for part in set(scene.objects) - gate_start - {gate_root}:
    part.parent = gate_root
    part.matrix_parent_inverse = gate_root.matrix_world.inverted()
gate_root.rotation_euler.z = math.radians(24)

# Centerpiece: a hand-built asymmetric low-poly crystal, the silhouette of the app icon.
verts=[(-.71,-.35,-.11),(-.43,-.38,.64),(.27,-.35,.9),(.83,-.25,.27),(.68,-.31,-.65),
       (-.19,-.35,-.89),(-.17,-.92,-.04),(.19,.37,.12)]
faces=[(0,1,6),(1,2,6),(2,3,6),(3,4,6),(4,5,6),(5,0,6),
       (1,0,7),(2,1,7),(3,2,7),(4,3,7),(5,4,7),(0,5,7)]
mesh=bpy.data.meshes.new('Twelve intentional facets')
mesh.from_pydata(verts,[],faces)
mesh.materials.append(graphite)
mesh.materials.append(silver)
mesh.materials.append(gold)
mesh.materials.append(orange)
mesh.materials.append(black)
mesh.update()
crystal=bpy.data.objects.new('Hero crystal',mesh)
scene.collection.objects.link(crystal)
crystal.location=(-.72,-.63,.1)
for poly,index in zip(mesh.polygons,[1,0,1,2,0,0,0,1,2,3,4,0]):
    poly.material_index=index
# Clean physical seams: bevel and narrow, non-uniform metal wires.
bevel=crystal.modifiers.new('Facet edge light','BEVEL')
bevel.width=.016
bevel.segments=1
crystal.modifiers.new('Normals','WEIGHTED_NORMAL')
crystal.data.use_auto_smooth = True
wire=bpy.data.objects.new('Crystal wire shell',mesh.copy())
scene.collection.objects.link(wire)
wire.location=crystal.location
wire.data.materials.clear()
wire.data.materials.append(bright)
w=wire.modifiers.new('Cut seams','WIREFRAME')
w.thickness=.009

# A curved reconstruction trail flies out of the gate and visually resolves into game geometry.
random.seed(34)
fragments=[]
for i in range(205):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj=bpy.context.object
    obj.name=f'Voxel {i:03d}'
    obj.data.materials.append(teal if i%19==0 else orange if i%11==0 else silver if i%4==0 else graphite)
    mod=obj.modifiers.new('Tiny machined edge','BEVEL')
    mod.width=.08
    mod.segments=1
    obj.modifiers.new('Normals','WEIGHTED_NORMAL')
    obj.data.use_auto_smooth = True
    fragments.append((obj,random.random(),random.random()*TAU,random.uniform(.25,1.1),random.uniform(.065,.18)))

# Floating drafting lines are a quiet product detail, not a decorative UI overlay.
for i in range(13):
    x=1.1+i*.33
    beam(f'Calibration tick {i}',(x,.48,-1.62),(x,.48,-1.62+(.10 if i%3 else .18)),
         .007,.007,teal_soft,.001)
beam('Calibration baseline',(1.05,.49,-1.67),(5.18,.49,-1.67),.006,.006,teal_soft,.001)

bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-1.75))
bpy.context.object.data.materials.append(floor_mat)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,5.5,0),rotation=(math.pi/2,0,0))
bpy.context.object.data.materials.append(back)


def area(name, loc, color, power, size, target):
    data=bpy.data.lights.new(name,'AREA')
    data.energy=power
    data.color=color
    data.shape='DISK'
    data.size=size
    obj=bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.location=loc
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

area('Long cool box',(-3.8,-4.6,4.6),(.53,.83,1),1400,5,(-1,0,0))
area('Cyan gate spill',(-1.7,.4,1),(.0,.95,.85),700,3,(-1,-.4,0))
area('Warm cutting rim',(3.0,1.1,2.0),(1,.38,.16),1100,3,(1,0,0))
area('Front flash',(0,-7,1.5),(.9,1,1),420,6,(-.2,0,0))

bpy.ops.object.camera_add(location=(.75,-12.5,1.35))
camera=bpy.context.object
camera.rotation_euler=(Vector((.7,0,.16))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=12.4
scene.camera=camera
OUT.mkdir(parents=True,exist_ok=True)

for frame in range(1 if PREVIEW else COUNT):
    t=.18 if PREVIEW else frame/COUNT
    teal.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=4.4+1.1*math.sin(TAU*t)
    crystal.rotation_euler=(.09*math.sin(TAU*t),-.2+.34*math.sin(TAU*t),.07*math.sin(TAU*t))
    crystal.location.z=.09+.09*math.sin(TAU*t)
    wire.rotation_euler=crystal.rotation_euler
    wire.location=crystal.location
    for obj,base,phase,spread,size in fragments:
        p=(base+t)%1
        theta=phase+TAU*(1.15*p+t*.30)
        center=-.15+5.35*p
        radius=spread*(.12+.95*math.sin(math.pi*p))
        # Bend sharply toward the camera before crossing the near jamb.
        # This visible foreground overlap is what makes the portal the source.
        depth=-.70-1.45*(1-math.exp(-13*p))-.35*p
        obj.location=(center, depth+radius*math.sin(theta)*.55,
                      -.02+radius*math.cos(theta)*.85)
        s=size*(.48+.85*math.sin(math.pi*p))
        obj.scale=(s*1.35,s*.72,s)
        obj.rotation_euler=(theta*.45,theta*.7,theta*.32)
    scene.render.filepath=str(OUT/('preview.png' if PREVIEW else f'frame-{frame:03d}.png'))
    bpy.ops.render.render(write_still=True)
    print(f'MESHGATE_HERO {frame+1}/{1 if PREVIEW else COUNT}',flush=True)
