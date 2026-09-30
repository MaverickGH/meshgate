"""MeshGate generation runner — builds an AI-written `build(mg)` in Blender once per quality tier and exports it.

    blender -b --factory-startup -P sources/generate/run_generated.py -- --code model.py --name fire_hydrant
            --out-dir out/gen/fire_hydrant [--tiers mobile-low,mobile-mid,pc] [--targets web,unity,godot,unreal]
            [--collision none|box|convex] [--size 0.9] [--preview] [--seed 1]

The richest tier becomes the canonical `<name>.glb` (+ `.fbx` and engine variants for --targets, `.blend`, preview
PNG); every other tier is rebuilt from the same code at its own detail and written as `<name>.<tier>.glb`, validated
against the tier budget. Writes `<name>.report.json` (read by meshgate.py gen and the desktop app) and prints one
`MESHGATE_REPORT <path>` line at the end.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import bpy
except ImportError:
    print("Run inside Blender: blender -b --factory-startup -P sources/generate/run_generated.py -- --code model.py ...")
    sys.exit(2)

import argparse
import json
import math
import os
import random
import tempfile
import traceback

import mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "blender"))
import safety  # noqa: E402
from meshgate_blender import checks, export, finish, modeling, tools  # noqa: E402

ORDER = list(modeling.TIERS)


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="Build AI-written MeshGate model code per quality tier")
    ap.add_argument("--code", required=True, help="python file defining build(mg)")
    ap.add_argument("--params", default="{}", help='JSON {name: value} for mg.param (Studio sliders)')
    ap.add_argument("--name", required=True, help="asset name (ASCII, file names derive from it)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tiers", default="mobile-low,mobile-mid,mobile-high,pc", help="tiers to build; the richest is canonical")
    ap.add_argument("--targets", default="web,unity,godot,unreal", help="engine variants for the canonical file")
    ap.add_argument("--collision", default="none", choices=["none", "box", "convex"], help="collision proxy for static meshes")
    ap.add_argument("--size", type=float, default=0.0, help="expected largest dimension in meters (0 = do not check)")
    ap.add_argument("--preview", action="store_true", help="render <name>.png of the canonical model (Workbench)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--colors", default="texture", choices=["texture", "vertex"], help="palette textures or vertex colours")
    ap.add_argument("--caps", default="", help="your triangle limits per tier: mobile-low=300,pc=2000")
    ap.add_argument("--texture", type=int, default=0, help="baked texture size in px (1024…8192); tiers still cap it, "
                    "a size above the PC tier also writes <name>.master.glb")
    ap.add_argument("--topology", default="tri", choices=["tri", "quad"], help="FBX and .blend topology (GLB is always triangles)")
    ap.add_argument("--finish", default="none", choices=["none", "faceted", "weathered", "clean"],
                    help="faceted: low-poly look enforced (flat, few segments); weathered: dirt, variation and relief baked into textures")
    ap.add_argument("--outline", action="store_true", help="toon ink line: an inverted hull on mobile-high and PC")
    ap.add_argument("--split", action="store_true", help="every separate thing its own object (to move in an engine)")
    ap.add_argument("--edits", default="", help="JSON file of hand changes to the split parts (Studio's part editor)")
    ap.add_argument("--section-fit", default="{}", help='JSON {part: {"scale": [x, y, z], "move": [x, y, z]}}: parts fitted to a reference')
    ap.add_argument("--look", default="", help="JSON file of the chosen look: morph values and colours (Studio's Appearance)")
    ap.add_argument("--fit", default="[]", help="JSON [[from, to, width ratio], …]: proportions fitted to a reference")
    ap.add_argument("--colour-fit", default="{}", help='JSON {colour name: [r, g, b]}: colours fitted to a reference')
    ap.add_argument("--pose", default="none", choices=list(modeling.POSES),
                    help="rest pose of rigged characters: none (as modelled), a (A-pose) or t (T-pose)")
    return ap.parse_args(argv)


def _trace(exc: BaseException) -> str:
    """The part of a traceback that points into the generated code, plus the message."""
    if isinstance(exc, modeling.ModelError):
        frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<generated>"]
        where = f"line {frames[-1].lineno}: " if frames else ""
        return where + str(exc)
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<generated>"]
    lines = [f"line {f.lineno}, in {f.name}: {f.line or ''}".rstrip() for f in frames]
    return "\n".join(lines + [f"{type(exc).__name__}: {exc}"])


def build_tier(code_obj, name: str, tier: str, seed: int, tmp: str, collision: str, colors: str = "texture",
               finish_: str = "none", texture: int = 0, topology: str = "tri", budget_override: dict | None = None,
               save_high: str | None = None, high: str | None = None, params: dict | None = None,
               pose: str = "none", outline: bool = False, fit: list | None = None, colour_fit: dict | None = None,
               split: bool = False, edits: dict | None = None, look: dict | None = None,
               section_fit: dict | None = None) -> dict:
    """Fresh scene → build(mg) at the tier's detail → finalize → contract fixes. Returns notes and in-Blender issues.
    save_high = write this (PC) build's geometry to a .blend; high = such a .blend: a lighter tier bakes its normal map
    from that detailed model (high → low, as an artist bakes a sculpt onto a game mesh)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    budget = {**export.load_profiles()["profiles"][tier]["asset"], **(budget_override or {})}
    kit = modeling.Kit(tier, seed=seed, name=name, tmp=tmp, colors=colors, max_materials=budget["max_materials"],
                       max_influences=budget.get("max_influences", 4), params=params, max_tris=budget.get("max_tris"),
                       finish=finish_, max_texture=budget.get("max_texture"), max_texture_mb=budget.get("max_texture_mb"),
                       pose=pose, outline=outline, fit=fit, colour_fit=colour_fit, split=split,
                       edits=edits, look=look, max_file_mb=budget.get("max_file_mb"), section_fit=section_fit)
    g = safety.restricted_globals({"math": math, "random": random, "mathutils": mathutils})
    exec(code_obj, g)  # noqa: S102 — code passed safety.check before reaching here
    g["build"](kit)
    notes = kit._finalize()
    ctx = bpy.context
    if topology == "quad":
        notes += finish.quads(ctx)
    hero = finish_ == "weathered"   # realistic: a dense hero model with each material's relief pressed in
    if save_high:
        finish.save_high(ctx, save_high, hero=hero, cells=kit._cells())
    if finish_ in ("weathered", "clean"):
        src = high if high and os.path.exists(high) else (save_high if save_high and hero else None)
        hi = finish.load_high(ctx, src) if src else []
        notes += finish.weathered(ctx, budget, tier, tmp, name, want=texture or None, clean=finish_ == "clean", high=hi,
                                  hero=hero and bool(hi))
    if collision != "none":
        static = [o for o in ctx.scene.objects if o.type == "MESH" and not o.animation_data
                  and not (o.parent and o.parent.animation_data)]
        if static:
            tools.add_collision(ctx, static, collision.upper())
    checks.MAX_TEXTURE = max(4096, budget["max_texture"])   # the 8K master keeps its size
    before = [i for i in checks.run_checks(ctx) if i.severity != checks.INFO]
    fixed = checks.fix_all(ctx) if any(i.fix for i in before) else []
    after = [i for i in checks.run_checks(ctx) if i.severity != checks.INFO]
    return {"notes": notes + [f"fixed: {f}" for f in fixed], "issues": [f"[{i.code}] {i.label()}" for i in after],
            "facts": kit._facts() if tier == "pc" or save_high is not None else None,
            "params": kit._params, "credits": getattr(kit, "_credits", []), "dims_m": kit._dims(),
            "palette": {n: {"index": c["index"], "rgb": [round(x, 4) for x in c["rgb"]], "glow": c["glow"]}
                        for n, c in kit._colors.items()},
            "palette_grid": modeling.CELLS,
            "morphs": [{k: m[k] for k in ("name", "label", "two_sided", "value")} for m in kit._morphs],
            "sections": kit.sections_out(),
            "bake_colour": ctx.scene.get("mg_bake_colour"), "clips": sorted({t.name for o in ctx.scene.objects if o.animation_data
                                                     for t in o.animation_data.nla_tracks})}


