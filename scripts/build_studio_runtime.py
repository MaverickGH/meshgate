"""Prepare a fixed CPython and uv for native Studio modules on the build platform."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "apps/studio/desktop/runtime/studio"
PYTHON = "3.11.16"
UV = "0.12.19"


def python_path(base: Path = DEST) -> Path:
    return base / ("python/python.exe" if os.name == "nt" else "python/bin/python3.11")


def build() -> Path:
    expected = {"python": PYTHON, "uv": UV, "system": sys.platform, "machine": platform.machine()}
    marker = DEST / "runtime.json"
    uv = DEST / ("uv.exe" if os.name == "nt" else "uv")
    if marker.exists() and json.loads(marker.read_text()) == expected and python_path().is_file() and uv.is_file():
        return python_path()
    cache = ROOT / "out/studio-runtime-build"
    wheels = cache / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:",
                    "--dest", str(wheels), f"uv=={UV}"], check=True)
    # pip selects a wheel for the host interpreter's architecture, also used by the compiled modules.
    candidates = list(wheels.glob(f"uv-{UV}-*.whl"))
    if len(candidates) != 1:
        raise RuntimeError("Expected one host uv wheel; remove out/studio-runtime-build/wheels before changing architecture")
    DEST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(candidates[0]) as wheel:
        binary = next(n for n in wheel.namelist() if n.endswith("/" + uv.name))
        uv.write_bytes(wheel.read(binary))
        uv.chmod(0o755)
        for name in wheel.namelist():
            if "/licenses/" in name and not name.endswith("/"):
                folder = DEST / "uv-licenses"
                folder.mkdir(exist_ok=True)
                (folder / Path(name).name).write_bytes(wheel.read(name))
    env = {**os.environ, "UV_PYTHON_INSTALL_DIR": str(cache / "python"),
           "UV_PYTHON_BIN_DIR": str(cache / "bin"), "UV_CACHE_DIR": str(cache / "cache")}
    arch = "aarch64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
    system = {"darwin": "macos", "win32": "windows", "linux": "linux"}[sys.platform]
    request = f"cpython-{PYTHON}-{system}-{arch}-{'gnu' if system == 'linux' else 'none'}"
    subprocess.run([str(uv), "python", "install", request], env=env, check=True)
    executable = subprocess.check_output([str(uv), "python", "find", "--managed-python", request],
                                         env=env, text=True).strip()
    prefix = Path(subprocess.check_output([executable, "-c", "import sys; print(sys.base_prefix)"], text=True).strip())
    target = DEST / "python"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(prefix, target, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    subprocess.run([str(python_path()), "-c", "import ssl,venv,ensurepip; print('Studio Python ready')"], check=True)
    marker.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    return python_path()


if __name__ == "__main__":
    print(build())
