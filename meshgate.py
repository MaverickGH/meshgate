#!/usr/bin/env python3
"""MeshGate CLI — one entry point for the whole pipeline.

    python3 meshgate.py doctor                               # which tools are found
    python3 meshgate.py export scene.blend --out asset.glb [--fbx] [--draco]
    python3 meshgate.py character avatar.glb --out hero.glb  # rigged humanoid → contract (+ idle/wave)
    python3 meshgate.py validate asset.glb [asset.fbx ...] [--strict] [--json]
    python3 meshgate.py serve [--glb samples/asset.glb]
    python3 meshgate.py samples                              # rebuild every demo asset in samples/
    python3 meshgate.py check web|blender|unity|godot|unreal|all   # headless checks; blender = add-on on every Blender
                                                             # found, unreal = plugin vs UE 5.4–5.6 API stubs
    python3 meshgate.py addon                                # build the Blender add-on zip → dist/
    python3 meshgate.py install-blender [--all|--uninstall]  # install + enable the add-on in your Blender
    python3 meshgate.py gen "a cast-iron fire hydrant" [--ai claude] [--tiers ...]   # text → asset per quality tier
    python3 meshgate.py gen --list-ai                        # which AI CLIs are installed (claude, codex, gemini, ollama)
    python3 meshgate.py studio                               # MeshGate Studio: the generation app in your browser

Pure stdlib. Tool paths come from MESHGATE_BLENDER / MESHGATE_UNITY / MESHGATE_GODOT, then PATH,
then the usual install locations on macOS, Linux and Windows.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
BLENDER_SCRIPTS = ROOT / "sources" / "blender"
UNITY_SAMPLE = ROOT / "targets" / "unity" / "MeshGateSample"
GODOT_DEMO = ROOT / "targets" / "godot" / "MeshGateDemo"
DEMO_ASSETS = ["demo", "hero", "lantern", "barrel", "drone"]


# ----------------------------------------------------------------------------
# tool discovery
# ----------------------------------------------------------------------------

def _first_existing(candidates: list[str]) -> str | None:
    for pattern in candidates:
        for path in sorted(glob.glob(os.path.expanduser(pattern)), reverse=True):  # newest version first
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    return None


def find_blender() -> str | None:
    return os.environ.get("MESHGATE_BLENDER") or shutil.which("blender") or _first_existing([
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "~/Applications/Blender.app/Contents/MacOS/Blender",
        "/usr/bin/blender", "/snap/bin/blender", "/opt/blender*/blender",
        "~/blender*/blender", "~/Applications/blender*/blender",   # Linux: the blender.org archive unpacked at home
        "C:/Program Files/Blender Foundation/Blender */blender.exe",
        "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe",
    ])


def find_blenders() -> list[str]:
    """Every Blender to test: MESHGATE_BLENDERS (os.pathsep list), the default one, and ~/.cache/meshgate/blender/*."""
    found = [p for p in os.environ.get("MESHGATE_BLENDERS", "").split(os.pathsep) if p]
    default = find_blender()
    if default:
        found.append(default)
    for app in sorted(glob.glob(os.path.expanduser("~/.cache/meshgate/blender/*"))):
        for exe in (os.path.join(app, "Contents/MacOS/Blender"), os.path.join(app, "blender"), os.path.join(app, "blender.exe")):
            if os.path.isfile(exe):
                found.append(exe)
    unique = []
    for f in found:
        if os.path.realpath(f) not in {os.path.realpath(u) for u in unique}:
            unique.append(f)
    return unique


def blender_version(exe: str) -> str:
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60).stdout
        return out.splitlines()[0].replace("Blender ", "").strip() if out else "?"
    except Exception:  # noqa: BLE001
        return "?"


def find_unity() -> str | None:
    return os.environ.get("MESHGATE_UNITY") or _first_existing([
        "/Applications/Unity/Hub/Editor/6000.*/Unity.app/Contents/MacOS/Unity",
        "~/Unity/Hub/Editor/6000.*/Editor/Unity",
        "C:/Program Files/Unity/Hub/Editor/6000.*/Editor/Unity.exe",
    ])


def find_godot() -> str | None:
    return os.environ.get("MESHGATE_GODOT") or shutil.which("godot") or shutil.which("godot4") or _first_existing([
        "/Applications/Godot.app/Contents/MacOS/Godot",
        "~/Applications/Godot.app/Contents/MacOS/Godot",
        "C:/Program Files/Godot*/Godot*.exe",
    ])


def find_unreal() -> str | None:
    return os.environ.get("MESHGATE_UNREAL") or _first_existing([
        "/Users/Shared/Epic Games/UE_5.*/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor",
        "C:/Program Files/Epic Games/UE_5.*/Engine/Binaries/Win64/UnrealEditor.exe",
        "~/UnrealEngine/Engine/Binaries/Linux/UnrealEditor",
    ])


PLUGINS = {   # what MeshGate installs into each tool, relative to the MeshGate files
    "blender": "sources/blender/meshgate_blender",
    "unity": "targets/unity/com.meshgate.unity",
    "godot": "targets/godot/MeshGateDemo/addons/meshgate",
    "unreal": "targets/unreal/MeshGate",
}
HOW = {
    "blender": "Studio → Install add-on, or python3 meshgate.py install-blender (close Blender first)",
    "unity": "Package Manager → Add package from disk → com.meshgate.unity/package.json (plus glTFast from the registry)",
    "godot": "copy the meshgate folder to res://addons/ and enable it in Project → Plugins",
    "unreal": "copy the MeshGate folder to <Project>/Plugins/, enable Python Editor Script Plugin and Interchange",
}


def _version_from_path(path: str, pattern: str) -> str | None:
    import re as _re
    m = _re.search(pattern, path.replace("\\", "/"))
    return m.group(1) if m else None


def tools_status() -> dict:
    """Everything MeshGate can connect to on this machine — for `doctor` and the Studio status screen."""
    blender = find_blender()
    unity, godot, unreal = find_unity(), find_godot(), find_unreal()
    godot_ver = None
    if godot:
        try:
            godot_ver = subprocess.run([godot, "--version"], capture_output=True, text=True, timeout=15).stdout.strip().split(".stable")[0] or None
        except (OSError, subprocess.TimeoutExpired):
            godot_ver = None
    info = {
        "python": {"path": sys.executable, "version": platform.python_version(), "ok": sys.version_info >= (3, 9)},
        "blender": {"path": blender, "version": blender_version(blender).split()[0] if blender else None,
                    "addon": _addon_installed(blender), "url": "https://www.blender.org/download/"},
        "unity": {"path": unity, "version": _version_from_path(unity or "", r"Editor/(\d[^/]+)/"), "url": "https://unity.com/download"},
        "godot": {"path": godot, "version": godot_ver, "url": "https://godotengine.org/download"},
        "unreal": {"path": unreal, "version": _version_from_path(unreal or "", r"UE_(\d[\d.]*)"), "url": "https://www.unrealengine.com/download"},
        "node": {"path": shutil.which("node"), "version": None, "url": "https://nodejs.org"},
    }
    for tool, rel in PLUGINS.items():
        folder = ROOT / rel
        info[tool]["plugin"] = str(folder) if folder.exists() else None
        info[tool]["how"] = HOW[tool]
    return info


def need(tool: str | None, name: str, env: str) -> str:
    if not tool:
        sys.exit(f"✗ {name} not found. Install it or set {env}=/path/to/{name.lower()}")
    return tool


