"""Render the MeshGate README hero with Blender 3.5+: parts fly out of the portal and snap together, bottom to top, like
a construction kit — a windmill that turns its sails, a treasure chest that opens, a street lamp that lights up. Each
model comes apart before the next one; the loop restarts after the lamp.

blender -b -t 6 --python scripts/render_readme_hero.py -- --preview      # one frame, mid-build
blender -b -t 6 --python scripts/render_readme_hero.py
ffmpeg -framerate 14 -i out/hero-frames/frame-%03d.png -filter_complex '[0:v] split [a][b];[a] palettegen=max_colors=160:stats_mode=diff [p];[b][p] paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle' -loop 0 docs/img/meshgate-hero-v4.gif
"""
import bpy
import math
import random
import sys
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out' / 'hero-frames'
PREVIEW = '--preview' in sys.argv
COUNT = 144                 # 48 frames per model
FLOOR = -1.75
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
scene.render.resolution_x = 1200
scene.render.resolution_y = 480
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
flight = mat('Kit part in flight', (.32, .62, .62), .55, .2, (.0, .85, .75), 1.6)
treasure = mat('Treasure glow', (1, .62, .18), .3, .3, (1, .55, .12), .4)
lamp_glass = mat('Lantern glass', (.85, .78, .6), .1, .15, (1, .62, .28), 0)


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
gate = [(-2.36,FLOOR+.1),(-2.36,1.11),(-1.60,1.88),(.21,1.88),(.98,1.11),(.98,FLOOR+.1)]
ring('Structural gate',gate,.15,.30,.52,black,.065)
ring('Machined face',gate,-.18,.245,.115,graphite,.027)
ring('Outer chamfer',gate,-.252,.035,.025,silver,.009)
inner = [(-2.07,FLOOR+.14),(-2.07,1.0),(-1.46,1.60),(.07,1.60),(.67,1.0),(.67,FLOOR+.14)]
ring('Luminous inner gate',inner,-.285,.08,.045,teal,.018)
ring('Photon core',inner,-.322,.017,.022,bright,.005)
# The gate stands on the floor: a heavy foot under each leg.
for x in (-2.36, .98):
    beam(f'Gate foot {x:+.2f}', (x, -.02, FLOOR), (x, -.02, FLOOR+.16), .62, .9, black, .04)
    beam(f'Foot trim {x:+.2f}', (x, -.48, FLOOR+.155), (x, -.48, FLOOR+.175), .5, .03, silver, .005)
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

# The kit: three models built from simple parts, each in build order (bottom to top). A part flies out of the portal on
# an arc, turns into place, lands with a small snap and a flash, then keeps its own material.
X0, Y0 = 3.45, .35
models = []
parts = []   # the model being defined


def finish(obj, material):
    mod = obj.modifiers.new('Machined edge', 'BEVEL')
    mod.width, mod.segments, mod.limit_method = .018, 1, 'ANGLE'
    obj.modifiers.new('Normals', 'WEIGHTED_NORMAL')
    obj.data.use_auto_smooth = True
    obj.data.materials.append(material)
    obj.rotation_mode = 'QUATERNION'
    parts.append({'obj': obj, 'mat': material, 'loc': obj.location.copy(), 'rot': obj.rotation_quaternion.copy(),
                  'scale': obj.scale.copy()})
    return obj


def part(kind, loc, material, rot=(0, 0, 0), **size):
    {'cyl': bpy.ops.mesh.primitive_cylinder_add, 'cone': bpy.ops.mesh.primitive_cone_add}[kind](
        location=loc, rotation=rot, **size)
    return finish(bpy.context.object, material)


def box(loc, dims, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.scale = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, material)


def pivot(name, loc, children, rot=(0, 0, 0)):
    """An empty the given parts turn around (sails on the rotor, the chest lid on its hinge)."""
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.location = loc
    e.rotation_euler = rot
    bpy.context.view_layer.update()
    for c in children:
        c.parent = e
        c.matrix_parent_inverse = e.matrix_world.inverted()
    return e


def light(name, loc, color):
    data = bpy.data.lights.new(name, 'POINT')
    data.energy, data.color, data.shadow_soft_size = 0, color, .15
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = loc
    return data


def model(finale):
    global parts
    models.append({'parts': parts, 'finale': finale})
    parts = []


def smooth(u):
    u = min(1, max(0, u))
    return u * u * (3 - 2 * u)


