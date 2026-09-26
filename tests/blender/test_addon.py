"""MeshGate add-on test — runs inside Blender (any version 3.5 … 5.x).

    blender -b --factory-startup -P tests/blender/test_addon.py -- --zip dist/meshgate-blender-X.zip --out /tmp/mg

Driven by `python3 meshgate.py check blender`, which runs it in an isolated user profile per Blender
version (BLENDER_USER_* env vars), so the user's own Blender settings are never touched.

Steps: install + enable the add-on from the zip → build a deliberately broken scene (Cyrillic names,
unapplied scale, no UVs, external non-power-of-two texture, below the ground, Mixamo skeleton, unweighted
vertices) → Check must find every problem → Fix all must clear every auto-fixable one → add collision + LODs
→ Export for web/Unity/Godot/Unreal → validate every file and look inside the engine variants → export each
sample .blend. Writes a JSON summary to <out>/result.json and exits non-zero on failure.
"""

import json
import os
import struct
import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import traceback

import addon_utils
import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ZIP = os.path.abspath(argv[argv.index("--zip") + 1])
OUT = os.path.abspath(argv[argv.index("--out") + 1])
SAMPLES = os.path.abspath(argv[argv.index("--samples") + 1]) if "--samples" in argv else None
os.makedirs(OUT, exist_ok=True)

result = {"blender": bpy.app.version_string, "steps": [], "ok": True}


def step(name, ok, detail=""):
    result["steps"].append({"step": name, "ok": bool(ok), "detail": detail})
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not ok:
        result["ok"] = False


def glb_node_names(path):
    data = open(path, "rb").read()
    n, _ = struct.unpack_from("<II", data, 12)
    gltf = json.loads(data[20:20 + n])
    return [x.get("name", "") for x in gltf.get("nodes", [])], gltf


# ----------------------------------------------------------------------------
# 1. install + enable
# ----------------------------------------------------------------------------

def install():
    if bpy.app.version >= (4, 2, 0):
        module = "bl_ext.user_default.meshgate"
        if not addon_utils.check(module)[0]:
            bpy.ops.extensions.package_install_files(filepath=ZIP, repo="user_default", enable_on_install=True)
    else:
        module = "meshgate"
        bpy.ops.preferences.addon_install(filepath=ZIP, overwrite=True)
    addon_utils.enable(module, default_set=True)
    loaded, enabled = addon_utils.check(module)
    step("add-on installed and enabled", enabled and hasattr(bpy.types.Scene, "meshgate"), module)
    global MODULE
    MODULE = module
    return sys.modules[module]


MODULE = None


# ----------------------------------------------------------------------------
# 2. broken scene
# ----------------------------------------------------------------------------

