"""MeshGate — headless export from Blender to a contract GLB (+ FBX and engine variants).

    blender -b scene.blend -P sources/blender/export_meshgate.py -- --out out.glb [--fbx] [--draco]
            [--targets web,unity,godot,unreal] [--check] [--fix] [--selection] [--validate]

Same code as the MeshGate add-on panel (sources/blender/meshgate_blender): the contract is enforced
by export flags and scene preparation — meters, Y-up, applied scale, PBR from Principled BSDF, packed
textures, animations from actions/NLA, no cameras/lights, objects hidden from render are skipped.
--check prints the in-Blender contract issues; --fix applies every automatic fix before exporting.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):   # Windows pipes default to cp1252; MeshGate prints ✓, — and ·
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import bpy  # only available inside Blender
except ImportError:  # run with plain python — print a hint
    print("This script runs inside Blender: blender -b scene.blend -P <this file> -- --out out.glb")
    sys.exit(2)

import argparse
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshgate_blender import checks, export  # noqa: E402


def _args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser(description="MeshGate export Blender→GLB")
    ap.add_argument("--out", required=True, help="path to the output .glb")
    ap.add_argument("--fbx", action="store_true", help="also write <name>.fbx (Unity/Unreal editor, Humanoid)")
    ap.add_argument("--draco", action="store_true", help="Draco-compress the output GLB itself (web only)")
    ap.add_argument("--targets", default="", help="comma list of web,unity,godot,unreal — adds the engine variants they need")
    ap.add_argument("--profiles", default="", help="comma list of quality tiers (mobile-low,mobile-mid,mobile-high) — writes "
                                                    "<name>.<tier>.glb within each tier's budget (core/profiles.json)")
    ap.add_argument("--selection", action="store_true", help="export only selected objects")
    ap.add_argument("--no-animations", action="store_true", help="do not export animations")
    ap.add_argument("--no-apply-scale", action="store_true", help="do not apply object scale before export")
    ap.add_argument("--image-format", default="AUTO", choices=["AUTO", "PNG", "JPEG", "WEBP"], help="packed texture format")
    ap.add_argument("--check", action="store_true", help="print in-Blender contract issues before exporting")
    ap.add_argument("--fix", action="store_true", help="apply every automatic contract fix before exporting")
    ap.add_argument("--save-fixed", help="with --fix: save the fixed scene to this .blend")
    ap.add_argument("--validate", action="store_true", help="validate every written file; exit 1 if any fails --strict")
    return ap.parse_args(argv)


def _print_issues(title: str, issues) -> None:
    print(f"— MeshGate check ({title}): {len(issues)} issues —")
    for i in issues:
        mark = {"ERROR": "✗", "WARNING": "⚠", "INFO": "·"}[i.severity]
        print(f"  {mark} [{i.code}] {i.label()}" + (f"   (auto-fix: {i.fix})" if i.fix else ""))


def main() -> int:
    args = _args()
    ctx = bpy.context
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]

    if args.check or args.fix:
        _print_issues("before", checks.run_checks(ctx, args.selection, set(targets)))
    if args.fix:
        for line in checks.fix_all(ctx, args.selection):
            print(f"  fixed {line}")
        _print_issues("after", checks.run_checks(ctx, args.selection, set(targets)))
        if args.save_fixed:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save_fixed), copy=True)
            print(f"MeshGate: fixed scene saved -> {args.save_fixed}")

    result = export.export_asset(
        ctx, args.out, targets=targets, fbx=args.fbx, draco=args.draco, selection=args.selection,
        animations=not args.no_animations, image_format=args.image_format,
        apply_scale=not args.no_apply_scale, validate=args.validate,
        profiles=[p.strip() for p in args.profiles.split(",") if p.strip()])

    for path in result.files:
        print(f"MeshGate: exported -> {path} ({os.path.getsize(path) / 1024:.0f} KB)")
    if args.validate:
        print("— MeshGate validate —")
        for line in export.summary_lines(result):
            print("  " + line)
        print("Result: " + ("all files satisfy the contract." if result.ok else "some files do NOT satisfy the contract."))
        return 0 if result.ok else 1
    for note in result.notes:
        print(f"  · {note}")
    return 0


if __name__ == "__main__":
    code = main()
    if code:
        sys.exit(code)