# 1. Windmill — the sails spin once it is whole
F = FLOOR
z = F
part('cyl', (X0, Y0, z+.07), graphite, vertices=12, radius=.98, depth=.14); z += .14
part('cyl', (X0, Y0, z+.05), black, vertices=12, radius=.8, depth=.1); z += .1
for k, (r1, r2, m) in enumerate([(.64, .57, graphite), (.57, .5, silver), (.5, .43, graphite)]):
    part('cone', (X0, Y0, z+.29), m, vertices=8, radius1=r1, radius2=r2, depth=.58)
    if k < 2:
        part('cyl', (X0, Y0, z+.58), orange, vertices=8, radius=r2+.04, depth=.05)
    if k == 0:
        box((X0, Y0-r1+.05, z+.22), (.3, .1, .42), orange)
    else:
        box((X0, Y0-r1+.04, z+.3), (.18, .08, .2), teal)
    z += .58
part('cyl', (X0, Y0, z+.04), silver, vertices=8, radius=.5, depth=.08); z += .08
part('cone', (X0, Y0, z+.3), gold, vertices=8, radius1=.6, radius2=0, depth=.6)
hub_z = z - .12
part('cyl', (X0, Y0-.62, hub_z), bright, rot=(math.pi/2, 0, 0), vertices=10, radius=.13, depth=.3)
blades = []
for k in range(4):
    a = k*math.pi/2 + math.radians(20)
    blades.append(box((X0 + .62*math.cos(a), Y0-.72, hub_z + .62*math.sin(a)), (1.02, .05, .17),
                      graphite if k % 2 else silver, rot=(0, -a, 0)))
box((X0+1.15, Y0-.35, F+.19), (.38, .38, .38), gold, rot=(0, 0, math.radians(18)))
part('cyl', (X0-1.1, Y0-.3, F+.24), graphite, vertices=10, radius=.2, depth=.48)
rotor = pivot('Rotor', (X0, Y0-.72, hub_z), blades)
model(lambda tl: setattr(rotor, 'rotation_euler', (0, -30 * max(0, tl - .75)**1.3, 0)))

# 2. Treasure chest — the lid opens and the gold inside lights up. Built facing the camera, then turned to a three-quarter
#    view so the open lid reads; a little bigger than life so it holds its own next to the windmill.
S, TURN = 1.25, math.radians(-32)
top = F + .6*S
start = len(parts)
box((X0, Y0, F+.03), (1.36*S, .9*S, .06), graphite)
box((X0, Y0, F+.33*S), (1.2*S, .76*S, .54*S), gold)
for dx in (-.36, .36):
    box((X0+dx*S, Y0, F+.33*S), (.09*S, .8*S, .56*S), silver)
box((X0, Y0, top-.03), (1.08*S, .64*S, .05), treasure)
box((X0, Y0-.4*S, F+.5*S), (.16*S, .06*S, .2*S), orange)
lid_from = len(parts)
box((X0, Y0, top+.13*S), (1.2*S, .76*S, .26*S), gold)
for dx in (-.36, .36):
    box((X0+dx*S, Y0, top+.13*S), (.09*S, .8*S, .28*S), silver)
box((X0, Y0-.39*S, top+.06*S), (.3*S, .05*S, .08*S), silver)
lid = [p['obj'] for p in parts[lid_from:]]
for k in range(3):
    part('cyl', (X0+.95*S, Y0-.45*S, F+.02+.042*k), gold, vertices=12, radius=.11*S, depth=.04)
turn = Matrix.Rotation(TURN, 4, 'Z')
centre = Vector((X0, Y0, 0))
for p in parts[start:]:                    # the whole chest turns about its centre
    p['loc'] = centre + turn.to_3x3() @ (p['loc'] - centre)
    p['rot'] = turn.to_quaternion() @ p['rot']
    p['obj'].location, p['obj'].rotation_quaternion = p['loc'], p['rot']
hinge_at = centre + turn.to_3x3() @ (Vector((X0, Y0+.38*S, top)) - centre)
hinge = pivot('Lid hinge', hinge_at, lid, rot=(0, 0, TURN))
glow = light('Treasure light', centre + Vector((0, 0, top+.4)), (1, .62, .25))


def chest(tl):
    o = smooth((tl - .75) / .09)
    hinge.rotation_euler = (-1.05 * o, 0, TURN)
    treasure.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value = .4 + 3.2 * o
    glow.energy = 70 * o


model(chest)