def run(cmd: list[str], **kw) -> int:
    print("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    return subprocess.call(cmd, **kw)


# ----------------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------------

def _addon_installed(blender_exe: str | None) -> str | None:
    """Where the MeshGate add-on sits in this Blender's user profile (extension or legacy add-on), if anywhere."""
    if not blender_exe:
        return None
    ver = blender_version(blender_exe).split()[0]
    major_minor = ".".join(ver.split(".")[:2])
    homes = {"Darwin": Path.home() / "Library" / "Application Support" / "Blender",
             "Windows": Path(os.environ.get("APPDATA", "")) / "Blender Foundation" / "Blender"}
    base = homes.get(platform.system(), Path.home() / ".config" / "blender") / major_minor
    for cand in (base / "extensions" / "user_default" / "meshgate", base / "scripts" / "addons" / "meshgate"):
        if (cand / "__init__.py").exists():
            return str(cand)
    return None


def cmd_doctor(_args) -> int:
    blender = find_blender()
    rows = [
        ("python", sys.executable, platform.python_version()),
        ("blender", blender, blender_version(blender) if blender else "needed for export, gen, samples"),
        ("unity", find_unity(), "check unity (6000.0+)"),
        ("godot", find_godot(), "check godot (4.4+)"),
        ("unreal", find_unreal(), "UE 5.4–5.6, plugin in targets/unreal"),
        ("node", shutil.which("node"), "npm installs the AI tools"),
    ]
    width = 16
    print("Tools:")
    for name, path, note in rows:
        print(f"  {'✓' if path else '·'} {name.ljust(width)}{path or 'not found'}   ({note})")
    addon = _addon_installed(blender)
    print(f"  {'✓' if addon else '·'} {'blender add-on'.ljust(width)}{addon or 'not installed — python3 meshgate.py install-blender'}")

    sys.path.insert(0, str(ROOT / "sources" / "generate"))
    import generate
    import mesh
    ai = generate.available_ai()
    providers = mesh.status()
    images = mesh.images.available()
    print("Generation (meshgate.py gen, MeshGate Studio):")
    login = {name: generate.signed_in(name) if path else None for name, path in ai.items()}
    for name, path in ai.items():
        note = "" if login[name] is not False else "   (not signed in)"
        print(f"  {'✓' if path and login[name] is not False else '·'} {('ai: ' + name).ljust(width)}"
              f"{path or 'not installed — ' + generate.ADAPTERS[name]['url']}{note}")
    for pid, info in providers.items():
        if pid == "command":
            continue
        need = info.get("needs") or (f"set {info['key_env']}" if info.get("key_env") else "")
        print(f"  {'✓' if info['ready'] else '·'} {('mesh: ' + pid).ljust(width)}{'ready' if info['ready'] else need}")
    for name, ok in images.items():
        print(f"  {'✓' if ok else '·'} {('image: ' + name).ljust(width)}{'ready' if ok else 'set ' + mesh.images.PROVIDERS[name]}")
    import components
    print("Optional components (installed separately):")
    for cid, c in components.status().items():
        if cid == "triposr":
            continue
        state = ("installed" + (f" — then {c['missing']}" if c["missing"] else "")) if c["installed"] else \
            f"not installed — python3 meshgate.py gen --setup {cid} ({c['size']}, {c['gpu']})"
        print(f"  {'✓' if c['installed'] and not c['missing'] else '·'} {cid.ljust(width)}{state}")

    tips = []
    if not blender:
        tips.append("install Blender 3.5+ (https://www.blender.org/download/) or set MESHGATE_BLENDER")
    elif not addon:
        tips.append("put the add-on into Blender: python3 meshgate.py install-blender")
    if not any(ai.values()):
        tips.append("for text → 3D install one AI CLI (Claude Code, Codex, Gemini or Ollama) and sign in once")
    for name, state in login.items():
        if state is False:
            tips.append(f"{name} is installed but not signed in: {generate.LOGIN_HINTS[name]}")
    if not providers["triposr"]["ready"]:
        tips.append("for picture → 3D without keys: python3 meshgate.py gen --setup triposr (~3 GB, MIT)")
    if tips:
        print("Next:")
        for t in tips:
            print(f"  → {t}")
    return 0


def cmd_export(args) -> int:
    blender = need(find_blender(), "Blender", "MESHGATE_BLENDER")
    cmd = [blender, "-b", str(Path(args.blend).resolve()), "-P", str(BLENDER_SCRIPTS / "export_meshgate.py"), "--",
           "--out", str(Path(args.out).resolve()), "--validate"]
    for flag in ("fbx", "draco", "selection", "no_animations"):
        if getattr(args, flag):
            cmd.append("--" + flag.replace("_", "-"))
    if args.image_format:
        cmd += ["--image-format", args.image_format]
    if args.targets:
        cmd += ["--targets", args.targets]
    if args.profiles:
        cmd += ["--profiles", args.profiles]
    return run(cmd)


def cmd_character(args) -> int:
    blender = need(find_blender(), "Blender", "MESHGATE_BLENDER")
    out = Path(args.out).resolve()
    blend = out.with_suffix(".blend")
    cmd = [blender, "-b", "-P", str(BLENDER_SCRIPTS / "animate_humanoid.py"), "--", "--in", str(Path(args.src).resolve()), "--blend", str(blend)]
    if args.no_anim:
        cmd.append("--no-anim")
    code = run(cmd)
    if code:
        return code
    return run([blender, "-b", str(blend), "-P", str(BLENDER_SCRIPTS / "export_meshgate.py"), "--", "--out", str(out), "--fbx", "--validate"])


def cmd_validate(args) -> int:
    worst = 0
    glbs = [f for f in args.files if f.lower().endswith((".glb", ".gltf"))]
    fbxs = [f for f in args.files if f.lower().endswith(".fbx")]
    extra = (["--strict"] if args.strict else []) + (["--json"] if args.json else [])
    if glbs:
        worst = max(worst, subprocess.call([sys.executable, str(ROOT / "core" / "validate_glb.py"), *glbs, *extra]))
    if fbxs:
        worst = max(worst, subprocess.call([sys.executable, str(ROOT / "core" / "validate_fbx.py"), *fbxs, *extra]))
    if not glbs and not fbxs:
        sys.exit("✗ pass .glb or .fbx files")
    return worst


def cmd_serve(args) -> int:
    cmd = [sys.executable, str(ROOT / "targets" / "web" / "serve.py"), "--port", str(args.port)]
    if args.glb:
        cmd += ["--glb", os.path.relpath(Path(args.glb).resolve(), ROOT)]
    if args.no_browser:
        cmd.append("--no-browser")
    return run(cmd)


def cmd_samples(args) -> int:
    blender = need(find_blender(), "Blender", "MESHGATE_BLENDER")
    steps = [
        [blender, "-b", "-P", str(BLENDER_SCRIPTS / "make_demo_scene.py"), "--", "--blend", str(SAMPLES / "meshgate_demo.blend")],
        [blender, "-b", "-P", str(BLENDER_SCRIPTS / "make_demo_character.py"), "--", "--blend", str(SAMPLES / "meshgate_hero.blend")],
        [blender, "-b", "-P", str(BLENDER_SCRIPTS / "make_demo_props.py"), "--", "--out-dir", str(SAMPLES)],
    ]
    for name in DEMO_ASSETS:
        steps.append([blender, "-b", str(SAMPLES / f"meshgate_{name}.blend"), "-P", str(BLENDER_SCRIPTS / "export_meshgate.py"), "--",
                      "--out", str(SAMPLES / f"meshgate_{name}.glb"), "--fbx", "--validate"])
    steps.append([blender, "-b", str(SAMPLES / "meshgate_demo.blend"), "-P", str(BLENDER_SCRIPTS / "export_meshgate.py"), "--",
                  "--out", str(SAMPLES / "meshgate_demo.draco.glb"), "--draco", "--validate"])
    steps.append([blender, "-b", "-P", str(BLENDER_SCRIPTS / "make_pack_zombie_cats.py"), "--", "--out-dir", str(SAMPLES / "packs" / "zombie_cats")])
    steps.append([sys.executable, str(ROOT / "sources" / "generate" / "make_generated_pack.py"), "--blender", blender])   # the generated pack
    for step in steps:
        if args.only and not any(args.only in part for part in step):
            continue
        code = run(step, stdout=subprocess.DEVNULL if args.quiet else None)
        if code:
            return code
    return cmd_validate(argparse.Namespace(files=[str(p) for p in sorted(SAMPLES.glob("*.glb")) + sorted(SAMPLES.glob("*.fbx"))], strict=True, json=False))


def _check_web() -> int:
    code = cmd_validate(argparse.Namespace(files=[str(p) for p in sorted(SAMPLES.glob("*.glb"))], strict=True, json=False))
    code = max(code, subprocess.call([sys.executable, str(ROOT / "tests" / "check_profiles.py")]))   # tiers identical everywhere
    code = max(code, subprocess.call([sys.executable, str(ROOT / "tests" / "generate" / "test_generate.py")]))   # gen: safety, prompt
    code = max(code, subprocess.call([sys.executable, str(ROOT / "tests" / "generate" / "test_library.py")]))   # free-model library
    code = max(code, subprocess.call([sys.executable, str(ROOT / "tests" / "generate" / "test_mcp.py")]))   # MCP server protocol
    code = max(code, subprocess.call([sys.executable, str(ROOT / "tests" / "studio" / "test_server.py")]))   # studio: token, host, paths
    code = max(code, subprocess.call([sys.executable, str(ROOT / "tests" / "generate" / "test_providers.py")]))   # cloud generators
    code = max(code, subprocess.call([sys.executable, str(ROOT / "tests" / "check_links.py")]))   # docs: links + translations
    code = max(code, subprocess.call([sys.executable, str(ROOT / "tests" / "studio" / "test_ui_strings.py")]))   # UI labels
    node = shutil.which("node")
    if node:
        for js in ("app.js", "meshgate-viewer.js"):
            code = max(code, subprocess.call([node, "--check", str(ROOT / "targets" / "web" / js)]))
    print("web: samples valid" + (", JS syntax ok" if node else "") + ("" if code == 0 else " — FAILED"))
    return code


def _check_unity(render: bool) -> int:
    unity = need(find_unity(), "Unity", "MESHGATE_UNITY")
    logs = Path(tempfile.mkdtemp(prefix="meshgate-unity-"))
    code = run([unity, "-batchmode", "-nographics", "-projectPath", str(UNITY_SAMPLE), "-executeMethod", "MeshGateSampleTools.BuildAll",
                "-quit", "-logFile", str(logs / "build.log")])
    if code:
        print(f"✗ unity: BuildAll failed — see {logs / 'build.log'}")
        return code
    results = logs / "playmode.xml"
    test_cmd = [unity, "-batchmode", "-projectPath", str(UNITY_SAMPLE), "-runTests", "-testPlatform", "PlayMode",
                "-testResults", str(results), "-logFile", str(logs / "tests.log")]
    if not render:
        test_cmd.insert(2, "-nographics")
    run(test_cmd)
    if not results.exists():
        print(f"✗ unity: no test results — see {logs / 'tests.log'}")
        return 1
    import xml.etree.ElementTree as ET
    r = ET.parse(results).getroot()
    failed = int(r.get("failed", "0"))
    skipped = int(r.get("skipped", "0")) + int(r.get("inconclusive", "0"))
    print(f"unity: {r.get('passed')}/{r.get('total')} PlayMode tests passed"
          + (f", {skipped} skipped (the scene render needs --render)" if skipped and not render else f", {skipped} skipped" if skipped else "")
          + (f", {failed} failed — see {results}" if failed else ""))
    for tc in r.iter("test-case"):
        if tc.get("result") == "Failed":
            msg = tc.find("failure/message")
            print(f"  ✗ {tc.get('name')}: {(msg.text or '').strip()[:300] if msg is not None else ''}")
    return 1 if failed else 0


def _check_godot() -> int:
    godot = need(find_godot(), "Godot", "MESHGATE_GODOT")
    dest = GODOT_DEMO / "samples"
    dest.mkdir(exist_ok=True)
    for glb in SAMPLES.glob("meshgate_*.glb"):
        shutil.copy2(glb, dest / glb.name)
    if not (GODOT_DEMO / ".godot").exists():
        subprocess.call([godot, "--headless", "--path", str(GODOT_DEMO), "--import"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return run([godot, "--headless", "--path", str(GODOT_DEMO), "-s", "tests/test_meshgate.gd"])


def build_addon() -> Path:
    # inside the desktop app the MeshGate files are read-only: build the zip in a temporary folder then
    out_dir = ROOT / "dist" if os.access(ROOT, os.W_OK) else Path(tempfile.mkdtemp(prefix="meshgate-addon-"))
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_blender_addon.py"), "--out-dir", str(out_dir)],
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit(out.stdout + out.stderr)
    print(out.stdout.strip())
    return Path(out.stdout.split()[1])


def _check_blender(generators: bool = True) -> int:
    blenders = find_blenders()
    if not blenders:
        need(None, "Blender", "MESHGATE_BLENDER")
    zip_path = build_addon()
    rows, worst = [], 0
    for exe in blenders:
        ver = blender_version(exe)
        work = Path(tempfile.mkdtemp(prefix=f"meshgate-blender-{ver.split()[0]}-"))
        prof = work / "profile"
        env = {**os.environ, "BLENDER_USER_RESOURCES": str(prof), "BLENDER_USER_SCRIPTS": str(prof / "scripts"),
               "BLENDER_USER_CONFIG": str(prof / "config"), "BLENDER_USER_DATAFILES": str(prof / "datafiles")}
        print(f"\n--- Blender {ver} ({exe})")
        code = subprocess.call([exe, "-b", "--factory-startup", "-P", str(ROOT / "tests" / "blender" / "test_addon.py"), "--",
                                "--zip", str(zip_path), "--out", str(work / "addon"), "--samples", str(SAMPLES)],
                               env=env, stdout=open(work / "addon.log", "w"), stderr=subprocess.STDOUT)
        try:
            res = json.load(open(work / "addon" / "result.json"))
            failed = [s for s in res["steps"] if not s["ok"]]
            passed = len(res["steps"]) - len(failed)
            status = f"add-on {passed}/{len(res['steps'])}"
            for s_ in failed:
                print(f"  ✗ {s_['step']}: {s_['detail'][:400]}")
        except Exception:  # noqa: BLE001
            status, code = "add-on: no result (see log)", code or 1
        ai_ok = _check_generation(exe, work / "gen")
        status += f", gen {'ok' if ai_ok else 'FAILED'}"
        code = code or (0 if ai_ok else 1)
        gen_status = "—"
        if generators:
            gen_dir = work / "samples"
            gen_ok = True
            scripts = [["make_demo_scene.py", "--blend", str(gen_dir / "meshgate_demo.blend")],
                       ["make_demo_character.py", "--blend", str(gen_dir / "meshgate_hero.blend")],
                       ["make_demo_props.py", "--out-dir", str(gen_dir)]]
            for script, *rest in scripts:
                r = subprocess.run([exe, "-b", "--factory-startup", "-P", str(BLENDER_SCRIPTS / script), "--", *rest],
                                   env=env, capture_output=True, text=True)
                if r.returncode or "Traceback" in r.stdout + r.stderr:
                    gen_ok = False
                    print(f"  ✗ {script}: " + (r.stdout + r.stderr)[-800:])
            made = sorted(gen_dir.glob("meshgate_*.blend"))
            for blend in made:
                r = subprocess.run([exe, "-b", str(blend), "-P", str(BLENDER_SCRIPTS / "export_meshgate.py"), "--",
                                    "--out", str(blend.with_suffix(".glb")), "--fbx", "--validate"], env=env, capture_output=True, text=True)
                if r.returncode:
                    gen_ok = False
                    print(f"  ✗ export {blend.name}: " + (r.stdout + r.stderr)[-800:])
            expected = {"demo": ["beacon_spin", "lid_open"], "hero": ["idle", "wave"], "lantern": ["flicker", "swing"], "barrel": [], "drone": ["hover", "rotors"]}
            for name, want in expected.items():
                glb = gen_dir / f"meshgate_{name}.glb"
                if glb.exists():
                    rep = json.loads(subprocess.run([sys.executable, str(ROOT / "core" / "validate_glb.py"), str(glb), "--json"], capture_output=True, text=True).stdout)
                    if sorted(rep.get("animations", [])) != want:
                        gen_ok = False
                        print(f"  ✗ {glb.name}: clips {sorted(rep.get('animations', []))}, expected {want}")
            # the example pack: every asset exported + validated inside the generator, clip names checked here
            pack_dir = gen_dir / "packs" / "zombie_cats"
            r = subprocess.run([exe, "-b", "--factory-startup", "-P", str(BLENDER_SCRIPTS / "make_pack_zombie_cats.py"), "--",
                                "--out-dir", str(pack_dir)], env=env, capture_output=True, text=True)
            pack_ok = r.returncode == 0 and "every asset satisfies the contract" in r.stdout
            try:
                idx = json.load(open(pack_dir / "index.json"))
                clips = {a["file"]: sorted(a["clips"]) for a in idx["assets"]}
                pack_ok &= len(idx["assets"]) == 12 and clips.get("zc_zombie_cat.glb") == ["idle", "shamble"] \
                    and clips.get("zc_diorama.glb") == ["bubbles", "idle", "shamble", "swing", "yarn_swing"]
            except Exception:  # noqa: BLE001
                pack_ok = False
            if not pack_ok:
                gen_ok = False
                print("  ✗ zombie cats pack: " + (r.stdout + r.stderr)[-800:])
            gen_status = f"generators {'ok' if gen_ok and len(made) == 5 else 'FAILED'} ({len(made)}/5 assets, pack {'12/12' if pack_ok else 'FAILED'})"
            code = code or (0 if gen_ok and len(made) == 5 else 1)
        rows.append((ver, status, gen_status, "ok" if code == 0 else "FAILED", work))
        worst = max(worst, 1 if code else 0)
    print("\nBlender compatibility:")
    for ver, st, gen, verdict, work in rows:
        print(f"  {verdict:6}  Blender {ver:<14} {st:<16} {gen}   logs: {work}")
    return worst


def _check_generation(exe: str, work: Path) -> bool:
    """Text-to-asset without a real AI: a stand-in CLI answers broken code first, then the fix — the whole
    ask → build → feedback → fix loop — and the animated chest example runs through --code."""
    import shlex
    ok = True
    fake = f"{shlex.quote(sys.executable)} {shlex.quote(str(ROOT / 'tests' / 'generate' / 'fake_ai.py'))}"
    runs = {"hydrant": ["a fire hydrant", "--ai-cmd", fake, "--size", "0.8"],
            "chest": ["--code", str(ROOT / "sources" / "generate" / "examples" / "treasure_chest.py"), "--collision", "box"]}
    for name, extra in runs.items():
        out = work / name
        r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", *extra, "--name", name, "--blender", exe,
                            "--out-dir", str(out)], capture_output=True, text=True)
        try:
            g = json.load(open(out / "gen.json"))
            rep = g["report"]
            tiers = rep["tiers"]
            tris = [tiers[t]["tris"] for t in ("mobile-low", "mobile-mid", "mobile-high", "pc")]
            good = g["ok"] and all(tiers[t]["within_budget"] for t in tiers) and tris == sorted(tris) and tris[0] < tris[-1]
            if name == "hydrant":
                good &= len(g["attempts"]) == 2 and "part kind 'barrel'" in g["attempts"][0]["problems"][0]
            else:
                good &= tiers["pc"]["clips"] == ["open"] and "chest.unreal.fbx" in rep["files"] and "chest.godot.glb" in rep["files"]
        except Exception as exc:  # noqa: BLE001
            good = False
            print(f"  ✗ gen {name}: {exc}")
        if not good:
            ok = False
            print(f"  ✗ gen {name}: " + (r.stdout + r.stderr)[-1200:])
    ok &= _check_refine(exe, work)
    ok &= _check_vertex_and_caps(exe, work)
    ok &= _check_hidden(exe, work)
    ok &= _check_finish(exe, work)
    ok &= _check_sculpt(exe, work)
    ok &= _check_rework(exe, work)
    ok &= _check_blender_tools(exe, work)
    ok &= _check_review(exe, work)
    ok &= _check_character(exe, work)
    ok &= _check_facts(exe, work)
    ok &= _check_hard_surface(exe, work)
    ok &= _check_relations(exe, work)
    ok &= _check_live(exe, work)
    ok &= _check_instances(exe, work)
    ok &= _check_tiles(exe, work)
    ok &= _check_modules(exe, work)
    ok &= _check_quality(exe, work)
    ok &= _check_concept(exe, work)
    if exe == (find_blenders() or [exe])[0]:   # Studio's Cancel stops the Blender of a job that never ends
        r = subprocess.run([sys.executable, str(ROOT / "tests" / "studio" / "test_cancel.py"), "--blender", exe],
                           capture_output=True, text=True)
        if r.returncode:
            ok = False
            print("  ✗ cancel: " + (r.stdout + r.stderr)[-600:])
        else:
            print("  ✓ Studio cancel stops Blender")
    return ok


def _check_concept(exe: str, work: Path) -> bool:
    """Text → concept sheet → kit code with a stand-in Codex CLI (it draws out.png and answers with build code): the
    sheet is drawn, handed to the AI with the rules for reading the views, and the model builds on every tier."""
    import stat
    shim_dir = work / "codex-shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    fake = ROOT / "tests" / "generate" / "fake_codex.py"
    if os.name == "nt":
        (shim_dir / "codex.cmd").write_text(f'@"{sys.executable}" "{fake}" %*\n')
    else:
        shim = shim_dir / "codex"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PATH": str(shim_dir) + os.pathsep + os.environ.get("PATH", "")}
    out = work / "concept"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "a cast-iron street lamp", "--name", "lamp",
                        "--concept", "sheet", "--ai", "codex", "--image-provider", "codex", "--blender", exe, "--no-preview",
                        "--out-dir", str(out)], capture_output=True, text=True, env=env)
    try:
        g = json.load(open(out / "gen.json"))
        first = (out / "attempt_1.py").read_text().splitlines()[0]
        good = g["ok"] and g.get("concept") == "sheet" and (out / "concept.png").exists() \
            and "reference=True" in first and "sheet_rules=True" in first
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ concept: {exc}")
    if not good:
        print("  ✗ concept sheet → kit code: " + (r.stdout + r.stderr)[-800:])
    return good


