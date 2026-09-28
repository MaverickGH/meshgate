"""zc_scratch_post_ruin — ruined cat scratching post: pink carpet base/top/shelf, frayed sisal rope pole."""
import math


def build(mg):
    carpet = mg.color("carpet_fabric", "#c46fc4", rough=0.85, material="fabric")
    carpet_dk = mg.color("carpet_fabric_dark", "#9c4f9e", rough=0.9, material="fabric")
    rope = mg.color("sisal", (0.83, 0.66, 0.42), rough=0.9, material="fabric")
    rope_dk = mg.color("sisal_dark", (0.68, 0.51, 0.30), rough=0.95, material="fabric")
    metal = mg.color("metal", (0.72, 0.73, 0.76), rough=0.35, metal=1.0)

    parts = []
    rng = mg.rng

    # ---- base: square carpeted slab ----
    bw, bt = 0.56, 0.11
    parts.append(mg.part("cube", carpet, loc=(0, 0, bt / 2), scale=(bw, bw, bt), bevel=0.02))
    parts.append(mg.part("cube", carpet_dk, loc=(0, 0, 0.012), scale=(bw + 0.01, bw + 0.01, 0.024), bevel=0.01))
    # torn carpet chunks around base edge
    if mg.at_least("mobile-mid"):
        for i in range(7):
            a = rng.uniform(0, math.tau)
            r = bw / 2 - 0.02
            parts.append(mg.part("cube", carpet_dk,
                                 loc=(math.cos(a) * r, math.sin(a) * r, bt + 0.01),
                                 scale=(0.05, 0.05, 0.03), rot=(0, 0, a), bevel=0.008))

    # ---- rope pole ----
    z0, z1 = bt - 0.01, 1.00
    parts.append(mg.part("cyl", rope_dk, loc=(0, 0, (z0 + z1) / 2),
                         scale=(0.20, 0.20, z1 - z0), vertices=20, bevel=0.005))
    # coiled rope rings stacked up the pole (frayed = varied)
    step = 0.066
    z = z0 + 0.03
    while z < z1 - 0.02:
        wob = rng.uniform(-0.006, 0.006)
        minr = 0.030 + rng.uniform(-0.006, 0.004)
        col = rope if rng.random() > 0.25 else rope_dk
        parts.append(mg.part("torus", col, loc=(wob, wob, z),
                             major_radius=0.128, minor_radius=minr, exact=False))
        z += step + rng.uniform(-0.006, 0.006)
    # frayed rope strands sticking out
    if mg.at_least("mobile-high"):
        for i in range(10):
            a = rng.uniform(0, math.tau)
            zz = rng.uniform(z0 + 0.1, z1 - 0.1)
            r = 0.135
            p0 = (math.cos(a) * 0.12, math.sin(a) * 0.12, zz)
            p1 = (math.cos(a) * r, math.sin(a) * r, zz + rng.uniform(-0.03, 0.03))
            parts.append(mg.tube([p0, p1], 0.008, rope, sides=5))

    # ---- side shelf (left = -X), cracked ----
    sx, sz = -0.30, 0.52
    parts.append(mg.part("cube", carpet, loc=(sx, 0, sz), scale=(0.34, 0.30, 0.06), bevel=0.015))
    parts.append(mg.part("cube", carpet_dk, loc=(sx, 0, sz - 0.03), scale=(0.35, 0.31, 0.02), bevel=0.01))
    # crack / broken corner chunk
    parts.append(mg.part("cube", carpet_dk, loc=(sx - 0.16, 0.12, sz),
                         scale=(0.05, 0.06, 0.065), rot=(0, 0, 0.5)))
    if mg.at_least("mobile-mid"):
        for i in range(3):
            parts.append(mg.part("cube", carpet_dk,
                                 loc=(sx + rng.uniform(-0.1, 0.1), 0.14, sz + 0.03),
                                 scale=(0.02, 0.04, 0.02), rot=(0, 0, rng.uniform(0, 1))))

    # ---- tilted top platform ----
    tz = 1.09
    tilt = (0.09, 0.0, 0.05)
    parts.append(mg.part("cube", carpet, loc=(0, 0, tz), scale=(0.60, 0.44, 0.07),
                         rot=tilt, bevel=0.02))
    parts.append(mg.part("cube", carpet_dk, loc=(0, 0, tz - 0.035), scale=(0.61, 0.45, 0.025),
                         rot=tilt, bevel=0.012))

    # ---- small metal bits (staples / rivets on top & base) ----
    if mg.at_least("mobile-mid"):
        parts.append(mg.part("ico", metal, loc=(-0.06, -0.05, tz + 0.05), scale=(0.05, 0.05, 0.035)))
        parts.append(mg.part("ico", metal, loc=(0.20, 0.18, bt + 0.02), scale=(0.03, 0.03, 0.02)))

    mg.join("zc_scratch_post_ruin", parts)
