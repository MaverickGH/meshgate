#!/usr/bin/env python3
"""MeshGate portable archive — Studio in your browser without installing anything (Linux, or any OS).

    python3 scripts/make_portable.py [--version 0.6.5] [--out dist] [--keep]

Writes <out>/MeshGate-<version>-portable.zip with everything `python3 meshgate.py studio` needs, the engine plugins,
the docs and three.js for offline use. The release workflow attaches it to every version next to the installers.
Unpack, then: python3 meshgate.py studio
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = [
    "meshgate.py", "LICENSE", "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.ru.md", "README.md", "README.ru.md",
    "core", "sources", "docs", "apps/studio/server.py", "apps/studio/ui", "apps/studio/README.md", "apps/studio/README.ru.md",
    "targets/web/meshgate-viewer.js", "targets/web/index.html", "targets/web/app.js",
    "targets/unity/com.meshgate.unity", "targets/godot/MeshGateDemo/addons/meshgate", "targets/unreal/MeshGate",
    "scripts/build_blender_addon.py", "scripts/install_blender_addon.py", "scripts/vendor_three.py",
]
SKIP = re.compile(r"(^\._|__pycache__|\.pyc$|\.DS_Store$|\.blend1$)")
START = """MeshGate Studio — portable

Needs Python 3.9+ (nothing to pip install) and Blender 3.5+. Then, in this folder:
On Windows, double-click START_WINDOWS.cmd (MESHGATE_PYTHON can specify your Python).

    python3 meshgate.py doctor     # what is found and what is missing
    python3 meshgate.py studio     # opens Studio in your browser (runs on this computer only)

Generated assets go to ~/Documents/MeshGate Assets. Guide: docs/getting-started.md

---

MeshGate Studio — переносная версия

Нужны Python 3.9+ (ничего ставить через pip не нужно) и Blender 3.5+. Потом в этой папке:
На Windows запусти START_WINDOWS.cmd двойным кликом (MESHGATE_PYTHON задаёт путь к Python).

    python3 meshgate.py doctor     # что найдено и чего не хватает
    python3 meshgate.py studio     # открывает студию в браузере (работает только на этом компьютере)

Готовые ассеты сохраняются в ~/Documents/MeshGate Assets. Руководство: docs/getting-started.ru.md
"""

START_WINDOWS = r'''@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if exist "%~dp0native-core.json" (
    if not exist "%~dp0runtime\studio\python\python.exe" (
        echo The bundled Python is missing. Extract the full archive again.
        pause
        exit /b 1
    )
    set "PATH=%~dp0runtime\studio;%PATH%"
    "%~dp0runtime\studio\python\python.exe" meshgate.py studio %*
    goto done
)
if defined MESHGATE_PYTHON goto custom_python
if exist "%~dp0runtime\windows\python\python.exe" (
    set "PATH=%~dp0runtime\windows;%PATH%"
    "%~dp0runtime\windows\python\python.exe" meshgate.py studio %*
    goto done
)
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (
    py -3 meshgate.py studio %*
    goto done
)
python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (
    python meshgate.py studio %*
    goto done
)
python3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (
    python3 meshgate.py studio %*
    goto done
)
echo Install Python 3.9+ from https://www.python.org/downloads/ and add it to PATH.
pause
exit /b 1
:custom_python
"%MESHGATE_PYTHON%" meshgate.py studio %*
:done
if errorlevel 1 pause
'''


def version() -> str:
    m = re.search(r'^VERSION = "([^"]+)"', (ROOT / "apps" / "studio" / "server.py").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else json.loads((ROOT / "native/studio/index.json").read_text())["version"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", default=version())
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--keep", help="also leave the unpacked folder here (for tests)")
    ap.add_argument("--windows-runtime", action="store_true", help="include the private Windows x64 Python + uv")
    ap.add_argument("--compiled", action="store_true", help="package native Studio and its fixed Python for this platform")
    args = ap.parse_args()
    if not (ROOT / "apps" / "studio" / "ui" / "vendor" / "three" / "build" / "three.module.js").exists():
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "vendor_three.py")])   # offline viewer
    platform_name = {"darwin": "macos", "win32": "windows", "linux": "linux"}[sys.platform]
    name = f"MeshGate-{args.version}-{platform_name + '-' if args.compiled else 'windows-' if args.windows_runtime else ''}portable"
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / name
        if args.compiled:
            from build_studio_runtime import DEST
            resources = DEST / "resources"
            if not (resources / "native-core.json").is_file():
                raise RuntimeError("Run scripts/prepare_studio_bundle.py first")
            shutil.copytree(resources, stage)
            shutil.copytree(DEST / "python", stage / "runtime/studio/python")
            shutil.copytree(DEST / "uv-licenses", stage / "runtime/studio/uv-licenses")
            for rel in ("runtime.json", "uv.exe" if sys.platform == "win32" else "uv"):
                shutil.copy2(DEST / rel, stage / "runtime/studio" / rel)
        elif args.windows_runtime:
            runtime = ROOT / "apps/studio/desktop/runtime/windows"
            if not (runtime / "python/python.exe").is_file():
                raise RuntimeError("Run scripts/build_windows_runtime.py first")
            shutil.copytree(runtime, stage / "runtime/windows", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for rel in ([] if args.compiled else INCLUDE):
            src = ROOT / rel
            if src.is_dir():
                shutil.copytree(src, stage / rel, ignore=lambda d, names: [n for n in names if SKIP.search(n)])
            elif src.exists():
                (stage / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, stage / rel)
            else:
                print(f"missing: {rel}")
                return 1
        intro = ("Windows x64: Python and uv are included. Double-click START_WINDOWS.cmd.\n"
                 "Windows x64: Python и uv включены. Запусти START_WINDOWS.cmd двойным кликом.\n\n") if args.windows_runtime else ""
        (stage / "START.txt").write_text(intro + START, encoding="utf-8")
        (stage / "START_WINDOWS.cmd").write_bytes(START_WINDOWS.replace("\n", "\r\n").encode("ascii"))
        if args.compiled:
            start = '''#!/bin/sh
cd "$(dirname "$0")" || exit 1
export PATH="$PWD/runtime/studio:$PATH"
exec "$PWD/runtime/studio/python/bin/python3.11" meshgate.py studio "$@"
'''
            (stage / "START.sh").write_text(start, encoding="utf-8")
            (stage / "START.sh").chmod(0o755)
            (stage / "START.txt").write_text(
                "MeshGate Studio: Python is included. Windows: START_WINDOWS.cmd; macOS/Linux: sh START.sh.\n"
                "This archive runs only on the OS and architecture listed in runtime/studio/runtime.json.\n"
                "Python включён. Windows: START_WINDOWS.cmd; macOS/Linux: sh START.sh.\n", encoding="utf-8")
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=True)
        archive = out / f"{name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for f in sorted(stage.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(stage.parent))
        if args.keep:
            dest = Path(args.keep).resolve()
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(stage, dest)
    print(f"{archive} ({archive.stat().st_size / 2 ** 20:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