def _check_vertex_and_caps(exe: str, work: Path) -> bool:
    """--colors vertex and --tris on both engines: no textures, COLOR_0 present, every tier within your limit."""
    ok = True
    runs = {"vc_kit": ["--code", str(ROOT / "sources" / "generate" / "examples" / "toxic_can.py"), "--tris", "low=600,pc=4000"],
            "vc_mesh": ["--mesh", str(ROOT / "sources" / "generate" / "examples" / "hydrant_triposr_raw.glb"), "--size", "0.8",
                        "--tris", "300"]}
    for name, extra in runs.items():
        out = work / name
        r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", *extra, "--colors", "vertex", "--name", name,
                            "--blender", exe, "--no-preview", "--out-dir", str(out)], capture_output=True, text=True)
        try:
            g = json.load(open(out / "gen.json"))
            tiers, caps = g["report"]["tiers"], g["caps"]
            good = g["ok"] and all(t["tris"] <= caps.get(k, 10 ** 9) for k, t in tiers.items())
            for k, t in tiers.items():
                rep = json.loads(subprocess.run([sys.executable, str(ROOT / "core" / "validate_glb.py"), str(out / t["file"]), "--json"],
                                                capture_output=True, text=True).stdout)
                rep = rep[0] if isinstance(rep, list) else rep
                with open(out / t["file"], "rb") as f:
                    head = f.read(20)
                    js = json.loads(f.read(int.from_bytes(head[12:16], "little")))
                has_color = all("COLOR_0" in p_["attributes"] for m in js["meshes"] for p_ in m["primitives"])
                good &= rep.get("textures", 1) == 0 and has_color
        except Exception as exc:  # noqa: BLE001
            good = False
            print(f"  ✗ {name}: {exc}")
        if not good:
            ok = False
            print(f"  ✗ vertex colours + limits ({name}): " + (r.stdout + r.stderr)[-800:])
    return ok


