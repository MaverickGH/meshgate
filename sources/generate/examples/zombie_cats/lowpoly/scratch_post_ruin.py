"""zc_scratch_post_ruin — ruined cat scratching post: carpeted base, rope pole, tilted top, side shelf."""
import math


def build(mg):
    pink = mg.color("fabric_pink", "#c46fc4", rough=0.9)
    pink_dk = mg.color("fabric_pink_dark", "#9c4f9e", rough=0.9)
    board = mg.color("fabric_pink_edge", (0.4, 0.14, 0.26), rough=0.85)
    rope = mg.color("rope", (0.83, 0.66, 0.44), rough=0.85, material="fabric")
    rope_dk = mg.color("rope_dark", (0.58, 0.44, 0.28), rough=0.9, material="fabric")
    metal = mg.color("iron", (0.55, 0.57, 0.6), rough=0.4, metal=1.0)

    parts = []

    # ---- carpeted square base ----
    bw = 0.5
    parts.append(mg.part("cube", board, loc=(0, 0, 0.02), scale=(bw + 0.02, bw + 0.02, 0.04)))
    parts.append(mg.part("cube", pink, loc=(0, 0, 0.075), scale=(bw, bw, 0.075), bevel=0.02, taper=0.9))
    parts.append(mg.part("cube", pink_dk, loc=(0, 0, 0.045), scale=(bw + 0.01, bw + 0.01, 0.03)))

    # ---- central pole core ----
    pole_z0, pole_z1 = 0.08, 1.02
    parts.append(mg.part("cyl", rope_dk, loc=(0, 0, (pole_z0 + pole_z1) / 2),
                         scale=(0.1, 0.1, pole_z1 - pole_z0), vertices=10, smooth=False))

    # ---- sisal rope helix wrapped around the pole ----
    turns = 11
    rr = 0.075
    minor = 0.028
    seg = mg.seg(6)
    n = turns * seg
    pts, radii = [], []
    for i in range(n + 1):
        t = i / n
        ang = t * turns * 2 * math.pi
        z = pole_z0 + t * (pole_z1 - pole_z0)
        fray = 1.0 + 0.18 * math.sin(t * 40.0) + mg.rng.uniform(-0.06, 0.06)
        pts.append((rr * math.cos(ang), rr * math.sin(ang), z))
        radii.append(minor * fray)
    parts.append(mg.tube(pts, 0, rope, sides=6, radii=radii, smooth=False, cap=True))

    # frayed rope wisps sticking out (higher tiers)
    if mg.at_least("mobile-high"):
        for k in range(5):
            zz = mg.rng.uniform(pole_z0 + 0.1, pole_z1 - 0.1)
            a = mg.rng.uniform(0, 2 * math.pi)
            bx, by = rr * math.cos(a), rr * math.sin(a)
            tip = (bx * 2.2 + mg.rng.uniform(-0.03, 0.03), by * 2.2, zz + mg.rng.uniform(-0.04, 0.04))
            parts.append(mg.tube([(bx, by, zz), tip], 0.008, rope_dk, sides=4, smooth=False))

    # ---- side shelf on the viewer's left (-X), cracked ----
    sh_z = 0.5
    sh = mg.part("cube", pink, loc=(-0.28, 0.0, sh_z), scale=(0.34, 0.28, 0.05), bevel=0.012, taper=0.94)
    parts.append(sh)
    parts.append(mg.part("cube", pink_dk, loc=(-0.28, 0.0, sh_z - 0.03), scale=(0.35, 0.29, 0.02)))
    if mg.at_least("mobile-mid"):
        # crack across the shelf top
        parts.append(mg.part("cube", board, loc=(-0.3, 0.02, sh_z + 0.028),
                             scale=(0.02, 0.2, 0.01), rot=(0, 0, 0.4)))

    # ---- tilted top platform ----
    top_z = 1.08
    tp = mg.part("cube", pink, loc=(0, 0, top_z), scale=(0.5, 0.42, 0.06),
                 rot=(0.11, 0.05, 0.0), bevel=0.018, taper=0.93)
    parts.append(tp)
    parts.append(mg.part("cube", pink_dk, loc=(0, 0, top_z - 0.04), scale=(0.5, 0.42, 0.03),
                         rot=(0.11, 0.05, 0.0)))
    # small screw/bolt on top
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cyl", metal, loc=(-0.05, -0.02, top_z + 0.06),
                             scale=(0.05, 0.05, 0.02), rot=(0.11, 0.05, 0.0), vertices=8))

    # ---- torn carpet tufts around base edge ----
    if mg.at_least("mobile-high"):
        for k in range(8):
            a = mg.rng.uniform(0, 2 * math.pi)
            ex = (bw / 2) * (1 if math.cos(a) > 0 else -1) * mg.rng.uniform(0.7, 1.0)
            ey = (bw / 2) * (1 if math.sin(a) > 0 else -1) * mg.rng.uniform(0.7, 1.0)
            parts.append(mg.part("cube", pink, loc=(ex, ey, 0.11),
                                 scale=(0.03, 0.03, mg.rng.uniform(0.02, 0.05)),
                                 rot=(mg.rng.uniform(-0.4, 0.4), mg.rng.uniform(-0.4, 0.4), 0)))

    mg.join("zc_scratch_post_ruin", parts)
