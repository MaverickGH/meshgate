"""zc_toxic_can — giant opened cat-food tin with glowing toxic goo and a peeled-back lid."""
import math


def build(mg):
    metal = mg.color("metal", "#9a9ba3", rough=0.4, metal=1.0)
    purple = mg.color("purple", "#5b2a86", rough=0.55)
    goo = mg.color("goo", "#63c93a", rough=0.3, glow=1.7)
    fish = mg.color("fish", "#2c7fae", rough=0.5)

    R, H = 0.28, 0.68
    parts = []

    # can body (metal) with purple label band in the middle
    parts.append(mg.part("cyl", metal, loc=(0, 0, H / 2), scale=(2 * R, 2 * R, H), bevel=0.008))
    parts.append(mg.part("cyl", purple, loc=(0, 0, 0.34), scale=(2 * R + 0.01, 2 * R + 0.01, 0.44)))
    # rim lips top and bottom
    parts.append(mg.part("torus", metal, loc=(0, 0, H - 0.01), major_radius=R - 0.01, minor_radius=0.022))
    parts.append(mg.part("torus", metal, loc=(0, 0, 0.03), major_radius=R - 0.01, minor_radius=0.022))

    # toxic goo surface sitting just inside the rim
    parts.append(mg.part("cyl", goo, loc=(0, 0, H - 0.03), scale=(2 * (R - 0.02), 2 * (R - 0.02), 0.05)))

    # goo bubbling up on top
    for i in range(5):
        a = i / 5 * math.tau + 0.4
        rr = mg.rng.uniform(0.05, 0.16)
        s = mg.rng.uniform(0.03, 0.06)
        parts.append(mg.part("sphere", goo, loc=(math.cos(a) * rr, math.sin(a) * rr, H - 0.01 + s * 0.4),
                             scale=(s, s, s)))
    if mg.at_least("mobile-mid"):
        # goo bulging / spilling over the front rim edge
        for a in (-0.5, -0.1, 0.35):
            parts.append(mg.part("sphere", goo, loc=(math.sin(a) * R, -math.cos(a) * R, H - 0.02),
                                 scale=(0.11, 0.11, 0.07)))
        # a drip running down the front
        parts.append(mg.tube([(-0.06, -R - 0.01, H - 0.05), (-0.07, -R - 0.02, H - 0.28),
                              (-0.06, -R - 0.02, H - 0.45)], 0.03, goo, sides=8))

    # green puddles on the ground
    for (px, py, sx, sy) in [(-0.02, -0.38, 0.28, 0.22), (0.30, -0.22, 0.20, 0.16),
                             (-0.34, 0.05, 0.18, 0.15), (0.12, 0.30, 0.16, 0.13)]:
        parts.append(mg.part("sphere", goo, loc=(px, py, 0.015), scale=(sx, sy, 0.05)))

    # blue fish picture on the label front (-Y)
    fish_outline = [(-0.10, 0.0), (-0.07, 0.045), (0.0, 0.055), (0.055, 0.03),
                    (0.055, 0.065), (0.11, 0.055), (0.11, -0.055), (0.055, -0.065),
                    (0.055, -0.03), (0.0, -0.055), (-0.07, -0.045)]
    parts.append(mg.extrude(fish_outline, 0.04, fish, loc=(-0.01, -R + 0.01, 0.36),
                            bevel=0.006, smooth=True))

    # small rivets around the top rim (detail)
    if mg.at_least("mobile-high"):
        for i in range(12):
            a = i / 12 * math.tau
            parts.append(mg.part("sphere", metal, loc=(math.cos(a) * R, math.sin(a) * R, 0.03),
                                 scale=(0.02, 0.02, 0.02)))

    # peeled-back lid standing behind the can, hinged at the back rim
    t = 0.8
    cy = 0.28 + 0.28 * math.sin(t)
    cz = H + 0.28 * math.cos(t)
    parts.append(mg.part("cyl", metal, loc=(0, cy, cz), scale=(2 * R, 2 * R, 0.02),
                         rot=(math.pi / 2 + t, 0, 0), bevel=0.01))
    parts.append(mg.part("torus", metal, loc=(0, cy, cz), major_radius=R - 0.005, minor_radius=0.02,
                         rot=(math.pi / 2 + t, 0, 0)))

    mg.join("zc_toxic_can", parts)