def _check_hidden(exe: str, work: Path) -> bool:
    """Faces hidden inside another closed piece go; faces that cross its surface stay (no holes, same size)."""
    out = work / "hidden"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "hidden_parts.py"),
                        "--name", "hidden", "--blender", exe, "--no-preview", "--out-dir", str(out)], capture_output=True, text=True)
    try:
        pc = json.load(open(out / "gen.json"))["report"]["tiers"]["pc"]
        removed = int(re.search(r"removed (\d+) hidden faces", " ".join(pc["notes"])).group(1))
        # ico (80) + the arm's inner cap (1 n-gon); box 12 + arm 12 sides × 2 + outer cap 10 triangles stay
        good = removed == 81 and pc["tris"] == 12 + 24 + 10 and abs(pc["dims_m"][0] - 1.4) < 0.01
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ hidden faces: {exc}")
    if not good:
        print("  ✗ hidden faces: " + (r.stdout + r.stderr)[-800:])
    return good


def _check_sculpt(exe: str, work: Path) -> bool:
    """The artist tools (blob, skin, cut, bend, twist, sculpt, eye) build on every tier, lighter on phones, with the bend
    in the right place; the realistic finish bakes every tier's relief from the dense hero model (high → low)."""
    out = work / "sculpt"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "sculpt_tools.py"),
                        "--name", "sculpt", "--style", "realistic", "--tiers", "pc,mobile-mid,mobile-low", "--blender", exe,
                        "--no-preview", "--out-dir", str(out)], capture_output=True, text=True)
    try:
        g = json.load(open(out / "gen.json"))
        t = g["report"]["tiers"]
        pc, mid, low = t["pc"], t["mobile-mid"], t["mobile-low"]
        good = (g["ok"] and pc["tris"] > mid["tris"] > low["tris"] and abs(pc["dims_m"][0] - 0.97) < 0.03
                and abs(pc["dims_m"][2] - 0.82) < 0.03
                and any("relief from the hero model" in n for n in mid["notes"] + pc["notes"])
                and all(x["within_budget"] for x in t.values()))
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ sculpt tools: {exc}")
    if not good:
        print("  ✗ sculpt tools: " + (r.stdout + r.stderr)[-1200:])
    return good


