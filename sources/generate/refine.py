"""MeshGate refine — bring any generated or downloaded mesh to the asset contract, once per quality tier.

    blender -b --factory-startup -P sources/generate/refine.py -- --src raw.glb --name robot --out-dir out/gen/robot
            [--tiers mobile-low,mobile-mid,mobile-high,pc] [--targets web,unity,godot,unreal] [--size 1.2]
            [--turn 0] [--detail 1.0] [--collision none|box|convex] [--preview]

Neural generators (TripoSR, Meshy, Tripo, TRELLIS, Hunyuan3D…) return one dense, arbitrarily scaled mesh with vertex
colours or a messy texture atlas. For every tier this script: normalises it (meters, grounded, centred, front -Y),
cleans it (merged doubles, loose parts, outward normals), decimates a copy to the tier's share of the triangle budget,
unwraps fresh UVs, bakes base colour and a normal map from the dense source onto the light copy (Cycles), builds one
PBR material, exports with the MeshGate exporter and validates against the tier budget. The richest tier becomes the
canonical `<name>.glb` with engine variants. Writes `<name>.report.json` in the same shape as run_generated.py.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import bpy
except ImportError:
    print("Run inside Blender: blender -b --factory-startup -P sources/generate/refine.py -- --src raw.glb ...")
    sys.exit(2)

import argparse
import json
import math
import os
import tempfile
import traceback

import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "blender"))
from meshgate_blender import checks, compat, export, finish, modeling, tools  # noqa: E402
from meshgate_blender.modeling import TIERS  # noqa: E402

# Share of each tier's triangle budget a single generated prop gets by default: neural meshes carry little real detail
# past ~60k triangles, and a scene holds many props. --detail scales these.
SHARE = {"mobile-low": 0.5, "mobile-mid": 0.4, "mobile-high": 0.35, "pc": 0.25}
MAX_BAKE = 2048


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="Bring a generated mesh to the MeshGate contract per quality tier")
    ap.add_argument("--src", required=True, help=".glb/.gltf/.obj/.fbx/.ply/.stl")
    ap.add_argument("--name", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tiers", default=",".join(TIERS))
    ap.add_argument("--targets", default="web,unity,godot,unreal")
    ap.add_argument("--size", type=float, default=0.0, help="largest dimension in meters (0 = keep a plausible size, else 1 m)")
    ap.add_argument("--turn", type=float, default=0.0, help="degrees to turn around the up axis so the front faces -Y")
    ap.add_argument("--detail", type=float, default=1.0, help="multiplier for the per-tier triangle share")
    ap.add_argument("--collision", default="none", choices=["none", "box", "convex"])
    ap.add_argument("--no-upright", action="store_true", help="keep the tilt of the source (no automatic standing up)")
    ap.add_argument("--vertex-srgb", action="store_true", help="vertex colours hold sRGB values (TripoSR), not linear")
    ap.add_argument("--gpu", action="store_true", help="bake on the GPU (Metal, OptiX, CUDA, HIP) instead of the CPU")
    ap.add_argument("--cpu", action="store_true", help="force the CPU even with --gpu (the fallback after a crash)")
    ap.add_argument("--colors", default="texture", choices=["texture", "vertex"], help="baked textures or vertex colours")
    ap.add_argument("--caps", default="", help="your triangle limits: mobile-low=300,pc=2000 (below the tier defaults)")
    ap.add_argument("--texture", type=int, default=0, help="baked texture size in px (tiers still cap it; above PC → master.glb)")
    ap.add_argument("--topology", default="tri", choices=["tri", "quad"], help="quad: QuadriFlow remesh per tier instead of decimation")
    ap.add_argument("--pbr", action="store_true", help="also bake ambient occlusion into the glTF occlusion slot")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--split", action="store_true", help="every separate thing its own object (to move in an engine)")
    ap.add_argument("--edits", default="", help="JSON file of hand changes to the split parts (Studio's part editor)")
    return ap.parse_args(argv)


# ----------------------------------------------------------------------------
# import and normalise
# ----------------------------------------------------------------------------

def import_any(path: str):
    ext = os.path.splitext(path)[1].lower()
    ops = bpy.ops
    if ext in (".glb", ".gltf"):
        ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        (ops.wm.obj_import if hasattr(ops.wm, "obj_import") else ops.import_scene.obj)(filepath=path)
    elif ext == ".fbx":
        ops.import_scene.fbx(filepath=path)
    elif ext == ".ply":
        (ops.wm.ply_import if hasattr(ops.wm, "ply_import") else ops.import_mesh.ply)(filepath=path)
    elif ext == ".stl":
        (ops.wm.stl_import if hasattr(ops.wm, "stl_import") else ops.import_mesh.stl)(filepath=path)
    else:
        raise ValueError(f"unsupported mesh format {ext} — use GLB, glTF, OBJ, FBX, PLY or STL")


def select_only(objs, active=None):
    bpy.context.view_layer.update()   # removed objects leave stale entries until the view layer updates
    for o in bpy.context.view_layer.objects:
        if o is not None:
            o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)


def merged_source(turn_deg: float):
    """All imported meshes → one object with transforms applied; everything else removed."""
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == "MESH"]
    if not meshes:
        raise ValueError("the file has no mesh")
    # a rigged model stands in its rest pose (the modelled shape), not in whatever frame of a clip the file opens on
    for arm in [o for o in scene.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    for o in meshes:   # keep the evaluated shape (rest pose, modifiers), drop the rig
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        for m in list(o.modifiers):
            select_only([o])
            try:
                with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o]):
                    bpy.ops.object.modifier_apply(modifier=m.name)
            except RuntimeError:
                o.modifiers.remove(m)
    for o in [o for o in scene.objects if o.type != "MESH"]:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    select_only(meshes)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    src = bpy.context.view_layer.objects.active
    src.name = "mg_source"
    src.data.name = "mg_source"
    if src.data.shape_keys:
        src.shape_key_clear()
    if turn_deg:
        src.data.transform(Matrix.Rotation(math.radians(turn_deg), 4, "Z"))
    return src


def bounds(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _hull_area(pts) -> float:
    """Area of the 2D convex hull of (x, y) points (monotone chain)."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return 0.0

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return abs(sum(hull[i][0] * hull[i - 1][1] - hull[i - 1][0] * hull[i][1] for i in range(len(hull)))) / 2


