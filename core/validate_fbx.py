#!/usr/bin/env python3
"""MeshGate — FBX check (the fallback path for engine editors).

FBX is a proprietary binary format; it cannot be fully validated the way GLB can. This script
parses the binary FBX container (7.x) and extracts what matters for import into Unity/Unreal:
units (UnitScaleFactor), axes, the list of models and meshes, animations (AnimationStack),
embedded textures, materials. Pure stdlib.

    python3 core/validate_fbx.py path/to/asset.fbx [--json] [--strict]
Exit code: 0 — ok, 1 — errors (or warnings with --strict), 2 — not a binary FBX.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

_MAGIC = b"Kaydara FBX Binary  \x00"


class FbxError(Exception):
    pass


def _read_prop(data: bytes, pos: int) -> tuple[Any, int]:
    t = data[pos:pos + 1]
    pos += 1
    if t in b"CYIFDL":
        fmt = {b"C": "<?", b"Y": "<h", b"I": "<i", b"F": "<f", b"D": "<d", b"L": "<q"}[t]
        return struct.unpack_from(fmt, data, pos)[0], pos + struct.calcsize(fmt)
    if t in b"SR":
        n = struct.unpack_from("<I", data, pos)[0]
        raw = data[pos + 4:pos + 4 + n]
        return (raw.decode("utf-8", "replace") if t == b"S" else raw), pos + 4 + n
    if t in b"fdlibc":
        count, enc, comp_len = struct.unpack_from("<III", data, pos)
        pos += 12
        raw = data[pos:pos + comp_len]
        if enc == 1:
            raw = zlib.decompress(raw)
        fmt = {b"f": "f", b"d": "d", b"l": "q", b"i": "i", b"b": "?", b"c": "b"}[t]
        return list(struct.unpack_from(f"<{count}{fmt}", raw, 0)), pos + comp_len
    raise FbxError(f"unknown property type {t!r} at offset {pos}")


def parse_fbx(path: Path) -> tuple[int, list[dict]]:
    data = path.read_bytes()
    if not data.startswith(_MAGIC):
        raise FbxError("no 'Kaydara FBX Binary' signature — this is ASCII FBX or not FBX at all (the validator only reads binary)")
    version = struct.unpack_from("<I", data, 23)[0]
    big = version >= 7500
    hdr = "<QQQB" if big else "<IIIB"
    hdr_len = struct.calcsize(hdr)

    def read_node(pos: int) -> tuple[dict | None, int]:
        end, nprops, _plen, nlen = struct.unpack_from(hdr, data, pos)
        pos += hdr_len
        if end == 0:
            return None, pos
        name = data[pos:pos + nlen].decode("ascii", "replace")
        pos += nlen
        props = []
        for _ in range(nprops):
            v, pos = _read_prop(data, pos)
            props.append(v)
        children = []
        while pos < end:
            child, pos = read_node(pos)
            if child is None:
                break
            children.append(child)
        return {"name": name, "props": props, "children": children}, end

    nodes = []
    pos = 27
    while pos < len(data):
        node, pos = read_node(pos)
        if node is None:
            break
        nodes.append(node)
    return version, nodes


def _find(nodes: list[dict], name: str) -> list[dict]:
    return [n for n in nodes if n["name"] == name]


def _p70(node: dict) -> dict[str, Any]:
    """Properties from a Properties70 block → {name: value(s)}."""
    out = {}
    for p70 in _find(node["children"], "Properties70"):
        for p in _find(p70["children"], "P"):
            out[p["props"][0]] = p["props"][4:] if len(p["props"]) > 5 else (p["props"][4] if len(p["props"]) > 4 else None)
    return out


def inspect(path: Path) -> dict[str, Any]:
    version, root = parse_fbx(path)
    errors, warnings, notes = [], [], []

    gs = _find(root, "GlobalSettings")
    settings = _p70(gs[0]) if gs else {}
    unit = settings.get("UnitScaleFactor")
    up = settings.get("UpAxis"); front = settings.get("FrontAxis"); coord = settings.get("CoordAxis")
    if unit is None:
        warnings.append("no GlobalSettings.UnitScaleFactor — units unknown")
    elif abs(unit - 100.0) < 1e-6:
        notes.append("UnitScaleFactor = 100 → units are meters (Unity: File Scale 1, Unreal: no rescale)")
    else:
        warnings.append(f"UnitScaleFactor = {unit:g} — not meters (1 = centimeters: Unity will set File Scale 0.01, objects may arrive ×100)")
    if up is not None and up != 1:
        warnings.append(f"UpAxis = {up} — expected 1 (Y-up)")

    objects = _find(root, "Objects")
    obj_children = objects[0]["children"] if objects else []
    models = [n for n in obj_children if n["name"] == "Model"]
    geoms = [n for n in obj_children if n["name"] == "Geometry"]
    stacks = [n for n in obj_children if n["name"] == "AnimationStack"]
    materials = [n for n in obj_children if n["name"] == "Material"]
    videos = [n for n in obj_children if n["name"] == "Video"]
    textures = [n for n in obj_children if n["name"] == "Texture"]

    def _name(n: dict) -> str:
        raw = n["props"][1] if len(n["props"]) > 1 else ""
        return raw.split("\x00")[0]

    model_names = [_name(m) for m in models]
    mesh_models = [_name(m) for m in models if len(m["props"]) > 2 and m["props"][2] == "Mesh"]
    anim_names = [_name(s) for s in stacks]
    mat_names = [_name(m) for m in materials]
    embedded = sum(1 for v in videos if any(c["name"] == "Content" and c["props"] and len(c["props"][0]) > 0 for c in v["children"]))

    if not models:
        errors.append("no models at all (Objects/Model)")
    if not geoms:
        errors.append("no geometry (Objects/Geometry)")
    scaled = []
    for m in models:
        sc = _p70(m).get("Lcl Scaling")
        if sc and any(abs(v - 1.0) > 1e-4 for v in sc[:3]):
            scaled.append(_name(m))
    if scaled:
        warnings.append(f"scale ≠ 1 on models: {', '.join(scaled[:5])} — will show up in Unity/Unreal as unapplied scale")
    bad = [n for n in model_names if n and not all(c.isascii() and (c.isalnum() or c in "_-.") for c in n)]
    if bad:
        warnings.append(f"names with spaces/non-Latin characters: {', '.join(bad[:5])}")
    if textures and embedded < len(videos):
        warnings.append(f"{embedded} of {len(videos)} textures embedded — the rest are external files")
    triangles = 0
    for g in geoms:
        for pvi in _find(g["children"], "PolygonVertexIndex"):
            triangles += sum(1 for i in pvi["props"][0] if i < 0)  # each face ends with a negative index
    dup = sorted({n for n in anim_names if anim_names.count(n) > 1})
    if dup:
        notes.append(f"duplicate take names: {', '.join(dup)} — FBX bakes one take per object NLA strip; a clip spanning N objects yields N takes (a single one in GLB)")
    notes.append("FBX materials are Phong/Lambert: roughness/metallic maps do not carry over via FBX, only albedo/normal/emissive; use GLB for PBR")

    size_mb = path.stat().st_size / (1024 * 1024)
    return {
        "file": path.name, "fbx_version": version, "size_mb": round(size_mb, 3),
        "unit_scale_factor": unit, "up_axis": up, "front_axis": front, "coord_axis": coord,
        "models": len(models), "mesh_models": mesh_models, "geometries": len(geoms), "polygons": triangles,
        "materials": mat_names, "textures": len(textures), "embedded_textures": embedded,
        "animations": anim_names,
        "errors": errors, "warnings": warnings, "notes": notes,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):   # Windows consoles and pipes default to cp1252; MeshGate prints ✓ and —
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="MeshGate — binary FBX check.")
    ap.add_argument("fbx", type=Path, nargs="+")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    worst = 0
    for i, path in enumerate(args.fbx):
        if i and not args.json:
            print()
        if not path.is_file():
            print(f"✗ file not found: {path}")
            worst = 2
            continue
        try:
            r = inspect(path)
        except (FbxError, struct.error, zlib.error, UnicodeDecodeError) as exc:
            print(f"✗ {path.name}: {exc}")
            worst = 2
            continue
        failed = bool(r["errors"]) or (args.strict and bool(r["warnings"]))
        r["ok"] = not failed
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f"— MeshGate validate FBX: {r['file']} —")
            print(f"  FBX {r['fbx_version']}   size: {r['size_mb']:.2f} MB   UnitScaleFactor: {r['unit_scale_factor']}   axes up/front/coord: {r['up_axis']}/{r['front_axis']}/{r['coord_axis']}")
            print(f"  models: {r['models']} (meshes: {len(r['mesh_models'])})   geometries: {r['geometries']}   polygons: {r['polygons']:,}")
            print(f"  materials: {', '.join(r['materials']) or '—'}")
            print(f"  textures: {r['textures']} (embedded: {r['embedded_textures']})   animations: {', '.join(r['animations']) or '—'}")
            for n in r["notes"]: print(f"  · {n}")
            for w in r["warnings"]: print(f"  ⚠ {w}")
            for e in r["errors"]: print(f"  ✗ {e}")
            print("Result: " + ("does NOT comply." if r["errors"] else "warnings (--strict)." if failed else "binary FBX parsed, no contract issues." + (" (with warnings)" if r["warnings"] else "")))
        worst = max(worst, 1 if failed else 0)
    return worst


if __name__ == "__main__":
    sys.exit(main())
