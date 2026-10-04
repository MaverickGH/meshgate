"""Stage Studio resources, replacing orchestration source with native libraries."""
from __future__ import annotations

import json
import hashlib
import platform
import sys
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

from build_studio_runtime import ROOT, DEST, build, python_path
from make_portable import INCLUDE, SKIP


def prepare() -> Path:
    python = build()
    index_path = ROOT / "native/studio/index.json"
    if index_path.is_file():
        index = json.loads(index_path.read_text())
        system = {"darwin": "macos", "win32": "windows", "linux": "linux"}[sys.platform]
        machine = platform.machine().lower()
        arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
        record = index["packages"][system + "-" + arch]
        archive = index_path.parent / record["file"]
        if hashlib.sha256(archive.read_bytes()).hexdigest() != record["sha256"]:
            raise RuntimeError("Native package checksum mismatch")
    else:
        uv = DEST / ("uv.exe" if os.name == "nt" else "uv")
        venv = ROOT / "out/studio-native-build-venv"
        compiler = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not compiler.is_file():
            subprocess.run([str(uv), "venv", "--python", str(python), str(venv)], check=True)
        subprocess.run([str(uv), "pip", "install", "--python", str(compiler),
                        "Cython==3.3.0", "setuptools==84.0.0"], check=True)
        output = ROOT / "out/studio-native-package"
        subprocess.run([str(compiler), str(ROOT / "scripts/build_native_core.py"),
                        "--studio", "--out", str(output)], check=True)
        archives = list(output.glob("MeshGate-native-studio-*.zip"))
        if len(archives) != 1:
            raise RuntimeError("Expected exactly one native Studio archive; clean out/studio-native-package")
        archive = archives[0]
    resources = DEST / "resources"
    if resources.exists():
        shutil.rmtree(resources)
    resources.mkdir()
    for rel in INCLUDE:
        source = ROOT / rel
        target = resources / rel
        if source.is_dir():
            shutil.copytree(source, target, ignore=lambda d, names: [n for n in names if SKIP.search(n)])
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            raise RuntimeError(f"Missing bundle resource: {rel}")
    with zipfile.ZipFile(archive) as package:
        package.extractall(resources)
    manifest = json.loads((resources / "native-core.json").read_text())
    for rel in manifest["files"]:
        wrapper = (resources / rel).read_text(encoding="utf-8")
        if "_spec.loader.exec_module(_native)" not in wrapper or len(wrapper) > 1000:
            raise RuntimeError(f"Source implementation leaked into native bundle: {rel}")
    subprocess.run([str(python_path()), str(resources / "meshgate.py"), "gen", "a crate", "--prompt-only"],
                   stdout=subprocess.DEVNULL, check=True)
    print(resources)
    return resources


if __name__ == "__main__":
    prepare()
