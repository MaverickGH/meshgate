"""Animated GIFs for the documentation pages, rendered in Blender 3.5+ (Eevee) from MeshGate's own assets.

    python3 sources/generate/make_style_packs.py                                  # once: out/packs/zombie_cats_*
    blender -b -t 8 --python scripts/render_doc_gifs.py -- [--only tiers,styles,fix,lods,collision] [--preview]
    python3 scripts/render_doc_gifs.py [--only …]                                 # frames → docs/img/*.gif

tiers      docs/quality-tiers.md   the zombie cat at every tier, wireframe and triangle count, on a turntable
styles     docs/generation.md      one cat tombstone switching stylized → low-poly → realistic
fix        sources/blender         Check → Fix all: a crate in centimetres, lying down and floating snaps into place
lods       targets/unity           Unity LOD Group: the camera pulls back and the model drops to lighter levels
collision  targets/unreal, godot   balls bounce off the convex collision hull that UCX_ / -convcolonly carry
"""

import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "doc-gifs"
PACKS = ROOT / "out" / "packs"
FPS = {"tiers": 16, "styles": 16, "fix": 16, "lods": 16, "collision": 20}
FILES = {"tiers": "quality-tiers", "styles": "styles-switch", "fix": "blender-fix", "lods": "unity-lods",
         "collision": "engine-collision"}   # docs/img/<file>.gif
GIFS = list(FPS)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    only = next((argv[i + 1] for i, a in enumerate(argv) if a == "--only" and i + 1 < len(argv)), ",".join(GIFS))
    return [g for g in only.split(",") if g in GIFS], "--preview" in argv


def encode(names):
    """Frames → GIF (plain Python, needs ffmpeg)."""
    for name in names:
        frames = OUT / name
        out = ROOT / "docs" / "img" / f"{FILES[name]}.gif"
        subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS[name]), "-i",
                               str(frames / "frame-%03d.png"), "-filter_complex",
                               "[0:v] split [a][b];[a] palettegen=max_colors=160:stats_mode=diff [p];"
                               "[b][p] paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle", "-loop", "0", str(out)])
        print(f"{out.relative_to(ROOT)}  {out.stat().st_size / 2 ** 20:.1f} MB")


try:
    import bpy
    from mathutils import Matrix, Vector
except ImportError:          # plain Python: make the GIFs from rendered frames
    encode(args()[0])
    sys.exit(0)

FONT = next((p for p in ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
                         "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if Path(p).exists()), None)
ORANGE, TEAL, RED, GREEN = (1, .45, .16), (0, .85, .75), (.9, .28, .24), (.3, .82, .45)


# ----------------------------------------------------------------------------- studio

def reset(w=960, h=480):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "BLENDER_EEVEE"
    e = s.eevee
    e.taa_render_samples = 48
    for attr, val in (("use_gtao", True), ("gtao_distance", 1.5), ("use_bloom", True), ("bloom_intensity", .04),
                      ("use_soft_shadows", True), ("shadow_cube_size", "1024"), ("shadow_cascade_size", "2048")):
        if hasattr(e, attr):
            setattr(e, attr, val)
    s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = w, h, 100
    s.render.image_settings.file_format = "PNG"
    s.view_settings.view_transform = "Filmic"
    s.view_settings.look = "Medium High Contrast"
    s.view_settings.exposure = .2
    world = bpy.data.worlds.new("studio")
    s.world = world
    world.color = (.008, .011, .015)
    return s


def mat(name, color, metal=0.0, rough=.45, glow=None, power=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if glow:
        (b.inputs.get("Emission Color") or b.inputs["Emission"]).default_value = (*glow, 1)
        b.inputs["Emission Strength"].default_value = power
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = "BLEND"
        if hasattr(m, "shadow_method"):
            m.shadow_method = "NONE"
    return m


def stage(floor_z=0.0):
    """Floor and backdrop in the hero's colours, a warm key, a cool rim and a soft front fill."""
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, floor_z))
    bpy.context.object.data.materials.append(mat("floor", (.02, .028, .034), .1, .72))
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 9, 0), rotation=(math.pi / 2, 0, 0))
    bpy.context.object.data.materials.append(mat("backdrop", (.008, .013, .018), 0, .9))
    area("key", (-4, -5, 6), (1, .9, .8), 900, 4, (0, 0, .5))
    area("rim", (4.5, 3.5, 4), (.55, .75, 1), 700, 3, (0, 0, .6))
    area("fill", (0, -7, 1.5), (.9, .95, 1), 220, 6, (0, 0, .6))


