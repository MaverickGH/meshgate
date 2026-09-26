"""Street lamp 3.2 m: metal pole on round base, curved arm, fish-shaped lantern glowing warm yellow, rust band low on pole."""
import math


def build(mg):
    steel = mg.color("steel", "#8a9098", rough=0.45, metal=1.0)
    steel_d = mg.color("steel_d", "#6b7178", rough=0.5, metal=1.0)
    rust = mg.color("rust", "#8a4a28", rough=0.8, metal=0.1)
    fish = mg.color("fish", "#4f7fa8", rough=0.5, metal=0.2)
    fish_d = mg.color("fish_d", "#3a5f82", rough=0.55, metal=0.2)
    glow = mg.color("glow", "#ffd066", rough=0.4, glow=2.5)

    top = 2.88
    parts = []

    # round base
    parts.append(mg.lathe([(0.0, 0.0), (0.18, 0.0), (0.18, 0.05),
                           (0.14, 0.06), (0.05, 0.07)], steel_d, segments=mg.seg(24)))
    # pole
    parts.append(mg.part("cyl", steel, loc=(0, 0, top / 2 + 0.05),
                         scale=(0.07, 0.07, top), vertices=mg.seg(16)))
    # rust band low on pole
    parts.append(mg.part("cyl", rust, loc=(0, 0, 0.85),
                         scale=(0.076, 0.076, 0.16), vertices=mg.seg(16)))

    # curved arm: from pole top forward (-Y) and slightly up
    arm_pts = []
    for i in range(9):
        t = i / 8.0
        ang = t * (math.pi / 2)
        x = 0.0
        y = -0.55 * math.sin(ang)
        z = top + 0.10 + 0.18 * (1 - math.cos(ang)) - 0.02 * t
        arm_pts.append((x, y, z))
    parts.append(mg.tube(arm_pts, 0.045, steel, sides=mg.seg(12)))

    arm_end = arm_pts[-1]
    # short dropper connecting arm to lantern
    lx, ly = arm_end[0], arm_end[1]
    lz = arm_end[2] - 0.28
    parts.append(mg.part("cyl", steel_d, loc=(lx, ly, arm_end[2] - 0.12),
                         scale=(0.02, 0.02, 0.24), vertices=mg.seg(8)))

    # fish lantern body (ellipsoid along Y), nose to -Y, tail to +Y
    body = mg.part("sphere", fish, loc=(lx, ly, lz),
                   scale=(0.24, 0.42, 0.24), segments=mg.seg(24))
    parts.append(body)
    # glowing warm-yellow belly underside
    parts.append(mg.part("sphere", glow, loc=(lx, ly, lz - 0.06),
                         scale=(0.20, 0.34, 0.14), segments=mg.seg(20)))
    # tail fin (triangular) at +Y back
    parts.append(mg.extrude([(0.0, 0.0), (0.22, 0.10), (0.22, -0.10)], 0.02, fish_d,
                            loc=(lx, ly + 0.20, lz), rot=(0, math.pi / 2, 0)))

    if mg.at_least("mobile-high"):
        # small side fins
        fin = mg.extrude([(0.0, 0.0), (0.12, 0.05), (0.10, -0.05)], 0.015, fish_d,
                         loc=(lx + 0.16, ly, lz - 0.02), rot=(0, 0, 0))
        parts.append(fin)
        parts.append(mg.mirror_x(fin))
        # rim ring under belly
        parts.append(mg.part("torus", steel_d, loc=(lx, ly, lz - 0.12),
                             scale=(0.30, 0.42, 0.30), major_radius=0.5, minor_radius=0.04))

    mg.join("zc_street_lamp", parts)
