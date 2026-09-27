"""Tiling materials for big surfaces: seamless texture sets (colour, normal, occlusion-roughness-metallic) drawn with
numpy, for walls, floors, roads, roofs and ground that a single colour atlas cannot cover at a readable scale.

Every pattern is periodic by construction — the lattice noise wraps, cells and boards are laid out on the tile — so
the image repeats with no seam. One tile covers `size` meters; the kit maps it over the surface by world position.
"""

from __future__ import annotations

import os

import numpy as np

PATTERNS = ("bricks", "planks", "tiles", "cobble", "shingles", "plates", "plaster", "ground")


def _noise(px: int, cells: int, rng, octaves: int = 4) -> np.ndarray:
    """Periodic fractal value noise in 0..1: each octave's lattice wraps around the tile."""
    out = np.zeros((px, px), np.float32)
    amp, total = 1.0, 0.0
    t = (np.arange(px, dtype=np.float32) + 0.5) / px
    for o in range(octaves):
        k = cells * 2 ** o
        grid = rng.random((k, k)).astype(np.float32)
        x = t * k
        i0 = np.floor(x).astype(int) % k
        i1 = (i0 + 1) % k
        f = x - np.floor(x)
        f = f * f * (3 - 2 * f)
        rows = grid[i0][:, i0] * (1 - f)[None, :] + grid[i0][:, i1] * f[None, :]
        rows1 = grid[i1][:, i0] * (1 - f)[None, :] + grid[i1][:, i1] * f[None, :]
        out += amp * (rows * (1 - f)[:, None] + rows1 * f[:, None])
        total += amp
        amp *= 0.5
    return out / total


def _grid_uv(px: int):
    t = (np.arange(px, dtype=np.float32) + 0.5) / px
    return np.meshgrid(t, t)   # u across (columns), v up (rows; row 0 is the bottom in Blender)


def _cells(px, cols, rows, gap, offset_rows=0.5, rng=None, bevel=0.35):
    """Running-bond cells (bricks, tiles, shingles): per-pixel cell id, and a 0..1 height that falls at the joints."""
    u, v = _grid_uv(px)
    r = np.floor(v * rows)
    uu = u * cols + (r % 2) * offset_rows * (1 if offset_rows else 0)
    c = np.floor(uu) % cols
    fu, fv = uu - np.floor(uu), v * rows - r
    edge = np.minimum(np.minimum(fu, 1 - fu) * (1.0 / cols) * px, np.minimum(fv, 1 - fv) * (1.0 / rows) * px)
    g = gap * px   # joint half-width in px
    h = np.clip((edge - g) / max(g * bevel * 4, 1.0), 0.0, 1.0)
    cid = (r * cols + c).astype(int)
    return cid, h


def _voronoi(px, n, rng):
    """Periodic cells (cobbles, flagstones): cell id and the distance to the nearest edge, via wrapped seeds."""
    seeds = rng.random((n, 2)).astype(np.float32)
    u, v = _grid_uv(px)
    best = np.full((px, px), 9.0, np.float32)
    second = np.full((px, px), 9.0, np.float32)
    cid = np.zeros((px, px), int)
    for i, (sx, sy) in enumerate(seeds):
        dx = np.abs(u - sx); dx = np.minimum(dx, 1 - dx)
        dy = np.abs(v - sy); dy = np.minimum(dy, 1 - dy)
        d = np.sqrt(dx * dx + dy * dy)
        closer = d < best
        second = np.where(closer, best, np.minimum(second, d))
        cid = np.where(closer, i, cid)
        best = np.where(closer, d, best)
    return cid, second - best


