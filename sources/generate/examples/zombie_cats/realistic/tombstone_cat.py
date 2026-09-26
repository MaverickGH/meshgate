"""Cat-shaped tombstone: eared stone slab with a carved paw print on a low base, glowing green goo puddle."""
import math


def build(mg):
    stone = mg.color("stone", (0.55, 0.55, 0.51), rough=0.92)
    stone_d = mg.color("stone_d", (0.34, 0.34, 0.30), rough=0.9)
    stone_b = mg.color("stone_b", (0.62, 0.62, 0.57), rough=0.88)
    moss = mg.color("moss", (0.32, 0.36, 0.20), rough=0.95)
    goo = mg.color("goo", (0.35, 0.95, 0.18), rough=0.25, glow=2.4)
    goo_d = mg.color("goo_d", (0.20, 0.60, 0.10), rough=0.3, glow=1.4)

    parts = []

    # ---- low stone base ----
    bw, bd, bh = 0.80, 0.34, 0.14
    parts.append(mg.part("cube", stone_b, loc=(0, 0, bh / 2),
                         scale=(bw, bd, bh), bevel=0.02))
    parts.append(mg.part("cube", stone, loc=(0, 0, bh - 0.02),
                         scale=(bw - 0.06, bd - 0.06, 0.04), bevel=0.015))

    # ---- the eared slab (front view outline in XZ) ----
    depth = 0.13
    outline = [
        (-0.35, 0.0), (-0.35, 0.80),
        (-0.28, 1.12),          # left ear tip
        (0.0, 0.84),            # notch between ears
        (0.28, 1.12),           # right ear tip
        (0.35, 0.80), (0.35, 0.0),
    ]
    parts.append(mg.extrude(outline, depth, stone, loc=(0, 0, 0.05),
                            bevel=0.018, smooth=False))

    # ---- carved paw print on the front face (-Y) ----
    fy = -depth / 2 - 0.005
    parts.append(mg.part("sphere", stone_d, loc=(0, fy, 0.71),
                         scale=(0.17, 0.05, 0.13)))
    toes = [(-0.115, 0.83), (-0.04, 0.875), (0.04, 0.875), (0.115, 0.83)]
    for tx, tz in toes:
        parts.append(mg.part("sphere", stone_d, loc=(tx, fy, tz),
                             scale=(0.058, 0.045, 0.07)))

    # ---- wear: mossy patches and chips on richer tiers ----
    if mg.at_least("mobile-mid"):
        for i in range(7):
            mx = mg.rng.uniform(-0.32, 0.32)
            mz = mg.rng.uniform(0.15, 1.0)
            parts.append(mg.part("sphere", moss, loc=(mx, fy + 0.01, mz),
                                 scale=(mg.rng.uniform(0.04, 0.09),
                                        0.02, mg.rng.uniform(0.04, 0.09))))
    if mg.at_least("mobile-high"):
        for i in range(5):
            cx = mg.rng.uniform(-0.34, 0.34)
            cz = mg.rng.uniform(0.2, 1.05)
            parts.append(mg.part("cube", stone_d,
                                 loc=(cx, fy + 0.005, cz),
                                 scale=(0.03, 0.03, 0.03),
                                 rot=(0, mg.rng.uniform(0, 3), 0),
                                 bevel=0.005))

    mg.join("zc_tombstone_cat", parts)

    # ---- glowing green goo puddle (kept as same-material blob) ----
    goo_parts = []
    goo_parts.append(mg.part("sphere", goo, loc=(0.40, 0.07, 0.012),
                             scale=(0.22, 0.17, 0.03)))
    goo_parts.append(mg.part("sphere", goo, loc=(0.30, -0.08, 0.010),
                             scale=(0.12, 0.10, 0.025)))
    goo_parts.append(mg.part("sphere", goo_d, loc=(0.52, 0.12, 0.012),
                             scale=(0.10, 0.09, 0.02)))
    if mg.at_least("mobile-mid"):
        for i in range(4):
            gx = mg.rng.uniform(0.25, 0.55)
            gy = mg.rng.uniform(-0.14, 0.16)
            goo_parts.append(mg.part("sphere", goo,
                                     loc=(gx, gy, 0.01),
                                     scale=(mg.rng.uniform(0.04, 0.08),
                                            mg.rng.uniform(0.04, 0.07), 0.02)))
    mg.join("zc_goo", goo_parts)
