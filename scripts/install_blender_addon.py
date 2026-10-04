#!/usr/bin/env python3
"""Install (or remove) the MeshGate add-on into your Blender — the same thing Preferences → Install does, in one command.

    python3 scripts/install_blender_addon.py                    # build dist/meshgate-blender-*.zip, install into the Blender found
    python3 scripts/install_blender_addon.py --blender /path/to/blender
    python3 scripts/install_blender_addon.py --all              # every Blender found (MESHGATE_BLENDERS, default, ~/.cache/meshgate/blender)
    python3 scripts/install_blender_addon.py --zip meshgate-blender-0.5.0.zip   # a downloaded release zip
    python3 scripts/install_blender_addon.py --uninstall

What it does, per Blender:
  1. backs up userpref.blend (if you have one) next to it as userpref.blend.meshgate-<time>;
  2. runs Blender headless with YOUR profile: Blender 4.2+ installs the zip as an extension (user_default repo),
     older ones as a legacy add-on; enables it and saves preferences;
  3. starts Blender again and checks the add-on is enabled and its panel is registered.
Close Blender first — a running Blender writes its own preferences on exit and would undo step 2.
"""

import argparse
import datetime
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import meshgate  # noqa: E402  (tool discovery + zip build live in the CLI)

INSTALL = r'''
import os, shutil, sys, addon_utils, bpy
zip_path, action = sys.argv[sys.argv.index("--") + 1:][:2]
new = bpy.app.version >= (4, 2, 0)
module = "bl_ext.user_default.meshgate" if new else "meshgate"
if action == "install":
    if new:
        kw = {"filepath": zip_path, "repo": "user_default", "enable_on_install": True}
        props = {p.identifier for p in bpy.ops.extensions.package_install_files.get_rna_type().properties}
        if "overwrite" in props:
            kw["overwrite"] = True
        bpy.ops.extensions.package_install_files(**kw)
    else:
        bpy.ops.preferences.addon_install(filepath=zip_path, overwrite=True)
    addon_utils.enable(module, default_set=True)
    bpy.ops.wm.save_userpref()
else:
    mod = sys.modules.get(module)
    folder = os.path.dirname(mod.__file__) if mod and getattr(mod, "__file__", None) else None
    addon_utils.disable(module, default_set=True)
    bpy.ops.wm.save_userpref()                 # first forget it in preferences …
    if folder is None:                          # … then delete the files (not enabled → look in the add-on paths)
        bases = list(addon_utils.paths())
        if new:                                 # the EXTENSIONS resource type exists only in 4.2+
            bases.append(bpy.utils.user_resource("EXTENSIONS", path="user_default"))
        for base in bases:
            if base and os.path.isdir(os.path.join(base, "meshgate")):
                folder = os.path.join(base, "meshgate")
                break
    if folder and os.path.basename(folder) == "meshgate" and os.path.isdir(folder):
        shutil.rmtree(folder)
        print("MESHGATE REMOVED", folder)
print("MESHGATE DONE", bpy.utils.user_resource("CONFIG"))
'''

VERIFY = r'''
import os, re, sys, addon_utils, bpy
module = "bl_ext.user_default.meshgate" if bpy.app.version >= (4, 2, 0) else "meshgate"
loaded, enabled = addon_utils.check(module)
mod = sys.modules.get(module)
path = getattr(mod, "__file__", "") or ""
ver = ""
manifest = os.path.join(os.path.dirname(path), "blender_manifest.toml") if path else ""
if manifest and os.path.isfile(manifest):          # extensions (4.2+) take the version from the manifest
    m = re.search(r'^version = "([^"]+)"', open(manifest, encoding="utf-8").read(), re.M)
    ver = m.group(1) if m else ""
elif mod is not None:
    ver = ".".join(map(str, getattr(mod, "bl_info", {}).get("version", ())))
print(f"MESHGATE VERIFY enabled={enabled} panel={hasattr(bpy.types, 'MESHGATE_PT_main')} version={ver} path={path}")
'''


