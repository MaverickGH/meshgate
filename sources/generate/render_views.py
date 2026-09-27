"""One asset from four sides (3/4, front, side, back — or from above for flat things) in a 2×2 sheet: studio light on
a blue-grey floor, like the Zombie Cats concept art. With a reference picture, the sheet goes on the right of it in one
image — what the AI review loop (`gen --review`) looks at, and handy for people too.

    blender -b -P sources/generate/render_views.py -- model.glb sheet.png [size_px] [samples] [reference.png]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
src, out = a[0], a[1]
px = int(a[2]) if len(a) > 2 else 1024
samples = int(a[3]) if len(a) > 3 else 48
reference = a[4] if len(a) > 4 and a[4] else None

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in sc.objects if o.type == "MESH"]
for o in sc.objects:   # collision proxies and LODs are not part of the look
    if o.name.startswith(("UCX_", "UBX_")) or "_LOD" in o.name or o.name.endswith("_collision"):
        o.hide_render = True
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in meshes if not o.hide_render for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
centre, radius = (lo + hi) / 2, max((hi - lo).length / 2, 0.05)

# floor and world
bpy.ops.mesh.primitive_plane_add(size=radius * 40, location=(centre.x, centre.y, lo.z))
floor = sc.objects[-1] if sc.objects[-1].type == "MESH" else bpy.context.active_object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
fb = fm.node_tree.nodes.get("Principled BSDF")
fb.inputs["Base Color"].default_value = (0.13, 0.17, 0.25, 1)
fb.inputs["Roughness"].default_value = 0.8
floor.data.materials.append(fm)
world = bpy.data.worlds.new("w")
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.14, 0.18, 0.26, 1)
bg.inputs["Strength"].default_value = 0.6


def light(name, kind, loc, energy, size):
    d = bpy.data.lights.new(name, kind)
    d.energy = energy
    if hasattr(d, "size"):
        d.size = size
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = centre + Vector(loc) * radius
    o.rotation_euler = (centre - o.location).to_track_quat("-Z", "Y").to_euler()


light("key", "AREA", (1.6, -2.2, 2.4), 550 * radius * radius, radius * 2.5)
light("fill", "AREA", (-2.4, -1.2, 1.2), 160 * radius * radius, radius * 3)
light("rim", "AREA", (-2.2, 1.8, 2.0), 220 * radius * radius, radius * 2)

cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 70
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
fov = 2 * math.atan(36 / 2 / cam_data.lens)
dist = radius / math.sin(fov / 2) * 1.08
cam_data.clip_start, cam_data.clip_end = radius * 0.01, radius * 100

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = samples
if hasattr(sc.cycles, "use_denoising"):
    sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = px // 2
sc.render.image_settings.file_format = "PNG"
try:
    sc.view_settings.view_transform = "AgX"
except TypeError:
    sc.view_settings.view_transform = "Filmic"

views = [("three_quarter", (0.75, -1.6, 0.55)), ("front", (0, -1, 0.15)), ("side", (1, 0, 0.15)), ("back", (-0.5, 1.2, 0.35))]
if (hi.z - lo.z) < 0.3 * max(hi.x - lo.x, hi.y - lo.y):   # flat things (a tile, a pile of bones) read from above
    views = [("three_quarter", (0.7, -1.1, 1.0)), ("top", (0.0, -0.12, 1.0)), ("front", (0, -1, 0.5)), ("back", (-0.6, 1.0, 0.9))]
tmp = os.path.splitext(out)[0]
tiles = []
for name, d in views:
    d = Vector(d).normalized()
    cam.location = centre + d * dist
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{tmp}.{name}.png"
    bpy.ops.render.render(write_still=True)
    tiles.append(bpy.data.images.load(sc.render.filepath))

# stitch the four views into one 2×2 sheet, with the reference picture on its left when there is one
half = px // 2
left = px if reference else 0
width = left + px
pixels = [0.2, 0.25, 0.34, 1.0] * (width * px)
for i, img in enumerate(tiles):
    src_px = list(img.pixels)
    ox, oy = left + (i % 2) * half, (1 - i // 2) * half   # the four views left to right, top to bottom
    for row in range(half):
        s0 = row * half * 4
        d = ((oy + row) * width + ox) * 4
        pixels[d:d + half * 4] = src_px[s0:s0 + half * 4]
if reference:
    ref = bpy.data.images.load(os.path.abspath(reference))
    rw, rh = ref.size
    k = min(px / rw, px / rh)
    w, h = max(1, int(rw * k)), max(1, int(rh * k))
    ref.scale(w, h)
    rp = list(ref.pixels)
    ch = ref.channels
    ox, oy = (px - w) // 2, (px - h) // 2
    for row in range(h):
        for col in range(w):
            si = (row * w + col) * ch
            d = ((oy + row) * width + ox + col) * 4
            pixels[d:d + 3] = rp[si:si + 3]
sheet = bpy.data.images.new("sheet", width, px, alpha=False)
sheet.pixels = pixels
sheet.filepath_raw = out
sheet.file_format = "PNG"
sheet.save()
for name, _ in views:
    os.remove(f"{tmp}.{name}.png")
print(f"MeshGate views: {out}")
