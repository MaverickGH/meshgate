"""Barricade of stacked cardboard boxes with a zombie cat (ears + glowing eyes) hiding in the top box."""
import math


def build(mg):
    card = mg.color("cardboard", (0.62, 0.47, 0.27), rough=0.85)
    tape = mg.color("tape", (0.47, 0.35, 0.20), rough=0.7)
    ear = mg.color("cat_fur", (0.42, 0.52, 0.47), rough=0.8)
    eye = mg.color("eye_glow", (0.25, 1.0, 0.25), rough=0.3, glow=3.0)

    parts = []

    def box(loc, size, rot=0.0):
        w, d, h = size
        cx, cy, cz = loc
        parts.append(mg.part("cube", card, loc=loc, scale=size, rot=(0, 0, rot), bevel=0.02))
        # tape seam across the top (running along X, narrow in Y)
        tz = cz + h / 2 - 0.005
        parts.append(mg.part("cube", tape, loc=(cx, cy, tz + 0.008),
                             scale=(w + 0.012, d * 0.22, 0.02), rot=(0, 0, rot)))
        if mg.at_least("mobile-high"):
            # tape running down the front face
            fy = cy - math.cos(rot) * d / 2 - math.sin(rot) * 0.0
            parts.append(mg.part("cube", tape, loc=(cx, cy - d / 2 - 0.004, cz + h * 0.15),
                                 scale=(w * 0.22, 0.02, h * 0.7), rot=(0, 0, rot)))

    # bottom row
    box((-0.62, 0.00, 0.30), (0.55, 0.60, 0.60), rot=0.04)
    box((0.05, 0.05, 0.28), (0.78, 0.70, 0.56), rot=-0.02)
    box((0.62, -0.16, 0.27), (0.50, 0.50, 0.54), rot=0.10)

    # top row
    box((-0.35, 0.06, 0.90), (0.60, 0.60, 0.58), rot=-0.03)
    cat = (0.35, -0.05, 0.88)
    cbw = 0.56
    box(cat, (0.55, cbw, 0.56), rot=0.02)

    # dented corners (small pushed-in cubes) at higher tiers
    if mg.at_least("mobile-mid"):
        for (dx, dy, dz) in [(-0.85, -0.28, 0.05), (0.80, -0.38, 0.03),
                             (-0.12, 0.58, 1.15), (0.60, -0.30, 1.13)]:
            parts.append(mg.part("cube", card, loc=(dx, dy, dz),
                                 scale=(0.14, 0.14, 0.14), rot=(0.6, 0.5, 0.3), bevel=0.03))

    cx, cy, cz = cat
    top_z = cz + 0.28
    front_y = cy - cbw / 2

    # zombie cat: pointed ears poking out of the top
    for sx in (-1, 1):
        parts.append(mg.part("cone", ear, loc=(cx + sx * 0.12, cy + 0.10, top_z + 0.10),
                             scale=(0.15, 0.15, 0.26), rot=(0.12 * sx, 0.10 * sx, 0)))
    # glowing green eyes on the front face
    for sx in (-1, 1):
        parts.append(mg.part("sphere", eye, loc=(cx + sx * 0.09, front_y + 0.01, cz + 0.10),
                             scale=(0.06, 0.06, 0.06)))

    mg.join("zc_cardboard_barricade", parts)