def blender_running(exe: str) -> bool:
    try:
        out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    except Exception:  # noqa: BLE001 — Windows: no ps; we warn in the docs instead
        return False
    real = os.path.realpath(exe)
    return any(line.startswith(real) or line.startswith(exe) for line in out.splitlines() if " -b" not in line and "--background" not in line)


def run_py(exe: str, code: str, *args: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        script = f.name
    try:
        r = subprocess.run([exe, "-b", "-P", script, "--", *args], capture_output=True, text=True, timeout=300)
        return r.stdout + r.stderr
    finally:
        os.unlink(script)


def config_dir(exe: str) -> Path | None:
    out = run_py(exe, 'import bpy; print("MESHGATE CONFIG", bpy.utils.user_resource("CONFIG"))')
    for line in out.splitlines():
        if line.startswith("MESHGATE CONFIG"):
            return Path(line.split(" ", 2)[2].strip())
    return None


def handle(exe: str, zip_path: Path | None, uninstall: bool) -> bool:
    version = meshgate.blender_version(exe)
    print(f"\n— Blender {version}  ({exe})")
    if blender_running(exe):
        print("  ✗ this Blender is running — close it first (it saves its own preferences on exit)")
        return False
    cfg = config_dir(exe)
    if cfg and (cfg / "userpref.blend").exists():
        backup = cfg / f"userpref.blend.meshgate-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        shutil.copy2(cfg / "userpref.blend", backup)
        print(f"  · preferences backed up → {backup}")
    out = run_py(exe, INSTALL, str(zip_path) if zip_path else "-", "uninstall" if uninstall else "install")
    if "MESHGATE DONE" not in out:   # Blender logs harmless tracebacks at startup; judge by our own marker
        print("  ✗ Blender reported an error:\n" + "\n".join("    " + l for l in out.splitlines() if l.strip())[-2000:])
        return False
    check = run_py(exe, VERIFY)
    line = next((l for l in check.splitlines() if l.startswith("MESHGATE VERIFY")), "")
    enabled = "enabled=True" in line and "panel=True" in line
    if uninstall:
        ok = "enabled=False" in line or not line
        print(f"  {'✓' if ok else '✗'} MeshGate removed" if ok else f"  ✗ still enabled: {line}")
        return ok
    if enabled:
        rest = line.replace("MESHGATE VERIFY ", "")
        fields = dict(kv.split("=", 1) for kv in rest.split(" path=")[0].split(" ") if "=" in kv)
        fields["path"] = rest.split(" path=", 1)[1] if " path=" in rest else ""
        print(f"  ✓ MeshGate {fields.get('version', '')} installed and enabled")
        print(f"    {fields.get('path', '')}")
        print("    Open Blender → 3D View → press N → MeshGate tab (also File → Export → MeshGate)")
    else:
        print(f"  ✗ not enabled after install: {line or check[-1500:]}")
    return enabled


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blender", help="path to the Blender executable (default: MESHGATE_BLENDER, PATH, usual install places)")
    ap.add_argument("--all", action="store_true", help="every Blender found")
    ap.add_argument("--zip", help="use this add-on zip instead of building one")
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()

    if args.blender:
        targets = [args.blender]
    elif args.all:
        targets = meshgate.find_blenders()
    else:
        found = meshgate.find_blender()
        targets = [found] if found else []
    if not targets:
        print("✗ Blender not found — pass --blender /path/to/blender or set MESHGATE_BLENDER")
        return 2
    zip_path = None
    if not args.uninstall:
        zip_path = Path(args.zip).resolve() if args.zip else meshgate.build_addon()
        if not zip_path.is_file():
            print(f"✗ zip not found: {zip_path}")
            return 2
    ok = all([handle(exe, zip_path, args.uninstall) for exe in targets])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
