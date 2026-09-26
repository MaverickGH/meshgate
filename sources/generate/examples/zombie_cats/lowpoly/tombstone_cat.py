"""Cat-shaped tombstone: pointed-ear stone slab with a carved paw print on a low base, oozing glowing green goo."""
import math


def build(mg):
    mg.color("stone", "#6a6d72", rough=0.9)
    mg.color("stone_lit", "#7c8086", rough=0.9)
    mg.color("paw", "#34363b", rough=0.95)
    mg.color("goo", "#7ce000", rough=0.35, glow=2.2)
    mg.color("goo_dk", "#57b400", rough=0.4, glow=1.4)

    parts = []

    # low stone base
    parts.append(mg.part("cube", "stone", loc=(0, 0, 0.07), scale=(0.7, 0.28, 0.14), bevel=0.02))
    parts.append(mg.part("cube", "stone_lit", loc=(0, 0, 0.135), scale=(0.66, 0.24, 0.02), bevel=0.01))

    # slab silhouette with two pointed cat ears (front view = XZ)
    outline = [
        (-0.30, 0.13), (-0.31, 0.55), (-0.30, 0.82),
        (-0.29, 1.05),                      # left ear tip
        (-0.13, 0.84), (0.00, 0.90), (0.13, 0.84),
        (0.29, 1.05),                       # right ear tip
        (0.30, 0.82), (0.31, 0.55), (0.30, 0.13),
    ]
    parts.append(mg.extrude(outline, 0.15, "stone", bevel=0.014))

    # faceted rock chips on richer tiers
    if mg.at_least("mobile-high"):
        for x, z, s in [(-0.31, 0.35, 0.06), (0.31, 0.62, 0.05), (-0.30, 0.72, 0.05),
                        (0.30, 0.28, 0.06), (-0.34, 0.05, 0.05)]:
            parts.append(mg.part("ico", "stone_lit",
                                 loc=(x, mg.rng.uniform(-0.05, 0.05), z),
                                 scale=(s, 0.12, s),
                                 rot=(0, 0, mg.rng.uniform(0, 1.0))))

    # carved paw print on the front face (front = -Y)
    fy = -0.055
    parts.append(mg.part("sphere", "paw", loc=(0, fy, 0.54), scale=(0.17, 0.07, 0.15)))
    toes = [(-0.115, 0.70), (-0.04, 0.75), (0.04, 0.75), (0.115, 0.70)]
    for tx, tz in toes:
        parts.append(mg.part("sphere", "paw", loc=(tx, fy, tz), scale=(0.075, 0.06, 0.09)))

    body = mg.join("zc_tombstone_cat", parts)

    # puddle of glowing green goo at the front-left, with a drip down the base
    goo = []
    goo.append(mg.part("sphere", "goo", loc=(-0.02, -0.22, 0.015), scale=(0.34, 0.30, 0.05)))
    goo.append(mg.part("sphere", "goo", loc=(-0.20, -0.16, 0.012), scale=(0.14, 0.14, 0.04)))
    goo.append(mg.part("sphere", "goo_dk", loc=(0.14, -0.20, 0.012), scale=(0.12, 0.12, 0.04)))
    # drip running down the front of the base
    goo.append(mg.part("cube", "goo", loc=(-0.05, -0.15, 0.09), scale=(0.06, 0.03, 0.16), bevel=0.02))
    goo.append(mg.part("sphere", "goo", loc=(-0.05, -0.15, 0.02), scale=(0.10, 0.08, 0.05)))
    if mg.at_least("mobile-mid"):
        for i in range(5):
            gx = mg.rng.uniform(-0.28, 0.22)
            gy = mg.rng.uniform(-0.30, -0.10)
            r = mg.rng.uniform(0.03, 0.06)
            goo.append(mg.part("sphere", "goo_dk", loc=(gx, gy, 0.01), scale=(r, r, 0.03)))
    goo_mesh = mg.join("zc_tombstone_goo", goo)
    mg.attach(goo_mesh, body)