def broken_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable(MODULE, default_set=True)   # factory settings switch add-ons off
    scene = bpy.context.scene
    scene.unit_settings.system = "IMPERIAL"

    # external 300×200 texture on disk (not packed, not power of two)
    img = bpy.data.images.new("tex src", 300, 200)
    img.pixels.foreach_set([0.8, 0.3, 0.1, 1.0] * 300 * 200)
    tex_path = os.path.join(OUT, "texture_300x200.png")
    img.filepath_raw = tex_path; img.file_format = "PNG"; img.save()
    bpy.data.images.remove(img)
    img = bpy.data.images.load(tex_path)

    mat = bpy.data.materials.new("мой материал"); mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage"); tex.image = img
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -1.0))
    box = bpy.context.active_object
    box.name = "Коробка тест"
    box.scale = (0.6, 0.4, 0.4)
    box.data.materials.append(mat)
    while box.data.uv_layers:
        box.data.uv_layers.remove(box.data.uv_layers[0])

    # Mixamo-style skeleton + a skinned mesh with unweighted vertices
    arm_data = bpy.data.armatures.new("rig"); arm = bpy.data.objects.new("rig", arm_data)
    scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    spec = {
        "mixamorig:Hips": ((0, 2, 0.95), (0, 2, 1.05), None), "mixamorig:Spine": ((0, 2, 1.05), (0, 2, 1.2), "mixamorig:Hips"),
        "mixamorig:Spine1": ((0, 2, 1.2), (0, 2, 1.3), "mixamorig:Spine"), "mixamorig:Spine2": ((0, 2, 1.3), (0, 2, 1.42), "mixamorig:Spine1"),
        "mixamorig:Neck": ((0, 2, 1.42), (0, 2, 1.52), "mixamorig:Spine2"), "mixamorig:Head": ((0, 2, 1.52), (0, 2, 1.75), "mixamorig:Neck"),
    }
    for side, sx in (("Left", 1), ("Right", -1)):
        spec.update({
            f"mixamorig:{side}Shoulder": ((sx * .05, 2, 1.4), (sx * .17, 2, 1.4), "mixamorig:Spine2"),
            f"mixamorig:{side}Arm": ((sx * .17, 2, 1.4), (sx * .45, 2, 1.4), f"mixamorig:{side}Shoulder"),
            f"mixamorig:{side}ForeArm": ((sx * .45, 2, 1.4), (sx * .7, 2, 1.4), f"mixamorig:{side}Arm"),
            f"mixamorig:{side}Hand": ((sx * .7, 2, 1.4), (sx * .8, 2, 1.4), f"mixamorig:{side}ForeArm"),
            f"mixamorig:{side}UpLeg": ((sx * .1, 2, .92), (sx * .1, 2, .5), "mixamorig:Hips"),
            f"mixamorig:{side}Leg": ((sx * .1, 2, .5), (sx * .1, 2, .08), f"mixamorig:{side}UpLeg"),
            f"mixamorig:{side}Foot": ((sx * .1, 2, .08), (sx * .1, 1.88, .02), f"mixamorig:{side}Leg"),
            f"mixamorig:{side}ToeBase": ((sx * .1, 1.88, .02), (sx * .1, 1.8, .02), f"mixamorig:{side}Foot"),
        })
    eb = {}
    for name, (h, t, _) in spec.items():
        b = arm_data.edit_bones.new(name); b.head, b.tail = h, t; eb[name] = b
    for name, (_, _, parent) in spec.items():
        if parent:
            eb[name].parent = eb[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=1.7, location=(0, 2, 0.85), vertices=12)
    body = bpy.context.active_object; body.name = "body"
    body.data.materials.append(bpy.data.materials.new("body_skin"))
    body.data.materials[0].use_nodes = True
    g = body.vertex_groups.new(name="mixamorig:Spine")
    g.add([v.index for v in body.data.vertices if v.co.z > 0], 1.0, "REPLACE")   # lower half unweighted
    mod = body.modifiers.new("rig", "ARMATURE"); mod.object = arm
    body.parent = arm
    return box


# ----------------------------------------------------------------------------
# 3. check → fix → export
# ----------------------------------------------------------------------------

def codes():
    return {i.code for i in bpy.context.scene.meshgate.issues}