def upright(src, limit: float = 40.0) -> float:
    """Undo camera tilt: single-image generators assume a level camera, so a photo taken from above comes out
    leaning. An object standing on the floor rests on a broad flat base; leaning, it touches the floor with an edge.
    Search tilts around X and Y (coarse, then fine) for the largest support area — the convex hull of the points in
    the lowest 3 % of the height, relative to the object's footprint. Returns the correction in degrees."""
    import random
    verts = [v.co.copy() for v in src.data.vertices]
    if len(verts) > 5000:
        verts = random.Random(1).sample(verts, 5000)

    def support(rx: float, ry: float) -> float:
        m = Matrix.Rotation(math.radians(ry), 3, "Y") @ Matrix.Rotation(math.radians(rx), 3, "X")
        pts = [m @ v for v in verts]
        zs = [p.z for p in pts]
        lo, hi = min(zs), max(zs)
        slab = lo + (hi - lo) * 0.03
        base = [(round(p.x, 5), round(p.y, 5)) for p in pts if p.z <= slab]
        foot = _hull_area([(round(p.x, 4), round(p.y, 4)) for p in pts[::7]])
        return _hull_area(base) / foot if foot > 0 else 0.0

    level = support(0, 0)
    coarse = [(support(i * 5.0, j * 5.0), i * 5.0, j * 5.0) for i in range(-8, 9) for j in range(-8, 9)
              if math.hypot(i, j) * 5.0 <= limit]
    top = max(coarse)
    # A flat base gives the same support over a few degrees around upright: take the centre of that plateau
    # (the mean of all near-best fine tilts), not whichever edge the search meets first.
    fine = [(support(top[1] + i, top[2] + j), top[1] + i, top[2] + j) for i in range(-6, 7) for j in range(-6, 7)]
    peak = max(f[0] for f in fine)
    near = [f for f in fine if f[0] >= peak * 0.98]
    best = (peak, sum(f[1] for f in near) / len(near), sum(f[2] for f in near) / len(near))
    _, rx, ry = best
    if math.hypot(rx, ry) < 2.0 or best[0] < level * 1.25:   # no clearly better base: leave it as generated
        return 0.0
    src.data.transform(Matrix.Rotation(math.radians(ry), 4, "Y") @ Matrix.Rotation(math.radians(rx), 4, "X"))
    return math.hypot(rx, ry)


def normalise(src, size: float, stand_up: bool = True) -> list:
    notes = []
    if stand_up:
        tilt = upright(src)
        if tilt:
            notes.append(f"stood upright (the camera tilt had leaned it {tilt:.0f}°; --no-upright keeps it)")
    lo, hi = bounds(src)
    biggest = max(hi - lo)
    if biggest <= 0:
        raise ValueError("the mesh is flat or empty")
    k = 1.0
    if size > 0:
        k = size / biggest
    elif not 0.02 <= biggest <= 200:
        k = 1.0 / biggest
        notes.append(f"scaled to 1 m (the file was {biggest:.3g} units across; pass --size for the real size)")
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    src.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation(-centre))
    if abs(k - 1) > 1e-6 and size > 0:
        notes.append(f"scaled ×{k:.3g} to {size:g} m")
    return notes


