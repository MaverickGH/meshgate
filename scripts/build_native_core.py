#!/usr/bin/env python3
"""Build a platform/Python-specific native validator package, without changing the checkout."""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("validate_glb", "validate_fbx")
STUDIO_MODULES = {
    "meshgate": "meshgate.py",
    "server": "apps/studio/server.py",
    "generate": "sources/generate/generate.py",
    "bridge": "sources/generate/bridge.py",
    "components": "sources/generate/components.py",
}


def build(out: Path, studio: bool = False) -> Path:
    try:
        import Cython
        import setuptools
    except ImportError as exc:
        raise RuntimeError("Build dependencies missing: install Cython and setuptools in a build venv") from exc
    tag = sys.implementation.cache_tag + "-" + sysconfig.get_platform()
    out.mkdir(parents=True, exist_ok=True)
    modules = STUDIO_MODULES if studio else {n: f"core/{n}.py" for n in MODULES}
    archive = out / f"MeshGate-native-{'studio' if studio else 'core'}-{tag}.zip"
    with tempfile.TemporaryDirectory(prefix="meshgate-native-") as tmp:
        work = Path(tmp)
        stage = work / "package"
        core = stage / "core"
        core.mkdir(parents=True)
        for name, rel in modules.items():
            shutil.copy2(ROOT / rel, work / f"_meshgate_{name}.py")
        setup = '''from setuptools import setup, Extension
from Cython.Build import cythonize
setup(name="meshgate-native-core", ext_modules=cythonize(
    [Extension("_meshgate_" + n, ["_meshgate_" + n + ".py"]) for n in %r],
    compiler_directives={"language_level": 3, "binding": True,
                         "embedsignature": False, "emit_code_comments": False,
                         "annotation_typing": False, "infer_types": False}))
''' % (tuple(modules),)
        (work / "setup.py").write_text(setup, encoding="utf-8")
        subprocess.run([sys.executable, "setup.py", "build_ext", "--build-lib", str(core)], cwd=work, check=True)
        suffix = sysconfig.get_config_var("EXT_SUFFIX")
        for name, rel in modules.items():
            library = core / f"_meshgate_{name}{suffix}"
            if not library.is_file():
                raise RuntimeError(f"Compiled library missing: {name}")
            if sys.platform != "win32":
                strip = shutil.which("strip")
                if not strip:
                    raise RuntimeError("strip is required to remove debug information from native libraries")
                subprocess.run([strip, "-S", str(library)], check=True)
            destination = stage / Path(rel).parent
            destination.mkdir(parents=True, exist_ok=True)
            if destination != core:
                shutil.move(library, destination / library.name)
            # Load by file path: Blender's add-on also loads validators with spec_from_file_location.
            wrapper = '''"""Native MeshGate validator entry point. See LICENSE."""
import sys as _runtime
if _runtime.implementation.cache_tag != %r:
    raise RuntimeError("Use the Python runtime shipped with MeshGate")
import importlib.util as _util
from pathlib import Path as _Path
_spec = _util.spec_from_file_location(%r, _Path(__file__).with_name(%r))
_native = _util.module_from_spec(_spec)
_spec.loader.exec_module(_native)
globals().update({k: v for k, v in vars(_native).items() if not k.startswith("__")})
if __name__ == "__main__":
    raise SystemExit(_native.main())
''' % (sys.implementation.cache_tag, f"_meshgate_{name}", f"_meshgate_{name}{suffix}")
            (stage / rel).write_text(wrapper, encoding="utf-8")
        if not studio:
            shutil.copy2(ROOT / "core/profiles.json", core / "profiles.json")
        shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
        (stage / "native-core.json").write_text(json.dumps({
            "python": platform.python_version(), "cache_tag": sys.implementation.cache_tag,
            "platform": sysconfig.get_platform(), "modules": list(modules), "files": list(modules.values()),
            "cython": Cython.__version__, "setuptools": setuptools.__version__,
        }, indent=2) + "\n", encoding="utf-8")
        # Fail before producing an archive if imports, profile lookup or CLI entry points break.
        if not studio:
            subprocess.run([sys.executable, "-c",
                        "import validate_glb, validate_fbx; "
                        "assert len(validate_glb.load_profiles()['order']) == 4; "
                            "assert callable(validate_fbx.inspect)"], cwd=core, check=True)
            for name in MODULES:
                subprocess.run([sys.executable, str(core / f"{name}.py"), "--help"],
                               stdout=subprocess.DEVNULL, check=True)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for file in sorted(stage.rglob("*")):
                if file.is_file() and "__pycache__" not in file.parts:
                    z.write(file, file.relative_to(stage))
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist/native-core")
    parser.add_argument("--studio", action="store_true", help="compile Studio orchestration; leave Blender modules portable")
    args = parser.parse_args()
    print(build(args.out.resolve(), args.studio))