def main():
    mod = install()
    box = broken_scene()
    s = bpy.context.scene.meshgate

    bpy.ops.meshgate.check()
    found = codes()
    expected = {"UNITS", "SCALE", "NAMES", "NO_UV", "UNPACKED", "NPOT", "GROUND", "BONE_NAMES", "WEIGHTS"}
    step("check finds every planted problem", expected <= found, f"missing {sorted(expected - found)}" if not expected <= found else ", ".join(sorted(found)))

    bpy.ops.meshgate.fix_all()
    left = [(i.code, i.fix) for i in s.issues]
    step("fix all clears every auto-fixable issue", not any(f for _, f in left), f"left: {left}")

    arm = bpy.data.objects["rig"]
    humanoid = {"Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftUpperArm", "RightLowerArm", "LeftUpperLeg", "RightToes"}
    step("Mixamo bones renamed to Unity Humanoid", humanoid <= {b.name for b in arm.data.bones}, ", ".join(sorted(b.name for b in arm.data.bones))[:200])
    box = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("korobka"))
    step("Cyrillic name transliterated", box.name == "korobka_test", box.name)

    for o in bpy.context.view_layer.objects:
        o.select_set(o == box)
    bpy.context.view_layer.objects.active = box
    bpy.ops.meshgate.add_collision()
    bpy.ops.meshgate.make_lods()
    step("collision proxy and LODs created", bpy.data.objects.get("COL_korobka_test") is not None and bpy.data.objects.get("korobka_test_LOD2") is not None)

    s.target_web = s.target_unity = s.target_godot = s.target_unreal = True
    s.fbx = True; s.web_draco = True
    s.out_dir = OUT + os.sep; s.asset_name = "fixture"
    bpy.ops.meshgate.export()
    report = [line.text for line in s.report]
    print("\n".join("    " + r for r in report))
    files = ["fixture.glb", "fixture.draco.glb", "fixture.fbx", "fixture.unity.fbx", "fixture.unreal.fbx", "fixture.godot.glb"]
    missing = [f for f in files if not os.path.isfile(os.path.join(OUT, f))]
    step("export writes canonical GLB + every engine variant", not missing, f"missing {missing}" if missing else ", ".join(files))
    step("every exported file passes the validator (--strict)", all(line.startswith("✓") for line in report if line[:1] in "✓⚠✗"),
         "; ".join(line for line in report if line[:1] in "⚠✗"))

    export = sys.modules[mod.__name__ + ".export"]
    canon_nodes, canon = glb_node_names(os.path.join(OUT, "fixture.glb"))
    step("canonical GLB has no proxies/LODs", not any(n.startswith(("COL_", "UCX_")) or "_LOD" in n or "colonly" in n for n in canon_nodes), ", ".join(canon_nodes))
    rep = export.validate_file(os.path.join(OUT, "fixture.glb"))
    step("canonical GLB: Humanoid skeleton, meters, on the ground",
         rep.get("humanoid") is True and rep["bounds_min_m"][1] > -0.01 and max(rep["dims_m"]) < 3.5, f"humanoid={rep.get('humanoid')} min={rep.get('bounds_min_m')} dims={rep.get('dims_m')}")
    step("draco variant is compressed", export.validate_file(os.path.join(OUT, "fixture.draco.glb")).get("draco") is True)
    godot_nodes, _ = glb_node_names(os.path.join(OUT, "fixture.godot.glb"))
    step("godot variant has -convcolonly collision", any(n.endswith("-convcolonly") for n in godot_nodes), ", ".join(godot_nodes))
    fbx_mod = export._load_module("validate_fbx")
    _, unreal_root = fbx_mod.parse_fbx(__import__("pathlib").Path(os.path.join(OUT, "fixture.unreal.fbx")))
    unreal_models = [n["props"][1].split("\x00")[0] for n in fbx_mod._find(fbx_mod._find(unreal_root, "Objects")[0]["children"], "Model")]
    step("unreal variant has UCX_ collision", "UCX_korobka_test_00" in unreal_models, ", ".join(unreal_models))
    _, unity_root = fbx_mod.parse_fbx(__import__("pathlib").Path(os.path.join(OUT, "fixture.unity.fbx")))
    unity_models = [n["props"][1].split("\x00")[0] for n in fbx_mod._find(fbx_mod._find(unity_root, "Objects")[0]["children"], "Model")]
    step("unity variant has _LOD0.._LOD2", {"korobka_test_LOD0", "korobka_test_LOD1", "korobka_test_LOD2"} <= set(unity_models), ", ".join(unity_models))
    step("scene restored after variants (names, hidden proxies)",
         bpy.data.objects.get("korobka_test") is not None and bpy.data.objects["COL_korobka_test"].hide_render)

    # quality tiers: a heavy textured mesh must come out within each tier's asset budget
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable(MODULE, default_set=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=0.5, location=(0, 0, 0.5))
    heavy = bpy.context.active_object; heavy.name = "heavy_sphere"
    img = bpy.data.images.new("heavy_albedo", 2048, 2048); img.generated_type = "UV_GRID"; img.pack()
    mat = bpy.data.materials.new("heavy_mat"); mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage"); tex.image = img
    mat.node_tree.links.new(tex.outputs["Color"], next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"])
    heavy.data.materials.append(mat)
    tiers_dir = os.path.join(OUT, "tiers")
    r = export.export_asset(bpy.context, os.path.join(tiers_dir, "heavy.glb"), profiles=["mobile-low", "mobile-mid", "mobile-high"])
    table = export.load_profiles()["profiles"]
    for prof in ("mobile-low", "mobile-mid", "mobile-high"):
        rep = export.validate_file(os.path.join(tiers_dir, f"heavy.{prof}.glb"), profile=prof)
        b = table[prof]["asset"]
        mimes = sorted({i.get("mime") for i in rep.get("images", [])})
        step(f"tier {prof}: within budget", rep["ok"] and rep["triangles"] <= b["max_tris"] and rep["max_texture"] <= b["max_texture"],
             f"{rep['triangles']:,}/{b['max_tris']:,} tris, texture {rep['max_texture']}/{b['max_texture']}px, {mimes}")
    canon = export.validate_file(os.path.join(tiers_dir, "heavy.glb"))
    step("canonical GLB untouched by tiers", canon["triangles"] > 60000 and canon["max_texture"] == 2048 and "meshgate_tier" not in heavy.modifiers
         and bpy.data.images.get("heavy_albedo").size[0] == 2048, f"{canon['triangles']:,} tris, {canon['max_texture']}px")
    low_img = export.validate_file(os.path.join(tiers_dir, "heavy.mobile-low.glb"))["images"]
    step("mobile tiers use JPEG textures", all(i.get("mime") == "image/jpeg" for i in low_img), str([i.get("mime") for i in low_img]))

    # the Kit panel: build code into a scene, guard rails, bring a model in at a size
    kit = sys.modules[mod.__name__ + ".kit_ui"]
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable(MODULE, default_set=True)
    ks = bpy.context.scene.meshgate_kit
    ks.code = os.path.join(repo, "sources", "generate", "examples", "zombie_cats", "lowpoly", "zombie_cat.py")
    ks.name, ks.tier, ks.finish = "zc", "mobile-low", "faceted"
    res = bpy.ops.meshgate.kit_build()
    tris = sum(len(p.vertices) - 2 for o in bpy.context.scene.objects if o.type == "MESH" for p in o.data.polygons)
    ks = bpy.context.scene.meshgate_kit   # with a window the build switched to a scene of its own
    step("kit panel builds build(mg) code at a tier", res == {"FINISHED"} and 200 < tris <= 8000, f"{res} {tris:,} tris; {ks.status}")
    bad = os.path.join(OUT, "bad_build.py")
    with open(bad, "w") as f:
        f.write("import os\ndef build(mg):\n    os.system('echo no')\n")
    ks.code = bad
    try:
        got = str(bpy.ops.meshgate.kit_build())
    except RuntimeError as exc:   # operators report ERROR as an exception in background mode
        got = str(exc)
    step("kit panel refuses unsafe build code", "CANCELLED" in got or "refused" in got, got[:200])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable(MODULE, default_set=True)
    objs = kit.import_model(bpy.context, os.path.join(repo, "sources", "generate", "examples", "hydrant_triposr_raw.glb"), 0.5, (1, 2, 0))
    bpy.context.view_layer.update()
    import mathutils
    pts = [o.matrix_world @ mathutils.Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    size = max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3))
    low = min(p.z for p in pts)
    step("kit panel imports a model at a size, standing on the cursor", abs(size - 0.5) < 0.01 and abs(low) < 0.01, f"size {size:.3f} lowest {low:.3f}")

    if SAMPLES:
        clips = {"demo": ["beacon_spin", "lid_open"], "hero": ["idle", "wave"], "lantern": ["flicker", "swing"],
                 "barrel": [], "drone": ["hover", "rotors"]}
        for name in ("demo", "hero", "lantern", "barrel", "drone"):
            blend = os.path.join(SAMPLES, f"meshgate_{name}.blend")
            if not os.path.isfile(blend):
                continue
            bpy.ops.wm.open_mainfile(filepath=blend)
            r = export.export_asset(bpy.context, os.path.join(OUT, "samples", f"{name}.glb"), targets=["web", "unity", "godot", "unreal"], fbx=True)
            step(f"sample {name}: export + validate", r.ok, "; ".join(export.summary_lines(r))[:300])
            got = sorted(r.reports[0].get("animations", []))
            step(f"sample {name}: exact clip names", got == clips[name], f"{got} (expected {clips[name]})")


try:
    main()
except Exception:  # noqa: BLE001
    step("test crashed", False, traceback.format_exc()[-1500:])
json.dump(result, open(os.path.join(OUT, "result.json"), "w"), indent=2, ensure_ascii=False)
print(f"RESULT {'PASS' if result['ok'] else 'FAIL'} Blender {bpy.app.version_string}")
sys.exit(0 if result["ok"] else 1)
