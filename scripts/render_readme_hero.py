"""Render the MeshGate README hero in Blender 3.5+.

blender -b -t 4 --python scripts/render_readme_hero.py -- --preview
blender -b -t 4 --python scripts/render_readme_hero.py
Then encode the PNG frames with ffmpeg. No external assets are used.
"""
import bpy
import math
import random
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "hero-frames"
PREVIEW = "--preview" in sys.argv
COUNT = 32

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 32
scene.eevee.use_gtao = True
scene.eevee.gtao_distance = 3
scene.eevee.gtao_factor = 1.1
scene.eevee.use_bloom = True
scene.eevee.bloom_intensity = 0.018
scene.render.resolution_x = 1100
scene.render.resolution_y = 400
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1
scene.world.color = (0.01, 0.01, 0.012)


def mat(name, color, metallic=0, roughness=0.5, emission=None, strength=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    return m


charcoal = mat("Graphite titanium", (0.055, 0.061, 0.069), .86, .3)
steel = mat("Machined silver", (.42, .45, .47), .78, .27)
light_steel = mat("Brushed bright edge", (.7, .72, .7), .72, .3)
ember = mat("Warm signal", (.95, .36, .11), .32, .28, (.95, .22, .055), 2.5)
dark_ember = mat("Copper edge", (.38, .12, .045), .72, .26)
back = mat("Backdrop", (.009, .011, .014), .1, .72)
floor_mat = mat("Floor", (.018, .02, .023), .4, .45)


def beam(name, a, b, width, depth, material, bevel=.03):
    center = (Vector(a) + Vector(b)) / 2
    direction = Vector(b) - Vector(a)
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (width, depth, direction.length)
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = obj.modifiers.new("Machined corners", "BEVEL")
    mod.width = bevel
    mod.segments = 2
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    obj.data.materials.append(material)
    obj.data.use_auto_smooth = True
    return obj


# Five heavy facets make the portal read as an architectural G, open at its foot.
portal = [(-2.0, -1.35), (-2.0, 1.15), (-1.38, 1.76), (.18, 1.76), (.8, 1.15), (.8, -1.35)]
for i in range(len(portal) - 1):
    a, b = portal[i], portal[i + 1]
    beam(f"Gate segment {i:02d}", (a[0], .22, a[1]), (b[0], .22, b[1]), .19, .34, charcoal, .055)
    beam(f"Inner silver rib {i:02d}", (a[0] + .055, -.01, a[1] - .035),
         (b[0] + .055, -.01, b[1] - .035), .033, .045, light_steel, .008)
    beam(f"Signal line {i:02d}", (a[0] + .11, -.15, a[1] - .11),
         (b[0] + .11, -.15, b[1] - .11), .023, .025, ember, .005)
    for j in range(9):
        u0, u1 = (j + .08) / 9, (j + .86) / 9
        p0 = (a[0] * (1-u0) + b[0] * u0, -.035, a[1] * (1-u0) + b[1] * u0)
        p1 = (a[0] * (1-u1) + b[0] * u1, -.035, a[1] * (1-u1) + b[1] * u1)
        beam(f"Gate facet {i:02d}-{j:02d}", p0, p1, .2, .08,
             steel if (i * 9 + j) % 6 == 0 else charcoal, .015)

# Core asset: a bevelled solid with inset, deliberately geometric enough to survive GIF scaling.
bpy.ops.mesh.primitive_cube_add(size=1.15, location=(-.55, -.5, .05))
core = bpy.context.object
core.name = "Generated asset"
core.rotation_euler = (.31, .46, -.18)
bevel = core.modifiers.new("Cut facets", "BEVEL")
bevel.width = .15
bevel.segments = 1
core.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
core.data.materials.append(steel)
core.data.use_auto_smooth = True

# A restrained wire cage exposes the asset topology without covering its faces.
bpy.ops.mesh.primitive_cube_add(size=1.2, location=core.location)
cage = bpy.context.object
cage.name = "Asset wire topology"
cage.rotation_euler = core.rotation_euler
wire = cage.modifiers.new("Mesh edges", "WIREFRAME")
wire.thickness = .018
cage.data.materials.append(dark_ember)

# A field of individual pieces converges into the asset, then re-enters from the right.
random.seed(82)
fragments = []
for i in range(105):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = f"Build fragment {i:03d}"
    obj.data.materials.append(ember if i % 11 == 0 else steel if i % 4 == 0 else charcoal)
    mod = obj.modifiers.new("Soft edge", "BEVEL")
    mod.width = .09
    mod.segments = 1
    obj.data.use_auto_smooth = True
    obj.modifiers.new("Normals", "WEIGHTED_NORMAL")
    fragments.append((obj, i / len(range(105)), random.random() * math.tau, random.uniform(.65, 1.35)))

# Subtle floor catches the physical depth; a backdrop keeps the README banner dark.
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -1.7))
floor = bpy.context.object
floor.name = "Studio floor"
floor.data.materials.append(floor_mat)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 3.4, 0), rotation=(math.pi / 2, 0, 0))
bg = bpy.context.object
bg.name = "Backdrop"
bg.data.materials.append(back)


def area(name, location, color, energy, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector((-0.4, 0, 0)) - obj.location).to_track_quat("-Z", "Y").to_euler()


area("Cool key", (-3.5, -4.5, 4.3), (.72, .83, 1), 1050, 5)
area("Copper rim", (2.4, .4, 2.1), (1, .42, .18), 950, 3)
area("Soft front", (0, -6, 0), (1, .94, .88), 430, 6)

bpy.ops.object.camera_add(location=(.45, -10, 1.45))
camera = bpy.context.object
camera.rotation_euler = (Vector((.45, 0, .12)) - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 10.8
scene.camera = camera

OUT.mkdir(parents=True, exist_ok=True)
for frame in range(1 if PREVIEW else COUNT):
    t = (.22 if PREVIEW else frame / COUNT)
    core.rotation_euler = (.31 + .05 * math.sin(t * math.tau), .46 + t * math.tau, -.18)
    core.location.x = -.55 + .13 * math.sin(t * math.tau)
    cage.location = core.location
    cage.rotation_euler = core.rotation_euler
    for obj, base, phase, spread in fragments:
        p = (base + t) % 1
        spiral = phase + p * math.tau * 2.7
        radius = spread * (1 - .62 * p)
        obj.location = (4.6 - 5.1 * p, .3 + math.sin(spiral) * radius * .58,
                        math.cos(spiral) * radius)
        size = (.065 + .095 * (1 - p)) * min(1, (1 - p) * 8)
        obj.scale = (size * 1.7, size * .75, size)
        obj.rotation_euler = (spiral * .24, spiral * .46, spiral * .2)
    scene.render.filepath = str(OUT / ("preview.png" if PREVIEW else f"frame-{frame:03d}.png"))
    bpy.ops.render.render(write_still=True)
    print(f"MESHGATE_HERO {frame + 1}/{1 if PREVIEW else COUNT}", flush=True)
