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
# close-ups the AI asked for: [{"at": [x, y, z], "from": [dx, dy, dz], "size": m}, …] (up to two, as extra tiles)
import json as _json
closeups = (_json.loads(a[5]) if len(a) > 5 and a[5] else [])[:2]

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
# a hair below the model: a model with its own ground at the lowest point (a yard, a street) must not z-fight it
bpy.ops.mesh.primitive_plane_add(size=radius * 40, location=(centre.x, centre.y, lo.z - max(radius * 0.002, 0.001)))
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
shots = [(name, centre, Vector(d).normalized(), dist) for name, d in views]


def _mask_crop(mask, n=64):
    """A silhouette cropped to its box and fitted, aspect kept, into an n × n square (for comparing outlines)."""
    import numpy as np
    ys, xs = np.nonzero(mask)
    if len(xs) < 8:
        return None
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = m.shape
    k = n / max(h, w)
    out_ = np.zeros((n, n), bool)
    hh, ww = max(1, int(h * k)), max(1, int(w * k))
    yi = (np.arange(hh) / k).astype(int).clip(0, h - 1)
    xi = (np.arange(ww) / k).astype(int).clip(0, w - 1)
    oy, ox = (n - hh) // 2, (n - ww) // 2
    out_[oy:oy + hh, ox:ox + ww] = m[yi][:, xi]
    return out_


