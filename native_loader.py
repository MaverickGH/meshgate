"""Load a published native Studio module with its matching CPython runtime."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import platform
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent


def load(relative, namespace):
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 11):
        raise RuntimeError("Native MeshGate requires bundled Python 3.11. Run scripts/build_studio_runtime.py first.")
    system = {"darwin": "macos", "win32": "windows", "linux": "linux"}[sys.platform]
    machine = platform.machine().lower()
    if machine not in ("arm64", "aarch64", "x86_64", "amd64"):
        raise RuntimeError("Unsupported architecture: " + machine)
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    index = json.loads((ROOT / "native/studio/index.json").read_text())
    record = index["packages"][system + "-" + arch]
    package = ROOT / "native/studio" / record["file"]
    if hashlib.sha256(package.read_bytes()).hexdigest() != record["sha256"]:
        raise RuntimeError("Native package checksum mismatch")
    name = "_meshgate_" + Path(relative).stem
    suffix = ".pyd" if os.name == "nt" else ".so"
    with zipfile.ZipFile(package) as archive:
        candidates = [p for p in archive.namelist() if Path(p).parent == Path(relative).parent
                      and Path(p).name.startswith(name + ".") and p.endswith(suffix)]
        if len(candidates) != 1:
            raise RuntimeError("Native module missing from package")
        target = ROOT / candidates[0]
        data = archive.read(candidates[0])
        if not target.is_file() or hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(data).digest():
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
                tmp.write(data)
                temp = Path(tmp.name)
            try:
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
    spec = importlib.util.spec_from_file_location(name, target)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    namespace.update({k: v for k, v in vars(native).items() if not k.startswith("__")})
    return native
