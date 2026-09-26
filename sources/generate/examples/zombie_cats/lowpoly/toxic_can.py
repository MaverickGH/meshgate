"""Giant opened cat-food tin: purple label, glowing green toxic goo, peeled-back lid, puddles."""
import math


def build(mg):
    steel = mg.color("steel", (0.55, 0.56, 0.60), rough=0.4, metal=1.0)
    purple = mg.color("purple", (0.35, 0.12, 0.45), rough=0.6)
    goo = mg.color("goo", (0.45, 0.80, 0.15), rough=0.35, glow=1.6)
    fish = mg.color("fish", (0.15, 0.45, 0.65), rough=0.6)

    R = 0.28          # can radius
    body_h = 0.72     # cylinder height
    ground = 0.0

    parts = []
    # metal can wall (slightly larger than the label)
    parts.append(mg.part("cyl", steel, loc=(0, 0, body_h / 2),
                         scale=(2 * R, 2 * R, body_h), vertices=24))
    # purple label band wrapping the middle
    parts.append(mg.part("cyl", purple, loc=(0, 0, body_h / 2),
                         scale=(2 * R + 0.015, 2 * R + 0.015, body_h * 0.62), vertices=24))
    # top rim ring (steel lip)
    parts.append(mg.part("cyl", steel, loc=(0, 0, body_h - 0.02),
                         scale=(2 * R + 0.02, 2 * R + 0.02, 0.06), vertices=24))
    # bottom rim
    parts.append(mg.part("cyl", steel, loc=(0, 0, 0.03),
                         scale=(2 * R + 0.02, 2 * R + 0.02, 0.06), vertices=24))

    # fish picture on the label (front, -Y)
    parts.append(mg.part("ico", fish, loc=(-0.06, -R - 0.02, body_h * 0.55),
                         scale=(0.14, 0.05, 0.09)))
    parts.append(mg.extrude([(0.0, 0.0), (0.09, 0.05), (0.09, -0.05)], 0.04, fish,
                            loc=(0.02, -R - 0.02, body_h * 0.55)))

    # toxic goo pooled at the top, filling the tin
    parts.append(mg.part("cyl", goo, loc=(0, 0, body_h - 0.03),
                         scale=(2 * R - 0.01, 2 * R - 0.01, 0.06), vertices=24))
    # goo dome / spill over the rim
    parts.append(mg.part("sphere", goo, loc=(0, 0, body_h),
                         scale=(2 * R - 0.02, 2 * R - 0.02, 0.12)))

    # bubbles on the goo surface
    if mg.at_least("mobile-mid"):
        for _ in range(6):
            a = mg.rng.uniform(0, math.tau)
            r = mg.rng.uniform(0, R - 0.06)
            s = mg.rng.uniform(0.03, 0.06)
            parts.append(mg.part("sphere", goo,
                                 loc=(math.cos(a) * r, math.sin(a) * r, body_h + 0.02),
                                 scale=(s, s, s)))

    # goo dribbles running down over the rim
    for a in (0.6, 2.4, 4.4):
        x, y = math.cos(a) * (R + 0.005), math.sin(a) * (R + 0.005)
        parts.append(mg.part("sphere", goo, loc=(x, y, body_h - 0.14),
                             scale=(0.06, 0.06, 0.22)))

    # puddles of goo on the ground
    for cx, cy, s in [(0.02, -0.42, 0.24), (-0.30, -0.30, 0.18), (0.34, -0.20, 0.15)]:
        parts.append(mg.part("cyl", goo, loc=(cx, cy, ground + 0.015),
                             scale=(s, s * 0.7, 0.03), vertices=16))
        parts.append(mg.part("sphere", goo, loc=(cx, cy, ground + 0.02),
                             scale=(s * 0.6, s * 0.4, 0.05)))

    can = mg.join("zc_toxic_can", parts)

    # the round lid, peeled back and standing up, hinged at the back rim
    lid_parts = [
        mg.part("cyl", steel, loc=(0, 0, 0), scale=(2 * R + 0.02, 2 * R + 0.02, 0.03),
                rot=(math.pi / 2, 0, 0), vertices=24),
    ]
    lid = mg.join("zc_toxic_can_lid", lid_parts)
    # place lid standing up behind the can and hinge at back top rim
    mg.pivot(lid, (0, R, body_h))
    mg.attach(lid, can)
    mg.animate(lid, "peel",
               [(1, (0, 0, 0)), (30, (-1.9, 0, 0)), (60, (-1.9, 0, 0)), (90, (0, 0, 0))])