def _check_rework(exe: str, work: Path) -> bool:
    """mg.model reworks a library model (a stand-in in a temporary library): only the kept part, repainted, credited."""
    lib = work / "rework_config" / "library" / ("0" * 32)
    lib.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "sources" / "generate" / "examples" / "hydrant_triposr_raw.glb", lib / "model.glb")
    (lib / "credit.json").write_text(json.dumps({"uid": "0" * 32, "name": "Stand-in hydrant", "author": "MeshGate tests",
                                                 "url": "https://example.test/model", "license": "cc0", "license_name": "CC0",
                                                 "license_url": None, "file": "model.glb"}))
    out = work / "rework"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "rework_model.py"),
                        "--name", "rework", "--style", "realistic", "--tiers", "pc,mobile-low", "--blender", exe, "--no-preview",
                        "--out-dir", str(out)], capture_output=True, text=True,
                       env={**os.environ, "MESHGATE_CONFIG_DIR": str(work / "rework_config")})
    try:
        g = json.load(open(out / "gen.json"))
        pc = g["report"]["tiers"]["pc"]
        good = (g["ok"] and 0.6 < pc["dims_m"][2] < 0.72 and g.get("credit") and g["credit"][0]["name"] == "Stand-in hydrant"
                and "Stand-in hydrant" in (out / "CREDITS.txt").read_text())
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ rework a library model: {exc}")
    if not good:
        print("  ✗ rework a library model: " + (r.stdout + r.stderr)[-1200:])
    return good


def _check_blender_tools(exe: str, work: Path) -> bool:
    """Spline curves, scatter and modifiers build on every tier (fewer copies and segments on phones), same size."""
    out = work / "blender_tools"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "blender_tools.py"),
                        "--name", "tools2", "--tiers", "pc,mobile-low", "--blender", exe, "--no-preview", "--out-dir", str(out)],
                       capture_output=True, text=True)
    try:
        g = json.load(open(out / "gen.json"))
        pc, low = g["report"]["tiers"]["pc"], g["report"]["tiers"]["mobile-low"]
        good = (g["ok"] and pc["tris"] > low["tris"] and abs(pc["dims_m"][0] - 1.45) < 0.03 and abs(pc["dims_m"][2] - 0.607) < 0.03
                and abs(low["dims_m"][0] - pc["dims_m"][0]) < 0.02)
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ curves, scatter, modifiers: {exc}")
    if not good:
        print("  ✗ curves, scatter, modifiers: " + (r.stdout + r.stderr)[-1200:])
    return good


def _check_review(exe: str, work: Path) -> bool:
    """Stage 3 with a stand-in AI: the model is rendered next to the reference, the AI sees that sheet, its improved code
    replaces the model only after a clean build, and the loop stops at MATCH 9/10."""
    import shlex
    out = work / "review"
    fake = f"{shlex.quote(sys.executable)} {shlex.quote(str(ROOT / 'tests' / 'generate' / 'fake_ai.py'))}"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "a fire hydrant", "--ai-cmd", fake, "--engine", "kit",
                        "--image", str(ROOT / "sources" / "generate" / "examples" / "hydrant_picture.png"), "--review", "2",
                        "--tiers", "pc,mobile-low", "--name", "review", "--blender", exe, "--no-preview", "--out-dir", str(out)],
                       capture_output=True, text=True)
    try:
        g = json.load(open(out / "gen.json"))
        rv = g["report"]["reviews"]
        good = (g["ok"] and [x["match"] for x in rv] == [6.0, 9.0] and rv[0]["accepted"] and not rv[1]["accepted"]
                and rv[0].get("closeups") == [{"at": [0.0, 0.0, 0.4], "from": [1.0, -1.0, 0.5], "size": 0.3}]
                and all("attached" in x["notes"][0] for x in rv) and "#d0342a" in (out / "review.py").read_text()
                and (out / "views.png").exists() and (out / "review_1.png").exists())
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ visual review loop: {exc}")
    if not good:
        print("  ✗ visual review loop: " + (r.stdout + r.stderr)[-1500:])
    return good


def _check_character(exe: str, work: Path) -> bool:
    """A kit character: Humanoid skeleton, three clips, bones per vertex within each tier, cutout fur cards on the
    rich tiers only, the same size on every tier (measured in the rest pose)."""
    out = work / "character"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "character_rig.py"),
                        "--name", "critter", "--tiers", "pc,mobile-low", "--targets", "web,unity", "--blender", exe,
                        "--no-preview", "--out-dir", str(out)], capture_output=True, text=True)
    try:
        g = json.load(open(out / "gen.json"))
        t = g["report"]["tiers"]
        reps = {k: json.loads(subprocess.run([sys.executable, str(ROOT / "core" / "validate_glb.py"), str(out / v["file"]),
                                               "--json", "--profile", k], capture_output=True, text=True).stdout) for k, v in t.items()}
        reps = {k: (v[0] if isinstance(v, list) else v) for k, v in reps.items()}
        mats = {k: [m.get("alphaMode") for m in _glb_json(out / v["file"])["materials"]] for k, v in t.items()}
        good = (g["ok"] and all(r_.get("humanoid") for r_ in reps.values())
                and all(sorted(r_.get("animations", [])) == ["attack", "idle", "walk"] for r_ in reps.values())
                and reps["pc"]["max_influences"] <= 4 and reps["mobile-low"]["max_influences"] <= 2
                and "MASK" in mats["pc"] and "MASK" not in mats["mobile-low"]
                and abs(t["pc"]["dims_m"][2] - t["mobile-low"]["dims_m"][2]) < 0.03)
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ character (rig, clips, fur): {exc}")
    if not good:
        print("  ✗ character (rig, clips, fur): " + (r.stdout + r.stderr)[-1500:])
    return good


