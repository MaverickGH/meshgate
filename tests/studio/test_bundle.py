#!/usr/bin/env python3
"""The desktop bundle carries its own copy of MeshGate: check that copy works on its own.

    python3 tests/studio/test_bundle.py <resources/meshgate> [--blender PATH]

Without Blender: the files Studio needs are there, the bundled server starts and answers /api/status, and gen builds a
prompt. With Blender: a kit build and a mesh refine run from the bundled files only.
"""
import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

NEEDED = ["meshgate.py", "LICENSE", "core/validate_glb.py", "core/validate_fbx.py", "core/profiles.json",
          "sources/blender/meshgate_blender/__init__.py", "sources/blender/meshgate_blender/modeling.py",
          "sources/generate/generate.py", "sources/generate/run_generated.py", "sources/generate/refine.py",
          "sources/generate/safety.py", "sources/generate/procs.py", "sources/generate/keys.py", "sources/generate/prompts/model.md",
          "sources/generate/mesh/__init__.py", "sources/generate/mesh/triposr_run.py",
          "sources/generate/examples/treasure_chest.py", "sources/generate/examples/hydrant_triposr_raw.glb",
          "apps/studio/server.py", "apps/studio/ui/index.html", "apps/studio/ui/studio.js",
          "apps/studio/ui/vendor/three/build/three.module.js", "targets/web/meshgate-viewer.js",
          "scripts/build_blender_addon.py", "scripts/install_blender_addon.py",
          "targets/unity/com.meshgate.unity/package.json", "targets/godot/MeshGateDemo/addons/meshgate/plugin.cfg",
          "targets/unreal/MeshGate/MeshGate.uplugin"]
FAILS = []


def step(name, ok, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--blender")
    ap.add_argument("--private-runtime", action="store_true", help="require bundled Windows Python; no host Python or tools on PATH")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    missing = [f for f in NEEDED if not (root / f).is_file()]
    step("the bundle carries every file Studio needs", not missing, ", ".join(missing))
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MESHGATE_STUDIO_TOKEN": "bundle-test",
           "MESHGATE_PYTHON": sys.executable, "PYTHONUTF8": "1"}
    python = sys.executable
    if args.private_runtime:
        python = str(root / "runtime/windows/python/python.exe")
        if not Path(python).is_file():
            step("private Python is present", False, python)
            return 1
        for key in list(env):
            if key.startswith(("MESHGATE_", "UV_", "HF_", "PYTHON")) or key == "U2NET_HOME":
                env.pop(key)
        env.update({"PATH": str(root / "runtime/windows") + os.pathsep + os.path.join(os.environ["SystemRoot"], "System32"),
                    "MESHGATE_STUDIO_TOKEN": "bundle-test", "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    lib = Path(tempfile.mkdtemp(prefix="meshgate-bundle-"))
    launch = [python, str(root / "meshgate.py"), "studio"]
    if os.name == "nt" and (root / "START_WINDOWS.cmd").is_file():
        launch = ["cmd.exe", "/d", "/c", str(root / "START_WINDOWS.cmd")]
    srv = subprocess.Popen([*launch, "--port", "0", "--no-browser",
                            "--library", str(lib)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=env,
                           cwd=str(root))
    url = None
    t0 = time.time()
    while time.time() - t0 < 30 and url is None:
        line = srv.stdout.readline()
        m = re.match(r"MESHGATE_STUDIO http://127\.0\.0\.1:(\d+)/", line or "")
        url = int(m.group(1)) if m else None
    status = {}
    if url:
        c = http.client.HTTPConnection("127.0.0.1", url, timeout=20)
        c.request("GET", "/api/status", headers={"Host": f"127.0.0.1:{url}", "X-MeshGate-Token": "bundle-test"})
        status = json.loads(c.getresponse().read() or b"{}")
        c = http.client.HTTPConnection("127.0.0.1", url, timeout=20)
        c.request("GET", "/three/build/three.module.js", headers={"Host": f"127.0.0.1:{url}"})
        three = c.getresponse().status
    if os.name == "nt" and launch[0] == "cmd.exe":
        subprocess.run(["taskkill", "/PID", str(srv.pid), "/T", "/F"], capture_output=True)
    else:
        srv.terminate()
    srv.wait(timeout=10)
    step("the bundled server starts and answers /api/status with the token from the environment",
         bool(url) and len(status.get("tiers", [])) == 4)
    step("the bundled status finds the engine plugins it ships", bool(url) and all(
        (status.get("tools", {}).get(t) or {}).get("plugin") for t in ("blender", "unity", "godot", "unreal")))
    step("three.js is served from the bundle (offline viewer)", bool(url) and three == 200)
    r = subprocess.run([python, str(root / "meshgate.py"), "gen", "a crate", "--prompt-only"], capture_output=True,
                       text=True, env=env, cwd=str(root))
    step("gen builds a prompt from the bundled kit", "mg.part(" in r.stdout)
    if args.blender:
        for name, extra in (("chest", ["--code", str(root / "sources/generate/examples/treasure_chest.py")]),
                            ("hydrant", ["--mesh", str(root / "sources/generate/examples/hydrant_triposr_raw.glb"),
                                         "--size", "0.8", "--tiers", "mobile-low,mobile-mid"])):
            out = lib / name
            r = subprocess.run([python, str(root / "meshgate.py"), "gen", *extra, "--name", name, "--no-preview",
                                "--blender", args.blender, "--out-dir", str(out)], capture_output=True, text=True,
                               env=env, cwd=str(root))
            try:
                ok = json.loads((out / "gen.json").read_text())["ok"]
            except OSError:
                ok = False
            step(f"bundled gen: {name} builds and validates", ok, (r.stdout + r.stderr)[-400:])
    print("Result: " + ("the bundle works on its own." if not FAILS else f"{len(FAILS)} failed."))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
