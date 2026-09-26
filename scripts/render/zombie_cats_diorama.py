"""Beauty render of a Zombie Cats style pack as a tabletop diorama: Cycles, night, warm lantern pools, one camera for
every style. The street is laid out like zc_diorama in make_pack_zombie_cats.py.

    blender -b -P scripts/render/zombie_cats_diorama.py -- out/packs/zombie_cats_realistic docs/img/zc-realistic.png \
            [--samples 128] [--res 1600x1000]
"""
import bpy, sys, math, os
from mathutils import Vector
argv = sys.argv[sys.argv.index("--")+1:]
src, out = argv[0], argv[1]
samples = int(argv[argv.index("--samples")+1]) if "--samples" in argv else 96
res = argv[argv.index("--res")+1] if "--res" in argv else "1600x1000"
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---- the diorama: a GLB, or a folder of style assets placed like the original street
LAYOUT = [("zc_street_lamp", (-2.2, -1.1), 0.0), ("zc_street_lamp", (2.4, -2.9), math.pi), ("zc_dead_tree", (-2.5, 2.6), 0.4),
          ("zc_tombstone_cat", (0.6, 3.0), 0.1), ("zc_tombstone_cat", (1.6, 2.7), -0.2), ("zc_tombstone_cat", (2.6, 3.1), 0.25),
          ("zc_cardboard_barricade", (1.8, -3.1), 0.2), ("zc_toxic_can", (-0.6, 1.6), 0.0), ("zc_bones_pile", (0.3, 1.3), 0.0),
          ("zc_scratch_post_ruin", (-1.8, 0.9), 0.6), ("zc_zombie_cat", (-0.3, -1.0), 0.3), ("zc_zombie_cat", (1.0, -0.6), -0.4),
          ("zc_zombie_cat", (0.4, 2.2), math.pi)]
for ix in range(4):
    for iy in range(4):
        LAYOUT.append(("zc_road_tile" if iy == 1 else "zc_ground_tile", (-3 + ix * 2, -3 + iy * 2), 0.0))
for i, x in enumerate((-3, -1, 1, 3)):
    LAYOUT.append(("zc_fence_broken", (x, 3.9), 0.0))
    if i != 2:
        LAYOUT.append(("zc_fence_broken", (x, -3.9), math.pi))
for y in (1, 3):
    LAYOUT.append(("zc_fence_broken", (-3.9, y), math.pi / 2))

def import_root(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    return [o for o in new if o.parent is None or o.parent not in new], new

if os.path.isdir(src):
    lib = bpy.data.collections.new("lib")   # sources, hidden; the street uses collection instances
    present = {n for n, _, _ in LAYOUT if os.path.exists(os.path.join(src, n + ".glb"))}   # planned assets are left out
    LAYOUT = [item for item in LAYOUT if item[0] in present]
    for name in sorted(present):
        tops, new = import_root(os.path.join(src, name + ".glb"))
        coll = bpy.data.collections.new(name)
        for o in new:
            for c in o.users_collection:
                c.objects.unlink(o)
            coll.objects.link(o)
        for t in tops:
            t.location = (0, 0, 0)
    for name, (x, y), rz in LAYOUT:
        inst = bpy.data.objects.new(name + "_i", None)
        inst.instance_type = "COLLECTION"; inst.instance_collection = bpy.data.collections[name]
        inst.location = (x, y, 0)
        inst.rotation_euler.z = rz
        sc.collection.objects.link(inst)
else:
    import_root(src)
bpy.context.view_layer.update()
# glowing parts carry the dusk: lamps and goo read from across the street
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED" and n.inputs["Emission Strength"].default_value > 0:
                n.inputs["Emission Strength"].default_value = min(max(n.inputs["Emission Strength"].default_value * 1.2, 1.2), 1.6)

# ---- practical lights: warm pools under the lanterns, a green glow over the toxic can
def point(loc, energy, color, radius=0.12):
    l = bpy.data.objects.new("pt", bpy.data.lights.new("pt", "POINT")); sc.collection.objects.link(l)
    l.data.energy, l.data.color, l.data.shadow_soft_size = energy, color, radius
    l.location = loc
if os.path.isdir(src):
    lamp = bpy.data.collections["zc_street_lamp"]
    vs = [o.matrix_world @ v.co for o in lamp.all_objects if o.type == "MESH" for v in o.data.vertices]
    top = max(v.z for v in vs)
    head = [v for v in vs if v.z > top * 0.8]
    hx, hy = sum(v.x for v in head) / len(head), sum(v.y for v in head) / len(head)
    for name, (x, y), rz in LAYOUT:
        if name == "zc_street_lamp":
            c, s_ = math.cos(rz), math.sin(rz)
            point((x + hx * c - hy * s_, y + hx * s_ + hy * c, top * 0.82), 140, (1.0, 0.66, 0.32))
        if name == "zc_toxic_can":
            point((x, y, 1.2), 45, (0.35, 1.0, 0.2), 0.3)

# ---- a tabletop plinth under the street: the diorama floats in the dark like a game-board miniature
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.26))
base = bpy.context.active_object; base.scale = (8.7, 8.7, 0.5)
bev = base.modifiers.new("b", "BEVEL"); bev.width = 0.06; bev.segments = 3
bm = bpy.data.materials.new("plinth"); bm.use_nodes = True
bb = bm.node_tree.nodes["Principled BSDF"]; bb.inputs["Base Color"].default_value = (0.035, 0.022, 0.016, 1); bb.inputs["Roughness"].default_value = 0.45
base.data.materials.append(bm)

# ---- light: dusk sky + low warm sun + cool fill
w = bpy.data.worlds.new("night"); sc.world = w; w.use_nodes = True
nt = w.node_tree; bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tc.outputs["Generated"], sep.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
cr.elements[0].position, cr.elements[0].color = 0.0, (0.004, 0.005, 0.012, 1)
cr.elements[1].position, cr.elements[1].color = 1.0, (0.06, 0.035, 0.09, 1)
nt.links.new(sep.outputs["Z"], ramp.inputs[0]); nt.links.new(ramp.outputs[0], bg.inputs[0])
bg.inputs[1].default_value = 1.0
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 4.0; sun.data.color = (1.0, 0.55, 0.28); sun.data.angle = math.radians(4)
sun.rotation_euler = (math.radians(62), 0, math.radians(240))
fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "SUN")); sc.collection.objects.link(fill)
fill.data.energy = 1.6; fill.data.color = (0.35, 0.45, 1.0); fill.data.angle = math.radians(30)
fill.rotation_euler = (math.radians(60), 0, math.radians(40))

# ---- camera: three-quarter, from the south-east, a little above
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 46
target = Vector((0.45, 0.25, 0.2))
cam.location = Vector((10.5, -12.8, 10.0))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = (target - cam.location).length; cam.data.dof.aperture_fstop = 8

# ---- render
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"; sc.cycles.samples = samples; sc.cycles.use_denoising = True
try: sc.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception: pass
rx, ry = map(int, res.split("x")); sc.render.resolution_x, sc.render.resolution_y = rx, ry
for vt in ("AgX", "Filmic"):
    try:
        sc.view_settings.view_transform = vt; break
    except TypeError:
        pass
try: sc.view_settings.look = "AgX - Medium High Contrast" if sc.view_settings.view_transform == "AgX" else "Medium High Contrast"
except TypeError: pass
sc.view_settings.exposure = 0.55
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("BEAUTY", out)