def draw(pattern: str, rgb, rgb2=None, *, px: int = 512, seed: int = 1, rough: float = 0.7, metal: float = 0.0):
    """(colour sRGB, height 0..1, roughness, metallic) arrays, px × px, for one tile of a pattern."""
    rng = np.random.default_rng(seed)
    base = np.asarray(rgb, np.float32)
    joint = np.asarray(rgb2, np.float32) if rgb2 is not None else None
    fine = _noise(px, 8, rng, 5)
    grain = _noise(px, 32, rng, 3)
    if pattern in ("bricks", "tiles", "shingles"):
        cols, rows, gap = {"bricks": (4, 12, 0.006), "tiles": (4, 4, 0.004), "shingles": (6, 8, 0.004)}[pattern]
        cid, h = _cells(px, cols, rows, gap, 0.5 if pattern != "tiles" else 0.0, rng)
        var = rng.random(cid.max() + 1).astype(np.float32)[cid]
        if pattern == "shingles":   # each row overlaps the one below: brighter at the bottom lip, darker under it
            _, v = _grid_uv(px)
            fv = v * rows - np.floor(v * rows)
            h = h * (0.55 + 0.45 * (1 - fv))
        joint = joint if joint is not None else (np.array([0.62, 0.6, 0.56]) if pattern != "shingles" else base * 0.35)
        tint = 0.82 + 0.3 * var[..., None] + 0.12 * (fine[..., None] - 0.5)
        col = np.where(h[..., None] > 0.02, base * tint, joint * (0.9 + 0.2 * fine[..., None]))
        height = 0.15 + 0.85 * h + 0.05 * grain * h
        rgh = np.where(h > 0.02, rough + 0.1 * (var - 0.5), min(rough + 0.15, 1.0))
    elif pattern == "planks":
        boards = 5
        u, v = _grid_uv(px)
        b = np.floor(u * boards)
        fu = u * boards - b
        shift = rng.random(boards).astype(np.float32)[b.astype(int)]
        vv = (v + shift) % 1.0
        seam = np.minimum(vv, 1 - vv) * px < 1.5   # one butt joint per board, at a random height
        edge = np.minimum(fu, 1 - fu) / boards * px
        h = np.clip((edge - 1.0) / 3.0, 0, 1) * np.where(seam, 0.0, 1.0)
        var = rng.random(boards).astype(np.float32)[b.astype(int)]
        stripes = _noise(px, 4, rng, 4)
        streak = 0.5 + 0.5 * np.sin((u * boards * 7 + stripes * 5) * np.pi * 2)   # grain along the board
        tint = 0.78 + 0.28 * var[..., None] + 0.14 * (streak[..., None] - 0.5) + 0.1 * (fine[..., None] - 0.5)
        col = np.where(h[..., None] > 0.02, base * tint, base * 0.25)
        height = 0.2 + 0.8 * h + 0.04 * streak * h
        rgh = rough + 0.08 * (streak - 0.5)
    elif pattern == "cobble":
        cid, edge = _voronoi(px, 22, rng)
        h = np.clip(edge * px / 6.0, 0, 1) ** 0.6
        var = rng.random(cid.max() + 1).astype(np.float32)[cid]
        joint = joint if joint is not None else base * 0.45
        col = np.where(h[..., None] > 0.05, base * (0.75 + 0.4 * var[..., None] + 0.15 * (fine[..., None] - 0.5)),
                       joint * (0.8 + 0.3 * fine[..., None]))
        height = h * (0.85 + 0.15 * grain)
        rgh = np.where(h > 0.05, rough - 0.1 * var, min(rough + 0.2, 1.0))
    elif pattern == "plates":
        cid, h = _cells(px, 2, 2, 0.003, 0.0, rng, bevel=0.2)
        u, v = _grid_uv(px)
        fu, fv = (u * 2) % 1.0, (v * 2) % 1.0
        rivet = np.zeros_like(h)
        for cx in (0.06, 0.94):
            for cy in (0.06, 0.94):
                d = np.sqrt((fu - cx) ** 2 + (fv - cy) ** 2) * px / 2
                rivet = np.maximum(rivet, np.clip(1 - d / 5.0, 0, 1))
        var = rng.random(cid.max() + 1).astype(np.float32)[cid]
        col = base * (0.85 + 0.2 * var[..., None] + 0.12 * (grain[..., None] - 0.5))
        height = 0.2 + 0.7 * h + 0.3 * rivet
        rgh = rough + 0.2 * (fine - 0.5)
    else:   # plaster, ground: soft fractal variation, darker patches
        big = _noise(px, 3, rng, 5)
        dark = 0.75 + 0.45 * big[..., None] + 0.12 * (fine[..., None] - 0.5)
        if pattern == "ground" and joint is not None:   # patches of a second colour (moss, dirt, dry grass)
            mix = np.clip((big - 0.55) * 5, 0, 1)[..., None]
            col = base * dark * (1 - mix) + joint * dark * mix
        else:
            col = base * dark
        height = 0.5 * big + 0.5 * fine if pattern == "ground" else 0.3 * big + 0.7 * grain
        rgh = rough + 0.1 * (fine - 0.5)
    col = np.clip(col, 0.0, 1.0)
    return col, np.clip(height, 0.0, 1.0), np.clip(rgh, 0.04, 1.0), np.full((px, px), float(metal), np.float32)


def normal_from_height(height: np.ndarray, strength: float) -> np.ndarray:
    """Tangent-space normal map (0..1 RGB) from a periodic height field — neighbours wrap, so it stays seamless."""
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * strength
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * strength
    n = np.stack([-dx, -dy, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def cavity(height: np.ndarray) -> np.ndarray:
    """Occlusion from the height: joints and hollows darker (a periodic blur, so no seam either)."""
    blur = height.copy()
    for _ in range(3):
        blur = (blur + np.roll(blur, 2, 0) + np.roll(blur, -2, 0) + np.roll(blur, 2, 1) + np.roll(blur, -2, 1)) / 5
    return np.clip(1.0 - np.clip(blur - height, 0, 1) * 3.0 - (1 - height) * 0.25, 0.35, 1.0)


def make_images(bpy, name: str, spec: dict, px: int, tmp: str) -> dict:
    """Blender images for one tiling material: basecolor (sRGB), normal and ORM (non-colour), saved and packed."""
    col, height, rgh, met = draw(spec["pattern"], spec["rgb"], spec.get("rgb2"), px=px, seed=spec.get("seed", 1),
                                 rough=spec.get("rough", 0.7), metal=spec.get("metal", 0.0))
    ao = cavity(height)
    col = col * (0.55 + 0.45 * ao[..., None])   # joints read darker even where occlusion is not shown
    maps = {
        "basecolor": (col, False),
        "normal": (normal_from_height(height, strength=px / 64.0), True),
        "orm": (np.stack([ao, rgh, met], axis=-1), True),
    }
    out = {}
    for kind, (rgb, non_color) in maps.items():
        img = bpy.data.images.new(f"{name}_{kind}", px, px, alpha=False)
        if non_color:
            img.colorspace_settings.name = "Non-Color"
        # a byte image keeps its pixels in its own colour space: sRGB values go in as they are (as the palette does)
        rgba = np.concatenate([rgb.astype(np.float32), np.ones((px, px, 1), np.float32)], axis=-1)
        img.pixels.foreach_set(rgba.ravel())
        path = os.path.join(tmp, f"{name}_{kind}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        img.pack()
        img.filepath_raw = f"//textures/{name}_{kind}.png"
        out[kind] = img
    return out
