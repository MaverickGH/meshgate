"""Ruined cat scratching post: carpeted base + rope pole + tilted top platform + cracked side shelf."""
import math


def build(mg):
    carpet = mg.color("carpet", "#8a5878", rough=0.92)
    carpet_dk = mg.color("carpet_dk", "#5f3a54", rough=0.95)
    rope = mg.color("rope", "#a99a63", rough=0.85)
    rope_dk = mg.color("rope_dk", "#7d7042", rough=0.9)

    parts = []

    # ---- carpeted square base ----
    bw, bt = 0.55, 0.05
    parts.append(mg.part("cube", carpet, loc=(0, 0, bt / 2), scale=(bw, bw, bt), bevel=0.012))
    # torn carpet edge chunk (darker underside showing)
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", carpet_dk, loc=(bw / 2 - 0.02, 0.16, bt / 2 + 0.006),
                             scale=(0.09, 0.11, bt - 0.01), rot=(0, 0, 0.3), bevel=0.006))

    # ---- rope-wrapped pole ----
    pz0, pz1 = bt, 1.0
    pr = 0.065
    parts.append(mg.part("cyl", rope_dk, loc=(0, 0, (pz0 + pz1) / 2),
                         scale=(pr * 1.6, pr * 1.6, pz1 - pz0), vertices=20))
    # rope coils as stacked tori
    coil = 0.075
    n = int((pz1 - pz0) / coil)
    for i in range(n):
        z = pz0 + coil * (i + 0.5)
        col = rope if i % 2 == 0 else rope_dk
        r = pr * 1.05
        # frayed near top: some coils loosen / shrink
        if i >= n - 2 and mg.at_least("mobile-mid"):
            r *= 0.9
        parts.append(mg.part("torus", col, loc=(0, 0, z),
                             major_radius=r, minor_radius=coil * 0.55,
                             rot=(0, 0, mg.rng.uniform(0, 1))))
    # frayed rope strands at the top
    if mg.at_least("mobile-high"):
        for k in range(6):
            a = k / 6 * math.tau
            x, y = math.cos(a) * pr, math.sin(a) * pr
            parts.append(mg.tube([(x, y, pz1 - 0.02),
                                   (x * 1.5, y * 1.5, pz1 + 0.04),
                                   (x * 1.9 + mg.rng.uniform(-0.02, 0.02),
                                    y * 1.9 + mg.rng.uniform(-0.02, 0.02), pz1 + 0.09)],
                                  0, rope, radii=[0.012, 0.008, 0.002], sides=5))

    # ---- tilted top platform ----
    tw, tt = 0.5, 0.045
    tz = pz1 + 0.06
    tilt = 0.14
    parts.append(mg.part("cube", carpet, loc=(0, -0.02, tz), scale=(tw, tw, tt),
                         rot=(tilt, 0.05, 0.0), bevel=0.012))
    # little worn scuff mark on top
    if mg.at_least("mobile-high"):
        parts.append(mg.part("cyl", rope, loc=(-0.09, -0.06, tz + tt / 2 + 0.002),
                             scale=(0.06, 0.03, 0.006), rot=(tilt, 0.05, 0.4), vertices=10))

    # ---- cracked side shelf ----
    sw, st = 0.34, 0.04
    sz = 0.55
    sx = -pr - sw / 2 + 0.03
    parts.append(mg.part("cube", carpet, loc=(sx, 0.03, sz), scale=(sw, sw * 0.85, st),
                         rot=(-0.02, 0.02, 0.0), bevel=0.01))
    # crack: a dark wedge cut across the shelf
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("cube", carpet_dk, loc=(sx - 0.02, 0.03, sz + st / 2 - 0.006),
                             scale=(0.02, sw * 0.85, st * 0.7), rot=(0, 0, 0.35), bevel=0.003))
    # broken corner chunk hanging off the shelf
    if mg.at_least("mobile-high"):
        parts.append(mg.part("cube", carpet, loc=(sx - sw / 2 + 0.03, 0.03 - sw * 0.4, sz - 0.03),
                             scale=(0.08, 0.09, st * 0.9), rot=(0.3, 0, 0.2), bevel=0.006))

    mg.join("zc_scratch_post_ruin", parts)
