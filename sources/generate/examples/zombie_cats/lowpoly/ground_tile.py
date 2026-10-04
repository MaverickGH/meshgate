"""Square 2x2 m ground tile: low-poly patchy grass and dry dirt with pressed cat paw prints."""
import math


def build(mg):
    # bold flat palette (one material)
    mg.color("grass", (0.24, 0.45, 0.18), rough=0.9)
    mg.color("grass_lt", (0.35, 0.56, 0.24), rough=0.9)
    mg.color("grass_dk", (0.15, 0.33, 0.13), rough=0.9)
    mg.color("olive", (0.44, 0.5, 0.22), rough=0.9)
    mg.color("dirt", (0.42, 0.29, 0.16), rough=0.95)
    mg.color("dirt_dk", (0.3, 0.19, 0.1), rough=0.95)
    mg.color("paw", (0.2, 0.12, 0.06), rough=1.0)

    S = 2.0                       # tile edge
    base = 0.035                  # base thickness
    N = {"mobile-low": 8, "mobile-mid": 10, "mobile-high": 14, "pc": 18}[mg.tier]
    cell = S / N
    grass = ["grass", "grass", "grass_lt", "grass_dk", "olive"]
    dirts = ["dirt", "dirt", "dirt_dk"]

    # scattered dirt-blob centres for organic patches
    blobs = [(mg.rng.uniform(-0.8, 0.8), mg.rng.uniform(-0.8, 0.8),
              mg.rng.uniform(0.18, 0.4)) for _ in range(5)]

    parts = []
    for i in range(N):
        for j in range(N):
            cx = -S / 2 + (i + 0.5) * cell
            cy = -S / 2 + (j + 0.5) * cell
            edge = i == 0 or j == 0 or i == N - 1 or j == N - 1
            # dirt where near a blob centre
            is_dirt = any((cx - bx) ** 2 + (cy - by) ** 2 < br ** 2 for bx, by, br in blobs)
            col = mg.rng.choice(dirts if is_dirt else grass)
            # subtle top bump on interior cells only -> seamless flat edges
            h = base if edge else base + mg.rng.uniform(0.0, 0.014)
            parts.append(mg.part("cube", col, loc=(cx, cy, h / 2),
                                 scale=(cell, cell, h)))

    # trail of cat paw prints pressed into the surface
    def paw(px, py, s):
        pp = []
        zt = base - 0.004
        pp.append(mg.part("cyl", "paw", loc=(px, py, zt),
                          scale=(0.07 * s, 0.055 * s, 0.01), vertices=8))
        if mg.at_least("mobile-mid"):
            for a in (-0.7, -0.24, 0.24, 0.7):
                tx = px + math.sin(a) * 0.065 * s
                ty = py + math.cos(a) * 0.065 * s
                pp.append(mg.part("cyl", "paw", loc=(tx, ty, zt),
                                  scale=(0.026 * s, 0.026 * s, 0.01), vertices=6))
        return pp

    trail = [(-0.55, -0.35), (-0.2, 0.05), (0.2, 0.25), (0.55, 0.55)]
    for k, (px, py) in enumerate(trail):
        if k % 2 == 0 or mg.at_least("mobile-mid"):
            parts += paw(px, py, 1.0)

    mg.join("zc_ground_tile", parts)