def area(name, loc, color, power, size, target):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.color, d.shape, d.size = power, color, "DISK", size
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()
    return o


def camera(loc, target, ortho=None, lens=50):
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.object
    c.rotation_euler = (Vector(target) - c.location).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        c.data.type, c.data.ortho_scale = "ORTHO", ortho
    else:
        c.data.lens = lens
    bpy.context.scene.camera = c
    return c


def text(body, loc, size=.2, color=(.92, .93, .95), glow=1.2, align="CENTER", parent=None, rot=(math.pi / 2, 0, 0)):
    cu = bpy.data.curves.new("label", "FONT")
    cu.body, cu.size, cu.align_x = body, size, align
    if FONT:
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    o = bpy.data.objects.new("label", cu)
    bpy.context.scene.collection.objects.link(o)
    o.location, o.rotation_euler = loc, rot
    o.data.materials.append(mat("label", color, 0, .5, color, glow))
    if parent:
        o.parent = parent
    return o


def load(path):
    """Import a GLB under one empty at the origin (footprint centred, standing on z = 0). Returns (empty, meshes)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    meshes = [o for o in new if o.type == "MESH"]
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    holder = bpy.data.objects.new(Path(path).stem, None)
    bpy.context.scene.collection.objects.link(holder)
    for o in new:
        if o.parent is None:
            o.parent = holder
            o.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    return holder, meshes, hi - lo


def wire(meshes, color=ORANGE, thickness=.004, alpha=.75):
    """A glowing wireframe on top of each mesh, the way the tier's triangles really are."""
    m = mat("wire", color, 0, .5, color, 2.2, alpha)
    for o in meshes:
        d = o.copy()
        bpy.context.scene.collection.objects.link(d)
        d.parent, d.matrix_parent_inverse = o.parent, o.matrix_parent_inverse.copy()
        mod = d.modifiers.new("wire", "WIREFRAME")
        mod.thickness, mod.use_replace, mod.use_even_offset = thickness, True, False
        for slot in d.material_slots:
            slot.link, slot.material = "OBJECT", m
        if not d.material_slots:
            d.data.materials.append(m)


def show(obj, on):
    for o in [obj] + list(obj.children_recursive):
        o.hide_render = not on


def render(name, frames, step, preview):
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    s = bpy.context.scene
    todo = [frames // 2] if preview else range(frames)
    for f in todo:
        s.frame_set(f)
        step(f / frames, f)
        s.render.filepath = str(folder / (f"preview.png" if preview else f"frame-{f:03d}.png"))
        bpy.ops.render.render(write_still=True)
    print(f"MESHGATE_GIF {name}: {len(todo)} frame(s) in {folder.relative_to(ROOT)}", flush=True)


def smooth(u):
    u = min(1, max(0, u))
    return u * u * (3 - 2 * u)


def tier_tris(pack, asset):
    idx = json.loads((PACKS / pack / "index.json").read_text())
    a = next(x for x in idx["assets"] if x["file"] == f"{asset}.glb")
    return {"pc": a["tris"], **{t: e["tris"] for t, e in a["tiers"].items()}}


TIERS = [("pc", "PC", ""), ("mobile-high", "mobile high", ".mobile-high"), ("mobile-mid", "mobile mid", ".mobile-mid"),
         ("mobile-low", "mobile low", ".mobile-low")]


# ----------------------------------------------------------------------------- the GIFs

def gif_tiers(preview):
    reset(1040, 440)
    stage()
    pack, asset = "zombie_cats_stylized", "zc_zombie_cat"
    tris = tier_tris(pack, asset)
    holders = []
    plinth = mat("pedestal", (.03, .045, .05), .8, .3)
    top = .42
    for i, (tier, label, suffix) in enumerate(TIERS):
        x = (i - 1.5) * 1.35
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, top / 2))
        ped = bpy.context.object
        ped.scale = (1.05, .9, top)
        ped.data.materials.append(plinth)
        h, meshes, size = load(PACKS / pack / f"{asset}{suffix}.glb")
        h.location = (x, 0, top)
        wire(meshes, thickness=.0028, alpha=.55)
        holders.append(h)
        text(label, (x, -.46, .22), .13, rot=(math.pi / 2, 0, 0))
        text(f"{tris[tier]:,} tris", (x, -.46, .06), .1, ORANGE, 1.6, rot=(math.pi / 2, 0, 0))
    camera((0, -9, 2.6), (0, 0, .8), ortho=5.9)

    def step(t, f):
        for h in holders:
            h.rotation_euler.z = math.tau * t - .5
    render("tiers", 56, step, preview)