def export_modules(out: str, name: str, targets, image_format) -> list:
    """Modular kits (mg.module): every module also as its own GLB, origin at its grid corner, for snapping in engines."""
    ctx = bpy.context
    mods = [o for o in ctx.scene.objects if o.get("meshgate_module")]
    written = []
    for m in mods:
        keep = (m.parent, m.matrix_parent_inverse.copy(), m.location.copy())
        m.parent = None
        m.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        m.location = (0.0, 0.0, 0.0)
        ctx.view_layer.update()
        for o in ctx.view_layer.objects:
            o.select_set(o is m or o.parent is m)
        path = os.path.join(out, f"{name}_{m['meshgate_module']}.glb")
        try:
            res = export.export_asset(ctx, path, targets=[], fbx=False, selection=True, animations=False, validate=True,
                                      strict=True, image_format=image_format)
            rep = res.reports[0] if res.reports else {}
            written.append({"name": m["meshgate_module"], "file": os.path.basename(path), "ok": res.ok,
                            "dims_m": rep.get("dims_m"), "tris": rep.get("triangles")})
        finally:
            m.parent, m.matrix_parent_inverse, m.location = keep[0], keep[1], keep[2]
            ctx.view_layer.update()
    for o in ctx.view_layer.objects:
        o.select_set(False)
    return written