def clean(src) -> list:
    notes = []
    lo, hi = bounds(src)
    size = max(hi - lo)
    bm = bmesh.new()
    bm.from_mesh(src.data)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=size * 1e-5)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    # tiny floating islands (marching-cubes specks): drop islands under 0.2 % of the faces
    bm.faces.ensure_lookup_table()
    seen, islands = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, island = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            island.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        islands.append(island)
    limit = max(8, len(bm.faces) * 0.002)
    specks = [f for isl in islands if len(isl) < limit for f in isl]
    if specks and len(specks) < len(bm.faces) * 0.2:
        bmesh.ops.delete(bm, geom=specks, context="FACES")
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        notes.append(f"removed {len(islands) - sum(1 for i in islands if len(i) >= limit)} floating specks")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(src.data)
    bm.free()
    if n0 - len(src.data.vertices) > 0:
        notes.append(f"merged/removed {n0 - len(src.data.vertices):,} duplicate or loose vertices")
    for p in src.data.polygons:
        p.use_smooth = True
    return notes


def colour_source(src, vertex_srgb: bool = False) -> str:
    """Make sure the dense source shows its colour in Base Color, so a DIFFUSE/COLOR bake picks it up."""
    me = src.data
    attrs = getattr(me, "color_attributes", None)
    colour_attr = attrs[0].name if attrs and len(attrs) else (me.vertex_colors[0].name if getattr(me, "vertex_colors", None) and len(me.vertex_colors) else None)
    has_texture = False
    for m in me.materials:
        b = compat.principled(m) if m else None
        if b and b.inputs["Base Color"].is_linked:
            node = b.inputs["Base Color"].links[0].from_node
            has_texture |= node.type == "TEX_IMAGE"
    if has_texture:
        return "texture"
    mat = bpy.data.materials.new("mg_source_colour")
    mat.use_nodes = True
    b = compat.principled(mat)
    if colour_attr:
        node = mat.node_tree.nodes.new("ShaderNodeVertexColor")
        node.layer_name = colour_attr
        out = node.outputs["Color"]
        if vertex_srgb:   # the generator wrote picture (sRGB) values where glTF expects linear ones: decode them
            gamma = mat.node_tree.nodes.new("ShaderNodeGamma")
            gamma.inputs["Gamma"].default_value = 2.2
            mat.node_tree.links.new(out, gamma.inputs["Color"])
            out = gamma.outputs["Color"]
        mat.node_tree.links.new(out, b.inputs["Base Color"])
        kind = "vertex colours" + (" (sRGB)" if vertex_srgb else "")
    else:
        old = next((compat.principled(m) for m in me.materials if m and compat.principled(m)), None)
        if old:
            b.inputs["Base Color"].default_value = old.inputs["Base Color"].default_value
        kind = "material colour"
    me.materials.clear()
    me.materials.append(mat)
    return kind


# ----------------------------------------------------------------------------
# per tier
# ----------------------------------------------------------------------------