def gif_styles(preview):
    reset(820, 480)
    stage()
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.75, depth=.12, location=(0, 0, .06))
    bpy.context.object.data.materials.append(mat("pedestal", (.03, .045, .05), .9, .28))
    styles = [("stylized", "Stylized"), ("lowpoly", "Low-poly"), ("realistic", "Realistic")]
    items = []
    for key, label in styles:
        h, meshes, size = load(PACKS / f"zombie_cats_{key}" / "zc_tombstone_cat.glb")
        h.location.z = .12
        lab = text(label, (0, -.8, .02), .12, rot=(math.radians(78), 0, 0))
        items.append((h, lab))
    camera((0, -6.8, 2.1), (0, 0, .8), lens=64)
    n = len(items)

    def step(t, f):
        k = min(n - 1, int(t * n))
        local = t * n - k
        for i, (h, lab) in enumerate(items):
            on = i == k
            show(h, on)
            lab.hide_render = not on
            h.rotation_euler.z = .6 * math.sin(math.tau * local) - .2    # sway, always facing the camera
            grow = smooth(local / .12) * (1 - smooth((local - .88) / .12))
            h.scale = (grow,) * 3 if on else (0, 0, 0)
    render("styles", 72, step, preview)


def gif_fix(preview):
    reset(960, 480)
    stage()
    h, meshes, size = load(ROOT / "samples" / "meshgate_demo.glb")
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.05, location=(0, 0, 0))
    dot = bpy.context.object
    dot.data.materials.append(mat("origin", ORANGE, 0, .4, ORANGE, 4))
    issues = [("units: centimetres (scale 100)", "scale 1, meters"), ("lying on its side (Z-up)", "upright, Y-up"),
              ("floating 0.8 m", "standing on the ground"), ("origin off to the side", "origin at the bottom centre")]
    rows = []
    for i, (bad, good) in enumerate(issues):
        y = 1.55 - i * .36
        b = text(bad, (1.7, 0, y), .13, RED, 1.4, align="LEFT")
        g = text(good, (1.7, 0, y), .13, GREEN, 1.4, align="LEFT")
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.045, location=(1.58, 0, y + .045))
        d = bpy.context.object
        dm = mat("status", RED, 0, .4, RED, 3)
        d.data.materials.append(dm)
        rows.append((b, g, dm))
    title = text("Check  →  Fix all", (1.7, 0, 2.0), .17, align="LEFT")
    camera((.9, -9, 1.7), (.9, 0, 1.0), ortho=6.2)
    h.location.x = -.55
    windows = [(.14, .26), (.30, .42), (.46, .6), (.62, .72)]      # when each fix plays, in loop time

    def step(t, f):
        u = [smooth((t - a) / (b - a)) for a, b in windows]
        s = 1.8 - .8 * u[0]
        h.scale = (s, s, s)
        h.rotation_euler = (0, math.pi / 2 * (1 - u[1]), .3 * u[1])
        drop = .8 * (1 - u[2])
        if 0 < u[2] < 1:
            drop += .05 * math.sin(math.pi * u[2]) * (1 - u[2])
        h.location.z = 0
        bpy.context.view_layer.update()                  # stand on (or float above) the floor, never sink into it
        low = min((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box)
        h.location.z = drop - low
        off = Vector((.7, 0, .45)) * (1 - u[3])
        front = -(size.y * s / 2 + .08)                  # drawn just in front of the base, so it is never hidden
        dot.location = Vector((h.location.x, front, drop)) + off      # the crate's base is at height drop
        for i, (b, g, dm) in enumerate(rows):
            done = u[i] >= .98
            b.hide_render, g.hide_render = done, not done
            dm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*(GREEN if done else RED), 1)
            em = dm.node_tree.nodes["Principled BSDF"]
            (em.inputs.get("Emission Color") or em.inputs["Emission"]).default_value = (*(GREEN if done else RED), 1)
    render("fix", 72, step, preview)