def render_preview(path: str) -> str | None:
    """3/4 front view of the model, transparent background, Workbench with the palette colours."""
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == "MESH" and not o.get("meshgate_collision_for")]
    pts = [o.matrix_world @ mathutils.Vector(c) for o in meshes for c in o.bound_box]
    lo = mathutils.Vector([min(p[i] for p in pts) for i in range(3)])
    hi = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
    centre, radius = (lo + hi) / 2, max((hi - lo).length / 2, 0.05)
    cam_data = bpy.data.cameras.new("mg_preview")
    cam_data.lens = 50
    cam = bpy.data.objects.new("mg_preview", cam_data)
    scene.collection.objects.link(cam)
    direction = mathutils.Vector((0.9, -1.6, 0.8)).normalized()   # front is -Y: camera in front, to the right, above
    fov = 2 * math.atan(36 / 2 / cam_data.lens)
    cam.location = centre + direction * (radius / math.sin(fov / 2) * 1.05)
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.clip_start, cam_data.clip_end = radius * 0.01, radius * 50
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    shading = scene.display.shading
    shading.light = "STUDIO"
    has_textures = any(n.type == "TEX_IMAGE" for o in meshes for m in o.data.materials if m and m.node_tree
                       for n in m.node_tree.nodes)
    has_vertex = any(len(getattr(o.data, "color_attributes", [])) for o in meshes)
    shading.color_type = "VERTEX" if has_vertex and not has_textures else "TEXTURE"
    shading.show_cavity = True
    shading.show_shadows = False
    hidden = [o for o in scene.objects if o.get("meshgate_collision_for") or o.get("meshgate_lod_of")]
    for o in hidden:
        o.hide_render = True
    scene.render.filepath = path
    try:
        bpy.ops.render.render(write_still=True)
    except RuntimeError as exc:
        print(f"MeshGate gen: preview not rendered ({exc})")
        return None
    finally:
        bpy.data.objects.remove(cam)
    return path if os.path.exists(path) else None


