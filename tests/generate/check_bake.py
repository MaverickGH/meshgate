#!/usr/bin/env python3
"""Read the base-colour texture of a GLB (PNG) and report its colour content — proves a bake produced colour.

    python3 tests/generate/check_bake.py asset.glb [--blender=PATH]   → JSON (JPEG textures are decoded by Blender) {"mean": [r, g, b], "red": share, "blue": share, "dark": share}
"""
import json
import struct
import sys
import zlib
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

def png_pixels(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, idat, w, h, bpp = 8, b"", 0, 0, 3
    while pos < len(data):
        n, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and ctype in (2, 6), f"unsupported PNG (depth {depth}, type {ctype})"
            bpp = 3 if ctype == 2 else 4
        elif tag == b"IDAT":
            idat += body
        pos += 12 + n
    raw, stride, out, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out.append(bytes(line))
        prev = line
    return w, h, bpp, out


def base_colour_png(glb: str) -> bytes:
    d = open(glb, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    j = json.loads(d[20:20 + n])
    binoff = 20 + n + 8
    mat = j["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    img = j["images"][j["textures"][mat]["source"]]
    bv = j["bufferViews"][img["bufferView"]]
    return d[binoff + bv.get("byteOffset", 0): binoff + bv.get("byteOffset", 0) + bv["byteLength"]]


BLENDER_STATS = """
import bpy, json, sys
img = bpy.data.images.load(sys.argv[-1])
w, h = img.size
px = list(img.pixels)
rows = []
for y in range(h):
    base = y * w * 4
    rows.append(bytes(int(max(0.0, min(1.0, px[base + x * 4 + c])) * 255 + 0.5) for x in range(w) for c in range(3)))
print("MESHGATE_PIXELS " + json.dumps({"w": w, "h": h}))
open(sys.argv[-1] + ".rgb", "wb").write(b"".join(rows))
"""


def decoded(image: bytes, blender: str | None):
    """(w, h, bpp, rows) for PNG directly; JPEG through Blender, which every MeshGate check already has."""
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return png_pixels(image)
    if not blender:
        raise SystemExit("the texture is JPEG: pass --blender to decode it")
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        src, script = f"{tmp}/tex.jpg", f"{tmp}/stats.py"
        open(src, "wb").write(image)
        open(script, "w").write(BLENDER_STATS)
        out = subprocess.run([blender, "-b", "--factory-startup", "-P", script, "--", src], capture_output=True, text=True).stdout
        meta = json.loads(out.split("MESHGATE_PIXELS ", 1)[1].splitlines()[0])
        raw = open(src + ".rgb", "rb").read()
    w, h = meta["w"], meta["h"]
    return w, h, 3, [raw[y * w * 3:(y + 1) * w * 3] for y in range(h)]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--blender")]
    blender = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--blender=")), None)
    w, h, bpp, rows = decoded(base_colour_png(args[0]), blender)
    total, s, red, blue, dark = 0, [0, 0, 0], 0, 0, 0
    for row in rows[::4]:
        for x in range(0, w * bpp, bpp * 4):
            r, g, b = row[x], row[x + 1], row[x + 2]
            total += 1
            s[0] += r; s[1] += g; s[2] += b
            red += r > 120 and r > 2 * max(g, b)
            blue += b > 100 and b > 1.6 * max(r, g)
            dark += max(r, g, b) < 12
    print(json.dumps({"size": [w, h], "mean": [round(v / total) for v in s], "red": round(red / total, 3),
                      "blue": round(blue / total, 3), "dark": round(dark / total, 3)}))


if __name__ == "__main__":
    main()
