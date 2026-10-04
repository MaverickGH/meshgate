#!/usr/bin/env python3
"""The free-model library without the network: licence gate, search, download routes, credit. Pure stdlib.

    python3 tests/generate/test_library.py
"""

import gzip
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sources" / "generate"))
tmp = tempfile.mkdtemp()
os.environ["MESHGATE_CONFIG_DIR"] = tmp
os.environ.pop("SKETCHFAB_API_TOKEN", None)
import library  # noqa: E402

FAILS = []


def step(name, ok, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def refused(fn):
    try:
        fn()
    except library.LibraryError as exc:
        return str(exc)
    return None


UID_A, UID_B, UID_NC = "a" * 32, "b" * 32, "c" * 32
MODELS = {
    UID_A: {"uid": UID_A, "name": "Old stump", "user": {"username": "ann", "displayName": "Ann"}, "faceCount": 900,
            "license": {"slug": "cc0", "label": "CC0 Public Domain", "url": "http://creativecommons.org/publicdomain/zero/1.0/"},
            "viewerUrl": f"https://sketchfab.com/3d-models/stump-{UID_A}"},
    UID_B: {"uid": UID_B, "name": "Cat", "user": {"username": "bob"}, "faceCount": 5000,
            "license": {"slug": "by", "label": "CC Attribution", "url": "http://creativecommons.org/licenses/by/4.0/"},
            "viewerUrl": f"https://sketchfab.com/3d-models/cat-{UID_B}"},
    UID_NC: {"uid": UID_NC, "name": "NC cat", "user": {"username": "eve"}, "license": {"label": "CC Attribution-NonCommercial"}},
}
calls = []


def fake_get(path, params=None, token=None):
    calls.append((path, params, token))
    if path == "/search":
        lic = params["license"]
        hits = [m for m in MODELS.values() if library.license_slug(m) == lic]
        return {"results": [{**m, "license": {"uid": "x", "label": m["license"]["label"]}} for m in hits]}
    if path.endswith("/download"):
        return {"gltf": {"url": "https://example.test/cat.zip"}}
    return MODELS[path.rsplit("/", 1)[-1]]


def fake_download(url, dest, timeout=300):
    dest = Path(dest)
    if url.endswith("object-paths.json.gz"):
        with gzip.open(dest, "wt", encoding="utf-8") as f:
            json.dump({UID_A: f"glbs/000-001/{UID_A}.glb"}, f)
    elif url.endswith(".zip"):
        with zipfile.ZipFile(dest, "w") as z:
            z.writestr("scene.gltf", "{}")
            z.writestr("scene.bin", "")
    else:
        dest.write_bytes(b"glTF" + b"\0" * 16)
    return dest


library._get = fake_get
library.net.download = fake_download

# licence gate
step("slug from a search-result label", library.license_slug({"license": {"label": "CC Attribution-ShareAlike"}}) == "by-sa")
step("NonCommercial refused", "no commercial use" in (refused(lambda: library.check_license("by-nc")) or ""))
step("NoDerivs refused", "no changes" in (refused(lambda: library.check_license("by-nd")) or ""))
step("CC-BY-SA needs asking for", "--license by-sa" in (refused(lambda: library.check_license("by-sa")) or ""))
step("CC0 and CC-BY pass", refused(lambda: library.check_license("cc0")) is None and refused(lambda: library.check_license("by")) is None)
step("searching an NC licence refused", refused(lambda: library.search("cat", licenses=("by-nc",))) is not None)

# search: only usable licences, both taking turns
res = library.search("cat")
step("search returns CC0 and CC-BY only", [r["license"] for r in res] == ["cc0", "by"], str(res))
step("search asks the server per licence", [c[1]["license"] for c in calls if c[0] == "/search"] == ["cc0", "by"])
step("max faces filters", [r["uid"] for r in library.search("cat", max_faces=1000)] == [UID_A])

# download: Objaverse mirror when there, else Sketchfab with a token
p = library.get(UID_A)
c = library.credit_for(p)
step("CC0 model downloaded from the Objaverse mirror", p.name == "model.glb" and c["via"] == "objaverse" and c["license"] == "cc0")
step("reused on the second get", library.get(UID_A) == p)
step("newer model without a token explains", "SKETCHFAB_API_TOKEN" in (refused(lambda: library.get(UID_B)) or ""))
os.environ["SKETCHFAB_API_TOKEN"] = "t" * 30
p2 = library.get(f"https://sketchfab.com/3d-models/cat-{UID_B}")
c2 = library.credit_for(p2)
step("glTF archive from Sketchfab unpacked", p2.suffix == ".gltf" and c2["via"] == "sketchfab")
step("token sent only to the download call", all(t is None for path, _, t in calls if not path.endswith("/download"))
     and any(t for path, _, t in calls if path.endswith("/download")))
step("NC model never downloaded", "no commercial use" in (refused(lambda: library.get(UID_NC)) or "")
     and not (Path(tmp) / "library" / UID_NC).exists())
line = library.credit_line(c2)
step("credit line names title, author, source and licence",
     all(x in line for x in ('"Cat"', "bob", UID_B, "CC-BY 4.0", "licenses/by/4.0")), line)
step("bad id refused", refused(lambda: library.get("not-an-id")) is not None)

# archives cannot write outside the model folder
evil = Path(tmp) / "evil.zip"
with zipfile.ZipFile(evil, "w") as z:
    z.writestr("../../outside.gltf", "{}")
step("archive path escape refused", refused(lambda: library._unpack_gltf_zip(evil, Path(tmp) / "x")) is not None)

print("Result: " + ("all library checks passed." if not FAILS else f"{len(FAILS)} failed: {', '.join(FAILS)}"))
sys.exit(1 if FAILS else 0)
