"""Giant opened cat-food tin: metal can, purple fish label, glowing toxic goo, peeled lid, puddles."""
import math


def build(mg):
    steel = mg.color("steel", (0.62, 0.63, 0.66), rough=0.4, metal=1.0)
    purple = mg.color("purple", (0.34, 0.14, 0.5), rough=0.55)
    goo = mg.color("goo", (0.32, 0.82, 0.18), rough=0.3, glow=1.6)
    fish = mg.color("fish", (0.2, 0.45, 0.68), rough=0.5)

    R, H = 0.22, 0.70
    parts = []

    # ---- can body (metal) ----
    parts.append(mg.part("cyl", steel, loc=(0, 0, H / 2), scale=(2 * R, 2 * R, H), bevel=0.006))
    # top lip rim
    parts.append(mg.part("torus", steel, loc=(0, 0, H), scale=(1, 1, 0.5),
                         major_radius=R - 0.012, minor_radius=0.02))

    # ---- purple label band ----
    lz0, lz1 = 0.09, 0.60
    parts.append(mg.part("cyl", purple, loc=(0, 0, (lz0 + lz1) / 2),
                         scale=(2 * (R + 0.006), 2 * (R + 0.006), lz1 - lz0)))

    # ---- fish picture on the label front (-Y) ----
    if mg.at_least("mobile-mid"):
        outline = [(-0.09, 0.04), (-0.04, 0.0), (-0.09, -0.04), (-0.04, -0.035),
                   (0.04, -0.045), (0.08, -0.02), (0.09, 0.0), (0.08, 0.02),
                   (0.04, 0.045), (-0.04, 0.035)]
        parts.append(mg.extrude(outline, 0.02, fish, loc=(-0.01, -(R - 0.005), 0.35)))

    # ---- glowing goo domed over the open top ----
    parts.append(mg.part("sphere", goo, loc=(0, 0, H - 0.04),
                         scale=(2 * (R - 0.018), 2 * (R - 0.018), 0.13)))
    # blobs / bubbles on the goo surface
    for x, y, s in ((0.06, -0.05, 0.05), (-0.07, 0.05, 0.045), (0.02, 0.09, 0.035)):
        parts.append(mg.part("sphere", goo, loc=(x, y, H + 0.02), scale=(s, s, s)))
    if mg.at_least("mobile-high"):
        for i in range(6):
            a = mg.rng.uniform(0, math.tau)
            rr = mg.rng.uniform(0.04, 0.14)
            s = mg.rng.uniform(0.02, 0.04)
            parts.append(mg.part("sphere", goo,
                                 loc=(math.cos(a) * rr, math.sin(a) * rr, H + 0.01),
                                 scale=(s, s, s)))

    # ---- goo spilling over the rim ----
    if mg.at_least("mobile-mid"):
        for x in (-0.08, 0.10):
            zt = H + 0.01
            parts.append(mg.tube([(x, -R + 0.01, zt), (x + 0.01, -R - 0.02, zt - 0.08),
                                  (x, -R - 0.01, zt - 0.18)], 0.03, goo, sides=8))

    # ---- peeled lid standing up behind ----
    th = -2.2
    ly = R - R * math.cos(th)
    lz = H - R * math.sin(th)
    parts.append(mg.part("cyl", steel, loc=(0, ly, lz), rot=(th, 0, 0),
                         scale=(2 * (R + 0.02), 2 * (R + 0.02), 0.02), bevel=0.005))
    parts.append(mg.part("torus", steel, loc=(0, ly, lz), rot=(th, 0, 0),
                         scale=(1, 1, 0.6), major_radius=R + 0.02, minor_radius=0.015))

    # ---- puddles on the ground ----
    for x, y, sx, sy in ((0.0, -0.32, 0.22, 0.15), (-0.26, -0.12, 0.15, 0.12),
                         (0.24, -0.20, 0.14, 0.11)):
        parts.append(mg.part("sphere", goo, loc=(x, y, 0.02), scale=(sx, sy, 0.05)))

    mg.join("zc_toxic_can", parts)
