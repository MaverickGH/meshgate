"""Prepare the private Python + uv shipped by Windows Studio; no machine-wide installation."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "apps/studio/desktop/runtime/windows"
PYTHON = "cpython-3.11.16-windows-x86_64-none"
UV_URL = "https://files.pythonhosted.org/packages/c2/5d/8e0b84503b77ead843ef57e4f9305eb32a95cac6806c0e0d54b9404a5f7b/uv-0.12.19-py3-none-win_amd64.whl"
UV_SHA256 = "dcbc531a96762569bbfe9639b4f45f00aabff51f427540711f63e7c23f225fdf"


def main():
    if sys.platform != "win32":
        raise RuntimeError("Build the Windows runtime on Windows x64")
    marker = DEST / "runtime.json"
    expected = {"python": PYTHON, "uv_sha256": UV_SHA256}
    if marker.exists() and json.loads(marker.read_text()) == expected and (DEST / "python/python.exe").is_file() and (DEST / "uv.exe").is_file():
        print("Windows Python + uv already prepared")
        return
    DEST.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(UV_URL, timeout=120) as response:
        wheel = response.read()
    if hashlib.sha256(wheel).hexdigest() != UV_SHA256:
        raise RuntimeError("uv package checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        binary = next(n for n in archive.namelist() if n.endswith("/uv.exe"))
        (DEST / "uv.exe").write_bytes(archive.read(binary))
        for name in archive.namelist():
            if "/licenses/" in name and not name.endswith("/"):
                folder = DEST / "uv-licenses"
                folder.mkdir(exist_ok=True)
                (folder / Path(name).name).write_bytes(archive.read(name))
    cache = ROOT / "out/windows-runtime-build"
    env = {**os.environ, "UV_PYTHON_INSTALL_DIR": str(cache / "python"), "UV_CACHE_DIR": str(cache / "cache"),
           "UV_PYTHON_BIN_DIR": str(cache / "bin")}
    uv = str(DEST / "uv.exe")
    subprocess.check_call([uv, "python", "install", PYTHON], env=env)
    source = Path(subprocess.check_output([uv, "python", "find", "--managed-python", PYTHON], env=env, text=True).strip()).parent
    target = DEST / "python"
    # Only replace this script's own build output, never a system Python or arbitrary configured path.
    if target.resolve().parent != DEST.resolve():
        raise RuntimeError("Unexpected runtime destination")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    subprocess.check_call([str(target / "python.exe"), "-c", "import ssl,venv,ensurepip; print('Private Python ready')"])
    marker.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
