"""zc_ground_tile: 2x2 m square ground tile, patchy grass and dry dirt with pressed cat paw prints."""
import math


def build(mg):
    # clean base colours (grass greens + dry dirt) - one palette material
    greens = [
        mg.color("grass_light", "#6f8f36", rough=0.85),
        mg.color("grass", "#557d2c", rough=0.85),
        mg.color("grass_mid", "#48702a", rough=0.85),
        mg.color("grass_dark", "#37561f", rough=0.85),
        mg.color("olive", "#7e7b3a", rough=0.85),
    ]
    dirts = [
        mg.color("dirt", "#6b4a2b", rough=0.9),
        mg.color("dirt_light", "#82603a", rough=0.9),
        mg.color("dirt_dark", "#4a3019", rough=0.9),
    ]
    paw_col = mg.color("paw", "#3a2414", rough=0.95)

    size = 2.0
    thick = 0.04
    n = {0: 6, 1: 9, 2: 12, 3: 16}[mg.level]
    cell = size / n

    parts = []
    for iy in range(n):
        for ix in range(n):
            x = -size / 2 + (ix + 0.5) * cell
            y = -size / 2 + (iy + 0.5) * cell
            # weight toward grass, occasional dirt patches
            if mg.rng.random() < 0.72:
                col = mg.rng.choice(greens)
            else:
                col = mg.rng.choice(dirts)
            parts.append(mg.part("cube", col, loc=(x, y, thick / 2),
                                 scale=(cell, cell, thick), exact=True))

    # --- cat paw prints pressed into the surface, a diagonal trail ---
    def paw(cx, cy, ang, s):
        # main pad + four toe pads as shallow dark discs flush with the top
        top = thick + 0.001
        ph = 0.012
        pieces = []
        pieces.append(mg.part("cyl", paw_col, loc=(cx, cy, top - ph / 2),
                              scale=(0.055 * s, 0.045 * s, ph), vertices=10))
        for t in (-0.55, -0.18, 0.18, 0.55):
            tx = cx + math.cos(ang + t) * 0.06 * s
            ty = cy + math.sin(ang + t) * 0.06 * s
            pieces.append(mg.part("cyl", paw_col, loc=(tx, ty, top - ph / 2),
                                  scale=(0.022 * s, 0.022 * s, ph), vertices=8))
        return pieces

    if mg.at_least("mobile-mid"):
        trail = [(-0.6, -0.5), (-0.3, -0.15), (0.05, 0.25), (0.45, 0.6)]
    else:
        trail = [(-0.4, -0.3), (0.1, 0.3)]
    prev = None
    for (px, py) in trail:
        if prev is None:
            ang = math.pi / 3
        else:
            ang = math.atan2(py - prev[1], px - prev[0])
        parts.extend(paw(px, py, ang, 1.0))
        prev = (px, py)

    mg.join("zc_ground_tile", parts)
