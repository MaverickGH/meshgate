"""Every Zombie Cats asset in a row, one row per style (stylized, low-poly, realistic), studio light, orthographic.

    blender -b -P scripts/render/zombie_cats_lineup.py -- out/packs docs/img/zc-styles-lineup.png [samples]
"""
import bpy, sys, math, os
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
packs, out = a[0], a[1]; samples = int(a[2]) if len(a) > 2 else 96
# the 3.2 m street lamp would cover its own column; it is in the diorama renders
ORDER = ["zombie_cat", "tombstone_cat", "toxic_can", "dead_tree", "fence_broken", "cardboard_barricade", "scratch_post_ruin",
         "bones_pile"]
STYLES = ["stylized", "lowpoly", "realistic"]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
row_gap = 4.2
LABELS = {"stylized": "Stylized", "lowpoly": "Low-poly", "realistic": "Realistic"}
loaded = {}   # (style, name) → (top objects, min x, max x)
for style in STYLES:
    for name in ORDER:
        path = os.path.join(packs, f"zombie_cats_{style}", f"zc_{name}.glb")
        if not os.path.exists(path):        # planned: a "coming soon" placeholder goes here after the columns are measured
            loaded[(style, name)] = None
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        tops = [o for o in new if o.parent not in new]
        for t in tops:
            t.rotation_euler.z += math.radians(-25)
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
        loaded[(style, name)] = (tops, min(p.x for p in pts), max(p.x for p in pts), max(p.z for p in pts))
width = {n: max(loaded[(s_, n)][2] - loaded[(s_, n)][1] for s_ in STYLES if loaded[(s_, n)]) for n in ORDER}
height = {n: max(loaded[(s_, n)][3] for s_ in STYLES if loaded[(s_, n)]) for n in ORDER}
ghost = bpy.data.materials.new("coming soon"); ghost.use_nodes = True
gb = ghost.node_tree.nodes["Principled BSDF"]
gb.inputs["Base Color"].default_value = (.55, .6, .7, 1)
(gb.inputs.get("Emission Color") or gb.inputs["Emission"]).default_value = (.55, .6, .7, 1)
gb.inputs["Emission Strength"].default_value = .6
x = 0.0
for name in ORDER:   # one column per asset, as wide as its widest style: the rows line up
    for r, style in enumerate(STYLES):
        if loaded[(style, name)] is None:     # outline of the missing asset, sized like its other styles
            y = (len(STYLES) - 1 - r) * row_gap
            gw, gh = max(width[name] * .8, .75), max(height[name], .75)      # big enough to hold its label
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x + width[name] / 2, y, gh / 2))
            box = bpy.context.active_object
            box.scale = (gw, .35, gh)
            mod = box.modifiers.new("outline", "WIREFRAME"); mod.thickness, mod.use_even_offset = .012, False
            box.data.materials.append(ghost)
            bpy.ops.object.text_add(location=(x + width[name] / 2, y - .3, gh / 2))
            tx = bpy.context.active_object
            tx.data.body, tx.data.size, tx.data.align_x, tx.data.align_y = "coming\nsoon", .16, "CENTER", "CENTER"
            tx.rotation_euler = (math.radians(58), 0, 0)
            tx.data.materials.append(ghost)
            continue
        tops, lo, hi, top = loaded[(style, name)]
        for t in tops:
            t.location.x += x + width[name] / 2 - (lo + hi) / 2
            t.location.y += (len(STYLES) - 1 - r) * row_gap   # stylized at the back, realistic in front
    x += width[name] + 0.6
for r, style in enumerate(STYLES):   # row labels on the floor, in front of each row
    bpy.ops.object.text_add(location=(-0.2, (len(STYLES) - 1 - r) * row_gap - 1.25, 0.01))
    txt = bpy.context.active_object
    txt.data.body = LABELS[style]; txt.data.size = 0.55; txt.data.extrude = 0.01
    tm = bpy.data.materials.new("label"); tm.use_nodes = True
    tb = tm.node_tree.nodes["Principled BSDF"]; tb.inputs["Base Color"].default_value = (0.75, 0.78, 0.9, 1)
    txt.data.materials.append(tm)
for m in bpy.data.materials:   # glowing parts glow, not blow out, in a studio shot
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED" and n.inputs["Emission Strength"].default_value > 0.6:
                n.inputs["Emission Strength"].default_value = 0.6
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
fm = bpy.data.materials.new("floor"); fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]; fb.inputs["Base Color"].default_value = (0.022, 0.024, 0.03, 1); fb.inputs["Roughness"].default_value = 0.6
bpy.context.active_object.data.materials.append(fm)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.012, 0.013, 0.02, 1)
def light(n, e, col, loc, size):
    l = bpy.data.objects.new(n, bpy.data.lights.new(n, "AREA")); sc.collection.objects.link(l)
    l.data.energy, l.data.color, l.data.size = e, col, size
    l.location = Vector(loc); l.rotation_euler = (Vector((x / 2, row_gap, 0.6)) - l.location).to_track_quat("-Z", "Y").to_euler()
light("key", 9000, (1.0, 0.85, 0.7), (x * 0.25, -9, 11), 10)
light("rim", 6000, (0.5, 0.65, 1.0), (x * 0.8, 14, 7), 10)
light("fill", 1200, (0.8, 0.85, 1.0), (x + 6, -4, 3), 8)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = x * 1.02
tgt = Vector((x / 2 - 0.3, row_gap * 0.95, 0.9))
cam.location = tgt + Vector((0, -1, 0.62)).normalized() * 40
cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 2400, 1250
for vt in ("AgX", "Filmic"):
    try: sc.view_settings.view_transform = vt; break
    except TypeError: pass
sc.render.filepath = out; bpy.ops.render.render(write_still=True)
print("LINEUP", out)
