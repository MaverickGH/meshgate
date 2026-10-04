"""Compare packaged native validators with source validators (run with the build Python)."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive", type=Path)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        with zipfile.ZipFile(args.archive) as z:
            names = z.namelist()
            assert not any(n.endswith((".c", ".pyx", ".pyc", ".pdb")) for n in names), names
            assert set(n for n in names if n.endswith(".py")) == {
                "core/validate_glb.py", "core/validate_fbx.py"}
            z.extractall(stage)
        metadata = json.loads((stage / "native-core.json").read_text())
        assert metadata["cache_tag"] == sys.implementation.cache_tag
        corrupt = stage / "corrupt.glb"
        corrupt.write_bytes(b"not a model")
        cases = [("validate_glb", ROOT / "samples/meshgate_demo.glb"),
                 ("validate_glb", corrupt), ("validate_glb", stage / "missing.glb"),
                 ("validate_fbx", ROOT / "samples/meshgate_demo.fbx")]
        assert cases[0][1].is_file() and cases[-1][1].is_file(), "Demo assets missing"
        for module, asset in cases:
            commands = [[sys.executable, str(base / "core" / f"{module}.py"),
                         str(asset), "--json", "--strict"] for base in (ROOT, stage)]
            results = [subprocess.run(c, capture_output=True, text=True) for c in commands]
            assert results[0].returncode == results[1].returncode, results
            assert results[0].stdout == results[1].stdout, results
            assert not results[1].stderr, results[1].stderr
        # Blender loads validator entry points by absolute path, without core on sys.path.
        for name in ("validate_glb", "validate_fbx"):
            spec = importlib.util.spec_from_file_location("meshgate_" + name, stage / "core" / f"{name}.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert callable(mod.main)
            if name == "validate_glb":
                assert len(mod.load_profiles()["order"]) == 4
    print("Native package: source parity, invalid/missing inputs and absolute-path loading passed")


if __name__ == "__main__":
    main()