def main() -> int:
    args = _args()
    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)
    name = modeling.Kit._ascii(args.name).lower()
    code = open(args.code, encoding="utf-8").read()
    tiers = sorted({t.strip() for t in args.tiers.split(",") if t.strip() in ORDER}, key=ORDER.index, reverse=True)
    if not tiers:
        print("MeshGate gen: no valid tiers"); return 2
    canonical = tiers[0]
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    report = {"name": name, "canonical": canonical, "tiers": {}, "files": [], "ok": False, "problems": [], "advice": [],
              "preview": None, "blend": None}
    report_path = os.path.join(out, f"{name}.report.json")
    caps = {k: int(v) for k, v in (item.split("=") for item in args.caps.split(",") if "=" in item)}

    def done(code_: int) -> int:
        report["ok"] = code_ == 0 and not report["problems"]
        json.dump(report, open(report_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"MESHGATE_REPORT {report_path}")
        return code_

    found = safety.check(code)
    if found:
        report["problems"] = [f"safety: {p}" for p in found]
        return done(1)
    code_obj = compile(code, "<generated>", "exec")
    try:
        params = {str(k): float(v) for k, v in json.loads(args.params or "{}").items()}
    except (ValueError, AttributeError):
        params = {}
    try:
        edits = json.load(open(args.edits, encoding="utf-8")) if args.edits else {}
    except (OSError, ValueError):
        edits = {}
    try:
        look = json.load(open(args.look, encoding="utf-8")) if args.look else {}
    except (OSError, ValueError):
        look = {}

    # weathered textures are photo-like: JPEG, as for the mesh engine's bakes; the flat palette stays lossless
    baked = args.finish in ("weathered", "clean")
    image_format = "JPEG" if baked else "AUTO"
    export.FBX_TRIANGLES = args.topology == "tri"
    with tempfile.TemporaryDirectory() as tmp:
        # the high model: PC geometry for the lighter tiers; for realistic also a dense hero every tier bakes from
        high = os.path.join(tmp, "high.blend") if baked and "pc" in tiers and (len(tiers) > 1 or args.finish == "weathered") else None
        for tier in tiers:
            is_canon = tier == canonical
            try:
                info = build_tier(code_obj, name, tier, args.seed, tmp, args.collision, args.colors, args.finish,
                                  args.texture, args.topology, save_high=high if tier == "pc" else None,
                                  high=high if tier != "pc" else None, params=params, pose=args.pose, outline=args.outline,
                                  fit=json.loads(args.fit or "[]"), colour_fit=json.loads(args.colour_fit or "{}"),
                                  split=args.split, edits=edits, look=look,
                                  section_fit=json.loads(args.section_fit or "{}"))
            except Exception as exc:  # noqa: BLE001 — every failure goes back to the AI as feedback
                report["problems"].append(f"build(mg) failed at tier {tier}:\n{_trace(exc)}")
                return done(1)
            entry = {**info, "file": None}
            if is_canon:
                glb = os.path.join(out, f"{name}.glb")
                cap_notes: list = []
                objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.get("meshgate_collision_for")]
                if caps.get(tier) and export.evaluated_tris(bpy.context, objs) > caps[tier]:
                    with export._tier(bpy.context, objs, {"max_tris": caps[tier], "max_texture": 1 << 20}, cap_notes):
                        res = export.export_asset(bpy.context, glb, targets=targets, fbx=bool({"unity", "unreal"} & set(targets)),
                                                  validate=True, strict=True, image_format=image_format)
                else:
                    res = export.export_asset(bpy.context, glb, targets=targets, fbx=bool({"unity", "unreal"} & set(targets)),
                                              validate=True, strict=True, image_format=image_format)
                entry["notes"] += [f"{n} (your cap)" for n in cap_notes]
                mods = export_modules(out, name, targets, image_format)
                if mods:
                    report["modules"] = mods
                    report["files"] += [m["file"] for m in mods]
                rep = export.validate_file(glb, profile=tier)
                report["files"] += [os.path.basename(f) for f in res.files]
                variant_problems = [f"{r.get('file')}: {e}" for r in res.reports[1:] for e in r.get("errors", [])]
                report["problems"] += variant_problems
                blend = os.path.join(out, f"{name}.blend")
                bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups (reset by factory settings)
                bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True, copy=True)
                report["blend"] = os.path.basename(blend)
                if args.preview:
                    png = render_preview(os.path.join(out, f"{name}.png"))
                    report["preview"] = os.path.basename(png) if png else None
            else:
                glb = os.path.join(out, f"{name}.{tier}.glb")
                tier_notes: list = []
                export.export_tier(bpy.context, glb, tier, notes=tier_notes, max_tris=caps.get(tier),
                                   image_format=image_format if baked else None)
                entry["notes"] += [f"{n} (your cap)" if caps.get(tier) else n for n in tier_notes]
                rep = export.validate_file(glb, profile=tier)
                report["files"].append(os.path.basename(glb))
            bud = rep.get("budget") or {}
            entry.update({"file": os.path.basename(glb), "tris": rep.get("triangles", 0),
                          "max_tris": next((x["limit"] for x in bud.get("items", []) if x["name"] == "tris"), None),
                          "within_budget": bool(bud.get("ok")), "draw_calls": rep.get("draw_calls"),
                          "materials": rep.get("materials"), "max_texture": rep.get("max_texture"),
                          "size_mb": rep.get("size_mb"), "errors": rep.get("errors", []), "warnings": rep.get("warnings", []),
                          "fits": rep.get("fits", [])})
            entry["cap"], entry["colors"] = caps.get(tier), args.colors
            if any(n.startswith("decimated") and n.endswith("(your cap)") for n in entry["notes"]):
                report["advice"].append(f"tier {tier}: decimated to your cap of {caps[tier]:,} triangles — for cleaner shapes "
                                        f"the build code can build less at this tier")
            decimated = any(n.startswith("decimated") and not n.endswith("(your cap)") for n in entry["notes"])
            if decimated:
                report["problems"].append(f"tier {tier}: the model built {info.get('dims_m')} m but over the "
                                          f"{entry['max_tris']:,}-triangle budget, MeshGate had to decimate it — build less "
                                          f"geometry at this tier (fewer segments, skip small details below "
                                          f"mg.at_least(...))")
            for e in entry["errors"]:
                report["problems"].append(f"tier {tier}: {e}")
            for w in entry["warnings"]:
                report["problems"].append(f"tier {tier}: {w}")
            for i in entry["issues"]:
                report["problems"].append(f"tier {tier}: contract: {i}")
            report["tiers"][tier] = entry
            facts = entry.pop("facts", None)
            if facts and not report.get("facts"):   # measured, for the AI's next round
                report["facts"] = facts
                for f in facts.get("floating", []):
                    report["advice"].append(f"geometry: the {f['what']} from line {f['line']} floats {f['gap_cm']} cm away from "
                                            f"everything else (at {f['at']}) — sink it into the piece it belongs to")
                for m in facts.get("modules") or []:
                    if m.get("off_grid"):
                        report["advice"].append(f"module {m['name']}: off its {m['grid_m']:g} m grid — {'; '.join(m['off_grid'])}; "
                                                "build it from its corner at the origin so it snaps")
            palette = entry.pop("palette", None)
            if palette and not report.get("palette"):   # colour names → palette cells (a colour fit reads them)
                report["palette"] = palette
            grid = entry.pop("palette_grid", None)
            if grid and not report.get("palette_grid"):
                report["palette_grid"] = grid
            secs = entry.pop("sections", [])
            if secs and not report.get("sections"):   # the model's named parts (mg.section), for fitting part by part
                report["sections"] = secs
            morph_list = entry.pop("morphs", [])
            if morph_list and not report.get("morphs"):   # the Appearance sliders (the same on every tier)
                report["morphs"] = morph_list
            declared = entry.pop("params", [])
            if declared and not report.get("params"):   # the sliders Studio shows (the same on every tier)
                report["params"] = declared
            for c in entry.pop("credits", []):   # library models used through mg.model: credited once per asset
                if all(x.get("uid") != c.get("uid") for x in report.setdefault("credits", [])):
                    report["credits"].append(c)
            print(f"  {'✓' if entry['within_budget'] and not entry['errors'] else '✗'} {tier:12} {entry['tris']:>7,} tris"
                  f" / {entry['max_tris'] or 0:,}  {entry['file']}  dims {info['dims_m']} m"
                  + (f"  clips {', '.join(info['clips'])}" if info["clips"] else ""), flush=True)
            for n in entry["notes"]:
                print(f"      · {n}", flush=True)
        pc_max = export.load_profiles()["profiles"]["pc"]["asset"]["max_texture"]
        if args.texture > pc_max and baked and "pc" in tiers:
            # above the PC tier's limit: one more PC build baked at the full size, for renders and film
            build_tier(code_obj, name, "pc", args.seed, tmp, "none", args.colors, args.finish, args.texture, args.topology,
                       budget_override={"max_texture": args.texture, "max_texture_mb": 4096}, params=params, pose=args.pose, outline=args.outline,
                                  fit=json.loads(args.fit or "[]"), colour_fit=json.loads(args.colour_fit or "{}"),
                                  split=args.split, edits=edits, look=look,
                                  section_fit=json.loads(args.section_fit or "{}"))
            master = os.path.join(out, f"{name}.master.glb")
            export.export_asset(bpy.context, master, targets=(), fbx=False, validate=False, image_format=image_format)
            report["files"].append(os.path.basename(master))
            report["master"] = {"file": os.path.basename(master), "texture": args.texture}
            print(f"  ✓ master       {args.texture} px textures, beyond the PC tier  {os.path.basename(master)}", flush=True)
        elif args.texture and not baked:
            report["advice"].append("the texture size applies to baked textures: the realistic style, or --pbr for the "
                                    "others (their flat palette needs no more than 256 px)")

    canon = report["tiers"][canonical]
    if args.size > 0:
        biggest = max(canon["dims_m"])
        if not (args.size / 2 <= biggest <= args.size * 2):
            report["problems"].append(f"size: the model's largest dimension is {biggest:.2f} m, expected about "
                                      f"{args.size:.2f} m — build in real-world meters")
    counts = [report["tiers"][t]["tris"] for t in reversed(tiers)]
    if len(counts) > 1 and counts[-1] <= counts[0]:
        report["advice"].append("detail: the richest tier has no more triangles than the lightest — use mg.seg(), "
                                "mg.at_least() and the tier-adjusted segments so richer tiers get more shape")
    return done(0)


if __name__ == "__main__":
    code = main()
    if code:
        sys.exit(code)
