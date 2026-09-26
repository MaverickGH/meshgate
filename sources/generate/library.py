#!/usr/bin/env python3
"""MeshGate library — find free 3D models you may use commercially, download them with their credit, refine them.

    python3 meshgate.py library search "sleeping cat" [--license cc0,by] [--max-faces 200000] [--count 12]
    python3 meshgate.py library get <uid>              # → ~/.meshgate/library/<uid>/ (model + credit.json)
    python3 meshgate.py library list
    python3 meshgate.py gen --library <uid> --size 0.4  # download if needed, then refine to every tier

Search runs on Sketchfab (no account needed). Only licences that allow commercial use and changes are offered:
CC0 (no credit needed) and CC-BY (credit the author); CC-BY-SA also works but makes your changed model CC-BY-SA too,
so it has to be asked for. NonCommercial, NoDerivs, Editorial and store licences are refused — the licence is
checked again on Sketchfab right before every download, and it travels with the model (credit.json) into the
generated asset (gen.json, CREDITS.txt).

Downloads come from the Objaverse mirror on Hugging Face (allenai/objaverse, ~800k Sketchfab models, no account)
when the model is in it; newer models download from Sketchfab itself with your API token (SKETCHFAB_API_TOKEN, from
sketchfab.com → Settings → Password & API). Models stay on your computer, outside the repository.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
import urllib.parse
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import keys  # noqa: E402
from mesh import net  # noqa: E402

API = "https://api.sketchfab.com/v3"
OBJAVERSE = "https://huggingface.co/datasets/allenai/objaverse/resolve/main"
# slug → (short name, what it asks of you); only these are ever downloaded
LICENSES = {
    "cc0": ("CC0", "no credit needed, any use"),
    "by": ("CC-BY 4.0", "credit the author; commercial use and changes allowed"),
    "by-sa": ("CC-BY-SA 4.0", "credit the author; your changed model must be CC-BY-SA as well"),
}
DEFAULT_LICENSES = ("cc0", "by")
REFUSED = {"by-nd": "no changes allowed", "by-nc": "no commercial use", "by-nc-sa": "no commercial use",
           "by-nc-nd": "no commercial use or changes", "ed": "editorial use only", "st": "store licence",
           "free-st": "store licence"}


class LibraryError(RuntimeError):
    pass


def folder() -> Path:
    return keys.folder() / "library"


def _get(path: str, params: dict | None = None, token: str | None = None) -> dict:
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    try:
        return net.request("GET", url, headers={"Authorization": f"Token {token}"} if token else None, timeout=60)
    except net.ProviderError as exc:
        raise LibraryError(str(exc)) from None


def license_slug(model: dict) -> str:
    """Sketchfab gives the licence as {uid, label} in search results and with a slug on the model page."""
    lic = model.get("license") or {}
    if lic.get("slug"):
        return lic["slug"]
    label = (lic.get("label") or "").lower()
    table = {"cc0 public domain": "cc0", "cc attribution": "by", "cc attribution-sharealike": "by-sa",
             "cc attribution-noderivs": "by-nd", "cc attribution-noncommercial": "by-nc",
             "cc attribution-noncommercial-sharealike": "by-nc-sa", "cc attribution-noncommercial-noderivs": "by-nc-nd",
             "editorial": "ed", "standard": "st", "free standard": "free-st"}
    return table.get(label, label or "unknown")


def check_license(slug: str, allowed=DEFAULT_LICENSES) -> None:
    if slug in REFUSED:
        raise LibraryError(f"licence {slug}: {REFUSED[slug]} — MeshGate only uses CC0 and CC-BY models")
    if slug not in LICENSES:
        raise LibraryError(f"licence '{slug}' is not one MeshGate can use (CC0, CC-BY, or CC-BY-SA when asked for)")
    if slug not in allowed:
        raise LibraryError(f"licence {LICENSES[slug][0]}: {LICENSES[slug][1]} — add --license {slug} to accept it")


def summary(m: dict) -> dict:
    slug = license_slug(m)
    user = m.get("user") or {}
    return {"uid": m["uid"], "name": m.get("name") or m["uid"], "author": user.get("displayName") or user.get("username"),
            "author_url": user.get("profileUrl") or (f"https://sketchfab.com/{user['username']}" if user.get("username") else None),
            "license": slug, "license_name": LICENSES.get(slug, (slug,))[0],
            "license_url": (m.get("license") or {}).get("url"),
            "url": m.get("viewerUrl") or f"https://sketchfab.com/3d-models/{m['uid']}",
            "faces": m.get("faceCount"), "animated": bool(m.get("animationCount")),
            "thumbnail": max((t for t in (m.get("thumbnails") or {}).get("images", []) if t.get("width", 0) <= 640),
                             key=lambda t: t.get("width", 0), default={}).get("url")}


def search(query: str, *, licenses=DEFAULT_LICENSES, count: int = 12, max_faces: int | None = None,
           animated: bool | None = None) -> list[dict]:
    """Downloadable models matching query, only under the given (usable) licences, most liked first per licence."""
    for slug in licenses:
        check_license(slug, licenses)
    groups = []
    for slug in licenses:
        params = {"type": "models", "q": query, "downloadable": "true", "license": slug, "count": min(24, count),
                  "sort_by": "-likeCount"}
        if max_faces:
            params["max_face_count"] = max_faces
        if animated is not None:
            params["animated"] = str(animated).lower()
        groups.append([summary(m) for m in _get("/search", params).get("results", [])])
    found = [g[i] for i in range(max(map(len, groups), default=0)) for g in groups if i < len(g)]   # licences take turns
    found = [f for f in found if f["license"] in licenses and (not max_faces or (f["faces"] or 0) <= max_faces)]
    return found[:count]


def _objaverse_paths() -> dict:
    """uid → path inside the Objaverse mirror (the 20 MB index is downloaded once and kept)."""
    cache = folder() / "objaverse-object-paths.json.gz"
    if not cache.exists() or cache.stat().st_size < 1000:
        cache.parent.mkdir(parents=True, exist_ok=True)
        print("  downloading the Objaverse index (20 MB, once)…", flush=True)
        net.download(f"{OBJAVERSE}/object-paths.json.gz", cache.with_suffix(".part"), timeout=600)
        os.replace(cache.with_suffix(".part"), cache)
    with gzip.open(cache, "rt", encoding="utf-8") as f:
        return json.load(f)


def _unpack_gltf_zip(archive: Path, dest: Path) -> Path:
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():   # stay inside dest: no absolute paths or ..
            target = (dest / member).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise LibraryError(f"unsafe path in the archive: {member}")
        z.extractall(dest)
    archive.unlink()
    scenes = sorted(dest.rglob("*.gltf")) + sorted(dest.rglob("*.glb"))
    if not scenes:
        raise LibraryError("the archive has no .gltf or .glb")
    return scenes[0]


def get(uid: str, *, licenses=DEFAULT_LICENSES, via: str = "auto", log=print) -> Path:
    """Download one model (licence re-checked first) into the library; returns the model file. Already there → reused."""
    uid = uid.strip().rsplit("-", 1)[-1].rsplit("/", 1)[-1]   # a full Sketchfab URL works too
    if not uid.isalnum() or len(uid) != 32:
        raise LibraryError(f"'{uid}' is not a Sketchfab model id (32 letters and digits)")
    dest = folder() / uid
    existing = model_file(dest)
    if existing:
        check_license(json.loads((dest / "credit.json").read_text(encoding="utf-8"))["license"], licenses)
        return existing
    info = summary(_get(f"/models/{uid}"))
    check_license(info["license"], licenses)
    dest.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("SKETCHFAB_API_TOKEN") or keys.load().get("SKETCHFAB_API_TOKEN")
    path, how = None, None
    if via in ("auto", "objaverse"):
        rel = _objaverse_paths().get(uid)
        if rel:
            log(f"  downloading {info['name']} from the Objaverse mirror…")
            path, how = net.download(f"{OBJAVERSE}/{rel}", dest / "model.glb", timeout=900), "objaverse"
        elif via == "objaverse":
            raise LibraryError("this model is not in the Objaverse mirror (it is newer) — use --via sketchfab")
    if path is None:
        if not token:
            raise LibraryError("this model is not in the free Objaverse mirror: add your Sketchfab API token "
                               "(SKETCHFAB_API_TOKEN, sketchfab.com → Settings → Password & API) to download it")
        links = _get(f"/models/{uid}/download", token=token)
        if links.get("glb", {}).get("url"):
            log(f"  downloading {info['name']} from Sketchfab (glb, {links['glb'].get('size', 0) / 2 ** 20:.1f} MB)…")
            path = net.download(links["glb"]["url"], dest / "model.glb", timeout=900)
        elif links.get("gltf", {}).get("url"):
            log(f"  downloading {info['name']} from Sketchfab (glTF archive)…")
            path = _unpack_gltf_zip(net.download(links["gltf"]["url"], dest / "model.zip", timeout=900), dest / "model")
        else:
            raise LibraryError("Sketchfab offered no glTF download for this model")
        how = "sketchfab"
    credit = {**info, "via": how, "fetched": time.strftime("%Y-%m-%d"), "file": str(path.relative_to(dest))}
    (dest / "credit.json").write_text(json.dumps(credit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def model_file(dest: Path) -> Path | None:
    try:
        credit = json.loads((dest / "credit.json").read_text(encoding="utf-8"))
        p = dest / credit["file"]
        return p if p.exists() else None
    except (OSError, ValueError, KeyError):
        return None


def credit_for(mesh_path: str | Path) -> dict | None:
    """The credit.json of a library model, found from its file path (the model may sit in a subfolder)."""
    p = Path(mesh_path).resolve()
    for d in [p.parent, *p.parents][:3]:
        f = d / "credit.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                return None
    return None


def credit_line(c: dict) -> str:
    """One attribution line in the form CC-BY asks for: title, author, source, licence."""
    return (f"\"{c['name']}\" by {c.get('author') or 'unknown'} ({c['url']}), {c['license_name']}"
            + (f" ({c['license_url']})" if c.get("license_url") else "") + ". Changed: refined by MeshGate.")


def entries() -> list[dict]:
    out = []
    for d in sorted(folder().glob("*/credit.json")):
        try:
            out.append(json.loads(d.read_text(encoding="utf-8")))
        except ValueError:
            pass
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="meshgate.py library", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="find downloadable CC0 / CC-BY models on Sketchfab")
    s.add_argument("query")
    s.add_argument("--license", default=",".join(DEFAULT_LICENSES), help="cc0,by (default) — by-sa when you accept it")
    s.add_argument("--count", type=int, default=12)
    s.add_argument("--max-faces", type=int)
    s.add_argument("--json", action="store_true")
    g = sub.add_parser("get", help="download a model with its credit into the library")
    g.add_argument("uid", help="Sketchfab model id or URL")
    g.add_argument("--license", default=",".join(DEFAULT_LICENSES))
    g.add_argument("--via", default="auto", choices=["auto", "objaverse", "sketchfab"])
    sub.add_parser("list", help="models already in the library")
    args = ap.parse_args(argv)
    keys.apply_env()
    try:
        if args.cmd == "search":
            lic = tuple(x.strip() for x in args.license.split(",") if x.strip())
            res = search(args.query, licenses=lic, count=args.count, max_faces=args.max_faces)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
                return 0
            for r in res:
                print(f"  {r['uid']}  {r['license_name']:12} {r['faces'] or 0:>9,} faces  {r['name'][:48]} — {r['author']}")
            print(f"{len(res)} models. Next: meshgate.py gen --library <uid> --size <meters>" if res else "Nothing found.")
        elif args.cmd == "get":
            lic = tuple(x.strip() for x in args.license.split(",") if x.strip())
            path = get(args.uid, licenses=lic, via=args.via)
            c = credit_for(path)
            print(f"✓ {path}\n  credit: {credit_line(c)}")
        else:
            for c in entries():
                print(f"  {c['uid']}  {c['license_name']:12} {c['name'][:48]} — {c.get('author')}")
            print(f"library: {folder()}")
    except (LibraryError, net.ProviderError, OSError) as exc:
        print(f"✗ {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
