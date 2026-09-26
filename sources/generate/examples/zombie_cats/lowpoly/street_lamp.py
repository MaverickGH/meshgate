"""zc_street_lamp — street lamp: pole on round base, rust band, curved arm, fish lantern glowing warm yellow."""
import math


def build(mg):
    metal = mg.color("metal", "#8b9097", rough=0.5, metal=0.9)
    dark = mg.color("metal_dk", "#6a6f76", rough=0.55, metal=0.9)
    rust = mg.color("rust", "#9c4a24", rough=0.85, metal=0.1)
    fish = mg.color("fish", "#4d7ba8", rough=0.5, metal=0.1)
    fin = mg.color("fin", "#3f6a94", rough=0.5, metal=0.1)
    glow = mg.color("glow", "#ffcf5c", rough=0.4, glow=2.4)

    top = 3.02
    parts = []

    # round base
    parts.append(mg.lathe([(0, 0), (0.22, 0), (0.22, 0.05), (0.18, 0.07),
                           (0.09, 0.085), (0.05, 0.09)], metal,
                          loc=(0, 0, 0), segments=mg.seg(20)))

    # pole
    parts.append(mg.part("cyl", metal, loc=(0, 0, top / 2 + 0.05),
                         scale=(0.08, 0.08, top), vertices=mg.seg(14)))

    # rust band low on the pole
    parts.append(mg.part("cyl", rust, loc=(0, 0, 0.9),
                         scale=(0.088, 0.088, 0.14), vertices=mg.seg(14)))

    # curved arm reaching to the front (-Y)
    arm = [(0, 0, top - 0.05), (0, 0, top + 0.06), (0, -0.12, top + 0.09),
           (0, -0.35, top + 0.04), (0, -0.52, top - 0.02)]
    parts.append(mg.tube(arm, 0.038, metal, sides=mg.seg(10)))

    # drop connector holding the lantern
    parts.append(mg.part("cyl", dark, loc=(0, -0.52, top - 0.12),
                         scale=(0.03, 0.03, 0.22), vertices=mg.seg(8)))

    # fish lantern -------------------------------------------------
    fx, fy, fz = 0, -0.52, top - 0.30
    # body
    parts.append(mg.part("sphere", fish, loc=(fx, fy, fz),
                         scale=(0.17, 0.34, 0.17),
                         segments=mg.seg(14), ring_count=mg.seg(10)))
    # pointed head/nose to the front
    parts.append(mg.part("cone", fish, loc=(fx, fy - 0.20, fz),
                         scale=(0.15, 0.15, 0.14), rot=(math.pi / 2, 0, 0),
                         vertices=mg.seg(12)))
    # glowing warm-yellow belly
    parts.append(mg.part("sphere", glow, loc=(fx, fy, fz - 0.08),
                         scale=(0.155, 0.30, 0.09),
                         segments=mg.seg(14), ring_count=mg.seg(8)))
    # tail fin (vertical sheet) at the back
    tail = [(0, -0.03), (0, 0.03), (0.22, 0.15), (0.22, -0.15)]
    parts.append(mg.extrude(tail, 0.02, fin, loc=(fx, fy + 0.16, fz),
                            rot=(0, 0, math.pi / 2)))

    if mg.at_least("mobile-high"):
        # small side fins
        pf = [(0, 0), (0.12, 0.06), (0.11, -0.05)]
        f1 = mg.extrude(pf, 0.015, fin, loc=(0.13, fy, fz - 0.02),
                        rot=(0, 0.5, math.pi / 2))
        parts.append(f1)
        parts.append(mg.mirror_x(f1))
        # top fin
        parts.append(mg.extrude([(0, 0), (-0.05, 0.10), (0.08, 0.09), (0.06, 0)],
                                0.02, fin, loc=(0, fy, fz + 0.15)))

    mg.join("zc_street_lamp", parts)
