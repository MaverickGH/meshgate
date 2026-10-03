#!/usr/bin/env python3
"""MeshGate portable archive — Studio in your browser without installing anything (Linux, or any OS).

    python3 scripts/make_portable.py [--version 0.6.5] [--out dist] [--keep]

Writes <out>/MeshGate-<version>-portable.zip with everything `python3 meshgate.py studio` needs, the engine plugins,
the docs and three.js for offline use. The release workflow attaches it to every version next to the installers.
Unpack, then: python3 meshgate.py studio
"""

from __future__ import annotations

import argparse
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
if defined MESHGATE_PYTHON goto custom_python
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
    return m.group(1) if m else "dev"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", default=version())
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--keep", help="also leave the unpacked folder here (for tests)")
    args = ap.parse_args()
    if not (ROOT / "apps" / "studio" / "ui" / "vendor" / "three" / "build" / "three.module.js").exists():
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "vendor_three.py")])   # offline viewer
    name = f"MeshGate-{args.version}-portable"
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / name
        for rel in INCLUDE:
            src = ROOT / rel
            if src.is_dir():
                shutil.copytree(src, stage / rel, ignore=lambda d, names: [n for n in names if SKIP.search(n)])
            elif src.exists():
                (stage / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, stage / rel)
            else:
                print(f"missing: {rel}")
                return 1
        (stage / "START.txt").write_text(START, encoding="utf-8")
        (stage / "START_WINDOWS.cmd").write_bytes(START_WINDOWS.replace("\n", "\r\n").encode("ascii"))
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=True)
        archive = out / f"{name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
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
