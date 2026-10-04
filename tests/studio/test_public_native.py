"""Verify that public Studio entry points contain loaders and checked native packages."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FILES = ("meshgate.py", "apps/studio/server.py", "sources/generate/generate.py",
         "sources/generate/bridge.py", "sources/generate/components.py")
index = json.loads((ROOT / "native/studio/index.json").read_text())
assert set(index["packages"]) == {"macos-arm64", "windows-x64", "linux-x64"}
for rel in FILES:
    text = (ROOT / rel).read_text()
    assert "native_loader import load" in text and len(text) < 1000, rel
for platform, record in index["packages"].items():
    path = ROOT / "native/studio" / record["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"], platform
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert sum(n.endswith((".so", ".pyd")) for n in names) == 5, names
        assert not any(p.endswith((".c", ".cpp", ".pyx", ".pdb", ".map", ".lib", ".exp")) for p in names), names
        assert set(p for p in names if p.endswith(".py")) == set(FILES)
        for rel in FILES:
            text = z.read(rel).decode()
            assert "_spec.loader.exec_module(_native)" in text and len(text) < 1000
        metadata = json.loads(z.read("native-core.json"))
        assert metadata["cache_tag"] == "cpython-311"
        assert set(metadata["files"]) == set(FILES)
        assert "LICENSE" in names
print("Public native packages: three platforms, checksums and source exclusion passed")