def gif_lods(preview):
    reset(720, 384)
    stage()
    pack, asset = "zombie_cats_realistic", "zc_toxic_can"
    tris = tier_tris(pack, asset)
    levels = [("pc", "LOD0", ""), ("mobile-mid", "LOD1", ".mobile-mid"), ("mobile-low", "LOD2", ".mobile-low")]
    cam = camera((0, -2.6, 1.0), (0, 0, .5), lens=50)
    items = []
    for i, (tier, lod, suffix) in enumerate(levels):
        h, meshes, size = load(PACKS / pack / f"{asset}{suffix}.glb")
        wire(meshes, thickness=.0035, alpha=.6)
        lab = text(f"{lod}  ·  {tris[tier]:,} tris", (-.5, .19, -1.5), .045, ORANGE, 1.8, align="LEFT", parent=cam, rot=(0, 0, 0))
        items.append((h, lab))
    text("Unity LOD Group", (-.5, .235, -1.5), .05, parent=cam, align="LEFT", rot=(0, 0, 0))

    def step(t, f):
        d = .5 - .5 * math.cos(math.tau * t)            # 0 → 1 → 0: pull back, come closer
        dist = 3.5 + 8.5 * d
        cam.location = (0, -dist, .5 + dist * .19)
        cam.rotation_euler = (Vector((0, 0, .5)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        k = 0 if dist < 5.6 else (1 if dist < 9.0 else 2)
        for i, (h, lab) in enumerate(items):
            show(h, i == k)
            lab.hide_render = i != k
            h.rotation_euler.z = .6 * t
    render("lods", 60, step, preview)


def gif_collision(preview):
    import bmesh
    reset(960, 480)
    stage()
    h, meshes, size = load(PACKS / "zombie_cats_stylized" / "zc_cardboard_barricade.glb")
    h.rotation_euler.z = math.radians(-8)
    bpy.context.view_layer.update()
    bm = bmesh.new()                                    # one convex hull around the prop: what UCX_ / -convcolonly carry
    for o in meshes:
        for v in o.data.vertices:
            bm.verts.new(o.matrix_world @ v.co)
    res = bmesh.ops.convex_hull(bm, input=bm.verts)
    loose = {v for v in res["geom_interior"] + res["geom_unused"] if isinstance(v, bmesh.types.BMVert)}
    bmesh.ops.delete(bm, geom=list(loose), context="VERTS")
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(6), verts=bm.verts, edges=bm.edges)
    hull_me = bpy.data.meshes.new("UCX_barricade")
    bm.to_mesh(hull_me)
    bm.free()
    hull = bpy.data.objects.new("UCX_barricade", hull_me)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mat("hull", TEAL, 0, .3, TEAL, .6, .14))
    hw = hull.copy()
    bpy.context.scene.collection.objects.link(hw)
    mod = hw.modifiers.new("wire", "WIREFRAME")
    mod.thickness, mod.use_replace, mod.use_even_offset = .008, True, False
    hw.material_slots[0].link, hw.material_slots[0].material = "OBJECT", mat("hullwire", TEAL, 0, .4, TEAL, 3, .9)
    bpy.ops.rigidbody.world_add()
    s = bpy.context.scene
    s.rigidbody_world.point_cache.frame_start, s.rigidbody_world.point_cache.frame_end = 0, 80
    for obj, kind, shape in ((hull, "PASSIVE", "CONVEX_HULL"),):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.rigidbody.object_add(type=kind)
        obj.rigid_body.collision_shape = shape
        obj.select_set(False)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    ground = bpy.context.object
    ground.hide_render = True
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    import random
    random.seed(3)
    ball_mat = mat("ball", ORANGE, .2, .3, ORANGE, .8)
    for i in range(9):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.1, location=(random.uniform(-.8, .8), random.uniform(-.2, .2),
                                                                  2.2 + i * .35))
        b = bpy.context.object
        bpy.ops.object.shade_smooth()
        b.data.materials.append(ball_mat)
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        b.rigid_body.restitution, b.rigid_body.friction, b.rigid_body.collision_shape = .55, .4, "SPHERE"
    hull.rigid_body.restitution = .6
    text("convex collision:  UCX_ for Unreal  ·  -convcolonly for Godot", (0, 1.2, 1.72), .12, TEAL, 1.5)
    camera((0, -7.5, 2.6), (0, 0, .7), ortho=4.6)

    def step(t, f):
        pass
    render("collision", 80, step, preview)


if __name__ == "__main__":
    names, preview = args()
    for name in names:
        globals()[f"gif_{name}"](preview)
