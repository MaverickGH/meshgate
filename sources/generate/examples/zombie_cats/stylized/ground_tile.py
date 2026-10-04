"""Square ground tile 2x2m ~4cm thick: patchy grass and dry dirt with cat paw prints. Tiles seamlessly (flat straight edges)."""
import math


def build(mg):
    # --- palette: harmonious stylized grass + dry dirt ---
    grass = [
        mg.color("grass_mid", "#4a7a34", rough=0.85),
        mg.color("grass_light", "#5f8f3e", rough=0.85),
        mg.color("grass_dark", "#37642a", rough=0.88),
        mg.color("grass_olive", "#6e8438", rough=0.85),
    ]
    dirt = [
        mg.color("dirt_mid", "#6b4a2a", rough=0.9),
        mg.color("dirt_dark", "#48321f", rough=0.9),
        mg.color("dirt_dry", "#8a6a3c", rough=0.88),
    ]
    paw_col = mg.color("paw", "#241708", rough=0.95)

    size = 2.0
    base_th = 0.028          # solid slab so the tile is closed and seamless
    top_th = 0.014           # colored surface cells
    top_z = base_th          # cells sit on the slab

    # grid resolution scales with tier
    n = {0: 8, 1: 11, 2: 14, 3: 18}[mg.level]
    cell = size / n
    half = size / 2.0

    parts = []
    # closed dirt slab (bottom, edges flat and straight -> tiles seamlessly)
    parts.append(mg.part("cube", "dirt_dark", loc=(0, 0, base_th / 2),
                         scale=(size, size, base_th)))

    # patch layout: a seeded value-ish noise so grass and dirt form readable blobs
    def patch(ix, iy):
        v = math.sin(ix * 0.9 + 0.5) + math.cos(iy * 0.8 - 0.3) \
            + math.sin((ix + iy) * 0.55) + mg.rng.uniform(-0.7, 0.7)
        if v < -0.6:
            return mg.rng.choice(dirt)
        return mg.rng.choice(grass)

    # colored top cells; border cells kept flat for seamless edges
    for iy in range(n):
        for ix in range(n):
            cx = -half + (ix + 0.5) * cell
            cy = -half + (iy + 0.5) * cell
            col = patch(ix, iy)
            border = ix == 0 or iy == 0 or ix == n - 1 or iy == n - 1
            bump = 0.0 if border else mg.rng.uniform(0.0, 0.008)
            h = top_th + bump
            parts.append(mg.part("cube", col, loc=(cx, cy, top_z + h / 2),
                                 scale=(cell * 1.001, cell * 1.001, h)))

    surf = top_z + top_th

    # --- cat paw prints pressed into the surface along a diagonal trail ---
    def paw(x, y, ang, s):
        ca, sa = math.cos(ang), math.sin(ang)
        def place(ox, oy, rx, ry):
            px = x + ox * ca - oy * sa
            py = x * 0 + y + ox * sa + oy * ca
            parts.append(mg.part("sphere", paw_col,
                                 loc=(px, py, surf - 0.003),
                                 scale=(rx * s, ry * s, 0.02),
                                 segments=10, ring_count=6))
        # main pad
        place(0.0, -0.045 * 1, 0.075, 0.06)
        # four toe beans
        for tx in (-0.06, -0.02, 0.02, 0.06):
            place(tx, 0.05, 0.028, 0.032)

    trail = [(-0.55, -0.45, 0.5), (-0.05, 0.05, 0.7),
             (0.45, 0.5, 0.4)]
    if mg.at_least("mobile-mid"):
        trail.insert(1, (-0.3, -0.2, 0.6))
        trail.append((0.15, 0.28, 0.55))
    for (px, py, a) in trail:
        paw(px, py, a, 1.0)

    mg.join("zc_ground_tile", parts)
