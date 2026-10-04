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

# a toon ink line is an inside-out hull the engines draw back-face culled; Cycles ignores culling, so its back faces
# are made see-through here — the render then shows the line as a game does
for m in bpy.data.materials:
    if m.name.endswith("_ink") and m.use_nodes:
        nt = m.node_tree
        mout = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
        if mout and mout.inputs["Surface"].links:
            src = mout.inputs["Surface"].links[0].from_socket
            # seen only by the camera, from the front: back faces, shadows and reflections pass through it
            mix, see = nt.nodes.new("ShaderNodeMixShader"), nt.nodes.new("ShaderNodeBsdfTransparent")
            geo, path, front = nt.nodes.new("ShaderNodeNewGeometry"), nt.nodes.new("ShaderNodeLightPath"), nt.nodes.new("ShaderNodeMath")
            front.operation = "SUBTRACT"
            front.inputs[0].default_value = 1.0
            nt.links.new(geo.outputs["Backfacing"], front.inputs[1])
            shown = nt.nodes.new("ShaderNodeMath")
            shown.operation = "MULTIPLY"
            nt.links.new(front.outputs[0], shown.inputs[0])
            nt.links.new(path.outputs["Is Camera Ray"], shown.inputs[1])
            nt.links.new(shown.outputs[0], mix.inputs[0])
            nt.links.new(see.outputs[0], mix.inputs[1])
            nt.links.new(src, mix.inputs[2])
            nt.links.new(mix.outputs[0], mout.inputs["Surface"])

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
shots = [(name, centre, Vector(d).normalized(), dist, None) for name, d in views]
# Repeatable orthographic review cameras; no perspective/elevation drift between revisions.
reference_spec = _json.loads(reference) if reference and reference.lstrip().startswith("{") else {}
if reference_spec.get("fixed_views"):
    views = [("three_quarter", (.707,-.707,0)), ("front", (0,-1,0)),
             ("side", (1,0,0)), ("back", (0,1,0))]
    frame = max(hi.z-lo.z, hi.x-lo.x, hi.y-lo.y)*1.15
    shots = [(name, centre, Vector(direction).normalized(), dist, frame) for name,direction in views]



def _mask_crop(mask, n=64, params=False):
    """A silhouette cropped to its box and fitted, aspect kept, into an n × n square (for comparing outlines).
    params=True also returns how a pixel maps into it: (y0, x0, scale, y offset, x offset)."""
    import numpy as np
    ys, xs = np.nonzero(mask)
    if len(xs) < 8:
        return (None, None) if params else None
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = m.shape
    k = n / max(h, w)
    out_ = np.zeros((n, n), bool)
    hh, ww = max(1, int(h * k)), max(1, int(w * k))
    yi = (np.arange(hh) / k).astype(int).clip(0, h - 1)
    xi = (np.arange(ww) / k).astype(int).clip(0, w - 1)
    oy, ox = (n - hh) // 2, (n - ww) // 2
    out_[oy:oy + hh, ox:ox + ww] = m[yi][:, xi]
    return (out_, (ys.min(), xs.min(), k, oy, ox)) if params else out_