def _check_facts(exe: str, work: Path) -> bool:
    """Geometry facts: a cup floating above a table is reported by its code line (and nothing that stands is),
    and it reaches the AI as advice."""
    out = work / "facts"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "facts_test.py"),
                        "--name", "facts", "--tiers", "pc,mobile-low", "--blender", exe, "--no-preview", "--out-dir", str(out)],
                       capture_output=True, text=True)
    try:
        g = json.load(open(out / "gen.json"))
        fl = g["report"]["facts"]["floating"]
        good = (g["ok"] and [f["line"] for f in fl] == [9] and 4 <= fl[0]["gap_cm"] <= 8
                and any("line 9" in a for a in g["report"]["advice"]) and g["report"]["tiers"]["pc"]["tris"] < 60000)
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ geometry facts: {exc}")
    if not good:
        print("  ✗ geometry facts: " + (r.stdout + r.stderr)[-1200:])
    return good


def _check_hard_surface(exe: str, work: Path) -> bool:
    """Hard-surface tools: inset panels, a swept frame with mitred corners, weighted normals, and baked UVs that use the
    texture well (area covered, even texel density), reported to the AI."""
    out = work / "hard_surface"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "hard_surface.py"),
                        "--name", "crate", "--pbr", "--tiers", "pc,mobile-low", "--blender", exe, "--no-preview",
                        "--out-dir", str(out)], capture_output=True, text=True)
    try:
        g = json.load(open(out / "gen.json"))
        pc = g["report"]["tiers"]["pc"]
        uv = g["report"]["facts"]["uv"]
        good = (g["ok"] and abs(pc["dims_m"][0] - 0.837) < 0.03 and abs(pc["dims_m"][2] - 0.725) < 0.03
                and any("weighted normals" in n for n in pc["notes"]) and uv["used"] > 0.3 and uv["density_spread"] < 0.35)
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ hard surface (inset, sweep, weighted normals, UVs): {exc}")
    if not good:
        print("  ✗ hard surface (inset, sweep, weighted normals, UVs): " + (r.stdout + r.stderr)[-1200:])
    return good


def _check_relations(exe: str, work: Path) -> bool:
    """Pieces placed by other pieces (place, snap, align): nothing floats, the set is the right size, and the socket
    reaches the GLB as a child of the asset."""
    out = work / "relations"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "relations.py"),
                        "--name", "table_set", "--tiers", "pc,mobile-low", "--blender", exe, "--no-preview", "--out-dir", str(out)],
                       capture_output=True, text=True)
    try:
        g = json.load(open(out / "gen.json"))
        pc = g["report"]["tiers"]["pc"]
        nodes = _glb_json(out / pc["file"])["nodes"]
        names = [n.get("name") for n in nodes]
        root = next(n for n in nodes if n.get("name") == "table_set")
        good = (g["ok"] and not g["report"]["facts"]["floating"] and abs(pc["dims_m"][0] - 1.45) < 0.03
                and abs(pc["dims_m"][2] - 0.838) < 0.02 and "SOCKET_lamp_hook" in names
                and names.index("SOCKET_lamp_hook") in root.get("children", []))
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ relations and sockets: {exc}")
    if not good:
        print("  ✗ relations and sockets: " + (r.stdout + r.stderr)[-1200:])
    return good


def _check_live(exe: str, work: Path) -> bool:
    """The AI link end to end, as an AI client uses it: `meshgate.py mcp` starts a background Blender, builds kit code
    in the live scene, reports facts, renders the views, measures between build lines and exports a checked GLB."""
    env = {**os.environ, "MESHGATE_BLENDER": exe, "MESHGATE_CONFIG_DIR": str(work / "live_config")}
    proc = subprocess.Popen([sys.executable, str(ROOT / "meshgate.py"), "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env)
    got: dict = {}

    def ask(mid, method, params=None):
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n")
        proc.stdin.flush()
        got[mid] = json.loads(proc.stdout.readline())
        return got[mid]

    def tool(mid, name, **args):
        return ask(mid, "tools/call", {"name": name, "arguments": args})["result"]
    try:
        ask(1, "initialize", {"protocolVersion": "2024-11-05"})
        names = {t["name"] for t in ask(2, "tools/list")["result"]["tools"]}
        code = (ROOT / "tests" / "generate" / "relations.py").read_text(encoding="utf-8")
        built = tool(3, "blender_build", code=code)
        facts = json.loads(built["content"][0]["text"])
        view = tool(4, "blender_view", closeups=[{"at": [0.2, 0, 0.8], "from": [1, -1, 0.5], "size": 0.3}])
        gap = json.loads(tool(5, "blender_measure", a="line 9", b="line 11")["content"][0]["text"])
        glb = work / "live_export" / "live.glb"
        exported = json.loads(tool(6, "blender_export", path=str(glb))["content"][0]["text"])
        good = ({"kit_reference", "blender_build", "blender_view", "blender_measure", "blender_export"} <= names
                and facts.get("ok") and not facts["facts"]["floating"] and abs(facts["size_m"][0] - 1.45) < 0.03
                and view["content"][0]["type"] == "image" and len(view["content"][0]["data"]) > 10000
                and gap.get("touching") and exported.get("ok") and glb.exists())
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ AI link (mcp): {type(exc).__name__}: {exc}")
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    if not good:
        print("  ✗ AI link (mcp): " + json.dumps(got, default=str)[-1500:])
    return good


def _check_instances(exe: str, work: Path) -> bool:
    """Instances (a forest scattered as shared meshes, a fence of instanced posts): the file stores each repeated mesh
    once, copies count as drawn triangles, nothing floats — and the sharing survives tier decimation and the realistic
    bake (whose colour must really bake)."""
    got = {}
    for style, tiers in (("stylized", "pc,mobile-low"), ("realistic", "mobile-mid")):
        out = work / f"instances_{style}"
        r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "instances.py"),
                            "--name", "forest", "--style", style, "--tiers", tiers, "--blender", exe, "--no-preview",
                            "--out-dir", str(out)], capture_output=True, text=True)
        try:
            got[style] = json.load(open(out / "gen.json"))
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ instances {style}: {exc}\n" + (r.stdout + r.stderr)[-800:])
            return False
    try:
        def glb(style, tier):
            g = got[style]
            rep = json.loads(subprocess.run([sys.executable, str(ROOT / "core" / "validate_glb.py"),
                                             str(work / f"instances_{style}" / g["report"]["tiers"][tier]["file"]), "--json"],
                                            capture_output=True, text=True).stdout)
            return rep[0] if isinstance(rep, list) else rep
        pc, low, real = glb("stylized", "pc"), glb("stylized", "mobile-low"), glb("realistic", "mobile-mid")
        good = (got["stylized"]["ok"] and got["realistic"]["ok"] and not got["stylized"]["report"]["facts"]["floating"]
                and pc["nodes"] > 40 and pc["meshes"] <= 10 and pc["instanced_meshes"] >= 3
                and pc["unique_triangles"] * 4 < pc["triangles"] and low["instanced_meshes"] >= 2
                and real["instanced_meshes"] >= 2
                and (got["realistic"]["report"]["tiers"]["mobile-mid"].get("bake_colour") or 0) > 0.03)
        detail = {k: {x: v.get(x) for x in ("nodes", "meshes", "triangles", "unique_triangles", "instanced_meshes")}
                  for k, v in (("pc", pc), ("mobile-low", low), ("realistic", real))}
    except Exception as exc:  # noqa: BLE001
        good, detail = False, str(exc)
    if not good:
        print(f"  ✗ instances: {detail}")
    return good