def texture_plan(budget: dict, tier: str, want: int | None = None) -> tuple[int, int]:
    """(colour px, normal px or 0) within the tier's texture size and memory (RGBA × 4/3 for mipmaps).
    want: the texture size asked for (--texture); the tier's limit still caps it."""
    colour = min(budget["max_texture"], want or MAX_BAKE)
    mb = lambda px: px * px * 4 * 4 / 3 / 2 ** 20   # noqa: E731
    if tier == "mobile-low":
        return colour, 0
    for normal in ([colour] if tier == "pc" else []) + [colour // 2, colour // 4]:
        if mb(colour) + mb(normal) <= budget["max_texture_mb"]:
            return colour, normal
    return colour, 0


def setup_cycles(use_gpu: bool = False):
    """CPU by default: these bakes are small, a GPU spends longer compiling kernels than baking (M4 Pro: 14 s on
    the CPU against ~40 s on Metal), and a Metal bake in Blender 5.2 has crashed without a word."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 8
    if not use_gpu:
        scene.cycles.device = "CPU"
        return "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = backend
            except TypeError:
                continue
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type != "CPU"]
            if gpus:
                for d in prefs.devices:
                    d.use = True
                scene.cycles.device = "GPU"
                return backend
    except Exception:  # noqa: BLE001
        pass
    scene.cycles.device = "CPU"
    return "CPU"


def new_image(name: str, px: int, non_color: bool):
    img = bpy.data.images.new(name, px, px, alpha=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    img.generated_color = (0.5, 0.5, 1.0, 1.0) if non_color else (0.5, 0.5, 0.5, 1.0)
    return img


def pack(img, tmp: str):
    path = os.path.join(tmp, f"{img.name}.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.source = "FILE"
    img.reload()
    img.pack()
    img.filepath_raw = f"//textures/{img.name}.png"


def _base_colour(me):
    """(image, pixels H×W×4 as numpy) of the texture in Base Color, or (None, None) — vertex colours or none."""
    import numpy as np
    for mat in me.materials:
        if not mat or not mat.use_nodes:
            continue
        b = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b and b.inputs["Base Color"].is_linked:
            node = b.inputs["Base Color"].links[0].from_node
            if node.type == "TEX_IMAGE" and node.image and node.image.size[0]:
                img = node.image
                px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
                img.pixels.foreach_get(px)
                return img, px.reshape(img.size[1], img.size[0], 4)
    return None, None


def _uv_triangles(me):
    """Every face of the mesh as UV triangles (n × 3 × 2, numpy)."""
    import numpy as np
    uv = me.uv_layers.active.data if me.uv_layers else None
    tris = []
    if uv is None:
        return np.zeros((0, 3, 2))
    for p in me.polygons:
        li = list(p.loop_indices)
        for k in range(1, len(li) - 1):
            tris.append([uv[li[0]].uv[:], uv[li[k]].uv[:], uv[li[k + 1]].uv[:]])
    return np.array(tris, dtype=np.float64).reshape(-1, 3, 2)


def _uv_mask(me, w: int, h: int, grow: int = 2):
    """Which texture pixels the mesh's UV triangles cover (grown by a few pixels over the bake margin)."""
    import numpy as np
    mask = np.zeros((h, w), dtype=bool)
    for t in _uv_triangles(me):
        pts = t * (w, h)
        x0, y0 = np.floor(pts.min(0)).astype(int) - 1
        x1, y1 = np.ceil(pts.max(0)).astype(int) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
        if x1 <= x0 or y1 <= y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1) + .5, np.arange(y0, y1) + .5)
        (ax, ay), (bx, by), (cx, cy) = pts
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        inside = (l1 >= -.02) & (l2 >= -.02) & (1 - l1 - l2 >= -.02)
        mask[y0:y1, x0:x1] |= inside
    for _ in range(grow):
        g = mask.copy()
        g[1:] |= mask[:-1]; g[:-1] |= mask[1:]; g[:, 1:] |= mask[:, :-1]; g[:, :-1] |= mask[:, 1:]
        mask = g
    return mask


def part_colour_name(me):
    """A part named by the colour it shows most: sampled from its baked texture at its faces (or its vertex colours)."""
    import numpy as np
    img, px = _base_colour(me)
    samples, weights = [], []
    if img is not None:
        h, w = px.shape[:2]
        for t, p in zip(_uv_triangles(me), (q for q in me.polygons for _ in range(len(q.vertices) - 2))):
            u, v = t.mean(0)
            samples.append(px[min(h - 1, max(0, int(v * h))), min(w - 1, max(0, int(u * w))), :3])
            weights.append(p.area)
    elif getattr(me, "color_attributes", None) and len(me.color_attributes):
        data = me.color_attributes[0].data
        for p in me.polygons:
            samples.append(np.mean([data[i].color[:3] for i in p.loop_indices], axis=0) ** (1 / 2.2))
            weights.append(p.area)
    if not samples:
        return None
    rgb = np.average(np.array(samples), axis=0, weights=np.array(weights) + 1e-9)
    return modeling.colour_word(rgb)