def _fill_holes(mask):
    """A silhouette without holes: background that does not reach the edge is inside the figure. A picture's dark
    shorts or a shadowed shirt can match a dark backdrop and drop out of its outline; the gaps between the legs and
    between an arm and the body stay (they reach the edge)."""
    import numpy as np
    if mask is None:
        return None
    h, w = mask.shape
    outside = np.zeros_like(mask)
    stack = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < h and 0 <= x < w and not mask[y, x] and not outside[y, x]:
            outside[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return ~outside


def _part_metrics(ref_s, mod_s, rects) -> dict | None:
    """One part of the model against the same place in the picture: inside its box (a little larger, so a part the
    picture draws bigger is not cut off) — overlap, the picture's width and height against the model's, and how much
    higher (top) and further right (dx) the picture has it, in fractions of the figure's size."""
    import numpy as np
    rows = []
    for x0, x1, y0, y1 in rects:
        gx, gy = max(1, int((x1 - x0) * 0.15)), max(1, int((y1 - y0) * 0.15))
        x0, x1, y0, y1 = max(0, x0 - gx), min(64, x1 + gx), max(0, y0 - gy), min(64, y1 + gy)
        if x1 - x0 < 3 or y1 - y0 < 3:
            continue
        r, m = ref_s[y0:y1, x0:x1], mod_s[y0:y1, x0:x1]
        if r.sum() < 6 or m.sum() < 6:
            continue
        rw, mw = [int(v) for v in r.sum(1) if v > 0], [int(v) for v in m.sum(1) if v > 0]
        ry, my = np.nonzero(r.any(1))[0], np.nonzero(m.any(1))[0]
        # a part in two places (both arms): its sideways shift counts outwards, so both arms too close add up
        out_sign = (1 if (x0 + x1) / 2 >= 32 else -1) if len(rects) > 1 else 1
        rows.append({"iou": float((r & m).sum()) / max(1, (r | m).sum()),
                     "width": float(np.median(rw)) / max(1.0, float(np.median(mw))), "height": len(ry) / max(1, len(my)),
                     "top": float(ry.max() - my.max()) / 64,
                     "dx": out_sign * float(np.nonzero(r)[1].mean() - np.nonzero(m)[1].mean()) / 64})
    if not rows:
        return None
    return {k: round(sum(x[k] for x in rows) / len(rows), 3) for k in rows[0]}


def _fit_crop(mask, img, n):
    """_mask_crop for a picture: the pixels of `img` under the same crop and fit as `mask` (n × n × channels)."""
    import numpy as np
    ys, xs = np.nonzero(mask)
    if len(xs) < 8:
        return None, None
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    m, im = mask[y0:y1, x0:x1], img[y0:y1, x0:x1]
    h, w = m.shape
    k = n / max(h, w)
    hh, ww = max(1, int(h * k)), max(1, int(w * k))
    yi = (np.arange(hh) / k).astype(int).clip(0, h - 1)
    xi = (np.arange(ww) / k).astype(int).clip(0, w - 1)
    oy, ox = (n - hh) // 2, (n - ww) // 2
    om = np.zeros((n, n), bool)
    oi = np.zeros((n, n, im.shape[2]))
    om[oy:oy + hh, ox:ox + ww] = m[yi][:, xi]
    oi[oy:oy + hh, ox:ox + ww] = im[yi][:, xi]
    return om, oi


def _colour_compare(np, cam_dir, ref_img, ref_main, cells):
    """At the matched view: the model's own colours as lit (a small render) against the picture's colours at the same
    places, per palette colour (which colour a pixel is comes from a render of the palette UVs). Returns
    {cell index: {"model": sRGB, "ref": sRGB, "n": pixels}} and the mean colour difference (0…1)."""
    size = 128
    cam.location = centre + cam_dir * dist
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    keep = (sc.render.engine, sc.render.film_transparent, sc.render.resolution_x, sc.render.resolution_y,
            sc.cycles.samples, sc.cycles.filter_width, sc.view_settings.view_transform, sc.view_settings.look,
            sc.render.image_settings.file_format)
    floor.hide_render = True
    sc.render.engine, sc.render.film_transparent = "CYCLES", True
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.cycles.samples = 8
    sc.render.filepath = f"{tmp}.lit.png"
    bpy.ops.render.render(write_still=True)
    li = bpy.data.images.load(sc.render.filepath)
    lit = np.array(li.pixels[:]).reshape(size, size, 4)
    bpy.data.images.remove(li)
    # the palette cell of every pixel: the model drawn with its UVs as colour, unlit, unfiltered, linear
    idm = bpy.data.materials.new("mg_uv_id")
    idm.use_nodes = True
    nt = idm.node_tree
    for n_ in list(nt.nodes):
        nt.nodes.remove(n_)
    uvn, em, out_ = nt.nodes.new("ShaderNodeUVMap"), nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(uvn.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out_.inputs["Surface"])
    saved = []
    for o in sc.objects:
        if o.type == "MESH":
            for sl in o.material_slots:
                saved.append((sl, sl.material))
                sl.material = idm
    sc.cycles.samples, sc.cycles.filter_width = 1, 0.01
    sc.view_settings.view_transform, sc.view_settings.look = "Standard", "None"
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.filepath = f"{tmp}.uvid.exr"
    bpy.ops.render.render(write_still=True)
    ii = bpy.data.images.load(sc.render.filepath)
    uvid = np.array(ii.pixels[:]).reshape(size, size, 4)
    bpy.data.images.remove(ii)
    for sl, mat in saved:
        sl.material = mat
    bpy.data.materials.remove(idm)
    (sc.render.engine, sc.render.film_transparent, sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples,
     sc.cycles.filter_width, sc.view_settings.view_transform, sc.view_settings.look,
     sc.render.image_settings.file_format) = keep
    floor.hide_render = False
    for f_ in (f"{tmp}.lit.png", f"{tmp}.uvid.exr"):
        if os.path.exists(f_):
            os.remove(f_)
    n = 96
    alpha = lit[..., 3] > 0.5
    mm, mlit = _fit_crop(alpha, lit[..., :3], n)
    _, mid = _fit_crop(alpha, uvid[..., :2], n)
    rm, rimg = _fit_crop(ref_main, ref_img, n)
    if mm is None or rm is None:
        return {}, None
    both = mm & rm
    u = (mid[..., 0] * cells).astype(int).clip(0, cells - 1)
    v = (mid[..., 1] * cells).astype(int).clip(0, cells - 1)
    cell = u + cells * v
    out = {}
    for c in np.unique(cell[both]):
        sel = both & (cell == c)
        if sel.sum() < 6:
            continue
        out[int(c)] = {"model": [round(float(x), 3) for x in np.median(mlit[sel], axis=0)],
                       "ref": [round(float(x), 3) for x in np.median(rimg[sel], axis=0)], "n": int(sel.sum())}
    err = float(np.abs(mlit[both] - rimg[both]).mean()) if both.any() else None
    return out, err


def _main_shape(mask):
    """The figure in a mask: its largest connected shape with the big pieces right next to it, holes filled (a picture's
    shadow specks, background noise and captions go)."""
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
    # a figure is not always one piece in the mask: dark clothes on a dark background break it (shorts part the legs
    # from the body). Big pieces right above or below it, with a small gap, belong to it; a caption further down does not
    if best:
        ys, xs = np.nonzero(shape)
        y0_, y1_, x0_, x1_ = ys.min(), ys.max(), xs.min(), xs.max()
        gap = max(2, int(0.05 * (y1_ - y0_ + 1)))
        for j in range(1, k + 1):
            if j == best:
                continue
            part = label == j
            n = int(part.sum())
            if n < 0.02 * best_n:
                continue
            py, px_ = np.nonzero(part)
            overlaps = px_.max() >= x0_ and px_.min() <= x1_
            near = py.min() <= y1_ + gap and py.max() >= y0_ - gap
            if overlaps and near:
                shape |= part
                y0_, y1_ = min(y0_, py.min()), max(y1_, py.max())
    outside = np.zeros((h, w), bool)   # fill holes: everything the border cannot reach around the shape
    stack = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < h and 0 <= x < w and not outside[y, x] and not shape[y, x]:
            outside[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return ~outside


match = None
# a reference: one picture (the view that matches is searched round the front), or a character sheet —
# {"image": path, "views": ["front", "3/4front", "left", "back", "right", "3/4back"]} in the sheet's order, left to right
VIEW_YAW = {"front": 0, "3/4front": 45, "34front": 45, "left": 90, "back": 180, "right": -90, "3/4back": -135,
            "34back": -135, "3/4left": 45, "3/4right": -45}
sheet_views, parts_in = None, []
if reference and reference.lstrip().startswith("{"):
    spec = _json.loads(reference)
    reference, sheet_views = spec["image"], [str(v).lower().replace(" ", "") for v in spec.get("views") or []]
    parts_in = spec.get("sections") or []   # the model's named parts (mg.section), compared one by one
ref_front = None   # the part of the picture shown on the sheet's left (the front view of a character sheet)
if reference:
    import numpy as np
    rimg = bpy.data.images.load(os.path.abspath(reference))
    rw_, rh_ = rimg.size
    ra = np.array(rimg.pixels[:]).reshape(rh_, rw_, rimg.channels)[..., :3]
    border = np.concatenate([ra[0], ra[-1], ra[:, 0], ra[:, -1]])
    bgc = np.median(border, axis=0)
    step = max(1, max(rw_, rh_) // (160 * (len(sheet_views) if sheet_views else 1)))   # small copies suffice
    small = ra[::step, ::step]
    ref_mask = np.linalg.norm(small - bgc, axis=-1) > 0.15
    # a shadow is the background, only darker: the same hue at a lower brightness — not part of the object
    lum, bg_lum = small.mean(-1, keepdims=True), max(float(bgc.mean()), 1e-3)
    hue_off = np.linalg.norm(small / np.maximum(lum, 1e-3) - bgc / bg_lum, axis=-1)
    ref_mask &= ~((lum[..., 0] < bg_lum) & (hue_off < 0.25))
    # the views: the whole picture, or the sheet cut into its figures at the empty columns between them
    cuts = [(0, ref_mask.shape[1])]
    if sheet_views:
        occ = ref_mask.sum(0) > max(2, 0.01 * ref_mask.shape[0])
        runs, x = [], 0
        while x < len(occ):
            if occ[x]:
                x0 = x
                while x < len(occ) and occ[x:x + 3].any():
                    x += 1
                runs.append((x0, x))
            x += 1
        runs = sorted(sorted(runs, key=lambda r: -ref_mask[:, r[0]:r[1]].sum())[:len(sheet_views)])
        if len(runs) == len(sheet_views):
            cuts = runs
        else:
            print(f"MeshGate views: the sheet shows {len(runs)} figures for {len(sheet_views)} views — using it whole")
            sheet_views = None
    names = sheet_views or ["picture"]
    refs = []
    for name, (x0, x1) in zip(names, cuts):
        main = np.zeros_like(ref_mask)
        main[:, x0:x1] = _main_shape(ref_mask[:, x0:x1])
        sil_ = _fill_holes(_mask_crop(main))
        if sil_ is not None:
            refs.append((name, sil_, main, (x0, x1)))
    if refs:
        floor.hide_render = True
        engine, film = sc.render.engine, sc.render.film_transparent
        sc.render.engine = "BLENDER_WORKBENCH"
        sc.render.film_transparent = True
        rx, ry = sc.render.resolution_x, sc.render.resolution_y
        sc.render.resolution_x = sc.render.resolution_y = 128
        cache = {}

        def silhouette(yaw, elev):
            if (yaw, elev) not in cache:
                a_ = math.radians(yaw)
                d = Vector((math.sin(a_), -math.cos(a_), elev)).normalized()
                cam.location = centre + d * dist
                cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
                sc.render.filepath = f"{tmp}.sil.png"
                bpy.ops.render.render(write_still=True)
                si = bpy.data.images.load(sc.render.filepath)
                crop, prm = _mask_crop(np.array(si.pixels[:]).reshape(128, 128, 4)[..., 3] > 0.5, params=True)
                bpy.data.images.remove(si)
                rects = {}   # every named part's box as seen from here, in the cropped outline's pixels
                if parts_in and crop is not None:
                    from bpy_extras.object_utils import world_to_camera_view
                    bpy.context.view_layer.update()
                    y0_, x0_, k_, oy_, ox_ = prm
                    for sec in parts_in:
                        rs = []
                        for lo_, hi_ in sec["boxes"]:
                            uv = [world_to_camera_view(sc, cam, Vector((x, y, z))) for x in (lo_[0], hi_[0])
                                  for y in (lo_[1], hi_[1]) for z in (lo_[2], hi_[2])]
                            xs_ = [(u.x * 128 - x0_) * k_ + ox_ for u in uv]
                            ys_ = [(u.y * 128 - y0_) * k_ + oy_ for u in uv]
                            rs.append((max(0, int(min(xs_))), min(64, int(max(xs_)) + 1),
                                       max(0, int(min(ys_))), min(64, int(max(ys_)) + 1)))
                        rects[sec["name"]] = rs
                cache[(yaw, elev)] = (crop, d, rects)
            return cache[(yaw, elev)]

        def widths(ref_s, mod_s):
            """The picture's width against the model's in ten bands from the bottom (median row width: a whisker or a
            stray speck in one row does not count)."""
            out_ = []
            for k in range(10):
                r0, r1 = int(k * 6.4), int((k + 1) * 6.4)
                rw = [int(x) for x in ref_s[r0:r1].sum(1) if x > 0]
                mw_ = [int(x) for x in mod_s[r0:r1].sum(1) if x > 0]
                if len(rw) >= 2 and len(mw_) >= 2:
                    out_.append([round(k / 10, 2), round((k + 1) / 10, 2), round(float(np.median(rw)) / float(np.median(mw_)), 3)])
            return out_
        views_out = []
        for name, ref_s, main, cut in refs:
            nominal = VIEW_YAW.get(name)
            yaws = range(-70, 71, 20) if nominal is None else (nominal - 15, nominal, nominal + 15)   # a sheet's angle is known
            best = None
            for elev in (0.1, 0.45):
                for yaw in yaws:
                    sil, d, rects = silhouette(((yaw + 180) % 360) - 180, elev)
                    if sil is None:
                        continue
                    iou = float((sil & ref_s).sum()) / max(1, (sil | ref_s).sum())
                    if best is None or iou > best[0]:
                        best = (iou, ((yaw + 180) % 360) - 180, elev, d, sil, rects)
            if best:
                # widths and depths are measured square to the view (its exact angle on the sheet): at another angle a
                # width mixes the model's breadth and depth
                exact = silhouette(nominal, best[2])[0] if nominal is not None else best[4]
                parts_v = {}
                for sec_name, rs in best[5].items():
                    pm = _part_metrics(ref_s, best[4], rs)
                    if pm:
                        parts_v[sec_name] = pm
                views_out.append({"name": name, "iou": round(best[0], 3), "yaw_deg": best[1], "elevation": best[2],
                                  "bands": widths(ref_s, exact if exact is not None else best[4]), "_best": best,
                                  "_ref": (ref_s, main, cut), "_parts": parts_v})
        if os.path.exists(f"{tmp}.sil.png"):
            os.remove(f"{tmp}.sil.png")
        sc.render.engine, sc.render.film_transparent = engine, film
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        floor.hide_render = False
        if views_out:
            prim = next((v for v in views_out if v["name"] in ("front", "picture")), views_out[0])
            best, (ref_sil, main, cut) = prim["_best"], prim["_ref"]
            match = {"iou": round(sum(v["iou"] for v in views_out) / len(views_out), 3), "yaw_deg": prim["yaw_deg"],
                     "elevation": prim["elevation"], "bands": prim["bands"]}
            if sheet_views:
                match["views"] = [{k: v[k] for k in ("name", "iou", "yaw_deg", "elevation", "bands")} for v in views_out]
                # every view of the sheet with its outlines laid over the model's (white both, red only the picture,
                # blue only the model), side by side: <sheet>.views.png
                strip = np.zeros((64, 64 * len(views_out), 3))
                for i, v in enumerate(views_out):
                    r_, m_ = v["_ref"][0], v["_best"][4]
                    tile = np.zeros((64, 64, 3))
                    tile[m_ & r_] = (1, 1, 1)
                    tile[r_ & ~m_] = (0.9, 0.2, 0.2)
                    tile[m_ & ~r_] = (0.25, 0.45, 1.0)
                    strip[:, 64 * i:64 * (i + 1)] = tile
                big = np.repeat(np.repeat(strip, 4, 0), 4, 1)
                vimg = bpy.data.images.new("views", big.shape[1], big.shape[0], alpha=False)
                vimg.pixels = np.concatenate([big, np.ones(big.shape[:2] + (1,))], axis=2).ravel().tolist()
                vimg.filepath_raw = os.path.splitext(out)[0] + ".views.png"
                vimg.file_format = "PNG"
                vimg.save()
                # the widths across (front and back) and the depths (the sides), each averaged over its views
                def mean_bands(vs):
                    acc = {}
                    for v in vs:
                        for b in v["bands"]:
                            acc.setdefault((b[0], b[1]), []).append(b[2])
                    return [[a_, b_, round(sum(r) / len(r), 3)] for (a_, b_), r in sorted(acc.items())]
                across = [v for v in views_out if v["name"] in ("front", "back")]
                sides = [v for v in views_out if v["name"] in ("left", "right")]
                if across:
                    match["bands"] = mean_bands(across)
                if sides:
                    match["depth_bands"] = mean_bands(sides)
            if parts_in:   # every named part on its own, over all the views that show it
                summary = []

                def avg(rows_, k):
                    return round(sum(r_[k] for r_ in rows_) / len(rows_), 3) if rows_ else None
                for sec in parts_in:
                    per = [(v, v["_parts"][sec["name"]]) for v in views_out if sec["name"] in v["_parts"]]
                    if not per:
                        continue
                    allp = [pm for _, pm in per]
                    across_ = [pm for v, pm in per if abs(v["yaw_deg"]) < 25 or abs(v["yaw_deg"]) > 155]
                    sides_ = [pm for v, pm in per if 60 < abs(v["yaw_deg"]) < 120]
                    front_ = [pm for v, pm in per if abs(v["yaw_deg"]) < 25]
                    summary.append({"name": sec["name"], "iou": avg(allp, "iou"), "width": avg(across_, "width"),
                                    "depth": avg(sides_, "width"), "height": avg(allp, "height"), "top": avg(allp, "top"),
                                    "dx": avg(front_, "dx"), "views": len(per)})
                match["sections"] = sorted(summary, key=lambda x_: x_["iou"])
                # every part up close in the front view: its outline over the picture's, one tile each (the order of
                # match["sections"]) — <sheet>.parts.png, for people and the AI review
                pv = prim
                tiles_ = []
                for sm in match["sections"]:
                    rs = pv["_best"][5].get(sm["name"]) or []
                    if not rs:
                        continue
                    x0, x1, y0, y1 = rs[0]
                    gx, gy = max(2, int((x1 - x0) * 0.3)), max(2, int((y1 - y0) * 0.3))
                    x0, x1, y0, y1 = max(0, x0 - gx), min(64, x1 + gx), max(0, y0 - gy), min(64, y1 + gy)
                    r_, m_ = pv["_ref"][0][y0:y1, x0:x1], pv["_best"][4][y0:y1, x0:x1]
                    if r_.size == 0:
                        continue
                    tl = np.zeros(r_.shape + (3,))
                    tl[m_ & r_] = (1, 1, 1)
                    tl[r_ & ~m_] = (0.9, 0.2, 0.2)
                    tl[m_ & ~r_] = (0.25, 0.45, 1.0)
                    kk = 64 / max(tl.shape[:2])
                    yi = (np.arange(int(tl.shape[0] * kk)) / kk).astype(int).clip(0, tl.shape[0] - 1)
                    xi = (np.arange(int(tl.shape[1] * kk)) / kk).astype(int).clip(0, tl.shape[1] - 1)
                    t64 = np.zeros((64, 64, 3))
                    zz = tl[yi][:, xi]
                    t64[:zz.shape[0], :zz.shape[1]] = zz
                    tiles_.append(t64)
                if tiles_:
                    pstrip = np.concatenate(tiles_, axis=1)
                    pbig = np.repeat(np.repeat(pstrip, 3, 0), 3, 1)
                    pimg = bpy.data.images.new("parts", pbig.shape[1], pbig.shape[0], alpha=False)
                    pimg.pixels = np.concatenate([pbig, np.ones(pbig.shape[:2] + (1,))], axis=2).ravel().tolist()
                    pimg.filepath_raw = os.path.splitext(out)[0] + ".parts.png"
                    pimg.file_format = "PNG"
                    pimg.save()
            shots.append(("matched", centre, best[3], dist, None))
            both = np.zeros((64, 64, 3))
            both[best[4] & ref_sil] = (1, 1, 1)
            both[ref_sil & ~best[4]] = (0.9, 0.2, 0.2)
            both[best[4] & ~ref_sil] = (0.25, 0.45, 1.0)
            match["_overlay"] = both
            x0, x1 = cut
            ref_front = ra[:, x0 * step:min(rw_, x1 * step)]
            try:   # the colours at the matched view, per palette colour (what a colour fit corrects)
                cols, err = _colour_compare(np, best[3], small, main, 8)
                match["colours"], match["colour_error"] = cols, (round(err, 4) if err is not None else None)
            except Exception as exc:  # noqa: BLE001 — the outline match still stands without it
                print(f"MeshGate views: colour compare skipped ({exc})")
for i, c in enumerate(closeups):   # the AI's own camera: a point, the direction it looks from, the width to frame
    look = Vector(c.get("from") or (0.6, -1, 0.4)).normalized()
    size = max(float(c.get("size") or radius * 0.5), radius * 0.05)
    shots.append((f"closeup{i}", Vector(c["at"]), look, size / 2 / math.sin(fov / 2) * 1.1,
                  size*1.1 if c.get("ortho") else None))
for name, target, d, dd, ortho in shots:
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
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
    if ref_front is not None:
        rgb = ref_front
    else:
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
    for v in match.get("views") or []:
        print(f"MeshGate views:   {v['name']:9} {v['iou']:.2f} at {v['yaw_deg']}°")
print(f"MeshGate views: {out}")