def _check_tiles(exe: str, work: Path) -> bool:
    """Tiling materials (a yard: brick walls joined with wooden frames, a shingle roof, cobbles, planks, ground): each
    tile gets its own seamless material within the tier's material and texture budget, phones keep the largest one,
    and the realistic finish bakes the rest while the tiled surfaces keep repeating."""
    got = {}
    for style, tiers in (("stylized", "pc,mobile-low"), ("realistic", "mobile-mid")):
        out = work / f"tiles_{style}"
        r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "tiles_scene.py"),
                            "--name", "yard", "--style", style, "--tiers", tiers, "--blender", exe, "--no-preview",
                            "--out-dir", str(out)], capture_output=True, text=True)
        try:
            got[style] = json.load(open(out / "gen.json"))
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ tiles {style}: {exc}\n" + (r.stdout + r.stderr)[-800:])
            return False
    try:
        st, re_ = got["stylized"]["report"]["tiers"], got["realistic"]["report"]["tiers"]["mobile-mid"]
        laid = [n for n in st["pc"]["notes"] if n.startswith("tiling materials:")]
        good = (got["stylized"]["ok"] and got["realistic"]["ok"] and laid and laid[0].count("(") == 5
                and st["pc"]["materials"] == 6 and st["pc"]["within_budget"] and st["mobile-low"]["materials"] <= 2
                and st["mobile-low"]["within_budget"] and re_["materials"] >= 3 and re_["within_budget"]
                and (re_.get("bake_colour") or 0) > 0.03)
        detail = {"pc": (st["pc"]["materials"], laid), "mobile-low": st["mobile-low"]["materials"],
                  "realistic": (re_["materials"], re_.get("bake_colour"))}
    except Exception as exc:  # noqa: BLE001
        good, detail = False, str(exc)
    if not good:
        print(f"  ✗ tiles: {detail}")
    return good


def _check_modules(exe: str, work: Path) -> bool:
    """A modular kit on a 2 m grid: every module is also its own GLB with the origin at its grid corner, and the one
    built 10 cm too wide is reported off the grid (facts and advice) while the others are not."""
    out = work / "modules"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", str(ROOT / "tests" / "generate" / "modules_scene.py"),
                        "--name", "kit", "--tiers", "pc,mobile-low", "--blender", exe, "--no-preview", "--out-dir", str(out)],
                       capture_output=True, text=True)
    try:
        g = json.load(open(out / "gen.json"))
        mods = {m["name"]: m for m in g["report"].get("modules") or []}
        off = {m["name"] for m in g["report"]["facts"].get("modules") or [] if m["off_grid"]}
        wall = json.loads(subprocess.run([sys.executable, str(ROOT / "core" / "validate_glb.py"), str(out / "kit_wall.glb"), "--json"],
                                         capture_output=True, text=True).stdout)
        wall = wall[0] if isinstance(wall, list) else wall
        good = (g["ok"] and set(mods) == {"wall", "wall_window", "doorway", "floor", "post", "wall_wide"}
                and all(m["ok"] for m in mods.values()) and off == {"wall_wide"}
                and any("module wall_wide" in a for a in g["report"]["advice"])
                and [round(x, 3) for x in wall["bounds_min_m"]] == [0.0, 0.0, -0.1] and wall["dims_m"][0] == 2.0)
        detail = {"modules": sorted(mods), "off": sorted(off), "wall": (wall.get("bounds_min_m"), wall.get("dims_m"))}
    except Exception as exc:  # noqa: BLE001
        good, detail = False, f"{exc}: " + (r.stdout + r.stderr)[-600:]
    if not good:
        print(f"  ✗ modular kit: {detail}")
    return good


def _check_finish(exe: str, work: Path) -> bool:
    """The style's finish: lowpoly is faceted with fewer triangles than stylized; realistic bakes weathered textures
    (colour at the tier's size plus a normal map) and keeps one material."""
    code = str(ROOT / "sources" / "generate" / "examples" / "toxic_can.py")
    got = {}
    for style, tier in (("stylized", "pc"), ("lowpoly", "pc"), ("realistic", "mobile-mid")):
        out = work / f"finish_{style}"
        r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--code", code, "--style", style, "--tiers", tier,
                            "--name", f"finish_{style}", "--blender", exe, "--no-preview", "--out-dir", str(out)],
                           capture_output=True, text=True)
        try:
            g = json.load(open(out / "gen.json"))
            got[style] = (g, g["report"]["tiers"][tier])
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ finish {style}: {exc}\n" + (r.stdout + r.stderr)[-800:])
            return False
    try:
        (gs, st), (gl, lp), (gr, re_) = got["stylized"], got["lowpoly"], got["realistic"]
        rep = json.loads(subprocess.run([sys.executable, str(ROOT / "core" / "validate_glb.py"),
                                         str(work / "finish_realistic" / re_["file"]), "--json"], capture_output=True, text=True).stdout)
        rep = rep[0] if isinstance(rep, list) else rep
        good = (gl["finish"] == "faceted" and lp["tris"] < st["tris"] and gr["finish"] == "weathered"
                and any("weathered finish baked" in n for n in re_["notes"]) and re_["max_texture"] == 1024
                and re_["materials"] == 1 and rep.get("textures", 0) >= 3 and re_["within_budget"]
                and (re_.get("bake_colour") or 0) > 0.03)   # the colour really baked (a failed bake is black)
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ finish: {exc}")
    if not good:
        print(f"  ✗ finish: lowpoly {got['lowpoly'][1].get('tris')} vs stylized {got['stylized'][1].get('tris')} tris; "
              f"realistic {got['realistic'][1]}")
    return good


def _glb_json(path: Path) -> dict:
    with open(path, "rb") as f:
        head = f.read(20)
        return json.loads(f.read(int.from_bytes(head[12:16], "little")))


def _check_quality(exe: str, work: Path) -> bool:
    """--pbr bakes a full PBR set with an occlusion map (within the tier's texture limit); --topology quad gives the
    mesh engine all-quad topology."""
    runs = {"pbr": ["--code", str(ROOT / "sources" / "generate" / "examples" / "toxic_can.py"), "--style", "stylized",
                    "--pbr", "--texture", "2k", "--tiers", "mobile-mid"],
            "quad": ["--mesh", str(ROOT / "sources" / "generate" / "examples" / "hydrant_triposr_raw.glb"), "--size", "0.8",
                     "--topology", "quad", "--tiers", "mobile-low"]}
    got = {}
    for name, extra in runs.items():
        out = work / f"quality_{name}"
        r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", *extra, "--name", f"q_{name}", "--blender", exe,
                            "--no-preview", "--out-dir", str(out)], capture_output=True, text=True)
        try:
            got[name] = json.load(open(out / "gen.json"))
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ quality {name}: {exc}\n" + (r.stdout + r.stderr)[-800:])
            return False
    try:
        pbr = got["pbr"]["report"]["tiers"]["mobile-mid"]
        mats = _glb_json(work / "quality_pbr" / pbr["file"]).get("materials", [])
        quad = got["quad"]["report"]["tiers"]["mobile-low"]
        good = (got["pbr"]["finish"] == "clean" and pbr["max_texture"] == 1024 and pbr["within_budget"]
                and any("occlusionTexture" in m for m in mats) and str(quad.get("topology", "")).startswith("quad")
                and quad["within_budget"])
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ quality: {exc}")
    if not good:
        print(f"  ✗ quality: pbr {got.get('pbr', {}).get('report', {}).get('tiers')} quad {got.get('quad', {}).get('report', {}).get('tiers')}")
    return good