def _main_shape(mask):
    """The largest connected shape of a mask with its holes filled (a picture's shadow specks and background noise go)."""
    import numpy as np
    h, w = mask.shape
    label = np.zeros((h, w), int)
    best, best_n, k = 0, 0, 0
    for y0 in range(h):
        for x0 in range(w):
            if not mask[y0, x0] or label[y0, x0]:
                continue
            k += 1
            stack, n = [(y0, x0)], 0
            label[y0, x0] = k
            while stack:
                y, x = stack.pop()
                n += 1
                for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not label[yy, xx]:
                        label[yy, xx] = k
                        stack.append((yy, xx))
            if n > best_n:
                best, best_n = k, n
    shape = label == best
    outside = np.zeros((h, w), bool)   # fill holes: everything the border cannot reach around the shape
    stack = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < h and 0 <= x < w and not outside[y, x] and not shape[y, x]:
            outside[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return ~outside


match = None
if reference:
    # the view that matches the reference: its outline (the background is the border's colour) against the model's
    # silhouette from a ring of angles; the best one is rendered next to the picture, with the outlines overlaid
    import numpy as np
    rimg = bpy.data.images.load(os.path.abspath(reference))
    rw_, rh_ = rimg.size
    ra = np.array(rimg.pixels[:]).reshape(rh_, rw_, rimg.channels)[..., :3]
    border = np.concatenate([ra[0], ra[-1], ra[:, 0], ra[:, -1]])
    bgc = np.median(border, axis=0)
    step = max(1, max(rw_, rh_) // 160)   # a small copy is enough for an outline
    small = ra[::step, ::step]
    ref_mask = np.linalg.norm(small - bgc, axis=-1) > 0.15
    # a shadow is the background, only darker: the same hue at a lower brightness — not part of the object
    lum, bg_lum = small.mean(-1, keepdims=True), max(float(bgc.mean()), 1e-3)
    hue_off = np.linalg.norm(small / np.maximum(lum, 1e-3) - bgc / bg_lum, axis=-1)
    ref_mask &= ~((lum[..., 0] < bg_lum) & (hue_off < 0.25))
    ref_sil = _mask_crop(_main_shape(ref_mask))
    if ref_sil is not None:
        floor.hide_render = True
        engine, film = sc.render.engine, sc.render.film_transparent
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.render.film_transparent = True
        rx, ry = sc.render.resolution_x, sc.render.resolution_y
        sc.render.resolution_x = sc.render.resolution_y = 128
        best = None
        for elev in (0.1, 0.45):
            for yaw in range(-70, 71, 20):
                a_ = math.radians(yaw)
                d = Vector((math.sin(a_), -math.cos(a_), elev)).normalized()
                cam.location = centre + d * dist
                cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
                sc.render.filepath = f"{tmp}.sil.png"
                bpy.ops.render.render(write_still=True)
                si = bpy.data.images.load(sc.render.filepath)
                sil = _mask_crop(np.array(si.pixels[:]).reshape(128, 128, 4)[..., 3] > 0.5)
                bpy.data.images.remove(si)
                if sil is None:
                    continue
                iou = float((sil & ref_sil).sum()) / max(1, (sil | ref_sil).sum())
                if best is None or iou > best[0]:
                    best = (iou, yaw, elev, d, sil)
        os.remove(f"{tmp}.sil.png")
        sc.render.engine, sc.render.film_transparent = engine, film
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        floor.hide_render = False
        if best:
            match = {"iou": round(best[0], 3), "yaw_deg": best[1], "elevation": best[2]}
            shots.append(("matched", centre, best[3], dist))
            both = np.zeros((64, 64, 3))
            both[best[4] & ref_sil] = (1, 1, 1)
            both[ref_sil & ~best[4]] = (0.9, 0.2, 0.2)
            both[best[4] & ~ref_sil] = (0.25, 0.45, 1.0)
            match["_overlay"] = both
for i, c in enumerate(closeups):   # the AI's own camera: a point, the direction it looks from, the width to frame
    look = Vector(c.get("from") or (0.6, -1, 0.4)).normalized()
    size = max(float(c.get("size") or radius * 0.5), radius * 0.05)
    shots.append((f"closeup{i}", Vector(c["at"]), look, size / 2 / math.sin(fov / 2) * 1.1))
for name, target, d, dd in shots:
    cam.location = target + d * dd
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{tmp}.{name}.png"
    bpy.ops.render.render(write_still=True)
    tiles.append(bpy.data.images.load(sc.render.filepath))

# stitch the four views into one 2×2 sheet, with the reference picture on its left when there is one
half = px // 2
left = px if reference else 0
cols = 3 if closeups else 2   # close-ups take a third column: 3/4, front, close-up 1 / side, back, close-up 2
width = left + half * cols
pixels = [0.2, 0.25, 0.34, 1.0] * (width * px)
close_idx = [len(views) + i for i in range(len(closeups))] + [None, None]
order = [0, 1, close_idx[0], 2, 3, close_idx[1]] if closeups else [0, 1, 2, 3]
for slot, ti in enumerate(order):
    if ti is None or ti >= len(tiles):
        continue
    img = tiles[ti]
    src_px = list(img.pixels)
    ox, oy = left + (slot % cols) * half, (1 - slot // cols) * half   # the views left to right, top to bottom
    for row in range(half):
        s0 = row * half * 4
        d = ((oy + row) * width + ox) * 4
        pixels[d:d + half * 4] = src_px[s0:s0 + half * 4]
def _paste(img_rgb, ox, oy, box):
    """Paste an (h, w, 3) float array fitted into a box × box square at (ox, oy) of the sheet (rows bottom-up)."""
    import numpy as np
    h, w = img_rgb.shape[:2]
    k = min(box / w, box / h)
    ww, hh = max(1, int(w * k)), max(1, int(h * k))
    yi = (np.arange(hh) / k).astype(int).clip(0, h - 1)
    xi = (np.arange(ww) / k).astype(int).clip(0, w - 1)
    fit = img_rgb[yi][:, xi]
    x0, y0 = ox + (box - ww) // 2, oy + (box - hh) // 2
    for row in range(hh):
        d = ((y0 + row) * width + x0) * 4
        line = [0.0] * (ww * 4)
        line[0::4], line[1::4], line[2::4], line[3::4] = list(fit[row, :, 0]), list(fit[row, :, 1]), list(fit[row, :, 2]), [1.0] * ww
        pixels[d:d + ww * 4] = line


if reference:
    import numpy as np
    ref = bpy.data.images.load(os.path.abspath(reference))
    rgb = np.array(ref.pixels[:]).reshape(ref.size[1], ref.size[0], ref.channels)[..., :3]
    if match:   # the picture and the matched view side by side on top, their outlines overlaid below
        _paste(rgb, 0, half, half)
        mt = tiles[[n for n, *_ in shots].index("matched")]
        _paste(np.array(mt.pixels[:]).reshape(half, half, 4)[..., :3], half, half, half)
        _paste(match.pop("_overlay"), 0, 0, half)
    else:
        _paste(rgb, 0, 0, px)
sheet = bpy.data.images.new("sheet", width, px, alpha=False)
sheet.pixels = pixels
sheet.filepath_raw = out
sheet.file_format = "PNG"
sheet.save()
for name, *_ in shots:
    os.remove(f"{tmp}.{name}.png")
if match:
    with open(os.path.splitext(out)[0] + ".match.json", "w") as f:
        _json.dump(match, f)
    print(f"MeshGate views: best match with the reference {match['iou']:.2f} at {match['yaw_deg']}° round, "
          f"elevation {match['elevation']}")
print(f"MeshGate views: {out}")