def recolour_baked(obj, colour: str, tmp: str):
    """Repaint a part of a baked model: the texture under its faces takes the new colour and keeps its own light and
    detail (each pixel keeps its brightness against the part's average); vertex colours likewise. colour = "#rrggbb"."""
    import numpy as np
    if not (isinstance(colour, str) and len(colour) == 7 and colour.startswith("#")):
        return
    rgb = np.array([int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    lum_w = np.array([.2126, .7152, .0722])
    me = obj.data
    img, px = _base_colour(me)
    if img is not None:
        h, w = px.shape[:2]
        mask = _uv_mask(me, w, h)
        region = px[mask][:, :3]
        if not len(region):
            return
        lum = region @ lum_w
        px[mask, :3] = np.clip(rgb[None, :] * (lum / max(float(lum.mean()), 1e-4))[:, None], 0, 1)
        img.pixels.foreach_set(px.ravel())
        img.update()
        name = img.filepath_raw
        pack(img, tmp)          # saved and packed again, so the exporter writes the new pixels
        img.filepath_raw = name
    elif getattr(me, "color_attributes", None) and len(me.color_attributes):
        data = me.color_attributes[0].data
        cols = np.array([d.color[:] for d in data])
        lum = cols[:, :3] @ lum_w
        lin = rgb ** 2.2
        cols[:, :3] = np.clip(lin[None, :] * (lum / max(float(lum.mean()), 1e-4))[:, None], 0, 1)
        for d, c in zip(data, cols):
            d.color = c


def bake(kind: str, src, low, node, size: float, to_vertices: bool = False):
    if node is not None:
        nodes = low.data.materials[0].node_tree.nodes
        for n in nodes:
            n.select = False
        node.select = True
        nodes.active = node
    select_only([src, low], active=low)
    kwargs, _ = compat.operator_kwargs(
        bpy.ops.object.bake, type=kind, pass_filter={"COLOR"} if kind == "DIFFUSE" else set(),
        use_selected_to_active=True, cage_extrusion=size * 0.01, max_ray_distance=size * 0.03, margin=8,
        normal_space="TANGENT", use_clear=True, target="VERTEX_COLORS" if to_vertices else "IMAGE_TEXTURES")
    if kind != "DIFFUSE":
        kwargs.pop("pass_filter", None)
    bpy.ops.object.bake(**kwargs)


def quad_remesh(obj, target_tris: int) -> bool:
    """Clean quad topology at the tier's density (QuadriFlow, built into Blender). False when it cannot (non-manifold)."""
    select_only([obj])
    before = len(obj.data.polygons)
    try:
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
            res = bpy.ops.object.quadriflow_remesh(target_faces=max(60, target_tris // 2), use_mesh_symmetry=False,
                                                   use_preserve_sharp=False, use_preserve_boundary=False,
                                                   smooth_normals=False, seed=0)
    except Exception:  # noqa: BLE001
        return False
    polys = obj.data.polygons
    quads = sum(1 for p in polys if len(p.vertices) == 4)
    return "FINISHED" in res and len(polys) != before and quads >= .9 * len(polys)   # it really remeshed


def _islands(me) -> list:
    """Vertex indices of each loose piece of a mesh."""
    parent = list(range(len(me.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in me.edges:
        a_, b_ = find(e.vertices[0]), find(e.vertices[1])
        if a_ != b_:
            parent[a_] = b_
    out: dict = {}
    for v in me.vertices:
        out.setdefault(find(v.index), []).append(v.index)
    return list(out.values())


def _box(me) -> tuple:
    if not me.vertices:
        return (0.0, 0.0, 0.0)
    return tuple(max(v.co[c] for v in me.vertices) - min(v.co[c] for v in me.vertices) for c in range(3))


def quad_remesh_parts(obj, target_tris: int):
    """Quads for a mesh made of separate pieces (a pile of crates, a lid and its flaps, eyes and buttons): QuadriFlow on
    each piece with its share of the triangles — as many as it has now, scaled to the target, so small detailed pieces
    (eyes, knobs) keep their detail and nothing can fuse neighbours or starve thin flaps. A piece QuadriFlow would deform
    (its size changes by more than 12 % or its surface by more than 20 %) keeps decimated triangles paired into quads.
    Returns the share of quads, or None for a single piece (or too many to do one by one)."""
    me = obj.data
    groups = _islands(me)
    if not 2 <= len(groups) <= 150:
        return None
    tris_of = {}
    vert_group = {}
    for gi, vs in enumerate(groups):
        for i in vs:
            vert_group[i] = gi
    for p in me.polygons:
        gi = vert_group[p.vertices[0]]
        tris_of[gi] = tris_of.get(gi, 0) + len(p.vertices) - 2
    total = sum(tris_of.values())
    small = sum(1 for t_ in tris_of.values() if t_ * target_tris / max(1, total) < 24)   # pieces held at 24 triangles
    ratio = min(1.0, max(0.0, target_tris - 24 * small) / max(1, total) * (.92 if target_tris < total else 1))   # QuadriFlow overshoots a little
    pieces = []
    for gi, vs in enumerate(groups):
        keep = set(vs)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context="VERTS")
        pm = bpy.data.meshes.new(f"{obj.name}_piece")
        bm.to_mesh(pm)
        bm.free()
        for mat in me.materials:
            pm.materials.append(mat)
        po = bpy.data.objects.new(pm.name, pm)
        bpy.context.collection.objects.link(po)
        po.matrix_world = obj.matrix_world.copy()
        tris0 = sum(len(p.vertices) - 2 for p in pm.polygons)
        share = max(24, int(tris0 * ratio))
        box0, area0, backup = _box(pm), sum(p.area for p in pm.polygons), pm.copy()
        ok = quad_remesh(po, share)
        if ok:
            box1, area1 = _box(po.data), sum(p.area for p in po.data.polygons)
            ok = all(abs(a_ - b_) <= .12 * max(box0) for a_, b_ in zip(box0, box1)) and abs(area1 - area0) <= .2 * area0
        if not ok:   # decimate gently, then pair triangles into quads where the shape allows
            old = po.data
            po.data = backup
            bpy.data.meshes.remove(old)
            if tris0 > share:
                mod = po.modifiers.new("decimate", "DECIMATE")
                mod.decimate_type, mod.ratio, mod.use_collapse_triangulate = "COLLAPSE", share / tris0, True
                with bpy.context.temp_override(object=po, active_object=po, selected_objects=[po]):
                    bpy.ops.object.modifier_apply(modifier=mod.name)
            pair_quads(po)
        else:
            bpy.data.meshes.remove(backup)
        pieces.append(po)
    bm = bmesh.new()
    for po in pieces:   # from_mesh adds to what is there: the pieces back into one mesh
        bm.from_mesh(po.data)
    bm.to_mesh(me)
    bm.free()
    me.update()
    for po in pieces:
        pm = po.data
        bpy.data.objects.remove(po, do_unlink=True)
        bpy.data.meshes.remove(pm)
    polys = me.polygons
    return sum(1 for p in polys if len(p.vertices) == 4) / max(len(polys), 1)


def voxel_quads(obj, target_tris: int) -> float:
    """All-quad topology at the tier's density when QuadriFlow declines: a voxel remesh (like ZBrush DynaMesh) sized
    from the surface area; the details voxels smooth away come back through the normal map baked from the source."""
    area = sum(p.area for p in obj.data.polygons)
    mod = obj.modifiers.new("voxel quads", "REMESH")
    mod.mode, mod.adaptivity = "VOXEL", 0.0
    mod.voxel_size = max(1.15 * (area / max(target_tris / 2, 60)) ** .5, 1e-4)   # 1.15: voxels land ~30 % denser
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    polys = obj.data.polygons
    return sum(1 for p in polys if len(p.vertices) == 4) / max(len(polys), 1)


def pair_quads(obj) -> float:
    """Pair triangles into quads wherever the shape allows (after decimation). Returns the share of quads."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.join_triangles(bm, faces=bm.faces, angle_face_threshold=math.radians(40),
                             angle_shape_threshold=math.radians(40), cmp_seam=False, cmp_sharp=False,
                             cmp_uvs=False, cmp_vcols=False, cmp_materials=True)
    share = sum(1 for f in bm.faces if len(f.verts) == 4) / max(len(bm.faces), 1)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return share


def build_tier(src, name: str, tier: str, budget: dict, detail: float, tmp: str, size: float,
               colors: str = "texture", cap: int | None = None, texture: int = 0, topology: str = "tri",
               pbr: bool = False) -> dict:
    """Decimated, unwrapped, baked copy of the source for one tier. Returns info for the report.
    colors="vertex": the colour is baked into the vertices of the light copy (no textures, no normal map).
    cap: your own triangle limit for this tier, below the default share."""
    src_tris = sum(len(p.vertices) - 2 for p in src.data.polygons)
    target = max(200, min(src_tris, int(budget["max_tris"] * SHARE[tier] * detail)))
    if cap:
        target = max(12, min(target, cap))
    low = src.copy()
    low.data = src.data.copy()
    bpy.context.collection.objects.link(low)
    low.name = low.data.name = name
    low.hide_render = False
    parts_share = quad_remesh_parts(low, target) if topology == "quad" else None
    quad = parts_share is not None or (topology == "quad" and quad_remesh(low, target))
    quad_share = parts_share if parts_share is not None else 1.0 if quad else 0.0
    if topology == "quad" and not quad:   # QuadriFlow declined (it refuses many scanned or generated meshes)
        quad_share = voxel_quads(low, target)
        quad = quad_share > .9
    if src_tris > target and not quad:
        mod = low.modifiers.new("decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = target / src_tris
        mod.use_collapse_triangulate = True
        with bpy.context.temp_override(object=low, active_object=low, selected_objects=[low]):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    if topology == "quad" and not quad:   # neither worked: pair what decimation left
        quad_share = pair_quads(low)
    for layer in list(low.data.uv_layers):
        low.data.uv_layers.remove(layer)
    attrs = getattr(low.data, "color_attributes", None)
    while attrs is not None and len(attrs):
        attrs.remove(attrs[0])
    low.data.uv_layers.new(name="UVMap")
    select_only([low])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")

    colour_px, normal_px = texture_plan(budget, tier, texture or None) if colors != "vertex" else (0, 0)
    mat = bpy.data.materials.new(f"{name}_{tier}")
    mat.use_nodes = True
    mat.use_backface_culling = True
    nt = mat.node_tree
    b = compat.principled(mat)
    b.inputs["Roughness"].default_value = 0.7
    b.inputs["Metallic"].default_value = 0.0
    low.data.materials.clear()
    low.data.materials.append(mat)
    if colors == "vertex":
        attr = low.data.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        low.data.color_attributes.active_color = attr
        if hasattr(low.data.color_attributes, "render_color_index"):
            low.data.color_attributes.render_color_index = low.data.color_attributes.active_color_index
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
        bake("DIFFUSE", src, low, None, size, to_vertices=True)
        for p in low.data.polygons:
            p.use_smooth = True
        return {"low": low, "target": target, "colour_px": 0, "normal_px": 0}
    c_img = new_image(f"{name}_{tier}_basecolor", colour_px, False)
    c_node = nt.nodes.new("ShaderNodeTexImage")
    c_node.image = c_img
    bake("DIFFUSE", src, low, c_node, size)
    pack(c_img, tmp)
    nt.links.new(c_node.outputs["Color"], b.inputs["Base Color"])
    if normal_px:
        n_img = new_image(f"{name}_{tier}_normal", normal_px, True)
        n_node = nt.nodes.new("ShaderNodeTexImage")
        n_node.image = n_img
        bake("NORMAL", src, low, n_node, size)
        pack(n_img, tmp)
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(n_node.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], b.inputs["Normal"])
    if pbr:   # ambient occlusion from the dense source, into the glTF occlusion slot
        ao_img = new_image(f"{name}_{tier}_occlusion", max(256, colour_px // 2), True)
        ao_node = nt.nodes.new("ShaderNodeTexImage")
        ao_node.image = ao_img
        bake("AO", src, low, ao_node, size)
        pack(ao_img, tmp)
        finish._occlusion(nt, ao_node.outputs["Color"])
    nt.nodes.active = c_node   # Workbench previews and the Blender viewport show the active image: the colour
    for p in low.data.polygons:
        p.use_smooth = True
    return {"low": low, "target": target, "colour_px": colour_px, "normal_px": normal_px, "quads": quad_share}


def render_preview(path: str):
    sys.path.insert(0, HERE)
    import run_generated
    bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
    return run_generated.render_preview(path)


def main() -> int:
    args = _args()
    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)
    name = "".join(c if c.isascii() and (c.isalnum() or c in "_-") else "_" for c in args.name).strip("_").lower() or "asset"
    tiers = sorted({t.strip() for t in args.tiers.split(",") if t.strip() in TIERS}, key=TIERS.index)
    canonical = tiers[-1]
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    table = export.load_profiles()["profiles"]
    export.FBX_TRIANGLES = args.topology == "tri"
    report = {"name": name, "canonical": canonical, "tiers": {}, "files": [], "ok": False, "problems": [], "advice": [],
              "preview": None, "blend": None, "engine": "mesh", "source": os.path.basename(args.src)}
    report_path = os.path.join(out, f"{name}.report.json")
    try:
        edits = json.load(open(args.edits, encoding="utf-8")) if args.edits else {}
    except (OSError, ValueError):
        edits = {}
    caps = {k: int(v) for k, v in (item.split("=") for item in args.caps.split(",") if "=" in item)}

    def done(code: int) -> int:
        report["ok"] = code == 0 and not report["problems"]
        json.dump(report, open(report_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"MESHGATE_REPORT {report_path}")
        return code

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups next to the results
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    try:
        import_any(os.path.abspath(args.src))
        src = merged_source(args.turn)
        notes = normalise(src, args.size, not args.no_upright) + clean(src)
        colour = colour_source(src, args.vertex_srgb)
    except Exception as exc:  # noqa: BLE001
        report["problems"].append(f"could not read the mesh: {exc}")
        traceback.print_exc()
        return done(1)
    lo, hi = bounds(src)
    size = max(hi - lo)
    src_tris = sum(len(p.vertices) - 2 for p in src.data.polygons)
    device = setup_cycles(args.gpu and not args.cpu)
    report["source_tris"] = src_tris
    report["colour_from"] = colour
    print(f"  source: {src_tris:,} tris, {[round(v, 3) for v in (hi - lo)]} m, colour from {colour}, baking on {device}", flush=True)
    for n in notes:
        print(f"      · {n}", flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        for tier in tiers:   # lightest first; the canonical (richest) one stays in the scene at the end
            budget = table[tier]["asset"]
            src.hide_render = False   # Cycles bakes only from objects visible to render
            try:
                info = build_tier(src, name, tier, budget, args.detail, tmp, size, args.colors, caps.get(tier),
                                  args.texture, args.topology, args.pbr)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                report["problems"].append(f"tier {tier}: {type(exc).__name__}: {exc}")
                return done(1)
            low = info["low"]
            src.hide_render = True    # …and the exporter skips objects hidden from render
            parts = modeling.split_parts(low, name_of=part_colour_name) if args.split else []
            if parts:   # the separate things as objects of their own under one root, to move in an engine
                bpy.data.objects.remove(low, do_unlink=True)   # first, so the root takes the asset's name
                root = bpy.data.objects.new(name, None)
                bpy.context.collection.objects.link(root)
                for p_ in parts:
                    mwp = p_.matrix_world.copy()
                    p_.parent = root
                    p_.matrix_world = mwp
                low = root
                if tier == canonical:
                    notes.append(f"split into parts: {len(parts)} objects, each with its origin at its base")
                if edits:
                    got = modeling.apply_edits(parts, edits, lambda o, c: recolour_baked(o, c, tmp))
                    if tier == canonical:
                        notes += got
            select_only([low, *parts])
            if tier == canonical:
                if args.collision != "none":
                    tools.add_collision(bpy.context, parts or [low], args.collision.upper())
                glb = os.path.join(out, f"{name}.glb")
                res = export.export_asset(bpy.context, glb, targets=targets, fbx=bool({"unity", "unreal"} & set(targets)),
                                          image_format="JPEG", validate=True, strict=True)
                report["files"] += [os.path.basename(f) for f in res.files]
                report["problems"] += [f"{r.get('file')}: {e}" for r in res.reports[1:] for e in r.get("errors", [])]
            else:
                glb = os.path.join(out, f"{name}.{tier}.glb")
                export.export_tier(bpy.context, glb, tier, image_format="JPEG")   # baked photo-like textures: JPEG on every tier
                report["files"].append(os.path.basename(glb))
            rep = export.validate_file(glb, profile=tier)
            bud = rep.get("budget") or {}
            entry = {"file": os.path.basename(glb), "tris": rep.get("triangles", 0),
                     "max_tris": next((x["limit"] for x in bud.get("items", []) if x["name"] == "tris"), None),
                     "within_budget": bool(bud.get("ok")), "draw_calls": rep.get("draw_calls"), "materials": rep.get("materials"),
                     "max_texture": rep.get("max_texture"), "size_mb": rep.get("size_mb"), "errors": rep.get("errors", []),
                     "warnings": rep.get("warnings", []), "fits": rep.get("fits", []), "dims_m": rep.get("dims_m"), "clips": [],
                     "notes": notes if tier == canonical else [], "textures": {"basecolor": info["colour_px"], "normal": info["normal_px"]},
                     "cap": caps.get(tier), "colors": args.colors, "topology": f"quad {round(info['quads'] * 100)} %" if info.get("quads") else "tri"}
            report["tiers"][tier] = entry
            for e in entry["errors"] + entry["warnings"]:
                report["problems"].append(f"tier {tier}: {e}")
            print(f"  {'✓' if entry['within_budget'] and not entry['errors'] else '✗'} {tier:12} {entry['tris']:>7,} tris / "
                  f"{entry['max_tris'] or 0:,}  {entry['file']}  "
                  + (f"textures {info['colour_px']}" + (f" + normal {info['normal_px']}" if info["normal_px"] else "")
                     if info["colour_px"] else "vertex colours, no textures")
                  + (f"  (your cap {caps[tier]:,})" if tier in caps else "")
                  + (f"  quads {round(info['quads'] * 100)} %" if info.get("quads") else ""), flush=True)
            if tier != canonical:
                meshes_ = parts or [low]
                for img in {n.image for o in meshes_ for m in o.data.materials[:1] for n in m.node_tree.nodes
                            if getattr(n, "image", None)}:
                    bpy.data.images.remove(img)
                for o in [*parts, low]:
                    bpy.data.objects.remove(o, do_unlink=True)
        pc_max = table["pc"]["asset"]["max_texture"] if "pc" in table else 4096
        if args.texture > pc_max and args.colors != "vertex" and "pc" in tiers:
            # above the PC tier's limit: one more PC copy baked at the full size, for renders and film
            src.hide_render = False
            info = build_tier(src, f"{name}_master", "pc", {**table["pc"]["asset"], "max_texture": args.texture,
                                                            "max_texture_mb": 4096}, args.detail, tmp, size, args.colors,
                              None, args.texture, args.topology, args.pbr)
            src.hide_render = True
            master = os.path.join(out, f"{name}.master.glb")
            select_only([info["low"]])
            export.export_asset(bpy.context, master, selection=True, validate=False, image_format="JPEG")
            report["files"].append(os.path.basename(master))
            report["master"] = {"file": os.path.basename(master), "texture": args.texture}
            print(f"  ✓ master       {args.texture} px textures, beyond the PC tier  {os.path.basename(master)}", flush=True)
            bpy.data.objects.remove(info["low"], do_unlink=True)
        bpy.data.objects.remove(src, do_unlink=True)
        blend = os.path.join(out, f"{name}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True, copy=True)
        report["blend"] = os.path.basename(blend)
        if args.preview:
            png = render_preview(os.path.join(out, f"{name}.png"))
            report["preview"] = os.path.basename(png) if png else None
    return done(0)


if __name__ == "__main__":
    code = main()
    if code:
        sys.exit(code)