def _check_refine(exe: str, work: Path) -> bool:
    """Mesh engine without a neural model: a dense, tilted, vertex-coloured stand-in goes through refine.py — it must
    come out upright, 1.2 m tall, within every tier and with the colour baked. With TripoSR installed, the example
    picture also runs through the real model (first Blender only, it is the same Python on every version)."""
    ok = True
    raw = work / "raw" / "raw.glb"
    raw.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([exe, "-b", "--factory-startup", "-P", str(ROOT / "tests" / "generate" / "make_raw_mesh.py"), "--", str(raw)],
                   capture_output=True, text=True, cwd=str(ROOT))
    out = work / "refine"
    r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--mesh", str(raw), "--name", "post", "--size", "1.2",
                        "--blender", exe, "--no-preview", "--out-dir", str(out)], capture_output=True, text=True)
    try:
        rep = json.load(open(out / "gen.json"))["report"]
        tiers = rep["tiers"]
        dims = tiers["pc"]["dims_m"]
        log = (out / "refine.blender.log").read_text()
        tilt = re.search(r"leaned it (\d+)°", log)
        bake = json.loads(subprocess.run([sys.executable, str(ROOT / "tests" / "generate" / "check_bake.py"),
                                          str(out / "post.mobile-mid.glb"), f"--blender={exe}"],
                                         capture_output=True, text=True).stdout)
        good = (rep["ok"] and all(t["within_budget"] for t in tiers.values()) and len(tiers) == 4
                and abs(dims[1] - 1.2) < 0.02 and max(dims[0], dims[2]) < 0.6 and tilt and 17 <= int(tilt.group(1)) <= 23
                and "specks" in log and bake["red"] > 0.1 and bake["blue"] > 0.1)
        if not good:
            print(f"  ✗ refine: ok={rep['ok']} dims={dims} tilt={tilt and tilt.group(1)} bake={bake}")
    except Exception as exc:  # noqa: BLE001
        good = False
        print(f"  ✗ refine: {exc} " + (r.stdout + r.stderr)[-800:])
    ok &= good
    sys.path.insert(0, str(ROOT / "sources" / "generate"))
    from mesh import triposr
    if triposr.available() and exe == (find_blenders() or [exe])[0]:
        out = work / "triposr"
        r = subprocess.run([sys.executable, str(ROOT / "meshgate.py"), "gen", "--image",
                            str(ROOT / "sources" / "generate" / "examples" / "hydrant_picture.png"), "--engine", "mesh",
                            "--provider", "triposr", "--name", "hydrant", "--size", "0.8", "--blender", exe, "--no-preview",
                            "--out-dir", str(out)], capture_output=True, text=True)
        try:
            rep = json.load(open(out / "gen.json"))["report"]
            good = rep["ok"] and len(rep["tiers"]) == 4 and all(t["within_budget"] for t in rep["tiers"].values())
        except Exception:  # noqa: BLE001
            good = False
        if not good:
            print("  ✗ TripoSR picture → 3D: " + (r.stdout + r.stderr)[-800:])
        else:
            print("  ✓ TripoSR picture → 3D → 4 tiers")
        ok &= good
    return ok


def _check_unreal() -> int:
    """No Unreal needed: every unreal.* name in the plugin is checked against the UE 5.4/5.5/5.6 API stubs."""
    code = run([sys.executable, str(ROOT / "tests" / "unreal" / "check_api.py"), "--download"])
    return max(code, run([sys.executable, str(ROOT / "tests" / "unreal" / "test_pack_import.py")]))   # file choice per pack/tier


def cmd_check(args) -> int:
    # checks keep their own settings folder: test runs must not teach the progress bar or fill the example library
    if not os.environ.get("MESHGATE_CHECK_KEEP_CONFIG"):
        os.environ["MESHGATE_CONFIG_DIR"] = tempfile.mkdtemp(prefix="meshgate-check-config-")
    if args.target == "blender":
        return _check_blender(not args.no_generators)
    targets = ["web", "blender", "unity", "godot", "unreal"] if args.target == "all" else [args.target]
    results = {}
    for t in targets:
        print(f"\n=== check {t} ===")
        if t == "web":
            results[t] = _check_web()
        elif t == "unity":
            results[t] = _check_unity(args.render)
        elif t == "godot":
            results[t] = _check_godot()
        elif t == "unreal":
            results[t] = _check_unreal()
        elif t == "blender":
            results[t] = _check_blender(not args.no_generators)
    print("\n" + "  ".join(f"{t}: {'ok' if c == 0 else 'FAILED'}" for t, c in results.items()))
    return max(results.values())


# ----------------------------------------------------------------------------

def cmd_gen(argv: list[str]) -> int:
    sys.path.insert(0, str(ROOT / "sources" / "generate"))
    import generate
    return generate.main(argv)


def cmd_studio(argv: list[str]) -> int:
    sys.path.insert(0, str(ROOT / "apps" / "studio"))
    import server
    return server.main(argv)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):   # Windows consoles and pipes default to cp1252; MeshGate prints ✓ and —
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":   # MCP server over stdio: AI clients drive Blender through the kit
        sys.path.insert(0, str(ROOT / "sources" / "generate"))
        import mcp_server
        return mcp_server.main()
    if len(sys.argv) > 1 and sys.argv[1] == "library":   # its own parser: sources/generate/library.py
        sys.path.insert(0, str(ROOT / "sources" / "generate"))
        import library
        return library.main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "gen":   # its own parser: sources/generate/generate.py
        return cmd_gen(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "studio":   # its own parser: apps/studio/server.py
        return cmd_studio(sys.argv[2:])
    ap = argparse.ArgumentParser(prog="meshgate", description="MeshGate — Blender/Maya → canonical glTF → web, Unity, Godot, Unreal.")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="show which tools were found").set_defaults(fn=cmd_doctor)
    sub.add_parser("addon", help="build the Blender add-on zip into dist/").set_defaults(fn=lambda a: (build_addon(), 0)[1])
    p = sub.add_parser("install-blender", help="build the add-on and install + enable it in your Blender (close Blender first)")
    p.add_argument("--blender"); p.add_argument("--all", action="store_true"); p.add_argument("--zip"); p.add_argument("--uninstall", action="store_true")
    p.set_defaults(fn=lambda a: run([sys.executable, str(ROOT / "scripts" / "install_blender_addon.py")]
                                    + (["--blender", a.blender] if a.blender else []) + (["--all"] if a.all else [])
                                    + (["--zip", a.zip] if a.zip else []) + (["--uninstall"] if a.uninstall else [])))

    p = sub.add_parser("export", help="export a .blend to a contract GLB (and optional FBX), then validate")
    p.add_argument("blend"); p.add_argument("--out", required=True)
    p.add_argument("--fbx", action="store_true"); p.add_argument("--draco", action="store_true")
    p.add_argument("--selection", action="store_true"); p.add_argument("--no-animations", dest="no_animations", action="store_true")
    p.add_argument("--image-format", choices=["AUTO", "PNG", "JPEG", "WEBP"])
    p.add_argument("--targets", help="web,unity,godot,unreal — engine variants (collision, LODs)")
    p.add_argument("--profiles", help="mobile-low,mobile-mid,mobile-high — quality tier variants within budget")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("character", help="bring a rigged humanoid (GLB/FBX; Unity/Mixamo/Rigify/UE bone names) to the contract")
    p.add_argument("src"); p.add_argument("--out", required=True); p.add_argument("--no-anim", action="store_true")
    p.set_defaults(fn=cmd_character)

    p = sub.add_parser("validate", help="check GLB/FBX files against the asset contract")
    p.add_argument("files", nargs="+"); p.add_argument("--strict", action="store_true"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("serve", help="open the web viewer")
    p.add_argument("--glb"); p.add_argument("--port", type=int, default=8770); p.add_argument("--no-browser", action="store_true")
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("samples", help="rebuild all demo assets in samples/ from their Blender scripts")
    p.add_argument("--only", help="substring filter, e.g. 'drone'"); p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_samples)

    sub.add_parser("gen", help="generate an asset from a text description through an AI CLI (meshgate.py gen --help)")
    sub.add_parser("mcp", help="MCP server for AI clients: live kit tools in Blender (claude mcp add meshgate -- python3 meshgate.py mcp)")
    sub.add_parser("library", help="find and download free CC0 / CC-BY models to refine (meshgate.py library --help)")
    sub.add_parser("studio", help="open MeshGate Studio, the local app for generation (meshgate.py studio --help)")

    p = sub.add_parser("check", help="run the engine checks headless")
    p.add_argument("target", choices=["web", "blender", "unity", "godot", "unreal", "all"])
    p.add_argument("--no-generators", action="store_true", help="blender: skip regenerating the demo assets on each version")
    p.add_argument("--render", action="store_true", help="unity: run with graphics so the scene render test produces a PNG")
    p.set_defaults(fn=cmd_check)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