# 3. Street lamp — the lantern lights up and throws a pool of light
part('cyl', (X0, Y0, F+.06), graphite, vertices=10, radius=.38, depth=.12)
part('cyl', (X0, Y0, F+.2), black, vertices=10, radius=.25, depth=.16)
part('cyl', (X0, Y0, F+.83), silver, vertices=10, radius=.075, depth=1.1)
part('cyl', (X0, Y0, F+1.41), orange, vertices=10, radius=.1, depth=.06)
part('cyl', (X0, Y0, F+1.99), graphite, vertices=10, radius=.065, depth=1.1)
part('cone', (X0, Y0, F+2.62), gold, vertices=8, radius1=.09, radius2=0, depth=.16)
box((X0+.38, Y0, F+2.36), (.8, .07, .07), silver)
box((X0+.2, Y0, F+2.2), (.45, .05, .05), graphite, rot=(0, math.radians(-38), 0))
box((X0+.72, Y0, F+2.28), (.03, .03, .12), silver)
part('cone', (X0+.72, Y0, F+2.17), gold, vertices=6, radius1=.22, radius2=.05, depth=.16)
part('cyl', (X0+.72, Y0, F+1.94), lamp_glass, vertices=6, radius=.15, depth=.3)
part('cone', (X0+.72, Y0, F+1.75), gold, vertices=6, radius1=.08, radius2=.16, depth=.08)
part('cyl', (X0-.85, Y0-.25, F+.22), orange, vertices=10, radius=.12, depth=.44)
part('cone', (X0-.85, Y0-.25, F+.5), orange, vertices=10, radius1=.13, radius2=.04, depth=.14)
box((X0-.85, Y0-.39, F+.3), (.1, .1, .1), silver)
lantern = light('Lantern light', (X0+.72, Y0-.25, F+1.9), (1, .66, .32))


def lamp(tl):
    o = smooth((tl - .75) / .06)
    flicker = 1 - .12 * math.sin(90 * tl) * (1 - o) if o > 0 else 0
    lamp_glass.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value = 9 * o * flicker
    lantern.energy = 260 * o * flicker


model(lamp)

for m in models:
    for p in m['parts']:     # hidden until launched
        p['obj'].scale = (0, 0, 0)

# Where the parts come from: the crystal in the middle of the portal.
random.seed(7)
for m in models:
    for p in m['parts']:
        p['spin'] = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))).normalized()

bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,FLOOR))
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

LAUNCH, FLIGHT, FLASH = .035, .12, .03       # in model time (0–1 per model): first launch, flight, landing flash
LAST = .62                                  # the last part launches here and lands by ~.74
SPIN, APART, GONE = .75, .88, .985          # the finale plays, then the kit comes apart for the next model


def ease_out(u):
    return 1 - (1 - u) ** 3


def pose(p, k, n, tl):
    """Where part k of n is at model time tl: hidden, flying, landed (with snap and flash) or coming apart."""
    obj, start = p['obj'], LAUNCH + k * (LAST - LAUNCH) / (n - 1)
    if tl < start or tl >= GONE:
        obj.scale = (0, 0, 0)
        return
    src = crystal.matrix_world.translation
    u = min(1, (tl - start) / FLIGHT)
    e = ease_out(u)
    if u < 1:
        mid = (src + p['loc']) / 2 + Vector((0, -1.3, 1.7))
        pos = (1-e)**2 * src + 2*(1-e)*e * mid + e**2 * p['loc']
        rot = p['spin'].to_track_quat('Z', 'Y').slerp(p['rot'], e)
        s = .3 + .7*e
        obj.data.materials[0] = flight
    else:
        pos, rot, s = p['loc'], p['rot'], 1.0
        landed = tl - start - FLIGHT
        if landed < FLASH:
            s = 1 + .07*math.sin(math.pi*landed/FLASH)
            obj.data.materials[0] = bright
        else:
            obj.data.materials[0] = p['mat']
    if tl >= APART:                         # come apart top-down, each part lifting and shrinking away
        a = min(1, max(0, (tl - APART - (n-1-k)*(GONE-APART)*.45/n) / ((GONE-APART)*.55)))
        pos = pos + Vector((0, 0, .9*a*a))
        s *= 1 - a
    obj.location = pos                      # parts on a pivot: rest-pose coordinates; the pivot turns them on top
    obj.rotation_quaternion = rot
    obj.scale = p['scale'] * s


for frame in range(1 if PREVIEW else COUNT):
    t = (.5 + 1) / 3 if PREVIEW else frame / COUNT        # preview: the chest, mid-build
    teal.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value = 4.4 + 1.1*math.sin(TAU*t*3)
    crystal.rotation_euler = (.09*math.sin(TAU*t), -.2 + .34*math.sin(TAU*t), .07*math.sin(TAU*t))
    crystal.location.z = .09 + .09*math.sin(TAU*t*3)
    wire.rotation_euler = crystal.rotation_euler
    wire.location = crystal.location
    current = min(len(models) - 1, int(t * len(models)))
    tl = t * len(models) - current
    for i, m in enumerate(models):
        m['finale'](tl if i == current else 0)
    bpy.context.view_layer.update()
    for i, m in enumerate(models):
        n = len(m['parts'])
        for k, p in enumerate(m['parts']):
            pose(p, k, n, tl if i == current else -1)
    scene.render.filepath = str(OUT / ('preview.png' if PREVIEW else f'frame-{frame:03d}.png'))
    bpy.ops.render.render(write_still=True)
    print(f'MESHGATE_HERO {frame+1}/{1 if PREVIEW else COUNT}', flush=True)
