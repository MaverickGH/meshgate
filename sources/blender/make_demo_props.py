"""MeshGate — demo prop set: three objects, each exercising its own part of the contract.

  lantern  — glass (BLEND + KHR_materials_transmission), emission, chain; `swing` animation
  barrel   — normal map from a procedural height field, metallic/roughness, hoops; no animations
  drone    — deep hierarchy, two clips (`rotors` and `hover`), details for LOD and collisions

Headless:
    blender -b -P sources/blender/make_demo_props.py -- --out-dir samples [--only lantern]
Each prop is saved as samples/meshgate_<name>.blend; export with export_meshgate.py.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import bpy
except ImportError:
    print("This script runs inside Blender")
    sys.exit(2)

import argparse
import math
import os
import tempfile

import numpy as np
from mathutils import Vector

# version compatibility (Blender 3.5 … 5.x) lives in the add-on package next to this script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshgate_blender import compat  # noqa: E402

TEX = 1024
FPS = 30


# ----------------------------------------------------------------------------
# common
# ----------------------------------------------------------------------------

def _args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="samples")
    ap.add_argument("--only", choices=["lantern", "barrel", "drone"], help="build only one prop")
    ap.add_argument("--tex-size", type=int, default=TEX)
    return ap.parse_args(argv)


def reset(frames=60):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"; sc.unit_settings.scale_length = 1.0
    sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = frames
    bpy.context.scene.cursor.location = (0, 0, 0)


def noise(size, cells, rng):
    grid = rng.random((cells + 1, cells + 1))
    xs = np.linspace(0, cells, size, endpoint=False)
    x0 = np.floor(xs).astype(int); fx = xs - x0; x1 = np.minimum(x0 + 1, cells)
    a = grid[x0[:, None], x0[None, :]] * (1 - fx[:, None]) + grid[x1[:, None], x0[None, :]] * fx[:, None]
    b = grid[x0[:, None], x1[None, :]] * (1 - fx[:, None]) + grid[x1[:, None], x1[None, :]] * fx[:, None]
    return a * (1 - fx[None, :]) + b * fx[None, :]


def make_image(name, rgba, tmpdir, is_data):
    h, w, _ = rgba.shape
    img = bpy.data.images.new(name, width=w, height=h, alpha=True)
    img.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    img.filepath_raw = os.path.join(tmpdir, f"{name}.png"); img.file_format = "PNG"; img.save(); img.pack()
    img.filepath_raw = f"//textures/{name}.png"
    return img


def height_to_normal(height: np.ndarray, strength: float = 4.0) -> np.ndarray:
    """Height map [0..1] → tangent-space normal map (OpenGL, +Y up — as glTF expects)."""
    dx = np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)
    dy = np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)
    nx, ny, nz = -dx * strength, -dy * strength, np.ones_like(height)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / n, ny / n, nz / n
    return np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz * 0.5 + 0.5, np.ones_like(nz)], axis=2)


def principled(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree.nodes["Principled BSDF"]


def link_tex(mat, bsdf, image, socket, is_normal=False, location=(-500, 0)):
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = image; tex.location = location
    if is_normal:
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (location[0] + 250, location[1])
        nt.links.new(tex.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        nt.links.new(tex.outputs["Color"], bsdf.inputs[socket])


def prim(op, name, mat=None, location=(0, 0, 0), scale=(1, 1, 1), rotation=(0, 0, 0), parent=None, smooth=False, **kw):
    op(location=location, rotation=rotation, **kw)
    o = bpy.context.active_object
    o.name = name; o.data.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if mat: o.data.materials.append(mat)
    if parent is not None: o.parent = parent
    for p in o.data.polygons: p.use_smooth = smooth
    return o


def bevel(o, width, segments=2):
    m = o.modifiers.new("bevel", "BEVEL"); m.width = width; m.segments = segments; m.limit_method = "ANGLE"


def shift(o, offset):
    for v in o.data.vertices: v.co += Vector(offset)


def root_empty(name):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    r = bpy.context.active_object; r.name = name
    return r


def action_to_nla(obj, name, keys, path="rotation_euler", interpolation="BEZIER"):
    """keys: [(frame, value)] → action `name` pushed into an NLA strip."""
    obj.animation_data_create()
    obj.animation_data.action = bpy.data.actions.new(name)
    obj.rotation_mode = "XYZ"
    for frame, value in keys:
        setattr(obj, path, value)
        obj.keyframe_insert(path, frame=frame)
    for fc in compat.fcurves(obj.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = interpolation
            if interpolation == "BEZIER": kp.easing = "EASE_IN_OUT"
    ad = obj.animation_data
    track = ad.nla_tracks.new(); track.name = name
    strip = track.strips.new(name, int(ad.action.frame_range[0]), ad.action); strip.name = name
    ad.action = None


def save(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True)
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
    print(f"MeshGate: {os.path.basename(path)} — {len(meshes)} meshes, {len(bpy.data.materials)} materials, {len(bpy.data.actions)} animations")


# ----------------------------------------------------------------------------
# lantern
# ----------------------------------------------------------------------------

def build_lantern(tmp, tex_size):
    reset(90)
    rng = np.random.default_rng(11)
    # scratched metal: roughness map
    rough = 0.45 + 0.35 * noise(tex_size, 64, rng)
    scratches = noise(tex_size, 6, rng)[:, (np.arange(tex_size) // 16)]
    rough = np.clip(rough - 0.2 * (scratches > 0.7), 0.2, 0.95)
    rough_img = make_image("lantern_metal_rough", np.stack([rough] * 3 + [np.ones_like(rough)], axis=2), tmp, True)

    metal, b = principled("lantern_metal")
    b.inputs["Base Color"].default_value = (0.22, 0.20, 0.18, 1); b.inputs["Metallic"].default_value = 1.0
    link_tex(metal, b, rough_img, "Roughness")
    glass, b = principled("lantern_glass")
    b.inputs["Base Color"].default_value = (0.95, 0.85, 0.6, 1); b.inputs["Roughness"].default_value = 0.08
    compat.socket(b, "Transmission").default_value = 1.0; b.inputs["IOR"].default_value = 1.45; b.inputs["Alpha"].default_value = 0.3
    compat.set_blend(glass, "BLEND")
    flame, b = principled("lantern_flame")
    b.inputs["Base Color"].default_value = (1.0, 0.6, 0.2, 1); compat.socket(b, "Emission").default_value = (1.0, 0.55, 0.15, 1)
    b.inputs["Emission Strength"].default_value = 6.0

    root = root_empty("meshgate_lantern")
    # hanger: hook ring on top, origin at the pivot point (0,0,0.55), the lantern swings around it
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.55))
    pivot = bpy.context.active_object; pivot.name = "hang_pivot"; pivot.parent = root
    ring = prim(bpy.ops.mesh.primitive_torus_add, "hook_ring", metal, (0, 0, 0.0), parent=pivot, smooth=True,
                major_radius=0.03, minor_radius=0.005, major_segments=24, minor_segments=8, rotation=(math.pi / 2, 0, 0))
    ring.location = (0, 0, 0.0)
    chain_y = -0.03
    for i in range(3):
        link = prim(bpy.ops.mesh.primitive_torus_add, f"chain_{i}", metal, (0, 0, 0), parent=pivot, smooth=True,
                    major_radius=0.016, minor_radius=0.004, major_segments=16, minor_segments=8,
                    rotation=(math.pi / 2, 0, 0 if i % 2 == 0 else math.pi / 2))
        link.location = (0, 0, chain_y - i * 0.028)
    cap = prim(bpy.ops.mesh.primitive_cone_add, "cap", metal, (0, 0, 0), parent=pivot, smooth=True, radius1=0.11, radius2=0.03, depth=0.07, vertices=24)
    cap.location = (0, 0, -0.15)
    body = prim(bpy.ops.mesh.primitive_cylinder_add, "glass_body", glass, (0, 0, 0), parent=pivot, smooth=True, radius=0.085, depth=0.22, vertices=32)
    body.location = (0, 0, -0.30)
    for i in range(4):
        a = i * math.pi / 2
        bar = prim(bpy.ops.mesh.primitive_cylinder_add, f"bar_{i}", metal, (0, 0, 0), parent=pivot, smooth=True, radius=0.006, depth=0.24, vertices=8)
        bar.location = (0.088 * math.cos(a), 0.088 * math.sin(a), -0.30)
    base = prim(bpy.ops.mesh.primitive_cylinder_add, "base", metal, (0, 0, 0), parent=pivot, smooth=True, radius=0.10, depth=0.04, vertices=32)
    base.location = (0, 0, -0.43); bevel(base, 0.006)
    wick = prim(bpy.ops.mesh.primitive_uv_sphere_add, "flame", flame, (0, 0, 0), parent=pivot, smooth=True, radius=0.028, segments=16, ring_count=10)
    wick.location = (0, 0, -0.34); wick.scale = (1, 1, 1.6); bpy.ops.object.transform_apply(scale=True)

    # swing: sway around the pivot point ±12°, 3 s
    action_to_nla(pivot, "swing", [(1, (0, math.radians(12), 0)), (45, (0, math.radians(-12), 0)), (90, (0, math.radians(12), 0))])
    # flicker: the flame pulses in scale (demonstrates scale animation)
    action_to_nla(wick, "flicker", [(1, (1, 1, 1)), (20, (1.15, 1.15, 1.3)), (40, (0.9, 0.9, 0.85)), (60, (1, 1, 1))], path="scale")
    return root


# ----------------------------------------------------------------------------
# barrel
# ----------------------------------------------------------------------------

def build_barrel(tmp, tex_size):
    reset(1)
    rng = np.random.default_rng(5)
    y = np.arange(tex_size)[:, None]; x = np.arange(tex_size)[None, :]
    staves = 12
    stave = (x * staves) // tex_size
    gap = np.broadcast_to(((x * staves) % tex_size) < tex_size * 0.02, (tex_size, tex_size))
    tone = rng.uniform(0.8, 1.15, staves)
    base = np.array([0.45, 0.28, 0.15])
    grain = 0.85 + 0.3 * noise(tex_size, 40, rng)[(np.arange(tex_size) // 6) % tex_size, :]
    color = base[None, None, :] * tone[stave][:, :, None] * grain[:, :, None]
    color[gap] *= 0.3
    albedo = np.concatenate([np.clip(color, 0, 1), np.ones((tex_size, tex_size, 1))], axis=2)
    height = 0.5 + 0.25 * noise(tex_size, 48, rng) - 0.5 * gap
    normal = height_to_normal(height, strength=6.0)
    rough = np.clip(0.6 + 0.3 * noise(tex_size, 24, rng), 0, 1)
    alb_img = make_image("barrel_wood_albedo", albedo, tmp, False)
    nrm_img = make_image("barrel_wood_normal", normal, tmp, True)
    rgh_img = make_image("barrel_wood_rough", np.stack([rough] * 3 + [np.ones_like(rough)], axis=2), tmp, True)

    wood, b = principled("barrel_wood")
    link_tex(wood, b, alb_img, "Base Color", location=(-500, 300))
    link_tex(wood, b, rgh_img, "Roughness", location=(-500, 0))
    link_tex(wood, b, nrm_img, None, is_normal=True, location=(-700, -300))
    iron, b = principled("barrel_iron")
    b.inputs["Base Color"].default_value = (0.35, 0.34, 0.33, 1); b.inputs["Metallic"].default_value = 1.0; b.inputs["Roughness"].default_value = 0.5

    root = root_empty("meshgate_barrel")
    body = prim(bpy.ops.mesh.primitive_cylinder_add, "barrel_body", wood, (0, 0, 0), parent=root, smooth=True, radius=0.30, depth=0.90, vertices=32)
    shift(body, (0, 0, 0.45))  # origin at the base
    # "belly": push the middle vertices outward
    for v in body.data.vertices:
        t = 1 - abs((v.co.z - 0.45) / 0.45)
        r = 1 + 0.12 * math.sin(t * math.pi / 2)
        v.co.x *= r; v.co.y *= r
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cylinder_project(direction="ALIGN_TO_OBJECT", scale_to_bounds=True)
    bpy.ops.mesh.select_all(action="DESELECT"); bpy.ops.object.mode_set(mode="OBJECT")
    for i, z in enumerate((0.10, 0.36, 0.54, 0.80)):
        t = 1 - abs((z - 0.45) / 0.45); r = 0.30 * (1 + 0.12 * math.sin(t * math.pi / 2))
        hoop = prim(bpy.ops.mesh.primitive_torus_add, f"hoop_{i}", iron, (0, 0, 0), parent=root, smooth=True,
                    major_radius=r + 0.004, minor_radius=0.012, major_segments=48, minor_segments=8)
        hoop.location = (0, 0, z); hoop.scale = (1, 1, 2.2); bpy.ops.object.transform_apply(scale=True)
    lid = prim(bpy.ops.mesh.primitive_cylinder_add, "lid", wood, (0, 0, 0), parent=root, smooth=False, radius=0.27, depth=0.03, vertices=32)
    lid.location = (0, 0, 0.905)
    bpy.context.view_layer.objects.active = lid
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66)); bpy.ops.mesh.select_all(action="DESELECT"); bpy.ops.object.mode_set(mode="OBJECT")
    return root


# ----------------------------------------------------------------------------
# drone
# ----------------------------------------------------------------------------

def build_drone(tmp, tex_size):
    reset(90)
    shell, b = principled("drone_shell")
    b.inputs["Base Color"].default_value = (0.85, 0.86, 0.9, 1); b.inputs["Roughness"].default_value = 0.35; b.inputs["Metallic"].default_value = 0.1
    dark, b = principled("drone_dark")
    b.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1); b.inputs["Roughness"].default_value = 0.5
    rotor_m, b = principled("drone_rotor")
    b.inputs["Base Color"].default_value = (0.2, 0.2, 0.22, 1); b.inputs["Roughness"].default_value = 0.4
    b.inputs["Alpha"].default_value = 0.85; compat.set_blend(rotor_m, "BLEND")
    lamp, b = principled("drone_lamp")
    b.inputs["Base Color"].default_value = (1, 0.2, 0.2, 1); compat.socket(b, "Emission").default_value = (1, 0.15, 0.1, 1); b.inputs["Emission Strength"].default_value = 5

    root = root_empty("meshgate_drone")
    # hover node: the whole body sways and lifts relative to root
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.12))
    hover = bpy.context.active_object; hover.name = "hover_pivot"; hover.parent = root
    body = prim(bpy.ops.mesh.primitive_uv_sphere_add, "body", shell, (0, 0, 0), parent=hover, smooth=True, radius=0.14, segments=32, ring_count=16)
    body.scale = (1.2, 1.0, 0.55); bpy.ops.object.transform_apply(scale=True)
    cam = prim(bpy.ops.mesh.primitive_uv_sphere_add, "camera_eye", dark, (0, 0, 0), parent=body, smooth=True, radius=0.045, segments=16, ring_count=10)
    cam.location = (0, -0.13, -0.03)
    beacon = prim(bpy.ops.mesh.primitive_uv_sphere_add, "tail_lamp", lamp, (0, 0, 0), parent=body, smooth=True, radius=0.02, segments=12, ring_count=8)
    beacon.location = (0, 0.15, 0.0)
    for i, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        arm = prim(bpy.ops.mesh.primitive_cylinder_add, f"arm_{i}", dark, (0, 0, 0), parent=body, smooth=True, radius=0.014, depth=0.30, vertices=10,
                   rotation=(0, math.pi / 2, math.atan2(sy, sx)))
        arm.location = (sx * 0.16, sy * 0.13, 0.0)
        motor = prim(bpy.ops.mesh.primitive_cylinder_add, f"motor_{i}", shell, (0, 0, 0), parent=arm, smooth=True, radius=0.03, depth=0.05, vertices=16)
        motor.location = (sx * 0.12, sy * 0.10, 0.02)
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
        hub = bpy.context.active_object; hub.name = f"rotor_{i}"; hub.parent = motor; hub.location = (0, 0, 0.03)
        for k in range(2):
            blade = prim(bpy.ops.mesh.primitive_cube_add, f"blade_{i}_{k}", rotor_m, (0, 0, 0), parent=hub, size=1.0)
            blade.scale = (0.24, 0.025, 0.004); bpy.ops.object.transform_apply(scale=True)
            blade.rotation_euler = (0, 0, k * math.pi / 2)
        action_to_nla(hub, "rotors", [(1, (0, 0, 0)), (90, (0, 0, math.tau * (6 if i % 2 == 0 else -6)))], interpolation="LINEAR")
    for i, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        leg = prim(bpy.ops.mesh.primitive_cylinder_add, f"leg_{i}", dark, (0, 0, 0), parent=body, smooth=True, radius=0.008, depth=0.12, vertices=8)
        leg.location = (sx * 0.07, sy * 0.06, -0.10)
    skid = prim(bpy.ops.mesh.primitive_cube_add, "skid", dark, (0, 0, 0), parent=body, size=1.0)
    skid.scale = (0.24, 0.20, 0.012); bpy.ops.object.transform_apply(scale=True); skid.location = (0, 0, -0.16)
    # hover: lift and a slight tilt (location + rotation on a single node)
    hover.animation_data_create(); hover.animation_data.action = bpy.data.actions.new("hover"); hover.rotation_mode = "XYZ"
    for frame, (dz, tilt) in ((1, (0.0, 0.0)), (30, (0.05, 3.0)), (60, (0.0, -3.0)), (90, (0.0, 0.0))):
        hover.location = (0, 0, 0.12 + dz); hover.keyframe_insert("location", frame=frame)
        hover.rotation_euler = (math.radians(tilt), 0, 0); hover.keyframe_insert("rotation_euler", frame=frame)
    for fc in compat.fcurves(hover.animation_data.action):
        for kp in fc.keyframe_points: kp.interpolation = "BEZIER"; kp.easing = "EASE_IN_OUT"
    ad = hover.animation_data; tr = ad.nla_tracks.new(); tr.name = "hover"
    st = tr.strips.new("hover", 1, ad.action); st.name = "hover"; ad.action = None
    return root


def main():
    args = _args()
    builders = {"lantern": build_lantern, "barrel": build_barrel, "drone": build_drone}
    for name, fn in builders.items():
        if args.only and args.only != name:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            fn(tmp, args.tex_size)
            save(os.path.join(args.out_dir, f"meshgate_{name}.blend"))


if __name__ == "__main__":
    main()
